"""DREAM Team orchestrator - ties agents, tasks, GitHub, and config together."""

import asyncio
import json
import subprocess
import time
from typing import AsyncIterator, Optional

from .agents import CTOAgent, ProjectAgent, AgentRole, AgentStatus
from .config.settings import DreamTeamConfig, ProjectConfig
from pathlib import Path

from .conversations import ConversationManager, Conversation
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
        self.conversations = ConversationManager(Path(self.config.config_dir))
        self._task_worker = None  # Set by server after init
        self._broadcast_fn = None  # Set by server after init
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
            current = agent.current_task or "none"

            lines.append(
                f"  - {agent.name} ({agent.agent_id}) {status_icon}: "
                f"project=\"{agent.repo_name}\" | {len(active)} active tasks | current: {current}"
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
        project_config = ProjectConfig(
            name=name,
            repo_url=repo_url,
            description=description,
            tech_stack=tech_stack or [],
            branch=branch,
        )

        workspace = self.github.get_project_path(name)
        if clone:
            try:
                workspace = await self.github.clone_repo(repo_url, name)
            except RuntimeError:
                pass

        agent = ProjectAgent(
            name=f"Agent-{name}",
            repo_url=repo_url,
            repo_name=name,
            tech_stack=tech_stack or [],
            project_description=description,
            branch=branch,
            workspace_path=workspace,
        )

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

    def get_task_results_context(self) -> str:
        """Build a context string of recent task results for the CTO."""
        recent = self.task_manager.get_recent_results(limit=10)
        if not recent:
            return ""

        lines = []
        for t in recent:
            status_tag = "COMPLETED" if t.status.value == "completed" else "FAILED"
            # Show more of the result so CTO has real context
            result_preview = (t.result or "")[:2000]
            if len(t.result or "") > 2000:
                result_preview += "... (truncated)"
            lines.append(
                f"- [{status_tag}] \"{t.title}\" (project: {t.project}): {result_preview}"
            )
        return "\n".join(lines)

    def get_active_progress_context(self) -> str:
        """Build a context string of in-progress tasks with live progress snapshots."""
        active = self.task_manager.get_active_tasks()
        if not active:
            return ""

        lines = []
        for t in active:
            agent = self.agents.get(t.assigned_agent_id) if t.assigned_agent_id else None
            agent_name = agent.name if agent else "unassigned"
            elapsed = ""
            if t.updated_at and t.created_at:
                try:
                    from datetime import datetime
                    started = datetime.fromisoformat(t.created_at)
                    now = datetime.now()
                    mins = int((now - started).total_seconds() / 60)
                    elapsed = f", running for {mins}m" if mins > 0 else ", just started"
                except Exception:
                    pass

            status_label = "IN PROGRESS" if t.status.value == "in_progress" else "PENDING"
            line = f"- [{status_label}] \"{t.title}\" (project: {t.project}, agent: {agent_name}{elapsed})"

            if t.progress_snapshot:
                # Show last 800 chars of progress
                snap = t.progress_snapshot[-800:] if len(t.progress_snapshot) > 800 else t.progress_snapshot
                line += f"\n  Latest output: {snap}"

            lines.append(line)
        return "\n".join(lines)

    def get_deployment_context(self) -> str:
        """Build context about the current deployment state."""
        # Check git status of each project workspace
        lines = []
        for agent in self.agents.values():
            ws = agent.workspace_path
            if not ws or not Path(ws).exists():
                lines.append(f"- {agent.repo_name}: workspace not found")
                continue
            try:
                head = subprocess.check_output(
                    ["git", "log", "-1", "--format=%h %s (%ar)"],
                    cwd=ws, text=True, timeout=5,
                ).strip()
                branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=ws, text=True, timeout=5,
                ).strip()
                # Check for uncommitted changes
                diff = subprocess.check_output(
                    ["git", "status", "--porcelain"],
                    cwd=ws, text=True, timeout=5,
                ).strip()
                dirty = f" ({len(diff.splitlines())} uncommitted changes)" if diff else ""
                lines.append(f"- {agent.repo_name}: branch={branch}, latest={head}{dirty}")
            except Exception:
                lines.append(f"- {agent.repo_name}: unable to read git status")

        if not lines:
            return ""
        return "\n".join(lines)

    async def delegate_to_cto(self, message: str) -> str:
        """Send a message to the CTO for analysis and delegation."""
        team_context = self.get_team_context()
        return await self.cto.analyze_request(message, team_context)

    def _process_cto_tasks(self, response_text: str, conversation_id: Optional[str] = None) -> list[dict]:
        """Parse CTO response for task blocks and auto-delegate to agents."""
        tasks_data = CTOAgent.extract_tasks(response_text)
        created = []

        for td in tasks_data:
            project = td.get("project", "")
            title = td.get("title", "Untitled task")
            description = td.get("description", title)
            priority_str = td.get("priority", "medium")

            agent = self.get_agent_for_project(project)
            if not agent:
                created.append({"project": project, "title": title, "status": "no_agent"})
                continue

            try:
                priority = TaskPriority(priority_str)
            except ValueError:
                priority = TaskPriority.MEDIUM

            task = self.task_manager.create_task(
                title=title,
                description=description,
                project=project,
                priority=priority,
                assigned_agent_id=agent.agent_id,
                conversation_id=conversation_id,
            )

            # Auto-execute via worker
            if self._task_worker:
                self._task_worker.enqueue(task.task_id)

            created.append({
                "project": project,
                "title": title,
                "task_id": task.task_id,
                "status": "queued",
            })

        return created

    async def delegate_to_cto_stream(
        self, message: str, conversation_id: Optional[str] = None
    ) -> AsyncIterator[str]:
        """Stream the CTO's response, with conversation context and auto-delegation."""
        team_context = self.get_team_context()

        conv = None
        project_scope = None
        conversation_messages = None
        conversation_summaries = None

        if conversation_id:
            conv = self.conversations.get(conversation_id)
            if conv:
                project_scope = conv.project
                # Add user message to conversation
                self.conversations.add_message(conversation_id, "user", message)
                # Get formatted messages for multi-turn
                conversation_messages = conv.get_anthropic_messages()
                # Get cross-conversation context
                conversation_summaries = self.conversations.get_cross_context(
                    exclude_conv_id=conversation_id
                )

        task_results = self.get_task_results_context()
        active_progress = self.get_active_progress_context()
        deployment_status = self.get_deployment_context()

        full_response = []
        async for chunk in self.cto.analyze_request_stream(
            message, team_context, project_scope, conversation_messages,
            conversation_summaries, task_results, active_progress, deployment_status,
            model_config=self.config.models,
        ):
            full_response.append(chunk)
            yield chunk

        response_text = "".join(full_response)

        # Save CTO response to conversation
        if conv:
            self.conversations.add_message(conversation_id, "cto", response_text)

        # Parse and auto-delegate tasks from CTO response
        created_tasks = self._process_cto_tasks(response_text, conversation_id)
        if created_tasks:
            # Stream a system note about delegated tasks
            queued = [t for t in created_tasks if t["status"] == "queued"]
            failed = [t for t in created_tasks if t["status"] == "no_agent"]
            parts = []
            if queued:
                names = ", ".join(f'"{t["title"]}"' for t in queued)
                parts.append(f"\n\n---\n**Delegated {len(queued)} task(s):** {names}")
            if failed:
                names = ", ".join(f'"{t["title"]}" (no agent for {t["project"]})' for t in failed)
                parts.append(f"\n**Could not delegate:** {names}")
            if parts:
                note = "".join(parts)
                yield note
                # Also save the delegation note
                if conv:
                    self.conversations.add_message(conversation_id, "system", note.strip())
                # Broadcast task updates
                if self._broadcast_fn:
                    for t in queued:
                        await self._broadcast_fn({
                            "type": "task_started",
                            "task": {"task_id": t["task_id"], "title": t["title"], "project": t["project"]},
                        })

    async def execute_task_on_project(
        self, project_name: str, task_description: str
    ) -> str:
        """Directly execute a task on a specific project's agent."""
        agent = self.get_agent_for_project(project_name)
        if not agent:
            return f"No agent found for project '{project_name}'"

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

    async def ensure_self_project(self) -> None:
        """Register the DREAM-Team repo itself so the CTO can self-manage."""
        if self.get_agent_for_project("DREAM-Team"):
            return  # Already registered

        # Find the repo path — either /opt/dream-team or the git root
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd="/opt/dream-team",
                capture_output=True, text=True,
            )
            repo_path = result.stdout.strip() if result.returncode == 0 else "/opt/dream-team"
        except Exception:
            repo_path = "/opt/dream-team"

        # Get the remote URL
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=repo_path,
                capture_output=True, text=True,
            )
            repo_url = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            repo_url = ""

        if not repo_url:
            return  # Can't determine repo URL, skip

        from .agents import ProjectAgent
        agent = ProjectAgent(
            name="Agent-DREAM-Team",
            repo_url=repo_url,
            repo_name="DREAM-Team",
            tech_stack=["python", "fastapi", "html", "javascript"],
            project_description="The DREAM Team platform itself - AI Agent Team Manager",
            branch="main",
            workspace_path=repo_path,
        )

        project_config = ProjectConfig(
            name="DREAM-Team",
            repo_url=repo_url,
            description="The DREAM Team platform itself",
            tech_stack=["python", "fastapi", "html", "javascript"],
            branch="main",
            agent_name=agent.name,
        )

        self.config.add_project(project_config)
        self.agents[agent.agent_id] = agent
        self.cto.register_agent(agent.agent_id, "DREAM-Team")
        self._save_agents()

    def get_team_status(self) -> dict:
        """Get a comprehensive status of the entire team."""
        return {
            "team_name": self.config.team_name,
            "cto": self.cto.to_dict(),
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "projects": [p.to_dict() for p in self.config.projects],
            "tasks": self.task_manager.get_summary(),
        }
