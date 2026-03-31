"""
游戏大厅模块 - 显示房间列表、创建/加入房间
"""

from rich.prompt import Prompt, IntPrompt, Confirm
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typing import Optional, Dict, List, Any

from .api_client import SyncAPIClient, User


console = Console()


class LobbyManager:
    """
    大厅管理器 - 处理房间列表、创建/加入房间。
    """

    def __init__(self, api_client: SyncAPIClient, current_user: User):
        self.api_client = api_client
        self.current_user = current_user
        self.current_room: Optional[Dict] = None

    def run(self) -> Optional[Dict]:
        """
        运行大厅流程。

        Returns:
            选择的房间信息，取消则返回 None
        """
        while True:
            # 获取房间列表
            rooms = self.api_client.get_rooms()

            # 显示大厅
            choice = self._show_lobby(rooms)

            if choice == "1":
                # 创建房间
                room = self._create_room()
                if room:
                    self.current_room = room
                    return room
            elif choice == "2":
                # 加入房间
                if rooms:
                    room = self._join_room(rooms)
                    if room:
                        self.current_room = room
                        return room
                else:
                    console.print("\n[yellow]当前没有可用的房间，请先创建房间。[/yellow]\n")
            elif choice == "3":
                # 刷新
                continue
            elif choice == "q":
                return None

    def _show_lobby(self, rooms: List[Dict]) -> str:
        """显示大厅和房间列表。"""
        console.clear()

        # 标题
        text = Text()
        text.append("\n", style="default")
        text.append("╔═══════════════════════════════════════════════════════════╗\n", style="bold cyan")
        text.append("║                                                           ║\n", style="cyan")
        text.append("║                    🎮 游戏大厅                             ║\n", style="bold yellow")
        text.append("║                                                           ║\n", style="cyan")
        text.append("╚═══════════════════════════════════════════════════════════╝\n", style="bold cyan")
        text.append("\n", style="default")

        console.print(text)

        # 用户信息
        console.print(f"  当前用户：[yellow]{self.current_user.display_name}[/yellow]  |  筹码：[green]${self.current_user.chips}[/green]\n")

        # 房间表格
        if rooms:
            table = Table(title="可用房间", box="DOUBLE", expand=True)
            table.add_column("ID", style="dim", width=6, justify="right")
            table.add_column("房间名称", style="bold", width=20)
            table.add_column("盲注", width=10, justify="right")
            table.add_column("买入", width=10, justify="right")
            table.add_column("玩家", width=10, justify="center")
            table.add_column("状态", width=10, justify="center")

            for room in rooms:
                status_style = "green" if room.get("status") == "waiting" else "yellow"
                status_text = "等待中" if room.get("status") == "waiting" else "游戏中"

                player_count = len(room.get("seats", []))
                max_seats = room.get("max_seats", 9)
                player_str = f"{player_count}/{max_seats}"

                table.add_row(
                    str(room["id"]),
                    room["name"],
                    f"{room['small_blind']}/{room['big_blind']}",
                    str(room.get("max_buyin", 2000)),
                    player_str,
                    f"[{status_style}]{status_text}[/{status_style}]"
                )

            console.print(table)
        else:
            console.print("  [dim]当前没有可用的房间[/dim]\n")

        # 菜单
        console.print("\n[bold cyan]请选择操作:[/bold cyan]\n")
        console.print("  [1] 创建房间")
        console.print("  [2] 加入房间" if rooms else "  [2] 加入房间 [dim](暂无房间)[/dim]")
        console.print("  [3] 刷新列表")
        console.print("  [q] 返回\n")

        return Prompt.ask(
            "[bold yellow]请输入选项[/bold yellow]",
            choices=["1", "2", "3", "q"],
            default="1"
        )

    def _create_room(self) -> Optional[Dict]:
        """创建房间。"""
        console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
        console.print("[bold]创建房间[/bold]")
        console.print("[green]═══════════════════════════════════════════════════════════[/green]\n")

        # 房间名称
        name = Prompt.ask("[bold]房间名称[/bold]", default=f"{self.current_user.display_name}的房间")

        # 玩家数量
        max_seats = IntPrompt.ask(
            "[bold]最大玩家数[/bold]",
            choices=[str(i) for i in range(2, 11)],
            default=9
        )

        # 盲注设置
        console.print("\n[bold]盲注设置:[/bold]")
        console.print("  [1] 标准 (10/20)")
        console.print("  [2] 高注 (50/100)")
        console.print("  [3] 定制\n")

        blind_choice = Prompt.ask("选择盲注级别", choices=["1", "2", "3"], default="1")

        if blind_choice == "1":
            small_blind = 10
            big_blind = 20
        elif blind_choice == "2":
            small_blind = 50
            big_blind = 100
        else:
            small_blind = IntPrompt.ask("[bold]小盲注[/bold]", default=10)
            big_blind = IntPrompt.ask("[bold]大盲注[/bold]", default=20)

        # 最大买入
        max_buyin = IntPrompt.ask(
            "[bold]最大买入[/bold]",
            default=2000
        )

        console.print("\n[dim]正在创建房间...[/dim]\n")

        room = self.api_client.create_room(
            name=name,
            max_seats=max_seats,
            small_blind=small_blind,
            big_blind=big_blind,
            max_buyin=max_buyin
        )

        if room:
            console.print(f"\n[green]✓ 房间创建成功！[/green]\n")
            console.print(f"  房间名称：[yellow]{room['name']}[/yellow]")
            console.print(f"  房间 ID: [cyan]#{room['id']}[/cyan]")
            console.print(f"  盲注：[green]{room['small_blind']}/{room['big_blind']}[/green]\n")
            return room
        else:
            console.print("\n[red]✗ 房间创建失败[/red]\n")
            return None

    def _join_room(self, rooms: List[Dict]) -> Optional[Dict]:
        """加入房间。"""
        console.print("\n[bold blue]═══════════════════════════════════════════════════════════[/bold blue]")
        console.print("[bold]加入房间[/bold]")
        console.print("[blue]═══════════════════════════════════════════════════════════[/blue]\n")

        # 显示房间选项
        for i, room in enumerate(rooms, 1):
            status = "等待中" if room.get("status") == "waiting" else "游戏中"
            player_count = len(room.get("seats", []))
            max_seats = room.get("max_seats", 9)
            console.print(f"  [{i}] {room['name']} - 盲注 {room['small_blind']}/{room['big_blind']} - 玩家：{player_count}/{max_seats} - [{status}]")

        console.print("  [q] 返回\n")

        choice = Prompt.ask(
            "[bold yellow]请选择房间[/bold yellow]",
            choices=[str(i) for i in range(1, len(rooms) + 1)] + ["q"],
            default="1"
        )

        if choice == "q":
            return None

        selected_room = rooms[int(choice) - 1]

        # 选择座位
        seat_index = IntPrompt.ask(
            "[bold]选择座位号[/bold]",
            default=1
        ) - 1  # 转换为 0-based 索引

        console.print("\n[dim]正在加入房间...[/dim]\n")

        result = self.api_client.join_room(selected_room["id"], seat_index)

        if result:
            console.print(f"\n[green]✓ 加入房间成功！[/green]\n")
            return selected_room
        else:
            console.print("\n[red]✗ 加入房间失败[/red]\n")
            return None


def show_room_list(rooms: List[Dict]):
    """显示房间列表。"""
    if not rooms:
        console.print("\n[dim]当前没有可用的房间[/dim]\n")
        return

    table = Table(title="可用房间", box="ROUNDED", expand=True)
    table.add_column("ID", style="dim", width=6)
    table.add_column("房间名称", style="bold", width=20)
    table.add_column("盲注", width=10)
    table.add_column("玩家", width=8)
    table.add_column("状态", width=10)

    for room in rooms:
        status_style = "green" if room.get("status") == "waiting" else "yellow"
        status_text = "等待中" if room.get("status") == "waiting" else "游戏中"
        player_count = len(room.get("seats", []))
        max_seats = room.get("max_seats", 9)

        table.add_row(
            str(room["id"]),
            room["name"],
            f"{room['small_blind']}/{room['big_blind']}",
            f"{player_count}/{max_seats}",
            f"[{status_style}]{status_text}[/{status_style}]"
        )

    console.print(table)


def prompt_create_room() -> Optional[Dict[str, Any]]:
    """提示创建房间信息。"""
    console.print("\n[bold green]═══════════════════════════════════════════════════════════[/bold green]")
    console.print("[bold]创建房间[/bold]")
    console.print("[green]═══════════════════════════════════════════════════════════[/green]\n")

    name = Prompt.ask("[bold]房间名称[/bold]", default="我的房间")
    max_seats = IntPrompt.ask("[bold]最大玩家数[/bold]", choices=[str(i) for i in range(2, 11)], default=9)

    console.print("\n[bold]盲注设置:[/bold]")
    console.print("  [1] 标准 (10/20)")
    console.print("  [2] 高注 (50/100)")
    console.print("  [3] 定制\n")

    blind_choice = Prompt.ask("选择盲注级别", choices=["1", "2", "3"], default="1")

    if blind_choice == "1":
        small_blind, big_blind = 10, 20
    elif blind_choice == "2":
        small_blind, big_blind = 50, 100
    else:
        small_blind = IntPrompt.ask("[bold]小盲注[/bold]", default=10)
        big_blind = IntPrompt.ask("[bold]大盲注[/bold]", default=20)

    max_buyin = IntPrompt.ask("[bold]最大买入[/bold]", default=2000)

    return {
        "name": name,
        "max_seats": max_seats,
        "small_blind": small_blind,
        "big_blind": big_blind,
        "max_buyin": max_buyin
    }
