from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.transaction import TransactionType
from app.schemas.common import Money, ZERO


class TransactionCreate(BaseModel):
    transaction_type: TransactionType
    amount: Money = Field(gt=ZERO, max_digits=14, decimal_places=2)
    source_account_id: uuid.UUID | None = None
    destination_account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    recurring_commitment_id: uuid.UUID | None = None
    merchant: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def validate_transaction_shape(self) -> TransactionCreate:
        if self.transaction_type in {TransactionType.EXPENSE, TransactionType.INVESTMENT}:
            if self.source_account_id is None:
                raise ValueError(f"{self.transaction_type.value} transactions require source_account_id")
            if self.destination_account_id is not None:
                raise ValueError(f"{self.transaction_type.value} transactions must not include destination_account_id")
            if self.category_id is None:
                raise ValueError(f"{self.transaction_type.value} transactions require category_id")
            return self

        if self.transaction_type in {TransactionType.INCOME, TransactionType.REFUND}:
            if self.destination_account_id is None:
                raise ValueError(f"{self.transaction_type.value} transactions require destination_account_id")
            if self.source_account_id is not None:
                raise ValueError(f"{self.transaction_type.value} transactions must not include source_account_id")
            return self

        if self.transaction_type == TransactionType.TRANSFER:
            if self.source_account_id is None or self.destination_account_id is None:
                raise ValueError("Transfer transactions require source_account_id and destination_account_id")
            if self.source_account_id == self.destination_account_id:
                raise ValueError("Transfer source and destination accounts must be different")
            if self.category_id is not None:
                raise ValueError("Transfer transactions must not include category_id")
            return self

        return self


class TransactionRead(BaseModel):
    id: uuid.UUID
    transaction_type: TransactionType
    amount: Decimal
    source_account_id: uuid.UUID | None
    destination_account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    recurring_commitment_id: uuid.UUID | None
    merchant: str | None
    description: str | None
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
