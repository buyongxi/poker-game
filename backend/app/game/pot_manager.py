from typing import List, Dict, Tuple
from dataclasses import dataclass, field


@dataclass
class Pot:
    """Represents a pot (main or side pot)."""
    amount: int = 0
    eligible_players: List[int] = field(default_factory=list)  # user_ids

    def add_chips(self, amount: int) -> None:
        self.amount += amount

    def is_eligible(self, user_id: int) -> bool:
        return user_id in self.eligible_players


class PotManager:
    """
    Manages the main pot and side pots in Texas Hold'em.
    Handles complex scenarios with all-in players.
    """

    def __init__(self):
        self.pots: List[Pot] = []
        self.player_bets: Dict[int, int] = {}  # user_id -> total bet this round
        self.player_total_bets: Dict[int, int] = {}  # user_id -> total bet in hand

    def reset(self) -> None:
        """Reset for new hand."""
        self.pots = []
        self.player_bets = {}
        self.player_total_bets = {}

    def new_betting_round(self) -> None:
        """Reset bets for new betting round (flop, turn, river)."""
        self.player_bets = {}

    def add_bet(self, user_id: int, amount: int) -> None:
        """Record a player's bet."""
        if user_id not in self.player_bets:
            self.player_bets[user_id] = 0
        if user_id not in self.player_total_bets:
            self.player_total_bets[user_id] = 0

        self.player_bets[user_id] += amount
        self.player_total_bets[user_id] += amount

    def get_player_bet(self, user_id: int) -> int:
        """Get player's bet in current round."""
        return self.player_bets.get(user_id, 0)

    def get_player_total_bet(self, user_id: int) -> int:
        """Get player's total bet in hand."""
        return self.player_total_bets.get(user_id, 0)

    def calculate_pots(self, active_players: List[int], all_in_players: List[int]) -> List[Pot]:
        """
        Calculate main pot and side pots based on all-in situations.

        Args:
            active_players: Players still in the hand (not folded)
            all_in_players: Players who are all-in

        Returns:
            List of pots with eligible players
        """
        self.pots = []

        if not active_players:
            return self.pots

        # Get all unique bet levels from all-in players
        bet_levels = sorted(set(
            self.player_total_bets.get(pid, 0)
            for pid in all_in_players + active_players
            if self.player_total_bets.get(pid, 0) > 0
        ))

        if not bet_levels:
            return self.pots

        prev_level = 0
        for level in bet_levels:
            pot = Pot()
            pot_amount = 0

            for player_id in active_players + all_in_players:
                player_total = self.player_total_bets.get(player_id, 0)
                if player_total > prev_level:
                    # This player contributed at this level
                    contribution = min(level, player_total) - prev_level
                    pot_amount += contribution

                    # Player is eligible if they haven't folded
                    if player_id in active_players or player_id in all_in_players:
                        if player_id not in pot.eligible_players:
                            pot.eligible_players.append(player_id)

            if pot_amount > 0:
                pot.amount = pot_amount
                self.pots.append(pot)

            prev_level = level

        return self.pots

    def get_total_pot(self) -> int:
        """Get total amount in all pots."""
        # If pots are calculated, return sum of pots
        if self.pots:
            return sum(pot.amount for pot in self.pots)
        # Otherwise, return sum of all player bets (during betting rounds)
        return sum(self.player_total_bets.values())

    def distribute_winnings(
        self,
        hand_rankings: Dict[int, Tuple]  # user_id -> (hand_rank, kickers)
    ) -> Dict[int, int]:
        """
        Distribute winnings based on hand rankings.

        Args:
            hand_rankings: Dict mapping user_id to their evaluated hand

        Returns:
            Dict mapping user_id to winnings
        """
        winnings = {}

        for pot in self.pots:
            # Find eligible players with best hand
            eligible_with_hands = {
                pid: hand_rankings[pid]
                for pid in pot.eligible_players
                if pid in hand_rankings
            }

            if not eligible_with_hands:
                continue

            # Find the best hand
            best_hand = max(eligible_with_hands.values())

            # Find all players with the best hand (ties)
            winners = [
                pid for pid, hand in eligible_with_hands.items()
                if hand == best_hand
            ]

            # Split pot among winners
            win_amount = pot.amount // len(winners)
            remainder = pot.amount % len(winners)

            for i, winner_id in enumerate(winners):
                winnings[winner_id] = winnings.get(winner_id, 0) + win_amount
                # First winner gets remainder (arbitrary but consistent)
                if i == 0:
                    winnings[winner_id] += remainder

        return winnings

    def to_dict(self) -> List[dict]:
        """Convert pots to dictionary for JSON serialization."""
        return [
            {
                "amount": pot.amount,
                "eligible_players": pot.eligible_players
            }
            for pot in self.pots
        ]
