"""Compatibility shim — use tools.kb_docs_fallback."""

from __future__ import annotations

from tools.kb_docs_fallback import (  # noqa: F401
    KbDocsFallbackInput,
    KbDocsFallbackOutput,
    WebSearchFallbackInput,
    WebSearchFallbackOutput,
    kb_docs_fallback,
    web_search_fallback,
)

__all__ = [
    "KbDocsFallbackInput",
    "KbDocsFallbackOutput",
    "WebSearchFallbackInput",
    "WebSearchFallbackOutput",
    "kb_docs_fallback",
    "web_search_fallback",
]
