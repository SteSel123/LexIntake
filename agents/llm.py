"""LLM factory and single-shot completion helpers for LexIntake.

Centralizes provider selection (OpenAI, Anthropic, Groq), model alias resolution,
token usage extraction, and structured/unstructured Agno agent runs. Intake and
interview agents call these helpers instead of wiring Agno directly.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from config import (
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    require_openai_api_key,
)
from monitoring.app_logging import get_console_logger, log_optional_failure

TModel = TypeVar("TModel", bound=BaseModel)
_logger = get_console_logger("agents.llm")


def _agent_kwargs(**kwargs: Any) -> dict[str, Any]:
    """Keep only Agent.__init__ kwargs supported by the installed Agno version."""
    from agno.agent import Agent

    supported = inspect.signature(Agent.__init__).parameters
    return {key: value for key, value in kwargs.items() if key in supported}


def build_model(
    provider: str | None = None,
    model_id: str | None = None,
) -> Any:
    """Build an Agno model for the requested provider."""
    active = (provider or LLM_PROVIDER or "openai").lower()
    model = model_id or LLM_MODEL

    # Friendly config names → provider-specific model IDs
    aliases = {
        "claude-3.5-sonnet": "claude-3-5-sonnet-latest",
        "claude-3-5-sonnet": "claude-3-5-sonnet-latest",
        "llama-3-70b": "llama-3.3-70b-versatile",
        "llama3-70b": "llama3-70b-8192",
    }
    model = aliases.get(model or "", model)

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
    """Return True when the provider's API key is configured in the environment."""
    p = provider.lower()
    if p == "openai":
        return bool(OPENAI_API_KEY)
    if p == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    if p == "groq":
        return bool(GROQ_API_KEY)
    return False


# Approximate USD per input/output token for cost telemetry (not billing-accurate)
COST_RATES = {
    "openai": (0.000002, 0.000008),
    "anthropic": (0.000003, 0.000015),
    "groq": (0.0000006, 0.0000008),
}


@dataclass
class CompletionResult:
    """Normalized result from a single LLM call, with optional parsed Pydantic payload."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    parsed: BaseModel | None = None


def estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate call cost in USD using rough per-provider token rates."""
    inn, out = COST_RATES.get(provider, COST_RATES["openai"])
    return input_tokens * inn + output_tokens * out


def _usage_from_run(run_out: Any, prompt: str, content: Any) -> tuple[int, int, int]:
    """Extract token counts from Agno run output, with char-length fallback when missing."""
    metrics = getattr(run_out, "metrics", None)
    in_tok = int(getattr(metrics, "input_tokens", None) or getattr(run_out, "input_tokens", None) or 0)
    out_tok = int(getattr(metrics, "output_tokens", None) or getattr(run_out, "output_tokens", None) or 0)
    # Some providers omit usage metadata; approximate ~4 chars per token
    if in_tok == 0 and out_tok == 0:
        in_tok = max(1, len(prompt) // 4)
        out_tok = max(1, len(str(content or "")) // 4)
    total = int(getattr(metrics, "total_tokens", None) or getattr(run_out, "total_tokens", None) or (in_tok + out_tok))
    return in_tok, out_tok, total


def _parse_structured(content: Any, output_schema: type[TModel]) -> TModel | None:
    """Coerce Agno response content into a Pydantic model; return None on failure."""
    if content is None:
        return None
    try:
        if isinstance(content, output_schema):
            return content
        if isinstance(content, BaseModel):
            return output_schema.model_validate(content.model_dump())
        if isinstance(content, dict):
            return output_schema.model_validate(content)
        if isinstance(content, str) and content.strip():
            return output_schema.model_validate_json(content)
    except (ValidationError, ValueError, TypeError) as exc:
        log_optional_failure(_logger, "structured parse", exc)
        return None
    return None


def complete_structured(
    model: Any,
    prompt: str,
    output_schema: type[TModel],
    *,
    system: str | None = None,
    name: str = "LexIntake Structured",
) -> CompletionResult:
    """Single-shot Agno run with a Pydantic ``output_schema``."""
    # Graceful no-op when LLM is disabled (tests or missing credentials)
    if not model:
        return CompletionResult(content="")
    from agno.agent import Agent

    agent = Agent(
        **_agent_kwargs(
            name=name,
            model=model,
            instructions=system,
            output_schema=output_schema,
            structured_outputs=True,
            parse_response=True,
            markdown=False,
            reasoning=False,
            telemetry=False,
        )
    )
    run_out = agent.run(prompt, output_schema=output_schema)
    parsed = _parse_structured(getattr(run_out, "content", None), output_schema)
    content = parsed.model_dump_json() if parsed is not None else str(getattr(run_out, "content", "") or "")
    in_tok, out_tok, total = _usage_from_run(run_out, prompt, content)
    return CompletionResult(
        content=content.strip(),
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=total,
        parsed=parsed,
    )


def complete(model: Any, prompt: str, *, system: str | None = None) -> CompletionResult:
    """Single-shot unstructured LLM completion (no tool loop)."""
    if not model:
        return CompletionResult(content="")
    from agno.agent import Agent

    agent = Agent(
        **_agent_kwargs(
            name="LexIntake Complete",
            model=model,
            instructions=system,
            markdown=False,
            reasoning=False,
            telemetry=False,
        )
    )
    run_out = agent.run(prompt)
    content = getattr(run_out, "content", None) or ""
    in_tok, out_tok, total = _usage_from_run(run_out, prompt, content)
    return CompletionResult(
        content=str(content).strip(),
        input_tokens=in_tok,
        output_tokens=out_tok,
        total_tokens=total,
    )

