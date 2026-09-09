"""In-memory interview session store for the HTTP API."""

from __future__ import annotations

import threading
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents.interview.agent import InterviewSession

_lock = threading.Lock()
_sessions: dict[str, "InterviewSession"] = {}


def create_session() -> tuple[str, "InterviewSession"]:
    from agents.interview.agent import InterviewSession

    session_id = str(uuid.uuid4())
    session = InterviewSession()
    with _lock:
        _sessions[session_id] = session
    return session_id, session


def get_session(session_id: str) -> "InterviewSession | None":
    with _lock:
        return _sessions.get(session_id)


def delete_session(session_id: str) -> bool:
    with _lock:
        return _sessions.pop(session_id, None) is not None
