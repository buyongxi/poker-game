from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.database import Base


class RoomStatus(str, enum.Enum):
    IDLE = "idle"        # 空闲，无人
    WAITING = "waiting"  # 等待玩家准备
    PLAYING = "playing"  # 游戏中


class SeatStatus(str, enum.Enum):
    EMPTY = "empty"      # 空座位
    WAITING = "waiting"  # 等待准备
    READY = "ready"      # 已准备
    PLAYING = "playing"  # 游戏中
    FOLDED = "folded"    # 已弃牌
    ALL_IN = "all_in"    # 全押
    DISCONNECTED = "disconnected"  # 断线


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    password = Column(String(100), nullable=True)  # 可选密码
    small_blind = Column(Integer, default=10, nullable=False)
    big_blind = Column(Integer, default=20, nullable=False)  # 2x small blind
    max_seats = Column(Integer, default=9, nullable=False)
    max_buyin = Column(Integer, default=2000, nullable=False)  # 100x big blind
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default=RoomStatus.IDLE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    owner = relationship("User", back_populates="owned_rooms")
    seats = relationship("Seat", back_populates="room", cascade="all, delete-orphan")
    game_records = relationship("GameRecord", back_populates="room")


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    seat_index = Column(Integer, nullable=False)
    chips = Column(Integer, default=0, nullable=False)
    net_chips = Column(Integer, default=0, nullable=False)  # 净筹码变化
    status = Column(String(20), default=SeatStatus.EMPTY, nullable=False)
    joined_at = Column(DateTime, nullable=True)

    # Relationships
    room = relationship("Room", back_populates="seats")
    user = relationship("User", back_populates="seats")

    class Config:
        unique_together = [("room_id", "seat_index")]
