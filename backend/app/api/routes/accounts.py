import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404
from app.core.database import get_db
from app.models.account import Account, AccountType
from app.schemas.account import AccountCreate, AccountRead, StatementBalanceUpdate
from app.services.balance_service import BalanceService
from app.services.date_utils import current_app_date, utc_now_naive


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    data = payload.model_dump()
    data["statement_balance_as_of"] = utc_now_naive() if payload.statement_balance > 0 else None
    account = Account(**data)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[AccountRead])
def list_accounts(db: Session = Depends(get_db)) -> list[Account]:
    return list(db.scalars(select(Account).order_by(Account.created_at, Account.name)).all())


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: uuid.UUID, db: Session = Depends(get_db)) -> Account:
    return get_account_or_404(db, account_id)


@router.put("/{account_id}/statement", response_model=AccountRead)
def update_statement_balance(
    account_id: uuid.UUID,
    payload: StatementBalanceUpdate,
    db: Session = Depends(get_db),
) -> Account:
    account = get_account_or_404(db, account_id)
    if account.account_type != AccountType.CREDIT_CARD:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Statement balances can only be set for credit-card accounts",
        )

    outstanding = BalanceService(db).credit_card_liability(account, current_app_date())
    if payload.statement_balance > outstanding:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Statement balance cannot exceed the card's current outstanding balance",
        )

    account.statement_balance = payload.statement_balance
    account.statement_due_date = payload.statement_due_date
    account.statement_balance_as_of = utc_now_naive() if payload.statement_balance > 0 else None
    db.commit()
    db.refresh(account)
    return account
