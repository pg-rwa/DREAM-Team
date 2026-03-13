"""CTO Agent - The team leader who delegates work to project agents."""

import json
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from .base import Agent, AgentRole, AgentStatus


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

        return f"""You are the CTO of the DREAM Team, an AI-powered development team.

Your responsibilities:
1. Receive ideas, feedback, and directions from the founder (user)
2. Break down high-level requests into specific, actionable tasks
3. Manage project agents behind the scenes — the founder doesn't interact with them directly
4. Track progress across all projects and report results back to the founder
5. Synthesize agent findings and give the founder clear, actionable summaries
{scope_text}{context_text}{results_text}
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
    ) -> AsyncIterator[str]:
        """Stream the CTO's analysis with multi-turn and cross-conversation context."""
        system_prompt = self.get_system_prompt(team_context, project_scope, conversation_summaries, task_results)

        if conversation_messages and len(conversation_messages) > 1:
            async for chunk in self.stream_anthropic_multi(system_prompt, conversation_messages):
                yield chunk
        else:
            user_prompt = f"Founder's message: {user_message}"
            async for chunk in self.stream_anthropic(system_prompt, user_prompt):
                yield chunk

    async def stream_anthropic_multi(
        self, system_prompt: str, messages: list[dict], model: str = "claude-sonnet-4-20250514"
    ) -> AsyncIterator[str]:
        """Stream with full conversation history."""
        import anthropic

        self.status = AgentStatus.WORKING
        full_result = []
        try:
            client = anthropic.AsyncAnthropic()
            async with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=system_prompt,
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
