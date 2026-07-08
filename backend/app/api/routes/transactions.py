import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.routes._helpers import get_account_or_404, get_category_or_404, get_commitment_or_404, get_emi_plan_or_404
from app.core.database import get_db
from app.models.account import AccountType
from app.models.commitment import CommitmentType, RecurringCommitment
from app.models.emi_plan import EMIPlan, EMISetupCurrentMonthState
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreate, TransactionRead
from app.services import date_utils
from app.services.balance_service import ZERO
from app.services.emi_service import EMIService


router = APIRouter(prefix="/transactions", tags=["transactions"])


def _validate_commitment_link(payload: TransactionCreate, commitment: RecurringCommitment) -> None:
    if payload.transaction_type == TransactionType.TRANSFER:
        raise HTTPException(
            status_code=422,
            detail="Transfers cannot be linked to recurring commitments",
        )

    if payload.category_id != commitment.category_id:
        raise HTTPException(
            status_code=422,
            detail="Linked transaction category_id must match the recurring commitment category_id",
        )

    if payload.source_account_id != commitment.account_id:
        raise HTTPException(
            status_code=422,
            detail="Linked transaction source_account_id must match the recurring commitment account_id",
        )

    if commitment.commitment_type == CommitmentType.FIXED_EXPENSE:
        if payload.transaction_type != TransactionType.EXPENSE:
            raise HTTPException(
                status_code=422,
                detail="Fixed expense commitments can only be linked to expense transactions",
            )
        return

    if commitment.commitment_type == CommitmentType.INVESTMENT:
        if payload.transaction_type != TransactionType.INVESTMENT:
            raise HTTPException(
                status_code=422,
                detail="Investment commitments can only be linked to investment transactions",
            )


def _validate_emi_link(db: Session, payload: TransactionCreate, emi_plan: EMIPlan, occurred_at: datetime) -> None:
    if payload.transaction_type != TransactionType.EXPENSE:
        raise HTTPException(status_code=422, detail="EMI plan transactions must be expense transactions")

    if payload.source_account_id != emi_plan.account_id:
        raise HTTPException(
            status_code=422,
            detail="Linked EMI transaction source_account_id must match the EMI plan credit-card account_id",
        )

    if payload.category_id != emi_plan.category_id:
        raise HTTPException(
            status_code=422,
            detail="Linked EMI transaction category_id must match the EMI plan category_id",
        )

    local_date = date_utils.app_local_date_from_utc_naive(occurred_at)
    if local_date < emi_plan.tracking_start_month:
        raise HTTPException(
            status_code=422,
            detail="Linked EMI transactions must occur on or after the EMI plan tracking_start_month",
        )

    installment_month = date_utils.month_start(local_date)
    if (
        installment_month == emi_plan.tracking_start_month
        and emi_plan.setup_current_month_state != EMISetupCurrentMonthState.NOT_POSTED
    ):
        raise HTTPException(
            status_code=422,
            detail="The tracking-month EMI installment is already economically recognized for this plan",
        )

    service = EMIService(db)
    expected_amount = service.expected_installment_amount(emi_plan, installment_month)
    if expected_amount <= ZERO:
        raise HTTPException(status_code=422, detail="This EMI plan has no installment due for that month")

    if Decimal(payload.amount) != expected_amount:
        raise HTTPException(
            status_code=422,
            detail=f"Linked EMI transaction amount must equal the expected installment amount {expected_amount}",
        )

    if service.full_month_transaction_exists(emi_plan, installment_month):
        raise HTTPException(
            status_code=422,
            detail="An EMI transaction already exists for this plan in that application-local month",
        )


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)) -> Transaction:
    data = payload.model_dump()

    if payload.recurring_commitment_id is not None and payload.emi_plan_id is not None:
        raise HTTPException(status_code=422, detail="Transactions cannot link to both a recurring commitment and an EMI plan")

    source_account = None
    if payload.source_account_id is not None:
        source_account = get_account_or_404(db, payload.source_account_id)

    if payload.destination_account_id is not None:
        get_account_or_404(db, payload.destination_account_id)

    if payload.category_id is not None:
        get_category_or_404(db, payload.category_id)

    linked_commitment = None
    if payload.recurring_commitment_id is not None:
        linked_commitment = get_commitment_or_404(db, payload.recurring_commitment_id)

    linked_emi_plan = None
    if payload.emi_plan_id is not None:
        linked_emi_plan = get_emi_plan_or_404(db, payload.emi_plan_id)

    if payload.occurred_at is None:
        data["occurred_at"] = date_utils.utc_now_naive()
    else:
        occurred_at = date_utils.normalize_transaction_datetime(payload.occurred_at)
        if occurred_at > date_utils.utc_now_naive():
            raise HTTPException(
                status_code=422,
                detail="Transactions cannot be future-dated",
            )
        data["occurred_at"] = occurred_at

    if payload.transaction_type == TransactionType.TRANSFER and source_account is not None:
        if source_account.account_type == AccountType.CREDIT_CARD:
            raise HTTPException(
                status_code=422,
                detail="Credit cards cannot be used as the source account for transfers",
            )

    if payload.transaction_type == TransactionType.INVESTMENT and source_account is not None:
        if source_account.account_type == AccountType.CREDIT_CARD:
            raise HTTPException(
                status_code=422,
                detail="Credit cards cannot be used as the source account for an investment",
            )

    if linked_commitment is not None:
        _validate_commitment_link(payload, linked_commitment)

    if linked_emi_plan is not None:
        _validate_emi_link(db, payload, linked_emi_plan, data["occurred_at"])

    transaction = Transaction(**data)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    account_id: uuid.UUID | None = Query(default=None),
    transaction_type: TransactionType | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")

    statement = select(Transaction)
    if account_id is not None:
        statement = statement.where(
            or_(Transaction.source_account_id == account_id, Transaction.destination_account_id == account_id)
        )
    if transaction_type is not None:
        statement = statement.where(Transaction.transaction_type == transaction_type)
    if category_id is not None:
        statement = statement.where(Transaction.category_id == category_id)
    if date_from is not None:
        statement = statement.where(Transaction.occurred_at >= date_utils.app_date_start_utc_naive(date_from))
    if date_to is not None:
        statement = statement.where(Transaction.occurred_at < date_utils.app_date_end_exclusive_utc_naive(date_to))

    statement = statement.order_by(Transaction.occurred_at.desc(), Transaction.created_at.desc())
    return list(db.scalars(statement).all())
