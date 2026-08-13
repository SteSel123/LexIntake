"""LLM factory for LexIntake (OpenAI / Anthropic / Groq)."""

from __future__ import annotations

import sys
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
