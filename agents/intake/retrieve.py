"""
KB retrieval for the intake agent (PostgreSQL + pgvector).

Searches `kb_docs` per planned doc_type, dedupes chunks, and builds short
citations for the screening message / self-check.
"""

from __future__ import annotations

from typing import Any, Callable

from agents.intake.models import IntakeFacts, KBCitation, PlanResult, RetrieveResult
from tools.common import match_practice_area, vector_search


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

    # One vector search per planned doc_type (sol_rules, past_case, …), then merge.
    for doc_type in plan.doc_types or [None]:
        _ingest(
            vector_search(
                query,
                top_k=top_k,
                practice_area=practice_area,
                jurisdiction=facts.jurisdiction,
                doc_type=doc_type,
                log=False,
            )
        )

    # Progressively relax filters when metadata is too strict for the seeded KB.
    if not collected:
        _ingest(
            vector_search(
                query,
                top_k=top_k,
                practice_area=practice_area,
                doc_type=(plan.doc_types or [None])[0],
                log=False,
            )
        )
    if not collected:
        _ingest(
            vector_search(
                query,
                top_k=top_k,
                practice_area=practice_area,
                log=False,
            )
        )
    if not collected:
        _ingest(vector_search(query, top_k=top_k, log=False))

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
