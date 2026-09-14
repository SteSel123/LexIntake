"""Intake application service — shared by API, frontend demo, and CLI.

Orchestrates LLM fact extraction, agent screening, lead scoring, JSON payload
assembly, and persistence of screened leads to Postgres ``intake_leads``.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from agents.intake.agent import IntakeAgent
from agents.intake.constants import LEGAL_DISCLAIMER
from agents.intake.models import IntakeFacts, IntakeResponse
from monitoring.app_logging import get_console_logger, log_optional_failure
from scoring.context import build_lead_score_context_from_response
from scoring.domain import apply_uncertain_narrative_override
from scoring.lead_scoring import score_lead

__all__ = [
    "LEGAL_DISCLAIMER",
    "build_result_payload",
    "finalize_screening_payload",
    "persist_intake_lead",
    "run_intake_analysis",
]

_logger = get_console_logger("intake.service")


def build_result_payload(
    response: IntakeResponse, facts: IntakeFacts, description: str
) -> dict[str, Any]:
    """Merge agent output, citations, lead score, and guardrail flags into one dict.

    Lead scoring runs after the agent returns so decision/explanation reflect
    both LLM reasoning and deterministic scoring rules (including uncertain-
    narrative overrides that force REVIEW/escalation).
    """
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
        uncertain=facts.uncertain,
    )
    payload = scored.model_dump()
    uncertain = bool(facts.uncertain)

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


def persist_intake_lead(
    facts: IntakeFacts,
    payload: dict[str, Any],
    *,
    source: str,
    case_viability: str | None = None,
    routing_recommendation: str | None = None,
) -> str | None:
    """Best-effort write of a screened lead to ``intake_leads``.

    Returns the new lead id, or ``None`` when persistence fails (API still succeeds).
    """
    lead_id = f"lead-{uuid.uuid4()}"
    row = {
        "id": lead_id,
        "source": source,
        "name": facts.name,
        "opposing_party": facts.opposing_party,
        "practice_area": facts.practice_area,
        "case_type": facts.case_type,
        "jurisdiction": facts.jurisdiction,
        "incident_date": facts.incident_date,
        "severity": facts.severity,
        "damages": facts.damages,
        "priority": facts.priority,
        "narrative": facts.narrative,
        "uncertain": facts.uncertain,
        "lead_score": payload.get("lead_score"),
        "decision": payload.get("decision"),
        "case_viability": case_viability,
        "escalate": bool(payload.get("escalate")),
        "routing_recommendation": routing_recommendation
        or payload.get("recommended_attorney"),
        "tool_results": payload.get("tool_results") or {},
        "citations": payload.get("citations") or [],
        "payload": payload,
    }
    try:
        from db.structured_db import insert_intake_lead

        return insert_intake_lead(row)
    except Exception as exc:  # noqa: BLE001 — persistence must not break screening
        log_optional_failure(_logger, "persist intake lead", exc)
        return None


def finalize_screening_payload(
    screening: IntakeResponse,
    facts: IntakeFacts,
    narrative: str,
    *,
    source: str = "interview",
) -> dict[str, Any]:
    """Attach latency, cost, and parsed facts after ``build_result_payload``.

    Used when the interview agent finishes and returns a full ``IntakeResponse``
    so the API can expose the same shape as the one-shot ``/analyze`` endpoint.
    Persists the lead to Postgres when available.
    """
    payload = build_result_payload(screening, facts, narrative)
    payload["latency_ms"] = float(getattr(screening, "latency_ms", 0) or 0)
    payload["cost"] = float(getattr(screening, "cost", 0) or 0)
    payload["parsed_facts"] = facts.model_dump()
    lead_id = persist_intake_lead(
        facts,
        payload,
        source=source,
        case_viability=getattr(screening, "case_viability", None),
        routing_recommendation=getattr(screening, "routing_recommendation", None),
    )
    if lead_id:
        payload["intake_lead_id"] = lead_id
    return payload


def run_intake_analysis(
    description: str,
    *,
    agent: IntakeAgent | None = None,
) -> dict[str, Any]:
    """Run the production intake pipeline and return a JSON-ready payload.

    Extracts facts via LLM structured output (``ExtractedIntakeFields``),
    invokes ``IntakeAgent.run_intake``, scores the lead, persists to
    ``intake_leads``, and records wall-clock latency plus optional LLM cost.
    """
    agent = agent or IntakeAgent()
    facts = agent.extract_facts(description)
    started = time.perf_counter()
    response = agent.run_intake(facts)
    latency_ms = (time.perf_counter() - started) * 1000.0
    payload = build_result_payload(response, facts, description)
    payload["latency_ms"] = round(latency_ms, 2)
    payload["cost"] = float(getattr(response, "cost", 0.0) or 0.0)
    payload["parsed_facts"] = facts.model_dump()
    lead_id = persist_intake_lead(
        facts,
        payload,
        source="analyze",
        case_viability=getattr(response, "case_viability", None),
        routing_recommendation=getattr(response, "routing_recommendation", None),
    )
    if lead_id:
        payload["intake_lead_id"] = lead_id
    return payload
