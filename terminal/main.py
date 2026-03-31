"""
德州扑克终端游戏 - 主入口

功能：
- 用户认证（登录/注册）
- 游戏大厅（创建/加入房间）
- 德州扑克游戏（在线联网或离线本地）

运行方式:
    python main.py
"""

import sys
import os
import time

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from api_client import SyncAPIClient, User
from ui.auth import AuthManager, display_login_success, display_auth_error
from lobby import LobbyManager
from poker_terminal import TerminalPokerClient
from online_client import OnlinePokerClient


def main():
    """主入口函数。"""
    # 初始化 API 客户端
    api_client = SyncAPIClient(base_url="http://localhost:8000")

    # 认证流程
    auth_manager = AuthManager(api_client)
    user = auth_manager.run()

    if not user:
        print("\n[yellow]已退出游戏，再见！[/yellow]\n")
        return

    # 显示登录成功
    display_login_success(user)

    # 检查是否为离线模式
    if user.id == 0:
        # 离线模式 - 直接启动本地游戏
        print("\n[green]进入离线模式，启动本地游戏...[/green]\n")
        client = TerminalPokerClient()
        client.run()
        return

    # 大厅流程
    lobby_manager = LobbyManager(api_client, user)
    room = lobby_manager.run()

    if not room:
        print("\n[yellow]已返回主菜单[/yellow]\n")
        return

    # 启动游戏
    print(f"\n[green]正在进入游戏：{room['name']}...[/green]\n")
    time.sleep(1)

    # 在线模式 - 使用 WebSocket 连接
    client = OnlinePokerClient(api_client, user, room)
    client.run()


if __name__ == "__main__":
    main()
