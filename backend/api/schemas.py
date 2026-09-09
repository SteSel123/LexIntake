"""HTTP request/response schemas for the LexIntake API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "lexintake-api"


class AnalyzeRequest(BaseModel):
    description: str = Field(..., min_length=1, description="Free-text case description")


class AnalyzeResponse(BaseModel):
    """Screening payload returned by quick analysis."""

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


class CreateInterviewResponse(BaseModel):
    session_id: str
    phase: str
    assistant_message: str
    missing_fields: list[str] = Field(default_factory=list)
    done: bool = False


class InterviewTurnRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Client reply for this turn")


class InterviewTurnResponse(BaseModel):
    session_id: str
    phase: str
    assistant_message: str
    missing_fields: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    done: bool = False
    screening: dict[str, Any] | None = None
