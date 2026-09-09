"""
Plan phase: decide questions, retrieval need, tools, and escalation.

This module is intentionally LLM-free. `IntakeAgent._llm_refine_plan` may
adjust the returned PlanResult afterward when a model is available.
"""

from __future__ import annotations

from agents.intake.constants import (
    ESCALATE_MISSING_MIN,
    FALLBACK_TOOL_NAME,
    PROMPTS,
)
from agents.intake.models import IntakeFacts, PlanResult
from tools.common import match_practice_area


def build_plan(facts: IntakeFacts) -> PlanResult:
    """
    Build a PlanResult from intake facts only (rules, no LLM).

    - missing_fields / questions: from empty required intake fields
    - tools_to_call / doc_types: which checks and KB doc types make sense
    - need_retrieval: whether vector search should run
    - escalate: too many missing fields → human review
    """
    missing: list[str] = []
    questions: list[str] = []
    values = facts.model_dump()
    # Each configured field maps to a follow-up question when absent.
    for field, question in PROMPTS.mapping("field_questions").items():
        if values.get(field) in (None, "", []):
            missing.append(field)
            questions.append(question)

    case_type = facts.case_type or facts.practice_area
    practice_area = match_practice_area(case_type or "") if case_type else None
    tools: list[str] = []
    doc_types: list[str] = []
    # Retrieve when we have a known practice area or free-text narrative to search on.
    need_retrieval = bool(practice_area or facts.narrative)

    # Tool selection: only schedule checks when the required inputs are present.
    if facts.jurisdiction and case_type and facts.incident_date:
        tools.append("check_statute_of_limitations")
        doc_types.append("sol_rules")
    if facts.name and facts.opposing_party:
        tools.append("conflict_check")
    if case_type and facts.damages is not None:
        tools.append("estimate_case_value")
        doc_types.append("past_case")
    if practice_area or facts.practice_area:
        tools.append("route_lead")
        doc_types.append("acceptance_criteria")
    escalate = len(missing) >= ESCALATE_MISSING_MIN
    # Unknown practice area → KB fallback search instead of specialized filters.
    if not practice_area and case_type:
        tools.append(FALLBACK_TOOL_NAME)

    # Retrieval query blends structured fields with a fixed legal-intake bias phrase.
    query_parts = [
        p
        for p in [
            practice_area or case_type,
            facts.jurisdiction,
            facts.narrative,
            "intake acceptance criteria statute settlement",
        ]
        if p
    ]
    return PlanResult(
        missing_fields=missing,
        questions=questions,
        need_retrieval=need_retrieval,
        tools_to_call=tools,
        escalate=escalate,
        retrieval_query=" ".join(query_parts).strip(),
        doc_types=sorted(set(doc_types)) or ["acceptance_criteria", "sol_rules", "faq"],
        reasoning=(
            f"missing={missing}; practice_area={practice_area}; "
            f"tools={tools}; retrieve={need_retrieval}"
        ),
    )
