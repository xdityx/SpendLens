import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class SafeToSpendSummary(BaseModel):
    liquid_cash: Decimal
    credit_card_liability: Decimal
    statement_balance_due: Decimal
    unbilled_card_liability: Decimal
    due_soon_cash_position: Decimal
    remaining_fixed_commitments: Decimal
    remaining_emi_installments: Decimal
    monthly_savings_target: Decimal
    savings_completed_this_month: Decimal
    remaining_savings_target: Decimal
    safe_to_spend: Decimal
    status: str


class CreditCardExposure(BaseModel):
    account_id: uuid.UUID
    account_name: str
    credit_limit: Decimal
    outstanding: Decimal
    available_credit: Decimal
    utilization_percentage: Decimal
    current_cycle_spend: Decimal
    statement_balance_due: Decimal
    statement_due_date: date | None
    statement_balance_as_of: datetime | None
    unbilled_balance: Decimal
    cycle_start_date: date
    cycle_end_date: date
    billing_day: int
    due_day: int
