"""
Shared scoring-domain helpers (uncertainty detection, decision post-process).

Keeps narrative-uncertainty logic out of score_lead() so the core engine stays
purely deterministic on structured tool inputs. Uncertainty itself comes from
LLM structured extraction (``IntakeFacts.uncertain``), not keyword scanning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scoring.constants import INSUFFICIENT_DATA_MSG, SCORE_REVIEW_MIN

if TYPE_CHECKING:
    from scoring.lead_scoring import LeadScoreOutput


def is_uncertain_intake(
    *,
    uncertain: bool | None = None,
    facts_uncertain: bool | None = None,
) -> bool:
    """True when LLM extraction (or an explicit flag) marked the intake uncertain."""
    if uncertain is not None:
        return bool(uncertain)
    if facts_uncertain is not None:
        return bool(facts_uncertain)
    return False


# Back-compat alias used by older call sites / tests.
def is_uncertain_narrative(
    text: str | None = None,
    *,
    uncertain: bool | None = None,
) -> bool:
    """Prefer ``uncertain`` flag; ignore free-text keyword scanning."""
    del text  # narrative keywords are no longer used
    return is_uncertain_intake(uncertain=uncertain)


def apply_uncertain_narrative_override(
    scored: LeadScoreOutput,
    *,
    narrative: str | None = None,
    tools: dict[str, Any] | None = None,
    uncertain: bool | None = None,
) -> LeadScoreOutput:
    """
    Escalate uncertain intakes to REVIEW when hard rejects do not apply.

    Keeps score_lead() pure for deterministic tool inputs; this named
    post-processor is the single place for narrative uncertainty overrides.
    Uncertainty is supplied by LLM structured output (``uncertain``), not regex.
    """
    del narrative  # kept for call-site compatibility
    if not is_uncertain_intake(uncertain=uncertain):
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
