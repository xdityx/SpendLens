from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404
from app.core.database import get_db
from app.models.commitment import RecurringCommitment
from app.schemas.commitment import CommitmentCreate, CommitmentRead


router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.post("", response_model=CommitmentRead, status_code=201)
def create_commitment(payload: CommitmentCreate, db: Session = Depends(get_db)) -> RecurringCommitment:
    get_category_or_404(db, payload.category_id)
    get_account_or_404(db, payload.account_id)

    commitment = RecurringCommitment(**payload.model_dump())
    db.add(commitment)
    db.commit()
    db.refresh(commitment)
    return commitment


@router.get("", response_model=list[CommitmentRead])
def list_commitments(db: Session = Depends(get_db)) -> list[RecurringCommitment]:
    return list(db.scalars(select(RecurringCommitment).order_by(RecurringCommitment.created_at)).all())
