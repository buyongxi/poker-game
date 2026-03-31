"""User input handling for terminal poker game."""

from rich.prompt import Prompt, IntPrompt, Confirm
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from typing import Dict, List, Optional, Any
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from app.game.engine import ActionType


console = Console()


def get_player_action(valid_actions: List[Dict], player_name: str = "你") -> Dict[str, Any]:
    """
    获取玩家输入的操作。

    Args:
        valid_actions: 有效操作列表
        player_name: 玩家名称

    Returns:
        包含 action 和 amount 的字典
    """
    # 显示可用操作
    console.print("\n[bold cyan]═ 可用操作 ═══════════════════════════════════════════════════[/bold cyan]")

    action_map = {}
    for i, action in enumerate(valid_actions, 1):
        action_type = action['action']
        if action_type == ActionType.RAISE:
            desc = f"[yellow]加注[/yellow] ${action['min_amount']} - ${action['max_amount']}"
        elif action_type == ActionType.ALL_IN:
            desc = f"[bold red]全押[/bold red] ${action['amount']}"
        elif action_type == ActionType.CALL:
            desc = f"[blue]跟注[/blue] ${action['amount']}"
        elif action_type == ActionType.CHECK:
            desc = f"[green]过牌[/green]"
        elif action_type == ActionType.FOLD:
            desc = f"[dim]弃牌[/dim]"
        else:
            desc = action_type.value

        action_map[str(i)] = action
        console.print(f"  [{i}] {desc}")

    console.print("[cyan]════════════════════════════════════════════════════════════════[/cyan]\n")

    while True:
        choice = Prompt.ask(
            "[bold yellow]请选择操作[/bold yellow]",
            choices=[str(i) for i in range(1, len(valid_actions) + 1)],
            default="1",
            show_choices=False
        )

        selected_action = action_map[choice]
        action_type = selected_action['action']

        # 处理加注金额
        if action_type == ActionType.RAISE:
            min_amt = selected_action['min_amount']
            max_amt = selected_action['max_amount']

            # 显示预设选项
            console.print(f"\n[cyan]加注预设：[/cyan] ", end="")
            presets = [
                min_amt,
                int((min_amt + max_amt) / 2),
                max_amt
            ]
            for j, p in enumerate(presets, 1):
                console.print(f"[{j}] ${p}  ", end="")
            console.print("[4] 自定义", end="")
            console.print()

            preset_choice = Prompt.ask(
                "选择预设",
                choices=["1", "2", "3", "4"],
                default="1",
                show_choices=False
            )

            if preset_choice == "4":
                amount = IntPrompt.ask(
                    f"输入加注金额 ({min_amt}-{max_amt})",
                    default=min_amt
                )
                amount = max(min_amt, min(amount, max_amt))  # 限制在范围内
            else:
                amount = presets[int(preset_choice) - 1]

            return {"action": action_type, "amount": amount}

        elif action_type == ActionType.ALL_IN:
            # 确认全押
            if Confirm.ask(f"[bold red]确认全押 ${selected_action['amount']}?[/bold red]", default=True):
                return {"action": action_type, "amount": selected_action['amount']}
            else:
                # 如果取消，重新选择
                continue

        else:
            return {"action": action_type, "amount": selected_action.get('amount', 0)}


def prompt_num_players() -> int:
    """提示输入玩家数量。"""
    console.print("\n[bold cyan]════════════════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold]游戏设置[/bold]")
    console.print("[cyan]════════════════════════════════════════════════════════════════[/cyan]\n")

    return IntPrompt.ask(
        "[bold]请输入玩家数量[/bold]",
        choices=[str(i) for i in range(2, 11)],
        default=6,
        show_choices=False
    )


def prompt_starting_chips() -> int:
    """提示输入起始筹码。"""
    console.print("\n[bold]筹码设置[/bold]\n")

    options = [
        (500, "短码"),
        (1000, "标准"),
        (2000, "深码"),
        (5000, "豪客"),
        (10000, "超级豪客")
    ]

    for i, (chips, label) in enumerate(options, 1):
        console.print(f"  [{i}] ${chips} ({label})")

    choice = Prompt.ask(
        "\n[bold]选择起始筹码[/bold]",
        choices=[str(i) for i in range(1, len(options) + 1)],
        default="2",
        show_choices=False
    )

    return options[int(choice) - 1][0]


def confirm_start_game() -> bool:
    """确认是否开始游戏。"""
    console.print("\n[bold green]════════════════════════════════════════════════════════════════[/bold green]")
    return Confirm.ask(
        "[bold green]是否开始游戏？[/bold green]",
        default=True
    )


def prompt_continue_game() -> bool:
    """询问是否继续下一局。"""
    console.print("\n[cyan]════════════════════════════════════════════════════════════════[/cyan]")
    return Confirm.ask(
        "[bold]是否继续下一局？[/bold]",
        default=True
    )


def prompt_rebuy(current_chips: int, recommended: int = 1000) -> bool:
    """
    询问是否补充筹码。

    Args:
        current_chips: 当前筹码
        recommended: 推荐补充到的金额
    """
    console.print(f"\n[yellow]⚠ 你的筹码已不足 (${current_chips})[/yellow]")
    return Confirm.ask(
        f"[bold]是否补充筹码到 ${recommended}?[/bold]",
        default=True
    )


def prompt_exit() -> bool:
    """确认是否退出游戏。"""
    console.print("\n[bold red]════════════════════════════════════════════════════════════════[/bold red]")
    return Confirm.ask(
        "[bold red]确定要退出游戏吗？[/bold red]",
        default=False
    )


def display_waiting(message: str = "等待其他玩家..."):
    """显示等待信息（临时状态）。"""
    console.print(f"\n[dim]ℹ {message}[/dim]\n")


def prompt_blind_amount(is_sb: bool, sb_amount: int, bb_amount: int) -> str:
    """提示盲注信息（仅用于显示）。"""
    if is_sb:
        console.print(f"\n[cyan]你是小盲注，需要下注 ${sb_amount}[/cyan]")
    else:
        console.print(f"\n[blue]你是大盲注，需要下注 ${bb_amount}[/blue]")
    return "sb" if is_sb else "bb"


class ActionMenu:
    """
    行动菜单类 - 提供更美观的操作选择界面。
    """

    def __init__(self, valid_actions: List[Dict]):
        self.valid_actions = valid_actions
        self.action_map: Dict[str, Dict] = {}

    def render(self) -> str:
        """渲染菜单并返回字符串。"""
        lines = []
        lines.append("[bold cyan]╔═══════════════════════════════════════════════════════════╗[/bold cyan]")
        lines.append("[bold cyan]║[/bold cyan]                  [bold]行动菜单[/bold]                              [bold cyan]║[/bold cyan]")
        lines.append("[bold cyan]╠═══════════════════════════════════════════════════════════╣[/bold cyan]")

        for i, action in enumerate(self.valid_actions, 1):
            action_type = action['action']
            key = str(i)

            if action_type == ActionType.RAISE:
                desc = f"加注到 ${action['min_amount']} - ${action['max_amount']}"
                style = "yellow"
            elif action_type == ActionType.ALL_IN:
                desc = f"全押 ${action['amount']}"
                style = "bold red"
            elif action_type == ActionType.CALL:
                desc = f"跟注 ${action['amount']}"
                style = "blue"
            elif action_type == ActionType.CHECK:
                desc = "过牌"
                style = "green"
            elif action_type == ActionType.FOLD:
                desc = "弃牌"
                style = "dim"
            else:
                desc = action_type.value
                style = "white"

            self.action_map[key] = action
            lines.append(f"[bold cyan]║[/bold cyan]  [{key}] [{style}]{desc}[/{style}]" + " " * (50 - len(desc) - 4) + "[bold cyan]║[/bold cyan]")

        lines.append("[bold cyan]╚═══════════════════════════════════════════════════════════╝[/bold cyan]")

        return "\n".join(lines)

    def get_choice(self) -> Dict[str, Any]:
        """获取用户选择。"""
        console.print(self.render())

        while True:
            choice = Prompt.ask(
                "\n[bold yellow]请选择[/bold yellow]",
                choices=list(self.action_map.keys()),
                default="1"
            )

            selected_action = self.action_map[choice]
            action_type = selected_action['action']

            if action_type == ActionType.RAISE:
                amount = IntPrompt.ask(
                    f"加注金额 ({selected_action['min_amount']}-{selected_action['max_amount']})",
                    default=selected_action['min_amount']
                )
                return {"action": action_type, "amount": amount}
            elif action_type == ActionType.ALL_IN:
                if Confirm.ask(f"确认全押 ${selected_action['amount']}?", default=True):
                    return {"action": action_type, "amount": selected_action['amount']}
                continue
            else:
                return {"action": action_type, "amount": selected_action.get('amount', 0)}
