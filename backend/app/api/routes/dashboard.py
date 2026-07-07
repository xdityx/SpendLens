from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dashboard import CreditCardExposure, SafeToSpendSummary
from app.services.card_service import CardService
from app.services.safe_to_spend_service import SafeToSpendService


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=SafeToSpendSummary)
def dashboard_summary(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return SafeToSpendService(db).summary(as_of)


@router.get("/cards/exposure", response_model=list[CreditCardExposure])
def credit_card_exposure(
    as_of: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return CardService(db).list_credit_card_exposure(as_of)
