"""Background task workers for executing agent tasks asynchronously."""

import asyncio
from typing import Optional


class TaskWorker:
    """Processes queued tasks in the background using project agents."""

    def __init__(self, team):
        self.team = team
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False

    def enqueue(self, task_id: str) -> None:
        self.queue.put_nowait(task_id)

    def stop(self) -> None:
        self._running = False

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

            try:
                result = await agent.execute_task(task.description)
                self.team.task_manager.complete_task(task_id, result)
            except Exception as e:
                self.team.task_manager.fail_task(task_id, str(e))
            finally:
                agent.current_task = None
