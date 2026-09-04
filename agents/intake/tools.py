"""Agno tools available to the intake agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / "tools"
for path in (str(ROOT), str(TOOLS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from check_statute_of_limitations import (  # noqa: E402
    CheckSOLInput,
    check_statute_of_limitations,
)
from conflict_check import ConflictCheckInput, conflict_check  # noqa: E402
from estimate_case_value import EstimateCaseValueInput, estimate_case_value  # noqa: E402
from route_lead import RouteLeadInput, route_lead  # noqa: E402
from web_search_fallback import WebSearchFallbackInput, web_search_fallback  # noqa: E402

TOOLS = [
    check_statute_of_limitations,
    conflict_check,
    estimate_case_value,
    route_lead,
    web_search_fallback,
]

ALLOWED_TOOL_NAMES = frozenset(
    {
        "check_statute_of_limitations",
        "conflict_check",
        "estimate_case_value",
        "route_lead",
        "web_search_fallback",
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
        except Exception:  # noqa: BLE001
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

        if "web_search_fallback" in plan.tools_to_call:
            fallback = web_search_fallback.entrypoint(
                WebSearchFallbackInput(
                    query=plan.retrieval_query or case_type or "intake guidance"
                )
            )
            result.web_fallback = parse_tool_payload(fallback)
            _log("web_search_fallback used")
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
    "WebSearchFallbackInput",
    "check_statute_of_limitations",
    "conflict_check",
    "estimate_case_value",
    "route_lead",
    "web_search_fallback",
]
