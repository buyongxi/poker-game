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
from ui.input import (
    get_player_action,
    prompt_rebuy,
)
from websocket_client import WebSocketClient, ChatMessage
from api_client import SyncAPIClient, User


class OnlinePokerClient:
    """
    在线扑克游戏客户端。

    通过 WebSocket 与后端通信，支持：
    - 实时游戏状态更新
    - 聊天功能
    - 准备/取消准备
    - 游戏操作
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

        # 倒计时
        self._countdown_thread: Optional[threading.Thread] = None
        self._remaining_time: Optional[int] = None
        self._stop_countdown = threading.Event()

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

        # 显示欢迎界面
        self._show_welcome()

        # 等待游戏状态
        self.display.display_message("等待游戏开始...", title="信息", style="cyan")

        # 主循环
        try:
            while self._running and self._connected:
                # 检查是否轮到自己行动
                if self._my_turn and self.game_state:
                    self._handle_my_turn()
                else:
                    # 等待其他玩家
                    self._render_waiting_state()
                    time.sleep(0.5)

        except KeyboardInterrupt:
            self._running = False
            self.display.display_message("游戏已中断", title="中断", style="yellow")

        finally:
            self.disconnect()

    def _on_connect(self):
        """WebSocket 连接建立。"""
        print("[OnlineClient] WebSocket 连接已建立")
        self._connected = True
        self.display.add_chat_message("已连接到游戏服务器", is_system=True)

    def _on_disconnect(self):
        """WebSocket 连接断开。"""
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
        self.display.clear()

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
            self.display.console.print(line)

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
        # 这里需要从游戏状态中获取可用操作
        # 由于是在线模式，我们需要解析游戏状态来构建操作菜单

        if not self.game_state:
            return None

        # 简化处理：显示操作提示，等待用户输入
        self.display.console.print("\n[bold yellow]轮到你行动！[/bold yellow]")
        self.display.console.print("[1] 弃牌  [2] 过牌  [3] 跟注  [4] 加注  [5] 全押")

        # 这里应该使用更复杂的输入处理
        # 简化版本：直接返回一个默认操作
        return {"action": "check", "amount": 0}

    def _render_waiting_state(self):
        """渲染等待状态。"""
        # 构建临时的游戏状态用于显示
        temp_game = self._create_temp_game_from_state()

        if temp_game:
            self.display.update_live(temp_game, None, "等待其他玩家行动...")
        else:
            self.display.console.print("\n[dim]等待游戏开始...[/dim]")

        # 显示聊天消息
        self._display_chat()

    def _render_game_state(self):
        """渲染游戏状态。"""
        temp_game = self._create_temp_game_from_state()

        if temp_game:
            current_player_id = self.game_state.get("current_player_id") if self.game_state else None
            self.display.update_live(temp_game, current_player_id)
        else:
            self.display.console.print("\n[dim]等待游戏数据...[/dim]")

    def _create_temp_game_from_state(self) -> Optional[GameEngine]:
        """从 WebSocket 游戏状态创建临时的 GameEngine 对象用于显示。"""
        # 这是一个简化实现，实际可能需要更复杂的转换
        # 这里返回 None 表示使用简化的显示模式
        return None

    def _display_chat(self):
        """显示聊天消息。"""
        messages = self.ws_client.get_chat_messages() if self.ws_client else []
        if messages:
            self.display.console.print("\n[bold cyan]聊天:[/bold cyan]")
            for msg in messages[-5:]:
                if msg.is_system:
                    self.display.console.print(f"  [dim][系统] {msg.message}[/dim]")
                else:
                    self.display.console.print(f"  {msg.username}: {msg.message}")

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
            self.display.add_chat_message("已准备", is_system=True)

    def send_unready(self):
        """发送取消准备信号。"""
        if self.ws_client and self._connected:
            self.ws_client.send_unready()
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
