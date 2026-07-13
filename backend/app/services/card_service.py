from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionType
from app.services.balance_service import BalanceService, ZERO
from app.services.date_utils import (
    app_date_end_exclusive_utc_naive,
    billing_cycle_bounds,
    billing_cycle_utc_bounds,
    current_app_date,
)


class CardService:
    def __init__(self, db: Session):
        self.db = db
        self.balance_service = BalanceService(db)

    def list_credit_card_exposure(self, as_of: date | None = None) -> list[dict[str, object]]:
        calculation_date = as_of or current_app_date()
        cards = self.db.scalars(
            select(Account)
            .where(Account.account_type == AccountType.CREDIT_CARD, Account.is_active.is_(True))
            .order_by(Account.created_at, Account.name)
        ).all()
        return [self.credit_card_exposure(card, calculation_date) for card in cards]

    def credit_card_exposure(self, card: Account, as_of: date) -> dict[str, object]:
        outstanding = self.balance_service.credit_card_liability(card, as_of)
        cycle_start, cycle_end = billing_cycle_bounds(card.billing_day, as_of)
        credit_limit = Decimal(card.credit_limit or ZERO)
        available_credit = credit_limit - outstanding
        statement_balance_due = self.statement_balance_due(card, as_of)
        unbilled_balance = max(outstanding - statement_balance_due, ZERO)
        utilization_percentage = ZERO
        if credit_limit > ZERO:
            utilization_percentage = (outstanding / credit_limit * Decimal("100")).quantize(Decimal("0.01"))

        return {
            "account_id": card.id,
            "account_name": card.name,
            "credit_limit": credit_limit,
            "outstanding": outstanding,
            "available_credit": available_credit,
            "utilization_percentage": utilization_percentage,
            "current_cycle_spend": self.current_cycle_spend(card, as_of),
            "statement_balance_due": statement_balance_due,
            "statement_due_date": card.statement_due_date if statement_balance_due > ZERO else None,
            "statement_balance_as_of": card.statement_balance_as_of,
            "unbilled_balance": unbilled_balance,
            "cycle_start_date": cycle_start,
            "cycle_end_date": cycle_end,
            "billing_day": card.billing_day,
            "due_day": card.due_day,
        }

    def statement_balance_due(self, card: Account, as_of: date) -> Decimal:
        snapshot = Decimal(card.statement_balance or ZERO)
        snapshot_at = card.statement_balance_as_of
        end_dt = app_date_end_exclusive_utc_naive(as_of)
        if snapshot <= ZERO or snapshot_at is None or snapshot_at >= end_dt:
            return ZERO

        credits = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.voided_at.is_(None),
                Transaction.destination_account_id == card.id,
                Transaction.transaction_type.in_([TransactionType.REFUND, TransactionType.TRANSFER]),
                Transaction.occurred_at >= snapshot_at,
                Transaction.occurred_at < end_dt,
            )
        )
        remaining = max(snapshot - Decimal(credits or ZERO), ZERO)
        outstanding = self.balance_service.credit_card_liability(card, as_of)
        return min(remaining, outstanding)

    def total_statement_balance_due(self, as_of: date | None = None) -> Decimal:
        calculation_date = as_of or current_app_date()
        cards = self.db.scalars(
            select(Account).where(Account.account_type == AccountType.CREDIT_CARD, Account.is_active.is_(True))
        ).all()
        return sum((self.statement_balance_due(card, calculation_date) for card in cards), ZERO)

    def current_cycle_spend(self, card: Account, as_of: date) -> Decimal:
        if card.billing_day is None:
            return ZERO

        start_dt, end_dt = billing_cycle_utc_bounds(card.billing_day, as_of)
        statement = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.voided_at.is_(None),
            Transaction.source_account_id == card.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.occurred_at >= start_dt,
            Transaction.occurred_at < end_dt,
        )
        result = self.db.scalar(statement)
        return Decimal(result or ZERO)
