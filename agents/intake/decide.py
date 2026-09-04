"""Intake-phase scoring: lead score, viability, routing, next steps."""

from __future__ import annotations

from typing import Literal

from agents.intake.models import DecisionResult, IntakeFacts, PlanResult, RetrieveResult, ToolPhaseResult


def decide(
    facts: IntakeFacts,
    plan: PlanResult,
    retrieval: RetrieveResult,
    tools: ToolPhaseResult,
    *,
    confidence_threshold: float,
) -> DecisionResult:
    """Lead score, viability, routing, next steps."""
    del facts
    score = 50
    confidence = 0.35
    next_steps: list[str] = []

    if retrieval.citations:
        score += min(10, 2 * len(retrieval.citations))
        confidence += 0.15

    sol = tools.sol or {}
    if sol:
        confidence += 0.15
        if sol.get("valid") is True and sol.get("expires_in", -1) != -1:
            score += 20
            next_steps.append("Confirm incident timeline documents for SOL file.")
        elif sol.get("valid") is False:
            score -= 35
            next_steps.append("Flag potential SOL issue for attorney review.")
        else:
            score -= 5
            next_steps.append("SOL uncertain — verify with attorney.")

    conflict = tools.conflict or {}
    if conflict:
        confidence += 0.1
        if conflict.get("conflict"):
            score -= 30
            next_steps.append("Conflict detected — do not discuss case merits; escalate.")
        else:
            score += 5

    estimate = tools.estimate or {}
    if estimate:
        confidence += 0.1
        est = float(estimate.get("estimate") or 0)
        explanation = str(estimate.get("explanation") or "")
        if "insufficient data" in explanation.lower():
            score -= 5
            next_steps.append("Insufficient comps — request more injury/damage detail.")
        elif est > 0:
            score += 15 if est >= 50_000 else 8

    routing = tools.routing or {}
    attorney = str(routing.get("attorney_name") or "").strip()
    if attorney:
        score += 10
        confidence += 0.1
        routing_recommendation = f"Route to {attorney}."
        next_steps.append(f"Schedule intake follow-up with {attorney}.")
    else:
        routing_recommendation = str(routing.get("motivation") or "Manual routing required.")
        next_steps.append("No attorney auto-assigned — human routing required.")

    if plan.missing_fields:
        score -= 5 * min(len(plan.missing_fields), 4)
        confidence -= 0.05 * len(plan.missing_fields)
        next_steps.append("Collect missing intake fields before engagement.")

    score = max(0, min(100, score))
    confidence = max(0.0, min(1.0, confidence))

    if conflict.get("conflict"):
        viability: Literal["viable", "not_viable", "needs_review"] = "needs_review"
    elif sol.get("valid") is False:
        viability = "not_viable"
    elif score >= 65 and confidence >= confidence_threshold:
        viability = "viable"
    elif score < 40:
        viability = "not_viable"
    else:
        viability = "needs_review"

    if not next_steps:
        next_steps.append("Continue structured intake questions.")

    return DecisionResult(
        lead_score=score,
        case_viability=viability,
        routing_recommendation=routing_recommendation,
        next_steps=next_steps,
        confidence=round(confidence, 3),
    )
