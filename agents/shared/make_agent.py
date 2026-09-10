"""Shared Agno agent factory and wiring helpers.

Provides a single entry point for constructing configured ``Agent`` instances:
model resolution, optional OpenTelemetry tracing, and version-safe kwargs so
LexIntake works across Agno releases that add or rename constructor flags.
"""

from __future__ import annotations

import inspect
from typing import Any, Sequence

from agno.agent import Agent

from agents.llm import build_model


def resolve_model(
    provider: str,
    model_id: str | None = None,
    model: Any | None = None,
) -> Any:
    """Resolve an Agno LLM model. Live API credentials are required."""
    if model is not None:
        return model
    return build_model(provider, model_id)


def enable_tracing() -> None:
    """Best-effort Agno OpenTelemetry tracing setup."""
    try:
        from monitoring.agno_tracing import enable_agno_monitoring

        enable_agno_monitoring()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("agents.shared").warning(
            "Agno tracing setup skipped: %s: %s", type(exc).__name__, exc
        )


def prepare_agent_kwargs(
    *,
    name: str,
    tools: Sequence[Any],
    instructions: str | list[str] | None,
    model: Any | None = None,
    markdown: bool = True,
    reasoning: bool = True,
    tool_choice: str | None = "auto",
    output_schema: Any | None = None,
    structured_outputs: bool | None = None,
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
    # Only pass kwargs the installed Agno version accepts (avoids TypeError on upgrade)
    supported = inspect.signature(Agent.__init__).parameters
    if reasoning and "reasoning" in supported:
        agent_kwargs["reasoning"] = True
    if tool_choice is not None and "tool_choice" in supported:
        agent_kwargs["tool_choice"] = tool_choice
    if output_schema is not None and "output_schema" in supported:
        agent_kwargs["output_schema"] = output_schema
        if structured_outputs is None:
            structured_outputs = True
    if structured_outputs is not None and "structured_outputs" in supported:
        agent_kwargs["structured_outputs"] = structured_outputs
    if output_schema is not None and "parse_response" in supported:
        agent_kwargs["parse_response"] = True
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
    output_schema: Any | None = None,
    structured_outputs: bool | None = None,
    enable_monitoring: bool = True,
    **kwargs: Any,
) -> Agent:
    """
    Construct a configured Agno ``Agent``.

    Used for shared wiring (model, tracing, reasoning/tool_choice). Subclasses
    that need custom ``__init__`` state should call ``resolve_model``,
    ``enable_tracing``, and ``prepare_agent_kwargs`` instead, then ``super()``.
    """
    # Fallback defaults allow importing in minimal test environments without config
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
            output_schema=output_schema,
            structured_outputs=structured_outputs,
            **kwargs,
        )
    )
