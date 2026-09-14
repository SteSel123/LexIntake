"""Add structured SOL duration columns to sol_rules.

Revision ID: 004_sol_duration
Revises: 003_kb_ref
Create Date: 2026-09-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_sol_duration"
down_revision: Union[str, Sequence[str], None] = "003_kb_ref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sol_rules", sa.Column("duration_days", sa.Integer(), nullable=True))
    op.add_column(
        "sol_rules",
        sa.Column("open_ended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("sol_rules", "open_ended")
    op.drop_column("sol_rules", "duration_days")
