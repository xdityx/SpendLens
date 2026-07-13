from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.commitment import RecurringCommitment
    from app.models.emi_plan import EMIPlan
    from app.models.transaction import Transaction


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class AccountType(str, Enum):
    BANK = "bank"
    CASH = "cash"
    WALLET = "wallet"
    CREDIT_CARD = "credit_card"


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        SAEnum(AccountType, values_callable=_enum_values, native_enum=False, length=32),
        nullable=False,
    )
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    opening_outstanding: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    billing_day: Mapped[int | None] = mapped_column(nullable=True)
    due_day: Mapped[int | None] = mapped_column(nullable=True)
    statement_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    statement_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    statement_balance_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    source_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="source_account",
        foreign_keys="Transaction.source_account_id",
    )
    destination_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="destination_account",
        foreign_keys="Transaction.destination_account_id",
    )
    commitments: Mapped[list["RecurringCommitment"]] = relationship(back_populates="account")
    emi_plans: Mapped[list["EMIPlan"]] = relationship(back_populates="account")
