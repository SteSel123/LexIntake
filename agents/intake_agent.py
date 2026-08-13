"""LexIntake Agentic RAG Intake Agent (Agno)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Literal

from agno.agent import Agent
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "tools"
DB_DIR = ROOT / "db"
ETL_DIR = ROOT / "etl"
MON_DIR = ROOT / "monitoring"
for path in (str(ROOT), str(AGENTS_DIR), str(TOOLS_DIR), str(DB_DIR), str(ETL_DIR), str(MON_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from check_statute_of_limitations import (  # noqa: E402
    CheckSOLInput,
    check_statute_of_limitations,
)
from common import match_practice_area  # noqa: E402
from conflict_check import ConflictCheckInput, conflict_check  # noqa: E402
from estimate_case_value import EstimateCaseValueInput, estimate_case_value  # noqa: E402
from route_lead import RouteLeadInput, route_lead  # noqa: E402
from web_search_fallback import WebSearchFallbackInput, web_search_fallback  # noqa: E402

try:
    from agents.llm import build_model  # noqa: E402
except ImportError:  # pragma: no cover
    from llm import build_model  # noqa: E402

try:
    from config import LLM_MODEL, LLM_PROVIDER  # noqa: E402
except ImportError:  # pragma: no cover
    LLM_PROVIDER = "openai"
    LLM_MODEL = "gpt-4.1"

logger = logging.getLogger("lexintake.agent.intake")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

LEGAL_DISCLAIMER = (
    "This is not legal advice. Consult a licensed attorney for legal guidance."
)
UNCERTAINTY_ESCALATION = (
    "Information unclear — escalating to a human intake specialist."
)
DEFAULT_CONFIDENCE_THRESHOLD = 0.55

INTAKE_INSTRUCTIONS = [
    "You are LexIntake, an intake screening assistant for a law firm.",
    "Never provide legal advice or tell users what they should do legally.",
    "You may summarize knowledge-base rules but must cite KB chunks.",
    "Never invent statutes, SOL rules, case law, or attorney profiles.",
    "If confidence is low, escalate to a human intake specialist.",
    "Always include exactly: This is not legal advice. Consult a licensed attorney for legal guidance.",
    "Use tools when needed: check_statute_of_limitations, conflict_check, estimate_case_value, route_lead.",
    "Prefer retrieved KB evidence. If evidence is missing, say so and escalate.",
    "Return a concise screening summary with next steps, never directives like 'you should sue'.",
]


# ---------------------------------------------------------------------------
# Structured models
# ---------------------------------------------------------------------------


class IntakeFacts(BaseModel):
    """Known intake facts collected so far."""

    name: str | None = None
    opposing_party: str | None = None
    practice_area: str | None = None
    case_type: str | None = None
    jurisdiction: str | None = None
    incident_date: str | None = None
    severity: str | None = "medium"
    damages: int | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    narrative: str | None = None


class PlanResult(BaseModel):
    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    need_retrieval: bool = False
    tools_to_call: list[str] = Field(default_factory=list)
    escalate: bool = False
    retrieval_query: str = ""
    doc_types: list[str] = Field(default_factory=list)
    reasoning: str = ""


class KBCitation(BaseModel):
    chunk_id: str
    practice_area: str = ""
    doc_type: str = ""
    excerpt: str = ""


class RetrieveResult(BaseModel):
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[KBCitation] = Field(default_factory=list)


class ToolPhaseResult(BaseModel):
    sol: dict[str, Any] | None = None
    conflict: dict[str, Any] | None = None
    estimate: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    web_fallback: dict[str, Any] | None = None


class DecisionResult(BaseModel):
    lead_score: int = Field(..., ge=0, le=100)
    case_viability: Literal["viable", "not_viable", "needs_review"]
    routing_recommendation: str
    next_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class SelfCheckResult(BaseModel):
    ok: bool
    issues: list[str] = Field(default_factory=list)
    escalate: bool = False
    disclaimers_present: bool = False
    citations_present: bool = False


class IntakeResponse(BaseModel):
    message: str
    disclaimer: str
    lead_score: int
    case_viability: str
    routing_recommendation: str
    next_steps: list[str]
    citations: list[KBCitation]
    tool_results: dict[str, Any]
    escalate: bool
    confidence: float
    questions: list[str] = Field(default_factory=list)
    provider: str = ""
    model_id: str = ""
    latency_ms: float = 0.0
    cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    used_llm: bool = False


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class IntakeAgent(Agent):
    """
    Agentic RAG intake agent with explicit phases:
    plan → retrieve → use_tools → decide → self_check → respond
    """

    def __init__(
        self,
        *,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        top_k: int = 8,
        model: Any | None = None,
        provider: str | None = None,
        model_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.top_k = max(5, min(10, int(top_k)))
        self._reasoning_log: list[str] = []
        self.provider = (provider or LLM_PROVIDER or "openai").lower()
        self.model_id = model_id or LLM_MODEL
        self._token_usage = {"input": 0, "output": 0, "total": 0}
        self._llm_cost = 0.0

        llm = model
        if llm is None and self.provider not in {"local", "deterministic", "hash", "none"}:
            try:
                llm = build_model(self.provider, self.model_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "LLM unavailable (%s); agent will use deterministic fallback path.",
                    exc,
                )
                llm = None
        elif self.provider in {"local", "deterministic", "hash", "none"}:
            llm = None

        # Agno Monitoring (native tracing) — no-op in offline CI
        try:
            from monitoring.agno_tracing import enable_agno_monitoring

            enable_agno_monitoring()
        except Exception:  # noqa: BLE001
            pass

        super().__init__(
            name="LexIntake Intake Agent",
            model=llm,
            tools=[
                check_statute_of_limitations,
                conflict_check,
                estimate_case_value,
                route_lead,
                web_search_fallback,
            ],
            instructions=INTAKE_INSTRUCTIONS,
            reasoning=True,
            tool_choice="auto",
            markdown=True,
            **kwargs,
        )

    @property
    def llm_ready(self) -> bool:
        return self.model is not None

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        # Approximate USD rates for provider comparison logging.
        rates = {
            "openai": (0.000002, 0.000008),
            "anthropic": (0.000003, 0.000015),
            "groq": (0.0000006, 0.0000008),
        }
        inn, out = rates.get(self.provider, (0.000002, 0.000008))
        return input_tokens * inn + output_tokens * out

    def _complete(self, prompt: str, *, system: str | None = None) -> str:
        """Single-shot LLM completion (no tool loop)."""
        if not self.model:
            return ""
        try:
            from agno.models.message import Message

            messages = []
            if system:
                messages.append(Message(role="system", content=system))
            messages.append(Message(role="user", content=prompt))
            response = self.model.response(messages)
            content = getattr(response, "content", None) or ""
            usage = getattr(response, "response_usage", None)
            in_tok = int(
                getattr(response, "input_tokens", None)
                or getattr(usage, "input_tokens", None)
                or getattr(usage, "prompt_tokens", None)
                or 0
            )
            out_tok = int(
                getattr(response, "output_tokens", None)
                or getattr(usage, "output_tokens", None)
                or getattr(usage, "completion_tokens", None)
                or 0
            )
            # Fallback estimate when provider omits usage counters.
            if in_tok == 0 and out_tok == 0:
                in_tok = max(1, len(prompt) // 4)
                out_tok = max(1, len(str(content)) // 4)
            self._token_usage["input"] += in_tok
            self._token_usage["output"] += out_tok
            self._token_usage["total"] += int(
                getattr(response, "total_tokens", 0) or (in_tok + out_tok)
            )
            self._llm_cost += self._estimate_cost(in_tok, out_tok)
            return str(content).strip()
        except Exception as exc:  # noqa: BLE001
            self._log("llm", f"completion failed: {exc}")
            return ""

    def _llm_refine_plan(self, facts: IntakeFacts, plan: PlanResult) -> PlanResult:
        """Ask the LLM to refine tool selection / retrieval focus (agentic planning)."""
        if not self.llm_ready:
            return plan
        prompt = f"""You are planning an intake screening run.
Return ONLY compact JSON with keys:
tools_to_call (array of tool names), retrieval_query (string), doc_types (array), escalate (bool), reasoning (string).

Allowed tools: check_statute_of_limitations, conflict_check, estimate_case_value, route_lead, web_search_fallback
Facts: {facts.model_dump_json()}
Draft plan: {plan.model_dump_json()}
Prefer calling tools when facts support them. Escalate when key facts are missing or ambiguous.
"""
        raw = self._complete(
            prompt,
            system="Plan intake tooling. Output JSON only. No legal advice.",
        )
        if not raw:
            return plan
        try:
            import json
            import re

            match = re.search(r"\{.*\}", raw, flags=re.S)
            payload = json.loads(match.group(0) if match else raw)
            allowed = {
                "check_statute_of_limitations",
                "conflict_check",
                "estimate_case_value",
                "route_lead",
                "web_search_fallback",
            }
            tools = [t for t in payload.get("tools_to_call", plan.tools_to_call) if t in allowed]
            if tools:
                plan.tools_to_call = tools
            if payload.get("retrieval_query"):
                plan.retrieval_query = str(payload["retrieval_query"])
            if isinstance(payload.get("doc_types"), list) and payload["doc_types"]:
                plan.doc_types = [str(x) for x in payload["doc_types"]]
            if "escalate" in payload:
                plan.escalate = bool(payload["escalate"]) or plan.escalate
            if payload.get("reasoning"):
                plan.reasoning = f"{plan.reasoning}; llm={payload['reasoning']}"
            self._log("plan", f"llm-refined tools={plan.tools_to_call}")
        except Exception as exc:  # noqa: BLE001
            self._log("plan", f"llm refine parse failed: {exc}")
        return plan

    def _llm_write_message(
        self,
        facts: IntakeFacts,
        retrieval: RetrieveResult,
        tools: ToolPhaseResult,
        decision: DecisionResult,
        escalate: bool,
        questions: list[str],
    ) -> str:
        """Generate the user-facing explanation with the configured LLM."""
        cites = [
            {
                "chunk_id": c.chunk_id,
                "practice_area": c.practice_area,
                "doc_type": c.doc_type,
                "excerpt": c.excerpt,
            }
            for c in retrieval.citations
        ]
        prompt = f"""Write a concise LexIntake screening summary for staff.
Requirements:
- Do NOT give legal advice or tell the prospect what they should do legally.
- Cite KB chunk_ids from the provided citations list (include a KB citations section).
- Include lead score, viability, routing, tool results, and next steps.
- If escalate=true OR confidence is low, include exactly: {UNCERTAINTY_ESCALATION}
- Always end with exactly: {LEGAL_DISCLAIMER}
- Do not invent statutes or cases.

Facts: {facts.model_dump_json()}
Tool results: {tools.model_dump_json()}
Decision: {decision.model_dump_json()}
Citations: {cites}
Escalate flag: {escalate}
Follow-up questions: {questions}
"""
        text = self._complete(
            prompt,
            system="\n".join(INTAKE_INSTRUCTIONS),
        )
        return text

    # -- internal logging (not shown to user) ---------------------------------

    def _log(self, step: str, detail: str) -> None:
        entry = f"[{step}] {detail}"
        self._reasoning_log.append(entry)
        logger.info(entry)

    # -- phases ---------------------------------------------------------------

    def plan(self, facts: IntakeFacts) -> PlanResult:
        """Decide questions, retrieval need, tools, and escalation."""
        missing: list[str] = []
        questions: list[str] = []

        required = {
            "name": "What is your full name?",
            "practice_area": "What type of legal matter is this (practice area)?",
            "jurisdiction": "In which US state did this occur (e.g., CA, NV)?",
            "incident_date": "What is the incident or event date (YYYY-MM-DD)?",
            "opposing_party": "Who is the opposing party or potentially at-fault party?",
            "damages": "What are your estimated damages or losses in USD (number)?",
        }
        values = facts.model_dump()
        for field, question in required.items():
            if values.get(field) in (None, "", []):
                missing.append(field)
                questions.append(question)

        case_type = facts.case_type or facts.practice_area
        practice_area = match_practice_area(case_type or "") if case_type else None

        tools: list[str] = []
        doc_types: list[str] = []
        need_retrieval = bool(practice_area or facts.narrative)

        if facts.jurisdiction and case_type and facts.incident_date:
            tools.append("check_statute_of_limitations")
            doc_types.append("sol_rules")
        if facts.name and facts.opposing_party:
            tools.append("conflict_check")
        if case_type and facts.damages is not None:
            tools.append("estimate_case_value")
            doc_types.append("past_case")
        if practice_area or facts.practice_area:
            tools.append("route_lead")
            doc_types.append("acceptance_criteria")

        escalate = len(missing) >= 5
        if not practice_area and case_type:
            tools.append("web_search_fallback")

        query_parts = [
            p
            for p in [
                practice_area or case_type,
                facts.jurisdiction,
                facts.narrative,
                "intake acceptance criteria statute settlement",
            ]
            if p
        ]
        plan = PlanResult(
            missing_fields=missing,
            questions=questions,
            need_retrieval=need_retrieval,
            tools_to_call=tools,
            escalate=escalate,
            retrieval_query=" ".join(query_parts).strip(),
            doc_types=sorted(set(doc_types)) or ["acceptance_criteria", "sol_rules", "faq"],
            reasoning=(
                f"missing={missing}; practice_area={practice_area}; "
                f"tools={tools}; retrieve={need_retrieval}"
            ),
        )
        self._log("plan", plan.reasoning)
        return plan

    def retrieve(
        self,
        facts: IntakeFacts,
        plan: PlanResult,
    ) -> RetrieveResult:
        """Query LanceDB kb_docs with metadata filters; return top-k chunks."""
        if not plan.need_retrieval:
            self._log("retrieve", "skipped (not needed)")
            return RetrieveResult()

        practice_area = match_practice_area(facts.case_type or facts.practice_area or "")
        query = plan.retrieval_query or (facts.narrative or practice_area or "intake")
        collected: list[dict[str, Any]] = []

        # Prefer filtered searches per planned doc_type, then a general search.
        doc_types = plan.doc_types or [None]
        for doc_type in doc_types:
            hits: list[dict[str, Any]] = []
            try:
                from embeddings import get_embedder
                from lancedb_store import search_kb_docs

                vector = get_embedder().embed([query])[0]
                hits = search_kb_docs(
                    vector,
                    top_k=self.top_k,
                    practice_area=practice_area,
                    jurisdiction=facts.jurisdiction,
                    doc_type=doc_type,
                )
            except Exception as exc:  # noqa: BLE001
                self._log("retrieve", f"filtered search failed ({doc_type}): {exc}")
                hits = []

            for hit in hits:
                chunk_id = str(hit.get("chunk_id") or "")
                if chunk_id and chunk_id not in {c.get("chunk_id") for c in collected}:
                    collected.append(hit)

        collected = collected[: self.top_k]
        citations = []
        for hit in collected:
            meta = hit.get("metadata") or {}
            citations.append(
                KBCitation(
                    chunk_id=str(hit.get("chunk_id") or "unknown"),
                    practice_area=str(meta.get("practice_area") or ""),
                    doc_type=str(meta.get("doc_type") or ""),
                    excerpt=str(hit.get("text") or "")[:220],
                )
            )

        try:
            from lancedb_store import ensure_kb_docs
            from monitoring.logger import log_retrieval

            total = int(ensure_kb_docs().count_rows())
            # Log metadata only (query sanitized inside logger)
            log_retrieval(query, hits=len(collected), total_chunks=total)
        except Exception as exc:  # noqa: BLE001
            self._log("retrieve", f"retrieval metrics failed: {exc}")

        self._log(
            "retrieve",
            f"query_len={len(query)} practice_area={practice_area} "
            f"jurisdiction={facts.jurisdiction} hits={len(collected)}",
        )
        return RetrieveResult(chunks=collected, citations=citations)

    def use_tools(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        """Invoke tools — prefer Agno Agent.run tool loop when LLM is ready."""
        if self.llm_ready:
            try:
                agentic = self._use_tools_agentic(facts, plan)
                if agentic and any(
                    [
                        agentic.sol,
                        agentic.conflict,
                        agentic.estimate,
                        agentic.routing,
                        agentic.web_fallback,
                    ]
                ):
                    self._log("tools", "agentic Agent.run tool_choice=auto")
                    return agentic
            except Exception as exc:  # noqa: BLE001
                self._log("tools", f"agentic path failed, falling back: {exc}")
        return self._use_tools_deterministic(facts, plan)

    def _parse_tool_payload(self, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            import json

            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {"raw": value}
            except Exception:  # noqa: BLE001
                return {"raw": value}
        return {"raw": str(value)}

    def _use_tools_agentic(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        """Let the LLM choose and call tools via Agno Agent.run."""
        case_type = facts.case_type or facts.practice_area or ""
        prompt = f"""Screen this intake lead by calling the appropriate tools now.

Facts (JSON):
{facts.model_dump_json()}

Suggested tools (you may add/remove as needed): {plan.tools_to_call}
Available tools:
- check_statute_of_limitations(jurisdiction, case_type, incident_date)
- conflict_check(name, opposing_party)
- estimate_case_value(case_type, severity, damages)
- route_lead(practice_area, priority)
- web_search_fallback(query) only if KB seems insufficient

Rules:
- Call tools with concrete arguments from the facts.
- Do not give legal advice.
- After tools complete, reply with one short sentence confirming tool results were collected.
"""
        run_out = self.run(prompt)
        result = ToolPhaseResult()
        tool_rows = getattr(run_out, "tools", None) or []
        for row in tool_rows:
            name = (
                getattr(row, "tool_name", None)
                or getattr(row, "name", None)
                or getattr(row, "function", None)
                or ""
            )
            name = str(name).lower()
            payload = self._parse_tool_payload(
                getattr(row, "result", None)
                or getattr(row, "content", None)
                or getattr(row, "tool_args", None)
            )
            if "statute" in name or "sol" in name:
                result.sol = payload
            elif "conflict" in name:
                result.conflict = payload
            elif "estimate" in name or "case_value" in name:
                result.estimate = payload
            elif "route" in name:
                result.routing = payload
            elif "web_search" in name or "fallback" in name:
                result.web_fallback = payload

        # If the model skipped a critical tool, fill deterministically.
        det = self._use_tools_deterministic(facts, plan)
        if not result.sol and det.sol:
            result.sol = det.sol
        if not result.conflict and det.conflict:
            result.conflict = det.conflict
        if not result.estimate and det.estimate:
            result.estimate = det.estimate
        if not result.routing and det.routing:
            result.routing = det.routing

        # Capture usage metrics from the agentic run when present
        metrics = getattr(run_out, "metrics", None)
        if metrics is not None:
            in_tok = int(getattr(metrics, "input_tokens", 0) or 0)
            out_tok = int(getattr(metrics, "output_tokens", 0) or 0)
            self._token_usage["input"] += in_tok
            self._token_usage["output"] += out_tok
            self._token_usage["total"] += in_tok + out_tok
            self._llm_cost += self._estimate_cost(in_tok, out_tok)

        _ = case_type  # retained for clarity / future prompts
        return result

    def _use_tools_deterministic(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        """Deterministically invoke planned Agno tools and merge outputs."""
        result = ToolPhaseResult()
        case_type = facts.case_type or facts.practice_area or ""

        try:
            if "check_statute_of_limitations" in plan.tools_to_call and facts.incident_date:
                sol = check_statute_of_limitations.entrypoint(
                    CheckSOLInput(
                        jurisdiction=facts.jurisdiction or "",
                        case_type=case_type,
                        incident_date=facts.incident_date,
                    )
                )
                result.sol = sol.model_dump() if hasattr(sol, "model_dump") else dict(sol)
                self._log("tools", f"SOL={result.sol}")

            if "conflict_check" in plan.tools_to_call and facts.name:
                conflict = conflict_check.entrypoint(
                    ConflictCheckInput(
                        name=facts.name,
                        opposing_party=facts.opposing_party or "",
                    )
                )
                result.conflict = (
                    conflict.model_dump() if hasattr(conflict, "model_dump") else dict(conflict)
                )
                self._log("tools", f"conflict={result.conflict.get('conflict')}")

            if "estimate_case_value" in plan.tools_to_call and facts.damages is not None:
                estimate = estimate_case_value.entrypoint(
                    EstimateCaseValueInput(
                        case_type=case_type,
                        severity=facts.severity or "medium",
                        damages=int(facts.damages),
                    )
                )
                result.estimate = (
                    estimate.model_dump() if hasattr(estimate, "model_dump") else dict(estimate)
                )
                self._log("tools", f"estimate={result.estimate.get('estimate')}")

            if "route_lead" in plan.tools_to_call:
                routing = route_lead.entrypoint(
                    RouteLeadInput(
                        practice_area=facts.practice_area or case_type,
                        priority=facts.priority,
                    )
                )
                result.routing = (
                    routing.model_dump() if hasattr(routing, "model_dump") else dict(routing)
                )
                self._log("tools", f"routing={result.routing.get('attorney_name')}")

            if "web_search_fallback" in plan.tools_to_call:
                fallback = web_search_fallback.entrypoint(
                    WebSearchFallbackInput(
                        query=plan.retrieval_query or case_type or "intake guidance"
                    )
                )
                result.web_fallback = (
                    fallback.model_dump() if hasattr(fallback, "model_dump") else dict(fallback)
                )
                self._log("tools", "web_search_fallback used")
        except Exception as exc:  # noqa: BLE001
            self._log("tools", f"error={exc}")

        return result

    def decide(
        self,
        facts: IntakeFacts,
        plan: PlanResult,
        retrieval: RetrieveResult,
        tools: ToolPhaseResult,
    ) -> DecisionResult:
        """Lead score, viability, routing, next steps."""
        score = 50
        confidence = 0.35
        next_steps: list[str] = []

        if retrieval.citations:
            score += min(10, 2 * len(retrieval.citations))
            confidence += 0.15

        sol = tools.sol or {}
        if sol:
            confidence += 0.15
            if sol.get("valid") is True and sol.get("expires_in", -1) != -1:
                score += 20
                next_steps.append("Confirm incident timeline documents for SOL file.")
            elif sol.get("valid") is False:
                score -= 35
                next_steps.append("Flag potential SOL issue for attorney review.")
            else:
                score -= 5
                next_steps.append("SOL uncertain — verify with attorney.")

        conflict = tools.conflict or {}
        if conflict:
            confidence += 0.1
            if conflict.get("conflict"):
                score -= 30
                next_steps.append("Conflict detected — do not discuss case merits; escalate.")
            else:
                score += 5

        estimate = tools.estimate or {}
        if estimate:
            confidence += 0.1
            est = float(estimate.get("estimate") or 0)
            explanation = str(estimate.get("explanation") or "")
            if "insufficient data" in explanation.lower():
                score -= 5
                next_steps.append("Insufficient comps — request more injury/damage detail.")
            elif est > 0:
                score += 15 if est >= 50_000 else 8

        routing = tools.routing or {}
        attorney = str(routing.get("attorney_name") or "").strip()
        if attorney:
            score += 10
            confidence += 0.1
            routing_recommendation = f"Route to {attorney}."
            next_steps.append(f"Schedule intake follow-up with {attorney}.")
        else:
            routing_recommendation = str(routing.get("motivation") or "Manual routing required.")
            next_steps.append("No attorney auto-assigned — human routing required.")

        if plan.missing_fields:
            score -= 5 * min(len(plan.missing_fields), 4)
            confidence -= 0.05 * len(plan.missing_fields)
            next_steps.append("Collect missing intake fields before engagement.")

        score = max(0, min(100, score))
        confidence = max(0.0, min(1.0, confidence))

        if conflict.get("conflict"):
            viability: Literal["viable", "not_viable", "needs_review"] = "needs_review"
        elif sol.get("valid") is False:
            viability = "not_viable"
        elif score >= 65 and confidence >= self.confidence_threshold:
            viability = "viable"
        elif score < 40:
            viability = "not_viable"
        else:
            viability = "needs_review"

        if not next_steps:
            next_steps.append("Continue structured intake questions.")

        decision = DecisionResult(
            lead_score=score,
            case_viability=viability,
            routing_recommendation=routing_recommendation,
            next_steps=next_steps,
            confidence=round(confidence, 3),
        )
        self._log("decide", decision.model_dump_json())
        return decision

    def self_check(
        self,
        response_draft: str,
        retrieval: RetrieveResult,
        decision: DecisionResult,
        plan: PlanResult,
    ) -> SelfCheckResult:
        """Validate guardrails, citations, and uncertainty handling."""
        issues: list[str] = []
        disclaimer_ok = (
            "not legal advice" in response_draft.lower()
            and "licensed attorney" in response_draft.lower()
        )
        if not disclaimer_ok:
            issues.append("Missing mandatory legal disclaimer.")

        citations_ok = bool(retrieval.citations) or not plan.need_retrieval
        if plan.need_retrieval and not retrieval.citations:
            issues.append("Retrieval was required but no KB citations were produced.")

        # Anti-hallucination: forbid inventing statute section markers without KB support
        banned_patterns = ["i am certain the statute", "guaranteed win", "you should sue"]
        lowered = response_draft.lower()
        for pattern in banned_patterns:
            if pattern in lowered:
                issues.append(f"Unsafe / advisory language detected: {pattern}")

        escalate = (
            plan.escalate
            or decision.confidence < self.confidence_threshold
            or decision.case_viability == "needs_review"
            or any("conflict" in i.lower() for i in issues)
        )
        if decision.confidence < self.confidence_threshold:
            issues.append("Confidence below threshold.")

        result = SelfCheckResult(
            ok=len(issues) == 0,
            issues=issues,
            escalate=escalate,
            disclaimers_present=disclaimer_ok,
            citations_present=bool(retrieval.citations),
        )
        self._log("self_check", result.model_dump_json())
        return result

    def respond(
        self,
        facts: IntakeFacts,
        plan: PlanResult,
        retrieval: RetrieveResult,
        tools: ToolPhaseResult,
        decision: DecisionResult,
        check: SelfCheckResult,
        *,
        use_llm: bool = True,
    ) -> IntakeResponse:
        """Build user-facing message with mandatory guardrails."""
        escalate = check.escalate or decision.confidence < self.confidence_threshold
        questions = plan.questions[:3]
        used_llm = False

        if use_llm and self.llm_ready:
            llm_message = self._llm_write_message(
                facts,
                retrieval,
                tools,
                decision,
                escalate=escalate,
                questions=questions,
            )
            if llm_message:
                message = llm_message
                used_llm = True
            else:
                message = ""
        else:
            message = ""

        if not message:
            citation_lines = []
            for cite in retrieval.citations:
                citation_lines.append(
                    f"- chunk_id={cite.chunk_id}; practice_area={cite.practice_area}; "
                    f"doc_type={cite.doc_type}"
                )
            citations_block = (
                "\n".join(citation_lines)
                if citation_lines
                else "- No KB chunks cited (insufficient retrieval matches)."
            )

            tool_summary_parts: list[str] = []
            if tools.sol:
                tool_summary_parts.append(
                    f"SOL check: valid={tools.sol.get('valid')}, "
                    f"expires_in={tools.sol.get('expires_in')} days."
                )
            if tools.conflict:
                tool_summary_parts.append(
                    f"Conflict check: conflict={tools.conflict.get('conflict')}."
                )
            if tools.estimate:
                tool_summary_parts.append(
                    f"Value estimate: ${float(tools.estimate.get('estimate') or 0):,.2f} "
                    f"(range ${float(tools.estimate.get('range_low') or 0):,.2f}"
                    f"–${float(tools.estimate.get('range_high') or 0):,.2f})."
                )
            if tools.routing:
                tool_summary_parts.append(
                    f"Routing: {tools.routing.get('attorney_name') or 'unassigned'}."
                )
            if tools.web_fallback:
                tool_summary_parts.append("Fallback retrieval was used (local KB only).")

            escalation_line = UNCERTAINTY_ESCALATION if escalate else ""
            question_block = ""
            if questions:
                question_block = "Next questions:\n" + "\n".join(f"- {q}" for q in questions)

            message = f"""LexIntake intake screening summary

Matter: {facts.practice_area or facts.case_type or 'unspecified'}
Jurisdiction: {facts.jurisdiction or 'unspecified'}
Lead score: {decision.lead_score}/100
Case viability: {decision.case_viability}
Routing recommendation: {decision.routing_recommendation}

Tool results:
{chr(10).join(f'- {p}' for p in tool_summary_parts) or '- No tools executed yet.'}

KB citations:
{citations_block}

Next steps:
{chr(10).join(f'- {s}' for s in decision.next_steps)}

{question_block}

{escalation_line}

{LEGAL_DISCLAIMER}

Reminder: This assistant explains intake screening information from firm knowledge sources only. It does not provide legal advice.
""".strip()

        # Guardrail enforcement (always)
        if LEGAL_DISCLAIMER.lower() not in message.lower() and "not legal advice" not in message.lower():
            message = f"{message}\n\n{LEGAL_DISCLAIMER}"
        if escalate and UNCERTAINTY_ESCALATION not in message:
            message = f"{message}\n\n{UNCERTAINTY_ESCALATION}"
        if retrieval.citations and "chunk_id=" not in message and "KB citation" not in message:
            cite_lines = "\n".join(
                f"- chunk_id={c.chunk_id}; practice_area={c.practice_area}; doc_type={c.doc_type}"
                for c in retrieval.citations
            )
            message = f"{message}\n\nKB citations:\n{cite_lines}"

        response = IntakeResponse(
            message=message,
            disclaimer=LEGAL_DISCLAIMER,
            lead_score=decision.lead_score,
            case_viability=decision.case_viability,
            routing_recommendation=decision.routing_recommendation,
            next_steps=decision.next_steps,
            citations=retrieval.citations,
            tool_results=tools.model_dump(),
            escalate=escalate,
            confidence=decision.confidence,
            questions=questions,
            provider=self.provider,
            model_id=str(self.model_id or ""),
            cost=float(self._llm_cost),
            input_tokens=int(self._token_usage["input"]),
            output_tokens=int(self._token_usage["output"]),
            used_llm=used_llm,
        )
        self._log("respond", f"escalate={escalate} score={decision.lead_score} llm={used_llm}")
        return response

    # -- orchestration --------------------------------------------------------

    def run_intake(self, facts: IntakeFacts | dict[str, Any]) -> IntakeResponse:
        """
        Execute full intake pipeline:
        plan → (llm refine) → retrieve → use_tools → decide → self_check → respond
        """
        import time

        self._reasoning_log.clear()
        self._token_usage = {"input": 0, "output": 0, "total": 0}
        self._llm_cost = 0.0
        started = time.perf_counter()
        intake = (
            facts
            if type(facts).__name__ == "IntakeFacts" and hasattr(facts, "model_dump")
            else IntakeFacts.model_validate(
                facts.model_dump() if hasattr(facts, "model_dump") else facts
            )
        )
        # Re-bind to this module's model to avoid dual-import class identity issues.
        if not isinstance(intake, IntakeFacts):
            intake = IntakeFacts.model_validate(intake.model_dump())
        elif type(intake) is not IntakeFacts:
            intake = IntakeFacts.model_validate(intake.model_dump())

        try:
            from monitoring.logger import (
                get_logger,
                log_case_value,
                log_escalation,
                log_event,
                log_lead_score,
                step_span,
            )
            from monitoring.metrics import get_metrics
        except Exception:  # noqa: BLE001
            get_logger = None  # type: ignore[assignment]
            step_span = None  # type: ignore[assignment]

        slog = get_logger(agent_id="intake") if get_logger else None
        if slog is not None:
            try:
                get_metrics().start_session(slog.session_id)
            except Exception:  # noqa: BLE001
                pass

        # Normalize practice area when possible
        if intake.case_type and not intake.practice_area:
            intake.practice_area = match_practice_area(intake.case_type) or intake.case_type
        elif intake.practice_area and not intake.case_type:
            intake.case_type = intake.practice_area

        def _run_step(name: str, fn):
            if step_span is None:
                return fn()
            with step_span(name):
                return fn()

        plan = _run_step("plan", lambda: self.plan(intake))
        if self.llm_ready:
            plan = _run_step("plan_llm", lambda: self._llm_refine_plan(intake, plan))
        retrieval = _run_step("retrieve", lambda: self.retrieve(intake, plan))
        tools = _run_step("tools", lambda: self.use_tools(intake, plan))
        decision = _run_step(
            "decision", lambda: self.decide(intake, plan, retrieval, tools)
        )

        if slog is not None:
            try:
                log_lead_score(decision.lead_score)
                if tools.estimate and tools.estimate.get("estimate") is not None:
                    log_case_value(float(tools.estimate["estimate"]))
                if tools.sol and tools.sol.get("valid") is False:
                    log_event("sol_failure", {"reason": "sol_invalid"})
                if tools.conflict and tools.conflict.get("conflict"):
                    log_event("conflict_detected", {"reason": "conflict"})
                if tools.routing and tools.routing.get("attorney_name"):
                    key = "".join(
                        ch if ch.isalnum() else "_"
                        for ch in str(tools.routing["attorney_name"]).lower()
                    )
                    log_event("attorney_route", {"attorney_key": key[:80]})
            except Exception:  # noqa: BLE001
                pass

        # Template draft for self-check; one LLM pass for final narrative
        def _self_check_phase():
            draft_local = self.respond(
                intake,
                plan,
                retrieval,
                tools,
                decision,
                SelfCheckResult(ok=True),
                use_llm=False,
            )
            check_local = self.self_check(draft_local.message, retrieval, decision, plan)
            final_local = self.respond(
                intake,
                plan,
                retrieval,
                tools,
                decision,
                check_local,
                use_llm=True,
            )
            final_local.escalate = check_local.escalate or final_local.escalate
            return final_local, check_local

        final, _check = _run_step("self-check", _self_check_phase)

        if final.escalate and UNCERTAINTY_ESCALATION not in final.message:
            final.message = f"{final.message}\n\n{UNCERTAINTY_ESCALATION}"

        final.latency_ms = (time.perf_counter() - started) * 1000.0
        final.cost = float(self._llm_cost)
        final.input_tokens = int(self._token_usage["input"])
        final.output_tokens = int(self._token_usage["output"])
        final.provider = self.provider
        final.model_id = str(self.model_id or "")

        if slog is not None:
            try:
                slog.log_tokens(
                    tokens=int(self._token_usage["total"]),
                    cost=float(self._llm_cost),
                )
            except Exception:  # noqa: BLE001
                pass

        if final.escalate and slog is not None:
            try:
                log_escalation("uncertainty_or_conflict")
            except Exception:  # noqa: BLE001
                pass

        return final


def build_default_agent(**kwargs: Any) -> IntakeAgent:
    """Factory for the default LexIntake intake agent."""
    return IntakeAgent(**kwargs)


if __name__ == "__main__":
    agent = IntakeAgent()
    sample = IntakeFacts(
        name="Elena Vasquez",
        opposing_party="Acme Logistics",
        practice_area="Personal Injury",
        case_type="Personal Injury",
        jurisdiction="CA",
        incident_date="2025-01-15",
        severity="high",
        damages=50000,
        priority="high",
        narrative="Rear-end collision with neck and back injuries",
    )
    result = agent.run_intake(sample)
    print(result.message)
    print("---")
    print(result.model_dump_json(indent=2)[:1200])
