"""FastAPI server for the DREAM Team web interface."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config.settings import DreamTeamConfig
from ..github.integration import GitHubManager
from ..team import DreamTeam
from .auth import create_session, get_api_key_display, require_auth, revoke_session, validate_session
from .workers import TaskWorker


# Global state
team: Optional[DreamTeam] = None
worker: Optional[TaskWorker] = None
github: Optional[GitHubManager] = None
ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global team, worker, github
    config = DreamTeamConfig.load()
    team = DreamTeam(config)
    worker = TaskWorker(team)
    github = GitHubManager(config.workspace_dir)
    worker_task = asyncio.create_task(worker.run())
    yield
    worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="DREAM Team",
        description="AI Agent Team Manager",
        version="0.1.0",
        lifespan=lifespan,
    )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # --- Auth routes ---

    class LoginRequest(BaseModel):
        api_key: str

    @app.post("/api/auth/login")
    async def login(req: LoginRequest, response: Response):
        session_token = create_session(req.api_key)
        if not session_token:
            raise HTTPException(status_code=401, detail="Invalid API key")
        response.set_cookie(
            "dream_session", session_token,
            httponly=True, samesite="strict", max_age=86400 * 7,
        )
        return {"token": session_token}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response):
        token = request.cookies.get("dream_session")
        if token:
            revoke_session(token)
        response.delete_cookie("dream_session")
        return {"ok": True}

    # --- Team routes ---

    @app.get("/api/team/status")
    async def team_status(_: str = Depends(require_auth)):
        return team.get_team_status()

    @app.get("/api/team/context")
    async def team_context(_: str = Depends(require_auth)):
        return {"context": team.get_team_context()}

    # --- CTO routes ---

    class CTOMessage(BaseModel):
        message: str

    @app.post("/api/cto/talk")
    async def talk_to_cto(req: CTOMessage, _: str = Depends(require_auth)):
        async def stream_response():
            async for chunk in team.delegate_to_cto_stream(req.message):
                # Send as Server-Sent Events format
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: {\"done\": true}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # --- Project routes ---

    class AddProjectRequest(BaseModel):
        name: str
        repo_url: str
        description: str = ""
        tech_stack: list[str] = []
        branch: str = "main"

    @app.get("/api/projects")
    async def list_projects(_: str = Depends(require_auth)):
        return {
            "projects": [p.to_dict() for p in team.config.projects],
            "agents": {
                aid: a.to_dict() for aid, a in team.agents.items()
            },
        }

    @app.post("/api/projects")
    async def add_project(req: AddProjectRequest, _: str = Depends(require_auth)):
        agent = await team.add_project(
            name=req.name,
            repo_url=req.repo_url,
            description=req.description,
            tech_stack=req.tech_stack,
            branch=req.branch,
        )
        await broadcast({
            "type": "project_added",
            "project": req.name,
            "agent": agent.to_dict(),
        })
        return {"agent": agent.to_dict()}

    @app.delete("/api/projects/{name}")
    async def remove_project(name: str, _: str = Depends(require_auth)):
        team.remove_project(name)
        await broadcast({"type": "project_removed", "project": name})
        return {"ok": True}

    @app.get("/api/projects/{name}/status")
    async def project_status(name: str, _: str = Depends(require_auth)):
        agent = team.get_agent_for_project(name)
        if not agent:
            raise HTTPException(status_code=404, detail=f"No agent for '{name}'")
        status = await agent.get_project_status()
        return {"project": name, "status": status}

    class AgentChatMessage(BaseModel):
        message: str

    @app.post("/api/projects/{name}/chat")
    async def chat_with_agent(name: str, req: AgentChatMessage, _: str = Depends(require_auth)):
        """Stream a chat response from a project agent."""
        agent = team.get_agent_for_project(name)
        if not agent:
            raise HTTPException(status_code=404, detail=f"No agent for '{name}'")

        async def stream_response():
            async for chunk in agent.chat_stream(req.message):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: {\"done\": true}\n\n"

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/projects/{name}/review")
    async def review_project(name: str, _: str = Depends(require_auth)):
        agent = team.get_agent_for_project(name)
        if not agent:
            raise HTTPException(status_code=404, detail=f"No agent for '{name}'")
        review = await agent.review_codebase()
        return {"project": name, "review": review}

    # --- Task routes ---

    class CreateTaskRequest(BaseModel):
        title: str
        description: str
        project: str
        priority: str = "medium"
        execute: bool = False  # If true, immediately execute via agent

    @app.get("/api/tasks")
    async def list_tasks(
        project: Optional[str] = None,
        status: Optional[str] = None,
        _: str = Depends(require_auth),
    ):
        tasks = team.task_manager.get_all_tasks()
        if project:
            tasks = [t for t in tasks if t.project == project]
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        return {
            "tasks": [t.to_dict() for t in tasks],
            "summary": team.task_manager.get_summary(),
        }

    @app.post("/api/tasks")
    async def create_task(req: CreateTaskRequest, _: str = Depends(require_auth)):
        from ..tasks.manager import TaskPriority

        agent = team.get_agent_for_project(req.project)
        agent_id = agent.agent_id if agent else None

        task = team.task_manager.create_task(
            title=req.title,
            description=req.description,
            project=req.project,
            priority=TaskPriority(req.priority),
            assigned_agent_id=agent_id,
        )

        if req.execute and agent:
            worker.enqueue(task.task_id)
            await broadcast({
                "type": "task_started",
                "task": task.to_dict(),
            })

        return {"task": task.to_dict()}

    @app.post("/api/tasks/{task_id}/execute")
    async def execute_task(task_id: str, _: str = Depends(require_auth)):
        task = team.task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        worker.enqueue(task_id)
        return {"queued": True, "task_id": task_id}

    # --- GitHub routes ---

    @app.get("/api/github/repos")
    async def list_github_repos(
        username: Optional[str] = None,
        _: str = Depends(require_auth),
    ):
        """List GitHub repos for the authenticated user."""
        repos = await github.list_repos(username or team.config.github_username or None)
        return {"repos": [r.to_dict() for r in repos]}

    class CreateRepoRequest(BaseModel):
        name: str
        description: str = ""
        private: bool = False

    @app.post("/api/github/repos")
    async def create_github_repo(req: CreateRepoRequest, _: str = Depends(require_auth)):
        """Create a new GitHub repo and optionally assign an agent."""
        repo = await github.create_repo(req.name, req.description, req.private)
        return {"repo": repo.to_dict()}

    @app.post("/api/github/repos/{repo_name}/assign")
    async def assign_agent_to_repo(repo_name: str, _: str = Depends(require_auth)):
        """Fetch a GitHub repo and assign a new agent to it."""
        # Find repo info from GitHub
        repos = await github.list_repos(team.config.github_username or None)
        repo = next((r for r in repos if r.name == repo_name), None)
        if not repo:
            raise HTTPException(status_code=404, detail=f"Repo '{repo_name}' not found on GitHub")

        # Add as project with an agent
        agent = await team.add_project(
            name=repo.name,
            repo_url=repo.clone_url,
            description=repo.description,
            tech_stack=[repo.language] if repo.language else [],
            branch=repo.default_branch,
        )
        await broadcast({
            "type": "project_added",
            "project": repo.name,
            "agent": agent.to_dict(),
        })
        return {"agent": agent.to_dict(), "repo": repo.to_dict()}

    @app.post("/api/github/import-all")
    async def import_all_repos(
        exclude: Optional[str] = None,
        _: str = Depends(require_auth),
    ):
        """Import all GitHub repos and assign an agent to each."""
        exclude_list = [e.strip().lower() for e in (exclude or "").split(",") if e.strip()]
        repos = await github.list_repos(team.config.github_username or None)
        results = []
        for repo in repos:
            if repo.name.lower() in exclude_list:
                continue
            # Skip if already has an agent
            if team.get_agent_for_project(repo.name):
                results.append({"repo": repo.name, "status": "already_assigned"})
                continue
            try:
                agent = await team.add_project(
                    name=repo.name,
                    repo_url=repo.clone_url,
                    description=repo.description,
                    tech_stack=[repo.language] if repo.language else [],
                    branch=repo.default_branch,
                )
                results.append({"repo": repo.name, "status": "assigned", "agent": agent.to_dict()})
            except Exception as e:
                results.append({"repo": repo.name, "status": "error", "error": str(e)})
        return {"results": results}

    # --- WebSocket for real-time updates ---

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        # Check auth via query param or cookie
        token = ws.query_params.get("token") or ws.cookies.get("dream_session")
        if not token or not validate_session(token):
            await ws.close(code=4001, reason="Unauthorized")
            return

        await ws.accept()
        ws_clients.append(ws)
        try:
            # Send initial state
            await ws.send_json({
                "type": "init",
                "team": team.get_team_status(),
            })
            while True:
                data = await ws.receive_text()
                # Handle incoming messages (e.g., CTO talk via WS)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "cto_talk":
                        response = await team.delegate_to_cto(msg["message"])
                        await ws.send_json({
                            "type": "cto_response",
                            "response": response,
                        })
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            ws_clients.remove(ws)

    # --- Web UI ---

    templates_dir = Path(__file__).parent / "templates"

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        token = request.cookies.get("dream_session")
        if not token or not validate_session(token):
            return RedirectResponse("/login")
        html = (templates_dir / "dashboard.html").read_text()
        return HTMLResponse(html)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        html = (templates_dir / "login.html").read_text()
        return HTMLResponse(html)

    return app


async def broadcast(message: dict) -> None:
    """Send a message to all connected WebSocket clients."""
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_clients.remove(ws)
