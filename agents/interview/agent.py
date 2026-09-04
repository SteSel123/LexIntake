"""Multi-turn prospective-client interview for LexIntake."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from agents.intake.agent import IntakeAgent, build_default_agent
from agents.intake.constants import LEGAL_DISCLAIMER, UNCERTAINTY_ESCALATION
from agents.intake.models import IntakeFacts, IntakeResponse
from agents.prompts import load_prompts

InterviewPhase = Literal["greeting", "collecting", "screening", "done"]

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
    role: Literal["assistant", "user", "system"]
    content: str


class InterviewTurnResult(BaseModel):
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
        values = self.facts.model_dump()
        missing: list[str] = []
        for key in REQUIRED_FIELDS:
            val = values.get(key)
            if val in (None, "", [], "Unknown Party", "Demo Prospect"):
                # Keep Demo Prospect as incomplete for interview mode
                if key == "name" and val == "Demo Prospect":
                    missing.append(key)
                elif key == "opposing_party" and val in (None, "", "Unknown Party"):
                    missing.append(key)
                elif key not in {"name", "opposing_party"} and val in (None, "", []):
                    missing.append(key)
                elif key == "name" and not val:
                    missing.append(key)
        return missing

    def start(self) -> InterviewTurnResult:
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
        """Heuristic extraction from free-text answers (works offline)."""
        from agents.intake.fact_parse import parse_case_description

        # Prefer incremental field fills when answering a specific prompt.
        last_q = ""
        for m in reversed(self.messages):
            if m.role == "assistant":
                last_q = m.content.lower()
                break

        cleaned = text.strip()

        if "name" in last_q and "full name" in last_q:
            self.facts.name = cleaned[:120]
        elif "opposing" in last_q or "at-fault" in last_q:
            self.facts.opposing_party = cleaned[:160]
        elif "jurisdiction" in last_q or "us state" in last_q:
            m = re.search(r"\b([A-Za-z]{2})\b", cleaned)
            self.facts.jurisdiction = (m.group(1) if m else cleaned[:2]).upper()
        elif "incident" in last_q or "event date" in last_q:
            iso = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", cleaned)
            if iso:
                self.facts.incident_date = iso.group(1)
            else:
                # Allow relative phrases; fact_parse will normalize when possible
                from agents.intake.fact_parse import infer_incident_date

                inferred = infer_incident_date(cleaned)
                self.facts.incident_date = inferred or cleaned[:32]
        elif "damages" in last_q or "losses" in last_q:
            digits = re.sub(r"[^\d.]", "", cleaned.replace(",", ""))
            if digits:
                try:
                    self.facts.damages = int(float(digits))
                except ValueError:
                    pass
        elif "practice" in last_q or "legal matter" in last_q:
            self.facts.practice_area = cleaned[:80]
            self.facts.case_type = cleaned[:80]

        # Always fold narrative signals from the full utterance.
        parsed = parse_case_description(cleaned)
        if not self.facts.practice_area and parsed.practice_area:
            self.facts.practice_area = parsed.practice_area
            self.facts.case_type = parsed.case_type
        if not self.facts.jurisdiction and parsed.jurisdiction:
            self.facts.jurisdiction = parsed.jurisdiction
        if not self.facts.incident_date and parsed.incident_date:
            self.facts.incident_date = parsed.incident_date
        if self.facts.damages is None and parsed.damages is not None:
            self.facts.damages = parsed.damages
        if (not self.facts.name or self.facts.name == "Demo Prospect") and parsed.name not in (
            None,
            "Demo Prospect",
        ):
            self.facts.name = parsed.name
        if (
            not self.facts.opposing_party or self.facts.opposing_party == "Unknown Party"
        ) and parsed.opposing_party not in (None, "Unknown Party"):
            self.facts.opposing_party = parsed.opposing_party

        narrative = (self.facts.narrative or "").strip()
        self.facts.narrative = (narrative + "\n" + cleaned).strip() if narrative else cleaned
        if parsed.severity:
            self.facts.severity = parsed.severity
        if parsed.priority:
            self.facts.priority = parsed.priority

        # LLM optional extraction when available
        assert self.agent is not None
        if self.agent.llm_ready:
            self._llm_extract_fields(cleaned)

    def _llm_extract_fields(self, text: str) -> None:
        assert self.agent is not None
        prompt = PROMPTS.user(
            "extract_fields",
            facts=self.facts.model_dump_json(),
            text=text,
        )
        raw = self.agent._complete(prompt, system=PROMPTS.text("extract_system"))
        from agents.llm import parse_json_object

        data = parse_json_object(raw)
        if not data:
            return
        for key in (
            "name",
            "opposing_party",
            "practice_area",
            "jurisdiction",
            "incident_date",
            "severity",
        ):
            val = data.get(key)
            if val not in (None, ""):
                setattr(self.facts, key, val)
                if key == "practice_area":
                    self.facts.case_type = str(val)
        if data.get("damages") is not None:
            try:
                self.facts.damages = int(data["damages"])
            except (TypeError, ValueError):
                pass

    def _questions_message(self, missing: list[str]) -> str:
        asks = missing[: self.max_questions_per_turn]
        lines = [FIELD_PROMPTS[f] for f in asks if f in FIELD_PROMPTS]
        preface = PROMPTS.text("questions_preface")
        return preface + "\n\n" + "\n".join(f"- {q}" for q in lines)

    def respond(self, user_text: str) -> InterviewTurnResult:
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

        # Allow early screening if user asks to finish and we have practice area + jurisdiction
        finish = any(
            p in text.lower()
            for p in ("done", "that's all", "thats all", "screen now", "finish", "ready")
        )
        if missing and not (finish and self.facts.practice_area and self.facts.jurisdiction):
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
        if not self.facts.name or self.facts.name == "Demo Prospect":
            self.facts.name = self.facts.name if self.facts.name and self.facts.name != "Demo Prospect" else "Interview Prospect"
        if not self.facts.opposing_party or self.facts.opposing_party == "Unknown Party":
            self.facts.opposing_party = self.facts.opposing_party or "Unknown Party"

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
    return InterviewSession(**kwargs)
