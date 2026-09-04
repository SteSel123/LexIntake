"""Shared intake runner for LexIntake UI & demo."""

from __future__ import annotations

import sys
import time
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

from agents.intake.agent import IntakeAgent  # noqa: E402
from agents.intake.models import IntakeFacts, IntakeResponse  # noqa: E402
from agents.intake.fact_parse import parse_case_description  # noqa: E402
from scoring.lead_scoring import score_lead  # noqa: E402

LEGAL_DISCLAIMER = "This is not legal advice. Consult a licensed attorney."


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

    if uncertain and scored.decision != "REJECT":
        payload["decision"] = "REVIEW"
        payload["priority"] = "Medium"
        payload["qualified"] = True
        payload["explanation"] = (
            "Insufficient data — escalating to a human intake specialist. "
            + str(payload.get("explanation") or "")
        )
    elif (
        uncertain
        and scored.decision == "REJECT"
        and not conflict.get("conflict")
        and sol.get("valid") is not False
    ):
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
        response.escalate or payload.get("decision") == "REVIEW" or uncertain
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
    payload["cost"] = float(getattr(response, "cost", 0.0) or 0.0)
    payload["parsed_facts"] = facts.model_dump()
    return payload
