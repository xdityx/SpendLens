import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404, get_emi_plan_or_404
from app.core.database import get_db
from app.models.account import AccountType
from app.models.emi_plan import EMIPlan
from app.schemas.emi_plan import EMIPlanCreate, EMIPlanRead, EMIPlanStatusRead, EMIPlanUpdate
from app.services.date_utils import current_app_date, month_start
from app.services.emi_service import EMIService


router = APIRouter(prefix="/emi-plans", tags=["emi-plans"])
LOCKED_FINANCIAL_CONFIG_ERROR = (
    "EMI financial configuration is locked after the tracking month or installment history begins. "
    "Only name, due day, and active status can be changed."
)


def _emi_plan_read(plan: EMIPlan, service: EMIService) -> dict[str, object]:
    reason = service.financial_configuration_lock_reason(plan)
    return {
        "id": plan.id,
        "name": plan.name,
        "account_id": plan.account_id,
        "category_id": plan.category_id,
        "monthly_installment": Decimal(plan.monthly_installment),
        "remaining_amount_at_setup": Decimal(plan.remaining_amount_at_setup),
        "due_day": plan.due_day,
        "tracking_start_month": plan.tracking_start_month,
        "setup_current_month_state": plan.setup_current_month_state,
        "is_active": plan.is_active,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "financial_configuration_locked": reason is not None,
        "financial_configuration_lock_reason": reason,
    }


def _financial_configuration_changed(plan: EMIPlan, payload: EMIPlanUpdate) -> bool:
    return any(
        [
            payload.account_id != plan.account_id,
            payload.category_id != plan.category_id,
            Decimal(payload.monthly_installment) != Decimal(plan.monthly_installment),
            Decimal(payload.remaining_amount_at_setup) != Decimal(plan.remaining_amount_at_setup),
            payload.setup_current_month_state != plan.setup_current_month_state,
        ]
    )


@router.post("", response_model=EMIPlanRead, status_code=201)
def create_emi_plan(payload: EMIPlanCreate, db: Session = Depends(get_db)) -> dict[str, object]:
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
    return _emi_plan_read(plan, EMIService(db))


@router.get("", response_model=list[EMIPlanRead])
def list_emi_plans(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    service = EMIService(db)
    plans = db.scalars(select(EMIPlan).order_by(EMIPlan.created_at, EMIPlan.name)).all()
    return [_emi_plan_read(plan, service) for plan in plans]


@router.get("/status", response_model=list[EMIPlanStatusRead])
def list_emi_plan_statuses(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return EMIService(db).list_statuses(as_of or current_app_date())


@router.get("/{emi_plan_id}", response_model=EMIPlanRead)
def get_emi_plan(emi_plan_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, object]:
    return _emi_plan_read(get_emi_plan_or_404(db, emi_plan_id), EMIService(db))


@router.put("/{emi_plan_id}", response_model=EMIPlanRead)
def update_emi_plan(
    emi_plan_id: uuid.UUID,
    payload: EMIPlanUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    plan = get_emi_plan_or_404(db, emi_plan_id)
    account = get_account_or_404(db, payload.account_id)
    if account.account_type != AccountType.CREDIT_CARD:
        raise HTTPException(status_code=422, detail="EMI plans must use a credit-card account")
    get_category_or_404(db, payload.category_id)

    service = EMIService(db)
    if service.is_financial_configuration_locked(plan) and _financial_configuration_changed(plan, payload):
        raise HTTPException(status_code=422, detail=LOCKED_FINANCIAL_CONFIG_ERROR)

    for field, value in payload.model_dump().items():
        setattr(plan, field, value)

    db.commit()
    db.refresh(plan)
    return _emi_plan_read(plan, service)
