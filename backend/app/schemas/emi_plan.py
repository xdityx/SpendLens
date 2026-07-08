import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.emi_plan import EMISetupCurrentMonthState
from app.schemas.common import Money, ZERO


class EMIPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_id: uuid.UUID
    category_id: uuid.UUID
    monthly_installment: Money = Field(gt=ZERO, max_digits=14, decimal_places=2)
    remaining_amount_at_setup: Money = Field(gt=ZERO, max_digits=14, decimal_places=2)
    due_day: int = Field(ge=1, le=28)
    setup_current_month_state: EMISetupCurrentMonthState


class EMIPlanRead(BaseModel):
    id: uuid.UUID
    name: str
    account_id: uuid.UUID
    category_id: uuid.UUID
    monthly_installment: Decimal
    remaining_amount_at_setup: Decimal
    due_day: int
    tracking_start_month: date
    setup_current_month_state: EMISetupCurrentMonthState
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EMIPlanStatusRead(BaseModel):
    emi_plan_id: uuid.UUID
    name: str
    account_id: uuid.UUID
    category_id: uuid.UUID
    monthly_installment: Decimal
    remaining_amount_at_setup: Decimal
    current_installment_amount: Decimal
    current_month_status: str
    current_month_reserve: Decimal
    remaining_unrecognized_amount: Decimal
    future_remaining_after_current_installment: Decimal
    due_day: int
    due_date: date
    posted_at: datetime | None
    is_active: bool
