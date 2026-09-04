"""Pydantic models for the intake screening pipeline."""

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
