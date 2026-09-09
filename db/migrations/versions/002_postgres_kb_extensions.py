"""Postgres extensions + heterogeneous kb_docs vector table.

Revision ID: 002_pg_kb
Revises: 001_initial
Create Date: 2026-09-09
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_pg_kb"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _embedding_dims() -> int:
    return int(os.getenv("LEXINTAKE_EMBEDDING_DIMS", "1536"))


def upgrade() -> None:
    dims = _embedding_dims()
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.execute(
        sa.text(
            f"""
            CREATE TABLE IF NOT EXISTS kb_docs (
                chunk_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                embedding vector({dims}) NOT NULL,
                doc_type TEXT NOT NULL DEFAULT '',
                practice_area TEXT NOT NULL DEFAULT '',
                jurisdictions TEXT[] NOT NULL DEFAULT '{{}}',
                content_hash TEXT,
                embedding_model TEXT,
                embedding_dimensions INTEGER,
                payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX IF NOT EXISTS idx_kb_docs_embedding_hnsw
            ON kb_docs USING hnsw (embedding vector_cosine_ops)
            """
        )
    )
    op.execute(
        sa.text("CREATE INDEX IF NOT EXISTS idx_kb_docs_doc_type ON kb_docs (doc_type)")
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_kb_docs_practice_area ON kb_docs (practice_area)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_kb_docs_jurisdictions "
            "ON kb_docs USING gin (jurisdictions)"
        )
    )
    op.execute(
        sa.text("CREATE INDEX IF NOT EXISTS idx_kb_docs_payload ON kb_docs USING gin (payload)")
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS idx_kb_docs_text_trgm "
            "ON kb_docs USING gin (text gin_trgm_ops)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS kb_docs CASCADE"))
