import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.commitment import CommitmentType
from app.schemas.common import Money, ZERO


class CommitmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: Money = Field(gt=ZERO, max_digits=14, decimal_places=2)
    category_id: uuid.UUID
    account_id: uuid.UUID
    commitment_type: CommitmentType
    due_day: int = Field(ge=1, le=28)
    is_active: bool = True


class CommitmentRead(BaseModel):
    id: uuid.UUID
    name: str
    amount: Decimal
    category_id: uuid.UUID
    account_id: uuid.UUID
    commitment_type: CommitmentType
    due_day: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitmentStatusRead(BaseModel):
    commitment_id: uuid.UUID
    name: str
    amount: Decimal
    category_id: uuid.UUID
    account_id: uuid.UUID
    due_day: int
    due_date: date
    paid_amount_this_month: Decimal
    remaining_amount_this_month: Decimal
    status: str
    fulfilled_at: datetime | None
