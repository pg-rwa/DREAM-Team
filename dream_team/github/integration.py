"""GitHub integration for managing repos and cloning projects."""

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RepoInfo:
    name: str
    full_name: str
    url: str
    clone_url: str
    description: str = ""
    default_branch: str = "main"
    language: str = ""
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "full_name": self.full_name,
            "url": self.url,
            "clone_url": self.clone_url,
            "description": self.description,
            "default_branch": self.default_branch,
            "language": self.language,
            "topics": self.topics,
        }


class GitHubManager:
    """Manages GitHub operations: listing repos, cloning, syncing."""

    def __init__(self, workspace_root: str = "~/.dream-team/projects"):
        self.workspace_root = Path(os.path.expanduser(workspace_root))
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    async def _run_cmd(self, cmd: list[str], cwd: Optional[str] = None) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            process.returncode,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )

    async def list_repos(self, username: Optional[str] = None) -> list[RepoInfo]:
        """List GitHub repos for the authenticated user or a specific user."""
        cmd = ["git", "ls-remote", "--get-url"]

        # Try using gh CLI first, fall back to git
        gh_cmd = ["gh", "repo", "list"]
        if username:
            gh_cmd.append(username)
        gh_cmd.extend([
            "--limit", "50",
            "--json", "name,nameWithOwner,url,sshUrl,description,defaultBranchRef,primaryLanguage,repositoryTopics",
        ])

        returncode, stdout, stderr = await self._run_cmd(gh_cmd)

        if returncode == 0 and stdout:
            try:
                repos_data = json.loads(stdout)
                repos = []
                for r in repos_data:
                    default_branch = "main"
                    if r.get("defaultBranchRef"):
                        default_branch = r["defaultBranchRef"].get("name", "main")
                    language = ""
                    if r.get("primaryLanguage"):
                        language = r["primaryLanguage"].get("name", "")
                    topics = []
                    if r.get("repositoryTopics"):
                        topics = [t.get("name", "") for t in r["repositoryTopics"]]

                    repos.append(RepoInfo(
                        name=r.get("name", ""),
                        full_name=r.get("nameWithOwner", ""),
                        url=r.get("url", ""),
                        clone_url=r.get("url", ""),
                        description=r.get("description", "") or "",
                        default_branch=default_branch,
                        language=language,
                        topics=topics,
                    ))
                return repos
            except json.JSONDecodeError:
                pass

        return []

    async def clone_repo(self, repo_url: str, repo_name: str) -> str:
        """Clone a repo into the workspace. Returns the local path."""
        target_dir = self.workspace_root / repo_name

        if target_dir.exists():
            # Pull latest instead of re-cloning
            returncode, stdout, stderr = await self._run_cmd(
                ["git", "pull"], cwd=str(target_dir)
            )
            return str(target_dir)

        returncode, stdout, stderr = await self._run_cmd(
            ["git", "clone", repo_url, str(target_dir)]
        )

        if returncode != 0:
            raise RuntimeError(f"Failed to clone {repo_url}: {stderr}")

        return str(target_dir)

    async def get_repo_info(self, repo_path: str) -> dict:
        """Get info about a local repo."""
        info = {}

        # Get current branch
        rc, stdout, _ = await self._run_cmd(
            ["git", "branch", "--show-current"], cwd=repo_path
        )
        if rc == 0:
            info["branch"] = stdout

        # Get remote URL
        rc, stdout, _ = await self._run_cmd(
            ["git", "remote", "get-url", "origin"], cwd=repo_path
        )
        if rc == 0:
            info["remote_url"] = stdout

        # Get recent commits
        rc, stdout, _ = await self._run_cmd(
            ["git", "log", "--oneline", "-5"], cwd=repo_path
        )
        if rc == 0:
            info["recent_commits"] = stdout

        # Get status
        rc, stdout, _ = await self._run_cmd(
            ["git", "status", "--short"], cwd=repo_path
        )
        if rc == 0:
            info["status"] = stdout or "(clean)"

        return info

    async def sync_repo(self, repo_path: str, branch: str = "main") -> str:
        """Pull latest changes for a repo."""
        rc, stdout, stderr = await self._run_cmd(
            ["git", "pull", "origin", branch], cwd=repo_path
        )
        if rc != 0:
            return f"Sync failed: {stderr}"
        return f"Synced successfully: {stdout}"

    def get_project_path(self, repo_name: str) -> str:
        return str(self.workspace_root / repo_name)

    def project_exists_locally(self, repo_name: str) -> bool:
        return (self.workspace_root / repo_name).exists()
