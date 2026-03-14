from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class RoomCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    password: Optional[str] = Field(None, max_length=100)
    small_blind: int = Field(10, ge=1)
    max_seats: int = Field(9, ge=2, le=9)
    max_buyin: int = Field(2000, ge=100)


class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, max_length=100)


class SeatResponse(BaseModel):
    id: int
    seat_index: int
    user_id: Optional[int]
    user_name: Optional[str]
    chips: int
    net_chips: int
    status: str

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    id: int
    name: str
    has_password: bool = False
    small_blind: int
    big_blind: int
    max_seats: int
    max_buyin: int
    owner_id: int
    status: str
    created_at: datetime
    seats: List[SeatResponse] = []
    player_count: int = 0

    class Config:
        from_attributes = True


class JoinRoom(BaseModel):
    password: Optional[str] = None
    buyin: int = Field(..., ge=1)


class SeatAction(BaseModel):
    action: str  # ready, unready, sit_out

class SwitchSeat(BaseModel):
    seat_index: int
