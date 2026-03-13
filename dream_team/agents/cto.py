"""CTO Agent - The team leader who delegates work to project agents."""

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from .base import Agent, AgentRole, AgentStatus


@dataclass
class CTOAgent(Agent):
    """The CTO oversees all project agents and delegates tasks.

    The CTO:
    - Receives high-level ideas/feedback from the user
    - Breaks them down into actionable tasks
    - Assigns tasks to the appropriate project agents
    - Monitors progress and reports back
    - Can spin up new project agents for new projects
    """

    name: str = "CTO"
    role: AgentRole = AgentRole.CTO
    description: str = "Chief Technology Officer - oversees all projects and delegates to agents"
    managed_agents: dict[str, str] = field(default_factory=dict)  # agent_id -> project_name

    def get_system_prompt(self, team_context: str = "", project_scope: Optional[str] = None) -> str:
        scope_text = ""
        if project_scope:
            scope_text = f"""
This conversation is focused on the project: {project_scope}
Keep your responses relevant to this project. You have agents working on it behind the scenes.
"""

        return f"""You are the CTO of the DREAM Team, an AI-powered development team.

Your responsibilities:
1. Receive ideas, feedback, and directions from the founder (user)
2. Break down high-level requests into specific, actionable tasks
3. Manage project agents behind the scenes — the founder doesn't interact with them directly
4. Track progress across all projects
5. Report status updates to the founder
6. Recommend when to create new agents for new projects
{scope_text}
Current team:
{team_context}

When the founder gives you an instruction:
- Analyze what needs to be done
- Identify which project(s) are affected
- Create clear, specific task descriptions
- Delegate appropriately to your agents

When delegating tasks, respond with a structured plan in this JSON format:
{{
    "analysis": "Your understanding of the request",
    "tasks": [
        {{
            "project": "project_name",
            "agent_id": "agent_id or 'new' if new agent needed",
            "title": "task title",
            "description": "detailed task description",
            "priority": "high/medium/low"
        }}
    ],
    "notes": "Any additional context or questions for the founder"
}}

If the request is a question or needs discussion, respond conversationally.
If the request needs clarification, ask specific questions."""

    def register_agent(self, agent_id: str, project_name: str) -> None:
        self.managed_agents[agent_id] = project_name

    def unregister_agent(self, agent_id: str) -> None:
        self.managed_agents.pop(agent_id, None)

    async def analyze_request(self, user_message: str, team_context: str) -> str:
        """Have the CTO analyze a user request and produce a delegation plan."""
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
    ) -> AsyncIterator[str]:
        """Stream the CTO's analysis using the Anthropic API directly.

        Supports multi-turn conversations by passing prior messages.
        """
        system_prompt = self.get_system_prompt(team_context, project_scope)

        if conversation_messages and len(conversation_messages) > 1:
            # Multi-turn: use full conversation history
            async for chunk in self.stream_anthropic_multi(system_prompt, conversation_messages):
                yield chunk
        else:
            # Single turn fallback
            user_prompt = f"Founder's message: {user_message}\n\nAnalyze this request and respond with your plan."
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
