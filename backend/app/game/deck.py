import random
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Card:
    """Represents a playing card."""
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    SUITS = ['h', 'd', 'c', 's']  # hearts, diamonds, clubs, spades
    RANK_VALUES = {rank: i for i, rank in enumerate(RANKS)}

    rank: str
    suit: str

    def __post_init__(self):
        if self.rank not in self.RANKS:
            raise ValueError(f"Invalid rank: {self.rank}")
        if self.suit not in self.SUITS:
            raise ValueError(f"Invalid suit: {self.suit}")

    @property
    def value(self) -> int:
        """Return numeric value of the rank (0-12)."""
        return self.RANK_VALUES[self.rank]

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self.rank}{self.suit})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit

    def __hash__(self) -> int:
        return hash((self.rank, self.suit))

    def to_dict(self) -> dict:
        return {"rank": self.rank, "suit": self.suit}

    @classmethod
    def from_str(cls, card_str: str) -> 'Card':
        """Create a Card from string like 'Ah' or '10s'."""
        if len(card_str) == 2:
            rank, suit = card_str[0], card_str[1]
        elif len(card_str) == 3:
            rank, suit = card_str[:2], card_str[2]
        else:
            raise ValueError(f"Invalid card string: {card_str}")
        return cls(rank, suit)


class Deck:
    """Represents a deck of 52 playing cards."""

    def __init__(self):
        self.cards: List[Card] = []
        self.reset()

    def reset(self) -> None:
        """Reset deck to full 52 cards."""
        self.cards = [
            Card(rank, suit)
            for suit in Card.SUITS
            for rank in Card.RANKS
        ]

    def shuffle(self) -> None:
        """Shuffle the deck."""
        random.shuffle(self.cards)

    def deal(self, num: int = 1) -> List[Card]:
        """Deal specified number of cards from top of deck."""
        if num > len(self.cards):
            raise ValueError(f"Cannot deal {num} cards, only {len(self.cards)} remaining")

        dealt = self.cards[:num]
        self.cards = self.cards[num:]
        return dealt

    def deal_one(self) -> Optional[Card]:
        """Deal a single card."""
        if not self.cards:
            return None
        return self.cards.pop(0)

    def remaining(self) -> int:
        """Return number of cards remaining in deck."""
        return len(self.cards)

    def burn(self) -> Optional[Card]:
        """Burn (discard) top card."""
        if self.cards:
            return self.cards.pop(0)
        return None
