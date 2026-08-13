"""Generate embeddings for chunked KB documents."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Protocol


TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)
DEFAULT_MODEL = os.getenv("LEXINTAKE_EMBEDDING_MODEL", "hash-v1")
DEFAULT_DIMENSIONS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "256"))


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbedder:
    """
    Dependency-free deterministic embedder for local development.

    Produces unit-length vectors from hashed tokens. Replace with OpenAI /
    sentence-transformers in production by implementing the Embedder protocol.
    """

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS, model_name: str = DEFAULT_MODEL) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be >= 8")
        self.dimensions = dimensions
        self.model_name = model_name

    def _tokenize(self, token: str) -> list[float]:
        vector = [0.0] * self.dimensions
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(self.dimensions):
            # Map bytes cyclically into [-1, 1]
            byte = digest[i % len(digest)]
            vector[i] = (byte / 255.0) * 2.0 - 1.0
        return vector

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            tokens = TOKEN_RE.findall(text.lower())
            if not tokens:
                vectors.append([0.0] * self.dimensions)
                continue

            acc = [0.0] * self.dimensions
            for token in tokens:
                token_vec = self._tokenize(token)
                for i, value in enumerate(token_vec):
                    acc[i] += value

            norm = math.sqrt(sum(v * v for v in acc)) or 1.0
            vectors.append([v / norm for v in acc])
        return vectors


def get_embedder() -> Embedder:
    """Factory for the active embedder implementation."""
    provider = os.getenv("LEXINTAKE_EMBEDDING_PROVIDER", "hash").lower()
    if provider == "hash":
        return HashEmbedder()
    raise ValueError(
        f"Unsupported LEXINTAKE_EMBEDDING_PROVIDER={provider!r}. "
        "Supported: 'hash'."
    )


def _needs_embedding(chunk: dict[str, Any], existing: dict[str, Any] | None, model: Embedder) -> bool:
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
    """
    Attach embedding vectors to chunks.

    Incremental: reuse stored embeddings when chunk_id + content_hash + model match.
    """
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

    # Preserve input order for stable downstream upserts
    by_id = {r["chunk_id"]: r for r in reuse + embedded}
    ordered = [by_id[c["chunk_id"]] for c in chunks if c.get("chunk_id") in by_id]
    stats = {"embedded": len(embedded), "reused": len(reuse), "total": len(ordered)}
    return ordered, stats


if __name__ == "__main__":
    from chunk import chunk_all
    from clean import clean_all
    from deduplicate import deduplicate_all
    from extract import extract_all
    from metadata import attach_metadata_all

    records, stats = embed_chunks(
        attach_metadata_all(chunk_all(deduplicate_all(clean_all(extract_all()))))
    )
    print(f"Embedded stats={stats} model={records[0]['embedding_model']}")
    print(f"dims={records[0]['embedding_dimensions']} first5={records[0]['embedding'][:5]}")
