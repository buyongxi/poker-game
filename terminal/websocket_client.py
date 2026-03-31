"""
WebSocket 客户端模块 - 连接后端 WebSocket 服务

负责与后端建立 WebSocket 连接，接收实时游戏状态更新，发送玩家操作。
"""

import json
import threading
import time
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False


class MessageType(Enum):
    """WebSocket 消息类型。"""
    GAME_STATE = "game_state"
    ROOM_STATE = "room_state"
    CHAT = "chat"
    USER_JOINED = "user_joined"
    USER_DISCONNECTED = "user_disconnected"
    USER_LEFT = "user_left"
    OWNER_CHANGED = "owner_changed"
    ROOM_DELETED = "room_deleted"
    HAND_COMPLETE = "hand_complete"
    GAME_ENDED = "game_ended"
    INFO = "info"
    ERROR = "error"


@dataclass
class ChatMessage:
    """聊天消息。"""
    user_id: int
    username: str
    message: str
    is_system: bool = False


@dataclass
class WSMessage:
    """WebSocket 消息。"""
    type: str
    data: Any


class WebSocketClient:
    """
    WebSocket 客户端。

    负责与后端建立 WebSocket 连接，处理消息收发。
    """

    def __init__(
        self,
        base_url: str = "ws://localhost:8000",
        token: Optional[str] = None,
        room_id: Optional[int] = None
    ):
        """
        初始化 WebSocket 客户端。

        Args:
            base_url: WebSocket 基础 URL
            token: JWT 认证 token
            room_id: 房间 ID
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("websocket-client 库未安装，请运行：pip install websocket-client")

        self.base_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.token = token
        self.room_id = room_id
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connected = False
        self._thread: Optional[threading.Thread] = None
        self._running = False

        # 回调函数
        self._on_game_state_callbacks: List[Callable] = []
        self._on_room_state_callbacks: List[Callable] = []
        self._on_chat_callbacks: List[Callable] = []
        self._on_info_callbacks: List[Callable] = []
        self._on_error_callbacks: List[Callable] = []
        self._on_connect_callbacks: List[Callable] = []
        self._on_disconnect_callbacks: List[Callable] = []

        # 当前游戏状态
        self.game_state: Optional[Dict] = None
        self.room_state: Optional[Dict] = None
        self.chat_messages: List[ChatMessage] = []
        self.info_messages: List[str] = []

    def connect(self, room_id: Optional[int] = None, token: Optional[str] = None) -> bool:
        """
        连接到 WebSocket 服务。

        Args:
            room_id: 房间 ID
            token: JWT 认证 token

        Returns:
            连接成功返回 True
        """
        if room_id:
            self.room_id = room_id
        if token:
            self.token = token

        if not self.room_id or not self.token:
            print("[WS] 错误：需要 room_id 和 token")
            return False

        # 构建 WebSocket URL
        ws_url = f"{self.base_url}/ws/room/{self.room_id}?token={self.token}"
        print(f"[WS] 连接到：{ws_url}")

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        # 等待连接建立
        for _ in range(50):  # 最多等待 5 秒
            if self.connected:
                return True
            time.sleep(0.1)

        return False

    def _run(self):
        """运行 WebSocket 循环（在独立线程中）。"""
        self.ws.run_forever()

    def _on_open(self, ws):
        """连接建立回调。"""
        print("[WS] 连接已建立")
        self.connected = True
        for callback in self._on_connect_callbacks:
            callback()

    def _on_message(self, ws, message: str):
        """消息接收回调。"""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")
            msg_data = data.get("data", {})

            print(f"[WS] 收到消息：{msg_type}")

            if msg_type == MessageType.GAME_STATE.value:
                self.game_state = msg_data
                for callback in self._on_game_state_callbacks:
                    callback(msg_data)

            elif msg_type == MessageType.ROOM_STATE.value:
                self.room_state = msg_data
                for callback in self._on_room_state_callbacks:
                    callback(msg_data)

            elif msg_type == MessageType.CHAT.value:
                chat_msg = ChatMessage(
                    user_id=msg_data.get("user_id", 0),
                    username=msg_data.get("username", "未知"),
                    message=msg_data.get("message", ""),
                    is_system=msg_data.get("is_system", False)
                )
                self.chat_messages.append(chat_msg)
                # 保留最近 100 条消息
                if len(self.chat_messages) > 100:
                    self.chat_messages = self.chat_messages[-100:]
                for callback in self._on_chat_callbacks:
                    callback(chat_msg)

            elif msg_type == MessageType.INFO.value:
                info_msg = msg_data.get("message", "")
                self.info_messages.append(info_msg)
                for callback in self._on_info_callbacks:
                    callback(info_msg)

            elif msg_type == MessageType.ERROR.value:
                error_msg = msg_data.get("message", "未知错误")
                print(f"[WS] 错误：{error_msg}")
                for callback in self._on_error_callbacks:
                    callback(error_msg)

            elif msg_type == MessageType.OWNER_CHANGED.value:
                # 房主变更，更新房间状态
                if self.room_state:
                    self.room_state["owner_id"] = msg_data.get("new_owner_id")
                for callback in self._on_room_state_callbacks:
                    callback(msg_data)

            elif msg_type == MessageType.HAND_COMPLETE.value:
                # 手牌结束，更新游戏状态
                if msg_data.get("result_message"):
                    chat_msg = ChatMessage(
                        user_id=0,
                        username="系统",
                        message=msg_data.get("result_message", ""),
                        is_system=True
                    )
                    self.chat_messages.append(chat_msg)
                    for callback in self._on_chat_callbacks:
                        callback(chat_msg)

            elif msg_type == MessageType.GAME_ENDED.value:
                self.game_state = None
                for callback in self._on_game_state_callbacks:
                    callback(None)

            elif msg_type == MessageType.ROOM_DELETED.value:
                print("[WS] 房间已被删除")
                self.disconnect()

        except json.JSONDecodeError as e:
            print(f"[WS] JSON 解析错误：{e}")
        except Exception as e:
            print(f"[WS] 消息处理错误：{e}")

    def _on_error(self, ws, error):
        """错误回调。"""
        print(f"[WS] 错误：{error}")
        for callback in self._on_error_callbacks:
            callback(str(error))

    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调。"""
        print(f"[WS] 连接已关闭：{close_status_code} - {close_msg}")
        self.connected = False
        for callback in self._on_disconnect_callbacks:
            callback()

    def disconnect(self):
        """断开连接。"""
        print("[WS] 断开连接")
        self._running = False
        if self.ws:
            self.ws.close()
        if self._thread:
            self._thread.join(timeout=2)
        self.connected = False
        self.game_state = None
        self.room_state = None

    def send(self, msg_type: str, data: Optional[Dict] = None) -> bool:
        """
        发送消息。

        Args:
            msg_type: 消息类型
            data: 消息数据

        Returns:
            发送成功返回 True
        """
        if not self.connected or not self.ws:
            print("[WS] 未连接，无法发送消息")
            return False

        message = {
            "type": msg_type,
            "data": data or {}
        }

        try:
            self.ws.send(json.dumps(message))
            print(f"[WS] 发送消息：{msg_type}")
            return True
        except Exception as e:
            print(f"[WS] 发送消息失败：{e}")
            return False

    # 便捷方法
    def send_ready(self) -> bool:
        """发送准备信号。"""
        return self.send("ready", {})

    def send_unready(self) -> bool:
        """发送取消准备信号。"""
        return self.send("unready", {})

    def send_start_game(self) -> bool:
        """发送开始游戏信号。"""
        return self.send("start_game", {})

    def send_stop_game(self) -> bool:
        """发送停止游戏信号。"""
        return self.send("stop_game", {})

    def send_action(self, action: str, amount: Optional[int] = None) -> bool:
        """
        发送游戏操作。

        Args:
            action: 操作类型 (fold/check/call/raise/all_in)
            amount: 加注金额（仅 raise 操作需要）
        """
        data = {"action": action}
        if amount is not None:
            data["amount"] = amount
        return self.send("action", data)

    def send_chat(self, message: str) -> bool:
        """发送聊天消息。"""
        return self.send("chat", {"message": message})

    # 回调注册方法
    def on_game_state(self, callback: Callable):
        """注册游戏状态更新回调。"""
        self._on_game_state_callbacks.append(callback)
        return callback

    def on_room_state(self, callback: Callable):
        """注册房间状态更新回调。"""
        self._on_room_state_callbacks.append(callback)
        return callback

    def on_chat(self, callback: Callable):
        """注册聊天消息回调。"""
        self._on_chat_callbacks.append(callback)
        return callback

    def on_info(self, callback: Callable):
        """注册信息消息回调。"""
        self._on_info_callbacks.append(callback)
        return callback

    def on_error(self, callback: Callable):
        """注册错误回调。"""
        self._on_error_callbacks.append(callback)
        return callback

    def on_connect(self, callback: Callable):
        """注册连接建立回调。"""
        self._on_connect_callbacks.append(callback)
        return callback

    def on_disconnect(self, callback: Callable):
        """注册连接断开回调。"""
        self._on_disconnect_callbacks.append(callback)
        return callback

    # 获取状态
    def get_game_state(self) -> Optional[Dict]:
        """获取当前游戏状态。"""
        return self.game_state

    def get_room_state(self) -> Optional[Dict]:
        """获取当前房间状态。"""
        return self.room_state

    def get_chat_messages(self) -> List[ChatMessage]:
        """获取聊天消息列表。"""
        return self.chat_messages.copy()

    def get_info_messages(self) -> List[str]:
        """获取信息消息列表。"""
        return self.info_messages.copy()

    def clear_info_messages(self):
        """清空信息消息。"""
        self.info_messages = []
