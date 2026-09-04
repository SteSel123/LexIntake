"""LexIntake Agentic RAG Intake Agent (Agno)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from agno.agent import Agent

ROOT = Path(__file__).resolve().parents[2]
for path in (str(ROOT), str(ROOT / "tools"), str(ROOT / "db"), str(ROOT / "etl"), str(ROOT / "monitoring")):
    if path not in sys.path:
        sys.path.insert(0, path)

from common import match_practice_area  # noqa: E402

from agents.intake.constants import (  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    INTAKE_INSTRUCTIONS,
    LEGAL_DISCLAIMER,
    PROMPTS,
    UNCERTAINTY_ESCALATION,
)
from agents.intake.decide import decide as score_intake  # noqa: E402
from agents.intake.guardrails import enforce_message_guardrails  # noqa: E402
from agents.intake.guardrails import self_check as run_self_check  # noqa: E402
from agents.intake.models import (  # noqa: E402
    DecisionResult,
    IntakeFacts,
    IntakeResponse,
    PlanResult,
    RetrieveResult,
    SelfCheckResult,
    ToolPhaseResult,
)
from agents.intake.retrieve import retrieve as retrieve_chunks  # noqa: E402
from agents.intake.tools import (  # noqa: E402
    ALLOWED_TOOL_NAMES,
    TOOLS,
    parse_tool_payload,
    run_deterministic,
)
from agents.llm import complete, estimate_cost, parse_json_object  # noqa: E402
from agents.shared import enable_tracing, prepare_agent_kwargs, resolve_model  # noqa: E402

try:
    from config import LLM_MODEL, LLM_PROVIDER  # noqa: E402
except ImportError:  # pragma: no cover
    LLM_PROVIDER = "openai"
    LLM_MODEL = "gpt-4.1"

from monitoring.app_logging import get_console_logger  # noqa: E402

logger = get_console_logger("agent.intake")


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

        llm = resolve_model(self.provider, self.model_id, model)
        enable_tracing()
        super().__init__(
            **prepare_agent_kwargs(
                name="LexIntake Intake Agent",
                model=llm,
                tools=TOOLS,
                instructions=INTAKE_INSTRUCTIONS,
                **kwargs,
            )
        )

    @property
    def llm_ready(self) -> bool:
        return self.model is not None

    def _record_usage(self, input_tokens: int, output_tokens: int, total_tokens: int | None = None) -> None:
        self._token_usage["input"] += input_tokens
        self._token_usage["output"] += output_tokens
        self._token_usage["total"] += total_tokens if total_tokens is not None else (input_tokens + output_tokens)
        self._llm_cost += estimate_cost(self.provider, input_tokens, output_tokens)

    def _complete(self, prompt: str, *, system: str | None = None) -> str:
        if not self.model:
            return ""
        try:
            result = complete(self.model, prompt, system=system)
            self._record_usage(result.input_tokens, result.output_tokens, result.total_tokens)
            return result.content
        except Exception as exc:  # noqa: BLE001
            self._log("llm", f"completion failed: {exc}")
            return ""

    def _log(self, step: str, detail: str) -> None:
        entry = f"[{step}] {detail}"
        self._reasoning_log.append(entry)
        logger.info(entry)

    def _llm_refine_plan(self, facts: IntakeFacts, plan: PlanResult) -> PlanResult:
        if not self.llm_ready:
            return plan
        raw = self._complete(
            PROMPTS.user("plan_refine", facts=facts.model_dump_json(), plan=plan.model_dump_json()),
            system=PROMPTS.text("plan_refine_system"),
        )
        payload = parse_json_object(raw)
        if not payload:
            if raw:
                self._log("plan", "llm refine parse failed: no JSON object")
            return plan
        tools = [t for t in payload.get("tools_to_call", plan.tools_to_call) if t in ALLOWED_TOOL_NAMES]
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
        cites = [
            {
                "chunk_id": c.chunk_id,
                "practice_area": c.practice_area,
                "doc_type": c.doc_type,
                "excerpt": c.excerpt,
            }
            for c in retrieval.citations
        ]
        return self._complete(
            PROMPTS.user(
                "write_message",
                uncertainty_escalation=UNCERTAINTY_ESCALATION,
                legal_disclaimer=LEGAL_DISCLAIMER,
                facts=facts.model_dump_json(),
                tools=tools.model_dump_json(),
                decision=decision.model_dump_json(),
                citations=cites,
                escalate=escalate,
                questions=questions,
            ),
            system="\n".join(INTAKE_INSTRUCTIONS),
        )

    def plan(self, facts: IntakeFacts) -> PlanResult:
        """Decide questions, retrieval need, tools, and escalation."""
        missing: list[str] = []
        questions: list[str] = []
        values = facts.model_dump()
        for field, question in PROMPTS.mapping("field_questions").items():
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

    def retrieve(self, facts: IntakeFacts, plan: PlanResult) -> RetrieveResult:
        return retrieve_chunks(facts, plan, top_k=self.top_k, log=self._log)

    def use_tools(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        if self.llm_ready:
            try:
                agentic = self._use_tools_agentic(facts, plan)
                if agentic and any(
                    [agentic.sol, agentic.conflict, agentic.estimate, agentic.routing, agentic.web_fallback]
                ):
                    self._log("tools", "agentic Agent.run tool_choice=auto")
                    return agentic
            except Exception as exc:  # noqa: BLE001
                self._log("tools", f"agentic path failed, falling back: {exc}")
        return self._use_tools_deterministic(facts, plan)

    def _use_tools_deterministic(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        return run_deterministic(facts, plan, log=lambda detail: self._log("tools", detail))

    def _use_tools_agentic(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        run_out = self.run(
            PROMPTS.user("use_tools", facts=facts.model_dump_json(), tools_to_call=plan.tools_to_call)
        )
        result = ToolPhaseResult()
        for row in getattr(run_out, "tools", None) or []:
            name = str(
                getattr(row, "tool_name", None)
                or getattr(row, "name", None)
                or getattr(row, "function", None)
                or ""
            ).lower()
            payload = parse_tool_payload(
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

        det = self._use_tools_deterministic(facts, plan)
        result.sol = result.sol or det.sol
        result.conflict = result.conflict or det.conflict
        result.estimate = result.estimate or det.estimate
        result.routing = result.routing or det.routing

        metrics = getattr(run_out, "metrics", None)
        if metrics is not None:
            in_tok = int(getattr(metrics, "input_tokens", 0) or 0)
            out_tok = int(getattr(metrics, "output_tokens", 0) or 0)
            self._record_usage(in_tok, out_tok)
        return result

    def decide(
        self,
        facts: IntakeFacts,
        plan: PlanResult,
        retrieval: RetrieveResult,
        tools: ToolPhaseResult,
    ) -> DecisionResult:
        decision = score_intake(
            facts, plan, retrieval, tools, confidence_threshold=self.confidence_threshold
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
        result = run_self_check(
            response_draft,
            retrieval,
            decision,
            plan,
            confidence_threshold=self.confidence_threshold,
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
        escalate = check.escalate or decision.confidence < self.confidence_threshold
        questions = plan.questions[:3]
        used_llm = False
        message = ""

        if use_llm and self.llm_ready:
            message = self._llm_write_message(
                facts, retrieval, tools, decision, escalate=escalate, questions=questions
            )
            used_llm = bool(message)

        if not message:
            citation_lines = [
                PROMPTS.text(
                    "citation_line",
                    chunk_id=cite.chunk_id,
                    practice_area=cite.practice_area,
                    doc_type=cite.doc_type,
                )
                for cite in retrieval.citations
            ]
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
            question_block = ""
            if questions:
                question_block = "Next questions:\n" + "\n".join(f"- {q}" for q in questions)
            message = PROMPTS.user(
                "screening_summary",
                matter=facts.practice_area or facts.case_type or "unspecified",
                jurisdiction=facts.jurisdiction or "unspecified",
                lead_score=decision.lead_score,
                case_viability=decision.case_viability,
                routing_recommendation=decision.routing_recommendation,
                tool_results=chr(10).join(f"- {p}" for p in tool_summary_parts)
                or PROMPTS.text("no_tools"),
                citations="\n".join(citation_lines) if citation_lines else PROMPTS.text("no_citations"),
                next_steps=chr(10).join(f"- {s}" for s in decision.next_steps),
                question_block=question_block,
                escalation_line=UNCERTAINTY_ESCALATION if escalate else "",
                legal_disclaimer=LEGAL_DISCLAIMER,
                reminder=PROMPTS.text("screening_reminder"),
            ).strip()

        message = enforce_message_guardrails(
            message, escalate=escalate, citations=retrieval.citations
        )
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

    def run_intake(self, facts: IntakeFacts | dict[str, Any]) -> IntakeResponse:
        """plan → (llm refine) → retrieve → use_tools → decide → self_check → respond"""
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
        if not isinstance(intake, IntakeFacts) or type(intake) is not IntakeFacts:
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
        decision = _run_step("decision", lambda: self.decide(intake, plan, retrieval, tools))

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

        def _self_check_phase():
            draft_local = self.respond(
                intake, plan, retrieval, tools, decision, SelfCheckResult(ok=True), use_llm=False
            )
            check_local = self.self_check(draft_local.message, retrieval, decision, plan)
            final_local = self.respond(
                intake, plan, retrieval, tools, decision, check_local, use_llm=True
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
                slog.log_tokens(tokens=int(self._token_usage["total"]), cost=float(self._llm_cost))
            except Exception:  # noqa: BLE001
                pass
        if final.escalate and slog is not None:
            try:
                log_escalation("uncertainty_or_conflict")
            except Exception:  # noqa: BLE001
                pass
        return final


def build_default_agent(**kwargs: Any) -> IntakeAgent:
    return IntakeAgent(**kwargs)
