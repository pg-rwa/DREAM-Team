"""Configuration management for the DREAM Team."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ProjectConfig:
    name: str
    repo_url: str
    description: str = ""
    tech_stack: list[str] = field(default_factory=list)
    branch: str = "main"
    agent_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repo_url": self.repo_url,
            "description": self.description,
            "tech_stack": self.tech_stack,
            "branch": self.branch,
            "agent_name": self.agent_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        return cls(**data)


@dataclass
class ModelConfig:
    """Model selection and cost controls."""
    # Model for complex tasks: planning, delegation, multi-step reasoning
    heavy_model: str = "claude-sonnet-4-6"
    # Model for simple tasks: status checks, acknowledgments, short Q&A
    light_model: str = "claude-haiku-4-5-20251001"
    # Max tokens for heavy vs light responses
    heavy_max_tokens: int = 8192
    light_max_tokens: int = 2048
    # Max conversation messages to send (older ones trimmed)
    max_history_messages: int = 20

    def to_dict(self) -> dict:
        return {
            "heavy_model": self.heavy_model,
            "light_model": self.light_model,
            "heavy_max_tokens": self.heavy_max_tokens,
            "light_max_tokens": self.light_max_tokens,
            "max_history_messages": self.max_history_messages,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DreamTeamConfig:
    """Central configuration for the DREAM Team."""

    config_dir: str = "~/.dream-team"
    workspace_dir: str = "~/.dream-team/projects"
    github_username: str = ""
    projects: list[ProjectConfig] = field(default_factory=list)
    cto_name: str = "CTO"
    team_name: str = "DREAM Team"
    models: ModelConfig = field(default_factory=ModelConfig)

    def __post_init__(self):
        self.config_dir = os.path.expanduser(self.config_dir)
        self.workspace_dir = os.path.expanduser(self.workspace_dir)
        Path(self.config_dir).mkdir(parents=True, exist_ok=True)
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)

    @property
    def config_path(self) -> Path:
        return Path(self.config_dir) / "config.json"

    @property
    def agents_path(self) -> Path:
        return Path(self.config_dir) / "agents.json"

    def save(self) -> None:
        data = {
            "github_username": self.github_username,
            "workspace_dir": self.workspace_dir,
            "cto_name": self.cto_name,
            "team_name": self.team_name,
            "projects": [p.to_dict() for p in self.projects],
            "models": self.models.to_dict(),
        }
        self.config_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls) -> "DreamTeamConfig":
        config = cls()
        if config.config_path.exists():
            try:
                data = json.loads(config.config_path.read_text())
                config.github_username = data.get("github_username", "")
                config.workspace_dir = os.path.expanduser(
                    data.get("workspace_dir", config.workspace_dir)
                )
                config.cto_name = data.get("cto_name", "CTO")
                config.team_name = data.get("team_name", "DREAM Team")
                config.projects = [
                    ProjectConfig.from_dict(p) for p in data.get("projects", [])
                ]
                if "models" in data:
                    config.models = ModelConfig.from_dict(data["models"])
            except (json.JSONDecodeError, KeyError):
                pass
        return config

    def add_project(self, project: ProjectConfig) -> None:
        # Replace if exists, otherwise append
        self.projects = [p for p in self.projects if p.name != project.name]
        self.projects.append(project)
        self.save()

    def remove_project(self, name: str) -> None:
        self.projects = [p for p in self.projects if p.name != name]
        self.save()

    def get_project(self, name: str) -> Optional[ProjectConfig]:
        for p in self.projects:
            if p.name == name:
                return p
        return None
