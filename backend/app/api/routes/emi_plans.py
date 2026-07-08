import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404, get_emi_plan_or_404
from app.core.database import get_db
from app.models.account import AccountType
from app.models.emi_plan import EMIPlan
from app.schemas.emi_plan import EMIPlanCreate, EMIPlanRead, EMIPlanStatusRead
from app.services.date_utils import current_app_date, month_start
from app.services.emi_service import EMIService


router = APIRouter(prefix="/emi-plans", tags=["emi-plans"])


@router.post("", response_model=EMIPlanRead, status_code=201)
def create_emi_plan(payload: EMIPlanCreate, db: Session = Depends(get_db)) -> EMIPlan:
    account = get_account_or_404(db, payload.account_id)
    if account.account_type != AccountType.CREDIT_CARD:
        raise HTTPException(status_code=422, detail="EMI plans must use a credit-card account")
    get_category_or_404(db, payload.category_id)

    data = payload.model_dump()
    data["tracking_start_month"] = month_start(current_app_date())
    data["is_active"] = True
    plan = EMIPlan(**data)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("", response_model=list[EMIPlanRead])
def list_emi_plans(db: Session = Depends(get_db)) -> list[EMIPlan]:
    return list(db.scalars(select(EMIPlan).order_by(EMIPlan.created_at, EMIPlan.name)).all())


@router.get("/status", response_model=list[EMIPlanStatusRead])
def list_emi_plan_statuses(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return EMIService(db).list_statuses(as_of or current_app_date())


@router.get("/{emi_plan_id}", response_model=EMIPlanRead)
def get_emi_plan(emi_plan_id: uuid.UUID, db: Session = Depends(get_db)) -> EMIPlan:
    return get_emi_plan_or_404(db, emi_plan_id)
