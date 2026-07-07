import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404
from app.core.database import get_db
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountRead


router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    account = Account(**payload.model_dump())
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
