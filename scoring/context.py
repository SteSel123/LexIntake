"""Build LeadScoreContext from intake pipeline artifacts (single source of truth)."""

from __future__ import annotations

from typing import Any

from agents.intake.models import (
    IntakeFacts,
    IntakeResponse,
    PlanResult,
    RetrieveResult,
    ToolPhaseResult,
)
from scoring.domain import is_uncertain_narrative
from tools.common import load_acceptance_criteria

# Heuristic signals mapped to KB must_have language (acceptance_criteria.json).
_FACT_SIGNALS: tuple[tuple[str, str], ...] = (
    ("name", "Client identity provided"),
    ("opposing_party", "Identifiable at-fault party or liable entity"),
    ("jurisdiction", "Jurisdiction confirmed for screening"),
    ("incident_date", "Incident date within applicable SOL for the jurisdiction"),
    ("damages", "Documented damages or injury value stated"),
    ("practice_area", "Practice area identified for intake routing"),
)


def build_acceptance_criteria(
    facts: IntakeFacts,
    *,
    narrative: str | None = None,
    practice_area: str | None = None,
) -> dict[str, Any]:
    """Derive acceptance payload from intake facts and KB must_have list."""
    area = practice_area or facts.practice_area or facts.case_type
    matched: list[str] = []
    unmet: list[str] = []

    values = facts.model_dump()
    for field, label in _FACT_SIGNALS:
        if values.get(field) not in (None, "", []):
            matched.append(label)

    kb_entry = load_acceptance_criteria(area)
    must_have: list[str] = []
    if isinstance(kb_entry, dict):
        must_have = list(kb_entry.get("must_have") or [])

    if must_have:
        for criterion in must_have:
            if criterion in matched:
                continue
            slug = criterion.lower()
            if "jurisdiction" in slug and facts.jurisdiction:
                matched.append(criterion)
            elif "sol" in slug and facts.incident_date:
                matched.append(criterion)
            elif "party" in slug or "fault" in slug:
                if facts.opposing_party:
                    matched.append(criterion)
            elif "injury" in slug or "medical" in slug:
                if facts.damages or (facts.severity and facts.severity != "low"):
                    matched.append(criterion)
            elif "causal" in slug and facts.narrative:
                matched.append(criterion)
            elif "employer" in slug and facts.opposing_party:
                matched.append(criterion)

    if must_have:
        for criterion in must_have:
            if criterion not in matched:
                unmet.append(criterion)

    if is_uncertain_narrative(narrative or facts.narrative):
        if "Jurisdiction confirmed for screening" not in matched:
            unmet.append("Jurisdiction confirmed for screening")
        matched = [m for m in matched if m != "Jurisdiction confirmed for screening"]

    return {
        "matched": list(dict.fromkeys(matched)),
        "unmet_required": list(dict.fromkeys(unmet)),
        "practice_area_match": bool(area),
    }


def build_lead_score_context(
    facts: IntakeFacts,
    plan: PlanResult,
    retrieval: RetrieveResult,
    tools: ToolPhaseResult,
    *,
    narrative: str | None = None,
) -> dict[str, Any]:
    """Assemble the dict consumed by score_lead()."""
    del plan  # reserved for future plan-aware acceptance rules
    citations = [
        {
            "chunk_id": c.chunk_id,
            "practice_area": c.practice_area,
            "doc_type": c.doc_type,
        }
        for c in retrieval.citations
    ]
    routing = tools.routing or {}
    return {
        "sol": tools.sol or {},
        "conflict": tools.conflict or {},
        "case_value": tools.estimate or {},
        "practice_area": facts.practice_area or facts.case_type or "Unknown",
        "acceptance_criteria": build_acceptance_criteria(
            facts, narrative=narrative, practice_area=facts.practice_area
        ),
        "recommended_attorney": routing.get("attorney_name"),
        "practice_area_match": bool(facts.practice_area or facts.case_type),
        "citations": citations,
    }


def build_lead_score_context_from_response(
    facts: IntakeFacts,
    response: IntakeResponse,
    *,
    narrative: str | None = None,
) -> dict[str, Any]:
    """Build score context from a completed IntakeResponse (API/UI path)."""
    tools_raw = response.tool_results or {}
    tools = ToolPhaseResult(
        sol=tools_raw.get("sol"),
        conflict=tools_raw.get("conflict"),
        estimate=tools_raw.get("estimate"),
        routing=tools_raw.get("routing"),
    )
    retrieval = RetrieveResult(citations=list(response.citations or []))
    return build_lead_score_context(
        facts,
        PlanResult(),
        retrieval,
        tools,
        narrative=narrative or facts.narrative,
    )
