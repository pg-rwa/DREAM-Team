"""Rich terminal dashboard for the DREAM Team."""

import asyncio
import shutil
from datetime import datetime
from typing import Optional

from ..agents.base import AgentStatus
from ..tasks.manager import TaskStatus


# ANSI color codes for terminal output (no external deps required)
class Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


def _center(text: str, width: int) -> str:
    stripped = text
    for attr in dir(Colors):
        if not attr.startswith("_"):
            stripped = stripped.replace(getattr(Colors, attr), "")
    pad = max(0, width - len(stripped))
    left = pad // 2
    right = pad - left
    return " " * left + text + " " * right


class DreamTeamDashboard:
    """Terminal-based dashboard for monitoring and controlling the DREAM Team."""

    def __init__(self, team):
        self.team = team

    def _get_terminal_width(self) -> int:
        return shutil.get_terminal_size((80, 24)).columns

    def _box(self, title: str, content: str, color: str = Colors.CYAN) -> str:
        width = min(self._get_terminal_width() - 2, 100)
        inner = width - 2

        lines = []
        lines.append(f"{color}{'=' * width}{Colors.RESET}")
        lines.append(f"{color}|{Colors.BOLD}{_center(title, inner)}{Colors.RESET}{color}|{Colors.RESET}")
        lines.append(f"{color}{'-' * width}{Colors.RESET}")

        for line in content.split("\n"):
            # Pad line to fill box
            stripped = line
            for attr in dir(Colors):
                if not attr.startswith("_"):
                    stripped = stripped.replace(getattr(Colors, attr), "")
            pad = max(0, inner - len(stripped))
            lines.append(f"{color}|{Colors.RESET} {line}{' ' * pad}{color}|{Colors.RESET}"[:width + 50])

        lines.append(f"{color}{'=' * width}{Colors.RESET}")
        return "\n".join(lines)

    def render_header(self) -> str:
        width = min(self._get_terminal_width() - 2, 100)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        team_name = self.team.config.team_name

        header = f"""
{Colors.BOLD}{Colors.CYAN}
  ██████╗ ██████╗ ███████╗ █████╗ ███╗   ███╗
  ██╔══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║
  ██║  ██║██████╔╝█████╗  ███████║██╔████╔██║
  ██║  ██║██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║
  ██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║
  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝
{Colors.RESET}
{Colors.BOLD}  {team_name} - AI Agent Team Manager{Colors.RESET}
{Colors.DIM}  Powered by Claude Code  |  {now}{Colors.RESET}
"""
        return header

    def render_team_overview(self) -> str:
        agents = self.team.agents
        cto = self.team.cto

        lines = []
        # CTO
        lines.append(
            f"  {Colors.YELLOW}★{Colors.RESET} {Colors.BOLD}{cto.name}{Colors.RESET} "
            f"({cto.role.value}) "
            f"[{self._status_badge(cto.status)}] "
            f"Managing {len(agents)} agents"
        )
        lines.append("")

        if not agents:
            lines.append(f"  {Colors.DIM}No project agents yet. Add projects to get started.{Colors.RESET}")
        else:
            for agent in agents.values():
                tasks = self.team.task_manager.get_tasks_for_agent(agent.agent_id)
                active = len([t for t in tasks if t.status.value in ("pending", "in_progress")])
                done = len([t for t in tasks if t.status == TaskStatus.COMPLETED])

                lines.append(
                    f"  {Colors.BLUE}●{Colors.RESET} {Colors.BOLD}{agent.name}{Colors.RESET} "
                    f"[{self._status_badge(agent.status)}]"
                )
                lines.append(
                    f"    Repo: {Colors.DIM}{agent.repo_name}{Colors.RESET} "
                    f"| Tasks: {active} active, {done} done"
                )
                if agent.current_task:
                    lines.append(f"    Working on: {agent.current_task[:60]}")
                lines.append("")

        return self._box("TEAM OVERVIEW", "\n".join(lines), Colors.CYAN)

    def render_projects(self) -> str:
        projects = self.team.config.projects
        lines = []

        if not projects:
            lines.append(f"  {Colors.DIM}No projects configured.{Colors.RESET}")
        else:
            for i, proj in enumerate(projects, 1):
                stack = ", ".join(proj.tech_stack) if proj.tech_stack else "N/A"
                lines.append(
                    f"  {Colors.GREEN}{i}.{Colors.RESET} {Colors.BOLD}{proj.name}{Colors.RESET}"
                )
                lines.append(f"     {Colors.DIM}{proj.repo_url}{Colors.RESET}")
                lines.append(f"     Stack: {stack} | Branch: {proj.branch}")
                if proj.description:
                    lines.append(f"     {proj.description[:80]}")
                lines.append("")

        return self._box("PROJECTS", "\n".join(lines), Colors.GREEN)

    def render_tasks(self, limit: int = 10) -> str:
        tasks = self.team.task_manager.get_all_tasks()[:limit]
        lines = []

        if not tasks:
            lines.append(f"  {Colors.DIM}No tasks yet.{Colors.RESET}")
        else:
            for task in tasks:
                status_icon = {
                    TaskStatus.PENDING: f"{Colors.YELLOW}○{Colors.RESET}",
                    TaskStatus.IN_PROGRESS: f"{Colors.BLUE}◉{Colors.RESET}",
                    TaskStatus.COMPLETED: f"{Colors.GREEN}✓{Colors.RESET}",
                    TaskStatus.FAILED: f"{Colors.RED}✗{Colors.RESET}",
                    TaskStatus.BLOCKED: f"{Colors.RED}⊘{Colors.RESET}",
                }.get(task.status, "?")

                prio = {
                    "high": f"{Colors.RED}HIGH{Colors.RESET}",
                    "medium": f"{Colors.YELLOW}MED{Colors.RESET}",
                    "low": f"{Colors.DIM}LOW{Colors.RESET}",
                }.get(task.priority.value, "")

                lines.append(
                    f"  {status_icon} [{prio}] {task.title[:50]}"
                )
                lines.append(
                    f"    {Colors.DIM}Project: {task.project} | "
                    f"ID: {task.task_id}{Colors.RESET}"
                )

        summary = self.team.task_manager.get_summary()
        lines.append("")
        lines.append(
            f"  {Colors.DIM}Total: {summary['total']} | "
            + " | ".join(f"{k}: {v}" for k, v in summary["by_status"].items())
            + f"{Colors.RESET}"
        )

        return self._box("TASKS", "\n".join(lines), Colors.YELLOW)

    def render_commands(self) -> str:
        commands = [
            f"  {Colors.BOLD}talk <message>{Colors.RESET}    - Talk to the CTO (your main interface)",
            f"  {Colors.BOLD}add <repo_url>{Colors.RESET}    - Add a new project from GitHub",
            f"  {Colors.BOLD}projects{Colors.RESET}          - List all projects",
            f"  {Colors.BOLD}team{Colors.RESET}              - Show team overview",
            f"  {Colors.BOLD}tasks{Colors.RESET}             - Show task board",
            f"  {Colors.BOLD}assign <proj> <task>{Colors.RESET} - Assign a task to a project agent",
            f"  {Colors.BOLD}status <project>{Colors.RESET}  - Get project status",
            f"  {Colors.BOLD}review <project>{Colors.RESET}  - Agent reviews project codebase",
            f"  {Colors.BOLD}work <project> <task>{Colors.RESET} - Have agent execute a task",
            f"  {Colors.BOLD}dashboard{Colors.RESET}         - Refresh this dashboard",
            f"  {Colors.BOLD}help{Colors.RESET}              - Show this help",
            f"  {Colors.BOLD}quit{Colors.RESET}              - Exit DREAM Team",
        ]
        return self._box("COMMANDS", "\n".join(commands), Colors.MAGENTA)

    def render_full_dashboard(self) -> str:
        parts = [
            self.render_header(),
            self.render_team_overview(),
            "",
            self.render_projects(),
            "",
            self.render_tasks(),
            "",
            self.render_commands(),
        ]
        return "\n".join(parts)

    def _status_badge(self, status: AgentStatus) -> str:
        badges = {
            AgentStatus.IDLE: f"{Colors.GREEN}IDLE{Colors.RESET}",
            AgentStatus.WORKING: f"{Colors.YELLOW}WORKING{Colors.RESET}",
            AgentStatus.WAITING: f"{Colors.BLUE}WAITING{Colors.RESET}",
            AgentStatus.ERROR: f"{Colors.RED}ERROR{Colors.RESET}",
            AgentStatus.OFFLINE: f"{Colors.DIM}OFFLINE{Colors.RESET}",
        }
        return badges.get(status, str(status))
