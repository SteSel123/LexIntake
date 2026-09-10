"""Tests for uncertain-narrative override and ``build_result_payload`` assembly.

Ensures incomplete or ambiguous narratives force REVIEW even when raw scores
would otherwise schedule a consult.
"""

from __future__ import annotations

from agents.intake.models import IntakeFacts, IntakeResponse, KBCitation
from backend.services.intake_service import build_result_payload
from scoring.domain import apply_uncertain_narrative_override, is_uncertain_narrative
from scoring.lead_scoring import LeadScoreOutput, score_lead
from tools.common import attorney_key


def test_is_uncertain_narrative_detects_keywords():
    assert is_uncertain_narrative("Facts are unclear and incomplete")
    assert not is_uncertain_narrative("Clear rear-end collision with liability")


def test_uncertain_override_forces_review_on_schedule():
    scored = LeadScoreOutput(
        qualified=True,
        lead_score=80,
        priority="High",
        decision="SCHEDULE_CONSULT",
        recommended_attorney="Jordan Hale",
        explanation="Strong case.",
    )
    out = apply_uncertain_narrative_override(
        scored, narrative="unclear immigration facts", tools={}
    )
    assert out.decision == "REVIEW"
    assert out.priority == "Medium"
    assert "Insufficient data" in out.explanation


def test_uncertain_override_softens_reject_without_hard_fail():
    scored = LeadScoreOutput(
        qualified=False,
        lead_score=20,
        priority="Low",
        decision="REJECT",
        recommended_attorney=None,
        explanation="Below threshold.",
    )
    out = apply_uncertain_narrative_override(
        scored,
        narrative="missing and unknown details",
        tools={"sol": {"valid": True}, "conflict": {"conflict": False}},
    )
    assert out.decision == "REVIEW"
    assert out.lead_score >= 40


def test_uncertain_override_keeps_conflict_reject():
    scored = LeadScoreOutput(
        qualified=False,
        lead_score=0,
        priority="Low",
        decision="REJECT",
        recommended_attorney=None,
        explanation="Conflict of interest detected.",
    )
    out = apply_uncertain_narrative_override(
        scored,
        narrative="unclear facts",
        tools={"conflict": {"conflict": True}, "sol": {"valid": True}},
    )
    assert out.decision == "REJECT"
    assert out.lead_score == 0


def test_build_result_payload_uses_post_processor():
    facts = IntakeFacts(practice_area="Immigration", narrative="Unclear immigration facts.")
    response = IntakeResponse(
        message="Screening summary. This is not legal advice. Consult a licensed attorney for legal guidance.",
        disclaimer="This is not legal advice. Consult a licensed attorney for legal guidance.",
        lead_score=75,
        case_viability="viable",
        routing_recommendation="Route to specialist.",
        next_steps=["Review"],
        citations=[KBCitation(chunk_id="c1", practice_area="immigration", doc_type="faq")],
        tool_results={
            "sol": {"valid": True, "expires_in": 200},
            "conflict": {"conflict": False},
            "estimate": {"estimate": 10_000},
            "routing": {"attorney_name": "A. Lee"},
        },
        escalate=False,
        confidence=0.7,
    )
    payload = build_result_payload(response, facts, "Unclear immigration facts in CA.")
    assert payload["decision"] == "REVIEW"
    assert payload["escalate"] is True
    assert payload["guardrails"]["disclaimer_present"] is True


def test_attorney_key_sanitizes():
    assert attorney_key("Jordan Hale!") == "jordan_hale_"
    assert len(attorney_key("x" * 200)) == 80


def test_finalize_screening_payload_attaches_runtime_fields():
    from backend.services.intake_service import finalize_screening_payload

    facts = IntakeFacts(practice_area="Personal Injury", narrative="Clear CA collision.")
    response = IntakeResponse(
        message="ok. This is not legal advice. Consult a licensed attorney for legal guidance.",
        disclaimer="This is not legal advice. Consult a licensed attorney for legal guidance.",
        lead_score=70,
        case_viability="viable",
        routing_recommendation="Route",
        next_steps=[],
        citations=[],
        tool_results={
            "sol": {"valid": True},
            "conflict": {"conflict": False},
            "estimate": {"estimate": 50_000},
            "routing": {},
        },
        escalate=False,
        confidence=0.8,
        latency_ms=12.5,
        cost=0.01,
    )
    payload = finalize_screening_payload(response, facts, facts.narrative or "")
    assert payload["latency_ms"] == 12.5
    assert payload["cost"] == 0.01
    assert payload["parsed_facts"]["practice_area"] == "Personal Injury"


def test_score_lead_still_deterministic_after_refactor():
    ctx = {
        "sol": {"valid": True, "expires_in": 120},
        "conflict": {"conflict": False},
        "case_value": {"estimate": 100_000},
        "practice_area": "Personal Injury",
        "practice_area_match": True,
        "acceptance_criteria": {"matched": ["a", "b"], "unmet_required": []},
        "recommended_attorney": "Jordan Hale",
    }
    assert score_lead(ctx).model_dump() == score_lead(ctx).model_dump()
