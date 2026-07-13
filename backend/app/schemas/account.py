from __future__ import annotations

import uuid
from datetime import date, datetime
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
    statement_balance: Money = Field(default=ZERO, ge=ZERO, max_digits=14, decimal_places=2)
    statement_due_date: date | None = None
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
            if self.statement_balance > self.opening_outstanding:
                raise ValueError("Statement balance cannot exceed opening outstanding")
            if self.statement_balance > ZERO and self.statement_due_date is None:
                raise ValueError("A positive statement balance requires statement_due_date")
            if self.statement_balance == ZERO and self.statement_due_date is not None:
                raise ValueError("statement_due_date must be empty when statement balance is zero")
            return self

        if self.opening_outstanding != ZERO:
            raise ValueError("Bank, cash, and wallet accounts must have opening_outstanding equal to zero")
        if (
            self.credit_limit is not None
            or self.billing_day is not None
            or self.due_day is not None
            or self.statement_balance != ZERO
            or self.statement_due_date is not None
        ):
            raise ValueError("Only credit-card accounts can define credit-card fields")
        return self


class StatementBalanceUpdate(BaseModel):
    statement_balance: Money = Field(ge=ZERO, max_digits=14, decimal_places=2)
    statement_due_date: date | None = None

    @model_validator(mode="after")
    def validate_statement(self) -> StatementBalanceUpdate:
        if self.statement_balance > ZERO and self.statement_due_date is None:
            raise ValueError("A positive statement balance requires statement_due_date")
        if self.statement_balance == ZERO and self.statement_due_date is not None:
            raise ValueError("statement_due_date must be empty when statement balance is zero")
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
    statement_balance: Decimal
    statement_due_date: date | None
    statement_balance_as_of: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
