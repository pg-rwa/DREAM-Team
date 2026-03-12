"""Project Agent - Handles a specific project/repo."""

import os
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from .base import Agent, AgentRole, AgentStatus


@dataclass
class ProjectAgent(Agent):
    """An agent dedicated to a specific project repository.

    Each ProjectAgent:
    - Knows its assigned GitHub repo
    - Has context about the project's tech stack and goals
    - Can execute code changes via Claude Code
    - Reports progress back to the CTO
    """

    role: AgentRole = AgentRole.PROJECT_LEAD
    repo_url: str = ""
    repo_name: str = ""
    tech_stack: list[str] = field(default_factory=list)
    project_description: str = ""
    branch: str = "main"

    def get_system_prompt(self) -> str:
        stack_str = ", ".join(self.tech_stack) if self.tech_stack else "Not specified"
        return f"""You are {self.name}, a project lead on the DREAM Team.

You are responsible for: {self.repo_name}
Repository: {self.repo_url}
Tech stack: {stack_str}
Project description: {self.project_description}
Working branch: {self.branch}
Workspace: {self.workspace_path}

Your responsibilities:
1. Implement features and fix bugs in your assigned project
2. Write clean, well-tested code
3. Follow the project's existing patterns and conventions
4. Report progress and blockers to the CTO
5. Keep the codebase healthy

When given a task, execute it thoroughly using the available tools.
Always work within your project directory."""

    async def execute_task(self, task_description: str) -> str:
        """Execute a development task on this project."""
        prompt = f"""{self.get_system_prompt()}

Task: {task_description}

Execute this task. Work within the project directory at {self.workspace_path}.
Provide a summary of what you did when complete."""

        # Use interactive mode for actual code changes
        return await self.execute_interactive(prompt, self.workspace_path)

    async def chat_stream(self, user_message: str) -> AsyncIterator[str]:
        """Stream a conversational response about this project."""
        system_prompt = self.get_system_prompt()
        async for chunk in self.stream_anthropic(system_prompt, user_message):
            yield chunk

    async def get_project_status(self) -> str:
        """Get current status of the project (git status, recent changes, etc.)."""
        prompt = f"""Check the current status of the project at {self.workspace_path}.
Report:
1. Git status (branch, uncommitted changes, recent commits)
2. Any obvious issues or TODOs
3. A brief summary of the project's current state

Be concise."""
        return await self.execute_claude_code(prompt, self.workspace_path)

    async def review_codebase(self) -> str:
        """Have the agent review and understand the codebase."""
        prompt = f"""Analyze the codebase at {self.workspace_path}.
Provide:
1. Project structure overview
2. Key technologies and frameworks used
3. Main features/components
4. Any notable patterns or architecture decisions

Be thorough but concise."""
        return await self.execute_claude_code(prompt, self.workspace_path)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update({
            "repo_url": self.repo_url,
            "repo_name": self.repo_name,
            "tech_stack": self.tech_stack,
            "project_description": self.project_description,
            "branch": self.branch,
        })
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectAgent":
        data["role"] = AgentRole(data["role"])
        data["status"] = AgentStatus(data["status"])
        data.pop("conversation_history", None)
        return cls(**data)
