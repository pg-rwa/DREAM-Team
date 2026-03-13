"""Conversation manager for persistent CTO chat threads."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Message:
    role: str  # "user" or "cto" or "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(**data)


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = "New Chat"
    project: Optional[str] = None  # If scoped to a project
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: list[Message] = field(default_factory=list)
    archived: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "project": self.project,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "archived": self.archived,
        }

    def to_summary(self) -> dict:
        """Return summary without full message history."""
        return {
            "id": self.id,
            "title": self.title,
            "project": self.project,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": len(self.messages),
            "last_message": self.messages[-1].content[:100] if self.messages else None,
            "archived": self.archived,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            id=data["id"],
            title=data.get("title", "New Chat"),
            project=data.get("project"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            messages=messages,
            archived=data.get("archived", False),
        )

    def add_message(self, role: str, content: str) -> Message:
        msg = Message(role=role, content=content)
        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()
        return msg

    def get_anthropic_messages(self, limit: int = 20) -> list[dict]:
        """Get recent messages formatted for Anthropic API."""
        recent = [m for m in self.messages if m.role in ("user", "cto")][-limit:]
        result = []
        for m in recent:
            role = "user" if m.role == "user" else "assistant"
            result.append({"role": role, "content": m.content})
        return result


class ConversationManager:
    """Manages persistent CTO conversation threads."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.conversations: dict[str, Conversation] = {}
        self._load()

    @property
    def _file(self) -> Path:
        return self.storage_dir / "conversations.json"

    def _load(self) -> None:
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text())
                for conv_data in data.get("conversations", []):
                    conv = Conversation.from_dict(conv_data)
                    self.conversations[conv.id] = conv
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        data = {"conversations": [c.to_dict() for c in self.conversations.values()]}
        self._file.write_text(json.dumps(data, indent=2))

    def create(self, title: str = "New Chat", project: Optional[str] = None) -> Conversation:
        conv = Conversation(title=title, project=project)
        self.conversations[conv.id] = conv
        self._save()
        return conv

    def get(self, conv_id: str) -> Optional[Conversation]:
        return self.conversations.get(conv_id)

    def list_all(self) -> list[dict]:
        """Return active (non-archived) conversation summaries sorted by most recent."""
        convs = sorted(
            (c for c in self.conversations.values() if not c.archived),
            key=lambda c: c.updated_at, reverse=True,
        )
        return [c.to_summary() for c in convs]

    def list_archived(self) -> list[dict]:
        """Return archived conversation summaries sorted by most recent."""
        convs = sorted(
            (c for c in self.conversations.values() if c.archived),
            key=lambda c: c.updated_at, reverse=True,
        )
        return [c.to_summary() for c in convs]

    def archive(self, conv_id: str) -> bool:
        """Archive a conversation (soft delete)."""
        conv = self.conversations.get(conv_id)
        if not conv:
            return False
        conv.archived = True
        self._save()
        return True

    def restore(self, conv_id: str) -> bool:
        """Restore an archived conversation."""
        conv = self.conversations.get(conv_id)
        if not conv:
            return False
        conv.archived = False
        self._save()
        return True

    def add_message(self, conv_id: str, role: str, content: str) -> Optional[Message]:
        conv = self.conversations.get(conv_id)
        if not conv:
            return None
        msg = conv.add_message(role, content)
        # Auto-title from first user message
        if conv.title == "New Chat" and role == "user":
            conv.title = content[:50] + ("..." if len(content) > 50 else "")
        self._save()
        return msg

    def delete(self, conv_id: str) -> bool:
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            self._save()
            return True
        return False

    def get_cross_context(self, exclude_conv_id: Optional[str] = None, max_convs: int = 5) -> str:
        """Build a summary of recent conversations for CTO cross-reference."""
        convs = sorted(self.conversations.values(), key=lambda c: c.updated_at, reverse=True)
        lines = []
        count = 0
        for c in convs:
            if c.id == exclude_conv_id or not c.messages or c.archived:
                continue
            if count >= max_convs:
                break
            project_tag = f" [{c.project}]" if c.project else ""
            last_user = ""
            last_cto = ""
            for m in reversed(c.messages):
                if m.role == "user" and not last_user:
                    last_user = m.content[:80]
                elif m.role == "cto" and not last_cto:
                    last_cto = m.content[:80]
                if last_user and last_cto:
                    break
            lines.append(f"- \"{c.title}\"{project_tag}: User said \"{last_user}\" / CTO said \"{last_cto}\"")
            count += 1
        return "\n".join(lines) if lines else ""
