"""
德州扑克终端游戏客户端

支持本地多人游戏（热座模式）或带简单机器人的单人游戏。
使用 Rich 库实现彩色输出和实时刷新。

运行方式:
    python poker_terminal.py
"""

import random
import time
from typing import Dict, List, Optional, Any
import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.game.engine import GameEngine, GamePhase, ActionType
from app.game.player import Player, PlayerStatus
from app.game.deck import Card

from ui.display import TerminalDisplay, CardDisplay
from ui.input import (
    get_player_action,
    prompt_num_players,
    prompt_starting_chips,
    confirm_start_game,
    prompt_continue_game,
    prompt_rebuy,
    prompt_exit,
)


class SimpleBot:
    """
    简单机器人 - 使用随机策略。

    决策逻辑：
    - 有对子或更好：倾向于加注/跟注
    - 有高牌（A/K/Q）：倾向于跟注
    - 其他：大部分时候弃牌
    """

    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username

    def decide_action(self, game: GameEngine, valid_actions: List[Dict]) -> Dict[str, Any]:
        """简单的决策逻辑。"""
        if not valid_actions:
            return {"action": ActionType.CHECK, "amount": 0}

        player = game.players.get(self.user_id)
        if not player or len(player.hole_cards) < 2:
            # 无手牌，随机弃牌或过牌
            return self._random_choice(valid_actions)

        # 评估手牌
        c1, c2 = player.hole_cards[0], player.hole_cards[1]
        hand_strength = self._evaluate_hand(player.hole_cards, game.community_cards)

        # 获取操作类型
        action_types = [a['action'] for a in valid_actions]

        # 强牌（一对或以上）
        if hand_strength >= 0.5:
            if ActionType.RAISE in action_types and random.random() < 0.6:
                raise_action = action_types[ActionType.RAISE]
                return {"action": ActionType.RAISE, "amount": raise_action['min_amount']}
            if ActionType.CALL in action_types:
                return {"action": ActionType.CALL, "amount": action_types[ActionType.CALL]['amount']}
            if ActionType.ALL_IN in action_types and random.random() < 0.5:
                return {"action": ActionType.ALL_IN, "amount": action_types[ActionType.ALL_IN]['amount']}
            return self._random_choice(valid_actions)

        # 中等牌（高牌）
        elif hand_strength >= 0.2:
            if ActionType.CALL in action_types and random.random() < 0.7:
                return {"action": ActionType.CALL, "amount": action_types[ActionType.CALL]['amount']}
            if ActionType.CHECK in action_types:
                return {"action": ActionType.CHECK, "amount": 0}
            return self._random_choice(valid_actions)

        # 弱牌
        else:
            if ActionType.CHECK in action_types:
                return {"action": ActionType.CHECK, "amount": 0}
            # 偶尔诈唬
            if ActionType.RAISE in action_types and random.random() < 0.1:
                return {"action": ActionType.RAISE, "amount": action_types[ActionType.RAISE]['min_amount']}
            if ActionType.CALL in action_types and random.random() < 0.2:
                return {"action": ActionType.CALL, "amount": action_types[ActionType.CALL]['amount']}
            return {"action": ActionType.FOLD, "amount": 0}

    def _evaluate_hand(self, hole_cards: List[Card], community_cards: List[Card]) -> float:
        """简单评估手牌强度。"""
        if len(hole_cards) < 2:
            return 0.0

        c1, c2 = hole_cards[0], hole_cards[1]
        strength = 0.0

        # 对子
        if c1.rank == c2.rank:
            strength += 0.5
            if c1.value >= 9:
                strength += 0.2

        # 高牌
        high_ranks = ['A', 'K', 'Q', 'J']
        if c1.rank in high_ranks and c2.rank in high_ranks:
            strength += 0.4
        elif c1.rank in high_ranks or c2.rank in high_ranks:
            strength += 0.2

        # 同花潜力
        if c1.suit == c2.suit:
            strength += 0.1

        # 顺子潜力
        if abs(c1.value - c2.value) <= 2:
            strength += 0.1

        return min(strength, 0.9)

    def _random_choice(self, valid_actions: List[Dict]) -> Dict[str, Any]:
        """随机选择一个操作。"""
        action = random.choice(valid_actions)
        return {
            "action": action['action'],
            "amount": action.get('amount', action.get('min_amount', 0))
        }


class TerminalPokerClient:
    """
    终端扑克游戏客户端。

    游戏流程：
    1. 设置游戏（玩家数、筹码）
    2. 开始游戏循环
    3. 每局：发牌 → 四轮下注 → 摊牌 → 结算
    4. 询问是否继续
    """

    def __init__(self):
        self.display = TerminalDisplay()
        self.game: Optional[GameEngine] = None
        self.bots: Dict[int, SimpleBot] = {}
        self.human_player_id = 0
        self.hand_count = 0
        self._running = False

    def run(self):
        """运行游戏主循环。"""
        self._running = True

        # 显示欢迎界面
        self.display.display_welcome()
        time.sleep(1)

        # 游戏设置
        num_players = prompt_num_players()
        starting_chips = prompt_starting_chips()

        # 初始化游戏
        self._setup_game(num_players, starting_chips)

        # 确认开始
        if not confirm_start_game():
            return

        # 游戏主循环
        try:
            while self._running:
                self.hand_count += 1
                self.display.set_hand_count(self.hand_count)

                self._play_hand()

                # 检查玩家筹码
                self._check_rebuy()

                # 询问是否继续
                if not prompt_continue_game():
                    break

            # 游戏结束
            self._show_final_results()

        except KeyboardInterrupt:
            self._running = False
            self.display.display_message(
                "游戏已中断",
                title="中断",
                style="yellow"
            )

    def _setup_game(self, num_players: int, starting_chips: int):
        """设置游戏。"""
        self.game = GameEngine(small_blind=10, big_blind=20)

        # 添加人类玩家
        self.game.add_player(
            user_id=self.human_player_id,
            username="你",
            seat_index=0,
            chips=starting_chips
        )
        self.display.record_starting_chips(self.human_player_id, starting_chips)

        # 添加机器人玩家
        bot_names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry", "Ivy"]
        random.shuffle(bot_names)

        for i in range(num_players - 1):
            bot_id = i + 1
            bot_name = bot_names[i] if i < len(bot_names) else f"Bot{i}"
            bot = SimpleBot(bot_id, bot_name)
            self.bots[bot_id] = bot

            self.game.add_player(
                user_id=bot_id,
                username=bot_name,
                seat_index=i + 1,
                chips=starting_chips
            )
            self.display.record_starting_chips(bot_id, starting_chips)

    def _play_hand(self):
        """进行一局游戏。"""
        # 开始一手牌
        if not self.game.start_hand():
            self.display.display_message(
                "无法开始游戏，玩家数量不足",
                title="错误",
                style="red"
            )
            return

        # 显示初始状态
        self._render_game_state()
        time.sleep(0.5)

        # 游戏循环
        max_rounds = 50
        rounds = 0

        while self.game.phase not in [GamePhase.SHOWDOWN, GamePhase.ENDED] and rounds < max_rounds:
            rounds += 1

            current_player = self.game.get_current_player()
            if not current_player:
                break

            # 处理玩家行动
            self._process_player_turn(current_player)

            # 渲染状态
            self._render_game_state()

            # 短暂延迟
            time.sleep(0.3)

        # 显示结果
        self._show_hand_result()

    def _process_player_turn(self, player: Player):
        """处理玩家回合。"""
        valid_actions = self.game.get_valid_actions(player.user_id)

        if not valid_actions:
            return

        if player.user_id == self.human_player_id:
            # 人类玩家输入
            self._human_player_action(player, valid_actions)
        else:
            # 机器人决策
            self._bot_player_action(player, valid_actions)

    def _human_player_action(self, player: Player, valid_actions: List[Dict]):
        """人类玩家操作。"""
        # 清屏并显示当前状态
        self.display.clear()
        self._render_game_state()

        # 显示操作菜单
        action_data = get_player_action(valid_actions, player.username)

        # 执行操作
        success, msg = self.game.execute_action(
            player.user_id,
            action_data['action'],
            action_data.get('amount', 0)
        )

        if not success:
            self.display.display_message(
                f"无效操作：{msg}",
                title="错误",
                style="red",
                clear_first=False
            )
            time.sleep(1)

    def _bot_player_action(self, player: Player, valid_actions: List[Dict]):
        """机器人操作。"""
        bot = self.bots.get(player.user_id)
        if bot:
            # 模拟思考延迟
            time.sleep(0.3 + random.random() * 0.5)
            action_data = bot.decide_action(self.game, valid_actions)
            self.game.execute_action(
                player.user_id,
                action_data['action'],
                action_data.get('amount', 0)
            )

    def _render_game_state(self, temporary_message: Optional[str] = None):
        """渲染游戏状态。"""
        if not self.game:
            return

        current_player_id = None
        current_player = self.game.get_current_player()
        if current_player:
            current_player_id = current_player.user_id

        # 使用 Live 模式渲染
        self.display.update_live(self.game, current_player_id, temporary_message)

    def _show_hand_result(self):
        """显示一手牌的结果。"""
        state = self.game.get_state()

        # 准备结果数据
        results = {
            'winners': state.get('winners', []),
            'pot_amount': state.get('current_pot', 0),
        }

        # 显示结果
        self.display.display_hand_result(self.game, results)

    def _check_rebuy(self):
        """检查玩家是否需要补充筹码。"""
        human_player = self.game.players.get(self.human_player_id)
        if human_player and human_player.chips < 50:
            if prompt_rebuy(human_player.chips, 1000):
                human_player.chips = 1000
                self.display.record_starting_chips(self.human_player_id, 1000)
                self.display.display_message(
                    f"已补充筹码到 $1000",
                    title="补充筹码",
                    style="green"
                )

    def _show_final_results(self):
        """显示最终游戏结果。"""
        self.display.clear()

        lines = []
        lines.append("[bold magenta]╔═══════════════════════════════════════════════════════════╗[/bold magenta]")
        lines.append("[bold magenta]║[/bold magenta]                  [bold]游戏结束[/bold]                              [bold magenta]║[/bold magenta]")
        lines.append("[bold magenta]╚═══════════════════════════════════════════════════════════╝[/bold magenta]")
        lines.append("")

        # 人类玩家结果
        human_player = self.game.players.get(self.human_player_id)
        if human_player:
            starting_chips = self.display._player_starting_chips.get(self.human_player_id, 1000)
            current = human_player.chips
            net = current - starting_chips

            net_style = "green" if net >= 0 else "red"
            net_sign = "+" if net >= 0 else ""

            lines.append(f"[bold]最终筹码：[/bold] [yellow]${current}[/yellow]")
            lines.append(f"[bold]净输赢：[/bold] [{net_style}]{net_sign}${net}[/{net_style}]")
            lines.append("")

            if net > 0:
                lines.append("[bold green]🎉 恭喜你！你赢了！[/bold green]")
            elif net < 0:
                lines.append("[bold yellow]😅 再接再厉！[/bold yellow]")
            else:
                lines.append("[bold cyan]收支平衡，不错！[/bold cyan]")

        lines.append("")
        lines.append(f"[dim]共进行了 {self.hand_count} 局游戏[/dim]")

        for line in lines:
            self.display.console.print(line)


def main():
    """主入口函数。"""
    try:
        client = TerminalPokerClient()
        client.run()
    except KeyboardInterrupt:
        print("\n\n[yellow]游戏已中断[/yellow]")
    except Exception as e:
        print(f"\n[red]错误：{e}[/red]")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
