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
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
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


def _format_installment_month(installment_month: date) -> str:
    return installment_month.strftime("%Y-%m")


def _validate_emi_link(
    db: Session,
    payload: TransactionCreate,
    emi_plan: EMIPlan,
    occurred_at: datetime,
    allow_inactive_emi_plan_id: uuid.UUID | None = None,
    allow_later_linked_transactions: bool = False,
) -> None:
    if payload.transaction_type != TransactionType.EXPENSE:
        raise HTTPException(status_code=422, detail="EMI plan transactions must be expense transactions")

    if not emi_plan.is_active and emi_plan.id != allow_inactive_emi_plan_id:
        raise HTTPException(status_code=422, detail="Inactive EMI plans cannot record new installments")

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
    missing_month = service.earliest_required_unrecognized_month_before(emi_plan, installment_month)
    if missing_month is not None:
        raise HTTPException(
            status_code=422,
            detail=f"An earlier EMI installment month must be recognized first: {_format_installment_month(missing_month)}",
        )

    if not allow_later_linked_transactions and service.later_linked_transaction_exists(emi_plan, installment_month):
        raise HTTPException(
            status_code=422,
            detail="Cannot backfill an EMI installment before an already-recorded later installment",
        )

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


def _get_transaction_or_404(db: Session, transaction_id: uuid.UUID) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def _validated_transaction_data(
    db: Session,
    payload: TransactionCreate,
    allow_inactive_emi_plan_id: uuid.UUID | None = None,
    existing_emi_transaction: Transaction | None = None,
) -> dict[str, object]:
    data = payload.model_dump()

    if payload.recurring_commitment_id is not None and payload.emi_plan_id is not None:
        raise HTTPException(status_code=422, detail="Transactions cannot link to both a recurring commitment and an EMI plan")

    source_account = None
    if payload.source_account_id is not None:
        source_account = get_account_or_404(db, payload.source_account_id)

    destination_account = None
    if payload.destination_account_id is not None:
        destination_account = get_account_or_404(db, payload.destination_account_id)

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

    if payload.transaction_type == TransactionType.INCOME and destination_account is not None:
        if destination_account.account_type == AccountType.CREDIT_CARD:
            raise HTTPException(
                status_code=422,
                detail="Income transactions cannot use a credit-card destination account",
            )

    if linked_commitment is not None:
        _validate_commitment_link(payload, linked_commitment)

    if linked_emi_plan is not None:
        allow_later_linked_transactions = False
        if existing_emi_transaction is not None and existing_emi_transaction.emi_plan_id == linked_emi_plan.id:
            existing_month = date_utils.month_start(
                date_utils.app_local_date_from_utc_naive(existing_emi_transaction.occurred_at)
            )
            replacement_month = date_utils.month_start(
                date_utils.app_local_date_from_utc_naive(data["occurred_at"])
            )
            allow_later_linked_transactions = existing_month == replacement_month

        _validate_emi_link(
            db,
            payload,
            linked_emi_plan,
            data["occurred_at"],
            allow_inactive_emi_plan_id=allow_inactive_emi_plan_id,
            allow_later_linked_transactions=allow_later_linked_transactions,
        )

    return data


def _assert_emi_correction_keeps_history_contiguous(
    db: Session,
    transaction: Transaction,
    replacement_emi_plan_id: uuid.UUID | None = None,
    replacement_occurred_at: datetime | None = None,
) -> None:
    if transaction.emi_plan_id is None:
        return

    original_month = date_utils.month_start(
        date_utils.app_local_date_from_utc_naive(transaction.occurred_at)
    )
    replacement_month = None
    if replacement_emi_plan_id is not None and replacement_occurred_at is not None:
        replacement_month = date_utils.month_start(
            date_utils.app_local_date_from_utc_naive(replacement_occurred_at)
        )

    if replacement_emi_plan_id == transaction.emi_plan_id and replacement_month == original_month:
        return

    plan = get_emi_plan_or_404(db, transaction.emi_plan_id)
    if EMIService(db).later_linked_transaction_exists(plan, original_month):
        raise HTTPException(
            status_code=422,
            detail="Cannot move, unlink, or void an EMI installment while a later installment exists",
        )


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)) -> Transaction:
    transaction = Transaction(**_validated_transaction_data(db, payload))
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
    include_voided: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")

    statement = select(Transaction)
    if not include_voided:
        statement = statement.where(Transaction.voided_at.is_(None))
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


@router.put("/{transaction_id}", response_model=TransactionRead)
def update_transaction(
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
) -> Transaction:
    transaction = _get_transaction_or_404(db, transaction_id)
    if transaction.voided_at is not None:
        raise HTTPException(status_code=409, detail="Voided transactions cannot be edited")

    original_emi_plan_id = transaction.emi_plan_id
    transaction.voided_at = date_utils.utc_now_naive()
    db.flush()

    try:
        data = _validated_transaction_data(
            db,
            payload,
            allow_inactive_emi_plan_id=(
                original_emi_plan_id if payload.emi_plan_id == original_emi_plan_id else None
            ),
            existing_emi_transaction=transaction,
        )
        _assert_emi_correction_keeps_history_contiguous(
            db,
            transaction,
            replacement_emi_plan_id=payload.emi_plan_id,
            replacement_occurred_at=data["occurred_at"],
        )
        for field, value in data.items():
            setattr(transaction, field, value)
        transaction.voided_at = None
        transaction.updated_at = date_utils.utc_now_naive()
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", response_model=TransactionRead)
def void_transaction(transaction_id: uuid.UUID, db: Session = Depends(get_db)) -> Transaction:
    transaction = _get_transaction_or_404(db, transaction_id)
    if transaction.voided_at is not None:
        return transaction

    voided_at = date_utils.utc_now_naive()
    transaction.voided_at = voided_at
    transaction.updated_at = voided_at
    db.flush()

    try:
        _assert_emi_correction_keeps_history_contiguous(db, transaction)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(transaction)
    return transaction
