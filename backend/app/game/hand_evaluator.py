from typing import List, Tuple
from dataclasses import dataclass
from enum import IntEnum
from app.game.deck import Card


class HandRank(IntEnum):
    """Poker hand rankings from lowest to highest."""
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8
    ROYAL_FLUSH = 9


@dataclass
class EvaluatedHand:
    """Represents an evaluated poker hand."""
    rank: HandRank
    kickers: Tuple[int, ...]  # Values for tie-breaking

    def __lt__(self, other: 'EvaluatedHand') -> bool:
        if self.rank != other.rank:
            return self.rank < other.rank
        return self.kickers < other.kickers

    def __eq__(self, other: 'EvaluatedHand') -> bool:
        return self.rank == other.rank and self.kickers == other.kickers

    def __gt__(self, other: 'EvaluatedHand') -> bool:
        return not (self < other or self == other)

    def __le__(self, other: 'EvaluatedHand') -> bool:
        return self < other or self == other

    def __ge__(self, other: 'EvaluatedHand') -> bool:
        return self > other or self == other


class HandEvaluator:
    """Evaluates poker hands and determines winners."""

    @staticmethod
    def evaluate(cards: List[Card]) -> EvaluatedHand:
        """
        Evaluate a 5-card hand and return its rank and kickers.
        Cards should be exactly 5 cards.
        """
        if len(cards) != 5:
            raise ValueError("Must provide exactly 5 cards")

        values = sorted([c.value for c in cards], reverse=True)
        suits = [c.suit for c in cards]

        is_flush = len(set(suits)) == 1
        is_straight, straight_high = HandEvaluator._check_straight(values)

        # Count occurrences of each value
        value_counts = {}
        for v in values:
            value_counts[v] = value_counts.get(v, 0) + 1

        counts = sorted(value_counts.values(), reverse=True)
        count_values = sorted(value_counts.keys(), key=lambda x: (value_counts[x], x), reverse=True)

        # Royal Flush
        if is_flush and is_straight and straight_high == 12:  # Ace high straight flush
            return EvaluatedHand(HandRank.ROYAL_FLUSH, (straight_high,))

        # Straight Flush
        if is_flush and is_straight:
            return EvaluatedHand(HandRank.STRAIGHT_FLUSH, (straight_high,))

        # Four of a Kind
        if counts == [4, 1]:
            quad_val = [v for v, c in value_counts.items() if c == 4][0]
            kicker = [v for v, c in value_counts.items() if c == 1][0]
            return EvaluatedHand(HandRank.FOUR_OF_A_KIND, (quad_val, kicker))

        # Full House
        if counts == [3, 2]:
            trip_val = [v for v, c in value_counts.items() if c == 3][0]
            pair_val = [v for v, c in value_counts.items() if c == 2][0]
            return EvaluatedHand(HandRank.FULL_HOUSE, (trip_val, pair_val))

        # Flush
        if is_flush:
            return EvaluatedHand(HandRank.FLUSH, tuple(values))

        # Straight
        if is_straight:
            return EvaluatedHand(HandRank.STRAIGHT, (straight_high,))

        # Three of a Kind
        if counts == [3, 1, 1]:
            trip_val = [v for v, c in value_counts.items() if c == 3][0]
            kickers = sorted([v for v, c in value_counts.items() if c == 1], reverse=True)
            return EvaluatedHand(HandRank.THREE_OF_A_KIND, (trip_val,) + tuple(kickers))

        # Two Pair
        if counts == [2, 2, 1]:
            pairs = sorted([v for v, c in value_counts.items() if c == 2], reverse=True)
            kicker = [v for v, c in value_counts.items() if c == 1][0]
            return EvaluatedHand(HandRank.TWO_PAIR, tuple(pairs) + (kicker,))

        # One Pair
        if counts == [2, 1, 1, 1]:
            pair_val = [v for v, c in value_counts.items() if c == 2][0]
            kickers = sorted([v for v, c in value_counts.items() if c == 1], reverse=True)
            return EvaluatedHand(HandRank.ONE_PAIR, (pair_val,) + tuple(kickers))

        # High Card
        return EvaluatedHand(HandRank.HIGH_CARD, tuple(values))

    @staticmethod
    def _check_straight(values: List[int]) -> Tuple[bool, int]:
        """
        Check if sorted values form a straight.
        Returns (is_straight, high_card_value).
        Handles ace-low straight (A-2-3-4-5).
        """
        unique_values = sorted(set(values), reverse=True)
        if len(unique_values) != 5:
            return False, 0

        # Check normal straight
        if unique_values[0] - unique_values[4] == 4:
            return True, unique_values[0]

        # Check ace-low straight (A-2-3-4-5)
        if unique_values == [12, 3, 2, 1, 0]:  # A, 5, 4, 3, 2
            return True, 3  # 5-high straight

        return False, 0

    @staticmethod
    def best_hand(hole_cards: List[Card], community_cards: List[Card]) -> EvaluatedHand:
        """
        Find the best 5-card hand from 2 hole cards and up to 5 community cards.
        """
        all_cards = hole_cards + community_cards
        if len(all_cards) < 5:
            raise ValueError("Need at least 5 cards total")

        best = None
        # Generate all 5-card combinations
        from itertools import combinations

        for combo in combinations(all_cards, 5):
            hand = HandEvaluator.evaluate(list(combo))
            if best is None or hand > best:
                best = hand

        return best

    @staticmethod
    def compare_hands(hand1: EvaluatedHand, hand2: EvaluatedHand) -> int:
        """
        Compare two hands.
        Returns: 1 if hand1 wins, -1 if hand2 wins, 0 if tie.
        """
        if hand1 > hand2:
            return 1
        elif hand1 < hand2:
            return -1
        return 0

    @staticmethod
    def get_hand_name(hand: EvaluatedHand) -> str:
        """Return human-readable name for a hand."""
        names = {
            HandRank.HIGH_CARD: "高牌",
            HandRank.ONE_PAIR: "一对",
            HandRank.TWO_PAIR: "两对",
            HandRank.THREE_OF_A_KIND: "三条",
            HandRank.STRAIGHT: "顺子",
            HandRank.FLUSH: "同花",
            HandRank.FULL_HOUSE: "葫芦",
            HandRank.FOUR_OF_A_KIND: "四条",
            HandRank.STRAIGHT_FLUSH: "同花顺",
            HandRank.ROYAL_FLUSH: "皇家同花顺",
        }
        return names[hand.rank]
