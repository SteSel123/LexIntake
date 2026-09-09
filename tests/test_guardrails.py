"""Guardrail self-check tests."""

from __future__ import annotations

from agents.intake.guardrails import enforce_message_guardrails, self_check
from agents.intake.models import DecisionResult, KBCitation, PlanResult, RetrieveResult


def test_self_check_requires_disclaimer():
    draft = "This case looks promising for intake."
    retrieval = RetrieveResult(citations=[KBCitation(chunk_id="c1", practice_area="pi", doc_type="faq")])
    decision = DecisionResult(
        lead_score=80,
        case_viability="viable",
        routing_recommendation="Route to Jordan Hale.",
        confidence=0.9,
    )
    plan = PlanResult(need_retrieval=True)
    result = self_check(draft, retrieval, decision, plan, confidence_threshold=0.55)
    assert result.disclaimers_present is False
    assert not result.ok


def test_enforce_message_guardrails_appends_disclaimer():
    msg = enforce_message_guardrails(
        "Screening summary for staff.",
        escalate=False,
        citations=[KBCitation(chunk_id="x", practice_area="pi", doc_type="faq")],
    )
    assert "not legal advice" in msg.lower()
