"""HTTP API tests for LexIntake FastAPI routes.

Uses FastAPI TestClient with mocked intake/interview services so CI does not
need a live LLM for backend coverage.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.intake.models import IntakeFacts, IntakeResponse
from agents.interview.agent import InterviewTurnResult
from backend.api.main import app
from backend.api import session_store


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    """Keep interview session map isolated across tests."""
    with session_store._lock:
        session_store._sessions.clear()
    yield
    with session_store._lock:
        session_store._sessions.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "lexintake-api"


def test_root_lists_endpoints(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["health"] == "/health"
    assert "intake" in body
    assert "interview" in body


@patch("backend.api.routes.intake.run_intake_analysis")
def test_analyze_returns_screening_payload(mock_run: MagicMock, client: TestClient) -> None:
    mock_run.return_value = {
        "decision": "REVIEW",
        "qualified": False,
        "priority": "Medium",
        "lead_score": 55,
        "explanation": "Needs human review.",
        "escalate": True,
        "agent_message": "Screening complete. This is not legal advice.",
        "citations": [],
        "tool_results": {"sol": None, "conflict": None, "estimate": None, "routing": None},
        "guardrails": {
            "disclaimer_present": True,
            "citations_present": False,
            "escalation_flag": True,
        },
        "parsed_facts": {"practice_area": "Personal Injury"},
        "latency_ms": 12.5,
        "cost": 0.0,
    }
    response = client.post(
        "/v1/intake/analyze",
        json={"description": "Rear-end collision in California last month."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "REVIEW"
    assert body["lead_score"] == 55
    assert body["escalate"] is True
    mock_run.assert_called_once_with("Rear-end collision in California last month.")


def test_analyze_rejects_whitespace_description(client: TestClient) -> None:
    response = client.post("/v1/intake/analyze", json={"description": "   "})
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_analyze_rejects_missing_description(client: TestClient) -> None:
    response = client.post("/v1/intake/analyze", json={})
    assert response.status_code == 422


@patch("backend.api.routes.intake.run_intake_analysis", side_effect=RuntimeError("boom"))
def test_analyze_maps_pipeline_errors_to_500(_mock_run: MagicMock, client: TestClient) -> None:
    response = client.post(
        "/v1/intake/analyze",
        json={"description": "Any non-empty case description."},
    )
    assert response.status_code == 500
    assert "failed" in response.json()["detail"].lower()


@patch("backend.api.routes.interview.create_session")
def test_start_interview_session(mock_create: MagicMock, client: TestClient) -> None:
    session = MagicMock()
    session.start.return_value = InterviewTurnResult(
        phase="collecting",
        assistant_message="Welcome. What practice area?",
        facts=IntakeFacts(),
        missing_fields=["name", "practice_area"],
        done=False,
    )
    mock_create.return_value = ("sess-1", session)

    response = client.post("/v1/interview/sessions")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "sess-1"
    assert body["phase"] == "collecting"
    assert body["done"] is False
    assert "Welcome" in body["assistant_message"]
    session.start.assert_called_once()


def test_interview_turn_unknown_session(client: TestClient) -> None:
    response = client.post(
        "/v1/interview/sessions/missing-id/turns",
        json={"message": "Personal injury"},
    )
    assert response.status_code == 404


def test_interview_turn_rejects_whitespace_message(client: TestClient) -> None:
    session = MagicMock()
    with session_store._lock:
        session_store._sessions["sess-blank"] = session

    response = client.post(
        "/v1/interview/sessions/sess-blank/turns",
        json={"message": "   "},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
    session.respond.assert_not_called()


@patch("backend.api.routes.interview.finalize_screening_payload")
def test_interview_turn_attaches_screening_when_done(
    mock_finalize: MagicMock, client: TestClient
) -> None:
    screening = IntakeResponse(
        message="Done. This is not legal advice.",
        disclaimer="This is not legal advice.",
        lead_score=70,
        case_viability="viable",
        routing_recommendation="SCHEDULE_CONSULT",
        next_steps=["Consult"],
        citations=[],
        tool_results={},
        escalate=False,
        confidence=0.8,
    )
    session = MagicMock()
    session.respond.return_value = InterviewTurnResult(
        phase="done",
        assistant_message="Screening finished.",
        facts=IntakeFacts(practice_area="Personal Injury", narrative="Crash details"),
        missing_fields=[],
        screening=screening,
        done=True,
    )
    mock_finalize.return_value = {
        "decision": "SCHEDULE_CONSULT",
        "lead_score": 70,
        "parsed_facts": {"practice_area": "Personal Injury"},
    }
    with session_store._lock:
        session_store._sessions["sess-done"] = session

    response = client.post(
        "/v1/interview/sessions/sess-done/turns",
        json={"message": "Please screen now"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["done"] is True
    assert body["phase"] == "done"
    assert body["screening"]["decision"] == "SCHEDULE_CONSULT"
    mock_finalize.assert_called_once()


def test_delete_interview_session(client: TestClient) -> None:
    with session_store._lock:
        session_store._sessions["sess-del"] = MagicMock()

    response = client.delete("/v1/interview/sessions/sess-del")
    assert response.status_code == 204
    assert session_store.get_session("sess-del") is None


def test_delete_unknown_interview_session(client: TestClient) -> None:
    response = client.delete("/v1/interview/sessions/does-not-exist")
    assert response.status_code == 404
