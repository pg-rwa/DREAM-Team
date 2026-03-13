"""CTO Agent - The team leader who delegates work to project agents."""

import json
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from .base import Agent, AgentRole, AgentStatus


# Keywords that indicate a message needs the heavy (Sonnet) model
_HEAVY_KEYWORDS = {
    "build", "implement", "create", "add", "fix", "refactor", "deploy",
    "design", "architect", "plan", "migrate", "upgrade", "rewrite",
    "feature", "integrate", "optimize", "debug", "investigate",
}


def _needs_heavy_model(message: str, has_task_context: bool = False) -> bool:
    """Decide whether a message needs the expensive model or can use Haiku.

    Uses Haiku (cheap) for: status checks, greetings, short confirmations, simple Q&A.
    Uses Sonnet (heavy) for: task delegation, planning, debugging, anything with ```tasks blocks.
    """
    msg_lower = message.lower().strip()

    # Short messages (< 30 chars) are almost always simple
    if len(msg_lower) < 30 and not any(kw in msg_lower for kw in _HEAVY_KEYWORDS):
        return False

    # Explicit task/build requests need Sonnet
    if any(kw in msg_lower for kw in _HEAVY_KEYWORDS):
        return True

    # If there are active task results to synthesize, use Sonnet
    if has_task_context:
        return True

    # Default to light for conversational messages
    return False


@dataclass
class CTOAgent(Agent):
    """The CTO oversees all project agents and delegates tasks."""

    name: str = "CTO"
    role: AgentRole = AgentRole.CTO
    description: str = "Chief Technology Officer - oversees all projects and delegates to agents"
    managed_agents: dict[str, str] = field(default_factory=dict)  # agent_id -> project_name

    def get_system_prompt(
        self,
        team_context: str = "",
        project_scope: Optional[str] = None,
        conversation_summaries: Optional[str] = None,
        task_results: Optional[str] = None,
        active_progress: Optional[str] = None,
        deployment_status: Optional[str] = None,
    ) -> str:
        scope_text = ""
        if project_scope:
            scope_text = f"""
This conversation is focused on the project: **{project_scope}**
Keep your responses relevant to this project. You have agents working on it behind the scenes.
"""

        context_text = ""
        if conversation_summaries:
            context_text = f"""
Recent activity across other conversations (for reference):
{conversation_summaries}
"""

        results_text = ""
        if task_results:
            results_text = f"""
Recent agent reports (task results from your delegated work):
{task_results}

Use these results to inform your responses. When the founder asks for updates, summarize what your agents found or accomplished. If a task failed, explain the issue and suggest next steps.
"""

        progress_text = ""
        if active_progress:
            progress_text = f"""
LIVE AGENT PROGRESS (tasks currently being executed by your agents):
{active_progress}

You have FULL VISIBILITY into what your agents are doing right now. When the founder asks about progress:
- Report what stage each agent is at based on their latest output
- Summarize what they've discovered or accomplished so far
- Estimate how much work remains based on the output you can see
- Flag if an agent appears stuck or is encountering errors
- Be specific — reference actual output, not vague platitudes
"""

        deploy_text = ""
        if deployment_status:
            deploy_text = f"""
DEPLOYMENT STATUS (current state of each project's codebase):
{deployment_status}

You can see each project's current branch, latest commit, and whether there are uncommitted changes.
When the founder asks about deployment:
- Report which commit is live and what it contains
- Flag if agent work has been committed but not yet deployed (commits ahead of deployed version)
- Note any uncommitted changes that suggest work in progress
- Confirm when new features are actually deployed and live
"""

        return f"""You are the CTO of the DREAM Team, an AI-powered development team.

Your responsibilities:
1. Receive ideas, feedback, and directions from the founder (user)
2. Break down high-level requests into specific, actionable tasks
3. Manage project agents behind the scenes — the founder doesn't interact with them directly
4. Track progress across all projects and report results back to the founder
5. Synthesize agent findings and give the founder clear, actionable summaries
{scope_text}{context_text}{results_text}{progress_text}{deploy_text}
Current team:
{team_context}

IMPORTANT - How to delegate work:
When the founder asks you to build, fix, or change something, you MUST delegate to your agents.
Include a JSON task block in your response using this exact format:

```tasks
[
  {{
    "project": "project-name",
    "title": "short task title",
    "description": "detailed description of what the agent should do",
    "priority": "high"
  }}
]
```

Rules for delegation:
- Use the exact project name from "Current team" above
- The agent will execute the task autonomously using Claude Code
- You can delegate multiple tasks at once
- If no matching project exists, tell the founder to add it first
- For questions, status checks, or discussion — just respond conversationally, no task block needed
- Always explain what you're delegating and why before the task block
- When you have task results available, reference them in your response to the founder"""

    def register_agent(self, agent_id: str, project_name: str) -> None:
        self.managed_agents[agent_id] = project_name

    def unregister_agent(self, agent_id: str) -> None:
        self.managed_agents.pop(agent_id, None)

    @staticmethod
    def extract_tasks(response: str) -> list[dict]:
        """Parse task blocks from CTO response text."""
        # Look for ```tasks ... ``` blocks
        pattern = r'```tasks\s*\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        tasks = []
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, list):
                    tasks.extend(parsed)
                elif isinstance(parsed, dict):
                    tasks.append(parsed)
            except json.JSONDecodeError:
                continue
        return tasks

    async def analyze_request(self, user_message: str, team_context: str) -> str:
        prompt = f"""{self.get_system_prompt(team_context)}

Founder's message: {user_message}

Analyze this request and respond with your plan."""
        return await self.execute_claude_code(prompt)

    async def analyze_request_stream(
        self,
        user_message: str,
        team_context: str,
        project_scope: Optional[str] = None,
        conversation_messages: Optional[list[dict]] = None,
        conversation_summaries: Optional[str] = None,
        task_results: Optional[str] = None,
        active_progress: Optional[str] = None,
        deployment_status: Optional[str] = None,
        model_config=None,
    ) -> AsyncIterator[str]:
        """Stream the CTO's analysis with smart model routing.

        Simple messages (status checks, greetings) -> Haiku (cheap)
        Complex messages (planning, delegation) -> Sonnet (capable)
        """
        system_prompt = self.get_system_prompt(
            team_context, project_scope, conversation_summaries,
            task_results, active_progress, deployment_status,
        )

        # Determine model based on message complexity
        has_task_context = bool(task_results or active_progress)
        use_heavy = _needs_heavy_model(user_message, has_task_context)

        if model_config:
            model = model_config.heavy_model if use_heavy else model_config.light_model
            max_tokens = model_config.heavy_max_tokens if use_heavy else model_config.light_max_tokens
            max_history = model_config.max_history_messages
        else:
            model = "claude-sonnet-4-6" if use_heavy else "claude-haiku-4-5-20251001"
            max_tokens = 8192 if use_heavy else 2048
            max_history = 20

        if conversation_messages and len(conversation_messages) > 1:
            # Trim conversation history to avoid unbounded cost
            trimmed = conversation_messages
            if len(trimmed) > max_history:
                trimmed = trimmed[-max_history:]
                # Ensure first message is from user (Anthropic requirement)
                if trimmed[0]["role"] != "user":
                    trimmed = trimmed[1:]
            async for chunk in self._stream_with_cache(
                system_prompt, trimmed, model, max_tokens
            ):
                yield chunk
        else:
            user_prompt = f"Founder's message: {user_message}"
            async for chunk in self._stream_with_cache(
                system_prompt, [{"role": "user", "content": user_prompt}],
                model, max_tokens,
            ):
                yield chunk

    async def _stream_with_cache(
        self,
        system_prompt: str,
        messages: list[dict],
        model: str,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        """Stream with prompt caching to reduce repeated input token costs."""
        import anthropic

        self.status = AgentStatus.WORKING
        full_result = []
        try:
            client = anthropic.AsyncAnthropic()
            # Use cache_control on system prompt to avoid re-processing it each call
            system_with_cache = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            async with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system_with_cache,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_result.append(text)
                    yield text
            self.status = AgentStatus.IDLE
        except Exception as e:
            self.status = AgentStatus.ERROR
            yield f"Anthropic API error: {e}"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["managed_agents"] = self.managed_agents
        return data
