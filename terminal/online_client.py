"""
在线德州扑克游戏客户端

通过 WebSocket 连接后端服务器，支持多人在线游戏。
使用 Rich 库实现彩色输出和实时刷新。
"""

import time
import threading
from typing import Dict, List, Optional, Any
import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.game.engine import GameEngine, GamePhase, ActionType
from app.game.player import Player, PlayerStatus
from app.game.deck import Card

from ui.display import TerminalDisplay, CardDisplay
from ui.input import get_player_action
from websocket_client import WebSocketClient, ChatMessage
from api_client import SyncAPIClient, User

from rich.prompt import Prompt, Confirm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED

console = Console()


class OnlinePokerClient:
    """
    在线扑克游戏客户端。

    通过 WebSocket 与后端通信，支持：
    - 实时游戏状态更新
    - 聊天功能
    - 准备/取消准备
    - 游戏操作

    显示区域划分：
    - 顶部：房间信息（房间名、盲注、买入）
    - 中间：玩家座位列表 / 游戏牌桌
    - 底部：操作按钮 / 聊天消息
    """

    def __init__(self, api_client: SyncAPIClient, user: User, room: Dict):
        self.api_client = api_client
        self.user = user
        self.room = room
        self.room_id = room["id"]

        self.display = TerminalDisplay()
        self.ws_client: Optional[WebSocketClient] = None

        self.human_player_id = user.id
        self._running = False
        self._connected = False
        self._my_turn = False
        self._action_ready = threading.Event()
        self._pending_action: Optional[Dict] = None

        # 游戏状态
        self.game_state: Optional[Dict] = None
        self.room_state: Optional[Dict] = None

        # 准备状态
        self.is_ready = False
        self.is_owner = False
        self.my_seat_index: Optional[int] = None

        # 倒计时
        self._countdown_thread: Optional[threading.Thread] = None
        self._remaining_time: Optional[int] = None
        self._stop_countdown = threading.Event()

        # 清屏标记
        self._cleared_for_game = False

    def connect(self) -> bool:
        """连接到 WebSocket 服务。"""
        # 构建 WebSocket URL（从 HTTP URL 转换）
        ws_url = self.api_client.base_url.replace("http://", "ws://").replace("https://", "wss://")

        self.ws_client = WebSocketClient(base_url=ws_url, token=self.api_client.token, room_id=self.room_id)

        # 注册回调
        self.ws_client.on_connect(self._on_connect)
        self.ws_client.on_disconnect(self._on_disconnect)
        self.ws_client.on_game_state(self._on_game_state)
        self.ws_client.on_room_state(self._on_room_state)
        self.ws_client.on_chat(self._on_chat)
        self.ws_client.on_info(self._on_info)
        self.ws_client.on_error(self._on_error)

        # 连接
        if not self.ws_client.connect():
            self.display.display_message("无法连接到游戏服务器", title="连接失败", style="red")
            return False

        return True

    def disconnect(self):
        """断开连接。"""
        self._running = False
        self._stop_countdown.set()

        if self.ws_client:
            self.ws_client.disconnect()

    def run(self):
        """运行游戏主循环。"""
        self._running = True

        # 连接 WebSocket
        if not self.connect():
            return

        # 清屏并显示欢迎界面
        console.clear()
        self._show_welcome()

        # 主循环 - 等待房间状态
        try:
            while self._running and self._connected:
                # 等待房间状态
                if self.room_state:
                    self._update_room_info()
                    break
                time.sleep(0.1)

            # 进入房间主循环
            self._room_loop()

        except KeyboardInterrupt:
            self._running = False
            self.display.display_message("游戏已中断", title="中断", style="yellow")

        finally:
            self.disconnect()

    def _room_loop(self):
        """房间主循环 - 处理准备阶段和游戏阶段。"""
        while self._running and self._connected:
            # 检查游戏是否激活
            if self.game_state and self.game_state.get("is_active"):
                # 游戏阶段
                if not self._cleared_for_game:
                    console.clear()
                    self._cleared_for_game = True
                self._game_loop()
            else:
                # 准备阶段
                self._cleared_for_game = False
                self._pregame_loop()

            time.sleep(0.2)

    def _pregame_loop(self):
        """准备阶段循环 - 显示房间信息，等待玩家准备。"""
        # 首次显示准备界面
        self._render_pregame_state()
        last_ready_count = -1

        while self._running and self._connected:
            # 检查是否进入游戏阶段
            if self.game_state and self.game_state.get("is_active"):
                return

            # 检查是否需要刷新（已准备人数变化）
            if self.room_state:
                ready_count = sum(1 for s in self.room_state.get("seats", []) if s.get("status") == "ready")
                if ready_count != last_ready_count:
                    self._render_pregame_state()
                    last_ready_count = ready_count

            # 处理输入（非阻塞）
            self._handle_pregame_input()

            time.sleep(0.3)

    def _game_loop(self):
        """游戏阶段循环 - 处理游戏操作。"""
        while self._running and self._connected:
            # 检查游戏是否结束
            if not self.game_state or not self.game_state.get("is_active"):
                return

            # 检查是否轮到自己行动
            if self._my_turn and self.game_state:
                self._handle_my_turn()
            else:
                # 等待其他玩家
                self._render_waiting_state()
                time.sleep(0.5)

    def _on_connect(self):
        """WebSocket 连接已建立。"""
        print("[OnlineClient] WebSocket 连接已建立")
        self._connected = True
        self.display.add_chat_message("已连接到游戏服务器", is_system=True)

    def _on_disconnect(self):
        """WebSocket 连接已断开。"""
        print("[OnlineClient] WebSocket 连接已断开")
        self._connected = False
        self._running = False

    def _on_game_state(self, state: Dict):
        """游戏状态更新回调。"""
        print(f"[OnlineClient] 游戏状态更新：{state.get('phase', 'unknown')}")
        self.game_state = state

        # 更新剩余时间
        remaining = state.get("remaining_time")
        if remaining is not None:
            self._remaining_time = remaining
            self.display.set_remaining_time(remaining)
            # 启动倒计时
            self._start_countdown()

        # 检查是否轮到自己
        current_player = state.get("current_player_id")
        self._my_turn = (current_player == self.human_player_id)

        if self._my_turn:
            self._action_ready.set()  # 唤醒行动线程

    def _on_room_state(self, state: Dict):
        """房间状态更新回调。"""
        print(f"[OnlineClient] 房间状态更新")
        self.room_state = state

        # 更新房主状态
        self.is_owner = (state.get("owner_id") == self.user.id)

        # 更新座位信息
        seats = state.get("seats", [])
        for seat in seats:
            if seat.get("user_id") == self.user.id:
                self.my_seat_index = seat.get("seat_index")
                break

    def _on_chat(self, message: ChatMessage):
        """聊天消息回调。"""
        if message.is_system:
            self.display.add_chat_message(f"[系统] {message.message}", is_system=True)
        else:
            self.display.add_chat_message(f"{message.username}: {message.message}")

    def _on_info(self, message: str):
        """信息消息回调。"""
        self.display.add_chat_message(f"[信息] {message}", is_system=True)

    def _on_error(self, error: str):
        """错误回调。"""
        self.display.add_chat_message(f"[错误] {error}", is_system=True)
        print(f"[OnlineClient] 错误：{error}")

    def _show_welcome(self):
        """显示欢迎界面。"""
        lines = []
        lines.append("[bold magenta]╔═══════════════════════════════════════════════════════════╗[/bold magenta]")
        lines.append("[bold magenta]║[/bold magenta]                  [bold]欢迎加入房间[/bold]                          [bold magenta]║[/bold magenta]")
        lines.append("[bold magenta]╚═══════════════════════════════════════════════════════════╝[/bold magenta]")
        lines.append("")
        lines.append(f"[bold]房间名称:[/bold] [yellow]{self.room.get('name', 'Unknown')}[/yellow]")
        lines.append(f"[bold]盲注:[/bold] [green]{self.room.get('small_blind', 10)}/{self.room.get('big_blind', 20)}[/green]")
        lines.append(f"[bold]最大买入:[/bold] [cyan]{self.room.get('max_buyin', 2000)}[/cyan]")
        lines.append("")
        lines.append("[dim]等待其他玩家加入...[/dim]")
        lines.append("[dim]输入 'ready' 准备，'chat <消息>' 发送聊天，'quit' 离开[/dim]")

        for line in lines:
            console.print(line)

    def _update_room_info(self):
        """更新房间信息（房主、座位等）。"""
        if self.room_state:
            self.is_owner = (self.room_state.get("owner_id") == self.user.id)

    def _render_pregame_state(self):
        """渲染准备阶段界面。"""
        console.clear()

        # 顶部：房间信息
        self._render_room_header()

        # 中间：玩家座位列表
        self._render_seat_list()

        # 底部：操作按钮和聊天
        self._render_pregame_actions()

        # 聊天消息
        self._display_chat()

    def _render_room_header(self):
        """渲染房间信息头部。"""
        lines = []
        lines.append("[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]")
        lines.append("[bold cyan]║[/bold cyan]                  [bold]游戏房间[/bold]                              [bold cyan]║[/bold cyan]")
        lines.append("[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]")
        lines.append("")
        lines.append(f"[bold]房间名称:[/bold] [yellow]{self.room.get('name', 'Unknown')}[/yellow]")
        lines.append(f"[bold]盲注:[/bold] [green]{self.room.get('small_blind', 10)}/{self.room.get('big_blind', 20)}[/green]")
        lines.append(f"[bold]最大买入:[/bold] [cyan]{self.room.get('max_buyin', 2000)}[/cyan]")
        lines.append(f"[bold]状态:[/bold] {'[green]等待中[/green]' if self.room.get('status') == 'waiting' else '[yellow]游戏中[/yellow]'}")

        for line in lines:
            console.print(line)
        console.print()

    def _render_seat_list(self):
        """渲染玩家座位列表。"""
        if not self.room_state:
            return

        seats = self.room_state.get("seats", [])
        if not seats:
            console.print("[dim]暂无玩家[/dim]\n")
            return

        table = Table(title="玩家座位", box=ROUNDED, expand=True)
        table.add_column("座位", style="dim", width=6, justify="center")
        table.add_column("玩家", style="bold", width=15)
        table.add_column("筹码", style="green", width=10, justify="right")
        table.add_column("净筹码", width=10, justify="right")
        table.add_column("状态", width=12, justify="center")

        for seat in seats:
            seat_index = seat.get("seat_index", -1)
            user_id = seat.get("user_id")
            user_name = seat.get("user_name", "空位")
            chips = seat.get("chips", 0)
            net_chips = seat.get("net_chips", 0)
            status = seat.get("status", "empty")

            # 座位号
            seat_str = f"{seat_index + 1}" if seat_index >= 0 else "-"

            # 玩家名
            if status == "empty":
                name_str = "[dim]空位[/dim]"
            else:
                name_str = user_name
                if user_id == self.user.id:
                    name_str = f"[yellow]→{user_name} (你)[/yellow]"
                elif user_id == self.room_state.get("owner_id"):
                    name_str = f"[magenta]👑 {user_name}[/magenta]"

            # 筹码
            chips_str = f"[green]${chips}[/green]"

            # 净筹码
            net_style = "green" if net_chips >= 0 else "red"
            net_sign = "+" if net_chips >= 0 else ""
            net_str = f"[{net_style}]{net_sign}${net_chips}[/{net_style}]"

            # 状态
            status_map = {
                "empty": ("[dim]空位[/dim]", "○"),
                "waiting": ("[dim]等待中[/dim]", "○"),
                "ready": ("[green]已准备[/green]", "●"),
                "playing": ("[yellow]游戏中[/yellow]", "●"),
                "folded": ("[dim]已弃牌[/dim]", "×"),
                "all_in": ("[bold red]ALL-IN[/bold red]", "★"),
                "disconnected": ("[red]已断线[/red]", "○"),
            }
            status_text, status_icon = status_map.get(status, ("未知", "○"))

            table.add_row(seat_str, name_str, chips_str, net_str, f"{status_icon} {status_text}")

        console.print(table)
        console.print()

    def _render_pregame_actions(self):
        """渲染准备阶段操作按钮。"""
        if not self.room_state:
            return

        # 找到自己的座位
        my_seat = None
        seats = self.room_state.get("seats", [])
        for seat in seats:
            if seat.get("user_id") == self.user.id:
                my_seat = seat
                break

        if not my_seat:
            console.print("[yellow]你还未入座，请选择座位加入[/yellow]\n")
            return

        # 显示我的座位信息
        lines = []
        lines.append("[bold cyan]─────────────────────────────────────────────────────[/bold cyan]")
        lines.append(f"[bold]我的座位:[/bold] 第 {my_seat.get('seat_index', 0) + 1} 号座")
        lines.append(f"[bold]我的筹码:[/bold] [green]${my_seat.get('chips', 0)}[/green]")
        net_chips = my_seat.get("net_chips", 0)
        net_style = "green" if net_chips >= 0 else "red"
        net_sign = "+" if net_chips >= 0 else ""
        lines.append(f"[bold]净筹码:[/bold] [{net_style}]{net_sign}${net_chips}[/{net_style}]")
        lines.append(f"[bold]状态:[/bold] {'[green]已准备[/green]' if my_seat.get('status') == 'ready' else '[dim]未准备[/dim]'}")
        lines.append("")

        # 操作按钮
        ready_count = sum(1 for s in seats if s.get("status") == "ready")
        player_count = sum(1 for s in seats if s.get("status") != "empty")
        lines.append(f"[bold]已准备:[/bold] {ready_count} / {player_count} 玩家")
        lines.append("")

        # 按钮提示
        if my_seat.get("chips", 0) == 0:
            lines.append("[yellow]⚠ 你的筹码已用完，请补充筹码[/yellow]")
            lines.append("  输入 'rebuy <数量>' 补充筹码")

        if my_seat.get("status") == "ready":
            lines.append("  输入 [bold]'unready'[/bold] 取消准备")
        else:
            lines.append("  输入 [bold]'ready'[/bold] 准备")

        if self.is_owner and ready_count >= 2:
            lines.append("  输入 [bold]'start'[/bold] 开始游戏 [green](房主专属)[/green]")
        elif self.is_owner:
            lines.append("[dim]  至少需要 2 名玩家准备才能开始游戏[/dim]")

        lines.append("  输入 [bold]'chat <消息>'[/bold] 发送聊天")
        lines.append("  输入 [bold]'quit'[/bold] 离开房间")
        lines.append("")

        for line in lines:
            console.print(line)

    def _handle_pregame_input(self):
        """处理准备阶段输入。"""
        # 获取自己的座位
        my_seat = None
        if self.room_state:
            seats = self.room_state.get("seats", [])
            for seat in seats:
                if seat.get("user_id") == self.user.id:
                    my_seat = seat
                    break

        if not my_seat:
            console.print("[yellow]你还未入座，请选择座位加入[/yellow]\n")
            return

        # 显示提示（不清屏）
        choice = Prompt.ask(
            "[bold cyan]请输入命令[/bold cyan] (ready/unready/start/chat/rebuy/quit/h)",
            default=""
        ).strip().lower()

        if not choice:
            return

        # 处理命令
        if choice == "ready":
            if my_seat.get("status") != "ready":
                self.send_ready()
                self._render_pregame_state()  # 刷新界面
            else:
                console.print("[yellow]你已准备[/yellow]\n")

        elif choice == "unready":
            if my_seat.get("status") == "ready":
                self.send_unready()
                self._render_pregame_state()  # 刷新界面
            else:
                console.print("[yellow]你还未准备[/yellow]\n")

        elif choice == "start":
            if self.is_owner:
                ready_count = sum(1 for s in self.room_state.get("seats", []) if s.get("status") == "ready")
                if ready_count >= 2:
                    if self.ws_client:
                        self.ws_client.send_start_game()
                        # 游戏开始后由游戏状态触发刷新
                else:
                    console.print("[yellow]至少需要 2 名玩家准备才能开始游戏[/yellow]\n")
            else:
                console.print("[yellow]只有房主可以开始游戏[/yellow]\n")

        elif choice.startswith("chat "):
            message = choice[5:].strip()
            if message:
                self.send_chat(message)
                # 聊天消息会自动显示在聊天区域

        elif choice.startswith("rebuy"):
            parts = choice.split()
            if len(parts) > 1:
                try:
                    amount = int(parts[1])
                    if my_seat.get("chips", 0) == 0:
                        # 调用 API 补充筹码
                        result = self.api_client.rebuy_chips(self.room_id, amount)
                        if result:
                            console.print(f"[green]补充筹码成功：${amount}[/green]\n")
                            self._render_pregame_state()  # 刷新界面
                        else:
                            console.print("[red]补充筹码失败[/red]\n")
                    else:
                        console.print("[yellow]只有筹码为 0 时才能补充[/yellow]\n")
                except ValueError:
                    console.print("[yellow]无效的筹码数量[/yellow]\n")
            else:
                console.print(f"[yellow]请输入补充筹码数量，例如：rebuy {self.room.get('max_buyin', 2000)}[/yellow]\n")

        elif choice == "quit" or choice == "q":
            # 离开房间
            if Confirm.ask("[bold]确定要离开房间吗？[/bold]"):
                self.api_client.leave_room(self.room_id)
                self._running = False

        elif choice == "help" or choice == "h":
            self._show_help()

        else:
            console.print(f"[yellow]未知命令：{choice}[/yellow]\n")
            self._show_help()

    def _show_help(self):
        """显示帮助信息。"""
        console.print("\n[bold cyan]可用命令:[/bold cyan]")
        console.print("  [bold]ready[/bold]     - 准备")
        console.print("  [bold]unready[/bold]   - 取消准备")
        console.print("  [bold]start[/bold]     - 开始游戏 (房主)")
        console.print("  [bold]chat <消息>[/bold] - 发送聊天")
        console.print("  [bold]rebuy <数量>[/bold] - 补充筹码 (筹码为 0 时)")
        console.print("  [bold]quit[/bold]    - 离开房间")
        console.print("  [bold]help[/bold]    - 显示帮助\n")

    def _render_waiting_state(self):
        """渲染等待状态。"""
        # 构建临时的游戏状态用于显示
        temp_game = self._create_temp_game_from_state()

        if temp_game:
            self.display.update_live(temp_game, None, "等待其他玩家行动...")
        else:
            console.print("\n[dim]等待其他玩家行动...[/dim]")

        # 显示聊天消息
        self._display_chat()

    def _render_game_state(self):
        """渲染游戏状态。"""
        temp_game = self._create_temp_game_from_state()

        if temp_game:
            current_player_id = self.game_state.get("current_player_id") if self.game_state else None
            self.display.update_live(temp_game, current_player_id)
        else:
            console.print("\n[dim]等待游戏数据...[/dim]")

    def _create_temp_game_from_state(self) -> Optional[GameEngine]:
        """从 WebSocket 游戏状态创建临时的 GameEngine 对象用于显示。"""
        # 简化实现：返回 None 表示使用简化的显示模式
        return None

    def _handle_my_turn(self):
        """处理自己的行动回合。"""
        # 渲染游戏状态
        self._render_game_state()

        # 等待用户输入
        action_data = self._get_human_action()

        if action_data:
            # 发送操作到服务器
            action = action_data.get("action")
            amount = action_data.get("amount")

            if action:
                success = self.ws_client.send_action(action, amount)
                if success:
                    self._my_turn = False
                    self.display.add_chat_message(f"已执行操作：{action}", is_system=True)
                else:
                    self.display.add_chat_message("操作发送失败", is_system=True)

    def _get_human_action(self) -> Optional[Dict]:
        """获取人类玩家的操作。"""
        if not self.game_state:
            return None

        # 简化处理：显示操作提示，等待用户输入
        console.print("\n[bold yellow]轮到你行动！[/bold yellow]")
        console.print("[1] 弃牌  [2] 过牌  [3] 跟注  [4] 加注  [5] 全押")

        # 简化版本：直接返回一个默认操作
        return {"action": "check", "amount": 0}

    def _display_chat(self):
        """显示聊天消息。"""
        messages = self.ws_client.get_chat_messages() if self.ws_client else []
        if messages:
            console.print("\n[bold cyan]聊天:[/bold cyan]")
            for msg in messages[-5:]:
                if msg.is_system:
                    console.print(f"  [dim][系统] {msg.message}[/dim]")
                else:
                    console.print(f"  {msg.username}: {msg.message}")

    def _start_countdown(self):
        """启动倒计时线程。"""
        self._stop_countdown.set()  # 停止之前的倒计时
        self._stop_countdown.clear()

        self._countdown_thread = threading.Thread(target=self._countdown_loop, daemon=True)
        self._countdown_thread.start()

    def _countdown_loop(self):
        """倒计时循环。"""
        while self._remaining_time is not None and self._remaining_time > 0:
            if self._stop_countdown.is_set():
                break

            time.sleep(1)
            if self._remaining_time is not None:
                self._remaining_time -= 1
                self.display.set_remaining_time(self._remaining_time)

    def send_ready(self):
        """发送准备信号。"""
        if self.ws_client and self._connected:
            self.ws_client.send_ready()
            self.is_ready = True
            self.display.add_chat_message("已准备", is_system=True)

    def send_unready(self):
        """发送取消准备信号。"""
        if self.ws_client and self._connected:
            self.ws_client.send_unready()
            self.is_ready = False
            self.display.add_chat_message("已取消准备", is_system=True)

    def send_chat(self, message: str):
        """发送聊天消息。"""
        if self.ws_client and self._connected:
            self.ws_client.send_chat(message)


def main():
    """测试入口。"""
    # 创建 API 客户端
    api_client = SyncAPIClient(base_url="http://localhost:8000")

    # 登录（测试用）
    result = api_client.login("test", "test123")
    if not result.success:
        print(f"登录失败：{result.error}")
        return

    user = result.user
    print(f"登录成功：{user.display_name}")

    # 获取房间列表
    rooms = api_client.get_rooms()
    if not rooms:
        print("没有可用的房间")
        return

    # 加入第一个房间（测试用）
    room = rooms[0]
    print(f"加入房间：{room['name']}")

    # 创建在线客户端
    client = OnlinePokerClient(api_client, user, room)
    client.run()


if __name__ == "__main__":
    main()
