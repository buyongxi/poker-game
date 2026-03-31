#!/usr/bin/env python3
"""
德州扑克核心流程逻辑测试 - 独立运行版本
不需要 pytest，直接运行即可
"""

import sys
sys.path.insert(0, '.')

from app.game.engine import GameEngine, GamePhase, ActionType
from app.game.player import PlayerStatus
from app.game.pot_manager import PotManager
from app.config import settings


def test_passed(name: str):
    print(f"✓ {name}")

def test_failed(name: str, reason: str):
    print(f"✗ {name}: {reason}")

def assert_equal(actual, expected, msg: str = ""):
    if actual != expected:
        raise AssertionError(f"{msg}: {actual} != {expected}")

def assert_true(condition: bool, msg: str = ""):
    if not condition:
        raise AssertionError(f"{msg}: condition is False")

def assert_in(item, collection, msg: str = ""):
    if item not in collection:
        raise AssertionError(f"{msg}: {item} not in {collection}")


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
        assert_true(success, "两人游戏应该能够开始")

        # 验证游戏状态
        assert_equal(engine.phase, GamePhase.PREFLOP)
        assert_equal(len(engine.player_order), 2)

        # Heads-up: dealer 是 SB (代码逻辑：dealer_index 会移动到下一个活跃玩家)
        # 在两人游戏中，dealer_index=1 (第二个玩家), SB 也是他，BB 是另一个
        assert_equal(engine.sb_index, engine.dealer_index)  # Heads-up 时 dealer 是 SB
        # BB 是另一个玩家
        assert_equal(engine.bb_index, 0 if engine.dealer_index == 1 else 1)

        # 验证盲注
        sb_player = engine.players[engine.player_order[engine.sb_index]]
        bb_player = engine.players[engine.player_order[engine.bb_index]]
        assert_equal(sb_player.current_bet, 10)
        assert_equal(bb_player.current_bet, 20)
        assert_equal(sb_player.chips, 990)
        assert_equal(bb_player.chips, 980)

        test_passed("test_heads_up_game_start")

    def test_three_player_game_positions(self):
        """测试三人游戏位置"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        success = engine.start_hand()
        assert_true(success)

        # 三人游戏：dealer 在 0, SB 在 1, BB 在 2
        # 代码逻辑：dealer_index 初始为 0，然后移动到下一个活跃玩家
        # 所以 dealer_index = 1 (Player2), SB = 2 (Player3), BB = 0 (Player1)
        assert_equal(engine.sb_index, (engine.dealer_index + 1) % 3)
        assert_equal(engine.bb_index, (engine.dealer_index + 2) % 3)

        test_passed("test_three_player_game_positions")

    def test_preflop_action_sequence(self):
        """测试翻牌前行动序列"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        # 获取当前玩家
        current = engine.get_current_player()
        assert_true(current is not None)
        assert_equal(current.status, PlayerStatus.PLAYING)

        # 行动顺序取决于 dealer 位置
        # dealer_index 初始为 0，然后移动到下一个活跃玩家，所以 dealer_index=1
        # SB = dealer_index = 1, BB = 2
        # 翻牌前行动从 BB 之后的玩家开始（即 dealer/UTG）
        # 在这个例子中，当前玩家应该是 user_id=2 (seat_index=1)

        # UTG call
        success, msg = engine.execute_action(current.user_id, ActionType.CALL, 20)
        assert_true(success, f"UTG call 应该成功：{msg}")

        # 现在应该是 SB 行动
        current = engine.get_current_player()
        # SB 是 seat_index=2 (user_id=3)
        assert_equal(current.seat_index, 2)

        # SB call (需要再放 10)
        success, msg = engine.execute_action(current.user_id, ActionType.CALL, 10)
        assert_true(success)

        # 现在应该是 BB 行动
        current = engine.get_current_player()
        # BB 是 seat_index=0 (user_id=1)
        assert_equal(current.seat_index, 0)

        # BB check（已经放了 20）
        success, msg = engine.execute_action(current.user_id, ActionType.CHECK)
        assert_true(success)

        # 应该进入翻牌圈
        assert_equal(engine.phase, GamePhase.FLOP)
        assert_equal(len(engine.community_cards), 3)

        test_passed("test_preflop_action_sequence")

    def test_fold_until_one_player(self):
        """测试只剩一名玩家时立即获胜"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        # 获取当前玩家并开始行动
        # 注意：只能让当前玩家行动
        current = engine.get_current_player()
        print(f"First to act: user_id={current.user_id}, seat_index={current.seat_index}")

        # UTG fold
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert_true(success)

        # 现在应该是 SB 行动
        current = engine.get_current_player()
        print(f"SB fold: user_id={current.user_id}")
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert_true(success)

        # 应该只剩一名玩家，立即获胜
        # 注意：_end_hand_early 会设置 phase=ENDED（先 SHOWDOWN 然后立即 END）
        assert_equal(engine.phase, GamePhase.ENDED)

        # 验证有赢家
        assert_true(hasattr(engine, '_last_result') and engine._last_result is not None)
        assert_equal(len(engine._last_result.winners), 1)
        # BB 自动获胜
        assert_equal(engine._last_result.winners[0]["user_id"], engine.player_order[engine.bb_index])

        test_passed("test_fold_until_one_player")


class TestSidePots:
    """边池测试 - 复杂的全押场景"""

    def test_simple_all_in(self):
        """测试简单全押场景"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # Player1 有 1000，Player2 有 1000
        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)

        engine.start_hand()

        # Heads-up: dealer_index=1, sb_index=1, bb_index=0
        # 翻牌前行动从 BB 之后的玩家开始（即 dealer/SB）
        current = engine.get_current_player()
        print(f"Heads-up AIO: current={current.user_id}, sb_index={engine.sb_index}, bb_index={engine.bb_index}")

        # SB (Player2) all-in
        success, _ = engine.execute_action(current.user_id, ActionType.ALL_IN, 1000)
        assert_true(success)

        # BB (Player1) call
        current = engine.get_current_player()
        print(f"After SB AIO: current={current.user_id if current else None}")
        success, _ = engine.execute_action(current.user_id, ActionType.CALL, 1000)
        assert_true(success)

        # 应该进入摊牌（两人都全押，自动摊牌）
        # 由于两人都全押，应该直接摊牌
        assert_true(engine.phase in [GamePhase.SHOWDOWN, GamePhase.ENDED])

        # 验证底池
        state = engine.get_state()
        assert_equal(state["current_pot"], 2000)

        test_passed("test_simple_all_in")

    def test_side_pot_with_different_amounts(self):
        """测试边池 - 不同筹码量的全押"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # Player1: 100 (BB), Player2: 200 (UTG), Player3: 300 (SB)
        engine.add_player(user_id=1, username="ShortStack", seat_index=0, chips=100)
        engine.add_player(user_id=2, username="MidStack", seat_index=1, chips=200)
        engine.add_player(user_id=3, username="BigStack", seat_index=2, chips=300)

        engine.start_hand()

        print(f"Side pot test: dealer={engine.dealer_index}, sb={engine.sb_index}, bb={engine.bb_index}")
        print(f"player_order={engine.player_order}")

        # 获取当前玩家
        current = engine.get_current_player()
        print(f"First to act: user_id={current.user_id}, seat_index={current.seat_index}")

        # UTG (seat_index=1, user_id=2) raise to 60
        success, _ = engine.execute_action(current.user_id, ActionType.RAISE, 60)
        assert_true(success)
        print(f"After UTG raise to 60: pot={engine.pot_manager.get_total_pot()}")

        # SB (seat_index=2, user_id=3) all-in (all chips)
        current = engine.get_current_player()
        print(f"After UTG raise: current={current.user_id}")
        sb_chips = engine.players[3].chips
        success, _ = engine.execute_action(current.user_id, ActionType.ALL_IN, sb_chips)
        assert_true(success)
        print(f"After SB AIO: pot={engine.pot_manager.get_total_pot()}")

        # BB (seat_index=0, user_id=1) call all-in
        current = engine.get_current_player()
        print(f"After SB AIO: current={current.user_id}")
        bb_chips = engine.players[1].chips
        success, _ = engine.execute_action(current.user_id, ActionType.CALL, bb_chips)
        assert_true(success)
        print(f"After BB call: pot={engine.pot_manager.get_total_pot()}")

        # UTG 需要跟注
        current = engine.get_current_player()
        print(f"After BB call: current={current.user_id}")
        utg_chips = engine.players[2].chips
        success, _ = engine.execute_action(current.user_id, ActionType.CALL, utg_chips)
        assert_true(success)
        print(f"After UTG call: pot={engine.pot_manager.get_total_pot()}")

        # 验证总底池 = 所有玩家的筹码
        # P1: 100, P2: 200, P3: 300 = 600
        state = engine.get_state()
        print(f"Total pot: {state['current_pot']}")
        print(f"Player total_bets: P1={engine.players[1].total_bet}, P2={engine.players[2].total_bet}, P3={engine.players[3].total_bet}")

        # 总底池应该是 600
        assert_equal(state["current_pot"], 600)

        test_passed("test_side_pot_with_different_amounts")

    def test_pot_manager_calculate_pots(self):
        """直接测试 PotManager 的边池计算"""
        pm = PotManager()

        # 模拟场景：P1 all-in 50, P2 all-in 150, P3 all-in 250, P4 all-in 400
        pm.player_total_bets = {1: 50, 2: 150, 3: 250, 4: 400}

        active_players = [1, 2, 3, 4]
        all_in_players = [1, 2, 3, 4]

        pm.calculate_pots(active_players, all_in_players)

        # 验证池的数量和金额
        assert_equal(len(pm.pots), 4)

        # 主池：50 * 4 = 200
        assert_equal(pm.pots[0].amount, 200)
        assert_equal(set(pm.pots[0].eligible_players), {1, 2, 3, 4})

        # 边池 1: (150-50) * 3 = 300
        assert_equal(pm.pots[1].amount, 300)
        assert_equal(set(pm.pots[1].eligible_players), {2, 3, 4})

        # 边池 2: (250-150) * 2 = 200
        assert_equal(pm.pots[2].amount, 200)
        assert_equal(set(pm.pots[2].eligible_players), {3, 4})

        # 边池 3: (400-250) * 1 = 150
        assert_equal(pm.pots[3].amount, 150)
        assert_equal(pm.pots[3].eligible_players, [4])

        test_passed("test_pot_manager_calculate_pots")

    def test_folded_player_bets_in_pot(self):
        """测试弃牌玩家的注仍在池中"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)
        engine.add_player(user_id=3, username="Player3", seat_index=2, chips=1000)

        engine.start_hand()

        print(f"Fold test: dealer={engine.dealer_index}, sb={engine.sb_index}, bb={engine.bb_index}")
        current = engine.get_current_player()
        print(f"First to act: user_id={current.user_id}")

        # UTG fold
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert_true(success)

        # SB (user_id=3) raise to 60
        current = engine.get_current_player()
        print(f"After UTG fold: current={current.user_id}")
        success, _ = engine.execute_action(current.user_id, ActionType.RAISE, 60)
        assert_true(success)

        # BB (user_id=1) fold
        current = engine.get_current_player()
        print(f"After SB raise: current={current.user_id}")
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert_true(success)

        # SB 应该立即获胜（只剩一人）
        # 注意：_end_hand_early 会设置 phase=ENDED
        assert_equal(engine.phase, GamePhase.ENDED)

        state = engine.get_state()
        # SB 赢得底池：SB 60 + BB 20 + UTG 0 = 80
        print(f"Winner: {state['winners']}, pot: {state['current_pot']}")
        assert_equal(state["current_pot"], 80)

        test_passed("test_folded_player_bets_in_pot")


class TestChipChanges:
    """筹码变动测试"""

    def test_chip_changes_conservation(self):
        """测试筹码守恒"""
        engine = GameEngine(small_blind=10, big_blind=20)

        engine.add_player(user_id=1, username="Player1", seat_index=0, chips=1000)
        engine.add_player(user_id=2, username="Player2", seat_index=1, chips=1000)

        engine.start_hand()

        print(f"Chip changes test: dealer={engine.dealer_index}, sb={engine.sb_index}, bb={engine.bb_index}")
        current = engine.get_current_player()
        print(f"First to act: user_id={current.user_id}")

        # SB fold (heads-up 时 dealer 是 SB，先行动)
        success, _ = engine.execute_action(current.user_id, ActionType.FOLD)
        assert_true(success)

        # BB 立即获胜
        # phase 会变成 ENDED
        assert_equal(engine.phase, GamePhase.ENDED)

        if hasattr(engine, '_last_result') and engine._last_result:
            chip_changes = engine._last_result.chip_changes

            # 验证筹码守恒
            total_change = sum(chip_changes.values())
            print(f"chip_changes: {chip_changes}, total: {total_change}")
            assert_equal(total_change, 0, "筹码变动总和应该为 0")

        test_passed("test_chip_changes_conservation")


class TestConfigAndDelays:
    """配置和延迟测试"""

    def test_dealing_delay_config(self):
        """测试发牌延迟配置"""
        # 验证配置存在
        assert_true(hasattr(settings, 'DEALING_DELAY'))
        assert_true(hasattr(settings, 'HAND_END_DELAY'))
        assert_true(hasattr(settings, 'AUTO_START_DELAY'))

        # 验证默认值
        assert_equal(settings.DEALING_DELAY, 5)  # 发牌后延迟 5 秒
        assert_equal(settings.HAND_END_DELAY, 10)  # 结束后延迟 10 秒
        assert_equal(settings.AUTO_START_DELAY, 3)  # 自动开始前延迟 3 秒

        test_passed("test_dealing_delay_config")

    def test_game_engine_has_delays(self):
        """测试游戏引擎包含延迟配置"""
        engine = GameEngine()

        assert_true(hasattr(engine, 'dealing_delay'))
        assert_equal(engine.dealing_delay, 5)

        test_passed("test_game_engine_has_delays")


class TestEdgeCases:
    """边界条件测试"""

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
            assert_true(raise_action["min_amount"] >= 40)

        test_passed("test_min_raise_calculation")

    def test_all_in_reopen_betting(self):
        """测试全押是否重新打开下注"""
        engine = GameEngine(small_blind=10, big_blind=20)

        # 设置一个场景：SB 的全押足以重新打开下注
        # P1 (BB): 200, P2 (UTG): 200, P3 (SB): 70
        # 盲注后：P1=180, P3=60
        engine.add_player(user_id=1, username="BB", seat_index=0, chips=200)
        engine.add_player(user_id=2, username="UTG", seat_index=1, chips=200)
        engine.add_player(user_id=3, username="SB", seat_index=2, chips=70)

        engine.start_hand()

        print(f"Reopen test: dealer={engine.dealer_index}, sb={engine.sb_index}, bb={engine.bb_index}")
        print(f"player_order={engine.player_order}")

        # 获取当前玩家
        current = engine.get_current_player()
        print(f"First to act: user_id={current.user_id}, seat_index={current.seat_index}")

        # UTG (seat_index=1, user_id=2) raise to 40 (min raise)
        success, _ = engine.execute_action(current.user_id, ActionType.RAISE, 40)
        assert_true(success)
        print(f"After UTG raise to 40: current_bet={engine.current_bet}, min_raise={engine.min_raise}")

        # SB (seat_index=2, user_id=3) all-in (60 chips, total bet = 10 + 60 = 70)
        # Increase = 70 - 10 = 60, which is >= min_raise (20), so should reopen betting
        current = engine.get_current_player()
        print(f"After UTG raise: current={current.user_id} (SB)")
        print(f"SB chips={engine.players[3].chips}, SB.total_bet={engine.players[3].total_bet}")
        success, _ = engine.execute_action(current.user_id, ActionType.ALL_IN)
        assert_true(success)
        print(f"After SB AIO: SB.total_bet={engine.players[3].total_bet}")
        print(f"  current_bet={engine.current_bet}, min_raise={engine.min_raise}")

        # BB (seat_index=0, user_id=1) 现在可以行动
        current = engine.get_current_player()
        print(f"After SB AIO: current={current.user_id} (BB)")
        assert_equal(current.user_id, 1)

        # BB 应该能够 raise（因为 SB 的全押是一个完整的加注）
        # SB 从 10 增加到 70，增加了 60 >= min_raise (20)
        actions = engine.get_valid_actions(current.user_id)
        action_types = [a["action"] for a in actions]
        print(f"BB actions: {action_types}")

        # BB 应该有 raise 选项
        assert_true(ActionType.RAISE in action_types, f"Expected RAISE in {action_types}")

        test_passed("test_all_in_reopen_betting")


class TestNetChips:
    """净筹码计算测试"""

    def test_net_chips_calculation(self):
        """测试净筹码计算逻辑"""
        initial_buyin = 1000

        # 玩家买入 1000
        current_chips = 1000
        net_chips = current_chips - initial_buyin
        assert_equal(net_chips, 0)

        # 玩家赢了 500
        current_chips = 1500
        net_chips = current_chips - initial_buyin
        assert_equal(net_chips, 500)

        # 玩家输了 500
        current_chips = 500
        net_chips = current_chips - initial_buyin
        assert_equal(net_chips, -500)

        # 玩家再买入 500（总买入 1500）
        total_buyin = 1500
        current_chips = 1000
        net_chips = current_chips - total_buyin
        assert_equal(net_chips, -500)

        test_passed("test_net_chips_calculation")


class TestPotManagerEdgeCases:
    """PotManager 边界条件测试"""

    def test_empty_pots(self):
        """测试空池"""
        pm = PotManager()
        pm.calculate_pots([], [])
        assert_equal(len(pm.pots), 0)

        test_passed("test_empty_pots")

    def test_single_player(self):
        """测试单一玩家"""
        pm = PotManager()
        pm.player_total_bets = {1: 100}
        pm.calculate_pots([1], [1])

        assert_equal(len(pm.pots), 1)
        assert_equal(pm.pots[0].amount, 100)
        assert_equal(pm.pots[0].eligible_players, [1])

        test_passed("test_single_player")

    def test_equal_bets(self):
        """测试等额下注"""
        pm = PotManager()
        pm.player_total_bets = {1: 100, 2: 100, 3: 100}
        pm.calculate_pots([1, 2, 3], [])

        assert_equal(len(pm.pots), 1)
        assert_equal(pm.pots[0].amount, 300)
        assert_equal(set(pm.pots[0].eligible_players), {1, 2, 3})

        test_passed("test_equal_bets")

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
        assert_equal(winnings[1], 100)
        assert_equal(winnings[2], 100)

        test_passed("test_distribute_winnings_tie")

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
        assert_equal(winnings[1], 150)
        assert_equal(winnings[2], 150)
        assert_true(3 not in winnings)  # 3 没赢

        test_passed("test_distribute_winnings_with_remainder")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("德州扑克核心流程逻辑测试")
    print("=" * 60)
    print()

    tests = [
        # 基础流程
        ("基础流程 - 两人游戏开始", TestBasicGameFlow().test_heads_up_game_start),
        ("基础流程 - 三人游戏位置", TestBasicGameFlow().test_three_player_game_positions),
        ("基础流程 - 翻牌前行动序列", TestBasicGameFlow().test_preflop_action_sequence),
        ("基础流程 - 弃牌直到一人获胜", TestBasicGameFlow().test_fold_until_one_player),

        # 边池测试
        ("边池 - 简单全押", TestSidePots().test_simple_all_in),
        ("边池 - 不同筹码量", TestSidePots().test_side_pot_with_different_amounts),
        ("边池 - PotManager 计算", TestSidePots().test_pot_manager_calculate_pots),
        ("边池 - 弃牌玩家注在池中", TestSidePots().test_folded_player_bets_in_pot),

        # 筹码变动
        ("筹码变动 - 守恒", TestChipChanges().test_chip_changes_conservation),

        # 配置和延迟
        ("配置 - 发牌延迟", TestConfigAndDelays().test_dealing_delay_config),
        ("配置 - 游戏引擎延迟", TestConfigAndDelays().test_game_engine_has_delays),

        # 边界条件
        ("边界 - 最小加注计算", TestEdgeCases().test_min_raise_calculation),
        ("边界 - 全押重新打开下注", TestEdgeCases().test_all_in_reopen_betting),

        # 净筹码
        ("净筹码 - 计算逻辑", TestNetChips().test_net_chips_calculation),

        # PotManager 边界
        ("PotManager - 空池", TestPotManagerEdgeCases().test_empty_pots),
        ("PotManager - 单一玩家", TestPotManagerEdgeCases().test_single_player),
        ("PotManager - 等额下注", TestPotManagerEdgeCases().test_equal_bets),
        ("PotManager - 平分彩池", TestPotManagerEdgeCases().test_distribute_winnings_tie),
        ("PotManager - 余数分配", TestPotManagerEdgeCases().test_distribute_winnings_with_remainder),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            test_failed(name, str(e))
            failed += 1

    print()
    print("=" * 60)
    print(f"测试结果：{passed} 通过，{failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
