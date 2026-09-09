"""Intake application service — shared by API, frontend demo, and CLI."""

from __future__ import annotations

import time
from typing import Any

from agents.intake.agent import IntakeAgent
from agents.intake.constants import LEGAL_DISCLAIMER
from agents.intake.fact_parse import parse_case_description
from agents.intake.models import IntakeFacts, IntakeResponse
from scoring.context import build_lead_score_context_from_response
from scoring.domain import apply_uncertain_narrative_override, is_uncertain_narrative
from scoring.lead_scoring import score_lead

__all__ = [
    "LEGAL_DISCLAIMER",
    "build_result_payload",
    "finalize_screening_payload",
    "run_intake_analysis",
]


def build_result_payload(
    response: IntakeResponse, facts: IntakeFacts, description: str
) -> dict[str, Any]:
    tools = response.tool_results or {}
    citations = [
        {
            "chunk_id": c.chunk_id,
            "practice_area": c.practice_area,
            "doc_type": c.doc_type,
        }
        for c in (response.citations or [])
    ]

    ctx = build_lead_score_context_from_response(
        facts, response, narrative=description
    )
    scored = apply_uncertain_narrative_override(
        score_lead(ctx),
        narrative=description,
        tools=tools,
    )
    payload = scored.model_dump()
    uncertain = is_uncertain_narrative(description)

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


def finalize_screening_payload(
    screening: IntakeResponse,
    facts: IntakeFacts,
    narrative: str,
) -> dict[str, Any]:
    """Attach latency/cost/facts after build_result_payload (API + frontend)."""
    payload = build_result_payload(screening, facts, narrative)
    payload["latency_ms"] = float(getattr(screening, "latency_ms", 0) or 0)
    payload["cost"] = float(getattr(screening, "cost", 0) or 0)
    payload["parsed_facts"] = facts.model_dump()
    return payload


def run_intake_analysis(
    description: str,
    *,
    agent: IntakeAgent | None = None,
) -> dict[str, Any]:
    """Run production intake pipeline and return JSON-ready payload."""
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
