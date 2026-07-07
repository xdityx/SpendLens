from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Uuid
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.account import _enum_values
from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.transaction import Transaction


class CommitmentType(str, Enum):
    FIXED_EXPENSE = "fixed_expense"
    INVESTMENT = "investment"


class RecurringCommitment(Base, TimestampMixin):
    __tablename__ = "recurring_commitments"

    id = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    account_id: Mapped[object] = mapped_column(Uuid(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    commitment_type: Mapped[CommitmentType] = mapped_column(
        SAEnum(CommitmentType, values_callable=_enum_values, native_enum=False, length=32),
        nullable=False,
    )
    due_day: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    category: Mapped["Category"] = relationship(back_populates="commitments")
    account: Mapped["Account"] = relationship(back_populates="commitments")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="recurring_commitment")
