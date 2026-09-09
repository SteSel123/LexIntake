"""Shared scoring-domain helpers (uncertainty, decision post-process)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scoring.constants import INSUFFICIENT_DATA_MSG, SCORE_REVIEW_MIN

if TYPE_CHECKING:
    from scoring.lead_scoring import LeadScoreOutput

UNCERTAIN_WORDS: tuple[str, ...] = (
    "unclear",
    "missing",
    "unknown",
    "incomplete",
    "uncertain",
)


def is_uncertain_narrative(text: str | None) -> bool:
    """True when free-text signals incomplete / unclear intake data."""
    if not text:
        return False
    lower = text.lower()
    return any(word in lower for word in UNCERTAIN_WORDS)


def apply_uncertain_narrative_override(
    scored: LeadScoreOutput,
    *,
    narrative: str | None,
    tools: dict[str, Any] | None = None,
) -> LeadScoreOutput:
    """
    Escalate uncertain narratives to REVIEW when hard rejects do not apply.

    Keeps score_lead() pure for deterministic tool inputs; this named
    post-processor is the single place for narrative uncertainty overrides
    (formerly duplicated in intake_service).
    """
    if not is_uncertain_narrative(narrative):
        return scored

    tools = tools or {}
    conflict = (tools.get("conflict") or {}).get("conflict")
    sol_valid = (tools.get("sol") or {}).get("valid")
    prefix = f"{INSUFFICIENT_DATA_MSG} "

    if scored.decision != "REJECT":
        return scored.model_copy(
            update={
                "decision": "REVIEW",
                "priority": "Medium",
                "qualified": True,
                "explanation": prefix + str(scored.explanation or ""),
            }
        )

    # Soften REJECT → REVIEW when conflict/SOL hard-fails are absent.
    if conflict or sol_valid is False:
        return scored

    return scored.model_copy(
        update={
            "decision": "REVIEW",
            "priority": "Medium",
            "qualified": True,
            "lead_score": max(SCORE_REVIEW_MIN, int(scored.lead_score or 0)),
            "explanation": prefix + str(scored.explanation or ""),
        }
    )
