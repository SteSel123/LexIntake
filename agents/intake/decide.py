"""
Intake-phase decision: delegates scoring to score_lead (single source of truth).

Turns tool outputs + facts into a DecisionResult used by respond / self_check:
lead_score, case_viability, routing text, next_steps, and a heuristic confidence.
"""

from __future__ import annotations

from typing import Literal

from agents.intake.models import DecisionResult, IntakeFacts, PlanResult, RetrieveResult, ToolPhaseResult
from scoring.constants import (
    CONFIDENCE_BASE,
    CONFIDENCE_CITATION_BOOST,
    CONFIDENCE_MISSING_FIELD_CAP,
    CONFIDENCE_MISSING_FIELD_PENALTY,
    CONFIDENCE_SCORE_BOOST,
    CONFIDENCE_SCORE_BOOST_MIN,
    CONFIDENCE_TOOL_BOOST,
)
from scoring.context import build_lead_score_context
from scoring.lead_scoring import score_lead


def _derive_next_steps(
    plan: PlanResult,
    tools: ToolPhaseResult,
    scored_decision: str,
) -> list[str]:
    """Build operational follow-ups from SOL / conflict / estimate / routing / plan gaps."""
    steps: list[str] = []
    sol = tools.sol or {}
    conflict = tools.conflict or {}
    estimate = tools.estimate or {}
    routing = tools.routing or {}

    if sol.get("valid") is True:
        steps.append("Confirm incident timeline documents for SOL file.")
    elif sol.get("valid") is False:
        steps.append("Flag potential SOL issue for attorney review.")
    elif sol:
        steps.append("SOL uncertain — verify with attorney.")

    if conflict.get("conflict"):
        steps.append("Conflict detected — do not discuss case merits; escalate.")
    if estimate and "insufficient data" in str(estimate.get("explanation") or "").lower():
        steps.append("Insufficient comps — request more injury/damage detail.")

    attorney = str(routing.get("attorney_name") or "").strip()
    if attorney:
        steps.append(f"Schedule intake follow-up with {attorney}.")
    elif routing:
        steps.append("No attorney auto-assigned — human routing required.")

    if plan.missing_fields:
        steps.append("Collect missing intake fields before engagement.")

    if scored_decision == "REJECT":
        steps.append("Document rejection rationale for compliance review.")
    elif scored_decision == "REVIEW":
        steps.append("Route to human intake specialist for review.")

    if not steps:
        steps.append("Continue structured intake questions.")
    return steps


def _map_viability(decision: str) -> Literal["viable", "not_viable", "needs_review"]:
    """Map score_lead decision labels onto IntakeResponse case_viability values."""
    if decision == "SCHEDULE_CONSULT":
        return "viable"
    if decision == "REJECT":
        return "not_viable"
    return "needs_review"


def _estimate_confidence(
    lead_score: int,
    retrieval: RetrieveResult,
    tools: ToolPhaseResult,
    plan: PlanResult,
) -> float:
    """
    Heuristic 0..1 confidence for escalation.

    Boosts for citations, tool results, and high lead scores; penalizes missing fields.
    """
    confidence = CONFIDENCE_BASE
    if retrieval.citations:
        confidence += CONFIDENCE_CITATION_BOOST
    if any([tools.sol, tools.conflict, tools.estimate, tools.routing]):
        confidence += CONFIDENCE_TOOL_BOOST
    if lead_score >= CONFIDENCE_SCORE_BOOST_MIN:
        confidence += CONFIDENCE_SCORE_BOOST
    confidence -= CONFIDENCE_MISSING_FIELD_PENALTY * min(
        len(plan.missing_fields), CONFIDENCE_MISSING_FIELD_CAP
    )
    return round(max(0.0, min(1.0, confidence)), 3)


def decide(
    facts: IntakeFacts,
    plan: PlanResult,
    retrieval: RetrieveResult,
    tools: ToolPhaseResult,
    *,
    confidence_threshold: float,
    narrative: str | None = None,
) -> DecisionResult:
    """
    Map canonical score_lead output to agent DecisionResult.

    confidence_threshold is intentionally unused here (self_check / respond escalate
    on low confidence); lead-score cutoffs live in scoring/constants.
    """
    del confidence_threshold  # used by self_check; scoring thresholds are in scoring/constants
    ctx = build_lead_score_context(facts, plan, retrieval, tools, narrative=narrative)
    scored = score_lead(ctx)

    routing = tools.routing or {}
    attorney = str(routing.get("attorney_name") or "").strip()
    if attorney:
        routing_recommendation = f"Route to {attorney}."
    else:
        routing_recommendation = str(routing.get("motivation") or scored.explanation[:120])

    return DecisionResult(
        lead_score=scored.lead_score,
        case_viability=_map_viability(scored.decision),
        routing_recommendation=routing_recommendation,
        next_steps=_derive_next_steps(plan, tools, scored.decision),
        confidence=_estimate_confidence(scored.lead_score, retrieval, tools, plan),
    )
