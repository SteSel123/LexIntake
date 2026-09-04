"""LanceDB retrieval for the intake agent."""

from __future__ import annotations

from typing import Any, Callable

from agents.intake.models import IntakeFacts, KBCitation, PlanResult, RetrieveResult
from common import match_practice_area, vector_search


def retrieve(
    facts: IntakeFacts,
    plan: PlanResult,
    *,
    top_k: int,
    log: Callable[[str, str], None] | None = None,
) -> RetrieveResult:
    """Query LanceDB kb_docs with metadata filters; return top-k chunks."""
    if not plan.need_retrieval:
        if log:
            log("retrieve", "skipped (not needed)")
        return RetrieveResult()

    practice_area = match_practice_area(facts.case_type or facts.practice_area or "")
    query = plan.retrieval_query or (facts.narrative or practice_area or "intake")
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for doc_type in plan.doc_types or [None]:
        hits = vector_search(
            query,
            top_k=top_k,
            practice_area=practice_area,
            jurisdiction=facts.jurisdiction,
            doc_type=doc_type,
            log=False,
        )
        for hit in hits:
            chunk_id = str(hit.get("chunk_id") or "")
            if chunk_id and chunk_id not in seen:
                seen.add(chunk_id)
                collected.append(hit)

    collected = collected[:top_k]
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
        from lancedb_store import ensure_kb_docs
        from monitoring.logger import log_retrieval

        total = int(ensure_kb_docs().count_rows())
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
