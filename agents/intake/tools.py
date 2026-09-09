"""Agno tools available to the intake agent."""

from __future__ import annotations

import json
from typing import Any, Callable

from agents.intake.constants import FALLBACK_TOOL_ALIASES, FALLBACK_TOOL_NAME
from tools.check_statute_of_limitations import (
    CheckSOLInput,
    check_statute_of_limitations,
)
from tools.conflict_check import ConflictCheckInput, conflict_check
from tools.estimate_case_value import EstimateCaseValueInput, estimate_case_value
from tools.kb_docs_fallback import (
    KbDocsFallbackInput,
    WebSearchFallbackInput,
    kb_docs_fallback,
    web_search_fallback,
)
from tools.route_lead import RouteLeadInput, route_lead

TOOLS = [
    check_statute_of_limitations,
    conflict_check,
    estimate_case_value,
    route_lead,
    kb_docs_fallback,
]

ALLOWED_TOOL_NAMES = frozenset(
    {
        "check_statute_of_limitations",
        "conflict_check",
        "estimate_case_value",
        "route_lead",
        *FALLBACK_TOOL_ALIASES,
    }
)


def parse_tool_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"raw": value}
        except json.JSONDecodeError:
            return {"raw": value}
    return {"raw": str(value)}


def run_deterministic(
    facts: Any,
    plan: Any,
    *,
    log: Callable[[str], None] | None = None,
) -> Any:
    """Invoke planned Agno tools and merge outputs."""
    from agents.intake.models import ToolPhaseResult

    result = ToolPhaseResult()
    case_type = facts.case_type or facts.practice_area or ""

    def _log(detail: str) -> None:
        if log:
            log(detail)

    try:
        if "check_statute_of_limitations" in plan.tools_to_call and facts.incident_date:
            sol = check_statute_of_limitations.entrypoint(
                CheckSOLInput(
                    jurisdiction=facts.jurisdiction or "",
                    case_type=case_type,
                    incident_date=facts.incident_date,
                )
            )
            result.sol = parse_tool_payload(sol)
            _log(f"SOL={result.sol}")

        if "conflict_check" in plan.tools_to_call and facts.name:
            conflict = conflict_check.entrypoint(
                ConflictCheckInput(
                    name=facts.name,
                    opposing_party=facts.opposing_party or "",
                )
            )
            result.conflict = parse_tool_payload(conflict)
            _log(f"conflict={result.conflict.get('conflict')}")

        if "estimate_case_value" in plan.tools_to_call and facts.damages is not None:
            estimate = estimate_case_value.entrypoint(
                EstimateCaseValueInput(
                    case_type=case_type,
                    severity=facts.severity or "medium",
                    damages=int(facts.damages),
                )
            )
            result.estimate = parse_tool_payload(estimate)
            _log(f"estimate={result.estimate.get('estimate')}")

        if "route_lead" in plan.tools_to_call:
            routing = route_lead.entrypoint(
                RouteLeadInput(
                    practice_area=facts.practice_area or case_type,
                    priority=facts.priority,
                )
            )
            result.routing = parse_tool_payload(routing)
            _log(f"routing={result.routing.get('attorney_name')}")

        planned_fallback = FALLBACK_TOOL_ALIASES.intersection(plan.tools_to_call or [])
        if planned_fallback:
            fallback = kb_docs_fallback.entrypoint(
                KbDocsFallbackInput(
                    query=plan.retrieval_query or case_type or "intake guidance"
                )
            )
            result.web_fallback = parse_tool_payload(fallback)
            _log(f"{FALLBACK_TOOL_NAME} used")
    except Exception as exc:  # noqa: BLE001
        _log(f"error={exc}")

    return result


__all__ = [
    "ALLOWED_TOOL_NAMES",
    "parse_tool_payload",
    "run_deterministic",
    "CheckSOLInput",
    "ConflictCheckInput",
    "EstimateCaseValueInput",
    "RouteLeadInput",
    "TOOLS",
    "KbDocsFallbackInput",
    "WebSearchFallbackInput",
    "check_statute_of_limitations",
    "conflict_check",
    "estimate_case_value",
    "route_lead",
    "kb_docs_fallback",
    "web_search_fallback",
]
