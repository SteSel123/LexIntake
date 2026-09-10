"""Generate embeddings for chunked KB documents via OpenAI (Agno adapter).

Supports incremental loads: unchanged chunks reuse stored vectors when model,
dimensions, and ``content_hash`` all match the existing row.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

try:
    from config import (
        EMBED_DIMS,
        EMBED_MODEL,
        EMBED_PROVIDER,
        OPENAI_API_KEY,
        require_openai_api_key,
    )
except ImportError:  # pragma: no cover
    EMBED_PROVIDER = os.getenv("LEXINTAKE_EMBEDDING_PROVIDER", "openai")
    EMBED_MODEL = os.getenv("LEXINTAKE_EMBEDDING_MODEL", "text-embedding-3-small")
    EMBED_DIMS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "1536"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    def require_openai_api_key() -> str:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is missing")
        return OPENAI_API_KEY


DEFAULT_MODEL = EMBED_MODEL
DEFAULT_DIMENSIONS = EMBED_DIMS


class Embedder(Protocol):
    """Minimal interface the ETL pipeline expects from any embedding backend."""

    model_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbedderAdapter:
    """Adapter around Agno OpenAIEmbedder exposing LexIntake .embed(texts)."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        self.model_name = model_name or EMBED_MODEL
        key = api_key or require_openai_api_key()
        dims = dimensions or EMBED_DIMS
        self._inner = OpenAIEmbedder(
            id=self.model_name,
            api_key=key,
            dimensions=dims,
            enable_batch=True,
            batch_size=64,
        )
        self.dimensions = int(self._inner.dimensions or dims)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for text in texts:
            vec = self._inner.get_embedding(text or " ")
            if not vec:
                vectors.append([0.0] * self.dimensions)
            else:
                vectors.append([float(x) for x in vec])
        return vectors


def get_embedder(provider: str | None = None) -> Embedder:
    """Factory for the active embedder implementation."""
    active = (provider or EMBED_PROVIDER or "openai").lower()
    if active in {"openai", "openai_embedder"}:
        return OpenAIEmbedderAdapter()
    raise ValueError(
        f"Unsupported LEXINTAKE_EMBEDDING_PROVIDER={active!r}. Supported: openai."
    )


def _needs_embedding(chunk: dict[str, Any], existing: dict[str, Any] | None, model: Embedder) -> bool:
    """True when no prior row exists or model/dims/content changed since last load."""
    if not existing:
        return True
    if existing.get("embedding_model") != model.model_name:
        return True
    if existing.get("embedding_dimensions") != model.dimensions:
        return True
    existing_hash = (existing.get("metadata") or {}).get("content_hash") or existing.get("content_hash")
    return existing_hash != chunk.get("content_hash")


def embed_chunks(
    chunks: list[dict[str, Any]],
    embedder: Embedder | None = None,
    existing_by_id: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Attach embedding vectors to chunks (incremental when possible)."""
    model = embedder or get_embedder()
    existing_by_id = existing_by_id or {}

    to_embed: list[dict[str, Any]] = []
    reuse: list[dict[str, Any]] = []

    for chunk in chunks:
        prior = existing_by_id.get(chunk.get("chunk_id"))
        if _needs_embedding(chunk, prior, model):
            to_embed.append(chunk)
        else:
            reused = dict(chunk)
            reused["embedding"] = prior.get("embedding")
            reused["embedding_model"] = prior.get("embedding_model")
            reused["embedding_dimensions"] = prior.get("embedding_dimensions")
            reuse.append(reused)

    vectors = model.embed([c.get("text", "") for c in to_embed]) if to_embed else []
    embedded: list[dict[str, Any]] = []
    for chunk, vector in zip(to_embed, vectors, strict=True):
        record = dict(chunk)
        record["embedding"] = vector
        record["embedding_model"] = model.model_name
        record["embedding_dimensions"] = model.dimensions
        embedded.append(record)

    by_id = {r["chunk_id"]: r for r in reuse + embedded}
    ordered = [by_id[c["chunk_id"]] for c in chunks if c.get("chunk_id") in by_id]
    stats = {"embedded": len(embedded), "reused": len(reuse), "total": len(ordered)}
    return ordered, stats


if __name__ == "__main__":
    from etl.extract.documents import extract_all
    from etl.transform.chunk import chunk_all
    from etl.transform.clean import clean_all
    from etl.transform.deduplicate import deduplicate_all
    from etl.transform.metadata import attach_metadata_all

    records, stats = embed_chunks(
        attach_metadata_all(chunk_all(deduplicate_all(clean_all(extract_all()))))
    )
    print(f"Embedded stats={stats} model={records[0]['embedding_model']}")
    print(f"dims={records[0]['embedding_dimensions']} first5={records[0]['embedding'][:5]}")
