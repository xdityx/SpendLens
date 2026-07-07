"""Initial Phase 1 schema.

Revision ID: 20260707_0001
Revises:
Create Date: 2026-07-07 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260707_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "account_type",
            sa.Enum("bank", "cash", "wallet", "credit_card", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("opening_balance", sa.Numeric(precision=14, scale=2), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "opening_outstanding",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("credit_limit", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("billing_day", sa.Integer(), nullable=True),
        sa.Column("due_day", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("opening_balance >= 0", name="ck_accounts_opening_balance_non_negative"),
        sa.CheckConstraint("opening_outstanding >= 0", name="ck_accounts_opening_outstanding_non_negative"),
        sa.CheckConstraint(
            """
            (
                account_type = 'credit_card'
                AND opening_balance = 0
                AND credit_limit IS NOT NULL
                AND credit_limit > 0
                AND billing_day BETWEEN 1 AND 28
                AND due_day BETWEEN 1 AND 28
            )
            OR
            (
                account_type IN ('bank', 'cash', 'wallet')
                AND opening_outstanding = 0
                AND credit_limit IS NULL
                AND billing_day IS NULL
                AND due_day IS NULL
            )
            """,
            name="ck_accounts_type_specific_fields",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )

    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "monthly_savings_target",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("salary_day", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("monthly_savings_target >= 0", name="ck_financial_profiles_savings_non_negative"),
        sa.CheckConstraint("salary_day BETWEEN 1 AND 28", name="ck_financial_profiles_salary_day"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recurring_commitments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "commitment_type",
            sa.Enum("fixed_expense", "investment", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_recurring_commitments_amount_positive"),
        sa.CheckConstraint("due_day BETWEEN 1 AND 28", name="ck_recurring_commitments_due_day"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("expense", "income", "transfer", "investment", "refund", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("source_account_id", sa.Uuid(), nullable=True),
        sa.Column("destination_account_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("recurring_commitment_id", sa.Uuid(), nullable=True),
        sa.Column("merchant", sa.String(length=120), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["destination_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["recurring_commitment_id"], ["recurring_commitments.id"]),
        sa.ForeignKeyConstraint(["source_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])
    op.create_index("ix_transactions_destination_account_id", "transactions", ["destination_account_id"])
    op.create_index("ix_transactions_occurred_at", "transactions", ["occurred_at"])
    op.create_index("ix_transactions_recurring_commitment_id", "transactions", ["recurring_commitment_id"])
    op.create_index("ix_transactions_source_account_id", "transactions", ["source_account_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_source_account_id", table_name="transactions")
    op.drop_index("ix_transactions_recurring_commitment_id", table_name="transactions")
    op.drop_index("ix_transactions_occurred_at", table_name="transactions")
    op.drop_index("ix_transactions_destination_account_id", table_name="transactions")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("recurring_commitments")
    op.drop_table("financial_profiles")
    op.drop_table("categories")
    op.drop_table("accounts")
