import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money, ZERO


class FinancialProfileUpsert(BaseModel):
    monthly_savings_target: Money = Field(default=ZERO, ge=ZERO, max_digits=14, decimal_places=2)
    salary_day: int = Field(ge=1, le=28)


class FinancialProfileRead(BaseModel):
    id: uuid.UUID
    monthly_savings_target: Decimal
    salary_day: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
