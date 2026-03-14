from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.room import Room, Seat, RoomStatus, SeatStatus
from app.models.user import User
from app.schemas.room import RoomCreate
from typing import List, Optional, Tuple
from app.config import settings


class RoomService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room(self, room_data: RoomCreate, owner_id: int) -> Room:
        """Create a new room."""
        room = Room(
            name=room_data.name,
            password=room_data.password,
            small_blind=room_data.small_blind,
            big_blind=room_data.small_blind * 2,
            max_seats=room_data.max_seats,
            max_buyin=room_data.max_buyin,
            owner_id=owner_id,
            status=RoomStatus.IDLE
        )
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)

        # Create empty seats
        for i in range(room.max_seats):
            seat = Seat(room_id=room.id, seat_index=i, status=SeatStatus.EMPTY)
            self.db.add(seat)
        await self.db.commit()

        # Auto-join owner to first seat with max buyin
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.seat_index == 0)
            )
        )
        owner_seat = result.scalars().first()
        if owner_seat:
            from datetime import datetime
            owner_seat.user_id = owner_id
            owner_seat.chips = room_data.max_buyin  # Default to max buyin for owner
            owner_seat.status = SeatStatus.WAITING
            owner_seat.joined_at = datetime.utcnow()
            room.status = RoomStatus.WAITING
            await self.db.commit()
            await self.db.refresh(room)

        return room

    async def get_room_by_id(self, room_id: int) -> Optional[Room]:
        result = await self.db.execute(
            select(Room).where(Room.id == room_id)
        )
        return result.scalar_one_or_none()

    async def get_all_rooms(self) -> List[Room]:
        result = await self.db.execute(select(Room))
        return result.scalars().all()

    async def get_active_rooms(self) -> List[Room]:
        result = await self.db.execute(
            select(Room).where(Room.status != RoomStatus.IDLE)
        )
        return result.scalars().all()

    async def delete_room(self, room_id: int) -> bool:
        room = await self.get_room_by_id(room_id)
        if room:
            await self.db.delete(room)
            await self.db.commit()
            return True
        return False

    async def join_room(
        self, room: Room, user: User, buyin: int, password: Optional[str] = None
    ) -> Tuple[Optional[Seat], str]:
        """User joins a room."""
        # Check password
        if room.password and room.password != password:
            return None, "房间密码错误"

        # Check if already in room
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.user_id == user.id)
            )
        )
        existing_seat = result.scalar_one_or_none()
        if existing_seat:
            return None, "你已在此房间中"

        # Find empty seat
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.status == SeatStatus.EMPTY)
            ).order_by(Seat.seat_index)
        )
        seat = result.scalars().first()

        if not seat:
            return None, "房间已满"

        # Check buyin
        if buyin > room.max_buyin:
            return None, f"买入金额超过上限 {room.max_buyin}"

        if buyin < room.big_blind:
            return None, f"买入金额不能少于 {room.big_blind}"

        # Update seat
        seat.user_id = user.id
        seat.chips = buyin
        seat.status = SeatStatus.WAITING
        from datetime import datetime
        seat.joined_at = datetime.utcnow()

        # Update room status
        if room.status == RoomStatus.IDLE:
            room.status = RoomStatus.WAITING

        await self.db.commit()
        await self.db.refresh(seat)

        return seat, ""

    async def leave_room(self, room: Room, user_id: int) -> Tuple[bool, str]:
        """User leaves a room."""
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.user_id == user_id)
            )
        )
        seat = result.scalar_one_or_none()

        if not seat:
            return False, "你不在该房间中"

        if room.status == RoomStatus.PLAYING and seat.status == SeatStatus.PLAYING:
            return False, "游戏中不能离开，请先弃牌"

        # Clear seat
        seat.user_id = None
        seat.chips = 0
        seat.net_chips = 0
        seat.status = SeatStatus.EMPTY
        seat.joined_at = None

        await self.db.commit()

        # Check if room is empty (no players with user_id)
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.user_id.isnot(None))
            )
        )
        remaining = result.scalars().all()

        if not remaining:
            # Delete the room when all players leave
            await self.db.delete(room)
            await self.db.commit()
            return True, "room_deleted"

        return True, ""

    async def get_room_seats(self, room_id: int) -> List[Seat]:
        result = await self.db.execute(
            select(Seat).where(Seat.room_id == room_id).order_by(Seat.seat_index)
        )
        return result.scalars().all()

    async def update_seat_status(
        self, room: Room, user_id: int, status: SeatStatus
    ) -> Optional[Seat]:
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.user_id == user_id)
            )
        )
        seat = result.scalar_one_or_none()

        if seat:
            seat.status = status
            await self.db.commit()
            await self.db.refresh(seat)

        return seat

    async def can_start_game(self, room: Room) -> Tuple[bool, str]:
        """Check if game can start."""
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.status == SeatStatus.READY)
            )
        )
        ready_seats = result.scalars().all()

        if len(ready_seats) < 2:
            return False, "需要至少2名玩家准备"

        return True, ""

    async def get_ready_players(self, room_id: int) -> List[Seat]:
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room_id, Seat.status == SeatStatus.READY)
            )
        )
        return result.scalars().all()

    async def update_room_status(self, room: Room, status: RoomStatus) -> Room:
        room.status = status
        await self.db.commit()
        await self.db.refresh(room)
        return room

    async def switch_seat(self, room: Room, user_id: int, target_seat_index: int) -> Tuple[Optional[Seat], str]:
        """Switch user to a different empty seat."""
        # Check if user is in the room
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.user_id == user_id)
            )
        )
        current_seat = result.scalars().first()

        if not current_seat:
            return None, "你不在该房间中"

        if room.status == RoomStatus.PLAYING and current_seat.status == SeatStatus.PLAYING:
            return None, "游戏中不能切换座位"

        # Check if target seat exists and is empty
        result = await self.db.execute(
            select(Seat).where(
                and_(Seat.room_id == room.id, Seat.seat_index == target_seat_index)
            )
        )
        target_seat = result.scalars().first()

        if not target_seat:
            return None, "目标座位不存在"

        if target_seat.user_id is not None:
            return None, "目标座位已被占用"

        # Swap seats
        target_seat.user_id = current_seat.user_id
        target_seat.chips = current_seat.chips
        target_seat.net_chips = current_seat.net_chips
        target_seat.status = current_seat.status
        target_seat.joined_at = current_seat.joined_at

        # Clear old seat
        current_seat.user_id = None
        current_seat.chips = 0
        current_seat.net_chips = 0
        current_seat.status = SeatStatus.EMPTY
        current_seat.joined_at = None

        await self.db.commit()
        await self.db.refresh(target_seat)

        return target_seat, ""
