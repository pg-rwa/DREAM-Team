"""Task management system for tracking and delegating work."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Task:
    title: str
    description: str
    project: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_agent_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    result: Optional[str] = None
    created_by: str = "cto"

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "project": self.project,
            "status": self.status.value,
            "priority": self.priority.value,
            "assigned_agent_id": self.assigned_agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        data["status"] = TaskStatus(data["status"])
        data["priority"] = TaskPriority(data["priority"])
        return cls(**data)


class TaskManager:
    """Manages the task queue and history for the DREAM Team."""

    def __init__(self, storage_path: str = "~/.dream-team/tasks.json"):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: dict[str, Task] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                for task_data in data.get("tasks", []):
                    task = Task.from_dict(task_data)
                    self.tasks[task.task_id] = task
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        data = {"tasks": [t.to_dict() for t in self.tasks.values()]}
        self.storage_path.write_text(json.dumps(data, indent=2))

    def create_task(
        self,
        title: str,
        description: str,
        project: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        assigned_agent_id: Optional[str] = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            project=project,
            priority=priority,
            assigned_agent_id=assigned_agent_id,
        )
        self.tasks[task.task_id] = task
        self._save()
        return task

    def assign_task(self, task_id: str, agent_id: str) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].assigned_agent_id = agent_id
            self.tasks[task_id].updated_at = datetime.now().isoformat()
            self._save()

    def start_task(self, task_id: str) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.IN_PROGRESS
            self.tasks[task_id].updated_at = datetime.now().isoformat()
            self._save()

    def complete_task(self, task_id: str, result: str = "") -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.COMPLETED
            self.tasks[task_id].result = result
            self.tasks[task_id].completed_at = datetime.now().isoformat()
            self.tasks[task_id].updated_at = datetime.now().isoformat()
            self._save()

    def fail_task(self, task_id: str, reason: str = "") -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.FAILED
            self.tasks[task_id].result = reason
            self.tasks[task_id].updated_at = datetime.now().isoformat()
            self._save()

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_tasks_for_agent(self, agent_id: str) -> list[Task]:
        return [t for t in self.tasks.values() if t.assigned_agent_id == agent_id]

    def get_tasks_for_project(self, project: str) -> list[Task]:
        return [t for t in self.tasks.values() if t.project == project]

    def get_pending_tasks(self) -> list[Task]:
        return [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]

    def get_active_tasks(self) -> list[Task]:
        return [
            t for t in self.tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        ]

    def get_all_tasks(self) -> list[Task]:
        return sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)

    def get_summary(self) -> dict:
        total = len(self.tasks)
        by_status = {}
        for t in self.tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        return {"total": total, "by_status": by_status}
