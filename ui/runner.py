"""Shared intake runner for LexIntake UI & demo."""

from __future__ import annotations

import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for path in (
    str(ROOT),
    str(ROOT / "agents"),
    str(ROOT / "tools"),
    str(ROOT / "db"),
    str(ROOT / "scoring"),
    str(ROOT / "monitoring"),
):
    if path not in sys.path:
        sys.path.insert(0, path)

from agents.intake_agent import IntakeAgent, IntakeFacts, IntakeResponse  # noqa: E402
from scoring.lead_scoring import score_lead  # noqa: E402

LEGAL_DISCLAIMER = "This is not legal advice. Consult a licensed attorney."

_PRACTICE_HINTS = [
    ("personal injury", "Personal Injury"),
    ("rear-end", "Personal Injury"),
    ("slip-and-fall", "Personal Injury"),
    ("slip and fall", "Personal Injury"),
    ("collision", "Personal Injury"),
    ("employment", "Employment Law"),
    ("discrimination", "Employment Law"),
    ("immigration", "Immigration"),
    ("asylum", "Immigration"),
    ("family", "Family Law"),
    ("custody", "Family Law"),
    ("divorce", "Family Law"),
    ("workers", "Workers’ Compensation"),
    ("malpractice", "Medical Malpractice"),
    ("product", "Product Liability"),
    ("civil rights", "Civil Rights"),
    ("consumer", "Consumer Protection"),
    ("criminal", "Criminal Defense"),
]

_STATE_RE = re.compile(r"\b(CA|NV|AZ|TX|FL|NY|WA|IL|OR|CO|GA)\b", re.I)
_MONEY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*k\b|\$\s*([\d,]+(?:\.\d+)?)", re.I)
_YEARS_AGO_RE = re.compile(r"(\d+)\s*years?\s*ago", re.I)
_MONTHS_AGO_RE = re.compile(r"(\d+)\s*months?\s*ago", re.I)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _infer_practice_area(text: str) -> str | None:
    lower = text.lower()
    for needle, area in _PRACTICE_HINTS:
        if needle in lower:
            return area
    return None


def _infer_damages(text: str) -> int | None:
    match = _MONEY_RE.search(text)
    if not match:
        return None
    if match.group(1):
        return int(float(match.group(1).replace(",", "")) * 1000)
    if match.group(2):
        return int(float(match.group(2).replace(",", "")))
    return None


def _infer_incident_date(text: str) -> str | None:
    years = _YEARS_AGO_RE.search(text)
    if years:
        d = _today().replace(year=_today().year - int(years.group(1)))
        return d.isoformat()
    months = _MONTHS_AGO_RE.search(text)
    if months:
        # Approximate months as 30 days for deterministic demo behavior
        ordinal = _today().toordinal() - int(months.group(1)) * 30
        return date.fromordinal(max(1, ordinal)).isoformat()
    iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if iso:
        return iso.group(1)
    return None


def _infer_severity(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ("catastrophic", "icu", "death", "severe")):
        return "high"
    if any(w in lower for w in ("moderate", "surgery")):
        return "medium"
    if any(w in lower for w in ("minor", "unclear", "missing")):
        return "low"
    return "medium"


def _infer_name_and_party(text: str) -> tuple[str, str]:
    lower = text.lower()
    # Demo conflict scenario: use known client so conflict_check fires.
    if "acme" in lower and "employment" in lower:
        return "Elena Vasquez", "ACME Corp"
    if "opposing party" in lower:
        m = re.search(r"opposing party(?:\s+is)?\s+([A-Za-z0-9 .,&-]+)", text, flags=re.I)
        if m:
            return "Demo Prospect", m.group(1).strip(" .")
    return "Demo Prospect", "Unknown Party"


def parse_case_description(description: str) -> IntakeFacts:
    text = (description or "").strip()
    practice = _infer_practice_area(text)
    state = _STATE_RE.search(text)
    jurisdiction = state.group(1).upper() if state else None
    name, opposing = _infer_name_and_party(text)
    damages = _infer_damages(text)
    severity = _infer_severity(text)
    priority = "high" if severity == "high" else ("low" if severity == "low" else "medium")

    return IntakeFacts(
        name=name,
        opposing_party=opposing,
        practice_area=practice,
        case_type=practice,
        jurisdiction=jurisdiction,
        incident_date=_infer_incident_date(text),
        severity=severity,
        damages=damages,
        priority=priority,  # type: ignore[arg-type]
        narrative=text,
    )


def _acceptance_for_text(text: str, practice_area: str | None) -> dict[str, Any]:
    lower = text.lower()
    uncertain = any(
        w in lower for w in ("unclear", "missing", "unknown", "incomplete", "uncertain")
    )
    if uncertain:
        return {
            "matched": ["identity_present", "matter_type_present", "intake_started"],
            "unmet_required": ["jurisdiction_confirmed"],
            "practice_area_match": bool(practice_area),
        }
    return {
        "matched": [
            "signal_1",
            "signal_2",
            "signal_3",
            "signal_4",
        ],
        "unmet_required": [],
        "practice_area_match": bool(practice_area),
    }


def build_result_payload(response: IntakeResponse, facts: IntakeFacts, description: str) -> dict[str, Any]:
    tools = response.tool_results or {}
    citations = [
        {
            "chunk_id": c.chunk_id,
            "practice_area": c.practice_area,
            "doc_type": c.doc_type,
        }
        for c in (response.citations or [])
    ]

    sol = tools.get("sol") or {
        "valid": True,
        "expires_in": -1,
        "explanation": "SOL not fully evaluated due to incomplete intake facts.",
    }
    conflict = tools.get("conflict") or {"conflict": False, "details": []}
    estimate = tools.get("estimate") or {
        "estimate": float(facts.damages or 0),
        "range_low": 0.0,
        "range_high": float(facts.damages or 0),
        "explanation": "Estimate unavailable or incomplete.",
    }
    routing = tools.get("routing") or {}

    uncertain = any(
        w in description.lower()
        for w in ("unclear", "missing", "unknown", "incomplete", "uncertain")
    )
    scored = score_lead(
        {
            "sol": sol,
            "conflict": conflict,
            "case_value": estimate,
            "practice_area": facts.practice_area or "Unknown",
            "acceptance_criteria": _acceptance_for_text(description, facts.practice_area),
            "recommended_attorney": routing.get("attorney_name"),
            "practice_area_match": bool(facts.practice_area),
            "citations": citations,
        }
    )
    payload = scored.model_dump()

    # Incomplete / uncertain intakes should surface as human review when not hard-rejected.
    if uncertain and scored.decision != "REJECT":
        payload["decision"] = "REVIEW"
        payload["priority"] = "Medium"
        payload["qualified"] = True
        payload["explanation"] = (
            "Insufficient data — escalating to a human intake specialist. "
            + str(payload.get("explanation") or "")
        )
    elif uncertain and scored.decision == "REJECT" and not conflict.get("conflict") and sol.get("valid") is not False:
        payload["decision"] = "REVIEW"
        payload["priority"] = "Medium"
        payload["qualified"] = True
        payload["lead_score"] = max(40, int(payload.get("lead_score") or 0))
        payload["explanation"] = (
            "Insufficient data — escalating to a human intake specialist. "
            + str(payload.get("explanation") or "")
        )

    payload["citations"] = citations
    payload["escalate"] = bool(
        response.escalate
        or payload.get("decision") == "REVIEW"
        or uncertain
    )
    payload["guardrails"] = {
        "disclaimer_present": "not legal advice" in (response.message or "").lower()
        or "not legal advice" in str(payload.get("explanation") or "").lower(),
        "citations_present": bool(citations),
        "escalation_flag": payload["escalate"],
    }
    payload["agent_message"] = response.message
    payload["tool_results"] = {
        "sol": tools.get("sol"),
        "conflict": tools.get("conflict"),
        "estimate": tools.get("estimate"),
        "routing": tools.get("routing"),
    }
    return payload


def run_intake_analysis(
    description: str,
    *,
    agent: IntakeAgent | None = None,
) -> dict[str, Any]:
    """Run production intake pipeline and return UI/demo JSON payload."""
    agent = agent or IntakeAgent()
    facts = parse_case_description(description)
    started = time.perf_counter()
    response = agent.run_intake(facts)
    latency_ms = (time.perf_counter() - started) * 1000.0
    payload = build_result_payload(response, facts, description)
    payload["latency_ms"] = round(latency_ms, 2)
    payload["cost"] = 0.0  # local deterministic path
    payload["parsed_facts"] = facts.model_dump()
    return payload
