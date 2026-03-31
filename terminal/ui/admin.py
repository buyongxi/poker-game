"""
管理员界面模块 - 用户管理功能
"""

from rich.prompt import Prompt, Confirm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.box import DOUBLE
from typing import Optional, Dict, List, Any

from api_client import SyncAPIClient, User


console = Console()


class AdminManager:
    """
    管理员管理器 - 处理用户管理功能。
    """

    def __init__(self, api_client: SyncAPIClient, current_user: User):
        self.api_client = api_client
        self.current_user = current_user

    def run(self):
        """运行管理员界面。"""
        while True:
            choice = self._show_admin_menu()

            if choice == "1":
                # 待审核用户
                self._manage_pending_users()
            elif choice == "2":
                # 所有用户
                self._manage_all_users()
            elif choice == "q":
                # 返回
                break

    def _show_admin_menu(self) -> str:
        """显示管理员菜单。"""
        console.clear()

        text = Text()
        text.append("\n", style="default")
        text.append("╔═══════════════════════════════════════════════════════════╗\n", style="bold magenta")
        text.append("║                                                           ║\n", style="magenta")
        text.append("║              🔧  管理员后台  🔧                           ║\n", style="bold yellow")
        text.append("║                                                           ║\n", style="magenta")
        text.append("╚═══════════════════════════════════════════════════════════╝\n", style="bold magenta")
        text.append("\n", style="default")

        console.print(text)

        # 管理员信息
        console.print(f"  当前管理员：[yellow]{self.current_user.display_name}[/yellow]  |  角色：[bold magenta]管理员[/bold magenta]\n")

        # 菜单
        console.print("[bold cyan]请选择操作:[/bold cyan]\n")
        console.print("  [1] 待审核用户管理")
        console.print("  [2] 所有用户管理")
        console.print("  [q] 返回大厅\n")

        return Prompt.ask(
            "[bold yellow]请输入选项[/bold yellow]",
            choices=["1", "2", "q"],
            default="q"
        )

    def _manage_pending_users(self):
        """管理待审核用户。"""
        console.print("\n[dim]正在获取待审核用户列表...[/dim]\n")

        pending_users = self.api_client.get_pending_users()

        if not pending_users:
            console.print("\n[yellow]当前没有待审核的用户。[/yellow]\n")
            Prompt.ask("按回车键返回")
            return

        # 显示待审核用户表格
        table = Table(title="待审核用户", box=DOUBLE, expand=True)
        table.add_column("ID", style="dim", width=6, justify="right")
        table.add_column("用户名", style="bold", width=15)
        table.add_column("显示名称", width=15)
        table.add_column("注册时间", width=20)
        table.add_column("操作", width=15, justify="center")

        for user in pending_users:
            table.add_row(
                str(user["id"]),
                user["username"],
                user.get("display_name", "-"),
                user.get("created_at", "未知")[:19].replace("T", " "),
                ""
            )

        console.print(table)

        # 选择用户进行操作
        console.print("\n[bold cyan]请选择操作:[/bold cyan]\n")
        console.print("  [1] 激活用户")
        console.print("  [2] 拒绝用户")
        console.print("  [q] 返回\n")

        choice = Prompt.ask(
            "[bold yellow]请输入选项[/bold yellow]",
            choices=["1", "2", "q"],
            default="q"
        )

        if choice == "q":
            return

        user_id = Prompt.ask("[bold]请输入用户 ID[/bold]")

        if choice == "1":
            if self.api_client.activate_user(int(user_id)):
                console.print(f"\n[green]✓ 用户 {user_id} 已激活[/green]\n")
            else:
                console.print(f"\n[red]✗ 激活用户 {user_id} 失败[/red]\n")
        elif choice == "2":
            if self.api_client.disable_user(int(user_id)):
                console.print(f"\n[green]✓ 用户 {user_id} 已拒绝[/green]\n")
            else:
                console.print(f"\n[red]✗ 拒绝用户 {user_id} 失败[/red]\n")

        Prompt.ask("按回车键继续")

    def _manage_all_users(self):
        """管理所有用户。"""
        console.print("\n[dim]正在获取用户列表...[/dim]\n")

        all_users = self.api_client.get_all_users()

        if not all_users:
            console.print("\n[yellow]当前没有其他用户。[/yellow]\n")
            Prompt.ask("按回车键返回")
            return

        # 显示用户表格
        table = Table(title="所有用户", box=DOUBLE, expand=True)
        table.add_column("ID", style="dim", width=6, justify="right")
        table.add_column("用户名", style="bold", width=15)
        table.add_column("显示名称", width=15)
        table.add_column("状态", width=10, justify="center")
        table.add_column("角色", width=10, justify="center")
        table.add_column("注册时间", width=20)

        for user in all_users:
            # 状态样式
            status = user.get("status", "unknown")
            if status == "active":
                status_style = "green"
                status_text = "正常"
            elif status == "pending":
                status_style = "yellow"
                status_text = "待审核"
            elif status == "disabled":
                status_style = "red"
                status_text = "已禁用"
            else:
                status_style = "dim"
                status_text = status

            # 角色样式
            role = user.get("role", "user")
            role_style = "magenta" if role == "admin" else "cyan"
            role_text = "管理员" if role == "admin" else "用户"

            table.add_row(
                str(user["id"]),
                user["username"],
                user.get("display_name", "-"),
                f"[{status_style}]{status_text}[/{status_style}]",
                f"[{role_style}]{role_text}[/{role_style}]",
                user.get("created_at", "未知")[:19].replace("T", " ")
            )

        console.print(table)

        # 选择用户进行操作
        console.print("\n[bold cyan]请选择操作:[/bold cyan]\n")
        console.print("  [1] 启用用户")
        console.print("  [2] 禁用用户")
        console.print("  [3] 设为管理员")
        console.print("  [4] 取消管理员")
        console.print("  [q] 返回\n")

        choice = Prompt.ask(
            "[bold yellow]请输入选项[/bold yellow]",
            choices=["1", "2", "3", "4", "q"],
            default="q"
        )

        if choice == "q":
            return

        user_id = Prompt.ask("[bold]请输入用户 ID[/bold]")

        if choice == "1":
            if self.api_client.enable_user(int(user_id)):
                console.print(f"\n[green]✓ 用户 {user_id} 已启用[/green]\n")
            else:
                console.print(f"\n[red]✗ 启用用户 {user_id} 失败[/red]\n")
        elif choice == "2":
            if self.api_client.disable_user(int(user_id)):
                console.print(f"\n[green]✓ 用户 {user_id} 已禁用[/green]\n")
            else:
                console.print(f"\n[red]✗ 禁用用户 {user_id} 失败[/red]\n")
        elif choice == "3":
            if self.api_client.set_admin(int(user_id), True):
                console.print(f"\n[green]✓ 用户 {user_id} 已设为管理员[/green]\n")
            else:
                console.print(f"\n[red]✗ 设置用户 {user_id} 为管理员失败[/red]\n")
        elif choice == "4":
            if self.api_client.set_admin(int(user_id), False):
                console.print(f"\n[green]✓ 用户 {user_id} 已取消管理员[/green]\n")
            else:
                console.print(f"\n[red]✗ 取消用户 {user_id} 管理员失败[/red]\n")

        Prompt.ask("按回车键继续")


def show_admin_entry():
    """显示管理员入口提示。"""
    console.print("\n[bold magenta]╔═══════════════════════════════════════════════════════════╗[/bold magenta]")
    console.print("[bold magenta]║[/bold magenta]  [yellow]⚙ 管理员入口：输入 'admin' 进入管理后台[/yellow]                    [bold magenta]║[/bold magenta]")
    console.print("[bold magenta]╚═══════════════════════════════════════════════════════════╝[/bold magenta]\n")
