"""DREAM Team orchestrator - ties agents, tasks, GitHub, and config together."""

import asyncio
import json
from typing import Optional

from .agents import CTOAgent, ProjectAgent, AgentRole, AgentStatus
from .config.settings import DreamTeamConfig, ProjectConfig
from .github.integration import GitHubManager
from .tasks.manager import TaskManager, Task, TaskPriority


class DreamTeam:
    """The main orchestrator that manages the entire DREAM Team."""

    def __init__(self, config: Optional[DreamTeamConfig] = None):
        self.config = config or DreamTeamConfig.load()
        self.github = GitHubManager(self.config.workspace_dir)
        self.task_manager = TaskManager()
        self.cto = CTOAgent(name=self.config.cto_name)
        self.agents: dict[str, ProjectAgent] = {}
        self._load_agents()

    def _load_agents(self) -> None:
        """Load agent state from disk."""
        if self.config.agents_path.exists():
            try:
                data = json.loads(self.config.agents_path.read_text())
                for agent_data in data.get("agents", []):
                    agent = ProjectAgent.from_dict(agent_data)
                    self.agents[agent.agent_id] = agent
                    self.cto.register_agent(agent.agent_id, agent.repo_name)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_agents(self) -> None:
        """Persist agent state to disk."""
        data = {"agents": [a.to_dict() for a in self.agents.values()]}
        self.config.agents_path.write_text(json.dumps(data, indent=2))

    def get_team_context(self) -> str:
        """Build a context string describing the current team for the CTO."""
        if not self.agents:
            return "No project agents registered yet."

        lines = []
        for agent in self.agents.values():
            status_icon = {
                AgentStatus.IDLE: "[IDLE]",
                AgentStatus.WORKING: "[BUSY]",
                AgentStatus.ERROR: "[ERR]",
                AgentStatus.OFFLINE: "[OFF]",
            }.get(agent.status, "[?]")

            tasks = self.task_manager.get_tasks_for_agent(agent.agent_id)
            active = [t for t in tasks if t.status.value in ("pending", "in_progress")]

            lines.append(
                f"  - {agent.name} ({agent.agent_id}) {status_icon}: "
                f"{agent.repo_name} | {len(active)} active tasks"
            )

        return "\n".join(lines)

    async def add_project(
        self,
        name: str,
        repo_url: str,
        description: str = "",
        tech_stack: Optional[list[str]] = None,
        branch: str = "main",
        clone: bool = True,
    ) -> ProjectAgent:
        """Add a new project and create its agent."""
        # Create project config
        project_config = ProjectConfig(
            name=name,
            repo_url=repo_url,
            description=description,
            tech_stack=tech_stack or [],
            branch=branch,
        )

        # Clone repo if requested
        workspace = self.github.get_project_path(name)
        if clone:
            try:
                workspace = await self.github.clone_repo(repo_url, name)
            except RuntimeError as e:
                # If clone fails, still create the agent with the expected path
                pass

        # Create agent
        agent = ProjectAgent(
            name=f"Agent-{name}",
            repo_url=repo_url,
            repo_name=name,
            tech_stack=tech_stack or [],
            project_description=description,
            branch=branch,
            workspace_path=workspace,
        )

        # Register everything
        project_config.agent_name = agent.name
        self.config.add_project(project_config)
        self.agents[agent.agent_id] = agent
        self.cto.register_agent(agent.agent_id, name)
        self._save_agents()

        return agent

    def remove_project(self, name: str) -> None:
        """Remove a project and its agent."""
        agent_id = None
        for aid, agent in self.agents.items():
            if agent.repo_name == name:
                agent_id = aid
                break

        if agent_id:
            self.cto.unregister_agent(agent_id)
            del self.agents[agent_id]
            self._save_agents()

        self.config.remove_project(name)

    def get_agent_for_project(self, project_name: str) -> Optional[ProjectAgent]:
        """Find the agent assigned to a project."""
        for agent in self.agents.values():
            if agent.repo_name == project_name:
                return agent
        return None

    async def delegate_to_cto(self, message: str) -> str:
        """Send a message to the CTO for analysis and delegation."""
        team_context = self.get_team_context()
        return await self.cto.analyze_request(message, team_context)

    async def delegate_to_cto_stream(self, message: str):
        """Stream the CTO's response to a message."""
        team_context = self.get_team_context()
        async for chunk in self.cto.analyze_request_stream(message, team_context):
            yield chunk

    async def execute_task_on_project(
        self, project_name: str, task_description: str
    ) -> str:
        """Directly execute a task on a specific project's agent."""
        agent = self.get_agent_for_project(project_name)
        if not agent:
            return f"No agent found for project '{project_name}'"

        # Create task record
        task = self.task_manager.create_task(
            title=task_description[:80],
            description=task_description,
            project=project_name,
            assigned_agent_id=agent.agent_id,
        )
        self.task_manager.start_task(task.task_id)

        try:
            result = await agent.execute_task(task_description)
            self.task_manager.complete_task(task.task_id, result)
            return result
        except Exception as e:
            error = str(e)
            self.task_manager.fail_task(task.task_id, error)
            return f"Task failed: {error}"

    def get_team_status(self) -> dict:
        """Get a comprehensive status of the entire team."""
        return {
            "team_name": self.config.team_name,
            "cto": self.cto.to_dict(),
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "projects": [p.to_dict() for p in self.config.projects],
            "tasks": self.task_manager.get_summary(),
        }
