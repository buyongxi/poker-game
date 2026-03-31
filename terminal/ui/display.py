"""Terminal display module for poker game - with live refresh support."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.box import ROUNDED
from typing import List, Dict, Optional, Any, Tuple
from contextlib import contextmanager
import sys
import os

# 添加后端路径以便导入游戏引擎
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.game.deck import Card
from app.game.player import Player, PlayerStatus
from app.game.engine import GameEngine, GamePhase, ActionType


class CardDisplay:
    """扑克牌显示工具。"""

    # 花色符号和颜色
    SUIT_SYMBOLS = {
        'h': '♥',  # Hearts - 红桃
        'd': '♦',  # Diamonds - 方块
        'c': '♣',  # Clubs - 梅花
        's': '♠',  # Spades - 黑桃
    }

    SUIT_COLORS = {
        'h': 'red',
        'd': 'red',
        'c': 'white',
        's': 'white',
    }

    @classmethod
    def card_to_text(cls, card: Card) -> Text:
        """将卡牌转换为带颜色的文本。"""
        suit_symbol = cls.SUIT_SYMBOLS.get(card.suit, card.suit)
        color = cls.SUIT_COLORS.get(card.suit, 'white')

        text = Text()
        text.append(f"{card.rank}", style=f"bold {color}")
        text.append(suit_symbol, style=color)
        return text

    @classmethod
    def render_card(cls, card: Card) -> str:
        """渲染单张卡牌为带样式的字符串。"""
        suit_symbol = cls.SUIT_SYMBOLS.get(card.suit, card.suit)
        color = cls.SUIT_COLORS.get(card.suit, 'white')
        return f"[{color} bold]{card.rank}{suit_symbol}[/{color}]"

    @classmethod
    def render_hand(cls, cards: List[Card], hide: bool = False) -> str:
        """渲染一手牌。"""
        if not cards:
            return "[dim]无牌[/dim]"
        if hide:
            return "[dim][🂠][🂠][/dim]"  # 牌背符号
        return "  ".join([cls.render_card(c) for c in cards])

    @classmethod
    def render_empty_slots(cls, count: int) -> str:
        """渲染空牌位（用于公共牌未发满时）。"""
        return "  ".join(["[dim][?][/dim]" for _ in range(count)])


class TerminalDisplay:
    """
    终端显示管理器 - 支持实时刷新和状态管理。

    状态分类：
    - 持久状态：公共牌、底池、玩家筹码等关键信息
    - 临时状态：等待提示、倒计时等，会在下次刷新时清除
    """

    # 游戏阶段名称映射
    PHASE_NAMES = {
        GamePhase.PREFLOP: "翻牌前",
        GamePhase.FLOP: "翻牌圈",
        GamePhase.TURN: "转牌圈",
        GamePhase.RIVER: "河牌圈",
        GamePhase.SHOWDOWN: "摊牌",
        GamePhase.ENDED: "结束",
    }

    # 玩家状态显示映射
    STATUS_DISPLAY = {
        'playing': ('[green]游戏中[/green]', '●'),
        'folded': ('[dim]已弃牌[/dim]', '×'),
        'all_in': ('[bold red]ALL-IN[/bold red]', '★'),
        'ready': ('[cyan]已准备[/cyan]', '○'),
        'waiting': ('[dim]等待中[/dim]', '○'),
        'disconnected': ('[red]已断线[/red]', '○'),
        'empty': ('[dim]空位[/dim]', '·'),
    }

    def __init__(self):
        self.console = Console()
        self._live: Optional[Live] = None
        self._last_render = ""

        # 状态追踪
        self._hand_count = 0
        self._player_starting_chips: Dict[int, int] = {}  # 用于计算净筹码

        # 聊天消息
        self._chat_messages: List[str] = []
        self._max_chat_messages = 10

        # 剩余时间
        self._remaining_time: Optional[int] = None

    def clear(self):
        """清屏。"""
        self.console.clear()

    @contextmanager
    def live_display(self, refresh_per_second: int = 4):
        """
        上下文管理器，用于实时刷新显示。

        使用方式:
            with display.live_display():
                while game_active:
                    display.update_live(game, current_player_id)
        """
        with Live("", console=self.console, refresh_per_second=refresh_per_second, transient=False) as live:
            self._live = live
            try:
                yield
            finally:
                self._live = None

    def update_live(self, game: GameEngine, current_player_id: Optional[int] = None,
                    temporary_message: Optional[str] = None):
        """
        更新实时显示。

        Args:
            game: 游戏引擎实例
            current_player_id: 当前行动玩家 ID
            temporary_message: 临时消息（如"等待其他玩家..."）
        """
        if not self._live:
            # 如果没有激活 Live 上下文，直接打印
            self.render_and_print(game, current_player_id, temporary_message)
            return

        renderable = self.render_layout(game, current_player_id, temporary_message)
        self._live.update(renderable)

    def render_and_print(self, game: GameEngine, current_player_id: Optional[int] = None,
                         temporary_message: Optional[str] = None):
        """渲染并打印游戏状态（非 Live 模式）。"""
        layout = self.render_layout(game, current_player_id, temporary_message)
        self.console.print(layout)

    def render_layout(self, game: GameEngine, current_player_id: Optional[int] = None,
                      temporary_message: Optional[str] = None) -> Layout:
        """
        渲染完整的游戏布局。

        布局结构：
        ┌─────────────────────────────────────────────────────┐
        │           Header (游戏信息)                          │
        ├─────────────────────────────────────────────────────┤
        │                                     │               │
        │         Table (玩家牌桌)             │   Chat        │
        │                                     │   (聊天)      │
        ├─────────────────────────────────────┤               │
        │   Footer (操作面板/临时消息)         │               │
        └─────────────────────────────────────┴───────────────┘
        """
        layout = Layout()

        # 顶部：游戏信息
        header = self._render_header(game)

        # 中间：玩家牌桌和聊天区域
        main_area = Layout(name="main")
        table_panel = self._render_player_table(game, current_player_id)
        chat_panel = self._render_chat_panel()

        main_area.split_row(
            Layout(table_panel, name="table", ratio=3),
            Layout(chat_panel, name="chat", ratio=1)
        )

        # 底部：操作面板或临时消息
        if temporary_message:
            # 临时消息优先显示（会在下次刷新时清除）
            footer = self._render_temporary_message(temporary_message)
        elif current_player_id:
            # 当前玩家的行动提示
            footer = self._render_action_footer(game, current_player_id)
        else:
            # 默认等待消息
            footer = self._render_default_footer(game)

        # 分割布局
        layout.split_column(
            Layout(header, size=8, name="header"),
            main_area,
            Layout(footer, size=6, name="footer")
        )

        return layout

    def _render_header(self, game: GameEngine) -> Panel:
        """渲染顶部游戏信息面板。"""
        phase_name = self.PHASE_NAMES.get(game.phase, "未知")
        community_cards = self._render_community_cards(game.community_cards)
        total_pot = game.pot_manager.get_total_pot()

        # 构建信息文本
        info = Text()
        info.append("阶段：", style="bold")
        info.append(f"{phase_name}", style="magenta")
        info.append("  │  ")
        info.append("公共牌：", style="bold")
        info.append(f"{community_cards}", style="cyan")
        info.append("  │  ")
        info.append("底池：", style="bold")
        info.append(f"${total_pot}", style="green bold")

        # 当前下注信息
        if game.current_bet > 0:
            info.append(f"  │  当前注：${game.current_bet}", style="yellow")

        return Panel(info, title="[bold magenta]🃏 德州扑克[/bold magenta]",
                     border_style="magenta", subtitle=f"第 {self._hand_count} 局")

    def _render_community_cards(self, cards: List[Card]) -> str:
        """渲染公共牌，未发满时显示空位。"""
        if not cards:
            return "[dim][?] [?] [?] [?] [?][/dim]"

        rendered = "  ".join([CardDisplay.render_card(c) for c in cards])

        # 补充空位
        empty_slots = 5 - len(cards)
        if empty_slots > 0:
            rendered += "  " + "  ".join(["[dim][?][/dim]" for _ in range(empty_slots)])

        return rendered

    def _render_player_table(self, game: GameEngine, current_player_id: Optional[int]) -> Panel:
        """渲染玩家牌桌表格。"""
        state = game.get_state()
        players = sorted(state['players'], key=lambda p: p['seat_index'])

        table = Table(box=ROUNDED, expand=True, title="📍 牌桌", border_style="blue")

        # 列定义
        table.add_column("座", style="dim", width=3, justify="center")
        table.add_column("玩家", style="bold", width=14)
        table.add_column("位", width=6, justify="center")
        table.add_column("筹码", style="green", width=8, justify="right")
        table.add_column("注", style="yellow", width=6, justify="right")
        table.add_column("净", width=7, justify="right")
        table.add_column("手牌", width=18, justify="center")
        table.add_column("状态", width=10, justify="center")

        for p in players:
            player_obj = game.players.get(p['user_id'])
            if not player_obj:
                continue

            # 座位号
            seat = str(p['seat_index'] + 1)

            # 玩家名（当前玩家高亮）
            name_style = "bold yellow" if p['user_id'] == current_player_id else "white"
            name = p['username']
            if p['user_id'] == current_player_id:
                name = f"→{name}"

            # 位置标记
            position = ""
            if p['is_dealer']:
                position += "[yellow]D[/yellow]"
            if p['is_sb']:
                position += "[cyan]S[/cyan]"
            if p['is_bb']:
                position += "[blue]B[/blue]"

            # 筹码
            chips = f"${p['chips']}"

            # 当前下注
            bet = f"${p['current_bet']}" if p['current_bet'] > 0 else "-"

            # 净筹码（计算输赢）
            net_chips = self._calculate_net_chips(p['user_id'], p['chips'])
            net_style = "green" if net_chips >= 0 else "red"
            net_sign = "+" if net_chips >= 0 else ""
            net = f"{net_sign}${net_chips}"

            # 手牌 - 仅显示当前玩家的手牌，其他玩家显示牌背
            if p['cards']:
                # 只有当前行动玩家或摊牌阶段才能看到所有玩家的手牌
                show_cards = (p['user_id'] == current_player_id or
                             game.phase == GamePhase.SHOWDOWN or
                             game.phase == GamePhase.ENDED)
                if show_cards:
                    cards_str = "  ".join([
                        f"[red]{c['rank']}{CardDisplay.SUIT_SYMBOLS.get(c['suit'], '')}[/red]"
                        if c['suit'] in ['h', 'd'] else
                        f"[white]{c['rank']}{CardDisplay.SUIT_SYMBOLS.get(c['suit'], '')}[/white]"
                        for c in p['cards']
                    ])
                else:
                    # 显示牌背
                    cards_str = "[dim][🂠][🂠][/dim]"
            else:
                cards_str = "[dim][🂠][🂠][/dim]"

            # 状态
            status_text, status_icon = self.STATUS_DISPLAY.get(p['status'], ('未知', '○'))

            table.add_row(seat, f"[{name_style}]{name}[/{name_style}]", position,
                         chips, bet, f"[{net_style}]{net}[/{net_style}]",
                         cards_str, f"{status_icon} {status_text}")

        return Panel(table, border_style="blue")

    def _calculate_net_chips(self, user_id: int, current_chips: int) -> int:
        """计算玩家净输赢。"""
        starting = self._player_starting_chips.get(user_id, 1000)
        return current_chips - starting

    def _render_action_footer(self, game: GameEngine, current_player_id: int) -> Panel:
        """渲染当前玩家的行动面板。"""
        player = game.players.get(current_player_id)
        if not player:
            return self._render_default_footer(game)

        valid_actions = game.get_valid_actions(current_player_id)
        actions_text = self._format_actions(valid_actions)

        content = Text()
        content.append(f"轮到你行动：{player.username}\n\n", style="bold yellow")
        content.append(f"你的手牌：{CardDisplay.render_hand(player.hole_cards)}\n", style="cyan")

        # 添加剩余时间显示
        if self._remaining_time is not None:
            if self._remaining_time <= 5:
                time_style = "bold red blink"
            elif self._remaining_time <= 10:
                time_style = "yellow"
            else:
                time_style = "green"
            content.append(f"\n剩余时间：[{time_style}]{self._remaining_time} 秒[/{time_style}]\n", style="white")

        content.append(f"可用操作：{actions_text}", style="white")

        return Panel(content, title="[bold]🎯 行动[/bold]", border_style="yellow")

    def _render_temporary_message(self, message: str) -> Panel:
        """渲染临时消息（如等待提示）。"""
        return Panel(f"[dim]{message}[/dim]", title="[bold]ℹ 信息[/bold]",
                     border_style="dim")

    def _render_default_footer(self, game: GameEngine) -> Panel:
        """渲染默认底部面板。"""
        if game.phase == GamePhase.ENDED:
            return Panel("[green]本局结束，准备开始下一局...[/green]",
                        title="[bold]✓ 完成[/bold]", border_style="green")
        else:
            return Panel("[dim]等待游戏开始...[/dim]",
                        title="[bold]ℹ 信息[/bold]", border_style="dim")

    def _render_chat_panel(self) -> Panel:
        """渲染聊天面板。"""
        if not self._chat_messages:
            return Panel("[dim]暂无消息...[/dim]", title="[bold]💬 聊天[/bold]",
                        border_style="dim")

        chat_lines = []
        for msg in self._chat_messages[-self._max_chat_messages:]:
            chat_lines.append(msg)

        chat_text = Text("\n".join(chat_lines))
        return Panel(chat_text, title="[bold]💬 聊天[/bold]",
                    border_style="blue")

    def add_chat_message(self, message: str, is_system: bool = False):
        """
        添加聊天消息。

        Args:
            message: 消息内容
            is_system: 是否为系统消息
        """
        if is_system:
            formatted = f"[green][系统][/green] [dim]{message}[/dim]"
        else:
            formatted = message
        self._chat_messages.append(formatted)
        # 限制消息数量
        if len(self._chat_messages) > self._max_chat_messages:
            self._chat_messages = self._chat_messages[-self._max_chat_messages:]

    def clear_chat_messages(self):
        """清空聊天消息。"""
        self._chat_messages = []

    def set_remaining_time(self, seconds: Optional[int]):
        """
        设置剩余时间。

        Args:
            seconds: 剩余秒数
        """
        self._remaining_time = seconds

    def _format_actions(self, actions: List[Dict]) -> str:
        """格式化可用操作列表。"""
        if not actions:
            return "无可用操作"

        formatted = []
        for a in actions:
            action_type = a['action'].value
            if action_type == 'raise':
                formatted.append(f"[yellow]加注[/yellow] (${a['min_amount']}-${a['max_amount']})")
            elif action_type == 'all_in':
                formatted.append(f"[bold red]全押[/bold red] (${a['amount']})")
            elif action_type == 'call':
                formatted.append(f"[blue]跟注[/blue] (${a['amount']})")
            else:
                formatted.append(action_type.capitalize())

        return "  ".join(formatted)

    def display_hand_result(self, game: GameEngine, results: Dict):
        """显示一手牌的结果。"""
        self.clear()

        lines = []
        lines.append("[bold magenta]╔═══════════════════════════════════════════════════════════╗[/bold magenta]")
        lines.append("[bold magenta]║[/bold magenta]                  [bold]本局结果[/bold]                            [bold magenta]║[/bold magenta]")
        lines.append("[bold magenta]╚═══════════════════════════════════════════════════════════╝[/bold magenta]")
        lines.append("")

        # 公共牌
        lines.append(f"[bold cyan]公共牌:[/bold cyan] {self._render_community_cards(game.community_cards)}")
        lines.append(f"[bold yellow]总底池:[/bold yellow] [green]${game.pot_manager.get_total_pot()}[/green]")
        lines.append("")

        # 获胜者
        if results.get('winners'):
            lines.append("[bold green]─────────────────────────────────────────────────────[/bold green]")
            for winner in results['winners']:
                winner_name = winner.get('username', f"玩家{winner.get('user_id', 'Unknown')}")
                lines.append(f"[bold green]🏆 获胜者：[/bold green][yellow]{winner_name}[/yellow]")
                lines.append(f"[green]   赢得：${winner.get('amount', 0)}[/green]")
                if winner.get('hand'):
                    lines.append(f"[cyan]   牌型：{winner['hand']}[/cyan]")
                if winner.get('cards'):
                    cards_display = " ".join([
                        f"[red]{c['rank']}{CardDisplay.SUIT_SYMBOLS.get(c['suit'], '')}[/red]"
                        if c['suit'] in ['h', 'd'] else
                        f"[white]{c['rank']}{CardDisplay.SUIT_SYMBOLS.get(c['suit'], '')}[/white]"
                        for c in winner['cards']
                    ])
                    lines.append(f"[white]   手牌：{cards_display}[/white]")
            lines.append("")

        # 玩家详情
        lines.append("[bold]─────────────────────────────────────────────────────[/bold]")
        state = game.get_state()
        for p in state['players']:
            player_obj = game.players.get(p['user_id'])
            if player_obj:
                # 摊牌阶段显示所有玩家的手牌
                if game.phase == GamePhase.SHOWDOWN or game.phase == GamePhase.ENDED:
                    cards_display = CardDisplay.render_hand(p['cards'])
                else:
                    cards_display = "[dim][🂠][🂠][/dim]"
                net = self._calculate_net_chips(p['user_id'], p['chips'])
                net_style = "green" if net >= 0 else "red"
                lines.append(f"  {p['username']}: {cards_display} | 净：[{net_style}]{net:+d}[/{net_style}]")

        for line in lines:
            self.console.print(line)

    def display_message(self, message: str, title: str = "信息", style: str = "white",
                        clear_first: bool = True):
        """
        显示消息面板。

        Args:
            message: 消息内容
            title: 面板标题
            style: 样式颜色
            clear_first: 是否先清屏
        """
        if clear_first:
            self.clear()

        panel = Panel(
            f"[{style}]{message}[/{style}]",
            title=f"[bold]{title}[/bold]",
            border_style=style
        )
        self.console.print(panel)

    def display_welcome(self):
        """显示欢迎界面。"""
        self.clear()

        welcome = Text()
        welcome.append("\n\n", style="default")
        welcome.append("╔═══════════════════════════════════════════════════════════╗\n", style="bold magenta")
        welcome.append("║                                                           ║\n", style="magenta")
        welcome.append("║            🃏  欢迎进入德州扑克终端版  🃏                  ║\n", style="bold yellow")
        welcome.append("║                                                           ║\n", style="magenta")
        welcome.append("╚═══════════════════════════════════════════════════════════╝\n", style="bold magenta")
        welcome.append("\n", style="default")
        welcome.append("  经典德州扑克游戏\n", style="cyan")
        welcome.append("  支持 2-10 名玩家\n", style="cyan")
        welcome.append("  包含 AI 机器人对手\n", style="cyan")
        welcome.append("\n", style="default")
        welcome.append("  按提示进行操作，祝你好运！\n\n", style="green")

        self.console.print(welcome)

    def set_hand_count(self, count: int):
        """设置当前局数。"""
        self._hand_count = count

    def record_starting_chips(self, user_id: int, chips: int):
        """记录玩家起始筹码（用于计算净输赢）。"""
        self._player_starting_chips[user_id] = chips
