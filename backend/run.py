import argparse
import os

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description='启动德州扑克游戏服务器')
    parser.add_argument('--admin-username', default=None, help='初始管理员用户名')
    parser.add_argument('--admin-password', default=None, help='初始管理员密码')
    parser.add_argument('--admin-display-name', default=None, help='初始管理员显示名称（默认由 .env 或程序内回退）')
    parser.add_argument('--action-timeout', type=int, help='玩家操作超时时间（秒）')

    args = parser.parse_args()

    # 必须在导入 app（进而实例化 Settings）之前写入环境变量
    if args.admin_username is not None:
        os.environ['ADMIN_USERNAME'] = args.admin_username
    if args.admin_password is not None:
        os.environ['ADMIN_PASSWORD'] = args.admin_password
    if args.admin_display_name is not None:
        os.environ['ADMIN_DISPLAY_NAME'] = args.admin_display_name
    if args.action_timeout is not None:
        os.environ['ACTION_TIMEOUT'] = str(args.action_timeout)

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
