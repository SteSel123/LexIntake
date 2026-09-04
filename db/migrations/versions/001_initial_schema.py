"""Initial clients, attorneys, and past_cases schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-09-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_clients_state", "clients", ["state"])

    op.create_table(
        "attorneys",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("specialization", sa.Text(), nullable=False),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("jurisdictions", sa.Text(), nullable=True),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_attorneys_availability", "attorneys", ["availability"])

    op.create_table(
        "past_cases",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("practice_area", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("facts", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("settlement_amount", sa.Integer(), nullable=True),
        sa.Column("attorney_id", sa.Text(), nullable=True),
        sa.Column("client_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.ForeignKeyConstraint(["attorney_id"], ["attorneys.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_past_cases_practice_area", "past_cases", ["practice_area"])
    op.create_index("idx_past_cases_jurisdiction", "past_cases", ["jurisdiction"])
    op.create_index("idx_past_cases_attorney_id", "past_cases", ["attorney_id"])
    op.create_index("idx_past_cases_client_id", "past_cases", ["client_id"])


def downgrade() -> None:
    op.drop_index("idx_past_cases_client_id", table_name="past_cases")
    op.drop_index("idx_past_cases_attorney_id", table_name="past_cases")
    op.drop_index("idx_past_cases_jurisdiction", table_name="past_cases")
    op.drop_index("idx_past_cases_practice_area", table_name="past_cases")
    op.drop_table("past_cases")
    op.drop_index("idx_attorneys_availability", table_name="attorneys")
    op.drop_table("attorneys")
    op.drop_index("idx_clients_state", table_name="clients")
    op.drop_table("clients")
