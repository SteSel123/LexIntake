"""Deduplicate cleaned documents before chunking."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(doc: dict[str, Any]) -> str:
    """
    Stable fingerprint for a document.

    Same logical content always yields the same hash (idempotent identity).
    """
    payload = {
        "source": doc.get("source"),
        "doc_type": doc.get("doc_type"),
        "practice_area": doc.get("practice_area"),
        "item_index": doc.get("item_index"),
        "text": doc.get("text", ""),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def deduplicate_all(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Drop exact duplicates by content hash; keep first occurrence.

    Attaches `content_hash` to each retained document for incremental loads.
    """
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    for doc in documents:
        digest = content_hash(doc)
        if digest in seen:
            continue
        seen.add(digest)
        record = dict(doc)
        record["content_hash"] = digest
        unique.append(record)

    return unique


if __name__ == "__main__":
    from clean import clean_all
    from extract import extract_all

    cleaned = clean_all(extract_all())
    unique = deduplicate_all(cleaned)
    print(f"Cleaned={len(cleaned)} unique={len(unique)} removed={len(cleaned) - len(unique)}")
