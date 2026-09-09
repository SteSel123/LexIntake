"""Tests that decide() delegates to score_lead (single scoring source)."""

from __future__ import annotations

from unittest.mock import patch

from agents.intake.decide import decide
from agents.intake.models import IntakeFacts, KBCitation, PlanResult, RetrieveResult, ToolPhaseResult
from scoring.context import build_lead_score_context
from scoring.lead_scoring import score_lead

_PI_ACCEPTANCE = {
    "must_have": [
        "Identifiable at-fault party or liable entity",
        "Documented physical injury or verifiable medical treatment",
        "Incident date within applicable SOL for the jurisdiction",
        "Clear causal link between incident and claimed injuries",
    ],
}


def _sample_pipeline():
    facts = IntakeFacts(
        name="Alex Rivera",
        opposing_party="City Transit",
        practice_area="Personal Injury",
        jurisdiction="CA",
        incident_date="2025-06-01",
        damages=45_000,
        narrative="Rear-end collision in CA with clear liability.",
    )
    plan = PlanResult(missing_fields=[], need_retrieval=True)
    retrieval = RetrieveResult(
        citations=[
            KBCitation(
                chunk_id="chunk-1",
                practice_area="personal_injury",
                doc_type="acceptance_criteria",
                excerpt="criteria",
            )
        ]
    )
    tools = ToolPhaseResult(
        sol={"valid": True, "expires_in": 400, "explanation": "OK"},
        conflict={"conflict": False, "details": []},
        estimate={"estimate": 45_000, "range_low": 30_000, "range_high": 60_000, "explanation": "comps"},
        routing={"attorney_name": "Jordan Hale", "motivation": "PI specialist"},
    )
    return facts, plan, retrieval, tools


@patch("scoring.context.load_acceptance_criteria", return_value=_PI_ACCEPTANCE)
def test_decide_matches_score_lead(_mock_acc):
    facts, plan, retrieval, tools = _sample_pipeline()
    ctx = build_lead_score_context(facts, plan, retrieval, tools, narrative=facts.narrative)
    expected = score_lead(ctx)
    decision = decide(
        facts, plan, retrieval, tools, confidence_threshold=0.55, narrative=facts.narrative
    )
    assert decision.lead_score == expected.lead_score
    if expected.decision == "SCHEDULE_CONSULT":
        assert decision.case_viability == "viable"
    elif expected.decision == "REJECT":
        assert decision.case_viability == "not_viable"
    else:
        assert decision.case_viability == "needs_review"
