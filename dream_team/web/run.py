#!/usr/bin/env python3
"""Launch the DREAM Team web server."""

import argparse
import os
import sys

import uvicorn

from .auth import get_api_key_display


def main():
    parser = argparse.ArgumentParser(description="DREAM Team Web Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for dev")
    parser.add_argument("--show-key", action="store_true", help="Show API key and exit")
    args = parser.parse_args()

    api_key = get_api_key_display()

    if args.show_key:
        print(f"API Key: {api_key}")
        return

    print(f"""
╔══════════════════════════════════════════════════╗
║            DREAM TEAM - Web Server               ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  Dashboard: http://{args.host}:{args.port}                ║
║                                                  ║
║  API Key:   {api_key[:20]}...       ║
║  (full key in ~/.dream-team/auth.json)           ║
║                                                  ║
╚══════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "dream_team.web.server:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
