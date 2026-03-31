#!/usr/bin/env python3
"""
终端前端功能测试脚本

用于验证终端前端的所有功能是否正常工作。
"""

import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

def test_api_client():
    """测试 API 客户端功能。"""
    print("\n" + "=" * 60)
    print("测试 API 客户端功能")
    print("=" * 60)

    # 直接导入模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("api_client", "api_client.py")
    api_client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_client)

    client = api_client.SyncAPIClient(base_url="http://localhost:8000")

    # 测试方法是否存在
    methods = [
        'login', 'register', 'get_current_user', 'get_rooms',
        'create_room', 'join_room', 'leave_room',
        'rebuy_chips', 'switch_seat', 'send_ready', 'send_unready',
        'send_start_game', 'send_stop_game', 'send_chat', 'send_action'
    ]

    all_passed = True
    for method in methods:
        if hasattr(client, method):
            print(f"  ✓ {method} 方法存在")
        else:
            print(f"  ✗ {method} 方法缺失")
            all_passed = False

    print("\nAPI 客户端功能测试完成\n")
    return all_passed


def test_websocket_client():
    """测试 WebSocket 客户端功能。"""
    print("\n" + "=" * 60)
    print("测试 WebSocket 客户端功能")
    print("=" * 60)

    # 检查 websocket-client 库是否安装
    try:
        import websocket
        print("  ✓ websocket-client 库已安装")
    except ImportError:
        print("  ✗ websocket-client 库未安装，请运行：pip install websocket-client")
        return False

    # 直接导入模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("websocket_client", "websocket_client.py")
    ws_client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ws_client)

    # 测试类是否存在
    if ws_client.WebSocketClient:
        print("  ✓ WebSocketClient 类已定义")
    else:
        print("  ✗ WebSocketClient 类未定义")
        return False

    # 测试方法是否存在
    methods = [
        'connect', 'disconnect', 'send',
        'send_ready', 'send_unready', 'send_start_game', 'send_stop_game',
        'send_action', 'send_chat',
        'on_game_state', 'on_room_state', 'on_chat',
        'get_game_state', 'get_room_state', 'get_chat_messages'
    ]

    all_passed = True
    for method in methods:
        if hasattr(ws_client.WebSocketClient, method):
            print(f"  ✓ {method} 方法已定义")
        else:
            print(f"  ✗ {method} 方法未定义")
            all_passed = False

    print("\nWebSocket 客户端功能测试完成\n")
    return all_passed


def test_display():
    """测试显示模块功能。"""
    print("\n" + "=" * 60)
    print("测试显示模块功能")
    print("=" * 60)

    # 直接导入模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("display", "ui/display.py")
    display_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(display_module)

    display = display_module.TerminalDisplay()

    # 测试方法是否存在
    methods = [
        'clear', 'live_display', 'update_live',
        'render_layout', 'render_and_print',
        'display_hand_result', 'display_message', 'display_welcome',
        'add_chat_message', 'clear_chat_messages',
        'set_remaining_time', 'record_starting_chips'
    ]

    all_passed = True
    for method in methods:
        if hasattr(display, method):
            print(f"  ✓ {method} 方法已定义")
        else:
            print(f"  ✗ {method} 方法未定义")
            all_passed = False

    # 测试 CardDisplay
    print("\n  测试 CardDisplay:")
    if display_module.CardDisplay:
        print("    ✓ CardDisplay 类已定义")
        if hasattr(display_module.CardDisplay, 'card_to_text'):
            print("    ✓ card_to_text 方法已定义")
        if hasattr(display_module.CardDisplay, 'render_card'):
            print("    ✓ render_card 方法已定义")
        if hasattr(display_module.CardDisplay, 'render_hand'):
            print("    ✓ render_hand 方法已定义")

    print("\n显示模块功能测试完成\n")
    return all_passed


def test_online_client():
    """测试在线游戏客户端。"""
    print("\n" + "=" * 60)
    print("测试在线游戏客户端")
    print("=" * 60)

    # 检查文件是否存在
    if not os.path.exists("online_client.py"):
        print("  ✗ online_client.py 文件不存在")
        return False

    # 检查是否有语法错误
    try:
        with open("online_client.py", "r") as f:
            compile(f.read(), "online_client.py", "exec")
        print("  ✓ online_client.py 语法正确")
    except SyntaxError as e:
        print(f"  ✗ online_client.py 语法错误：{e}")
        return False

    # 由于在线客户端依赖其他模块，这里只检查文件内容
    with open("online_client.py", "r") as f:
        content = f.read()

    # 检查关键类和函数是否存在
    checks = [
        ("OnlinePokerClient 类", "class OnlinePokerClient"),
        ("connect 方法", "def connect"),
        ("disconnect 方法", "def disconnect"),
        ("run 方法", "def run"),
        ("send_ready 方法", "def send_ready"),
        ("send_unready 方法", "def send_unready"),
        ("send_chat 方法", "def send_chat"),
        ("WebSocketClient 使用", "WebSocketClient"),
    ]

    all_passed = True
    for name, pattern in checks:
        if pattern in content:
            print(f"  ✓ {name} 存在")
        else:
            print(f"  ✗ {name} 缺失")
            all_passed = False

    print("\n在线游戏客户端测试完成\n")
    return all_passed


def test_main_integration():
    """测试主入口整合。"""
    print("\n" + "=" * 60)
    print("测试主入口整合")
    print("=" * 60)

    # 检查 main.py 是否存在
    if os.path.exists("main.py"):
        print("  ✓ main.py 文件存在")

        # 检查是否有语法错误
        try:
            with open("main.py", "r") as f:
                compile(f.read(), "main.py", "exec")
            print("  ✓ main.py 语法正确")
        except SyntaxError as e:
            print(f"  ✗ main.py 语法错误：{e}")
            print("\n主入口整合测试完成\n")
            return False
    else:
        print("  ✗ main.py 文件不存在")
        print("\n主入口整合测试完成\n")
        return False

    print("\n主入口整合测试完成\n")
    return True


def run_all_tests():
    """运行所有测试。"""
    print("\n" + "=" * 60)
    print("德州扑克终端前端 - 功能测试")
    print("=" * 60)

    results = []
    results.append(("API 客户端", test_api_client()))
    results.append(("WebSocket 客户端", test_websocket_client()))
    results.append(("显示模块", test_display()))
    results.append(("在线客户端", test_online_client()))
    results.append(("主入口", test_main_integration()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n总计：{passed} 通过，{failed} 失败")

    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
    print("\n提示：以上测试仅验证代码结构，实际功能需要运行后端服务后测试。")
    print("\n运行方式:")
    print("  1. 启动后端服务：cd backend && python run.py")
    print("  2. 运行终端前端：python main.py")
    print("  3. 离线模式：python poker_terminal.py")
    print()


if __name__ == "__main__":
    run_all_tests()
