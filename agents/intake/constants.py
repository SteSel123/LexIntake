"""Shared prompt constants for the intake agent."""

from __future__ import annotations

from pathlib import Path

from agents.prompts import load_prompts

PROMPTS = load_prompts(Path(__file__).with_name("prompts.xml"))
LEGAL_DISCLAIMER = PROMPTS.text("legal_disclaimer")
UNCERTAINTY_ESCALATION = PROMPTS.text("uncertainty_escalation")
INTAKE_INSTRUCTIONS = PROMPTS.items("instructions")
DEFAULT_CONFIDENCE_THRESHOLD = 0.55
