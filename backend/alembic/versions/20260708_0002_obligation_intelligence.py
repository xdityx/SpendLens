"""Add obligation intelligence EMI plans.

Revision ID: 20260708_0002
Revises: 20260707_0001
Create Date: 2026-07-08 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260708_0002"
down_revision: Union[str, None] = "20260707_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


setup_state_enum = sa.Enum(
    "not_posted",
    "included_in_opening_liability",
    "settled_before_tracking",
    native_enum=False,
    length=40,
)


def upgrade() -> None:
    op.create_table(
        "emi_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("monthly_installment", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("remaining_amount_at_setup", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column("tracking_start_month", sa.Date(), nullable=False),
        sa.Column("setup_current_month_state", setup_state_enum, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("monthly_installment > 0", name="ck_emi_plans_monthly_installment_positive"),
        sa.CheckConstraint("remaining_amount_at_setup > 0", name="ck_emi_plans_remaining_amount_positive"),
        sa.CheckConstraint("due_day BETWEEN 1 AND 28", name="ck_emi_plans_due_day"),
        sa.CheckConstraint(
            "setup_current_month_state IN ('not_posted', 'included_in_opening_liability', 'settled_before_tracking')",
            name="ck_emi_plans_setup_state",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emi_plans_account_id", "emi_plans", ["account_id"])
    op.create_index("ix_emi_plans_category_id", "emi_plans", ["category_id"])

    op.add_column("transactions", sa.Column("emi_plan_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_transactions_emi_plan_id_emi_plans", "transactions", "emi_plans", ["emi_plan_id"], ["id"])
    op.create_index("ix_transactions_emi_plan_id", "transactions", ["emi_plan_id"])
    op.create_check_constraint(
        "ck_transactions_single_obligation_link",
        "transactions",
        "recurring_commitment_id IS NULL OR emi_plan_id IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_transactions_single_obligation_link", "transactions", type_="check")
    op.drop_index("ix_transactions_emi_plan_id", table_name="transactions")
    op.drop_constraint("fk_transactions_emi_plan_id_emi_plans", "transactions", type_="foreignkey")
    op.drop_column("transactions", "emi_plan_id")
    op.drop_index("ix_emi_plans_category_id", table_name="emi_plans")
    op.drop_index("ix_emi_plans_account_id", table_name="emi_plans")
    op.drop_table("emi_plans")
