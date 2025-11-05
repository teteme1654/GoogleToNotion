"""Render entry point that can launch either Streamlit UI or Flask API."""
from __future__ import annotations

import os
import sys


def build_command(mode: str, port: str) -> list[str]:
    normalized = mode.lower()
    if normalized in {"streamlit", "ui"}:
        return [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_ui.py",
            "--server.port",
            port,
            "--server.address",
            "0.0.0.0",
        ]
    if normalized in {"flask", "api", "gunicorn"}:
        return [
            "gunicorn",
            "app:app",
            "--bind",
            f"0.0.0.0:{port}",
        ]
    raise ValueError(
        "Unsupported RENDER_PROCESS value. Use 'streamlit' (default) or 'flask'."
    )


def main() -> None:
    mode = os.getenv("RENDER_PROCESS", "streamlit")
    port = os.getenv("PORT", "10000")

    try:
        command = build_command(mode, port)
    except ValueError as error:
        print(f"❌ {error}")
        sys.exit(1)

    print(f"🚀 Starting Render process in '{mode}' mode on port {port}...")
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
