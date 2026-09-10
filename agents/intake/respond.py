"""
Respond phase: assemble IntakeResponse from pipeline artifacts.

Prefers an LLM-written ScreeningMessage when available; otherwise builds a
templated summary, then runs message guardrails (disclaimer / escalation).
"""

from __future__ import annotations

from typing import Callable

from agents.intake.constants import (
    LEGAL_DISCLAIMER,
    PROMPTS,
    RESPOND_QUESTIONS_MAX,
    UNCERTAINTY_ESCALATION,
)
from agents.intake.guardrails import enforce_message_guardrails
from agents.intake.models import (
    DecisionResult,
    IntakeFacts,
    IntakeResponse,
    PlanResult,
    RetrieveResult,
    SelfCheckResult,
    ToolPhaseResult,
)


def tool_summary_lines(tools: ToolPhaseResult) -> list[str]:
    """Short bullet lines describing each tool payload for the templated message."""
    parts: list[str] = []
    if tools.sol:
        parts.append(
            f"SOL check: valid={tools.sol.get('valid')}, "
            f"expires_in={tools.sol.get('expires_in')} days."
        )
    if tools.conflict:
        parts.append(f"Conflict check: conflict={tools.conflict.get('conflict')}.")
    if tools.estimate:
        parts.append(
            f"Value estimate: ${float(tools.estimate.get('estimate') or 0):,.2f} "
            f"(range ${float(tools.estimate.get('range_low') or 0):,.2f}"
            f"–${float(tools.estimate.get('range_high') or 0):,.2f})."
        )
    if tools.routing:
        parts.append(f"Routing: {tools.routing.get('attorney_name') or 'unassigned'}.")
    return parts


def build_templated_message(
    facts: IntakeFacts,
    plan: PlanResult,
    retrieval: RetrieveResult,
    tools: ToolPhaseResult,
    decision: DecisionResult,
    *,
    escalate: bool,
    questions: list[str],
) -> str:
    """Deterministic screening summary from prompts.xml (no LLM)."""
    citation_lines = [
        PROMPTS.text(
            "citation_line",
            chunk_id=cite.chunk_id,
            practice_area=cite.practice_area,
            doc_type=cite.doc_type,
        )
        for cite in retrieval.citations
    ]
    question_block = ""
    if questions:
        question_block = "Next questions:\n" + "\n".join(f"- {q}" for q in questions)
    return PROMPTS.user(
        "screening_summary",
        matter=facts.practice_area or facts.case_type or "unspecified",
        jurisdiction=facts.jurisdiction or "unspecified",
        lead_score=decision.lead_score,
        case_viability=decision.case_viability,
        routing_recommendation=decision.routing_recommendation,
        tool_results=chr(10).join(f"- {p}" for p in tool_summary_lines(tools))
        or PROMPTS.text("no_tools"),
        citations="\n".join(citation_lines) if citation_lines else PROMPTS.text("no_citations"),
        next_steps=chr(10).join(f"- {s}" for s in decision.next_steps),
        question_block=question_block,
        escalation_line=UNCERTAINTY_ESCALATION if escalate else "",
        legal_disclaimer=LEGAL_DISCLAIMER,
        reminder=PROMPTS.text("screening_reminder"),
    ).strip()


def build_response(
    facts: IntakeFacts,
    plan: PlanResult,
    retrieval: RetrieveResult,
    tools: ToolPhaseResult,
    decision: DecisionResult,
    check: SelfCheckResult,
    *,
    confidence_threshold: float,
    provider: str,
    model_id: str,
    llm_cost: float,
    input_tokens: int,
    output_tokens: int,
    write_message: Callable[..., str] | None = None,
    use_llm: bool = True,
    llm_ready: bool = False,
    log: Callable[[str, str], None] | None = None,
) -> IntakeResponse:
    """
    Build the final IntakeResponse for API / UI.

    Escalates when self_check says so or confidence is below threshold.
    Message path: optional LLM write → template fallback → guardrails.
    """
    escalate = check.escalate or decision.confidence < confidence_threshold
    questions = plan.questions[:RESPOND_QUESTIONS_MAX]
    used_llm = False
    message = ""

    # Prefer LLM wording when the caller allows it and a model is configured.
    if use_llm and llm_ready and write_message is not None:
        message = write_message(
            facts, retrieval, tools, decision, escalate=escalate, questions=questions
        )
        used_llm = bool(message)

    # Template path: always available (also used for the pre-self_check draft).
    if not message:
        message = build_templated_message(
            facts, plan, retrieval, tools, decision, escalate=escalate, questions=questions
        )

    # Enforce disclaimer / escalation language and citation hygiene.
    message = enforce_message_guardrails(
        message, escalate=escalate, citations=retrieval.citations
    )
    response = IntakeResponse(
        message=message,
        disclaimer=LEGAL_DISCLAIMER,
        lead_score=decision.lead_score,
        case_viability=decision.case_viability,
        routing_recommendation=decision.routing_recommendation,
        next_steps=decision.next_steps,
        citations=retrieval.citations,
        tool_results=tools.model_dump(),
        escalate=escalate,
        confidence=decision.confidence,
        questions=questions,
        provider=provider,
        model_id=str(model_id or ""),
        cost=float(llm_cost),
        input_tokens=int(input_tokens),
        output_tokens=int(output_tokens),
        used_llm=used_llm,
    )
    if log:
        log("respond", f"escalate={escalate} score={decision.lead_score} llm={used_llm}")
    return response
