import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404, get_commitment_or_404
from app.core.database import get_db
from app.models.account import Account, AccountType
from app.models.commitment import CommitmentType, RecurringCommitment
from app.schemas.commitment import CommitmentCreate, CommitmentRead, CommitmentStatusRead, CommitmentUpdate
from app.services.commitment_status_service import CommitmentStatusService
from app.services.date_utils import current_app_date


router = APIRouter(prefix="/commitments", tags=["commitments"])


def _validate_investment_account(commitment_type: CommitmentType, account: Account) -> None:
    if commitment_type == CommitmentType.INVESTMENT and account.account_type == AccountType.CREDIT_CARD:
        raise HTTPException(status_code=422, detail="Investment commitments cannot use a credit-card account")


@router.post("", response_model=CommitmentRead, status_code=201)
def create_commitment(payload: CommitmentCreate, db: Session = Depends(get_db)) -> RecurringCommitment:
    get_category_or_404(db, payload.category_id)
    account = get_account_or_404(db, payload.account_id)
    _validate_investment_account(payload.commitment_type, account)

    commitment = RecurringCommitment(**payload.model_dump())
    db.add(commitment)
    db.commit()
    db.refresh(commitment)
    return commitment


@router.get("", response_model=list[CommitmentRead])
def list_commitments(db: Session = Depends(get_db)) -> list[RecurringCommitment]:
    return list(db.scalars(select(RecurringCommitment).order_by(RecurringCommitment.created_at)).all())


@router.put("/{commitment_id}", response_model=CommitmentRead)
def update_commitment(
    commitment_id: uuid.UUID,
    payload: CommitmentUpdate,
    db: Session = Depends(get_db),
) -> RecurringCommitment:
    commitment = get_commitment_or_404(db, commitment_id)
    get_category_or_404(db, payload.category_id)
    account = get_account_or_404(db, payload.account_id)
    _validate_investment_account(commitment.commitment_type, account)

    for field, value in payload.model_dump().items():
        setattr(commitment, field, value)

    db.commit()
    db.refresh(commitment)
    return commitment


@router.get("/status", response_model=list[CommitmentStatusRead])
def list_commitment_statuses(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return CommitmentStatusService(db).list_active_fixed_statuses(as_of or current_app_date())
