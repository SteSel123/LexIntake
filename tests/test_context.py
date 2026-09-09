"""Acceptance criteria builder tests."""

from __future__ import annotations

from unittest.mock import patch

from agents.intake.models import IntakeFacts, PlanResult, RetrieveResult, ToolPhaseResult
from scoring.context import build_acceptance_criteria, build_lead_score_context


_PI_ACCEPTANCE = {
    "must_have": [
        "Identifiable at-fault party or liable entity",
        "Documented physical injury or verifiable medical treatment",
        "Incident date within applicable SOL for the jurisdiction",
        "Clear causal link between incident and claimed injuries",
    ],
}


@patch(
    "scoring.context.load_acceptance_criteria",
    return_value=_PI_ACCEPTANCE,
)
def test_acceptance_uses_real_signals_not_placeholders(_mock_acc):
    facts = IntakeFacts(
        name="Alex",
        opposing_party="ACME",
        jurisdiction="CA",
        incident_date="2025-01-01",
        damages=10_000,
        practice_area="Personal Injury",
    )
    acc = build_acceptance_criteria(facts)
    matched = acc["matched"]
    assert "signal_1" not in matched
    assert any("identity" in m.lower() or "party" in m.lower() for m in matched)


@patch("scoring.context.load_acceptance_criteria", return_value={"must_have": []})
def test_uncertain_narrative_marks_jurisdiction_unmet(_mock_acc):
    facts = IntakeFacts(practice_area="Immigration", narrative="Unclear immigration facts.")
    acc = build_acceptance_criteria(facts, narrative=facts.narrative)
    assert "Jurisdiction confirmed for screening" in acc["unmet_required"]


@patch("scoring.context.load_acceptance_criteria", return_value=_PI_ACCEPTANCE)
def test_build_lead_score_context_wires_tools(_mock_acc):
    facts = IntakeFacts(practice_area="Personal Injury", jurisdiction="CA")
    ctx = build_lead_score_context(
        facts,
        PlanResult(),
        RetrieveResult(),
        ToolPhaseResult(sol={"valid": True, "expires_in": 100}),
    )
    assert ctx["sol"]["valid"] is True
    assert ctx["practice_area"] == "Personal Injury"
