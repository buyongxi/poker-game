from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime

from app.database import get_db
from app.schemas.room import RoomCreate, RoomResponse, SeatResponse, JoinRoom, SeatAction, SwitchSeat
from app.services.room_service import RoomService
from app.services.user_service import UserService
from app.api.auth import get_current_active_user
from app.models.room import SeatStatus, RoomStatus

router = APIRouter()


def seat_to_response(seat, user_name: str = None) -> dict:
    return {
        "id": seat.id,
        "seat_index": seat.seat_index,
        "user_id": seat.user_id,
        "user_name": user_name,
        "chips": seat.chips,
        "net_chips": seat.net_chips,
        "status": seat.status.value if hasattr(seat.status, 'value') else seat.status
    }


async def room_to_response(room, db: AsyncSession) -> dict:
    room_service = RoomService(db)
    seats = await room_service.get_room_seats(room.id)

    user_service = UserService(db)
    seat_responses = []
    player_count = 0

    for seat in seats:
        user_name = None
        if seat.user_id:
            user = await user_service.get_user_by_id(seat.user_id)
            user_name = user.display_name if user else None
            if seat.status != SeatStatus.EMPTY:
                player_count += 1

        seat_responses.append(seat_to_response(seat, user_name))

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
        "created_at": room.created_at,
        "seats": seat_responses,
        "player_count": player_count
    }


@router.post("/", response_model=RoomResponse)
async def create_room(
    room_data: RoomCreate,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new room."""
    room_service = RoomService(db)
    room = await room_service.create_room(room_data, current_user.id)
    return await room_to_response(room, db)


@router.get("/", response_model=List[RoomResponse])
async def list_rooms(
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all rooms."""
    room_service = RoomService(db)
    rooms = await room_service.get_all_rooms()
    return [await room_to_response(room, db) for room in rooms]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: int,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get room details."""
    room_service = RoomService(db)
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")
    return await room_to_response(room, db)


@router.delete("/{room_id}")
async def delete_room(
    room_id: int,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a room (owner only)."""
    room_service = RoomService(db)
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
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Join a room."""
    room_service = RoomService(db)
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    seat, error = await room_service.join_room(room, current_user, join_data.buyin, join_data.password)
    if not seat:
        raise HTTPException(status_code=400, detail=error)

    return seat_to_response(seat, current_user.display_name)


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: int,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Leave a room."""
    room_service = RoomService(db)
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    # Check if player can leave
    seat = await room_service.get_user_seat(room, current_user.id)
    if seat:
        if room.status == RoomStatus.PLAYING:
            raise HTTPException(status_code=400, detail="游戏中无法离开房间")
        if seat.status == SeatStatus.READY:
            raise HTTPException(status_code=400, detail="请先取消准备后再离开房间")

    success, error = await room_service.leave_room(room, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail=error)

    return {"message": "已离开房间"}


@router.post("/{room_id}/ready")
async def set_ready(
    room_id: int,
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Set player as ready."""
    room_service = RoomService(db)
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
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Set player as not ready."""
    room_service = RoomService(db)
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
    current_user = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Switch to a different seat."""
    room_service = RoomService(db)
    room = await room_service.get_room_by_id(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="房间不存在")

    if room.status == RoomStatus.PLAYING:
        raise HTTPException(status_code=400, detail="游戏中不能切换座位")

    seat, error = await room_service.switch_seat(room, current_user.id, data.seat_index)
    if not seat:
        raise HTTPException(status_code=400, detail=error)

    return seat_to_response(seat, current_user.display_name)
