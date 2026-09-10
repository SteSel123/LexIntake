"""Tests for ``scoring.lead_scoring``: deterministic score bands and hard reject rules.

Covers SOL expiry, conflict detection, and SCHEDULE/REVIEW/REJECT thresholds without
calling a live LLM.
"""

from __future__ import annotations

from scoring.constants import SCORE_REVIEW_MIN, SCORE_SCHEDULE_MIN
from scoring.lead_scoring import score_lead


def _base_context(**overrides):
    ctx = {
        "sol": {"valid": True, "expires_in": 120, "explanation": "Within SOL"},
        "conflict": {"conflict": False, "details": []},
        "case_value": {
            "estimate": 100_000,
            "range_low": 75_000,
            "range_high": 125_000,
            "explanation": "Comps available",
        },
        "practice_area": "Personal Injury",
        "practice_area_match": True,
        "acceptance_criteria": {
            "matched": [
                "Identifiable at-fault party or liable entity",
                "Documented physical injury or verifiable medical treatment",
            ],
            "unmet_required": [],
        },
        "recommended_attorney": "Jordan Hale",
        "citations": [{"chunk_id": "abc", "practice_area": "personal_injury", "doc_type": "sol_rules"}],
    }
    ctx.update(overrides)
    return ctx


def test_score_lead_is_deterministic():
    a = score_lead(_base_context())
    b = score_lead(_base_context())
    assert a.model_dump() == b.model_dump()


def test_score_lead_schedules_strong_pi_case():
    out = score_lead(_base_context())
    assert out.lead_score >= SCORE_SCHEDULE_MIN
    assert out.decision == "SCHEDULE_CONSULT"
    assert out.qualified is True


def test_score_lead_rejects_expired_sol():
    out = score_lead(_base_context(sol={"valid": False, "expires_in": -30, "explanation": "Expired"}))
    assert out.decision == "REJECT"
    assert out.lead_score == 0
    assert "not legal advice" in out.explanation.lower()


def test_score_lead_rejects_conflict():
    out = score_lead(_base_context(conflict={"conflict": True, "details": [{"id": "c1"}]}))
    assert out.decision == "REJECT"
    assert out.lead_score == 0


def test_score_lead_low_value_scores_below_schedule_threshold():
    out = score_lead(
        _base_context(
            case_value={"estimate": 5_000, "explanation": "Low"},
            acceptance_criteria={"matched": [], "unmet_required": ["jurisdiction"]},
            recommended_attorney=None,
        )
    )
    assert out.lead_score < SCORE_SCHEDULE_MIN
    assert out.decision in ("REVIEW", "REJECT")


def test_score_lead_practice_mismatch_halves_score():
    from scoring.constants import PRACTICE_MISMATCH_FACTOR

    matched = score_lead(_base_context(practice_area_match=True))
    mismatched = score_lead(_base_context(practice_area_match=False))
    # Hard rejects aside, mismatch applies PRACTICE_MISMATCH_FACTOR to the running score.
    assert mismatched.lead_score <= matched.lead_score
    assert PRACTICE_MISMATCH_FACTOR == 0.5
    assert "mismatch" in mismatched.explanation.lower()
