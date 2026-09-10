"""
LexIntake lead scoring package.

Public surface for deterministic intake scoring: build context from pipeline
artifacts, compute a 0–100 lead score, and apply narrative-uncertainty overrides.
"""

from .domain import apply_uncertain_narrative_override, is_uncertain_narrative
from .lead_scoring import LeadScoreContext, LeadScoreOutput, score_lead

__all__ = [
    "LeadScoreContext",
    "LeadScoreOutput",
    "apply_uncertain_narrative_override",
    "is_uncertain_narrative",
    "score_lead",
]
