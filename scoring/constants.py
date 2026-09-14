"""
Named thresholds for deterministic lead scoring.

Centralizes magic numbers so score_lead(), context builders, and agent
confidence logic stay aligned and tunable without hunting through call sites.
"""

from __future__ import annotations

# ---- Decision bands (score_lead) -------------------------------------------
# Map clamped 0–100 score to SCHEDULE_CONSULT / REVIEW / REJECT outcomes.
SCORE_SCHEDULE_MIN = 70
SCORE_REVIEW_MIN = 40

# ---- Case value contribution (max 40 pts + optional high-value boost) ----
CASE_VALUE_DIVISOR = 2500.0  # estimate / divisor → points, capped at CASE_VALUE_MAX_POINTS
CASE_VALUE_MAX_POINTS = 40.0
HIGH_VALUE_THRESHOLD = 100_000  # flat boost when estimate exceeds this USD amount
HIGH_VALUE_BOOST = 10

# ---- Acceptance criteria contribution (max 30 pts) -------------------------
ACCEPTANCE_POINTS_PER_MATCH = 5
ACCEPTANCE_PENALTY_PER_UNMET = 10
ACCEPTANCE_MAX_POINTS = 30.0

# ---- Practice area match -------------------------------------------------
PRACTICE_MATCH_POINTS = 20.0
PRACTICE_MISMATCH_FACTOR = 0.5  # multiplicative penalty when area does not match firm focus

# ---- Attorney routing boost ------------------------------------------------
ATTORNEY_AVAILABLE_BOOST = 5  # small bump when route_lead assigned someone

# ---- SOL urgency (valid claims nearing deadline) -------------------------
SOL_URGENCY_DAYS = 60
SOL_URGENCY_BOOST = 10

# ---- Missing-data penalty --------------------------------------------------
# Applied once when required tool fields are absent (triggers human escalation).
MISSING_DATA_PENALTY = 15

# ---- User-facing explanation fragments -----------------------------------
# Shared by score_lead explanations and uncertain-narrative post-processor.
INSUFFICIENT_DATA_MSG = "Insufficient data — escalating to a human intake specialist."
SCORING_SCOPE_DISCLAIMER = (
    "This scoring evaluates intake viability only and does not prescribe legal action."
)

# ---- Agent confidence mapping (separate from lead_score 0–100) -------------
# Used by intake agents to modulate response confidence from score + evidence.
CONFIDENCE_BASE = 0.35
CONFIDENCE_CITATION_BOOST = 0.15
CONFIDENCE_TOOL_BOOST = 0.10
CONFIDENCE_SCORE_BOOST = 0.10
CONFIDENCE_SCORE_BOOST_MIN = 65  # lead_score threshold for CONFIDENCE_SCORE_BOOST
CONFIDENCE_MISSING_FIELD_PENALTY = 0.05
CONFIDENCE_MISSING_FIELD_CAP = 4
# Backward-compatible alias (was misused as 0.65 vs lead_score 0–100)
CONFIDENCE_VIABILITY_HIGH = CONFIDENCE_SCORE_BOOST_MIN
