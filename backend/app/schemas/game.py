from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"


class GamePhase(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


class GameAction(BaseModel):
    action: ActionType
    amount: Optional[int] = None  # For raise


class CardInfo(BaseModel):
    rank: str  # 2-10, J, Q, K, A
    suit: str  # h, d, c, s (hearts, diamonds, clubs, spades)

    def __str__(self):
        return f"{self.rank}{self.suit}"


class PlayerState(BaseModel):
    user_id: int
    username: str
    seat_index: int
    chips: int
    current_bet: int
    total_bet: int
    status: str  # playing, folded, all_in
    cards: List[CardInfo] = []
    is_dealer: bool = False
    is_sb: bool = False
    is_bb: bool = False
    is_current: bool = False


class PotInfo(BaseModel):
    amount: int
    players: List[int]  # user_ids eligible for this pot


class GameState(BaseModel):
    room_id: int
    phase: GamePhase
    community_cards: List[CardInfo] = []
    pots: List[PotInfo] = []
    current_pot: int = 0
    current_bet: int = 0
    min_raise: int = 0
    current_player_id: Optional[int] = None
    dealer_seat: int = 0
    sb_seat: int = 0
    bb_seat: int = 0
    players: List[PlayerState] = []
    winners: List[Dict[str, Any]] = []
    is_active: bool = True


class ChatMessage(BaseModel):
    message: str = Field(..., max_length=500)
