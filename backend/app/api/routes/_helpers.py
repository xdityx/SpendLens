import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.commitment import RecurringCommitment
from app.models.emi_plan import EMIPlan


def get_account_or_404(db: Session, account_id: uuid.UUID) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def get_category_or_404(db: Session, category_id: uuid.UUID) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def get_commitment_or_404(db: Session, commitment_id: uuid.UUID) -> RecurringCommitment:
    commitment = db.get(RecurringCommitment, commitment_id)
    if commitment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring commitment not found")
    return commitment


def get_emi_plan_or_404(db: Session, emi_plan_id: uuid.UUID) -> EMIPlan:
    emi_plan = db.get(EMIPlan, emi_plan_id)
    if emi_plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EMI plan not found")
    return emi_plan
