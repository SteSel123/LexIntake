"""Shared prompt constants and tuning thresholds for the intake agent.

Loads ``prompts.xml`` once at import time and exposes disclaimer text, instruction
lists, and numeric limits used by plan/respond/guardrail stages.
"""

from __future__ import annotations

from pathlib import Path

from agents.prompts import load_prompts

PROMPTS = load_prompts(Path(__file__).with_name("prompts.xml"))
LEGAL_DISCLAIMER = PROMPTS.text("legal_disclaimer")
UNCERTAINTY_ESCALATION = PROMPTS.text("uncertainty_escalation")
INTAKE_INSTRUCTIONS = PROMPTS.items("instructions")
# Below this decision confidence, guardrails flag escalation to a human
DEFAULT_CONFIDENCE_THRESHOLD = 0.55

# Plan / respond thresholds
TOP_K_MIN = 5  # Minimum KB chunks to retrieve when search is needed
TOP_K_MAX = 10  # Upper cap to control latency and context size
ESCALATE_MISSING_MIN = 5  # Escalate when this many required fields are still missing
RESPOND_QUESTIONS_MAX = 3  # Cap follow-up questions in the final response

# Placeholder values used when free-text extract cannot identify parties
SENTINEL_NAME = "Demo Prospect"
SENTINEL_PARTY = "Unknown Party"
INTERVIEW_PROSPECT_NAME = "Interview Prospect"

# US state / DC codes accepted as jurisdiction (validation only; LLM fills the field).
US_STATE_CODES = frozenset(
    {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }
)
