"""Named thresholds for deterministic lead scoring."""

from __future__ import annotations

# Decision bands (score_lead)
SCORE_SCHEDULE_MIN = 70
SCORE_REVIEW_MIN = 40

# Case value contribution
CASE_VALUE_DIVISOR = 2500.0
CASE_VALUE_MAX_POINTS = 40.0
HIGH_VALUE_THRESHOLD = 100_000
HIGH_VALUE_BOOST = 10

# Acceptance criteria contribution
ACCEPTANCE_POINTS_PER_MATCH = 5
ACCEPTANCE_PENALTY_PER_UNMET = 10
ACCEPTANCE_MAX_POINTS = 30.0

# Practice area match
PRACTICE_MATCH_POINTS = 20.0
PRACTICE_MISMATCH_FACTOR = 0.5

# Attorney routing boost
ATTORNEY_AVAILABLE_BOOST = 5

# SOL urgency
SOL_URGENCY_DAYS = 60
SOL_URGENCY_BOOST = 10

# Missing-data penalty
MISSING_DATA_PENALTY = 15

# Shared explanation fragment (also used by uncertain-narrative post-processor)
INSUFFICIENT_DATA_MSG = "Insufficient data — escalating to a human intake specialist."
SCORING_SCOPE_DISCLAIMER = (
    "This scoring evaluates intake viability only and does not prescribe legal action."
)

# Agent confidence mapping from lead score (0–100)
CONFIDENCE_BASE = 0.35
CONFIDENCE_CITATION_BOOST = 0.15
CONFIDENCE_TOOL_BOOST = 0.10
CONFIDENCE_SCORE_BOOST = 0.10
CONFIDENCE_SCORE_BOOST_MIN = 65  # lead_score threshold for CONFIDENCE_SCORE_BOOST
CONFIDENCE_MISSING_FIELD_PENALTY = 0.05
CONFIDENCE_MISSING_FIELD_CAP = 4
# Backward-compatible alias (was misused as 0.65 vs lead_score 0–100)
CONFIDENCE_VIABILITY_HIGH = CONFIDENCE_SCORE_BOOST_MIN
