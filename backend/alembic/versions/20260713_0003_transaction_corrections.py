"""Add transaction correction audit fields.

Revision ID: 20260713_0003
Revises: 20260708_0002
Create Date: 2026-07-13 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_0003"
down_revision: Union[str, None] = "20260708_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("transactions", sa.Column("voided_at", sa.DateTime(timezone=False), nullable=True))
    op.create_index("ix_transactions_voided_at", "transactions", ["voided_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_voided_at", table_name="transactions")
    op.drop_column("transactions", "voided_at")
    op.drop_column("transactions", "updated_at")