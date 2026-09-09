"""
KB retrieval for the intake agent (PostgreSQL + pgvector).

Searches `kb_docs` per planned doc_type, dedupes chunks, and builds short
citations for the screening message / self-check.
"""

from __future__ import annotations

from typing import Any, Callable

from agents.intake.models import IntakeFacts, KBCitation, PlanResult, RetrieveResult
from tools.common import match_practice_area


def retrieve(
    facts: IntakeFacts,
    plan: PlanResult,
    *,
    top_k: int,
    log: Callable[[str, str], None] | None = None,
) -> RetrieveResult:
    """
    Query kb_docs with metadata filters; return top-k chunks + citations.

    Skips entirely when `plan.need_retrieval` is False (incomplete / no query signal).
    Embeds the query once, then relaxes filters; falls back to fuzzy / any-row
    lookups so smoke scenarios still get grounding citations when filters miss.
    """
    if not plan.need_retrieval:
        if log:
            log("retrieve", "skipped (not needed)")
        return RetrieveResult()

    practice_area = match_practice_area(facts.case_type or facts.practice_area or "")
    query = plan.retrieval_query or (facts.narrative or practice_area or "intake")
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _ingest(hits: list[dict[str, Any]]) -> None:
        for hit in hits:
            chunk_id = str(hit.get("chunk_id") or "")
            # Dedupe across doc_type queries so the same chunk is not cited twice.
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                collected.append(hit)

    try:
        from db.pgvector_store import (
            fuzzy_text_search,
            list_kb_docs,
            search_kb_docs,
        )
        from etl.transform.embeddings import get_embedder

        # One embedding for all filter variants (avoids rate-limit / silent empty retries).
        vector = get_embedder().embed([query])[0]
        doc_types = list(plan.doc_types) if plan.doc_types else [None]
        filter_passes: list[dict[str, Any]] = [
            {
                "practice_area": practice_area,
                "jurisdiction": facts.jurisdiction,
                "doc_type": doc_type,
            }
            for doc_type in doc_types
        ]
        filter_passes.extend(
            [
                {
                    "practice_area": practice_area,
                    "jurisdiction": None,
                    "doc_type": doc_types[0],
                },
                {"practice_area": practice_area, "jurisdiction": None, "doc_type": None},
                {"practice_area": None, "jurisdiction": None, "doc_type": None},
            ]
        )

        for filters in filter_passes:
            if collected:
                break
            _ingest(
                search_kb_docs(
                    vector,
                    top_k=top_k,
                    practice_area=filters["practice_area"],
                    jurisdiction=filters["jurisdiction"],
                    doc_type=filters["doc_type"],
                )
            )

        # Lexical fallback — no extra embedding call.
        if not collected:
            _ingest(fuzzy_text_search(query, top_k=top_k))
        if not collected and practice_area:
            _ingest(list_kb_docs(top_k=top_k, practice_area=practice_area))
        if not collected:
            _ingest(list_kb_docs(top_k=top_k))
    except Exception as exc:  # noqa: BLE001
        if log:
            log("retrieve", f"vector path failed: {type(exc).__name__}: {exc}")
        try:
            from db.pgvector_store import list_kb_docs

            _ingest(list_kb_docs(top_k=top_k, practice_area=practice_area))
            if not collected:
                _ingest(list_kb_docs(top_k=top_k))
        except Exception as inner:  # noqa: BLE001
            if log:
                log("retrieve", f"list fallback failed: {type(inner).__name__}: {inner}")

    collected = collected[:top_k]
    # Compact citations for the UI / LLM message (excerpt truncated for prompt size).
    citations = [
        KBCitation(
            chunk_id=str(hit.get("chunk_id") or "unknown"),
            practice_area=str((hit.get("metadata") or {}).get("practice_area") or ""),
            doc_type=str((hit.get("metadata") or {}).get("doc_type") or ""),
            excerpt=str(hit.get("text") or "")[:220],
        )
        for hit in collected
    ]

    try:
        from db.pgvector_store import count_rows
        from monitoring.logger import log_retrieval

        total = count_rows()
        log_retrieval(query, hits=len(collected), total_chunks=total)
    except Exception as exc:  # noqa: BLE001
        if log:
            log("retrieve", f"retrieval metrics failed: {exc}")

    if log:
        log(
            "retrieve",
            f"query_len={len(query)} practice_area={practice_area} "
            f"jurisdiction={facts.jurisdiction} hits={len(collected)}",
        )
    return RetrieveResult(chunks=collected, citations=citations)
