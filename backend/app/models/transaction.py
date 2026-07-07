from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.account import _enum_values
from app.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category
    from app.models.commitment import RecurringCommitment


class TransactionType(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    INVESTMENT = "investment"
    REFUND = "refund"


class Transaction(Base):
    __tablename__ = "transactions"

    id = uuid_pk()
    transaction_type: Mapped[TransactionType] = mapped_column(
        SAEnum(TransactionType, values_callable=_enum_values, native_enum=False, length=32),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    source_account_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=True,
    )
    destination_account_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id"),
        nullable=True,
    )
    category_id: Mapped[object | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    recurring_commitment_id: Mapped[object | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("recurring_commitments.id"),
        nullable=True,
    )
    merchant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    source_account: Mapped["Account | None"] = relationship(
        back_populates="source_transactions",
        foreign_keys=[source_account_id],
    )
    destination_account: Mapped["Account | None"] = relationship(
        back_populates="destination_transactions",
        foreign_keys=[destination_account_id],
    )
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    recurring_commitment: Mapped["RecurringCommitment | None"] = relationship(back_populates="transactions")
