"""Agno tool: Postgres kb_docs fallback when structured sources lack information."""

from __future__ import annotations

from agno.tools import tool
from pydantic import BaseModel, Field

from tools.common import logger, tool_timer, vector_search

TOOL_NAME = "kb_docs_fallback"
KB_FALLBACK_TOP_K = 3
KB_FALLBACK_HIT_CONFIDENCE = 0.55
KB_FALLBACK_MISS_CONFIDENCE = 0.1


class KbDocsFallbackInput(BaseModel):
    query: str = Field(..., description="Search query for SOL, settlements, or availability")


class KbDocsFallbackOutput(BaseModel):
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)


# Backward-compatible aliases
WebSearchFallbackInput = KbDocsFallbackInput
WebSearchFallbackOutput = KbDocsFallbackOutput


@tool(
    name=TOOL_NAME,
    description=(
        "Fallback retrieval when structured tools lack information. "
        "Searches Postgres kb_docs only (no live web, no disk file reads)."
    ),
)
def kb_docs_fallback(payload: KbDocsFallbackInput) -> KbDocsFallbackOutput:
    """
    Deterministic fallback search against Postgres kb_docs.

    Side-effect free: no public internet and no direct kb/ file reads.
    """
    with tool_timer(TOOL_NAME):
        return _kb_docs_fallback_impl(payload)


# Legacy Agno / import name
web_search_fallback = kb_docs_fallback


def _kb_docs_fallback_impl(payload: KbDocsFallbackInput) -> KbDocsFallbackOutput:
    try:
        query = payload.query.strip()
        if not query:
            return KbDocsFallbackOutput(
                text="FALLBACK: empty query. No search performed.",
                confidence=0.0,
            )

        hits = vector_search(query, top_k=KB_FALLBACK_TOP_K)
        if hits:
            snippets = []
            for hit in hits:
                meta = hit.get("metadata") or {}
                snippets.append(
                    f"- [{meta.get('doc_type', 'unknown')} / {meta.get('practice_area', '')}] "
                    f"{str(hit.get('text') or '')[:240]}"
                )
            return KbDocsFallbackOutput(
                text=(
                    "FALLBACK SOURCE: Postgres kb_docs (not live web).\n"
                    + "\n".join(snippets)
                ),
                confidence=KB_FALLBACK_HIT_CONFIDENCE,
            )

        return KbDocsFallbackOutput(
            text=(
                "FALLBACK: insufficient kb_docs data for query "
                f"'{query}'. Live web search is not enabled; "
                "escalate to attorney research for SOL rules, settlements, or availability."
            ),
            confidence=KB_FALLBACK_MISS_CONFIDENCE,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("%s failed: %s", TOOL_NAME, exc)
        return KbDocsFallbackOutput(
            text=f"FALLBACK: tool error ({exc}). Manual research required.",
            confidence=0.0,
        )


if __name__ == "__main__":
    print(
        kb_docs_fallback.entrypoint(
            KbDocsFallbackInput(query="statute of limitations personal injury")
        )
    )
