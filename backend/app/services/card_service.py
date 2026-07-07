from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionType
from app.services.balance_service import BalanceService, ZERO
from app.services.date_utils import billing_cycle_bounds, end_of_day_exclusive


class CardService:
    def __init__(self, db: Session):
        self.db = db
        self.balance_service = BalanceService(db)

    def list_credit_card_exposure(self, as_of: date | None = None) -> list[dict[str, object]]:
        calculation_date = as_of or date.today()
        cards = self.db.scalars(
            select(Account)
            .where(Account.account_type == AccountType.CREDIT_CARD, Account.is_active.is_(True))
            .order_by(Account.created_at, Account.name)
        ).all()
        return [self.credit_card_exposure(card, calculation_date) for card in cards]

    def credit_card_exposure(self, card: Account, as_of: date) -> dict[str, object]:
        outstanding = self.balance_service.credit_card_liability(card, as_of)
        credit_limit = Decimal(card.credit_limit or ZERO)
        available_credit = credit_limit - outstanding
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
            "billing_day": card.billing_day,
            "due_day": card.due_day,
        }

    def current_cycle_spend(self, card: Account, as_of: date) -> Decimal:
        if card.billing_day is None:
            return ZERO

        cycle_start, _cycle_end = billing_cycle_bounds(card.billing_day, as_of)
        start_dt = datetime.combine(cycle_start, time.min)
        end_dt = end_of_day_exclusive(as_of)
        statement = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.source_account_id == card.id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.occurred_at >= start_dt,
            Transaction.occurred_at < end_dt,
        )
        result = self.db.scalar(statement)
        return Decimal(result or ZERO)
