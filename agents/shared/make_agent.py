"""Shared Agno agent factory and wiring helpers."""

from __future__ import annotations

import inspect
from typing import Any, Sequence

from agno.agent import Agent

from agents.llm import build_model
from monitoring.app_logging import get_console_logger

logger = get_console_logger("agent.shared")

LOCAL_PROVIDERS = frozenset({"local", "deterministic", "hash", "none"})


def resolve_model(
    provider: str,
    model_id: str | None = None,
    model: Any | None = None,
) -> Any | None:
    """Resolve an Agno LLM model, or None for deterministic/local paths."""
    if model is not None:
        return model
    if provider in LOCAL_PROVIDERS:
        return None
    try:
        return build_model(provider, model_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "LLM unavailable (%s); agent will use deterministic fallback path.",
            exc,
        )
        return None


def enable_tracing() -> None:
    """Best-effort Agno OpenTelemetry tracing setup."""
    try:
        from monitoring.agno_tracing import enable_agno_monitoring

        enable_agno_monitoring()
    except Exception:  # noqa: BLE001
        pass


def prepare_agent_kwargs(
    *,
    name: str,
    tools: Sequence[Any],
    instructions: str | list[str] | None,
    model: Any | None = None,
    markdown: bool = True,
    reasoning: bool = True,
    tool_choice: str | None = "auto",
    **kwargs: Any,
) -> dict[str, Any]:
    """Build kwargs for ``Agent.__init__``, including version-safe Agno flags."""
    agent_kwargs: dict[str, Any] = {
        "name": name,
        "model": model,
        "tools": list(tools),
        "instructions": instructions,
        "markdown": markdown,
        **kwargs,
    }
    supported = inspect.signature(Agent.__init__).parameters
    if reasoning and "reasoning" in supported:
        agent_kwargs["reasoning"] = True
    if tool_choice is not None and "tool_choice" in supported:
        agent_kwargs["tool_choice"] = tool_choice
    return agent_kwargs


def make_agent(
    *,
    name: str,
    tools: Sequence[Any],
    instructions: str | list[str] | None,
    provider: str | None = None,
    model_id: str | None = None,
    model: Any | None = None,
    markdown: bool = True,
    reasoning: bool = True,
    tool_choice: str | None = "auto",
    enable_monitoring: bool = True,
    **kwargs: Any,
) -> Agent:
    """
    Construct a configured Agno ``Agent``.

    Used for shared wiring (model, tracing, reasoning/tool_choice). Subclasses
    that need custom ``__init__`` state should call ``resolve_model``,
    ``enable_tracing``, and ``prepare_agent_kwargs`` instead, then ``super()``.
    """
    try:
        from config import LLM_MODEL, LLM_PROVIDER
    except ImportError:  # pragma: no cover
        LLM_PROVIDER = "openai"
        LLM_MODEL = "gpt-4.1"

    active_provider = (provider or LLM_PROVIDER or "openai").lower()
    active_model_id = model_id or LLM_MODEL
    llm = resolve_model(active_provider, active_model_id, model)
    if enable_monitoring:
        enable_tracing()
    return Agent(
        **prepare_agent_kwargs(
            name=name,
            tools=tools,
            instructions=instructions,
            model=llm,
            markdown=markdown,
            reasoning=reasoning,
            tool_choice=tool_choice,
            **kwargs,
        )
    )
