"""Deterministic Lead Scoring Engine for LexIntake."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEGAL_DISCLAIMER = "This is not legal advice. Consult a licensed attorney."
INSUFFICIENT_DATA_MSG = "Insufficient data — escalating to a human intake specialist."


def _observe_score(score: int, estimate: float | None, escalate: bool, reason: str = "") -> None:
    try:
        from monitoring.logger import log_case_value, log_escalation, log_event, log_lead_score

        log_lead_score(score)
        if estimate is not None:
            log_case_value(float(estimate))
        if escalate:
            log_escalation(reason or "insufficient_data")
        if score == 0 and reason:
            if "statute" in reason.lower() or "sol" in reason.lower():
                log_event("sol_failure", {"reason": "sol_invalid"})
            if "conflict" in reason.lower():
                log_event("conflict_detected", {"reason": "conflict"})
    except Exception:
        pass

Priority = Literal["High", "Medium", "Low"]
Decision = Literal["SCHEDULE_CONSULT", "REJECT", "REVIEW"]


class KBCitation(BaseModel):
    practice_area: str = ""
    doc_type: str = ""
    chunk_id: str = ""


class SOLContext(BaseModel):
    valid: bool | None = None
    expires_in: int | None = None
    explanation: str = ""


class ConflictContext(BaseModel):
    conflict: bool | None = None
    details: list[Any] = Field(default_factory=list)


class CaseValueContext(BaseModel):
    estimate: float | None = None
    range_low: float | None = None
    range_high: float | None = None
    explanation: str = ""


class AcceptanceCriteriaContext(BaseModel):
    """
    Flexible acceptance payload.

    Preferred:
      matched: criteria confirmed present
      unmet_required: required criteria still missing
    Also accepts:
      must_have_matched / must_have_unmet
      matched_count / unmet_required_count
    """

    matched: list[str] = Field(default_factory=list)
    unmet_required: list[str] = Field(default_factory=list)
    must_have_matched: list[str] = Field(default_factory=list)
    must_have_unmet: list[str] = Field(default_factory=list)
    matched_count: int | None = None
    unmet_required_count: int | None = None
    practice_area_match: bool | None = None

    def resolved_matched(self) -> list[str]:
        if self.matched:
            return list(self.matched)
        if self.must_have_matched:
            return list(self.must_have_matched)
        if self.matched_count is not None:
            return [f"matched_{i + 1}" for i in range(max(0, self.matched_count))]
        return []

    def resolved_unmet(self) -> list[str]:
        if self.unmet_required:
            return list(self.unmet_required)
        if self.must_have_unmet:
            return list(self.must_have_unmet)
        if self.unmet_required_count is not None:
            return [f"unmet_{i + 1}" for i in range(max(0, self.unmet_required_count))]
        return []


class LeadScoreContext(BaseModel):
    sol: SOLContext = Field(default_factory=SOLContext)
    conflict: ConflictContext = Field(default_factory=ConflictContext)
    case_value: CaseValueContext = Field(default_factory=CaseValueContext)
    practice_area: str | None = None
    acceptance_criteria: AcceptanceCriteriaContext | dict[str, Any] = Field(
        default_factory=AcceptanceCriteriaContext
    )
    recommended_attorney: str | None = None
    practice_area_match: bool | None = None
    citations: list[KBCitation] = Field(default_factory=list)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _coerce_acceptance(cls, value: Any) -> Any:
        if value is None:
            return AcceptanceCriteriaContext()
        return value

    def acceptance(self) -> AcceptanceCriteriaContext:
        if isinstance(self.acceptance_criteria, AcceptanceCriteriaContext):
            return self.acceptance_criteria
        return AcceptanceCriteriaContext.model_validate(self.acceptance_criteria)


class LeadScoreOutput(BaseModel):
    qualified: bool
    lead_score: int = Field(..., ge=0, le=100)
    priority: Priority
    decision: Decision
    recommended_attorney: str | None
    explanation: str


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _decision_from_score(score: int) -> tuple[bool, Priority, Decision]:
    if score >= 70:
        return True, "High", "SCHEDULE_CONSULT"
    if score >= 40:
        return True, "Medium", "REVIEW"
    return False, "Low", "REJECT"


def _format_citations(citations: list[KBCitation]) -> str:
    if not citations:
        return ""
    lines = [
        f"- practice_area={c.practice_area}; doc_type={c.doc_type}; chunk_id={c.chunk_id}"
        for c in citations
        if c.chunk_id or c.practice_area or c.doc_type
    ]
    if not lines:
        return ""
    return "KB citations:\n" + "\n".join(lines)


def score_lead(context: LeadScoreContext | dict[str, Any]) -> LeadScoreOutput:
    """
    Deterministic lead scoring.

    Same input always yields the same LeadScoreOutput.
    Evaluates SOL, conflicts, case value, acceptance criteria,
    practice-area match, and attorney availability.
    """
    ctx = (
        context
        if isinstance(context, LeadScoreContext)
        else LeadScoreContext.model_validate(context)
    )
    reasons: list[str] = []
    missing: list[str] = []
    hard_reject = False
    hard_reject_reason = ""

    # ---- required-data checks (uncertainty) ---------------------------------
    if ctx.sol.valid is None:
        missing.append("sol.valid")
    if ctx.conflict.conflict is None:
        missing.append("conflict.conflict")
    if ctx.case_value.estimate is None:
        missing.append("case_value.estimate")
    if not ctx.practice_area:
        missing.append("practice_area")

    acceptance = ctx.acceptance()
    matched = acceptance.resolved_matched()
    unmet = acceptance.resolved_unmet()
    if (
        acceptance.matched_count is None
        and not acceptance.matched
        and not acceptance.must_have_matched
        and acceptance.unmet_required_count is None
        and not acceptance.unmet_required
        and not acceptance.must_have_unmet
    ):
        missing.append("acceptance_criteria")

    # ---- 1) SOL hard reject / urgency --------------------------------------
    score = 0.0

    if ctx.sol.valid is False:
        hard_reject = True
        hard_reject_reason = "Statute of limitations indicates claim is not valid."
        reasons.append(hard_reject_reason)
    elif ctx.sol.valid is True:
        reasons.append("SOL appears valid based on provided screening data.")
        if ctx.sol.expires_in is not None and ctx.sol.expires_in >= 0 and ctx.sol.expires_in < 60:
            score += 10
            reasons.append(f"Urgency boost: SOL expires in {ctx.sol.expires_in} days (< 60).")

    # ---- 2) Conflict hard reject -------------------------------------------
    if ctx.conflict.conflict is True:
        hard_reject = True
        hard_reject_reason = "Conflict of interest detected."
        reasons.append(hard_reject_reason)
    elif ctx.conflict.conflict is False:
        reasons.append("No conflict detected in client screening.")

    if hard_reject:
        explanation_parts = [
            hard_reject_reason,
            "Lead rejected by deterministic screening rules.",
            " ".join(reasons),
        ]
        if missing:
            explanation_parts.append(INSUFFICIENT_DATA_MSG)
        cite_block = _format_citations(ctx.citations)
        if cite_block:
            explanation_parts.append(cite_block)
        explanation_parts.append(LEGAL_DISCLAIMER)
        explanation_parts.append(
            "This scoring evaluates intake viability only and does not prescribe legal action."
        )
        out = LeadScoreOutput(
            qualified=False,
            lead_score=0,
            priority="Low",
            decision="REJECT",
            recommended_attorney=ctx.recommended_attorney,
            explanation=" ".join(p for p in explanation_parts if p).strip(),
        )
        _observe_score(
            0,
            ctx.case_value.estimate,
            escalate=bool(missing),
            reason=hard_reject_reason,
        )
        return out

    # ---- 3) Case value (0–40) + high-value boost ---------------------------
    estimate = float(ctx.case_value.estimate or 0.0)
    case_value_points = min(40.0, estimate / 2500.0)
    score += case_value_points
    reasons.append(f"Case value points={case_value_points:.2f} from estimate={estimate:.2f}.")
    if estimate > 100_000:
        score += 10
        reasons.append("Priority boost: estimated value exceeds $100,000.")

    # ---- 4) Acceptance criteria (0–30) -------------------------------------
    acceptance_points = (5 * len(matched)) + (-10 * len(unmet))
    acceptance_points = max(0.0, min(30.0, float(acceptance_points)))
    score += acceptance_points
    reasons.append(
        f"Acceptance criteria points={acceptance_points:.1f} "
        f"(matched={len(matched)}, unmet_required={len(unmet)})."
    )

    # ---- 5) Practice area match --------------------------------------------
    practice_match = ctx.practice_area_match
    if practice_match is None:
        practice_match = acceptance.practice_area_match
    if practice_match is None:
        # If practice_area present and no explicit mismatch flag, treat as match.
        practice_match = bool(ctx.practice_area)

    if practice_match is False:
        score *= 0.5
        reasons.append("Practice area mismatch: total score reduced by 50%.")
    else:
        # Practice area match contributes up to 20 informational points when matched
        # and criteria were evaluable. Kept additive and deterministic.
        practice_points = 20.0 if ctx.practice_area else 0.0
        score += practice_points
        reasons.append(f"Practice area match points={practice_points:.1f}.")

    # ---- 6) Attorney availability ------------------------------------------
    if ctx.recommended_attorney:
        score += 5
        reasons.append(f"Attorney available: {ctx.recommended_attorney} (+5).")
    else:
        reasons.append("No recommended attorney assigned.")

    # ---- missing-data penalty ----------------------------------------------
    if missing:
        score -= 15
        reasons.append(INSUFFICIENT_DATA_MSG)
        reasons.append(f"Missing fields: {', '.join(missing)}.")

    lead_score = _clamp_score(score)
    qualified, priority, decision = _decision_from_score(lead_score)

    summary = (
        "Case appears viable based on SOL validity, conflict screening, case value, "
        "and acceptance criteria match."
        if qualified and decision == "SCHEDULE_CONSULT"
        else "Case requires additional review based on deterministic screening factors."
        if decision == "REVIEW"
        else "Case does not meet automatic qualification thresholds."
    )

    explanation_parts = [
        summary,
        " ".join(reasons),
    ]
    if missing:
        explanation_parts.append(INSUFFICIENT_DATA_MSG)
    cite_block = _format_citations(ctx.citations)
    if cite_block:
        explanation_parts.append(cite_block)
    explanation_parts.append(LEGAL_DISCLAIMER)
    explanation_parts.append(
        "This scoring evaluates intake viability only and does not prescribe legal action."
    )

    out = LeadScoreOutput(
        qualified=qualified,
        lead_score=lead_score,
        priority=priority,
        decision=decision,
        recommended_attorney=ctx.recommended_attorney,
        explanation=" ".join(p for p in explanation_parts if p).strip(),
    )
    _observe_score(
        lead_score,
        estimate,
        escalate=bool(missing) or decision == "REVIEW",
        reason="insufficient_data" if missing else ("review" if decision == "REVIEW" else ""),
    )
    if ctx.recommended_attorney:
        try:
            from monitoring.logger import log_event

            key = "".join(ch if ch.isalnum() else "_" for ch in ctx.recommended_attorney.lower())
            log_event("attorney_route", {"attorney_key": key[:80]})
        except Exception:
            pass
    return out


if __name__ == "__main__":
    sample = {
        "sol": {
            "valid": True,
            "expires_in": 120,
            "explanation": "Within SOL",
        },
        "conflict": {"conflict": False, "details": []},
        "case_value": {
            "estimate": 100000,
            "range_low": 75000,
            "range_high": 125000,
            "explanation": "Comps available",
        },
        "practice_area": "Personal Injury",
        "practice_area_match": True,
        "acceptance_criteria": {
            "matched": [
                "Identifiable at-fault party or liable entity",
                "Documented physical injury or verifiable medical treatment",
                "Incident date within applicable SOL for the jurisdiction",
                "Clear causal link between incident and claimed injuries",
            ],
            "unmet_required": [],
        },
        "recommended_attorney": "M. Cruz",
        "citations": [
            {
                "practice_area": "personal_injury",
                "doc_type": "sol_rules",
                "chunk_id": "abc123",
            }
        ],
    }
    out = score_lead(sample)
    print(out.model_dump_json(indent=2))

    # Determinism check
    out2 = score_lead(sample)
    assert out.model_dump() == out2.model_dump()
    print("deterministic=OK")
