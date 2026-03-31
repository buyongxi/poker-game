"""
认证模块 - 登录、注册界面
"""

from rich.prompt import Prompt, Confirm
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Optional, Tuple

from api_client import SyncAPIClient, User, LoginResult, RegisterResult


console = Console()


class AuthManager:
    """
    认证管理器 - 处理登录、注册流程。
    """

    def __init__(self, api_client: SyncAPIClient):
        self.api_client = api_client
        self.current_user: Optional[User] = None

    def run(self) -> Optional[User]:
        """
        运行认证流程。

        Returns:
            登录成功返回 User 对象，取消返回 None
        """
        while True:
            choice = self._show_auth_menu()

            if choice == "1":
                result = self._do_login()
                if result.success:
                    return result.user
            elif choice == "2":
                result = self._do_register()
                if result.success:
                    # 注册成功后提示登录
                    console.print("\n[green]注册成功！请使用用户名和密码登录。[/green]\n")
            elif choice == "3":
                # 离线模式
                return User(id=0, username="玩家", display_name="玩家", chips=1000)
            elif choice == "q":
                return None

    def _show_auth_menu(self) -> str:
        """显示认证菜单。"""
        console.clear()

        text = Text()
        text.append("\n", style="default")
        text.append("╔═══════════════════════════════════════════════════════════╗\n", style="bold magenta")
        text.append("║                                                           ║\n", style="magenta")
        text.append("║                       德州扑克终端版                       ║\n", style="bold yellow")
        text.append("║                                                           ║\n", style="magenta")
        text.append("╚═══════════════════════════════════════════════════════════╝\n", style="bold magenta")
        text.append("\n", style="default")

        console.print(text)

        console.print("[bold cyan]请选择操作:[/bold cyan]\n")
        console.print("  [1] 登录")
        console.print("  [2] 注册")
        console.print("  [3] 离线模式（本地游戏）")
        console.print("  [q] 退出\n")

        return Prompt.ask(
            "[bold yellow]请输入选项[/bold yellow]",
            choices=["1", "2", "3", "q"],
            default="3"
        )

    def _do_login(self) -> LoginResult:
        """执行登录流程。"""
        console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
        console.print("[bold]用户登录[/bold]")
        console.print("[cyan]═══════════════════════════════════════════════════════════[/cyan]\n")

        username = Prompt.ask("[bold]用户名[/bold]")
        password = Prompt.ask("[bold]密码[/bold]", password=True)

        console.print("\n[dim]正在登录...[/dim]\n")

        result = self.api_client.login(username, password)

        if result.success and result.user:
            console.print(f"\n[green]✓ 登录成功！欢迎 {result.user.display_name}[/green]\n")
            self.current_user = result.user
        elif result.success and not result.user:
            # 登录成功但获取用户信息失败
            console.print(f"\n[red]✗ 登录成功但获取用户信息失败[/red]\n")
            return LoginResult(success=False, error="获取用户信息失败")
        else:
            console.print(f"\n[red]✗ 登录失败：{result.error}[/red]\n")

        return result

    def _do_register(self) -> RegisterResult:
        """执行注册流程。"""
        console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
        console.print("[bold]用户注册[/bold]")
        console.print("[green]═══════════════════════════════════════════════════════════[/green]\n")

        console.print("[dim]提示：用户名和密码将用于后续登录[/dim]\n")

        username = Prompt.ask("[bold]用户名[/bold]")
        password = Prompt.ask("[bold]密码[/bold]", password=True)
        confirm_password = Prompt.ask("[bold]确认密码[/bold]", password=True)

        # 验证密码
        if password != confirm_password:
            console.print("\n[red]✗ 两次输入的密码不一致！[/red]\n")
            return RegisterResult(success=False, error="密码不匹配")

        display_name = Prompt.ask("[bold]显示名称[/bold]", default=username)

        console.print("\n[dim]正在注册...[/dim]\n")

        result = self.api_client.register(username, password, display_name)

        if result.success:
            console.print(f"\n[green]✓ 注册成功！[/green]\n")
        else:
            console.print(f"\n[red]✗ 注册失败：{result.error}[/red]\n")

        return result


def prompt_login() -> Tuple[Optional[str], Optional[str]]:
    """
    简单的登录提示。

    Returns:
        (username, password) 元组，取消则返回 (None, None)
    """
    console.print("\n[bold cyan]═══════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold]用户登录[/bold]")
    console.print("[cyan]═══════════════════════════════════════════════════════════[/cyan]\n")

    choice = Prompt.ask(
        "[bold]选择登录方式[/bold]",
        choices=["1", "2", "3"],
        default="1",
        show_choices=False
    )
    console.print(
        "  [1] 账号密码登录\n"
        "  [2] 快速登录（离线模式）\n"
        "  [3] 返回\n"
    )

    if choice == "1":
        username = Prompt.ask("[bold]用户名[/bold]")
        password = Prompt.ask("[bold]密码[/bold]", password=True)
        return username, password
    elif choice == "2":
        return "player", "offline"
    else:
        return None, None


def prompt_register() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    注册提示。

    Returns:
        (username, password, display_name) 元组，取消则返回 (None, None, None)
    """
    console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold]用户注册[/bold]")
    console.print("[green]═══════════════════════════════════════════════════════════[/green]\n")

    username = Prompt.ask("[bold]用户名[/bold]")
    if not username:
        return None, None, None

    password = Prompt.ask("[bold]密码[/bold]", password=True)
    confirm_password = Prompt.ask("[bold]确认密码[/bold]", password=True)

    if password != confirm_password:
        console.print("\n[red]✗ 两次输入的密码不一致！[/red]\n")
        return None, None, None

    display_name = Prompt.ask("[bold]显示名称[/bold]", default=username)

    return username, password, display_name


def display_login_success(user: User):
    """显示登录成功信息。"""
    console.print(f"\n[green]╔═══════════════════════════════════════════════════════════╗[/green]")
    console.print(f"[green]║[/green]  [bold]登录成功！[/bold]                                    [green]║[/green]")
    console.print(f"[green]╠═══════════════════════════════════════════════════════════╣[/green]")
    console.print(f"[green]║[/green]  欢迎，[yellow]{user.display_name}[/yellow]！                               [green]║[/green]")
    console.print(f"[green]║[/green]  用户名：[cyan]{user.username}[/cyan]                                      [green]║[/green]")
    console.print(f"[green]║[/green]  筹码：[green]${user.chips}[/green]                                         [green]║[/green]")
    console.print(f"[green]╚═══════════════════════════════════════════════════════════╝[/green]\n")


def display_auth_error(error: str):
    """显示认证错误信息。"""
    console.print(f"\n[red]╔═══════════════════════════════════════════════════════════╗[/red]")
    console.print(f"[red]║[/red]  [bold]认证失败[/bold]                                        [red]║[/red]")
    console.print(f"[red]╠═══════════════════════════════════════════════════════════╣[/red]")
    console.print(f"[red]║[/red]  {error}                                       [red]║[/red]")
    console.print(f"[red]╚═══════════════════════════════════════════════════════════╝[/red]\n")
