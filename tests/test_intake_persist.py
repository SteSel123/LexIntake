"""Tests for persisting screened intake leads to Postgres."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agents.intake.models import IntakeFacts, IntakeResponse
from backend.services.intake_service import (
    finalize_screening_payload,
    persist_intake_lead,
    run_intake_analysis,
)


def test_persist_intake_lead_writes_row():
    facts = IntakeFacts(
        name="Alex Rivera",
        opposing_party="City Transit",
        practice_area="Personal Injury",
        jurisdiction="CA",
        incident_date="2025-06-01",
        damages=45_000,
        narrative="Rear-end collision",
    )
    payload = {
        "lead_score": 72,
        "decision": "SCHEDULE_CONSULT",
        "escalate": False,
        "tool_results": {"sol": {"valid": True}},
        "citations": [],
    }
    with patch("db.structured_db.insert_intake_lead", return_value="lead-test") as mock_insert:
        lead_id = persist_intake_lead(facts, payload, source="analyze")
    assert lead_id == "lead-test"
    row = mock_insert.call_args.args[0]
    assert row["source"] == "analyze"
    assert row["name"] == "Alex Rivera"
    assert row["jurisdiction"] == "CA"
    assert row["lead_score"] == 72
    assert row["decision"] == "SCHEDULE_CONSULT"
    assert row["id"].startswith("lead-")


def test_persist_intake_lead_returns_none_on_db_error():
    facts = IntakeFacts(practice_area="Personal Injury", narrative="test")
    with patch("db.structured_db.insert_intake_lead", side_effect=RuntimeError("db down")):
        assert persist_intake_lead(facts, {"lead_score": 1}, source="analyze") is None


@patch("backend.services.intake_service.persist_intake_lead", return_value="lead-abc")
@patch("scoring.context.load_acceptance_criteria", return_value={"must_have": []})
@patch("agents.intake.agent.IntakeAgent")
def test_run_intake_analysis_includes_lead_id(
    mock_agent_cls: MagicMock, _mock_acc: MagicMock, _mock_persist: MagicMock
):
    from scoring.lead_scoring import LeadScoreOutput

    agent = MagicMock()
    mock_agent_cls.return_value = agent
    facts = IntakeFacts(practice_area="Personal Injury", narrative="crash in CA", jurisdiction="CA")
    agent.extract_facts.return_value = facts
    agent.run_intake.return_value = IntakeResponse(
        message="ok. This is not legal advice. Consult a licensed attorney for legal guidance.",
        disclaimer="This is not legal advice. Consult a licensed attorney for legal guidance.",
        lead_score=60,
        case_viability="needs_review",
        routing_recommendation="Review",
        next_steps=[],
        citations=[],
        tool_results={},
        escalate=False,
        confidence=0.5,
        cost=0.0,
    )
    with patch(
        "backend.services.intake_service.score_lead",
        return_value=LeadScoreOutput(
            qualified=True,
            lead_score=60,
            priority="Medium",
            decision="REVIEW",
            recommended_attorney=None,
            explanation="Review",
        ),
    ):
        payload = run_intake_analysis("crash in CA", agent=agent)
    assert payload["intake_lead_id"] == "lead-abc"


@patch("backend.services.intake_service.persist_intake_lead", return_value="lead-iv")
@patch("scoring.context.load_acceptance_criteria", return_value={"must_have": []})
def test_finalize_screening_payload_includes_lead_id(
    _mock_acc: MagicMock, _mock_persist: MagicMock
):
    from scoring.lead_scoring import LeadScoreOutput

    facts = IntakeFacts(practice_area="Immigration", narrative="asylum clock", uncertain=True)
    screening = IntakeResponse(
        message="Screen. This is not legal advice. Consult a licensed attorney for legal guidance.",
        disclaimer="This is not legal advice. Consult a licensed attorney for legal guidance.",
        lead_score=40,
        case_viability="needs_review",
        routing_recommendation="Escalate",
        next_steps=[],
        citations=[],
        tool_results={},
        escalate=True,
        confidence=0.4,
    )
    with patch(
        "backend.services.intake_service.score_lead",
        return_value=LeadScoreOutput(
            qualified=True,
            lead_score=40,
            priority="Medium",
            decision="SCHEDULE_CONSULT",
            recommended_attorney=None,
            explanation="Strong enough",
        ),
    ):
        payload = finalize_screening_payload(screening, facts, facts.narrative or "")
    assert payload["intake_lead_id"] == "lead-iv"
