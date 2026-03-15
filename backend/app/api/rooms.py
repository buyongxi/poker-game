import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.schemas.room import RoomCreate, RoomResponse, SeatResponse, JoinRoom, SeatAction, SwitchSeat, RebuyChips
from app.services.room_service import RoomService
from app.api.auth import get_current_active_user
from app.models.room import SeatStatus, RoomStatus

router = APIRouter()
logger = logging.getLogger(__name__)


def seat_to_response(seat) -> dict:
    return {
        "seat_index": seat.seat_index,
        "user_id": seat.user_id,
        "user_name": seat.user_name,
        "chips": seat.chips,
        "net_chips": seat.net_chips,
        "status": seat.status.value if hasattr(seat.status, 'value') else seat.status
    }


async def room_to_response(room) -> dict:
    room_service = RoomService()
    seats = await room_service.get_room_seats(room.id)

    seat_responses = []
    player_count = 0

    for seat in seats:
        if seat.user_id:
            if seat.status != SeatStatus.EMPTY:
                player_count += 1
        seat_responses.append(seat_to_response(seat))

    return {
        "id": room.id,
        "name": room.name,
        "has_password": bool(room.password),
        "small_blind": room.small_blind,
        "big_blind": room.big_blind,
        "max_seats": room.max_seats,
        "max_buyin": room.max_buyin,
        "owner_id": room.owner_id,
        "status": room.status.value if hasattr(room.status, 'value') else room.status,
        "seats": seat_responses,
        "player_count": player_count
    }


@router.post("/", response_model=RoomResponse)
async def create_room(
    room_data: RoomCreate,
    current_user = Depends(get_current_active_user)
):
    """Create a new room."""
    room_service = RoomService()
    try:
        room = await room_service.create_room(room_data, current_user.id, current_user.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await room_to_response(room)


@router.get("/", response_model=List[RoomResponse])
async def list_rooms(
    current_user = Depends(get_current_active_user)
):
    """List all rooms."""
    room_service = RoomService()
    rooms = await room_service.get_all_rooms()
    return [await room_to_response(room) for room in rooms]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: int,
    current_user = Depends(get_current_active_user)
):
    """Get room details."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return await room_to_response(room)


@router.delete("/{room_id}")
async def delete_room(
    room_id: int,
    current_user = Depends(get_current_active_user)
):
    """Delete a room (owner only)."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    if room.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="只有房主可以删除房间")

    if room.status == RoomStatus.PLAYING:
        raise HTTPException(status_code=400, detail="游戏中不能删除房间")

    await room_service.delete_room(room_id)
    return {"message": "房间已删除"}


@router.post("/{room_id}/join", response_model=SeatResponse)
async def join_room(
    room_id: int,
    join_data: JoinRoom,
    current_user = Depends(get_current_active_user)
):
    """Join a room."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    seat, error = await room_service.join_room(room, current_user.id, current_user.display_name, join_data.buyin, join_data.password)
    if not seat:
        raise HTTPException(status_code=400, detail=error)

    return seat_to_response(seat)


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: int,
    current_user = Depends(get_current_active_user)
):
    """Leave a room."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # Check if player can leave
    seat = await room_service.get_user_seat(room, current_user.id)
    if seat:
        if room.status == RoomStatus.PLAYING:
            raise HTTPException(status_code=400, detail="游戏中无法离开房间")
        # Owner can leave even if ready (will transfer ownership)
        # Non-owner must unready first
        if seat.status == SeatStatus.READY and room.owner_id != current_user.id:
            raise HTTPException(status_code=400, detail="请先取消准备后再离开房间")

    success, result = await room_service.leave_room(room_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail=result)

    # Broadcast room state update to other players via WebSocket
    from app.websocket.manager import manager, broadcast_room_state

    logger.debug(f"leave_room: result={result}, room_id={room_id}")

    # Check if room was deleted (all players left)
    if result == "room_deleted":
        await manager.broadcast_to_room(room_id, {
            "type": "room_deleted",
            "data": {"message": "房间已关闭"}
        })
        # Clean up memory
        manager.remove_room(room_id)
    else:
        await broadcast_room_state(room_id)

        # Broadcast owner changed notification
        if result.startswith("owner_transferred:"):
            new_owner_id = int(result.split(":")[1])
            # Get new owner name from room seats
            new_owner_name = f"玩家{new_owner_id}"
            room = await room_service.get_room_by_id(room_id)
            if room:
                for seat in room.seats.values():
                    if seat.user_id == new_owner_id:
                        new_owner_name = seat.user_name or f"玩家{new_owner_id}"
                        break
            logger.debug(f"Broadcasting owner_changed: new_owner_id={new_owner_id}, new_owner_name={new_owner_name}")
            await manager.broadcast_to_room(room_id, {
                "type": "owner_changed",
                "data": {
                    "new_owner_id": new_owner_id,
                    "new_owner_name": new_owner_name
                }
            })
        # Broadcast user left message
        await manager.broadcast_to_room(room_id, {
            "type": "user_left",
            "data": {
                "user_id": current_user.id,
                "username": current_user.display_name
            }
        })

    return {"message": "已离开房间"}


@router.post("/{room_id}/ready")
async def set_ready(
    room_id: int,
    current_user = Depends(get_current_active_user)
):
    """Set player as ready."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    seat = await room_service.update_seat_status(room, current_user.id, SeatStatus.READY)
    if not seat:
        raise HTTPException(status_code=400, detail="你不在该房间中")

    return {"message": "已准备"}


@router.post("/{room_id}/unready")
async def set_unready(
    room_id: int,
    current_user = Depends(get_current_active_user)
):
    """Set player as not ready."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    seat = await room_service.update_seat_status(room, current_user.id, SeatStatus.WAITING)
    if not seat:
        raise HTTPException(status_code=400, detail="你不在该房间中")

    return {"message": "已取消准备"}


@router.post("/{room_id}/switch-seat", response_model=SeatResponse)
async def switch_seat(
    room_id: int,
    data: SwitchSeat,
    current_user = Depends(get_current_active_user)
):
    """Switch to a different seat."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    if room.status == RoomStatus.PLAYING:
        raise HTTPException(status_code=400, detail="游戏中不能切换座位")

    seat, error = await room_service.switch_seat(room, current_user.id, data.seat_index)
    if not seat:
        raise HTTPException(status_code=400, detail=error)

    return seat_to_response(seat)


@router.post("/{room_id}/rebuy", response_model=SeatResponse)
async def rebuy_chips(
    room_id: int,
    data: RebuyChips,
    current_user = Depends(get_current_active_user)
):
    """Rebuy chips when out of chips (only once per hand)."""
    room_service = RoomService()
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    seat, error = await room_service.rebuy_chips(room, current_user.id, data.amount)
    if not seat:
        raise HTTPException(status_code=400, detail=error)

    return seat_to_response(seat)
