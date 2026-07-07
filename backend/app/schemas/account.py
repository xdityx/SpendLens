from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.account import AccountType
from app.schemas.common import Money, ZERO


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_type: AccountType
    opening_balance: Money = Field(default=ZERO, ge=ZERO, max_digits=14, decimal_places=2)
    opening_outstanding: Money = Field(default=ZERO, ge=ZERO, max_digits=14, decimal_places=2)
    credit_limit: Money | None = Field(default=None, gt=ZERO, max_digits=14, decimal_places=2)
    billing_day: int | None = Field(default=None, ge=1, le=28)
    due_day: int | None = Field(default=None, ge=1, le=28)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_account_rules(self) -> AccountCreate:
        if self.account_type == AccountType.CREDIT_CARD:
            if self.opening_balance != ZERO:
                raise ValueError("Credit-card accounts must have opening_balance equal to zero")
            if self.credit_limit is None:
                raise ValueError("Credit-card accounts require credit_limit")
            if self.billing_day is None:
                raise ValueError("Credit-card accounts require billing_day")
            if self.due_day is None:
                raise ValueError("Credit-card accounts require due_day")
            return self

        if self.opening_outstanding != ZERO:
            raise ValueError("Bank, cash, and wallet accounts must have opening_outstanding equal to zero")
        if self.credit_limit is not None or self.billing_day is not None or self.due_day is not None:
            raise ValueError("Only credit-card accounts can define credit_limit, billing_day, or due_day")
        return self


class AccountRead(BaseModel):
    id: uuid.UUID
    name: str
    account_type: AccountType
    opening_balance: Decimal
    opening_outstanding: Decimal
    credit_limit: Decimal | None
    billing_day: int | None
    due_day: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
