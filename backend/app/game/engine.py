import logging
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
from dataclasses import dataclass
import asyncio
from app.game.deck import Deck, Card
from app.game.player import Player, PlayerStatus
from app.game.hand_evaluator import HandEvaluator, EvaluatedHand
from app.game.pot_manager import PotManager
from app.config import settings

logger = logging.getLogger(__name__)


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
        self.dealing_delay = settings.DEALING_DELAY  # 发牌后等待时间

        # Game state
        self.phase = GamePhase.ENDED
        self.deck: Optional[Deck] = None
        self.community_cards: List[Card] = []
        self.players: Dict[int, Player] = {}  # user_id -> Player
        self.player_order: List[int] = []  # user_ids in seat order

        # Position markers
        self.dealer_index: int = 0
        self.dealer_user_id: Optional[int] = None  # Track dealer by user_id for stability
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
        self._last_result = None
        self._show_cards_at_end = False

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
        # 使用统一的活跃玩家判断条件：READY 或 PLAYING 或 is_in_hand()
        # 这与 _next_active_player() 的判断条件保持一致
        active_players = [
            uid for uid in self.player_order
            if self.players[uid].status in [PlayerStatus.READY, PlayerStatus.PLAYING]
            or self.players[uid].is_in_hand()
        ]

        if len(active_players) < 2:
            return

        # Restore dealer_index from dealer_user_id if the player is still present
        if self.dealer_user_id is not None and self.dealer_user_id in self.player_order:
            self.dealer_index = self.player_order.index(self.dealer_user_id)
        else:
            # Clamp dealer_index to valid range
            if self.dealer_index >= len(self.player_order):
                self.dealer_index = 0

        # Move dealer button to next active player
        self.dealer_index = self._next_active_player(self.dealer_index)
        self.dealer_user_id = self.player_order[self.dealer_index]

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
            # 统一使用 is_in_hand() 或状态为 READY/PLAYING 来判断活跃玩家
            # is_in_hand() 返回 True 如果状态是 PLAYING 或 ALL_IN
            if player.is_in_hand() or player.status == PlayerStatus.READY:
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
                # 注意：deal_cards() 会将状态改为 PLAYING
                # 如果玩家盲注后筹码为 0，需要恢复 ALL_IN 状态
                if player.chips == 0 and player.total_bet > 0:
                    player.status = PlayerStatus.ALL_IN
            elif player.status == PlayerStatus.ALL_IN:
                # Player went all-in posting blind - deal cards but keep ALL_IN status
                cards = self.deck.deal(2)
                player.hole_cards = cards

    def _set_first_to_act_preflop(self) -> None:
        """Set first player to act in preflop (after BB)."""
        start_index = self.bb_index
        for _ in range(len(self.player_order)):
            start_index = self._next_active_player(start_index)
            player = self.players[self.player_order[start_index]]
            if player.status == PlayerStatus.PLAYING and player.chips > 0:
                self.current_player_index = start_index
                player.is_current = True
                return

        # No player can act (all ALL_IN) - check if round complete and advance
        self.current_player_index = self._next_active_player(self.bb_index)
        if self._is_betting_round_complete():
            # 翻牌前全押，无需玩家行动，直接发完公共牌
            # _advance_phase() 返回 False 表示无需行动（all-in 情况）
            needs_action = self._advance_phase()
            # 断言验证：翻牌前全押不应需要玩家行动
            assert needs_action == False, "Preflop all-in should not require player action"

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

        # If min_raise is None, raises are closed (after an all-in that didn't fully raise)
        if can_raise and self.min_raise is not None:
            min_raise_total = self.current_bet + self.min_raise
            max_raise = player.chips + player.current_bet

            # Only add raise option if min raise is valid (min <= max)
            # This prevents raise option after an all-in that didn't fully raise
            if max_raise > self.current_bet and min_raise_total <= max_raise:
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
            logger.debug(f"After fold, active_players count: {len(active_players)}")
            if len(active_players) == 1:
                # Only one player left, they win immediately
                logger.debug(f"Calling _end_hand_early, winner: {active_players[0].user_id}")
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
            # If min_raise is None, raises are closed (after an all-in that didn't fully raise)
            if self.min_raise is None:
                return False, "当前轮次不允许加注"
            if amount < self.current_bet + self.min_raise:
                return False, f"加注金额不足，最小加注：{self.current_bet + self.min_raise}"
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
                increase = player.current_bet - self.current_bet
                if increase >= self.min_raise:
                    # Full raise - reopen betting for all other players
                    self.min_raise = increase
                    self.current_bet = player.current_bet
                    self.last_raiser_index = self.current_player_index
                    self.acted_this_round = {user_id}
                else:
                    # Not a full raise - update current bet but don't reopen betting
                    # Set min_raise to None to prevent further raises this round
                    self.current_bet = player.current_bet
                    self.min_raise = None  # Mark that raises are closed

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

    def _advance_phase(self) -> bool:
        """
        Advance to next game phase.
        Returns True if there's a player who needs to act (delay should be applied),
        False if no player action needed (all-in situation or immediate showdown).
        """
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
            return False

        # Check if only all-in players remain (or at most 1 non-all-in)
        non_all_in = [p for p in active_players if p.status == PlayerStatus.PLAYING]
        if len(non_all_in) <= 1:
            # Run out all community cards
            self._run_out_community_cards()
            return False

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
            return False

        # Set first to act for post-flop rounds
        # In heads-up, BB (non-dealer) acts first post-flop
        # In multi-way, SB (first player after dealer) acts first
        if len(self.player_order) == 2:
            self.current_player_index = self.bb_index
        else:
            self.current_player_index = self.sb_index
        # Find the first active player starting from that position
        player = self.players[self.player_order[self.current_player_index]]
        if not (player.is_in_hand() and player.status != PlayerStatus.ALL_IN):
            # SB might have folded or be all-in, find next active player
            for _ in range(len(self.player_order)):
                self.current_player_index = self._next_active_player(self.current_player_index)
                player = self.players[self.player_order[self.current_player_index]]
                if player.is_in_hand() and player.status != PlayerStatus.ALL_IN:
                    break
        player.is_current = True
        return True

    def _deal_flop(self) -> None:
        """Deal flop (3 community cards)."""
        self.deck.burn()
        self.community_cards.extend(self.deck.deal(3))

    def _deal_turn(self) -> None:
        """Deal turn (1 community card)."""
        self.deck.burn()
        card = self.deck.deal_one()
        if card:
            self.community_cards.append(card)
        else:
            logger.error("deck.deal_one() returned None in _deal_turn")

    def _deal_river(self) -> None:
        """Deal river (1 community card)."""
        self.deck.burn()
        card = self.deck.deal_one()
        if card:
            self.community_cards.append(card)
        else:
            logger.error("deck.deal_one() returned None in _deal_river")

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
                # 筹码守恒被破坏，这是严重错误
                logger.error(f"_end_hand_early: chip_changes sum = {total_change}, should be 0")
                logger.debug(f"chip_changes = {chip_changes}, total_pot = {total_pot}")
                # 在开发环境抛出异常，便于及时发现 bug
                if settings.DEBUG:
                    raise AssertionError(f"Chip conservation violated in _end_hand_early: sum = {total_change}")

            logger.debug(f"_end_hand_early: winner={winner.user_id}, total_pot={total_pot}")
            logger.debug(f"_end_hand_early: chip_changes={chip_changes}")
            logger.debug(f"_end_hand_early: winner.total_bet={winner.total_bet}, winner.chips before={winner.chips}")

            winner.chips += total_pot

            logger.debug(f"_end_hand_early: winner.chips after={winner.chips}")

            # Store result for later use (in handle_hand_end)
            # Don't expose cards when winning by fold
            self._last_result = GameResult(
                winners=[{"user_id": winner.user_id, "amount": total_pot}],
                pot_amount=total_pot,
                community_cards=self.community_cards,
                player_hands={},  # Empty - no showdown occurred
                player_names={p.user_id: p.username for p in self.players.values()},
                chip_changes=chip_changes
            )

            self._show_cards_at_end = True  # Show winner's cards at end
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
        player_positions = {p.user_id: p.seat_index for p in self.players.values()}
        winnings = self.pot_manager.distribute_winnings(rankings_tuple, player_positions)

        # Award chips and update chip_changes
        for user_id, amount in winnings.items():
            self.players[user_id].chips += amount
            chip_changes[user_id] += amount

        # Verify: sum of all chip_changes should be 0 (conservation of chips)
        total_change = sum(chip_changes.values())
        if total_change != 0:
            # 筹码守恒被破坏，这是严重错误
            logger.error(f"_showdown: chip_changes sum = {total_change}, should be 0")
            logger.debug(f"chip_changes = {chip_changes}")
            logger.debug(f"winnings = {winnings}")
            # 在开发环境抛出异常，便于及时发现 bug
            if settings.DEBUG:
                raise AssertionError(f"Chip conservation violated in _showdown: sum = {total_change}")

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

        self._show_cards_at_end = True
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
            "min_raise": self.current_bet + self.min_raise if self.min_raise is not None else None,  # Total amount needed for min raise
            "current_player_id": self.player_order[self.current_player_index] if self.player_order and self.current_player_index < len(self.player_order) else None,
            "dealer_seat": self.players[self.player_order[self.dealer_index]].seat_index if self.player_order and self.dealer_index < len(self.player_order) else 0,
            "sb_seat": self.players[self.player_order[self.sb_index]].seat_index if self.player_order and self.sb_index < len(self.player_order) else 0,
            "bb_seat": self.players[self.player_order[self.bb_index]].seat_index if self.player_order and self.bb_index < len(self.player_order) else 0,
            "players": [
                p.to_dict(show_cards=(
                    self.phase == GamePhase.SHOWDOWN or
                    (getattr(self, '_show_cards_at_end', False) and p.is_in_hand()) or
                    for_user_id == p.user_id
                ))
                for p in self.players.values()
            ],
            "winners": winners,
            "is_active": self.phase not in [GamePhase.ENDED]
        }
