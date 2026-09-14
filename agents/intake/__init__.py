"""Intake screening agent package.

Exports ``IntakeAgent``, fact/response models, prompt constants, and fact helpers
used by both staff-facing screening and the interview flow.
"""

from agents.intake.agent import IntakeAgent, build_default_agent
from agents.intake.constants import LEGAL_DISCLAIMER, UNCERTAINTY_ESCALATION
from agents.intake.fact_parse import apply_extracted_fields, is_iso_date, is_valid_jurisdiction
from agents.intake.models import IntakeFacts, IntakeResponse

__all__ = [
    "LEGAL_DISCLAIMER",
    "UNCERTAINTY_ESCALATION",
    "IntakeAgent",
    "IntakeFacts",
    "IntakeResponse",
    "apply_extracted_fields",
    "build_default_agent",
    "is_iso_date",
    "is_valid_jurisdiction",
]
