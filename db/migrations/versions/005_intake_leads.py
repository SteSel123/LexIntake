"""Create intake_leads table for persisting screened prospects.

Revision ID: 005_intake_leads
Revises: 004_sol_duration
Create Date: 2026-09-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_intake_leads"
down_revision: Union[str, Sequence[str], None] = "004_sol_duration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    created_at = sa.text("CURRENT_TIMESTAMP")
    op.create_table(
        "intake_leads",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("opposing_party", sa.Text(), nullable=True),
        sa.Column("practice_area", sa.Text(), nullable=True),
        sa.Column("case_type", sa.Text(), nullable=True),
        sa.Column("jurisdiction", sa.Text(), nullable=True),
        sa.Column("incident_date", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=True),
        sa.Column("damages", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("uncertain", sa.Boolean(), nullable=True),
        sa.Column("lead_score", sa.Integer(), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("case_viability", sa.Text(), nullable=True),
        sa.Column("escalate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("routing_recommendation", sa.Text(), nullable=True),
        sa.Column(
            "tool_results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=created_at),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_intake_leads_created_at", "intake_leads", ["created_at"])
    op.create_index("idx_intake_leads_jurisdiction", "intake_leads", ["jurisdiction"])
    op.create_index("idx_intake_leads_practice_area", "intake_leads", ["practice_area"])
    op.create_index("idx_intake_leads_decision", "intake_leads", ["decision"])


def downgrade() -> None:
    op.drop_index("idx_intake_leads_decision", table_name="intake_leads")
    op.drop_index("idx_intake_leads_practice_area", table_name="intake_leads")
    op.drop_index("idx_intake_leads_jurisdiction", table_name="intake_leads")
    op.drop_index("idx_intake_leads_created_at", table_name="intake_leads")
    op.drop_table("intake_leads")
