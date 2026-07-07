from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.financial_profile import FinancialProfile
from app.schemas.financial_profile import FinancialProfileRead, FinancialProfileUpsert


router = APIRouter(prefix="/financial-profile", tags=["financial profile"])


@router.put("", response_model=FinancialProfileRead)
def upsert_financial_profile(payload: FinancialProfileUpsert, db: Session = Depends(get_db)) -> FinancialProfile:
    profile = db.scalars(select(FinancialProfile).order_by(FinancialProfile.created_at).limit(1)).first()
    if profile is None:
        profile = FinancialProfile(**payload.model_dump())
        db.add(profile)
    else:
        profile.monthly_savings_target = payload.monthly_savings_target
        profile.salary_day = payload.salary_day

    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=FinancialProfileRead | None)
def get_financial_profile(db: Session = Depends(get_db)) -> FinancialProfile | None:
    return db.scalars(select(FinancialProfile).order_by(FinancialProfile.created_at).limit(1)).first()
