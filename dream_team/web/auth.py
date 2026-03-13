"""Authentication for the DREAM Team web interface."""

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


AUTH_CONFIG_PATH = Path(os.path.expanduser("~/.dream-team/auth.json"))
SESSIONS_PATH = Path(os.path.expanduser("~/.dream-team/sessions.json"))
SESSION_EXPIRY = 86400 * 7  # 7 days

# Session store — loaded from disk on startup, saved on every change
_sessions: dict[str, dict] = {}

security = HTTPBearer(auto_error=False)


def _load_sessions() -> None:
    """Load sessions from disk."""
    global _sessions
    if SESSIONS_PATH.exists():
        try:
            data = json.loads(SESSIONS_PATH.read_text())
            # Prune expired sessions on load
            now = time.time()
            _sessions = {
                k: v for k, v in data.items()
                if now - v.get("created_at", 0) < SESSION_EXPIRY
            }
        except (json.JSONDecodeError, KeyError):
            _sessions = {}


def _save_sessions() -> None:
    """Persist sessions to disk."""
    SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_PATH.write_text(json.dumps(_sessions, indent=2))
    try:
        SESSIONS_PATH.chmod(0o600)
    except OSError:
        pass


# Load on module import
_load_sessions()


def _get_api_key() -> str:
    """Get or create the API key."""
    AUTH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if AUTH_CONFIG_PATH.exists():
        try:
            data = json.loads(AUTH_CONFIG_PATH.read_text())
            if "api_key" in data:
                return data["api_key"]
        except (json.JSONDecodeError, KeyError):
            pass

    # Generate new API key
    api_key = f"dream-{secrets.token_urlsafe(32)}"
    AUTH_CONFIG_PATH.write_text(json.dumps({"api_key": api_key}, indent=2))
    AUTH_CONFIG_PATH.chmod(0o600)
    return api_key


def create_session(api_key: str) -> Optional[str]:
    """Validate API key and create a session token."""
    stored_key = _get_api_key()
    if not hmac.compare_digest(api_key, stored_key):
        return None

    session_token = secrets.token_urlsafe(32)
    _sessions[session_token] = {
        "created_at": time.time(),
        "last_active": time.time(),
    }
    _save_sessions()
    return session_token


def validate_session(token: str) -> bool:
    """Check if a session token is valid."""
    session = _sessions.get(token)
    if not session:
        return False
    if time.time() - session["created_at"] > SESSION_EXPIRY:
        _sessions.pop(token, None)
        _save_sessions()
        return False
    session["last_active"] = time.time()
    return True


def revoke_session(token: str) -> None:
    _sessions.pop(token, None)
    _save_sessions()


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """Dependency that enforces authentication.

    Accepts either:
    - Bearer token in Authorization header
    - session_token cookie
    - api_key query parameter (for initial login)
    """
    # Check Bearer token
    if credentials and validate_session(credentials.credentials):
        return credentials.credentials

    # Check cookie
    session_token = request.cookies.get("dream_session")
    if session_token and validate_session(session_token):
        return session_token

    raise HTTPException(status_code=401, detail="Not authenticated")


def get_api_key_display() -> str:
    """Get the API key for display to the user on first run."""
    return _get_api_key()
