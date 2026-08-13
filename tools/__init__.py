"""LexIntake Agno tools."""

from __future__ import annotations

try:
    from .check_statute_of_limitations import check_statute_of_limitations
    from .conflict_check import conflict_check
    from .estimate_case_value import estimate_case_value
    from .route_lead import route_lead
    from .web_search_fallback import web_search_fallback
except ImportError:  # pragma: no cover - script-style imports
    from check_statute_of_limitations import check_statute_of_limitations
    from conflict_check import conflict_check
    from estimate_case_value import estimate_case_value
    from route_lead import route_lead
    from web_search_fallback import web_search_fallback

ALL_TOOLS = [
    check_statute_of_limitations,
    conflict_check,
    estimate_case_value,
    route_lead,
    web_search_fallback,
]

__all__ = [
    "ALL_TOOLS",
    "check_statute_of_limitations",
    "conflict_check",
    "estimate_case_value",
    "route_lead",
    "web_search_fallback",
]
