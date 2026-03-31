"""
API 客户端模块 - 连接后端 REST API

提供登录、注册、用户信息获取等功能。
"""

import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json


@dataclass
class User:
    """用户数据类。"""
    id: int
    username: str
    display_name: str
    chips: int = 1000
    role: str = "user"  # "user" 或 "admin"
    status: str = "active"  # "active", "pending", "disabled"


@dataclass
class LoginResult:
    """登录结果。"""
    success: bool
    token: Optional[str] = None
    error: Optional[str] = None
    user: Optional[User] = None


@dataclass
class RegisterResult:
    """注册结果。"""
    success: bool
    error: Optional[str] = None
    user: Optional[User] = None


class APIClient:
    """
    后端 API 客户端。

    负责与后端 REST API 通信，处理认证和用户管理。
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.current_user: Optional[User] = None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头，包含认证 token。"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def login(self, username: str, password: str) -> LoginResult:
        """
        用户登录。

        Args:
            username: 用户名
            password: 密码

        Returns:
            LoginResult 包含登录结果
        """
        url = f"{self.base_url}/api/auth/login"
        data = {
            "username": username,
            "password": password
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})

                if response.status_code == 200:
                    result = response.json()
                    self.token = result["access_token"]

                    # 获取用户信息
                    user_result = await self.get_current_user()
                    if user_result:
                        self.current_user = user_result
                        return LoginResult(success=True, token=self.token, user=user_result)

                    # 获取用户信息失败，认为登录失败
                    return LoginResult(success=False, error="获取用户信息失败")
                else:
                    error_data = response.json()
                    return LoginResult(success=False, error=error_data.get("detail", "登录失败"))

        except httpx.RequestError as e:
            return LoginResult(success=False, error=f"连接错误：{str(e)}")
        except Exception as e:
            return LoginResult(success=False, error=f"登录失败：{str(e)}")

    async def register(self, username: str, password: str, display_name: str) -> RegisterResult:
        """
        用户注册。

        Args:
            username: 用户名
            password: 密码
            display_name: 显示名称

        Returns:
            RegisterResult 包含注册结果
        """
        url = f"{self.base_url}/api/auth/register"
        data = {
            "username": username,
            "password": password,
            "display_name": display_name
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=self._get_headers())

                if response.status_code == 200:
                    result = response.json()
                    return RegisterResult(
                        success=True,
                        user=User(
                            id=result["id"],
                            username=result["username"],
                            display_name=result["display_name"],
                            chips=result.get("chips", 1000)
                        )
                    )
                else:
                    error_data = response.json()
                    return RegisterResult(success=False, error=error_data.get("detail", "注册失败"))

        except httpx.RequestError as e:
            return RegisterResult(success=False, error=f"连接错误：{str(e)}")
        except Exception as e:
            return RegisterResult(success=False, error=f"注册失败：{str(e)}")

    async def get_current_user(self) -> Optional[User]:
        """获取当前用户信息。"""
        if not self.token:
            return None

        url = f"{self.base_url}/api/auth/me"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code == 200:
                    result = response.json()
                    return User(
                        id=result["id"],
                        username=result["username"],
                        display_name=result["display_name"],
                        chips=result.get("chips", 1000),
                        role=result.get("role", "user"),
                        status=result.get("status", "active")
                    )
        except Exception:
            pass

        return None

    async def get_rooms(self) -> list:
        """获取房间列表。"""
        url = f"{self.base_url}/api/rooms"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return []

    async def create_room(self, name: str, max_seats: int = 9,
                          small_blind: int = 10, big_blind: int = 20,
                          max_buyin: int = 2000) -> Optional[Dict]:
        """创建房间。"""
        url = f"{self.base_url}/api/rooms"
        data = {
            "name": name,
            "max_seats": max_seats,
            "small_blind": small_blind,
            "big_blind": big_blind,
            "max_buyin": max_buyin
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=self._get_headers())

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return None

    async def join_room(self, room_id: int, seat_index: int) -> Optional[Dict]:
        """加入房间。"""
        url = f"{self.base_url}/api/rooms/{room_id}/join"
        data = {"seat_index": seat_index}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=self._get_headers())

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return None

    async def leave_room(self, room_id: int) -> bool:
        """离开房间。"""
        url = f"{self.base_url}/api/rooms/{room_id}/leave"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self._get_headers())
                return response.status_code == 200
        except Exception:
            return False


# 同步版本的 API 客户端（用于终端应用）
class SyncAPIClient:
    """
    同步版本的 API 客户端。

    终端应用使用同步调用，避免 asyncio 复杂性。
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.current_user: Optional[User] = None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头，包含认证 token。"""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, username: str, password: str) -> LoginResult:
        """用户登录（同步版本）。"""
        url = f"{self.base_url}/api/auth/login"
        data = f"username={username}&password={password}"

        try:
            with httpx.Client() as client:
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                response = client.post(url, content=data, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    self.token = result["access_token"]

                    # 获取用户信息
                    user_result = self.get_current_user()
                    if user_result:
                        self.current_user = user_result
                        return LoginResult(success=True, token=self.token, user=user_result)

                    # 获取用户信息失败，认为登录失败
                    return LoginResult(success=False, error="获取用户信息失败")
                else:
                    error_data = response.json()
                    return LoginResult(success=False, error=error_data.get("detail", "登录失败"))

        except httpx.RequestError as e:
            return LoginResult(success=False, error=f"连接错误：{str(e)}")
        except Exception as e:
            return LoginResult(success=False, error=f"登录失败：{str(e)}")

    def register(self, username: str, password: str, display_name: str) -> RegisterResult:
        """用户注册（同步版本）。"""
        url = f"{self.base_url}/api/auth/register"
        data = {
            "username": username,
            "password": password,
            "display_name": display_name
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers())

                if response.status_code == 200:
                    result = response.json()
                    return RegisterResult(
                        success=True,
                        user=User(
                            id=result["id"],
                            username=result["username"],
                            display_name=result["display_name"],
                            chips=result.get("chips", 1000)
                        )
                    )
                else:
                    error_data = response.json()
                    return RegisterResult(success=False, error=error_data.get("detail", "注册失败"))

        except httpx.RequestError as e:
            return RegisterResult(success=False, error=f"连接错误：{str(e)}")
        except Exception as e:
            return RegisterResult(success=False, error=f"注册失败：{str(e)}")

    def get_current_user(self) -> Optional[User]:
        """获取当前用户信息（同步版本）。"""
        if not self.token:
            return None

        url = f"{self.base_url}/api/auth/me"

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self._get_headers())

                if response.status_code == 200:
                    result = response.json()
                    return User(
                        id=result["id"],
                        username=result["username"],
                        display_name=result["display_name"],
                        chips=result.get("chips", 1000),
                        role=result.get("role", "user"),
                        status=result.get("status", "active")
                    )
        except Exception as e:
            print(f"[DEBUG] get_current_user error: {e}")
            pass

        return None

    def get_rooms(self) -> list:
        """获取房间列表（同步版本）。"""
        url = f"{self.base_url}/api/rooms/"

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self._get_headers(), follow_redirects=True)

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return []

    def create_room(self, name: str, max_seats: int = 9,
                    small_blind: int = 10, big_blind: int = 20,
                    max_buyin: int = 2000) -> Optional[Dict]:
        """创建房间（同步版本）。"""
        url = f"{self.base_url}/api/rooms/"
        data = {
            "name": name,
            "max_seats": max_seats,
            "small_blind": small_blind,
            "big_blind": big_blind,
            "max_buyin": max_buyin
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers(), follow_redirects=True)

                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"[DEBUG] 创建房间失败：{response.status_code} - {response.text}")
        except Exception as e:
            print(f"[DEBUG] 创建房间异常：{e}")

        return None

    def join_room(self, room_id: int, seat_index: int) -> Optional[Dict]:
        """加入房间（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/join"
        data = {"seat_index": seat_index}

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers(), follow_redirects=True)

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return None

    def leave_room(self, room_id: int) -> bool:
        """离开房间（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/leave"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def rebuy_chips(self, room_id: int, amount: int) -> Optional[Dict]:
        """补充筹码（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/rebuy"
        data = {"amount": amount}

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers(), follow_redirects=True)

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return None

    def switch_seat(self, room_id: int, seat_index: int) -> Optional[Dict]:
        """切换座位（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/switch_seat"
        data = {"seat_index": seat_index}

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers(), follow_redirects=True)

                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return None

    def send_ready(self, room_id: int) -> bool:
        """设置准备状态（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/ready"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def send_unready(self, room_id: int) -> bool:
        """取消准备状态（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/unready"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def send_start_game(self, room_id: int) -> bool:
        """开始游戏（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/start_game"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def send_stop_game(self, room_id: int) -> bool:
        """停止游戏（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/stop_game"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def send_chat(self, room_id: int, message: str) -> bool:
        """发送聊天消息（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/chat"
        data = {"message": message}

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def send_action(self, room_id: int, action: str, amount: Optional[int] = None) -> bool:
        """发送游戏操作（同步版本）。"""
        url = f"{self.base_url}/api/rooms/{room_id}/action"
        data = {"action": action}
        if amount is not None:
            data["amount"] = amount

        try:
            with httpx.Client() as client:
                response = client.post(url, json=data, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    # ========== 管理员 API ==========

    def get_pending_users(self) -> List[Dict]:
        """获取待审核用户列表（管理员专用）。"""
        url = f"{self.base_url}/api/admin/pending"

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self._get_headers(), follow_redirects=True)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return []

    def get_all_users(self) -> List[Dict]:
        """获取所有用户列表（管理员专用）。"""
        url = f"{self.base_url}/api/users/"

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self._get_headers(), follow_redirects=True)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass

        return []

    def activate_user(self, user_id: int) -> bool:
        """激活用户（管理员专用）。"""
        url = f"{self.base_url}/api/admin/users/{user_id}/activate"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def disable_user(self, user_id: int) -> bool:
        """禁用用户（管理员专用）。"""
        url = f"{self.base_url}/api/admin/users/{user_id}/disable"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def enable_user(self, user_id: int) -> bool:
        """启用用户（管理员专用）。"""
        url = f"{self.base_url}/api/admin/users/{user_id}/enable"

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def set_admin(self, user_id: int, is_admin: bool) -> bool:
        """设置管理员权限（管理员专用）。"""
        url = f"{self.base_url}/api/admin/users/{user_id}/set-admin"
        params = {"is_admin": str(is_admin).lower()}

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self._get_headers(), params=params, follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False

    def is_admin_user(self) -> bool:
        """检查当前用户是否为管理员。"""
        if not self.current_user:
            return False
        # 检查用户数据中是否有 admin 角色
        return self.current_user.role == 'admin'
