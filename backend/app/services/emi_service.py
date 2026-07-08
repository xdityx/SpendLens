from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.emi_plan import EMIPlan, EMISetupCurrentMonthState
from app.models.transaction import Transaction, TransactionType
from app.services.balance_service import ZERO
from app.services.date_utils import (
    app_date_start_utc_naive,
    current_app_date,
    current_month_utc_bounds,
    full_month_utc_bounds,
    month_start,
)

RESERVED_STATUSES = {"upcoming", "due_today", "overdue"}
SETUP_RECOGNIZED_STATES = {
    EMISetupCurrentMonthState.INCLUDED_IN_OPENING_LIABILITY,
    EMISetupCurrentMonthState.SETTLED_BEFORE_TRACKING,
}


class EMIService:
    def __init__(self, db: Session):
        self.db = db

    def list_statuses(self, as_of: date | None = None, active_only: bool = False) -> list[dict[str, object]]:
        calculation_date = as_of or current_app_date()
        statement = select(EMIPlan).order_by(EMIPlan.due_day, EMIPlan.created_at, EMIPlan.name)
        if active_only:
            statement = statement.where(EMIPlan.is_active.is_(True))
        plans = self.db.scalars(statement).all()
        return [self.status_for_plan(plan, calculation_date) for plan in plans]

    def current_month_reserve_total(self, as_of: date) -> Decimal:
        statuses = self.list_statuses(as_of, active_only=True)
        return sum((Decimal(status["current_month_reserve"]) for status in statuses), ZERO)

    def status_for_plan(self, plan: EMIPlan, as_of: date) -> dict[str, object]:
        current_month = month_start(as_of)
        due_date = date(as_of.year, as_of.month, plan.due_day)
        remaining_before_current = self.remaining_before_month(plan, current_month)
        current_installment_amount = self.expected_installment_amount(plan, current_month)
        current_transaction = self.current_month_transaction(plan, as_of)
        current_recognized_amount = self._current_recognized_amount(plan, current_month, current_installment_amount, current_transaction)
        remaining_unrecognized_amount = max(remaining_before_current - current_recognized_amount, ZERO)
        future_remaining_after_current = max(remaining_before_current - current_installment_amount, ZERO)
        status = self._current_month_status(
            plan=plan,
            as_of=as_of,
            due_date=due_date,
            current_month=current_month,
            remaining_before_current=remaining_before_current,
            current_transaction=current_transaction,
        )
        current_month_reserve = current_installment_amount if status in RESERVED_STATUSES else ZERO

        return {
            "emi_plan_id": plan.id,
            "name": plan.name,
            "account_id": plan.account_id,
            "category_id": plan.category_id,
            "monthly_installment": Decimal(plan.monthly_installment),
            "remaining_amount_at_setup": Decimal(plan.remaining_amount_at_setup),
            "current_installment_amount": current_installment_amount,
            "current_month_status": status,
            "current_month_reserve": current_month_reserve,
            "remaining_unrecognized_amount": remaining_unrecognized_amount,
            "future_remaining_after_current_installment": future_remaining_after_current,
            "due_day": plan.due_day,
            "due_date": due_date,
            "posted_at": current_transaction.occurred_at if current_transaction is not None else None,
            "is_active": plan.is_active,
        }

    def expected_installment_amount(self, plan: EMIPlan, installment_month: date) -> Decimal:
        target_month = month_start(installment_month)
        if target_month < plan.tracking_start_month:
            return ZERO
        remaining_before_month = self.remaining_before_month(plan, target_month)
        if remaining_before_month <= ZERO:
            return ZERO
        return min(Decimal(plan.monthly_installment), remaining_before_month)

    def remaining_before_month(self, plan: EMIPlan, target_month: date) -> Decimal:
        target_month = month_start(target_month)
        if target_month < plan.tracking_start_month:
            return Decimal(plan.remaining_amount_at_setup)

        start_dt = app_date_start_utc_naive(target_month)
        linked_total = self._linked_total_before(plan, start_dt)
        setup_recognized = self._setup_recognized_amount(plan) if target_month > plan.tracking_start_month else ZERO
        return max(Decimal(plan.remaining_amount_at_setup) - setup_recognized - linked_total, ZERO)

    def current_month_transaction(self, plan: EMIPlan, as_of: date) -> Transaction | None:
        start_dt, end_dt = current_month_utc_bounds(as_of)
        return self.db.scalars(
            select(Transaction)
            .where(
                Transaction.emi_plan_id == plan.id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at < end_dt,
            )
            .order_by(Transaction.occurred_at, Transaction.created_at, Transaction.id)
            .limit(1)
        ).first()

    def full_month_transaction_exists(self, plan: EMIPlan, installment_month: date) -> bool:
        start_dt, end_dt = full_month_utc_bounds(installment_month)
        return (
            self.db.scalar(
                select(func.count(Transaction.id)).where(
                    Transaction.emi_plan_id == plan.id,
                    Transaction.occurred_at >= start_dt,
                    Transaction.occurred_at < end_dt,
                )
            )
            or 0
        ) > 0

    def _linked_total_before(self, plan: EMIPlan, end_dt: datetime) -> Decimal:
        result = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.emi_plan_id == plan.id,
                Transaction.transaction_type == TransactionType.EXPENSE,
                Transaction.occurred_at < end_dt,
            )
        )
        return Decimal(result or ZERO)

    def _setup_recognized_amount(self, plan: EMIPlan) -> Decimal:
        if plan.setup_current_month_state not in SETUP_RECOGNIZED_STATES:
            return ZERO
        return min(Decimal(plan.monthly_installment), Decimal(plan.remaining_amount_at_setup))

    def _current_recognized_amount(
        self,
        plan: EMIPlan,
        current_month: date,
        current_installment_amount: Decimal,
        current_transaction: Transaction | None,
    ) -> Decimal:
        if current_month == plan.tracking_start_month and plan.setup_current_month_state in SETUP_RECOGNIZED_STATES:
            return current_installment_amount
        if current_transaction is not None:
            return Decimal(current_transaction.amount)
        return ZERO

    def _current_month_status(
        self,
        plan: EMIPlan,
        as_of: date,
        due_date: date,
        current_month: date,
        remaining_before_current: Decimal,
        current_transaction: Transaction | None,
    ) -> str:
        if current_month == plan.tracking_start_month:
            if plan.setup_current_month_state == EMISetupCurrentMonthState.INCLUDED_IN_OPENING_LIABILITY:
                return "included_in_card_liability"
            if plan.setup_current_month_state == EMISetupCurrentMonthState.SETTLED_BEFORE_TRACKING:
                return "settled_before_tracking"

        if current_transaction is not None:
            return "posted"
        if remaining_before_current <= ZERO:
            return "completed"
        if as_of < due_date:
            return "upcoming"
        if as_of == due_date:
            return "due_today"
        return "overdue"
