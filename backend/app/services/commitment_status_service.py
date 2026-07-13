from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import CommitmentType, RecurringCommitment
from app.models.transaction import Transaction, TransactionType
from app.services.balance_service import ZERO
from app.services.date_utils import current_app_date, current_month_utc_bounds


class CommitmentStatusService:
    def __init__(self, db: Session):
        self.db = db

    def list_active_fixed_statuses(self, as_of: date | None = None) -> list[dict[str, object]]:
        calculation_date = as_of or current_app_date()
        commitments = self.db.scalars(
            select(RecurringCommitment)
            .where(
                RecurringCommitment.is_active.is_(True),
                RecurringCommitment.commitment_type == CommitmentType.FIXED_EXPENSE,
            )
            .order_by(RecurringCommitment.due_day, RecurringCommitment.created_at, RecurringCommitment.name)
        ).all()
        return [self.status_for_commitment(commitment, calculation_date) for commitment in commitments]

    def status_for_commitment(self, commitment: RecurringCommitment, as_of: date) -> dict[str, object]:
        transactions = self._linked_expense_transactions_this_month(commitment, as_of)
        paid_amount = sum((Decimal(transaction.amount) for transaction in transactions), ZERO)
        remaining_amount = max(Decimal(commitment.amount) - paid_amount, ZERO)
        due_date = date(as_of.year, as_of.month, commitment.due_day)
        status = self._status(as_of, due_date, paid_amount, remaining_amount)
        fulfilled_at = self._fulfilled_at(transactions, Decimal(commitment.amount)) if remaining_amount == ZERO else None

        return {
            "commitment_id": commitment.id,
            "name": commitment.name,
            "amount": Decimal(commitment.amount),
            "category_id": commitment.category_id,
            "account_id": commitment.account_id,
            "due_day": commitment.due_day,
            "due_date": due_date,
            "paid_amount_this_month": paid_amount,
            "remaining_amount_this_month": remaining_amount,
            "status": status,
            "fulfilled_at": fulfilled_at,
        }

    def remaining_fixed_commitments(self, as_of: date) -> Decimal:
        statuses = self.list_active_fixed_statuses(as_of)
        return sum((Decimal(status["remaining_amount_this_month"]) for status in statuses), ZERO)

    def _linked_expense_transactions_this_month(
        self,
        commitment: RecurringCommitment,
        as_of: date,
    ) -> list[Transaction]:
        start_dt, end_dt = current_month_utc_bounds(as_of)
        return list(
            self.db.scalars(
                select(Transaction)
                .where(
                    Transaction.voided_at.is_(None),
                    Transaction.recurring_commitment_id == commitment.id,
                    Transaction.transaction_type == TransactionType.EXPENSE,
                    Transaction.occurred_at >= start_dt,
                    Transaction.occurred_at < end_dt,
                )
                .order_by(Transaction.occurred_at, Transaction.created_at, Transaction.id)
            ).all()
        )

    @staticmethod
    def _fulfilled_at(transactions: list[Transaction], target_amount: Decimal) -> datetime | None:
        running_total = ZERO
        for transaction in transactions:
            running_total += Decimal(transaction.amount)
            if running_total >= target_amount:
                return transaction.occurred_at
        return None

    @staticmethod
    def _status(as_of: date, due_date: date, paid_amount: Decimal, remaining_amount: Decimal) -> str:
        if remaining_amount == ZERO:
            return "paid"
        if paid_amount > ZERO and as_of <= due_date:
            return "partial"
        if paid_amount > ZERO:
            return "overdue_partial"
        if as_of < due_date:
            return "upcoming"
        if as_of == due_date:
            return "due_today"
        return "overdue"
