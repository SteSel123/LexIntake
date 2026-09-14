"""Multi-turn prospective-client interview for LexIntake.

``InterviewSession`` drives a conversational intake: greet, collect required
fields via targeted questions, merge LLM structured extraction into ``IntakeFacts``,
then hand off to the full ``IntakeAgent`` screening pipeline when enough data exists
(or the user asks to finish early with practice area + jurisdiction known).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.intake.agent import IntakeAgent, build_default_agent
from agents.intake.constants import (
    INTERVIEW_PROSPECT_NAME,
    LEGAL_DISCLAIMER,
    SENTINEL_NAME,
    SENTINEL_PARTY,
    UNCERTAINTY_ESCALATION,
)
from agents.intake.models import IntakeFacts, IntakeResponse
from agents.prompts import load_prompts

InterviewPhase = Literal["greeting", "collecting", "screening", "done"]

# Minimum fields before running full screening (sentinel names count as missing)
REQUIRED_FIELDS = (
    "name",
    "practice_area",
    "jurisdiction",
    "incident_date",
    "opposing_party",
    "damages",
)

PROMPTS = load_prompts(Path(__file__).with_name("prompts.xml"))
FIELD_PROMPTS = PROMPTS.mapping("field_prompts")


class ChatMessage(BaseModel):
    """Single turn in the interview conversation history."""

    role: Literal["assistant", "user", "system"]
    content: str


class InterviewTurnResult(BaseModel):
    """Payload returned after ``start()`` or ``respond()`` for one interview turn."""

    phase: InterviewPhase
    assistant_message: str
    facts: IntakeFacts
    missing_fields: list[str] = Field(default_factory=list)
    screening: IntakeResponse | None = None
    done: bool = False


@dataclass
class InterviewSession:
    """Stateful multi-turn intake interview."""

    agent: IntakeAgent | None = None
    facts: IntakeFacts = field(default_factory=IntakeFacts)
    messages: list[ChatMessage] = field(default_factory=list)
    phase: InterviewPhase = "greeting"
    max_questions_per_turn: int = 2

    def __post_init__(self) -> None:
        if self.agent is None:
            self.agent = build_default_agent()

    def missing_fields(self) -> list[str]:
        """Return required field keys still empty or holding placeholder sentinel values."""
        from agents.intake.fact_parse import is_valid_jurisdiction

        values = self.facts.model_dump()
        missing: list[str] = []
        for key in REQUIRED_FIELDS:
            val = values.get(key)
            if key == "name" and (not val or val == SENTINEL_NAME):
                missing.append(key)
            elif key == "opposing_party" and (not val or val == SENTINEL_PARTY):
                missing.append(key)
            elif key == "jurisdiction" and not is_valid_jurisdiction(
                str(val) if val is not None else None
            ):
                missing.append(key)
            elif key not in {"name", "opposing_party", "jurisdiction"} and val in (
                None,
                "",
                [],
            ):
                missing.append(key)
        return missing

    def start(self) -> InterviewTurnResult:
        """Open the interview with welcome text and the first practice-area question."""
        self.phase = "collecting"
        msg = PROMPTS.text(
            "welcome",
            legal_disclaimer=LEGAL_DISCLAIMER,
            first_question=FIELD_PROMPTS["practice_area"],
        )
        self.messages.append(ChatMessage(role="assistant", content=msg))
        return InterviewTurnResult(
            phase=self.phase,
            assistant_message=msg,
            facts=self.facts,
            missing_fields=self.missing_fields(),
            done=False,
        )

    def _merge_text_into_facts(self, text: str) -> None:
        """Fill facts via LLM structured extraction (money/date/jurisdiction included)."""
        cleaned = text.strip()

        # Direct answers to name / opposing prompts (identity strings only).
        last_q = ""
        for m in reversed(self.messages):
            if m.role == "assistant":
                last_q = m.content.lower()
                break
        if "name" in last_q and "full name" in last_q:
            self.facts.name = cleaned[:120]
        if "opposing" in last_q or "at-fault" in last_q:
            self.facts.opposing_party = cleaned[:160]

        assert self.agent is not None
        extracted = self.agent.extract_facts(cleaned, base=self.facts)
        if isinstance(extracted, IntakeFacts):
            self.facts = extracted
        else:
            # Offline / stub agent: keep narrative only (no regex field inference).
            prior = (self.facts.narrative or "").strip()
            self.facts.narrative = (
                f"{prior}\n{cleaned}".strip() if prior and prior != cleaned else cleaned
            )

    def _questions_message(self, missing: list[str]) -> str:
        """Format follow-ups from ``FIELD_PROMPTS``.

        ``incident_date`` is always asked alone so the date picker / answer
        is not mixed with other fields in the same turn.
        """
        if "incident_date" in missing:
            asks = ["incident_date"]
        else:
            asks = missing[: self.max_questions_per_turn]
        lines = [FIELD_PROMPTS[f] for f in asks if f in FIELD_PROMPTS]
        preface = PROMPTS.text("questions_preface")
        return preface + "\n\n" + "\n".join(f"- {q}" for q in lines)

    def respond(self, user_text: str) -> InterviewTurnResult:
        """Process one user reply: extract facts, ask more questions, or run screening."""
        text = (user_text or "").strip()
        if not text:
            msg = PROMPTS.text("empty_reply")
            self.messages.append(ChatMessage(role="assistant", content=msg))
            return InterviewTurnResult(
                phase=self.phase,
                assistant_message=msg,
                facts=self.facts,
                missing_fields=self.missing_fields(),
            )

        self.messages.append(ChatMessage(role="user", content=text))
        self._merge_text_into_facts(text)
        missing = self.missing_fields()

        from agents.intake.fact_parse import is_valid_jurisdiction

        # Early exit: user signals done and we have enough context for a meaningful screen
        finish = any(
            p in text.lower()
            for p in ("done", "that's all", "thats all", "screen now", "finish", "ready")
        )
        can_finish_early = bool(
            finish
            and self.facts.practice_area
            and is_valid_jurisdiction(self.facts.jurisdiction)
        )
        if missing and not can_finish_early:
            self.phase = "collecting"
            msg = self._questions_message(missing)
            # Soft reminder of disclaimer once in a while
            if len(self.messages) <= 3:
                msg = f"{msg}\n\n{LEGAL_DISCLAIMER}"
            self.messages.append(ChatMessage(role="assistant", content=msg))
            return InterviewTurnResult(
                phase=self.phase,
                assistant_message=msg,
                facts=self.facts,
                missing_fields=missing,
                done=False,
            )

        # Enough information — run full screening pipeline
        self.phase = "screening"
        assert self.agent is not None
        # Replace parse-time sentinels with interview-specific labels before screening
        if not self.facts.name or self.facts.name == SENTINEL_NAME:
            self.facts.name = (
                self.facts.name
                if self.facts.name and self.facts.name != SENTINEL_NAME
                else INTERVIEW_PROSPECT_NAME
            )
        if not self.facts.opposing_party or self.facts.opposing_party == SENTINEL_PARTY:
            self.facts.opposing_party = self.facts.opposing_party or SENTINEL_PARTY

        screening = self.agent.run_intake(self.facts)
        self.phase = "done"
        summary = screening.message
        if screening.escalate and UNCERTAINTY_ESCALATION not in summary:
            summary = f"{summary}\n\n{UNCERTAINTY_ESCALATION}"
        closing = PROMPTS.text("closing", summary=summary)
        self.messages.append(ChatMessage(role="assistant", content=closing))
        return InterviewTurnResult(
            phase=self.phase,
            assistant_message=closing,
            facts=self.facts,
            missing_fields=[],
            screening=screening,
            done=True,
        )


def build_interview_session(**kwargs: Any) -> InterviewSession:
    """Factory for ``InterviewSession`` with optional custom agent or facts."""
    return InterviewSession(**kwargs)
