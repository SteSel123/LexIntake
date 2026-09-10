"""
LexIntake Agentic RAG Intake Agent (Agno).

Orchestrates a fixed pipeline over structured intake facts:
  plan → (optional LLM refine) → retrieve → use_tools → decide → self_check → respond

Each phase is a method; `run_intake` runs them in order and returns an IntakeResponse
for the API / UI (lead score, message, citations, escalation, token cost, etc.).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from agno.agent import Agent

from agents.intake.constants import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    INTAKE_INSTRUCTIONS,
    LEGAL_DISCLAIMER,
    PROMPTS,
    TOP_K_MAX,
    TOP_K_MIN,
    UNCERTAINTY_ESCALATION,
)
from agents.intake.decide import decide as score_intake
from agents.intake.guardrails import self_check as run_self_check
from agents.intake.models import (
    DecisionResult,
    IntakeFacts,
    IntakeResponse,
    PlanRefineOutput,
    PlanResult,
    RetrieveResult,
    ScreeningMessage,
    SelfCheckResult,
    ToolPhaseResult,
)
from agents.intake.plan import build_plan
from agents.intake.respond import build_response
from agents.intake.retrieve import retrieve as retrieve_chunks
from agents.intake.tools import (
    ALLOWED_TOOL_NAMES,
    TOOLS,
    parse_tool_payload,
    run_deterministic,
)
from agents.llm import complete_structured, usage_from_run
from agents.shared import enable_tracing, prepare_agent_kwargs, resolve_model
from monitoring.app_logging import get_console_logger, log_optional_failure
from tools.common import attorney_key, match_practice_area

try:
    from config import LLM_MODEL, LLM_PROVIDER
except ImportError:  # pragma: no cover
    LLM_PROVIDER = "openai"
    LLM_MODEL = "gpt-4.1"

logger = get_console_logger("agent.intake")


# Recoverable LLM / provider errors: log and continue with empty/None instead of crashing intake.
_LLM_FAILURES = (
    OSError,
    RuntimeError,
    TimeoutError,
    ValueError,
    TypeError,
    ConnectionError,
)


class IntakeAgent(Agent):
    """
    Agentic RAG intake agent with explicit phases:
    plan → retrieve → use_tools → decide → self_check → respond

    Subclasses Agno Agent so tool-calling can use Agent.run (agentic path),
    while scoring / planning stay deterministic Python for auditability.
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
        # Threshold used in decide / self_check to force escalation when unsure.
        self.confidence_threshold = confidence_threshold
        # How many KB chunks to keep after vector search (clamped to allowed range).
        self.top_k = max(TOP_K_MIN, min(TOP_K_MAX, int(top_k)))
        self.provider = (provider or LLM_PROVIDER or "openai").lower()
        self.model_id = model_id or LLM_MODEL
        # Session totals summed from Agno run.metrics (OTEL); reset in run_intake.
        self._token_usage = {"input": 0, "output": 0, "total": 0}
        self._llm_cost = 0.0

        llm = resolve_model(self.provider, self.model_id, model)
        enable_tracing()
        # Wire Agno: name, model, screening tools, and system instructions from prompts.xml.
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
        """True when a usable chat model was resolved (structured LLM steps can run)."""
        return self.model is not None

    def _accumulate_agno_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int | None = None,
        cost: float = 0.0,
    ) -> None:
        """Sum Agno/OTEL run metrics across intake LLM calls into session totals."""
        self._token_usage["input"] += input_tokens
        self._token_usage["output"] += output_tokens
        self._token_usage["total"] += total_tokens if total_tokens is not None else (input_tokens + output_tokens)
        self._llm_cost += float(cost or 0.0)

    def complete_structured(
        self,
        prompt: str,
        output_schema: type[Any],
        *,
        system: str | None = None,
        name: str = "LexIntake Structured",
    ) -> Any:
        """
        Structured LLM completion (Pydantic schema).

        Used by intake (plan refine, screening message) and interview agents.
        Returns None if the model is missing or the call fails.
        """
        if not self.model:
            return None
        try:
            result = complete_structured(
                self.model,
                prompt,
                output_schema,
                system=system,
                name=name,
            )
            self._accumulate_agno_usage(
                result.input_tokens, result.output_tokens, result.total_tokens, result.cost
            )
            return result.parsed
        except _LLM_FAILURES as exc:
            self._log("llm", f"structured completion failed: {type(exc).__name__}: {exc}")
            return None

    def _log(self, step: str, detail: str) -> None:
        """Emit a phase log line to the intake console logger."""
        logger.info("[%s] %s", step, detail)

    # ------------------------------------------------------------------
    # Phase helpers that optionally call the LLM
    # ------------------------------------------------------------------

    def _llm_refine_plan(self, facts: IntakeFacts, plan: PlanResult) -> PlanResult:
        """
        Ask the LLM to adjust tools / retrieval query / doc_types on top of the
        deterministic plan. Falls back to the original plan if parsing fails.
        Only tool names in ALLOWED_TOOL_NAMES are kept.
        """
        if not self.llm_ready:
            return plan
        refined = self.complete_structured(
            PROMPTS.user("plan_refine", facts=facts.model_dump_json(), plan=plan.model_dump_json()),
            PlanRefineOutput,
            system=PROMPTS.text("plan_refine_system"),
            name="LexIntake Plan Refine",
        )
        if not isinstance(refined, PlanRefineOutput):
            self._log("plan", "llm refine parse failed: no structured PlanRefineOutput")
            return plan
        tools = [t for t in refined.tools_to_call if t in ALLOWED_TOOL_NAMES]
        if tools:
            plan.tools_to_call = tools
        if refined.retrieval_query:
            plan.retrieval_query = refined.retrieval_query
        if refined.doc_types:
            plan.doc_types = [str(x) for x in refined.doc_types]
        plan.escalate = refined.escalate or plan.escalate
        if refined.reasoning:
            plan.reasoning = f"{plan.reasoning}; llm={refined.reasoning}"
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
        """
        Generate the client-facing screening message via structured LLM output.
        Returns '' when the model does not return a ScreeningMessage (caller uses template).
        """
        cites = [
            {
                "chunk_id": c.chunk_id,
                "practice_area": c.practice_area,
                "doc_type": c.doc_type,
                "excerpt": c.excerpt,
            }
            for c in retrieval.citations
        ]
        written = self.complete_structured(
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
            ScreeningMessage,
            system="\n".join(INTAKE_INSTRUCTIONS),
            name="LexIntake Screening Message",
        )
        if isinstance(written, ScreeningMessage):
            return written.message
        return ""

    # ------------------------------------------------------------------
    # Pipeline phases (callable individually or via run_intake)
    # ------------------------------------------------------------------

    def plan(self, facts: IntakeFacts) -> PlanResult:
        """
        Deterministic plan: missing fields → questions, which tools to run,
        whether KB retrieval is needed, and early escalate if too incomplete.
        """
        plan = build_plan(facts)
        self._log("plan", plan.reasoning)
        return plan

    def retrieve(self, facts: IntakeFacts, plan: PlanResult) -> RetrieveResult:
        """Vector-search the KB for relevant chunks/citations (or skip if plan says so)."""
        return retrieve_chunks(facts, plan, top_k=self.top_k, log=self._log)

    def use_tools(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        """
        Run intake tools (SOL, conflict, estimate, routing).

        Prefers Agno Agent.run (LLM picks/calls tools) when a model is ready;
        otherwise (or on failure) runs the planned tools deterministically.
        """
        if self.llm_ready:
            try:
                agentic = self._use_tools_agentic(facts, plan)
                # Only accept agentic output if at least one tool produced a payload.
                if agentic and any(
                    [agentic.sol, agentic.conflict, agentic.estimate, agentic.routing]
                ):
                    self._log("tools", "agentic Agent.run tool_choice=auto")
                    return agentic
            except _LLM_FAILURES as exc:
                self._log("tools", f"agentic path failed, falling back: {type(exc).__name__}: {exc}")
        return self._use_tools_deterministic(facts, plan)

    def _use_tools_deterministic(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        """Call exactly the tools listed in plan.tools_to_call with known inputs (no LLM)."""
        return run_deterministic(facts, plan, log=lambda detail: self._log("tools", detail))

    def _use_tools_agentic(self, facts: IntakeFacts, plan: PlanResult) -> ToolPhaseResult:
        """
        Let Agno run tools via the LLM, then map tool names → ToolPhaseResult fields.
        Fill any gaps from the deterministic path so required checks are not skipped.
        """
        run_out = self.run(
            PROMPTS.user("use_tools", facts=facts.model_dump_json(), tools_to_call=plan.tools_to_call)
        )
        result = ToolPhaseResult()
        for row in getattr(run_out, "tools", None) or []:
            # Agno tool-call rows expose different attribute names across versions.
            name = str(
                getattr(row, "tool_name", None)
                or getattr(row, "name", None)
                or getattr(row, "function", None)
                or ""
            ).lower()
            # Only accept real tool outputs — never tool_args (inputs look like payloads).
            raw = getattr(row, "result", None)
            if raw is None:
                raw = getattr(row, "content", None)
            if raw is None:
                continue
            payload = parse_tool_payload(raw)
            if not payload:
                continue
            if "statute" in name or "sol" in name:
                result.sol = payload
            elif "conflict" in name:
                result.conflict = payload
            elif "estimate" in name or "case_value" in name:
                result.estimate = payload
            elif "route" in name:
                result.routing = payload

        # Planned tools: deterministic path is the audit source of truth.
        # Agentic results only fill gaps (avoids incomplete LLM tool rows wiping SOL/estimate).
        det = self._use_tools_deterministic(facts, plan)
        result.sol = det.sol or result.sol
        result.conflict = det.conflict or result.conflict
        result.estimate = det.estimate or result.estimate
        result.routing = det.routing or result.routing

        in_tok, out_tok, total, cost = usage_from_run(run_out)
        self._accumulate_agno_usage(in_tok, out_tok, total, cost)
        return result

    def decide(
        self,
        facts: IntakeFacts,
        plan: PlanResult,
        retrieval: RetrieveResult,
        tools: ToolPhaseResult,
    ) -> DecisionResult:
        """Score the lead and map to ACCEPT / REVIEW / REJECT (+ next steps, confidence)."""
        decision = score_intake(
            facts,
            plan,
            retrieval,
            tools,
            confidence_threshold=self.confidence_threshold,
            narrative=facts.narrative,
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
        """
        Guardrails on a draft message: citations, confidence, escalate flags.
        Used before the final respond so unsafe drafts can force human review.
        """
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
        """
        Assemble the final IntakeResponse (message, scores, citations, cost metadata).
        When use_llm=True and the model is ready, prefers LLM-written screening text;
        otherwise uses the templated message builder.
        """
        return build_response(
            facts,
            plan,
            retrieval,
            tools,
            decision,
            check,
            confidence_threshold=self.confidence_threshold,
            provider=self.provider,
            model_id=str(self.model_id or ""),
            llm_cost=float(self._llm_cost),
            input_tokens=int(self._token_usage["input"]),
            output_tokens=int(self._token_usage["output"]),
            write_message=self._llm_write_message,
            use_llm=use_llm,
            llm_ready=self.llm_ready,
            log=self._log,
        )

    def _log_tool_metrics(self, tools: ToolPhaseResult, decision: DecisionResult) -> None:
        """Best-effort monitoring hooks (lead score, SOL failure, conflict, attorney route)."""
        try:
            from monitoring.logger import log_case_value, log_event, log_lead_score

            log_lead_score(decision.lead_score)
            if tools.estimate and tools.estimate.get("estimate") is not None:
                log_case_value(float(tools.estimate["estimate"]))
            if tools.sol and tools.sol.get("valid") is False:
                log_event("sol_failure", {"reason": "sol_invalid"})
            if tools.conflict and tools.conflict.get("conflict"):
                log_event("conflict_detected", {"reason": "conflict"})
            if tools.routing and tools.routing.get("attorney_name"):
                log_event(
                    "attorney_route",
                    {"attorney_key": attorney_key(str(tools.routing["attorney_name"]))},
                )
        except Exception as exc:  # noqa: BLE001 — metrics must not break intake
            log_optional_failure(logger, "tool metrics", exc)

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    def run_intake(self, facts: IntakeFacts | dict[str, Any]) -> IntakeResponse:
        """
        End-to-end intake:

          1. Normalize facts (IntakeFacts)
          2. plan (+ optional LLM refine)
          3. retrieve KB chunks
          4. use_tools (agentic or deterministic)
          5. decide (lead score / viability)
          6. draft message without LLM → self_check → final respond (LLM if available)
          7. Attach latency, tokens, cost; log escalation if needed
        """
        self._token_usage = {"input": 0, "output": 0, "total": 0}
        self._llm_cost = 0.0
        started = time.perf_counter()
        # Accept IntakeFacts, another pydantic model, or a plain dict from the API.
        if isinstance(facts, IntakeFacts):
            intake = facts
        elif hasattr(facts, "model_dump"):
            intake = IntakeFacts.model_validate(facts.model_dump())
        else:
            intake = IntakeFacts.model_validate(facts)

        # Monitoring is optional: intake must still work if logger/metrics are unavailable.
        try:
            from monitoring.logger import get_logger, log_escalation, step_span
            from monitoring.metrics import get_metrics
        except ImportError as exc:
            log_optional_failure(logger, "monitoring import", exc, level=logging.WARNING)
            get_logger = None  # type: ignore[assignment]
            step_span = None  # type: ignore[assignment]
            log_escalation = None  # type: ignore[assignment]
            get_metrics = None  # type: ignore[assignment]

        slog = get_logger(agent_id="intake") if get_logger else None
        if slog is not None and get_metrics is not None:
            try:
                get_metrics().start_session(slog.session_id)
            except Exception as exc:  # noqa: BLE001
                log_optional_failure(logger, "metrics session start", exc)

        # Keep case_type and practice_area in sync (tools / KB filters use both).
        if intake.case_type and not intake.practice_area:
            intake.practice_area = match_practice_area(intake.case_type) or intake.case_type
        elif intake.practice_area and not intake.case_type:
            intake.case_type = intake.practice_area

        def _run_step(name: str, fn):
            """Run a phase, wrapping it in a monitoring span when available."""
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
            self._log_tool_metrics(tools, decision)

        def _self_check_phase():
            # First respond without LLM to get a stable draft for guardrails,
            # then self_check, then final respond (may use LLM for the message).
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
        # Ensure escalated responses always include the standard uncertainty notice.
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
            except Exception as exc:  # noqa: BLE001
                log_optional_failure(logger, "token logging", exc)
        if final.escalate and slog is not None and log_escalation is not None:
            try:
                log_escalation("uncertainty_or_conflict")
            except Exception as exc:  # noqa: BLE001
                log_optional_failure(logger, "escalation logging", exc)
        return final


def build_default_agent(**kwargs: Any) -> IntakeAgent:
    """Factory used by API / frontend to construct a configured IntakeAgent."""
    return IntakeAgent(**kwargs)
