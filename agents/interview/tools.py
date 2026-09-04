"""Agno tools available to the interview agent.

Interview screening reuses the intake tool set via IntakeAgent.
"""

from __future__ import annotations

from agents.intake.tools import ALLOWED_TOOL_NAMES
from agents.intake.tools import TOOLS as INTAKE_TOOLS

TOOLS = list(INTAKE_TOOLS)

__all__ = ["ALLOWED_TOOL_NAMES", "TOOLS"]
