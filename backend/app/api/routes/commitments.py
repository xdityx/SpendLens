from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404
from app.core.database import get_db
from app.models.commitment import RecurringCommitment
from app.schemas.commitment import CommitmentCreate, CommitmentRead, CommitmentStatusRead
from app.services.commitment_status_service import CommitmentStatusService
from app.services.date_utils import current_app_date


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


@router.get("/status", response_model=list[CommitmentStatusRead])
def list_commitment_statuses(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return CommitmentStatusService(db).list_active_fixed_statuses(as_of or current_app_date())
