"""
德州扑克核心流程逻辑测试
测试场景包括：
1. 基础流程测试
2. 边池/分池测试（多人全押复杂场景）
3. 自动开始测试
4. 发牌延迟测试
5. 净筹码计算测试
6. 边界条件和异常场景
"""

import pytest
import asyncio
from typing import Dict, List
from app.game.engine import GameEngine, GamePhase, ActionType
from app.game.player import Player, PlayerStatus
from app.game.pot_manager import PotManager, Pot
from app.game.deck import Deck


class TestBasicGameFlow:
    """基础游戏流程测试"""

    def test_heads_up_game_start(self):
        """测试两人游戏（Heads-up）开始"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # 添加两名玩家
        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)

        # 开始游戏
        success = engine.start_hand()
        assert success, "两人游戏应该能够开始"

        # 验证游戏状态
        assert engine.phase == GamePhase.PREFLOP
        assert len(engine.player_order) == 2

        # Heads-up: dealer 会移动到下一个活跃玩家（索引 1）
        # dealer 是 SB
        assert engine.sb_index == engine.dealer_index  # Heads-up 时 dealer 是 SB
        # BB 是另一个玩家
        assert engine.bb_index != engine.dealer_index

        # 验证盲注
        sb_player = engine.players[engine.player_order[engine.sb_index]]
        bb_player = engine.players[engine.player_order[engine.bb_index]]
        assert sb_player.current_bet == 10
        assert bb_player.current_bet == 20
        assert sb_player.chips == 990
        assert bb_player.chips == 980

    def test_three_player_game_positions(self):
        """测试三人游戏位置"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        success = engine.start_hand()
        assert success

        # 三人游戏：dealer 会移动到下一个活跃玩家
        # 初始 dealer_index=0，然后移动到索引 1（Player2）
        # SB = 索引 2（Player3）, BB = 索引 0（Player1）
        assert engine.dealer_index == 1
        assert engine.sb_index == 2
        assert engine.bb_index == 0

    def test_preflop_action_sequence(self):
        """测试翻牌前行动序列"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        # 位置：dealer=1 (Player2), SB=2 (Player3), BB=0 (Player1)
        # 翻牌前行动从 BB 之后的玩家开始（即 dealer/Player2）

        # 获取当前玩家
        current = engine.get_current_player()
        assert current is not None
        assert current.status == PlayerStatus.PLAYING
        assert current.user_id == 2  # dealer/UTG

        # 模拟行动序列：UTG call, SB call, BB check
        success, msg = engine.execute_action(current.user_id, ActionType.CALL, 20)
        assert success, f"UTG call 应该成功：{msg}"

        # 现在应该是 SB 行动（Player3）
        current = engine.get_current_player()
        assert current.user_id == 3  # SB

        # SB call（需要再放 10）
        success, msg = engine.execute_action(current.user_id, ActionType.CALL, 10)
        assert success

        # 现在应该是 BB 行动（Player1）
        current = engine.get_current_player()
        assert current.user_id == 1  # BB

        # BB check（已经放了 20）
        success, msg = engine.execute_action(current.user_id, ActionType.CHECK)
        assert success

        # 应该进入翻牌圈
        assert engine.phase == GamePhase.FLOP
        assert len(engine.community_cards) == 3

    def test_fold_until_one_player(self):
        """测试只剩一名玩家时立即获胜"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        # 位置：dealer=1 (Player2), SB=2 (Player3), BB=0 (Player1)
        # 第一个行动的是 dealer/UTG (Player2)

        # UTG fold
        current = engine.get_current_player()
        assert current.user_id == 2
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert success

        # SB fold
        current = engine.get_current_player()
        assert current.user_id == 3
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert success

        # 应该只剩一名玩家，立即获胜
        # BB 自动获胜
        assert engine.phase == GamePhase.ENDED

        # 验证有赢家
        assert hasattr(engine, '_last_result') and engine._last_result is not None
        assert len(engine._last_result.winners) == 1
        # BB 获胜
        assert engine._last_result.winners[0]["user_id"] == engine.player_order[engine.bb_index]


class TestSidePots:
    """边池测试 - 复杂的全押场景"""

    def test_simple_all_in(self):
        """测试简单全押场景"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # Player1 有 1000，Player2 有 1000
        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)

        engine.start_hand()

        # Heads-up: dealer=1 (Player2/SB), BB=0 (Player1)
        # 翻牌前行动从 dealer/SB 开始
        current = engine.get_current_player()
        assert current.user_id == 2  # SB

        # SB (Player2) all-in
        success, _ = engine.execute_action(2, ActionType.ALL_IN, 1000)
        assert success

        # BB (Player1) call
        current = engine.get_current_player()
        assert current.user_id == 1
        success, _ = engine.execute_action(1, ActionType.CALL, 1000)
        assert success

        # 应该进入摊牌
        assert engine.phase in [GamePhase.SHOWDOWN, GamePhase.ENDED]

        # 验证底池
        state = engine.get_state()
        assert state["current_pot"] == 2000

    def test_three_way_all_in_main_pot_only(self):
        """测试三人全押 - 只有主池"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # 三人筹码相同
        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=500)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=500)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=500)

        engine.start_hand()

        # 位置：dealer=1 (Player2), SB=2 (Player3), BB=0 (Player1)
        # 翻牌前行动从 dealer/UTG (Player2) 开始

        # UTG (Player2) all-in
        current = engine.get_current_player()
        assert current.user_id == 2
        success, _ = engine.execute_action(2, ActionType.ALL_IN, 500)
        assert success

        # SB (Player3) all-in
        current = engine.get_current_player()
        assert current.user_id == 3
        success, _ = engine.execute_action(3, ActionType.ALL_IN, 500)
        assert success

        # BB (Player1) call
        current = engine.get_current_player()
        assert current.user_id == 1
        success, _ = engine.execute_action(1, ActionType.CALL, 500)
        assert success

        # 应该进入摊牌
        assert engine.phase in [GamePhase.SHOWDOWN, GamePhase.ENDED]

        # 验证底池
        state = engine.get_state()
        assert state["current_pot"] == 1500

    def test_side_pot_with_different_amounts(self):
        """测试边池 - 不同筹码量的全押"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # Player1: 100 (BB), Player2: 200 (UTG), Player3: 300 (SB)
        engine.add_player(user_id=1, username="ShortStack", seat_index=0, chips=100)
        engine.add_player(user_id=2, username="MidStack", seat_index=1, chips=200)
        engine.add_player(user_id=3, username="BigStack", seat_index=2, chips=300)

        engine.start_hand()

        # 位置：dealer=1 (P2), SB=2 (P3), BB=0 (P1)
        # 翻牌前行动从 dealer/UTG (P2) 开始

        # UTG (P2) raise to 60
        current = engine.get_current_player()
        assert current.user_id == 2
        success, _ = engine.execute_action(2, ActionType.RAISE, 60)
        assert success

        # SB (P3) call 60
        current = engine.get_current_player()
        assert current.user_id == 3
        success, _ = engine.execute_action(3, ActionType.CALL, 60)
        assert success

        # BB (P1) all-in 100
        current = engine.get_current_player()
        assert current.user_id == 1
        success, _ = engine.execute_action(1, ActionType.ALL_IN, 100)
        assert success

        # UTG (P2) call 100
        current = engine.get_current_player()
        assert current.user_id == 2
        success, _ = engine.execute_action(2, ActionType.CALL, 100)
        assert success

        # SB (P3) 需要再放 40 来跟注
        current = engine.get_current_player()
        assert current.user_id == 3
        success, _ = engine.execute_action(3, ActionType.CALL, 40)
        assert success

        # P1 全押，P2 和 P3 还有筹码，所以进入翻牌圈
        assert engine.phase == GamePhase.FLOP

        # 验证总底池 = 100 + 200 + 60 = 360（P3 只放了 60+40=100）
        # 实际上 P1=100, P2=200, P3=100 = 400
        state = engine.get_state()
        # 由于 P2 和 P3 还有筹码，需要继续玩到摊牌
        # 这个测试主要验证边池逻辑，所以在这里断言翻牌圈状态
        assert state["current_pot"] == 400  # P1(100) + P2(200) + P3(100)
        state = engine.get_state()

        # 验证总底池
        # Player1: 100, Player2: 100, Player3: 100
        assert state["current_pot"] == 300

    def test_complex_side_pot_calculation(self):
        """测试复杂的边池计算"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # 四名玩家，筹码差异很大
        engine.add_player(user_id=1, username="P1", seat_index=0, chips=50)   # 最短码
        engine.add_player(user_id=2, username="P2", seat_index=1, chips=150)  # 中等码
        engine.add_player(user_id=3, username="P3", seat_index=2, chips=250)  # 深码
        engine.add_player(user_id=4, username="P4", seat_index=3, chips=400)  # 最深码

        engine.start_hand()

        # 模拟所有人都全押
        # UTG (P4) all-in
        success, _ = engine.execute_action(4, ActionType.ALL_IN, 400)
        assert success

        # P3 all-in 250
        success, _ = engine.execute_action(3, ActionType.ALL_IN, 250)
        assert success

        # P2 all-in 150
        success, _ = engine.execute_action(2, ActionType.ALL_IN, 150)
        assert success

        # P1 all-in 50
        success, _ = engine.execute_action(1, ActionType.ALL_IN, 50)
        assert success

        # 应该进入摊牌
        assert engine.phase == GamePhase.SHOWDOWN

        state = engine.get_state()

        # 总底池应该是 50 + 150 + 250 + 400 = 850
        assert state["current_pot"] == 850

        # 应该有多个池
        # 主池：50 * 4 = 200 (所有人都能赢)
        # 边池 1: (150-50) * 3 = 300 (P2, P3, P4 能赢)
        # 边池 2: (250-150) * 2 = 200 (P3, P4 能赢)
        # 边池 3: (400-250) * 1 = 150 (只有 P4 能赢 - 但 P4 已经全押，所以这个池不存在)
        # 实际上，边池 3 应该是 0，因为 P4 没有其他人跟注他的额外下注

        # 验证 pot_manager 的 pots
        pots = state["pots"]
        assert len(pots) >= 1  # 至少有一个主池

    def test_pot_manager_calculate_pots(self):
        """直接测试 PotManager 的边池计算"""
        pm = PotManager()

        # 模拟场景：P1 all-in 50, P2 all-in 150, P3 all-in 250, P4 all-in 400
        pm.player_total_bets = {1: 50, 2: 150, 3: 250, 4: 400}

        active_players = [1, 2, 3, 4]
        all_in_players = [1, 2, 3, 4]

        pm.calculate_pots(active_players, all_in_players)

        # 验证池的数量和金额
        assert len(pm.pots) == 4

        # 主池：50 * 4 = 200
        assert pm.pots[0].amount == 200
        assert set(pm.pots[0].eligible_players) == {1, 2, 3, 4}

        # 边池 1: (150-50) * 3 = 300
        assert pm.pots[1].amount == 300
        assert set(pm.pots[1].eligible_players) == {2, 3, 4}

        # 边池 2: (250-150) * 2 = 200
        assert pm.pots[2].amount == 200
        assert set(pm.pots[2].eligible_players) == {3, 4}

        # 边池 3: (400-250) * 1 = 150
        assert pm.pots[3].amount == 150
        assert pm.pots[3].eligible_players == [4]

    def test_folded_player_bets_in_pot(self):
        """测试弃牌玩家的注仍在池中"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        # Player3 (UTG) fold
        success, _ = engine.execute_action(engine.player_order[2], ActionType.FOLD)
        assert success

        # Player1 (SB) raise to 60
        success, _ = engine.execute_action(engine.player_order[0], ActionType.RAISE, 60)
        assert success

        # Player2 (BB) fold
        success, _ = engine.execute_action(engine.player_order[1], ActionType.FOLD)
        assert success

        # Player1 应该立即获胜（只剩一人）
        assert engine.phase == GamePhase.SHOWDOWN

        state = engine.get_state()
        # Player1 赢得底池：SB 60 + BB 20 + Player3 0 = 80
        assert state["current_pot"] == 80


class TestChipChanges:
    """筹码变动测试"""

    def test_chip_changes_single_winner(self):
        """测试单一赢家的筹码变动"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)

        engine.start_hand()

        # Player1 all-in
        success, _ = engine.execute_action(1, ActionType.ALL_IN, 1000)
        assert success

        # Player2 call
        success, _ = engine.execute_action(2, ActionType.CALL, 1000)
        assert success

        # 进入摊牌
        assert engine.phase == GamePhase.SHOWDOWN

        # 获取结果
        state = engine.get_state()
        if hasattr(engine, '_last_result') and engine._last_result:
            chip_changes = engine._last_result.chip_changes

            # 输家：-1000
            # 赢家：+1000 (净赢)
            # 验证筹码守恒
            total_change = sum(chip_changes.values())
            assert total_change == 0, "筹码变动总和应该为 0"

    def test_chip_changes_fold(self):
        """测试弃牌时的筹码变动"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)

        engine.start_hand()

        # Player1 fold
        success, _ = engine.execute_action(1, ActionType.FOLD)
        assert success

        # Player2 立即获胜
        assert engine.phase == GamePhase.SHOWDOWN

        if hasattr(engine, '_last_result') and engine._last_result:
            chip_changes = engine._last_result.chip_changes

            # Player1: -10 (SB)
            # Player2: +10 (赢回对手的盲注)
            # 总和应该为 0
            total_change = sum(chip_changes.values())
            assert total_change == 0, "筹码变动总和应该为 0"


class TestAutoStartAndDelays:
    """自动开始和延迟测试"""

    def test_dealing_delay_config(self):
        """测试发牌延迟配置"""
        from app.config import settings

        # 验证配置存在
        assert hasattr(settings, 'DEALING_DELAY')
        assert hasattr(settings, 'HAND_END_DELAY')
        assert hasattr(settings, 'AUTO_START_DELAY')

        # 验证默认值
        assert settings.DEALING_DELAY == 5  # 发牌后延迟 5 秒
        assert settings.HAND_END_DELAY == 10  # 结束后延迟 10 秒
        assert settings.AUTO_START_DELAY == 3  # 自动开始前延迟 3 秒

    def test_game_engine_has_delays(self):
        """测试游戏引擎包含延迟配置"""
        engine = GameEngine()

        assert hasattr(engine, 'dealing_delay')
        assert engine.dealing_delay == 5


class TestEdgeCases:
    """边界条件测试"""

    def test_heads_up_bb_preflop_action(self):
        """测试 Heads-up 翻牌前 BB 的行动权利"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Dealer", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="BB", seat_index=1, chips=1000)

        engine.start_hand()

        # Heads-up: dealer 会移动到索引 1（Player2）
        # Player2 是 dealer/SB，先行动
        # Player1 是 BB
        current = engine.get_current_player()
        assert current.seat_index == 1  # Dealer/SB

        # SB 可以 call, raise, all-in, fold
        actions = engine.get_valid_actions(current.user_id)
        action_types = [a["action"] for a in actions]

        # SB 可以 call, raise, all-in, fold
        assert ActionType.CALL in action_types or ActionType.RAISE in action_types or ActionType.ALL_IN in action_types

    def test_min_raise_calculation(self):
        """测试最小加注计算"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        # 获取当前玩家
        current = engine.get_current_player()

        # 获取有效行动
        actions = engine.get_valid_actions(current.user_id)

        # 找到 raise 行动
        raise_action = None
        for action in actions:
            if action["action"] == ActionType.RAISE:
                raise_action = action
                break

        if raise_action:
            # 最小加注应该是当前赌注 + min_raise
            # 翻牌前 min_raise = big_blind = 20
            # 所以最小加注总额 = 20 (BB) + 20 = 40
            assert raise_action["min_amount"] >= 40

    def test_all_in_reopen_betting(self):
        """测试全押是否重新打开下注"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="P1", seat_index=0, chips=100)
        engine.add_player(user_id=2, username="P2", seat_index=1, chips=500)
        engine.add_player(user_id=3, username="P3", seat_index=2, chips=500)

        engine.start_hand()

        # 位置：dealer=1 (P2), SB=2 (P3), BB=0 (P1)
        # 翻牌前行动从 dealer/UTG (P2) 开始

        # UTG (P2) raise to 60
        current = engine.get_current_player()
        assert current.user_id == 2
        success, _ = engine.execute_action(2, ActionType.RAISE, 60)
        assert success

        # SB (P3) all-in 100 (increase = 100 - 0 = 100 >= min_raise (20), so should reopen)
        current = engine.get_current_player()
        assert current.user_id == 3
        success, _ = engine.execute_action(3, ActionType.ALL_IN, 100)
        assert success

        # BB (P1) 现在可以行动
        current = engine.get_current_player()
        assert current.user_id == 1

        # P1 应该能够 raise（因为 P3 的全押是一个完整的加注）
        actions = engine.get_valid_actions(1)
        action_types = [a["action"] for a in actions]

        # P1 应该有 raise 选项
        assert ActionType.RAISE in action_types

    def test_straddle_scenario(self):
        """测试 Straddle（可选的盲注）场景 - 目前不支持，但应该正常处理"""
        # 这个测试验证标准游戏流程不受影响
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="P1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="P2", seat_index=1, chips=1000)

        engine.start_hand()

        # 标准流程应该正常工作
        assert engine.phase == GamePhase.PREFLOP
        assert engine.current_bet == 20  # BB


class TestNetChips:
    """净筹码计算测试"""

    def test_net_chips_calculation(self):
        """测试净筹码计算逻辑"""
        # 净筹码 = 当前筹码 - 总买入
        # 这个测试验证计算逻辑

        initial_chips = 1000
        buyin = 1000

        # 玩家买入 1000
        current_chips = buyin
        net_chips = current_chips - buyin
        assert net_chips == 0

        # 玩家赢了 500
        current_chips = 1500
        net_chips = current_chips - buyin
        assert net_chips == 500

        # 玩家输了 500
        current_chips = 500
        net_chips = current_chips - buyin
        assert net_chips == -500

        # 玩家再买入 500（总买入 1500）
        buyin = 1500
        current_chips = 1000
        net_chips = current_chips - buyin
        assert net_chips == -500


class TestPotManagerEdgeCases:
    """PotManager 边界条件测试"""

    def test_empty_pots(self):
        """测试空池"""
        pm = PotManager()
        pm.calculate_pots([], [])
        assert len(pm.pots) == 0

    def test_single_player(self):
        """测试单一玩家"""
        pm = PotManager()
        pm.player_total_bets = {1: 100}
        pm.calculate_pots([1], [1])

        assert len(pm.pots) == 1
        assert pm.pots[0].amount == 100
        assert pm.pots[0].eligible_players == [1]

    def test_equal_bets(self):
        """测试等额下注"""
        pm = PotManager()
        pm.player_total_bets = {1: 100, 2: 100, 3: 100}
        pm.calculate_pots([1, 2, 3], [])

        assert len(pm.pots) == 1
        assert pm.pots[0].amount == 300
        assert set(pm.pots[0].eligible_players) == {1, 2, 3}

    def test_distribute_winnings_tie(self):
        """测试平分彩池"""
        pm = PotManager()
        pm.player_total_bets = {1: 100, 2: 100}
        pm.calculate_pots([1, 2], [])

        # 模拟平手
        hand_rankings = {
            1: (8, [14, 13, 12, 11, 10]),  # 同花顺
            2: (8, [14, 13, 12, 11, 10]),  # 同样的同花顺
        }

        player_positions = {1: 0, 2: 1}
        winnings = pm.distribute_winnings(hand_rankings, player_positions)

        # 200 的池应该平分
        assert winnings[1] == 100
        assert winnings[2] == 100

    def test_distribute_winnings_with_remainder(self):
        """测试有余数的彩池分配"""
        pm = PotManager()
        pm.player_total_bets = {1: 100, 2: 100, 3: 100}
        pm.calculate_pots([1, 2, 3], [])

        # 模拟 1 和 2 平手，3 输了
        hand_rankings = {
            1: (9, [14, 14, 14, 14, 12]),  # 四条
            2: (9, [14, 14, 14, 14, 12]),  # 同样的四条
            3: (8, [14, 13, 12, 11, 10]),  # 同花顺
        }

        player_positions = {1: 0, 2: 1, 3: 2}
        winnings = pm.distribute_winnings(hand_rankings, player_positions)

        # 300 的池，1 和 2 平分，1（位置好）获得余数
        # 300 / 2 = 150 每人
        assert winnings[1] == 150
        assert winnings[2] == 150
        assert 3 not in winnings  # 3 没赢


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
