"""Render web-service entrypoint: ensure DB/schema/KB, then serve the API."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    # First boot (and after empty DB) needs schema + ETL. Incremental ETL reuses
    # existing embeddings so restarts stay cheap.
    init = [sys.executable, "scripts/docker_init.py"]
    print("+", " ".join(init), flush=True)
    subprocess.check_call(init)

    port = os.environ.get("PORT", "8000")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]
    print("+", " ".join(cmd), flush=True)
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
