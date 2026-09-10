"""Seed tables for practice_areas, sol_rules, acceptance_criteria.

Relational reference data loaded from ``kb/*.json`` via ``seed_from_kb``;
complements vector chunks in ``kb_docs`` from migration 002.

Revision ID: 003_kb_ref
Revises: 002_pg_kb
Create Date: 2026-09-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_kb_ref"
down_revision: Union[str, Sequence[str], None] = "002_pg_kb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    created_at = sa.text("CURRENT_TIMESTAMP")

    # --- practice_areas ------------------------------------------------------
    op.create_table(
        "practice_areas",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=created_at),
        sa.PrimaryKeyConstraint("name"),
    )

    # --- sol_rules (statute snippets by area + jurisdiction) -----------------
    op.create_table(
        "sol_rules",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("practice_area", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=created_at),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sol_rules_practice_area", "sol_rules", ["practice_area"])
    op.create_index("idx_sol_rules_jurisdiction", "sol_rules", ["jurisdiction"])

    # --- acceptance_criteria (JSONB rules per practice area) -----------------
    op.create_table(
        "acceptance_criteria",
        sa.Column("practice_area", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=created_at),
        sa.PrimaryKeyConstraint("practice_area"),
    )


def downgrade() -> None:
    op.drop_table("acceptance_criteria")
    op.drop_index("idx_sol_rules_jurisdiction", table_name="sol_rules")
    op.drop_index("idx_sol_rules_practice_area", table_name="sol_rules")
    op.drop_table("sol_rules")
    op.drop_table("practice_areas")
