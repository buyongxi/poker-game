from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field
from app.game.deck import Card


class PlayerStatus(str, Enum):
    WAITING = "waiting"      # 等待准备
    READY = "ready"          # 已准备
    PLAYING = "playing"      # 游戏中
    FOLDED = "folded"        # 已弃牌
    ALL_IN = "all_in"        # 全押
    DISCONNECTED = "disconnected"  # 断线


@dataclass
class Player:
    """Represents a player in a poker game."""
    user_id: int
    username: str
    seat_index: int
    chips: int = 0
    current_bet: int = 0      # Current betting round bet
    total_bet: int = 0        # Total bet in current hand
    status: PlayerStatus = PlayerStatus.WAITING
    hole_cards: List[Card] = field(default_factory=list)
    is_dealer: bool = False
    is_sb: bool = False
    is_bb: bool = False
    is_current: bool = False

    def __post_init__(self):
        if not isinstance(self.status, PlayerStatus):
            self.status = PlayerStatus(self.status)

    def reset_for_hand(self) -> None:
        """Reset player state for new hand."""
        self.current_bet = 0
        self.total_bet = 0
        self.hole_cards = []
        if self.status == PlayerStatus.PLAYING:
            self.status = PlayerStatus.READY
        elif self.status == PlayerStatus.FOLDED:
            self.status = PlayerStatus.READY
        elif self.status == PlayerStatus.ALL_IN:
            self.status = PlayerStatus.READY
        self.is_current = False

    def reset_for_round(self) -> None:
        """Reset for new betting round."""
        self.current_bet = 0
        self.is_current = False

    def deal_cards(self, cards: List[Card]) -> None:
        """Deal hole cards to player."""
        self.hole_cards = cards
        self.status = PlayerStatus.PLAYING

    def fold(self) -> None:
        """Player folds."""
        self.status = PlayerStatus.FOLDED
        self.is_current = False

    def check(self) -> bool:
        """Player checks. Returns True if valid."""
        return self.current_bet == 0

    def call(self, amount: int) -> int:
        """
        Player calls. Returns actual amount called.
        May be less if player doesn't have enough chips.
        """
        needed = amount - self.current_bet
        actual = min(needed, self.chips)
        self.chips -= actual
        self.current_bet += actual
        self.total_bet += actual

        if self.chips == 0:
            self.status = PlayerStatus.ALL_IN

        return actual

    def raise_bet(self, total_amount: int) -> int:
        """
        Player raises to total amount. Returns actual amount bet.
        """
        needed = total_amount - self.current_bet
        actual = min(needed, self.chips)
        self.chips -= actual
        self.current_bet += actual
        self.total_bet += actual

        if self.chips == 0:
            self.status = PlayerStatus.ALL_IN

        return actual

    def all_in(self) -> int:
        """Player goes all-in. Returns amount bet."""
        amount = self.chips
        self.current_bet += amount
        self.total_bet += amount
        self.chips = 0
        self.status = PlayerStatus.ALL_IN
        return amount

    def post_blind(self, amount: int) -> int:
        """Post blind. Returns actual amount posted."""
        actual = min(amount, self.chips)
        self.chips -= actual
        self.current_bet = actual
        self.total_bet = actual
        return actual

    def can_act(self) -> bool:
        """Check if player can take action."""
        return self.status == PlayerStatus.PLAYING and self.chips > 0

    def is_in_hand(self) -> bool:
        """Check if player is still in the hand."""
        return self.status in [PlayerStatus.PLAYING, PlayerStatus.ALL_IN]

    def add_chips(self, amount: int) -> None:
        """Add chips to player's stack."""
        self.chips += amount

    def to_dict(self, show_cards: bool = False) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "seat_index": self.seat_index,
            "chips": self.chips,
            "current_bet": self.current_bet,
            "total_bet": self.total_bet,
            "status": self.status.value,
            "cards": [
                {"rank": c.rank, "suit": c.suit}
                for c in self.hole_cards
            ] if show_cards else [],
            "is_dealer": self.is_dealer,
            "is_sb": self.is_sb,
            "is_bb": self.is_bb,
            "is_current": self.is_current
        }
