"""Shared agent construction helpers re-exported for convenience.

Import ``make_agent``, ``resolve_model``, and related wiring from here rather
than reaching into ``agents.shared.make_agent`` directly.
"""

from agents.shared.make_agent import (
    enable_tracing,
    make_agent,
    prepare_agent_kwargs,
    resolve_model,
)

__all__ = [
    "enable_tracing",
    "make_agent",
    "prepare_agent_kwargs",
    "resolve_model",
]
