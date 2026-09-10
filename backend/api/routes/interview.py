"""Multi-turn interview session endpoints.

Guides the client through structured fact gathering; when complete, returns the
same screening payload shape as ``POST /v1/intake/analyze``.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.schemas import (
    CreateInterviewResponse,
    InterviewTurnRequest,
    InterviewTurnResponse,
)
from backend.api.session_store import create_session, delete_session, get_session
from backend.services.intake_service import finalize_screening_payload
from monitoring.app_logging import get_console_logger

router = APIRouter(prefix="/v1/interview", tags=["interview"])
_logger = get_console_logger("api.interview")


@router.post("/sessions", response_model=CreateInterviewResponse)
def start_session() -> CreateInterviewResponse:
    """Create an in-memory session and return the opening assistant message."""
    session_id, session = create_session()
    turn = session.start()
    return CreateInterviewResponse(
        session_id=session_id,
        phase=turn.phase,
        assistant_message=turn.assistant_message,
        missing_fields=turn.missing_fields,
        done=turn.done,
    )


@router.post("/sessions/{session_id}/turns", response_model=InterviewTurnResponse)
def respond(session_id: str, body: InterviewTurnRequest) -> InterviewTurnResponse:
    """Advance the interview with the client's message; attach screening when done."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found")

    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must not be empty")

    try:
        turn = session.respond(message)
    except Exception as exc:  # noqa: BLE001 — surface unexpected interview failures
        _logger.exception("Interview turn failed session_id=%s", session_id)
        raise HTTPException(status_code=500, detail=f"Interview turn failed: {exc}") from exc

    screening_payload = None
    if turn.done and turn.screening is not None:
        # Prefer accumulated narrative from facts; fall back to last user message.
        narrative = turn.facts.narrative or message
        screening_payload = finalize_screening_payload(
            turn.screening, turn.facts, narrative
        )

    return InterviewTurnResponse(
        session_id=session_id,
        phase=turn.phase,
        assistant_message=turn.assistant_message,
        missing_fields=turn.missing_fields,
        facts=turn.facts.model_dump(),
        done=turn.done,
        screening=screening_payload,
    )


@router.delete("/sessions/{session_id}", status_code=204)
def end_session(session_id: str) -> None:
    """Explicitly drop session state (optional cleanup after completion)."""
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Interview session not found")
