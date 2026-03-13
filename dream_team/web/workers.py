"""Background task workers for executing agent tasks asynchronously."""

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional


class TaskWorker:
    """Processes queued tasks in the background using project agents."""

    def __init__(self, team, broadcast_fn=None):
        self.team = team
        self.queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()  # (task_id, priority_rank)
        self._running = False
        self._broadcast = broadcast_fn

    def enqueue(self, task_id: str) -> None:
        """Add task to priority queue. HIGH=0, MEDIUM=1, LOW=2 (lower = higher priority)."""
        task = self.team.task_manager.get_task(task_id)
        priority_rank = {"high": 0, "medium": 1, "low": 2}.get(
            task.priority.value if task else "medium", 1
        )
        self.queue.put_nowait((task_id, priority_rank))

    def stop(self) -> None:
        self._running = False

    async def _notify(self, msg: dict) -> None:
        if self._broadcast:
            await self._broadcast(msg)

    async def _drain_and_sort(self) -> list[str]:
        """Drain all queued items, sort by priority, return task IDs."""
        items = []
        try:
            while True:
                items.append(self.queue.get_nowait())
        except asyncio.QueueEmpty:
            pass
        if not items:
            return []
        items.sort(key=lambda x: x[1])  # Sort by priority rank
        return [task_id for task_id, _ in items]

    def _verify_deployment(self, agent) -> dict:
        """Check git status of the agent's workspace after task completion."""
        ws = agent.workspace_path
        if not ws or not Path(ws).exists():
            return {"deployed": False, "reason": "workspace not found"}

        info = {}
        try:
            info["branch"] = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=ws, text=True, timeout=5,
            ).strip()
            info["commit"] = subprocess.check_output(
                ["git", "log", "-1", "--format=%h %s (%ar)"],
                cwd=ws, text=True, timeout=5,
            ).strip()
            dirty = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=ws, text=True, timeout=5,
            ).strip()
            info["uncommitted_files"] = len(dirty.splitlines()) if dirty else 0
            # Check if local is ahead of remote
            try:
                ahead = subprocess.check_output(
                    ["git", "rev-list", "--count", f"origin/{info['branch']}..HEAD"],
                    cwd=ws, text=True, timeout=5,
                ).strip()
                info["commits_ahead"] = int(ahead)
                info["pushed"] = int(ahead) == 0
            except Exception:
                info["pushed"] = None  # Can't determine
            info["deployed"] = True
        except Exception as e:
            info["deployed"] = False
            info["reason"] = str(e)
        return info

    async def run(self) -> None:
        """Main worker loop - processes tasks from the queue with priority ordering."""
        self._running = True
        while self._running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                task_id = item[0]
            except asyncio.TimeoutError:
                continue

            # Drain any other queued tasks and re-sort by priority
            more = await self._drain_and_sort()
            all_ids = [task_id] + more

            # Re-sort including the first item
            def _prio(tid):
                t = self.team.task_manager.get_task(tid)
                return {"high": 0, "medium": 1, "low": 2}.get(
                    t.priority.value if t else "medium", 1
                )
            all_ids.sort(key=_prio)

            for current_id in all_ids:
                await self._execute_task(current_id)

    async def _execute_task(self, task_id: str) -> None:
        """Execute a single task with progress tracking and deployment verification."""
        task = self.team.task_manager.get_task(task_id)
        if not task:
            return

        agent = None
        if task.assigned_agent_id:
            agent = self.team.agents.get(task.assigned_agent_id)
        elif task.project:
            agent = self.team.get_agent_for_project(task.project)

        if not agent:
            self.team.task_manager.fail_task(
                task_id, f"No agent available for project '{task.project}'"
            )
            return

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

        # Progress callback - throttled to avoid flooding WebSocket
        last_progress_time = [0.0]
        progress_buffer = []

        async def on_progress(chunk: str):
            progress_buffer.append(chunk)
            now = time.time()
            # Send progress at most every 2 seconds
            if now - last_progress_time[0] >= 2.0:
                last_progress_time[0] = now
                text = "".join(progress_buffer)
                # Send last 1500 chars as a progress snapshot
                snapshot = text[-1500:] if len(text) > 1500 else text
                # Store in TaskManager so CTO can query it
                self.team.task_manager.update_progress(task_id, snapshot)
                await self._notify({
                    "type": "task_progress",
                    "task_id": task_id,
                    "project": task.project,
                    "agent_id": agent.agent_id,
                    "title": task.title,
                    "conversation_id": task.conversation_id,
                    "progress": snapshot,
                })

        try:
            result = await agent.execute_task(task.description, progress_callback=on_progress)

            # Verify deployment status after completion
            deploy_info = self._verify_deployment(agent)
            deploy_summary = ""
            if deploy_info.get("deployed"):
                parts = [f"Branch: {deploy_info.get('branch', '?')}"]
                parts.append(f"Latest commit: {deploy_info.get('commit', '?')}")
                if deploy_info.get("uncommitted_files", 0) > 0:
                    parts.append(f"WARNING: {deploy_info['uncommitted_files']} uncommitted files")
                if deploy_info.get("pushed") is True:
                    parts.append("Changes pushed to remote")
                elif deploy_info.get("pushed") is False:
                    parts.append(f"NOT PUSHED — {deploy_info.get('commits_ahead', '?')} commits ahead of remote")
                deploy_summary = "\n".join(parts)
            else:
                deploy_summary = f"Deployment verification failed: {deploy_info.get('reason', 'unknown')}"

            self.team.task_manager.complete_task(task_id, result)

            # Post result back to the originating conversation (full result, not truncated)
            if task.conversation_id:
                # Include up to 3000 chars of result + deployment status
                result_preview = result[:3000] if len(result) > 3000 else result
                if len(result) > 3000:
                    result_preview += "\n... (full output truncated)"
                report = (
                    f"**Agent Report — {task.title}** (project: {task.project})\n"
                    f"Status: Completed\n\n{result_preview}\n\n"
                    f"---\n**Deployment Status:**\n{deploy_summary}"
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
                "result_preview": (result[:1500] if result else ""),
                "deployment": deploy_info,
            })
        except Exception as e:
            error = str(e)
            self.team.task_manager.fail_task(task_id, error)

            # Post failure back to the originating conversation
            if task.conversation_id:
                report = (
                    f"**Agent Report — {task.title}** (project: {task.project})\n"
                    f"Status: Failed\n\nError: {error[:2000]}"
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
                "error": error[:1500],
            })
        finally:
            agent.current_task = None
