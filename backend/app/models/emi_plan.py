from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.account import _enum_values
from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.transaction import Transaction


class EMISetupCurrentMonthState(str, Enum):
    NOT_POSTED = "not_posted"
    INCLUDED_IN_OPENING_LIABILITY = "included_in_opening_liability"
    SETTLED_BEFORE_TRACKING = "settled_before_tracking"


class EMIPlan(Base, TimestampMixin):
    __tablename__ = "emi_plans"
    __table_args__ = (
        CheckConstraint("monthly_installment > 0", name="ck_emi_plans_monthly_installment_positive"),
        CheckConstraint("remaining_amount_at_setup > 0", name="ck_emi_plans_remaining_amount_positive"),
        CheckConstraint("due_day BETWEEN 1 AND 28", name="ck_emi_plans_due_day"),
    )

    id = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    category_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    monthly_installment: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    remaining_amount_at_setup: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_day: Mapped[int] = mapped_column(nullable=False)
    tracking_start_month: Mapped[object] = mapped_column(Date, nullable=False)
    setup_current_month_state: Mapped[EMISetupCurrentMonthState] = mapped_column(
        SAEnum(EMISetupCurrentMonthState, values_callable=_enum_values, native_enum=False, length=40),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    account: Mapped["Account"] = relationship(back_populates="emi_plans")
    category: Mapped["Category"] = relationship(back_populates="emi_plans")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="emi_plan")
