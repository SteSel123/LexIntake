"""Shared prompt constants for the intake agent."""

from __future__ import annotations

from pathlib import Path

from agents.prompts import load_prompts

PROMPTS = load_prompts(Path(__file__).with_name("prompts.xml"))
LEGAL_DISCLAIMER = PROMPTS.text("legal_disclaimer")
UNCERTAINTY_ESCALATION = PROMPTS.text("uncertainty_escalation")
INTAKE_INSTRUCTIONS = PROMPTS.items("instructions")
DEFAULT_CONFIDENCE_THRESHOLD = 0.55

# Plan / respond thresholds
TOP_K_MIN = 5
TOP_K_MAX = 10
ESCALATE_MISSING_MIN = 5
RESPOND_QUESTIONS_MAX = 3

# Placeholder values used when free-text parse cannot identify parties
SENTINEL_NAME = "Demo Prospect"
SENTINEL_PARTY = "Unknown Party"
INTERVIEW_PROSPECT_NAME = "Interview Prospect"

# Agno tool name for Postgres kb_docs fallback (legacy alias kept in ALLOWED_TOOL_NAMES)
FALLBACK_TOOL_NAME = "kb_docs_fallback"
FALLBACK_TOOL_ALIASES = frozenset({"kb_docs_fallback", "web_search_fallback"})
