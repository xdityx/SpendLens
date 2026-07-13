"""Add credit-card statement balance tracking.

Revision ID: 20260714_0004
Revises: 20260713_0003
Create Date: 2026-07-14 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260714_0004"
down_revision: Union[str, None] = "20260713_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("statement_balance", sa.Numeric(precision=14, scale=2), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("accounts", sa.Column("statement_due_date", sa.Date(), nullable=True))
    op.add_column("accounts", sa.Column("statement_balance_as_of", sa.DateTime(timezone=False), nullable=True))
    op.create_check_constraint(
        "ck_accounts_statement_balance_non_negative",
        "accounts",
        "statement_balance >= 0",
    )
    op.create_check_constraint(
        "ck_accounts_statement_fields",
        "accounts",
        """
        (
            account_type = 'credit_card'
            AND (
                (statement_balance = 0 AND statement_due_date IS NULL AND statement_balance_as_of IS NULL)
                OR
                (statement_balance > 0 AND statement_due_date IS NOT NULL AND statement_balance_as_of IS NOT NULL)
            )
        )
        OR
        (
            account_type IN ('bank', 'cash', 'wallet')
            AND statement_balance = 0
            AND statement_due_date IS NULL
            AND statement_balance_as_of IS NULL
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint("ck_accounts_statement_fields", "accounts", type_="check")
    op.drop_constraint("ck_accounts_statement_balance_non_negative", "accounts", type_="check")
    op.drop_column("accounts", "statement_balance_as_of")
    op.drop_column("accounts", "statement_due_date")
    op.drop_column("accounts", "statement_balance")
