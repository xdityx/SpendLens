import uuid
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404, get_commitment_or_404
from app.core.database import get_db
from app.models.account import AccountType
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate, TransactionRead


router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)) -> Transaction:
    data = payload.model_dump()

    source_account = None
    if payload.source_account_id is not None:
        source_account = get_account_or_404(db, payload.source_account_id)

    if payload.destination_account_id is not None:
        get_account_or_404(db, payload.destination_account_id)

    if payload.category_id is not None:
        get_category_or_404(db, payload.category_id)

    if payload.recurring_commitment_id is not None:
        get_commitment_or_404(db, payload.recurring_commitment_id)

    if payload.transaction_type == TransactionType.INVESTMENT and source_account is not None:
        if source_account.account_type == AccountType.CREDIT_CARD:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Credit cards cannot be used as the source account for an investment",
            )

    if data["occurred_at"] is None:
        data["occurred_at"] = datetime.utcnow()

    transaction = Transaction(**data)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    account_id: uuid.UUID | None = Query(default=None),
    transaction_type: TransactionType | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must be <= date_to")

    statement = select(Transaction)
    if account_id is not None:
        statement = statement.where(
            or_(Transaction.source_account_id == account_id, Transaction.destination_account_id == account_id)
        )
    if transaction_type is not None:
        statement = statement.where(Transaction.transaction_type == transaction_type)
    if category_id is not None:
        statement = statement.where(Transaction.category_id == category_id)
    if date_from is not None:
        statement = statement.where(Transaction.occurred_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        statement = statement.where(Transaction.occurred_at < datetime.combine(date_to + timedelta(days=1), time.min))

    statement = statement.order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
    return list(db.scalars(statement).all())
