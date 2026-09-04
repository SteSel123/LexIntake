"""LLM factory and completion helpers for LexIntake."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    require_openai_api_key,
)


def build_model(
    provider: str | None = None,
    model_id: str | None = None,
) -> Any:
    """Build an Agno model for the requested provider."""
    active = (provider or LLM_PROVIDER or "openai").lower()
    model = model_id or LLM_MODEL

    aliases = {
        "claude-3.5-sonnet": "claude-3-5-sonnet-latest",
        "claude-3-5-sonnet": "claude-3-5-sonnet-latest",
        "llama-3-70b": "llama-3.3-70b-versatile",
        "llama3-70b": "llama3-70b-8192",
    }
    model = aliases.get(model or "", model)

    if active in {"local", "deterministic", "hash", "none"}:
        raise RuntimeError(f"Provider {active} has no remote LLM")

    if active == "openai":
        from agno.models.openai import OpenAIChat

        return OpenAIChat(id=model or "gpt-4.1", api_key=require_openai_api_key())

    if active == "anthropic":
        from agno.models.anthropic import Claude

        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is missing in .env")
        return Claude(id=model or "claude-3-5-sonnet-latest", api_key=ANTHROPIC_API_KEY)

    if active == "groq":
        from agno.models.groq import Groq

        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing in .env")
        return Groq(id=model or "llama-3.3-70b-versatile", api_key=GROQ_API_KEY)

    raise ValueError(f"Unsupported LLM provider: {active}")


def provider_available(provider: str) -> bool:
    p = provider.lower()
    if p in {"local", "deterministic", "hash", "none"}:
        return True
    if p == "openai":
        return bool(OPENAI_API_KEY)
    if p == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    if p == "groq":
        return bool(GROQ_API_KEY)
    return False


COST_RATES = {
    "openai": (0.000002, 0.000008),
    "anthropic": (0.000003, 0.000015),
    "groq": (0.0000006, 0.0000008),
}


@dataclass
class CompletionResult:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


def estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    inn, out = COST_RATES.get(provider, COST_RATES["openai"])
    return input_tokens * inn + output_tokens * out


def parse_json_object(raw: str) -> dict[str, Any] | None:
    """Extract the first JSON object from an LLM reply."""
    if not raw:
        return None
    try:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        payload = json.loads(match.group(0) if match else raw)
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001
        return None


def complete(model: Any, prompt: str, *, system: str | None = None) -> CompletionResult:
    """Single-shot LLM completion (no tool loop)."""
    if not model:
        return CompletionResult(content="")
    from agno.models.message import Message

    messages = []
    if system:
        messages.append(Message(role="system", content=system))
    messages.append(Message(role="user", content=prompt))
    response = model.response(messages)
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
    if in_tok == 0 and out_tok == 0:
        in_tok = max(1, len(prompt) // 4)
        out_tok = max(1, len(str(content)) // 4)
    total = int(getattr(response, "total_tokens", 0) or (in_tok + out_tok))
    return CompletionResult(
        content=str(content).strip(),
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=total,
    )

