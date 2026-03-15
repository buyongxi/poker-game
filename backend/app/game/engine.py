from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass
import asyncio
from app.game.deck import Deck, Card
from app.game.player import Player, PlayerStatus
from app.game.hand_evaluator import HandEvaluator, EvaluatedHand
from app.game.pot_manager import PotManager
from app.config import settings


class GamePhase(str, Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    ENDED = "ended"


class ActionType(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass
class GameResult:
    """Result of a completed hand."""
    winners: List[Dict]
    pot_amount: int
    community_cards: List[Card]
    player_hands: Dict[int, List[Card]]
    player_names: Dict[int, str] = None  # user_id -> username
    chip_changes: Dict[int, int] = None  # user_id -> chip change (positive = won, negative = lost)


class GameEngine:
    """
    Core Texas Hold'em game engine.
    Manages game state, player actions, and hand resolution.
    """

    def __init__(
        self,
        small_blind: int = 10,
        big_blind: int = 20,
        action_timeout: int = None
    ):
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.action_timeout = action_timeout or settings.ACTION_TIMEOUT

        # Game state
        self.phase = GamePhase.ENDED
        self.deck: Optional[Deck] = None
        self.community_cards: List[Card] = []
        self.players: Dict[int, Player] = {}  # user_id -> Player
        self.player_order: List[int] = []  # user_ids in seat order

        # Position markers
        self.dealer_index: int = 0
        self.sb_index: int = 0
        self.bb_index: int = 0
        self.current_player_index: int = 0

        # Betting state
        self.pot_manager = PotManager()
        self.current_bet: int = 0
        self.min_raise: int = big_blind
        self.last_raiser_index: Optional[int] = None
        self.acted_this_round: Set[int] = set()  # user_ids who have acted

        # Callbacks
        self.on_state_change = None
        self.on_player_action = None
        self.on_hand_complete = None

    def add_player(self, user_id: int, username: str, seat_index: int, chips: int) -> None:
        """Add a player to the game."""
        player = Player(
            user_id=user_id,
            username=username,
            seat_index=seat_index,
            chips=chips,
            status=PlayerStatus.READY  # Players added to game are ready
        )
        self.players[user_id] = player
        self._update_player_order()

    def remove_player(self, user_id: int) -> None:
        """Remove a player from the game."""
        if user_id in self.players:
            del self.players[user_id]
            self._update_player_order()

    def _update_player_order(self) -> None:
        """Update player order based on seat index."""
        self.player_order = sorted(
            self.players.keys(),
            key=lambda uid: self.players[uid].seat_index
        )

    def can_start(self) -> Tuple[bool, str]:
        """Check if game can start."""
        ready_players = [p for p in self.players.values() if p.status == PlayerStatus.READY]
        if len(ready_players) < 2:
            return False, "需要至少2名玩家准备"
        return True, ""

    def start_hand(self) -> bool:
        """Start a new hand."""
        can_start, msg = self.can_start()
        if not can_start:
            return False

        # Reset state
        self.deck = Deck()
        self.deck.shuffle()
        self.community_cards = []
        self.phase = GamePhase.PREFLOP
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.last_raiser_index = None
        self.acted_this_round = set()

        self.pot_manager.reset()

        # Reset players - set status to READY first (before dealing cards)
        for player in self.players.values():
            player.reset_for_hand()

        # Set positions
        self._set_positions()

        # Post blinds
        self._post_blinds()

        # Deal hole cards (this will set status to PLAYING)
        self._deal_hole_cards()

        # Set first to act (after big blind in preflop)
        self._set_first_to_act_preflop()

        return True

    def _set_positions(self) -> None:
        """Set dealer, SB, BB positions."""
        active_players = [
            uid for uid in self.player_order
            if self.players[uid].status == PlayerStatus.READY
        ]

        if len(active_players) < 2:
            return

        # Move dealer button
        self.dealer_index = self._next_active_player(self.dealer_index)

        # In heads-up, dealer is SB
        if len(active_players) == 2:
            self.sb_index = self.dealer_index
            self.bb_index = self._next_active_player(self.sb_index)
        else:
            self.sb_index = self._next_active_player(self.dealer_index)
            self.bb_index = self._next_active_player(self.sb_index)

        # Mark positions
        for uid, player in self.players.items():
            player.is_dealer = (uid == self.player_order[self.dealer_index])
            player.is_sb = (uid == self.player_order[self.sb_index])
            player.is_bb = (uid == self.player_order[self.bb_index])

    def _next_active_player(self, from_index: int) -> int:
        """Get next active player index (circular)."""
        n = len(self.player_order)
        for i in range(1, n + 1):
            idx = (from_index + i) % n
            uid = self.player_order[idx]
            player = self.players[uid]
            # Include both READY (preflop before cards dealt) and PLAYING states
            if player.status in [PlayerStatus.READY, PlayerStatus.PLAYING] or player.is_in_hand():
                return idx
        return from_index

    def _post_blinds(self) -> None:
        """Post small and big blinds."""
        sb_player = self.players[self.player_order[self.sb_index]]
        bb_player = self.players[self.player_order[self.bb_index]]

        sb_amount = sb_player.post_blind(self.small_blind)
        bb_amount = bb_player.post_blind(self.big_blind)

        self.pot_manager.add_bet(sb_player.user_id, sb_amount)
        self.pot_manager.add_bet(bb_player.user_id, bb_amount)

        self.current_bet = self.big_blind
        # Min raise is always the big blind amount
        # To raise, the total bet must be at least 2x the current bet (BB)
        # So min_raise = big_blind, making min total bet = BB + BB = 2*BB
        self.min_raise = self.big_blind

    def _deal_hole_cards(self) -> None:
        """Deal 2 cards to each active player."""
        for uid in self.player_order:
            player = self.players[uid]
            if player.status == PlayerStatus.READY:
                cards = self.deck.deal(2)
                player.deal_cards(cards)

    def _set_first_to_act_preflop(self) -> None:
        """Set first player to act in preflop (after BB)."""
        self.current_player_index = self._next_active_player(self.bb_index)
        self.players[self.player_order[self.current_player_index]].is_current = True

    def get_current_player(self) -> Optional[Player]:
        """Get the player whose turn it is."""
        if not self.player_order:
            return None
        return self.players.get(self.player_order[self.current_player_index])

    def get_valid_actions(self, user_id: int) -> List[Dict]:
        """Get valid actions for a player."""
        player = self.players.get(user_id)
        if not player or not player.is_current:
            return []

        actions = []

        # Fold is always available
        actions.append({"action": ActionType.FOLD, "amount": 0})

        # Check if can check
        if player.current_bet >= self.current_bet:
            actions.append({"action": ActionType.CHECK, "amount": 0})

        # Call
        call_amount = self.current_bet - player.current_bet
        if call_amount > 0 and player.chips > 0:
            actual_call = min(call_amount, player.chips)
            actions.append({"action": ActionType.CALL, "amount": actual_call})

        # Raise
        # Calculate call amount
        call_amount = self.current_bet - player.current_bet

        # Special case: BB in preflop can raise even when call_amount is 0
        can_raise = player.chips > call_amount or (
            player.is_bb and
            self.phase == GamePhase.PREFLOP and
            player.current_bet == self.current_bet and
            player.chips > 0
        )

        if can_raise:
            min_raise_total = self.current_bet + self.min_raise
            max_raise = player.chips + player.current_bet

            if max_raise > self.current_bet:
                actions.append({
                    "action": ActionType.RAISE,
                    "min_amount": min_raise_total,
                    "max_amount": max_raise
                })

        # All-in
        if player.chips > 0:
            actions.append({"action": ActionType.ALL_IN, "amount": player.chips})

        return actions

    def execute_action(self, user_id: int, action: ActionType, amount: int = 0) -> Tuple[bool, str]:
        """
        Execute a player action.
        Returns (success, message).
        """
        player = self.players.get(user_id)
        if not player:
            return False, "玩家不存在"

        if not player.is_current:
            return False, "不是你的回合"

        if self.phase == GamePhase.ENDED or self.phase == GamePhase.SHOWDOWN:
            return False, "游戏已结束"

        # Execute action
        if action == ActionType.FOLD:
            player.fold()

            # Check if only one player remains in hand
            active_players = [p for p in self.players.values() if p.is_in_hand()]
            print(f"[DEBUG] After fold, active_players count: {len(active_players)}")
            if len(active_players) == 1:
                # Only one player left, they win immediately
                print(f"[DEBUG] Calling _end_hand_early, winner: {active_players[0].user_id}")
                self._end_hand_early()
                return True, ""

        elif action == ActionType.CHECK:
            if player.current_bet < self.current_bet:
                return False, "无法过牌，需要跟注或弃牌"
            # Check is valid, no chips moved

        elif action == ActionType.CALL:
            call_amount = self.current_bet - player.current_bet
            actual = player.call(self.current_bet)
            self.pot_manager.add_bet(user_id, actual)

        elif action == ActionType.RAISE:
            if amount < self.current_bet + self.min_raise:
                return False, f"加注金额不足，最小加注: {self.current_bet + self.min_raise}"
            if amount > player.chips + player.current_bet:
                return False, "筹码不足"

            raise_amount = amount - player.current_bet
            old_bet = self.current_bet
            player.raise_bet(amount)
            self.pot_manager.add_bet(user_id, raise_amount)

            # Update min raise and reset acted_this_round (everyone needs to respond)
            self.min_raise = amount - old_bet
            self.current_bet = amount
            self.last_raiser_index = self.current_player_index
            self.acted_this_round = {user_id}  # Only raiser has acted

        elif action == ActionType.ALL_IN:
            all_in_amount = player.all_in()
            self.pot_manager.add_bet(user_id, all_in_amount)

            if player.current_bet > self.current_bet:
                self.min_raise = player.current_bet - self.current_bet
                self.current_bet = player.current_bet
                self.last_raiser_index = self.current_player_index
                self.acted_this_round = {user_id}  # Only all-in player has acted

        else:
            return False, "无效操作"

        # Record that this player has acted
        self.acted_this_round.add(user_id)

        # Clear current marker
        player.is_current = False

        # Check if betting round is complete
        if self._is_betting_round_complete():
            self._advance_phase()
        else:
            self._next_player()

        return True, ""

    def _is_betting_round_complete(self) -> bool:
        """Check if current betting round is complete."""
        active_players = [
            p for p in self.players.values()
            if p.is_in_hand() and p.status != PlayerStatus.ALL_IN
        ]

        if not active_players:
            return True

        # All active players must have matched the current bet
        for player in active_players:
            if player.current_bet < self.current_bet:
                return False

        # All active players must have acted
        for player in active_players:
            if player.user_id not in self.acted_this_round:
                return False

        return True

    def _next_player(self) -> None:
        """Move to next player to act."""
        # Skip folded and all-in players
        for _ in range(len(self.player_order)):
            self.current_player_index = self._next_active_player(self.current_player_index)
            player = self.players[self.player_order[self.current_player_index]]

            if player.is_in_hand() and player.status != PlayerStatus.ALL_IN:
                player.is_current = True
                return

        # No more players can act
        self._advance_phase()

    def _advance_phase(self) -> None:
        """Advance to next game phase."""
        # Reset betting for new round
        self.pot_manager.new_betting_round()
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.last_raiser_index = None
        self.acted_this_round = set()

        for player in self.players.values():
            player.reset_for_round()

        # Count active players
        active_players = [p for p in self.players.values() if p.is_in_hand()]

        if len(active_players) <= 1:
            # Only one player left, they win
            self._end_hand_early()
            return

        # Check if only all-in players remain
        non_all_in = [p for p in active_players if p.status == PlayerStatus.PLAYING]
        if not non_all_in:
            # Run out all community cards
            self._run_out_community_cards()
            return

        # Advance phase
        if self.phase == GamePhase.PREFLOP:
            self.phase = GamePhase.FLOP
            self._deal_flop()
        elif self.phase == GamePhase.FLOP:
            self.phase = GamePhase.TURN
            self._deal_turn()
        elif self.phase == GamePhase.TURN:
            self.phase = GamePhase.RIVER
            self._deal_river()
        elif self.phase == GamePhase.RIVER:
            self._showdown()
            return

        # Set first to act (starting from small blind for flop/turn/river)
        # In post-flop rounds, action starts from the small blind (first active player after dealer)
        self.current_player_index = self.sb_index
        # Find the first active player starting from SB
        player = self.players[self.player_order[self.current_player_index]]
        if not (player.is_in_hand() and player.status != PlayerStatus.ALL_IN):
            # SB might have folded or be all-in, find next active player
            for _ in range(len(self.player_order)):
                self.current_player_index = self._next_active_player(self.current_player_index)
                player = self.players[self.player_order[self.current_player_index]]
                if player.is_in_hand() and player.status != PlayerStatus.ALL_IN:
                    break
        player.is_current = True

    def _deal_flop(self) -> None:
        """Deal flop (3 community cards)."""
        self.deck.burn()
        self.community_cards.extend(self.deck.deal(3))

    def _deal_turn(self) -> None:
        """Deal turn (1 community card)."""
        self.deck.burn()
        self.community_cards.append(self.deck.deal_one())

    def _deal_river(self) -> None:
        """Deal river (1 community card)."""
        self.deck.burn()
        self.community_cards.append(self.deck.deal_one())

    def _run_out_community_cards(self) -> None:
        """Deal remaining community cards for all-in situation."""
        while len(self.community_cards) < 5:
            if len(self.community_cards) == 0:
                self._deal_flop()
            elif len(self.community_cards) == 3:
                self._deal_turn()
            elif len(self.community_cards) == 4:
                self._deal_river()

        self._showdown()

    def _end_hand_early(self) -> None:
        """End hand when only one player remains."""
        self.phase = GamePhase.SHOWDOWN

        # Find the winner
        active_players = [p for p in self.players.values() if p.is_in_hand()]
        if len(active_players) == 1:
            winner = active_players[0]

            # Get total pot from pot_manager (includes all bets, even from folded players)
            total_pot = self.pot_manager.get_total_pot()

            # Calculate chip changes
            # For each player: chip_change = final_chips - initial_chips
            # Since player.chips already has bets deducted, we need to track initial chips
            # chip_change for non-winners = -their_total_bet (they lost their bets)
            # chip_change for winner = total_pot - their_total_bet (they win the pot minus their own bet)
            chip_changes = {}

            # First, record what each player lost (their bets)
            for player in self.players.values():
                chip_changes[player.user_id] = -player.total_bet

            # Winner gains the entire pot (which includes all players' bets)
            # So winner's net change = total_pot - winner.total_bet
            # But we already set chip_changes[winner] = -winner.total_bet
            # Now add total_pot to it
            chip_changes[winner.user_id] += total_pot

            # Verify: sum of all chip_changes should be 0 (conservation of chips)
            total_change = sum(chip_changes.values())
            if total_change != 0:
                # This shouldn't happen, but log if it does
                print(f"[WARNING] _end_hand_early: chip_changes sum = {total_change}, should be 0")
                print(f"[DEBUG] chip_changes = {chip_changes}, total_pot = {total_pot}")

            print(f"[DEBUG] _end_hand_early: winner={winner.user_id}, total_pot={total_pot}")
            print(f"[DEBUG] _end_hand_early: chip_changes={chip_changes}")
            print(f"[DEBUG] _end_hand_early: winner.total_bet={winner.total_bet}, winner.chips before={winner.chips}")

            winner.chips += total_pot

            print(f"[DEBUG] _end_hand_early: winner.chips after={winner.chips}")

            # Store result for later use (in handle_hand_end)
            self._last_result = GameResult(
                winners=[{"user_id": winner.user_id, "amount": total_pot}],
                pot_amount=total_pot,
                community_cards=self.community_cards,
                player_hands={winner.user_id: winner.hole_cards},
                player_names={p.user_id: p.username for p in self.players.values()},
                chip_changes=chip_changes
            )

            self.phase = GamePhase.ENDED
            # Don't call on_hand_complete here - it will be called in handle_hand_end

    def _showdown(self) -> None:
        """Resolve hand at showdown."""
        self.phase = GamePhase.SHOWDOWN

        # Evaluate hands
        hand_rankings: Dict[int, EvaluatedHand] = {}
        active_players = [p for p in self.players.values() if p.is_in_hand()]
        folded_players = [p for p in self.players.values() if p.status == PlayerStatus.FOLDED]

        for player in active_players:
            hand = HandEvaluator.best_hand(player.hole_cards, self.community_cards)
            hand_rankings[player.user_id] = hand

        # Calculate pots - include folded players' bets
        active_ids = [p.user_id for p in active_players]
        all_in_ids = [p.user_id for p in active_players if p.status == PlayerStatus.ALL_IN]
        folded_ids = [p.user_id for p in folded_players]
        self.pot_manager.calculate_pots(active_ids, all_in_ids, folded_ids)

        # Calculate chip changes before distributing winnings
        # For each player: chip_change = winnings - total_bet
        chip_changes = {}

        # First, record what each player lost (their bets)
        for player in self.players.values():
            chip_changes[player.user_id] = -player.total_bet

        # Distribute winnings
        rankings_tuple = {uid: (hand.rank, hand.kickers) for uid, hand in hand_rankings.items()}
        winnings = self.pot_manager.distribute_winnings(rankings_tuple)

        # Award chips and update chip_changes
        for user_id, amount in winnings.items():
            self.players[user_id].chips += amount
            chip_changes[user_id] += amount

        # Verify: sum of all chip_changes should be 0 (conservation of chips)
        total_change = sum(chip_changes.values())
        if total_change != 0:
            print(f"[WARNING] _showdown: chip_changes sum = {total_change}, should be 0")
            print(f"[DEBUG] chip_changes = {chip_changes}")
            print(f"[DEBUG] winnings = {winnings}")

        # Prepare result
        winners = [
            {"user_id": uid, "amount": amount, "hand": HandEvaluator.get_hand_name(hand_rankings[uid])}
            for uid, amount in winnings.items()
        ]

        # Store result for get_state
        self._last_result = GameResult(
            winners=winners,
            pot_amount=self.pot_manager.get_total_pot(),
            community_cards=self.community_cards,
            player_hands={p.user_id: p.hole_cards for p in active_players},
            player_names={p.user_id: p.username for p in self.players.values()},
            chip_changes=chip_changes
        )

        self.phase = GamePhase.ENDED
        # Don't call on_hand_complete here - it will be called in handle_hand_end

    def get_state(self, for_user_id: Optional[int] = None) -> dict:
        """Get current game state."""
        # Get winners from last hand result if available
        winners = []
        if hasattr(self, '_last_result') and self._last_result:
            winners = self._last_result.winners

        return {
            "room_id": 0,  # Will be set by caller
            "phase": self.phase.value,
            "community_cards": [
                {"rank": c.rank, "suit": c.suit}
                for c in self.community_cards
            ],
            "pots": self.pot_manager.to_dict(),
            "current_pot": self.pot_manager.get_total_pot(),
            "current_bet": self.current_bet,
            "min_raise": self.current_bet + self.min_raise,  # Total amount needed for min raise
            "current_player_id": self.player_order[self.current_player_index] if self.player_order and self.current_player_index < len(self.player_order) else None,
            "dealer_seat": self.players[self.player_order[self.dealer_index]].seat_index if self.player_order and self.dealer_index < len(self.player_order) else 0,
            "sb_seat": self.players[self.player_order[self.sb_index]].seat_index if self.player_order and self.sb_index < len(self.player_order) else 0,
            "bb_seat": self.players[self.player_order[self.bb_index]].seat_index if self.player_order and self.bb_index < len(self.player_order) else 0,
            "players": [
                p.to_dict(show_cards=(
                    self.phase == GamePhase.SHOWDOWN or
                    for_user_id == p.user_id
                ))
                for p in self.players.values()
            ],
            "winners": winners,
            "is_active": self.phase not in [GamePhase.ENDED]
        }
