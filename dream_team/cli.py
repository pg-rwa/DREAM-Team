"""DREAM Team CLI - The single interface to manage your AI agent team."""

import asyncio
import json
import os
import readline
import sys
from typing import Optional

from .config.settings import DreamTeamConfig, ProjectConfig
from .team import DreamTeam
from .ui.dashboard import DreamTeamDashboard, Colors


def print_error(msg: str) -> None:
    print(f"\n{Colors.RED}  Error: {msg}{Colors.RESET}\n")


def print_success(msg: str) -> None:
    print(f"\n{Colors.GREEN}  {msg}{Colors.RESET}\n")


def print_info(msg: str) -> None:
    print(f"\n{Colors.CYAN}  {msg}{Colors.RESET}\n")


class DreamTeamCLI:
    """Interactive CLI for the DREAM Team."""

    def __init__(self):
        self.config = DreamTeamConfig.load()
        self.team = DreamTeam(self.config)
        self.dashboard = DreamTeamDashboard(self.team)
        self.running = True

    async def run(self) -> None:
        """Main event loop."""
        # Show welcome dashboard
        print(self.dashboard.render_full_dashboard())

        # Check first-time setup
        if not self.config.projects:
            print_info(
                "Welcome to DREAM Team! Start by adding your projects:\n"
                "    add <github_repo_url> [--name <name>] [--desc <description>]"
            )

        # Main REPL
        while self.running:
            try:
                prompt = f"{Colors.BOLD}{Colors.CYAN}DREAM>{Colors.RESET} "
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                await self.handle_command(user_input)

            except (KeyboardInterrupt, EOFError):
                print("\n")
                self.running = False
            except Exception as e:
                print_error(str(e))

        print_info("DREAM Team signing off. See you next time!")

    async def handle_command(self, raw_input: str) -> None:
        """Parse and execute a command."""
        parts = raw_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        handlers = {
            "talk": self.cmd_talk,
            "t": self.cmd_talk,
            "add": self.cmd_add_project,
            "remove": self.cmd_remove_project,
            "projects": self.cmd_list_projects,
            "team": self.cmd_team_overview,
            "tasks": self.cmd_tasks,
            "assign": self.cmd_assign_task,
            "status": self.cmd_project_status,
            "review": self.cmd_review_project,
            "work": self.cmd_work,
            "dashboard": self.cmd_dashboard,
            "dash": self.cmd_dashboard,
            "d": self.cmd_dashboard,
            "help": self.cmd_help,
            "h": self.cmd_help,
            "config": self.cmd_config,
            "quit": self.cmd_quit,
            "exit": self.cmd_quit,
            "q": self.cmd_quit,
        }

        handler = handlers.get(command)
        if handler:
            await handler(args)
        else:
            # If it doesn't match a command, treat it as talking to the CTO
            await self.cmd_talk(raw_input)

    async def cmd_talk(self, message: str) -> None:
        """Talk to the CTO agent."""
        if not message:
            print_error("Please provide a message. Usage: talk <message>")
            return

        print_info("CTO is thinking...")
        response = await self.team.delegate_to_cto(message)
        print(f"\n{Colors.YELLOW}  CTO:{Colors.RESET}")
        for line in response.split("\n"):
            print(f"  {line}")
        print()

        # Check if CTO wants to delegate tasks
        await self._maybe_process_delegation(response)

    async def _maybe_process_delegation(self, cto_response: str) -> None:
        """Check if CTO response contains delegation instructions and offer to execute."""
        try:
            # Try to extract JSON from the response
            json_start = cto_response.find("{")
            json_end = cto_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                plan = json.loads(cto_response[json_start:json_end])
                tasks = plan.get("tasks", [])
                if tasks:
                    print(f"  {Colors.CYAN}CTO has {len(tasks)} task(s) to delegate.{Colors.RESET}")
                    confirm = input(f"  {Colors.BOLD}Execute these tasks? (y/n): {Colors.RESET}").strip().lower()
                    if confirm in ("y", "yes"):
                        for task_info in tasks:
                            project = task_info.get("project", "")
                            description = task_info.get("description", task_info.get("title", ""))
                            agent = self.team.get_agent_for_project(project)
                            if agent:
                                print_info(f"Delegating to {agent.name}: {description[:60]}...")
                                result = await self.team.execute_task_on_project(project, description)
                                print(f"\n  {Colors.GREEN}Result from {agent.name}:{Colors.RESET}")
                                for line in result.split("\n")[:20]:
                                    print(f"  {line}")
                                print()
                            else:
                                print_error(f"No agent found for project '{project}'")
        except (json.JSONDecodeError, ValueError):
            pass  # Not a delegation response, that's fine

    async def cmd_add_project(self, args: str) -> None:
        """Add a new project. Usage: add <repo_url> [--name name] [--desc description]"""
        if not args:
            print_error("Usage: add <repo_url> [--name <name>] [--desc <description>]")
            return

        parts = args.split()
        repo_url = parts[0]

        # Parse optional flags
        name = ""
        description = ""
        tech_stack = []
        branch = "main"

        i = 1
        while i < len(parts):
            if parts[i] == "--name" and i + 1 < len(parts):
                name = parts[i + 1]
                i += 2
            elif parts[i] == "--desc" and i + 1 < len(parts):
                # Collect rest as description
                description = " ".join(parts[i + 1:])
                break
            elif parts[i] == "--stack" and i + 1 < len(parts):
                tech_stack = parts[i + 1].split(",")
                i += 2
            elif parts[i] == "--branch" and i + 1 < len(parts):
                branch = parts[i + 1]
                i += 2
            else:
                i += 1

        # Derive name from URL if not provided
        if not name:
            name = repo_url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]

        print_info(f"Adding project '{name}' from {repo_url}...")

        try:
            agent = await self.team.add_project(
                name=name,
                repo_url=repo_url,
                description=description,
                tech_stack=tech_stack,
                branch=branch,
            )
            print_success(
                f"Project '{name}' added! Agent '{agent.name}' "
                f"(ID: {agent.agent_id}) is now on the team."
            )
        except Exception as e:
            print_error(f"Failed to add project: {e}")

    async def cmd_remove_project(self, name: str) -> None:
        """Remove a project."""
        if not name:
            print_error("Usage: remove <project_name>")
            return

        self.team.remove_project(name.strip())
        print_success(f"Project '{name}' removed.")

    async def cmd_list_projects(self, _: str) -> None:
        """List all projects."""
        print(self.dashboard.render_projects())

    async def cmd_team_overview(self, _: str) -> None:
        """Show team overview."""
        print(self.dashboard.render_team_overview())

    async def cmd_tasks(self, _: str) -> None:
        """Show task board."""
        print(self.dashboard.render_tasks(limit=20))

    async def cmd_assign_task(self, args: str) -> None:
        """Assign a task. Usage: assign <project> <task description>"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print_error("Usage: assign <project_name> <task description>")
            return

        project_name = parts[0]
        task_desc = parts[1]

        agent = self.team.get_agent_for_project(project_name)
        if not agent:
            print_error(f"No agent for project '{project_name}'. Available: "
                       + ", ".join(a.repo_name for a in self.team.agents.values()))
            return

        task = self.team.task_manager.create_task(
            title=task_desc[:80],
            description=task_desc,
            project=project_name,
            assigned_agent_id=agent.agent_id,
        )
        print_success(f"Task '{task.task_id}' created and assigned to {agent.name}.")

    async def cmd_project_status(self, project_name: str) -> None:
        """Get project status."""
        project_name = project_name.strip()
        if not project_name:
            # Show all
            for agent in self.team.agents.values():
                print_info(f"Getting status for {agent.repo_name}...")
                status = await agent.get_project_status()
                print(f"\n  {Colors.BOLD}{agent.repo_name}:{Colors.RESET}")
                for line in status.split("\n"):
                    print(f"  {line}")
                print()
            return

        agent = self.team.get_agent_for_project(project_name)
        if not agent:
            print_error(f"No agent for project '{project_name}'")
            return

        print_info(f"Getting status for {project_name}...")
        status = await agent.get_project_status()
        print(f"\n{status}\n")

    async def cmd_review_project(self, project_name: str) -> None:
        """Have an agent review a project's codebase."""
        project_name = project_name.strip()
        if not project_name:
            print_error("Usage: review <project_name>")
            return

        agent = self.team.get_agent_for_project(project_name)
        if not agent:
            print_error(f"No agent for project '{project_name}'")
            return

        print_info(f"{agent.name} is reviewing {project_name}...")
        review = await agent.review_codebase()
        print(f"\n{review}\n")

    async def cmd_work(self, args: str) -> None:
        """Have an agent execute a task. Usage: work <project> <task>"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print_error("Usage: work <project_name> <task description>")
            return

        project_name = parts[0]
        task_desc = parts[1]

        agent = self.team.get_agent_for_project(project_name)
        if not agent:
            print_error(f"No agent for project '{project_name}'")
            return

        print_info(f"{agent.name} is working on: {task_desc[:60]}...")
        result = await self.team.execute_task_on_project(project_name, task_desc)
        print(f"\n  {Colors.GREEN}Result:{Colors.RESET}")
        for line in result.split("\n"):
            print(f"  {line}")
        print()

    async def cmd_dashboard(self, _: str) -> None:
        """Refresh dashboard."""
        print(self.dashboard.render_full_dashboard())

    async def cmd_help(self, _: str) -> None:
        """Show help."""
        print(self.dashboard.render_commands())

    async def cmd_config(self, args: str) -> None:
        """View or set config. Usage: config [key value]"""
        if not args:
            print(f"\n  {Colors.BOLD}Current Configuration:{Colors.RESET}")
            print(f"  Team name: {self.config.team_name}")
            print(f"  CTO name: {self.config.cto_name}")
            print(f"  GitHub user: {self.config.github_username or '(not set)'}")
            print(f"  Workspace: {self.config.workspace_dir}")
            print(f"  Projects: {len(self.config.projects)}")
            print()
            return

        parts = args.split(maxsplit=1)
        if len(parts) == 2:
            key, value = parts
            if key == "github_username":
                self.config.github_username = value
            elif key == "team_name":
                self.config.team_name = value
            elif key == "cto_name":
                self.config.cto_name = value
                self.team.cto.name = value
            else:
                print_error(f"Unknown config key: {key}")
                return
            self.config.save()
            print_success(f"Set {key} = {value}")

    async def cmd_quit(self, _: str) -> None:
        """Exit."""
        self.running = False


def main():
    """Entry point for the DREAM Team CLI."""
    cli = DreamTeamCLI()
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        print(f"\n{Colors.CYAN}  DREAM Team signing off.{Colors.RESET}\n")


if __name__ == "__main__":
    main()
