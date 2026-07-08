from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction, TransactionType
from app.services.balance_service import BalanceService, ZERO
from app.services.commitment_status_service import CommitmentStatusService
from app.services.date_utils import current_app_date, current_month_utc_bounds
from app.services.emi_service import EMIService


class SafeToSpendService:
    def __init__(self, db: Session):
        self.db = db
        self.balance_service = BalanceService(db)
        self.commitment_status_service = CommitmentStatusService(db)
        self.emi_service = EMIService(db)

    def summary(self, as_of: date | None = None) -> dict[str, Decimal | str]:
        calculation_date = as_of or current_app_date()
        profile = self._financial_profile()
        monthly_savings_target = Decimal(profile.monthly_savings_target) if profile else ZERO
        savings_completed = self._investment_transactions_this_month(calculation_date)
        remaining_savings_target = max(monthly_savings_target - savings_completed, ZERO)
        liquid_cash = self.balance_service.liquid_cash(calculation_date)
        credit_card_liability = self.balance_service.total_credit_card_liability(calculation_date)
        remaining_fixed_commitments = self._remaining_fixed_commitments(calculation_date)
        remaining_emi_installments = self._remaining_emi_installments(calculation_date)
        safe_to_spend = (
            liquid_cash
            - credit_card_liability
            - remaining_fixed_commitments
            - remaining_emi_installments
            - remaining_savings_target
        )

        return {
            "liquid_cash": liquid_cash,
            "credit_card_liability": credit_card_liability,
            "remaining_fixed_commitments": remaining_fixed_commitments,
            "remaining_emi_installments": remaining_emi_installments,
            "monthly_savings_target": monthly_savings_target,
            "savings_completed_this_month": savings_completed,
            "remaining_savings_target": remaining_savings_target,
            "safe_to_spend": safe_to_spend,
            "status": self._status(safe_to_spend),
        }

    def _financial_profile(self) -> FinancialProfile | None:
        return self.db.scalars(select(FinancialProfile).order_by(FinancialProfile.created_at).limit(1)).first()

    def _investment_transactions_this_month(self, as_of: date) -> Decimal:
        start_dt, end_dt = current_month_utc_bounds(as_of)
        result = self.db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.transaction_type == TransactionType.INVESTMENT,
                Transaction.occurred_at >= start_dt,
                Transaction.occurred_at < end_dt,
            )
        )
        return Decimal(result or ZERO)

    def _remaining_fixed_commitments(self, as_of: date) -> Decimal:
        return self.commitment_status_service.remaining_fixed_commitments(as_of)

    def _remaining_emi_installments(self, as_of: date) -> Decimal:
        return self.emi_service.current_month_reserve_total(as_of)

    @staticmethod
    def _status(safe_to_spend: Decimal) -> str:
        if safe_to_spend < ZERO:
            return "overcommitted"
        if safe_to_spend == ZERO:
            return "fully_allocated"
        return "available"
