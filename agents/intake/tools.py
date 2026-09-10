"""
Agno tools available to the intake agent.

`TOOLS` is registered on the Agno Agent for the agentic path.
`run_deterministic` calls the same tools from `plan.tools_to_call` without an LLM.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from tools.check_statute_of_limitations import (
    CheckSOLInput,
    check_statute_of_limitations,
)
from tools.conflict_check import ConflictCheckInput, conflict_check
from tools.estimate_case_value import EstimateCaseValueInput, estimate_case_value
from tools.route_lead import RouteLeadInput, route_lead

# Functions Agno may invoke when tool_choice=auto.
TOOLS = [
    check_statute_of_limitations,
    conflict_check,
    estimate_case_value,
    route_lead,
]

# Whitelist used when the LLM proposes tools during plan refine.
ALLOWED_TOOL_NAMES = frozenset(
    {
        "check_statute_of_limitations",
        "conflict_check",
        "estimate_case_value",
        "route_lead",
    }
)


def parse_tool_payload(value: Any) -> dict[str, Any]:
    """Normalize tool return values (Pydantic / dict / JSON string) into a plain dict."""
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
    """
    Invoke planned tools in fixed order and merge into ToolPhaseResult.

    Used as the non-LLM path and as a fill-in after agentic tool runs.
    Errors are logged but do not raise — intake continues with partial results.
    """
    from agents.intake.models import ToolPhaseResult

    result = ToolPhaseResult()
    case_type = facts.case_type or facts.practice_area or ""

    def _log(detail: str) -> None:
        if log:
            log(detail)

    try:
        # Statute of limitations — needs jurisdiction, case type, and a valid ISO date.
        if "check_statute_of_limitations" in plan.tools_to_call and facts.incident_date:
            from agents.intake.fact_parse import infer_incident_date, is_iso_date

            iso_date = (
                facts.incident_date
                if is_iso_date(facts.incident_date)
                else infer_incident_date(facts.incident_date)
            )
            if not iso_date:
                _log(f"SOL skipped: invalid incident_date={facts.incident_date!r}")
            else:
                sol = check_statute_of_limitations.entrypoint(
                    CheckSOLInput(
                        jurisdiction=facts.jurisdiction or "",
                        case_type=case_type,
                        incident_date=iso_date,
                    )
                )
                result.sol = parse_tool_payload(sol)
                _log(f"SOL={result.sol}")

        # Conflict of interest — client name vs opposing party.
        if "conflict_check" in plan.tools_to_call and facts.name:
            conflict = conflict_check.entrypoint(
                ConflictCheckInput(
                    name=facts.name,
                    opposing_party=facts.opposing_party or "",
                )
            )
            result.conflict = parse_tool_payload(conflict)
            _log(f"conflict={result.conflict.get('conflict')}")

        # Settlement / damages range from comparable cases.
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

        # Assign an attorney / queue by practice area.
        if "route_lead" in plan.tools_to_call:
            routing = route_lead.entrypoint(
                RouteLeadInput(
                    practice_area=facts.practice_area or case_type,
                    priority=facts.priority,
                )
            )
            result.routing = parse_tool_payload(routing)
            _log(f"routing={result.routing.get('attorney_name')}")
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
    "check_statute_of_limitations",
    "conflict_check",
    "estimate_case_value",
    "route_lead",
]
