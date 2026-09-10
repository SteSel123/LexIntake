"""HTTP request/response schemas for the LexIntake API.

Pydantic models validate inbound JSON and shape outbound payloads so OpenAPI
docs and client code stay aligned with the intake and interview endpoints.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# --- Health ----------------------------------------------------------------


class HealthResponse(BaseModel):
    """Liveness probe payload for load balancers and monitoring."""

    status: str = "ok"
    service: str = "lexintake-api"


# --- Quick intake (single-shot analysis) -----------------------------------


class AnalyzeRequest(BaseModel):
    """Free-text case narrative submitted for one-shot screening."""

    description: str = Field(..., min_length=1, description="Free-text case description")


class AnalyzeResponse(BaseModel):
    """Screening payload returned by quick analysis.

    Fields mirror the lead-scoring pipeline output: decision, score, citations,
    tool results (SOL, conflict, estimate, routing), and guardrail flags.
    Extra keys from the pipeline are allowed via ``extra="allow"``.
    """

    decision: str | None = None
    qualified: bool | None = None
    priority: str | None = None
    lead_score: int | None = None
    explanation: str | None = None
    escalate: bool | None = None
    agent_message: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    parsed_facts: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float | None = None
    cost: float | None = None

    model_config = {"extra": "allow"}


# --- Multi-turn interview --------------------------------------------------


class CreateInterviewResponse(BaseModel):
    """First assistant turn after a new interview session is created."""

    session_id: str
    phase: str
    assistant_message: str
    missing_fields: list[str] = Field(default_factory=list)
    done: bool = False


class InterviewTurnRequest(BaseModel):
    """Client reply for one interview turn."""

    message: str = Field(..., min_length=1, description="Client reply for this turn")


class InterviewTurnResponse(BaseModel):
    """Assistant reply plus collected facts; includes screening when ``done``."""

    session_id: str
    phase: str
    assistant_message: str
    missing_fields: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    done: bool = False
    screening: dict[str, Any] | None = None
