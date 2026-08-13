"""Agno tool: offline-safe fallback when KB/DB lack information."""

from __future__ import annotations

from agno.tools import tool
from pydantic import BaseModel, Field

from common import KB_DIR, logger, tool_timer, vector_search


class WebSearchFallbackInput(BaseModel):
    query: str = Field(..., description="Search query for SOL, settlements, or availability")


class WebSearchFallbackOutput(BaseModel):
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)


@tool(
    name="web_search_fallback",
    description=(
        "Fallback retrieval when KB/DB lack information. Uses local vector KB first; "
        "clearly marks when external web search would be required (no live web side effects)."
    ),
)
def web_search_fallback(payload: WebSearchFallbackInput) -> WebSearchFallbackOutput:
    """
    Deterministic fallback search.

    Side-effect free: does not call the public internet. Searches LanceDB kb_docs,
    then KB FAQs, then returns an explicit insufficient-data fallback.
    """
    with tool_timer("web_search_fallback"):
        return _web_search_fallback_impl(payload)


def _web_search_fallback_impl(payload: WebSearchFallbackInput) -> WebSearchFallbackOutput:
    try:
        query = payload.query.strip()
        if not query:
            return WebSearchFallbackOutput(
                text="FALLBACK: empty query. No search performed.",
                confidence=0.0,
            )

        hits = vector_search(query, top_k=3)
        if hits:
            snippets = []
            for hit in hits:
                meta = hit.get("metadata") or {}
                snippets.append(
                    f"- [{meta.get('doc_type', 'unknown')} / {meta.get('practice_area', '')}] "
                    f"{str(hit.get('text') or '')[:240]}"
                )
            return WebSearchFallbackOutput(
                text=(
                    "FALLBACK SOURCE: local vector KB (not live web).\n"
                    + "\n".join(snippets)
                ),
                confidence=0.55,
            )

        faq_file = KB_DIR / "faqs.md"
        if faq_file.exists():
            faq_text = faq_file.read_text(encoding="utf-8")
            q_tokens = [tok for tok in query.lower().split() if len(tok) > 2][:4]
            lines = [ln.strip() for ln in faq_text.splitlines() if ln.strip()]
            matched = [ln for ln in lines if any(tok in ln.lower() for tok in q_tokens)]
            if matched:
                return WebSearchFallbackOutput(
                    text=(
                        "FALLBACK SOURCE: local faqs.md (not live web).\n"
                        + "\n".join(matched[:8])
                    ),
                    confidence=0.4,
                )

        return WebSearchFallbackOutput(
            text=(
                "FALLBACK: insufficient local KB/DB data for query "
                f"'{query}'. Live web search is not enabled in this deterministic tool; "
                "escalate to attorney research for SOL rules, settlements, or availability."
            ),
            confidence=0.1,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("web_search_fallback failed: %s", exc)
        return WebSearchFallbackOutput(
            text=f"FALLBACK: tool error ({exc}). Manual research required.",
            confidence=0.0,
        )


if __name__ == "__main__":
    print(
        web_search_fallback.entrypoint(
            WebSearchFallbackInput(query="statute of limitations personal injury")
        )
    )
