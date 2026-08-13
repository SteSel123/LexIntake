"""LanceDB schema for the kb_docs collection."""

from __future__ import annotations

import os

import pyarrow as pa

COLLECTION_NAME = "kb_docs"
DEFAULT_EMBEDDING_DIMS = int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "1536"))

METADATA_TYPE = pa.struct(
    [
        pa.field("practice_area", pa.string()),
        pa.field("jurisdictions", pa.list_(pa.string())),
        pa.field("doc_type", pa.string()),
    ]
)


def embedding_type(dimensions: int = DEFAULT_EMBEDDING_DIMS) -> pa.DataType:
    """Fixed-size float32 vector type for chunk embeddings."""
    return pa.list_(pa.float32(), list_size=dimensions)


def kb_docs_schema(dimensions: int = DEFAULT_EMBEDDING_DIMS) -> pa.Schema:
    """
    Schema for kb_docs.

    Primary key for upsert: chunk_id
    Fields:
      - text
      - embedding
      - metadata.practice_area
      - metadata.jurisdictions
      - metadata.doc_type
    """
    return pa.schema(
        [
            pa.field("chunk_id", pa.string(), nullable=False),
            pa.field("text", pa.string(), nullable=False),
            pa.field("embedding", embedding_type(dimensions), nullable=False),
            pa.field("metadata", METADATA_TYPE, nullable=False),
        ]
    )


def empty_kb_docs_table(dimensions: int = DEFAULT_EMBEDDING_DIMS) -> pa.Table:
    """Empty Arrow table matching kb_docs schema (used to create the collection)."""
    schema = kb_docs_schema(dimensions)
    return pa.Table.from_pylist([], schema=schema)
