"""Base agent classes for the DREAM Team."""

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Optional


class AgentRole(str, Enum):
    CTO = "cto"
    PROJECT_LEAD = "project_lead"
    DEVELOPER = "developer"


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class AgentMessage:
    role: str  # "user", "agent", "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: Optional[str] = None


@dataclass
class Agent:
    """Base class for all DREAM Team agents."""

    agent_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    role: AgentRole = AgentRole.DEVELOPER
    status: AgentStatus = AgentStatus.IDLE
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    conversation_history: list[AgentMessage] = field(default_factory=list)
    current_task: Optional[str] = None
    workspace_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status.value,
            "description": self.description,
            "created_at": self.created_at,
            "current_task": self.current_task,
            "workspace_path": self.workspace_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
        data["role"] = AgentRole(data["role"])
        data["status"] = AgentStatus(data["status"])
        data.pop("conversation_history", None)
        return cls(**data)

    async def execute_claude_code(
        self, prompt: str, working_dir: Optional[str] = None
    ) -> str:
        """Execute a prompt via Claude Code CLI."""
        cwd = working_dir or self.workspace_path or os.getcwd()

        self.status = AgentStatus.WORKING
        self.conversation_history.append(
            AgentMessage(role="user", content=prompt, agent_id=self.agent_id)
        )

        try:
            cmd = [
                "claude",
                "--print",
                "--output-format", "text",
                prompt,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            result = stdout.decode("utf-8", errors="replace").strip()

            if process.returncode != 0 and not result:
                result = f"Error (exit {process.returncode}): {stderr.decode('utf-8', errors='replace').strip()}"

            self.conversation_history.append(
                AgentMessage(role="agent", content=result, agent_id=self.agent_id)
            )
            self.status = AgentStatus.IDLE
            return result

        except Exception as e:
            self.status = AgentStatus.ERROR
            error_msg = f"Claude Code execution failed: {e}"
            self.conversation_history.append(
                AgentMessage(role="system", content=error_msg, agent_id=self.agent_id)
            )
            return error_msg

    async def stream_anthropic(
        self, system_prompt: str, user_message: str, model: str = "claude-sonnet-4-6"
    ) -> AsyncIterator[str]:
        """Stream a response from the Anthropic API directly, yielding text chunks."""
        import anthropic

        self.status = AgentStatus.WORKING
        self.conversation_history.append(
            AgentMessage(role="user", content=user_message, agent_id=self.agent_id)
        )

        full_result = []
        try:
            client = anthropic.AsyncAnthropic()

            async with client.messages.stream(
                model=model,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                async for text in stream.text_stream:
                    full_result.append(text)
                    yield text

            result = "".join(full_result).strip()
            self.conversation_history.append(
                AgentMessage(role="agent", content=result, agent_id=self.agent_id)
            )
            self.status = AgentStatus.IDLE

        except Exception as e:
            self.status = AgentStatus.ERROR
            error_msg = f"Anthropic API error: {e}"
            self.conversation_history.append(
                AgentMessage(role="system", content=error_msg, agent_id=self.agent_id)
            )
            yield error_msg

    async def execute_interactive(
        self, prompt: str, working_dir: Optional[str] = None
    ) -> str:
        """Execute a prompt via Claude Code in interactive (non-print) mode with auto-accept."""
        cwd = working_dir or self.workspace_path or os.getcwd()

        self.status = AgentStatus.WORKING
        self.conversation_history.append(
            AgentMessage(role="user", content=prompt, agent_id=self.agent_id)
        )

        try:
            cmd = [
                "claude",
                "--dangerously-skip-permissions",
                "--output-format", "text",
                "-p", prompt,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            result = stdout.decode("utf-8", errors="replace").strip()

            if process.returncode != 0 and not result:
                result = f"Error (exit {process.returncode}): {stderr.decode('utf-8', errors='replace').strip()}"

            self.conversation_history.append(
                AgentMessage(role="agent", content=result, agent_id=self.agent_id)
            )
            self.status = AgentStatus.IDLE
            return result

        except Exception as e:
            self.status = AgentStatus.ERROR
            error_msg = f"Claude Code execution failed: {e}"
            self.conversation_history.append(
                AgentMessage(role="system", content=error_msg, agent_id=self.agent_id)
            )
            return error_msg

    async def execute_interactive_streaming(
        self, prompt: str, working_dir: Optional[str] = None, progress_callback=None,
    ) -> str:
        """Execute via Claude Code, streaming stdout chunks to a callback."""
        cwd = working_dir or self.workspace_path or os.getcwd()

        self.status = AgentStatus.WORKING
        self.conversation_history.append(
            AgentMessage(role="user", content=prompt, agent_id=self.agent_id)
        )

        try:
            cmd = [
                "claude",
                "--dangerously-skip-permissions",
                "--output-format", "text",
                "-p", prompt,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            chunks = []
            while True:
                chunk = await process.stdout.read(512)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                chunks.append(text)
                if progress_callback:
                    try:
                        await progress_callback(text)
                    except Exception:
                        pass

            await process.wait()
            result = "".join(chunks).strip()

            if process.returncode != 0 and not result:
                stderr_out = await process.stderr.read()
                result = f"Error (exit {process.returncode}): {stderr_out.decode('utf-8', errors='replace').strip()}"

            self.conversation_history.append(
                AgentMessage(role="agent", content=result, agent_id=self.agent_id)
            )
            self.status = AgentStatus.IDLE
            return result

        except Exception as e:
            self.status = AgentStatus.ERROR
            error_msg = f"Claude Code execution failed: {e}"
            self.conversation_history.append(
                AgentMessage(role="system", content=error_msg, agent_id=self.agent_id)
            )
            return error_msg

    def get_system_prompt(self) -> str:
        """Override in subclasses for role-specific system prompts."""
        return f"You are {self.name}, a {self.role.value} on the DREAM Team."
