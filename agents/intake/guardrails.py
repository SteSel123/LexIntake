"""Disclaimer, citation, and escalation checks for intake responses."""

from __future__ import annotations

from agents.intake.constants import LEGAL_DISCLAIMER, PROMPTS, UNCERTAINTY_ESCALATION
from agents.intake.models import DecisionResult, KBCitation, PlanResult, RetrieveResult, SelfCheckResult

BANNED_PATTERNS = (
    "i am certain the statute",
    "guaranteed win",
    "you should sue",
)


def self_check(
    response_draft: str,
    retrieval: RetrieveResult,
    decision: DecisionResult,
    plan: PlanResult,
    *,
    confidence_threshold: float,
) -> SelfCheckResult:
    """Validate guardrails, citations, and uncertainty handling."""
    issues: list[str] = []
    lowered = response_draft.lower()
    disclaimer_ok = "not legal advice" in lowered and "licensed attorney" in lowered
    if not disclaimer_ok:
        issues.append("Missing mandatory legal disclaimer.")

    if plan.need_retrieval and not retrieval.citations:
        issues.append("Retrieval was required but no KB citations were produced.")

    for pattern in BANNED_PATTERNS:
        if pattern in lowered:
            issues.append(f"Unsafe / advisory language detected: {pattern}")

    escalate = (
        plan.escalate
        or decision.confidence < confidence_threshold
        or decision.case_viability == "needs_review"
        or any("conflict" in issue.lower() for issue in issues)
    )
    if decision.confidence < confidence_threshold:
        issues.append("Confidence below threshold.")

    return SelfCheckResult(
        ok=len(issues) == 0,
        issues=issues,
        escalate=escalate,
        disclaimers_present=disclaimer_ok,
        citations_present=bool(retrieval.citations),
    )


def enforce_message_guardrails(
    message: str,
    *,
    escalate: bool,
    citations: list[KBCitation],
) -> str:
    """Always append disclaimer, escalation line, and citations when missing."""
    if LEGAL_DISCLAIMER.lower() not in message.lower() and "not legal advice" not in message.lower():
        message = f"{message}\n\n{LEGAL_DISCLAIMER}"
    if escalate and UNCERTAINTY_ESCALATION not in message:
        message = f"{message}\n\n{UNCERTAINTY_ESCALATION}"
    if citations and "chunk_id=" not in message and "KB citation" not in message:
        cite_lines = "\n".join(
            PROMPTS.text(
                "citation_line",
                chunk_id=cite.chunk_id,
                practice_area=cite.practice_area,
                doc_type=cite.doc_type,
            )
            for cite in citations
        )
        message = f"{message}\n\n{PROMPTS.text('citations_header')}\n{cite_lines}"
    return message
