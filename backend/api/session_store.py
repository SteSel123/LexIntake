"""In-memory interview session store for the HTTP API.

Interview state lives in process memory keyed by UUID. This keeps multi-turn
conversations fast without a database, but sessions are lost on restart and
are not shared across workers — acceptable for demos and single-process deploys.
"""

from __future__ import annotations

import threading
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.interview.agent import InterviewSession

# Thread-safe map: session_id -> InterviewSession agent instance.
_lock = threading.Lock()
_sessions: dict[str, "InterviewSession"] = {}


def create_session() -> tuple[str, "InterviewSession"]:
    """Allocate a new session id and empty ``InterviewSession``."""
    from agents.interview.agent import InterviewSession

    session_id = str(uuid.uuid4())
    session = InterviewSession()
    with _lock:
        _sessions[session_id] = session
    return session_id, session


def get_session(session_id: str) -> "InterviewSession | None":
    """Return the session for ``session_id``, or ``None`` if expired/unknown."""
    with _lock:
        return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    """Remove a session from memory. Returns ``True`` if it existed."""
    with _lock:
        return _sessions.pop(session_id, None) is not None
