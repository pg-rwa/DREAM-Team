"""Background task workers for executing agent tasks asynchronously."""

import asyncio
from typing import Optional


class TaskWorker:
    """Processes queued tasks in the background using project agents."""

    def __init__(self, team, broadcast_fn=None):
        self.team = team
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._broadcast = broadcast_fn

    def enqueue(self, task_id: str) -> None:
        self.queue.put_nowait(task_id)

    def stop(self) -> None:
        self._running = False

    async def _notify(self, msg: dict) -> None:
        if self._broadcast:
            await self._broadcast(msg)

    async def run(self) -> None:
        """Main worker loop - processes tasks from the queue."""
        self._running = True
        while self._running:
            try:
                task_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            task = self.team.task_manager.get_task(task_id)
            if not task:
                continue

            agent = None
            if task.assigned_agent_id:
                agent = self.team.agents.get(task.assigned_agent_id)
            elif task.project:
                agent = self.team.get_agent_for_project(task.project)

            if not agent:
                self.team.task_manager.fail_task(
                    task_id, f"No agent available for project '{task.project}'"
                )
                continue

            self.team.task_manager.start_task(task_id)
            agent.current_task = task.title

            # Notify UI that agent is now working
            await self._notify({
                "type": "agent_status",
                "project": task.project,
                "agent_id": agent.agent_id,
                "status": agent.status.value,
                "task": task.to_dict(),
            })

            try:
                result = await agent.execute_task(task.description)
                self.team.task_manager.complete_task(task_id, result)

                # Post result back to the originating conversation
                if task.conversation_id:
                    result_preview = result[:800] if len(result) > 800 else result
                    report = (
                        f"**Agent Report — {task.title}** (project: {task.project})\n"
                        f"Status: Completed\n\n{result_preview}"
                    )
                    self.team.conversations.add_message(
                        task.conversation_id, "system", report
                    )

                await self._notify({
                    "type": "task_completed",
                    "project": task.project,
                    "agent_id": agent.agent_id,
                    "status": agent.status.value,
                    "task": task.to_dict(),
                    "conversation_id": task.conversation_id,
                    "result_preview": (result[:300] if result else ""),
                })
            except Exception as e:
                error = str(e)
                self.team.task_manager.fail_task(task_id, error)

                # Post failure back to the originating conversation
                if task.conversation_id:
                    report = (
                        f"**Agent Report — {task.title}** (project: {task.project})\n"
                        f"Status: Failed\n\nError: {error[:500]}"
                    )
                    self.team.conversations.add_message(
                        task.conversation_id, "system", report
                    )

                await self._notify({
                    "type": "task_failed",
                    "project": task.project,
                    "agent_id": agent.agent_id,
                    "status": agent.status.value,
                    "task": task.to_dict(),
                    "conversation_id": task.conversation_id,
                    "error": error[:300],
                })
            finally:
                agent.current_task = None
