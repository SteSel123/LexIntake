"""
LexIntake Agno tools.

Registers intake screening tools (SOL, conflict, valuation, routing)
for the agent runtime. Supports both package imports and script-style execution.
"""

from __future__ import annotations

# Dual import path: package mode (tests, app) vs running a tool module directly.
try:
    from .check_statute_of_limitations import check_statute_of_limitations
    from .conflict_check import conflict_check
    from .estimate_case_value import estimate_case_value
    from .route_lead import route_lead
except ImportError:  # pragma: no cover - script-style imports
    from check_statute_of_limitations import check_statute_of_limitations
    from conflict_check import conflict_check
    from estimate_case_value import estimate_case_value
    from route_lead import route_lead

ALL_TOOLS = [
    check_statute_of_limitations,
    conflict_check,
    estimate_case_value,
    route_lead,
]

__all__ = [
    "ALL_TOOLS",
    "check_statute_of_limitations",
    "conflict_check",
    "estimate_case_value",
    "route_lead",
]
