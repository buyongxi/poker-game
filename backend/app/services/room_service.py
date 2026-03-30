import logging
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from app.models.room import RoomStatus, SeatStatus
from app.schemas.room import RoomCreate

logger = logging.getLogger(__name__)


class MemorySeat:
    """内存中的座位对象"""
    def __init__(self, seat_index: int):
        self.seat_index = seat_index
        self.user_id: Optional[int] = None
        self.user_name: Optional[str] = None
        self.chips: int = 0
        self.total_buyin: int = 0  # 累计买入金额
        self.status: SeatStatus = SeatStatus.EMPTY
        self.joined_at: Optional[datetime] = None


class MemoryRoom:
    """内存中的房间对象"""
    def __init__(self, room_id: int, name: str, password: str, small_blind: int,
                 big_blind: int, max_seats: int, max_buyin: int, owner_id: int):
        self.id = room_id
        self.name = name
        self.password = password
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.max_seats = max_seats
        self.max_buyin = max_buyin
        self.owner_id = owner_id
        self.status = RoomStatus.WAITING
        self.seats: Dict[int, MemorySeat] = {}
        # 初始化空座位
        for i in range(max_seats):
            self.seats[i] = MemorySeat(i)


class RoomService:
    """纯内存的房间管理服务"""

    # 类变量：所有房间存储在这里
    _rooms: Dict[int, MemoryRoom] = {}
    _next_room_id: int = 1

    def __init__(self):
        pass  # 不再需要数据库会话

    async def get_room_by_name(self, name: str) -> Optional[MemoryRoom]:
        """Get a room by name from memory."""
        for room in RoomService._rooms.values():
            if room.name == name:
                return room
        return None

    async def create_room(self, room_data: RoomCreate, owner_id: int, owner_name: str) -> MemoryRoom:
        """Create a new room in memory."""
        # Check if room with same name already exists
        existing_room = await self.get_room_by_name(room_data.name)
        if existing_room:
            raise ValueError("该房间名称已存在")

        room_id = RoomService._next_room_id
        RoomService._next_room_id += 1

        room = MemoryRoom(
            room_id=room_id,
            name=room_data.name,
            password=room_data.password,
            small_blind=room_data.small_blind,
            big_blind=room_data.small_blind * 2,
            max_seats=room_data.max_seats,
            max_buyin=room_data.max_buyin,
            owner_id=owner_id
        )

        # 房主自动加入第一个座位
        room.seats[0].user_id = owner_id
        room.seats[0].user_name = owner_name
        room.seats[0].chips = room_data.max_buyin
        room.seats[0].total_buyin = room_data.max_buyin  # 记录买入金额
        room.seats[0].status = SeatStatus.WAITING
        room.seats[0].joined_at = datetime.utcnow()

        RoomService._rooms[room_id] = room
        return room

    async def get_room_by_id(self, room_id: int) -> Optional[MemoryRoom]:
        """Get a room by ID from memory."""
        return RoomService._rooms.get(room_id)

    async def get_all_rooms(self) -> List[MemoryRoom]:
        """Get all rooms from memory."""
        return list(RoomService._rooms.values())

    async def get_active_rooms(self) -> List[MemoryRoom]:
        """Get all active rooms (not IDLE) from memory."""
        return [room for room in RoomService._rooms.values() if room.status != RoomStatus.IDLE]

    async def delete_room(self, room_id: int) -> bool:
        """Delete a room from memory."""
        if room_id in RoomService._rooms:
            del RoomService._rooms[room_id]
            return True
        return False

    async def join_room(
        self, room: MemoryRoom, user_id: int, user_name: str, buyin: int, password: Optional[str] = None
    ) -> Tuple[Optional[MemorySeat], str]:
        """User joins a room in memory."""
        # Check password
        if room.password and room.password != password:
            return None, "房间密码错误"

        # Check if already in room (reconnect case)
        for seat in room.seats.values():
            if seat.user_id == user_id:
                # Player is reconnecting, return their existing seat
                return seat, ""

        # Find empty seat
        empty_seat = None
        for seat in room.seats.values():
            if seat.status == SeatStatus.EMPTY:
                empty_seat = seat
                break

        if not empty_seat:
            return None, "房间已满"

        # Check buyin
        if buyin > room.max_buyin:
            return None, f"买入金额超过上限 {room.max_buyin}"

        if buyin < room.big_blind:
            return None, f"买入金额不能少于 {room.big_blind}"

        # Update seat
        empty_seat.user_id = user_id
        empty_seat.user_name = user_name
        empty_seat.chips = buyin
        empty_seat.total_buyin = buyin  # 记录买入金额
        empty_seat.status = SeatStatus.WAITING
        empty_seat.joined_at = datetime.utcnow()

        # Update room status
        if room.status == RoomStatus.IDLE:
            room.status = RoomStatus.WAITING

        return empty_seat, ""

    async def leave_room(self, room_id: int, user_id: int) -> Tuple[bool, str]:
        """User leaves a room in memory."""
        room = await self.get_room_by_id(room_id)
        if not room:
            return False, "房间不存在"

        # Find user's seat
        user_seat = None
        for seat in room.seats.values():
            if seat.user_id == user_id:
                user_seat = seat
                break

        if not user_seat:
            return False, "你不在该房间中"

        if room.status == RoomStatus.PLAYING and user_seat.status == SeatStatus.PLAYING:
            return False, "游戏中不能离开，请先弃牌"

        # Check if leaving user is the owner
        is_owner = room.owner_id == user_id
        logger.debug(f"leave_room: user_id={user_id}, is_owner={is_owner}, current owner_id={room.owner_id}")

        # Clear seat
        user_seat.user_id = None
        user_seat.user_name = None
        user_seat.chips = 0
        user_seat.total_buyin = 0
        user_seat.status = SeatStatus.EMPTY
        user_seat.joined_at = None

        # Check if room is empty (no players with user_id)
        remaining = [seat for seat in room.seats.values() if seat.user_id is not None]

        if not remaining:
            # Delete the room when all players leave
            del RoomService._rooms[room_id]
            return True, "room_deleted"

        # If owner left, transfer ownership to another player
        if is_owner and remaining:
            # Pick the first remaining player as new owner
            new_owner_id = remaining[0].user_id
            logger.debug(f"Transferring ownership from {user_id} to {new_owner_id}")
            room.owner_id = new_owner_id
            return True, f"owner_transferred:{new_owner_id}"

        return True, ""

    async def get_room_seats(self, room_id: int) -> List[MemorySeat]:
        """Get all seats for a room from memory."""
        room = await self.get_room_by_id(room_id)
        if not room:
            return []
        return [room.seats[i] for i in sorted(room.seats.keys())]

    async def update_seat_status(
        self, room: MemoryRoom, user_id: int, status: SeatStatus
    ) -> Optional[MemorySeat]:
        """Update a seat's status in memory."""
        for seat in room.seats.values():
            if seat.user_id == user_id:
                seat.status = status
                return seat
        return None

    async def can_start_game(self, room: MemoryRoom) -> Tuple[bool, str]:
        """Check if game can start."""
        ready_count = sum(1 for seat in room.seats.values() if seat.status == SeatStatus.READY)

        if ready_count < 2:
            return False, "需要至少2名玩家准备"

        return True, ""

    async def get_ready_players(self, room_id: int) -> List[MemorySeat]:
        """Get all ready players from memory."""
        room = await self.get_room_by_id(room_id)
        if not room:
            return []
        return [seat for seat in room.seats.values() if seat.status == SeatStatus.READY]

    async def update_room_status(self, room: MemoryRoom, status: RoomStatus) -> MemoryRoom:
        """Update room status in memory."""
        room.status = status
        return room

    async def switch_seat(self, room: MemoryRoom, user_id: int, target_seat_index: int) -> Tuple[Optional[MemorySeat], str]:
        """Switch user to a different empty seat in memory."""
        # Find user's current seat
        current_seat = None
        for seat in room.seats.values():
            if seat.user_id == user_id:
                current_seat = seat
                break

        if not current_seat:
            return None, "你不在该房间中"

        if room.status == RoomStatus.PLAYING and current_seat.status == SeatStatus.PLAYING:
            return None, "游戏中不能切换座位"

        # Check if target seat exists and is empty
        if target_seat_index not in room.seats:
            return None, "目标座位不存在"

        target_seat = room.seats[target_seat_index]

        if target_seat.user_id is not None:
            return None, "目标座位已被占用"

        # Swap seats
        target_seat.user_id = current_seat.user_id
        target_seat.user_name = current_seat.user_name
        target_seat.chips = current_seat.chips
        target_seat.total_buyin = current_seat.total_buyin
        target_seat.status = current_seat.status
        target_seat.joined_at = current_seat.joined_at

        # Clear old seat
        current_seat.user_id = None
        current_seat.user_name = None
        current_seat.chips = 0
        current_seat.total_buyin = 0
        current_seat.status = SeatStatus.EMPTY
        current_seat.joined_at = None

        return target_seat, ""

    async def get_user_seat(self, room: MemoryRoom, user_id: int) -> Optional[MemorySeat]:
        """Get user's seat in a room from memory."""
        for seat in room.seats.values():
            if seat.user_id == user_id:
                return seat
        return None

    async def rebuy_chips(self, room: MemoryRoom, user_id: int, amount: int) -> Tuple[Optional[MemorySeat], str]:
        """Rebuy chips when out of chips in memory."""
        seat = await self.get_user_seat(room, user_id)
        if not seat:
            return None, "你不在该房间中"

        # Check if player has chips
        if seat.chips > 0:
            return None, "你还有筹码，无法补充"

        # Check if game is active
        if room.status == RoomStatus.PLAYING:
            return None, "游戏中无法补充筹码"

        # Check rebuy amount
        if amount > room.max_buyin:
            return None, f"买入金额不能超过 {room.max_buyin}"

        if amount < room.big_blind:
            return None, f"买入金额不能少于 {room.big_blind}"

        # Update seat
        seat.chips = amount
        seat.total_buyin += amount  # 累加买入金额
        seat.status = SeatStatus.WAITING

        return seat, ""

    async def update_seat_chips(self, room: MemoryRoom, user_id: int, chips: int) -> Optional[MemorySeat]:
        """Update seat chips in memory."""
        seat = await self.get_user_seat(room, user_id)
        if seat:
            seat.chips = chips
        return seat
