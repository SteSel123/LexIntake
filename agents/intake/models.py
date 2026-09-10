"""Pydantic models for the intake screening pipeline.

Defines typed payloads exchanged between plan → retrieve → decide → respond
stages, plus structured LLM output schemas used by Agno ``output_schema`` runs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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
    """Deterministic + LLM-refined plan for the next intake pipeline steps."""

    missing_fields: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    need_retrieval: bool = False
    tools_to_call: list[str] = Field(default_factory=list)
    escalate: bool = False
    retrieval_query: str = ""
    doc_types: list[str] = Field(default_factory=list)
    reasoning: str = ""


class PlanRefineOutput(BaseModel):
    """Agno structured output for LLM plan refinement."""

    tools_to_call: list[str] = Field(
        default_factory=list,
        description=(
            "Tools to call from: check_statute_of_limitations, conflict_check, "
            "estimate_case_value, route_lead"
        ),
    )
    retrieval_query: str = Field(default="", description="Semantic search query for the KB")
    doc_types: list[str] = Field(
        default_factory=list,
        description="KB doc types such as sol_rules, past_case, acceptance_criteria, faq",
    )
    escalate: bool = Field(default=False, description="True when key facts are missing or ambiguous")
    reasoning: str = Field(default="", description="Short rationale for the refined plan")


class ScreeningMessage(BaseModel):
    """Agno structured output for the staff-facing screening narrative."""

    message: str = Field(..., description="Concise screening summary for intake staff")


class ExtractedIntakeFields(BaseModel):
    """Agno structured output for interview field extraction."""

    name: str | None = Field(default=None, description="Prospect full name")
    opposing_party: str | None = Field(default=None, description="Opposing or at-fault party")
    practice_area: str | None = Field(default=None, description="Legal practice area")
    jurisdiction: str | None = Field(default=None, description="US state code, e.g. CA")
    incident_date: str | None = Field(default=None, description="Incident date YYYY-MM-DD when known")
    damages: int | None = Field(default=None, description="Estimated damages in USD")
    severity: str | None = Field(default=None, description="low, medium, or high")


class KBCitation(BaseModel):
    """Reference to a knowledge-base chunk surfaced during retrieval."""

    chunk_id: str
    practice_area: str = ""
    doc_type: str = ""
    excerpt: str = ""


class RetrieveResult(BaseModel):
    """Raw KB chunks plus normalized citations for staff-facing output."""

    chunks: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[KBCitation] = Field(default_factory=list)


class ToolPhaseResult(BaseModel):
    """Aggregated outputs from optional intake tools (SOL, conflict, routing, etc.)."""

    sol: dict[str, Any] | None = None
    conflict: dict[str, Any] | None = None
    estimate: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class DecisionResult(BaseModel):
    """Scoring and routing decision produced after tools and retrieval."""

    lead_score: int = Field(..., ge=0, le=100)
    case_viability: Literal["viable", "not_viable", "needs_review"]
    routing_recommendation: str
    next_steps: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class SelfCheckResult(BaseModel):
    """Guardrail self-check before finalizing the staff-facing message."""

    ok: bool
    issues: list[str] = Field(default_factory=list)
    escalate: bool = False
    disclaimers_present: bool = False
    citations_present: bool = False


class IntakeResponse(BaseModel):
    """Complete intake screening result returned to callers and the interview flow."""

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
