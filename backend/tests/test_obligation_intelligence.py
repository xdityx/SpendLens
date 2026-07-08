from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.category import Category
from app.models.commitment import CommitmentType, RecurringCommitment
from app.models.emi_plan import EMIPlan, EMISetupCurrentMonthState
from app.models.transaction import Transaction, TransactionType
from app.services import date_utils
from app.services.balance_service import BalanceService
from app.services.commitment_status_service import CommitmentStatusService
from app.services.emi_service import EMIService
from app.services.safe_to_spend_service import SafeToSpendService

D = Decimal
JULY_AS_OF = date(2026, 7, 8)


def at(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, 0)


def add_category(db: Session, name: str = "Food") -> Category:
    category = Category(name=name)
    db.add(category)
    db.flush()
    return category


def add_bank(db: Session, name: str = "Bank", opening_balance: str = "10000") -> Account:
    account = Account(
        name=name,
        account_type=AccountType.BANK,
        opening_balance=D(opening_balance),
        opening_outstanding=D("0"),
    )
    db.add(account)
    db.flush()
    return account


def add_card(
    db: Session,
    name: str = "Card",
    opening_outstanding: str = "0",
    credit_limit: str = "10000",
) -> Account:
    account = Account(
        name=name,
        account_type=AccountType.CREDIT_CARD,
        opening_balance=D("0"),
        opening_outstanding=D(opening_outstanding),
        credit_limit=D(credit_limit),
        billing_day=15,
        due_day=25,
    )
    db.add(account)
    db.flush()
    return account


def add_commitment(
    db: Session,
    account: Account,
    category: Category,
    amount: str = "300",
    due_day: int = 10,
) -> RecurringCommitment:
    commitment = RecurringCommitment(
        name="Rent",
        amount=D(amount),
        category_id=category.id,
        account_id=account.id,
        commitment_type=CommitmentType.FIXED_EXPENSE,
        due_day=due_day,
        is_active=True,
    )
    db.add(commitment)
    db.flush()
    return commitment


def add_emi_plan(
    db: Session,
    account: Account,
    category: Category,
    monthly_installment: str = "850",
    remaining_amount_at_setup: str = "2500",
    setup_state: EMISetupCurrentMonthState = EMISetupCurrentMonthState.NOT_POSTED,
    tracking_start_month: date = date(2026, 7, 1),
    due_day: int = 12,
) -> EMIPlan:
    plan = EMIPlan(
        name="Tata Neu EMI",
        account_id=account.id,
        category_id=category.id,
        monthly_installment=D(monthly_installment),
        remaining_amount_at_setup=D(remaining_amount_at_setup),
        due_day=due_day,
        tracking_start_month=tracking_start_month,
        setup_current_month_state=setup_state,
        is_active=True,
    )
    db.add(plan)
    db.flush()
    return plan


def add_transaction(
    db: Session,
    transaction_type: TransactionType,
    amount: str,
    occurred_at: datetime = at(2026, 7, 8),
    source_account: Account | None = None,
    destination_account: Account | None = None,
    category: Category | None = None,
    commitment: RecurringCommitment | None = None,
    emi_plan: EMIPlan | None = None,
    created_at: datetime | None = None,
) -> Transaction:
    transaction = Transaction(
        transaction_type=transaction_type,
        amount=D(amount),
        source_account_id=source_account.id if source_account else None,
        destination_account_id=destination_account.id if destination_account else None,
        category_id=category.id if category else None,
        recurring_commitment_id=commitment.id if commitment else None,
        emi_plan_id=emi_plan.id if emi_plan else None,
        occurred_at=occurred_at,
        created_at=created_at or occurred_at,
    )
    db.add(transaction)
    db.flush()
    return transaction


def create_category(client: TestClient, name: str = "EMI") -> str:
    response = client.post("/api/v1/categories", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_bank(client: TestClient, name: str = "Bank") -> str:
    response = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "bank", "opening_balance": "10000.00"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_card(client: TestClient, name: str = "Card") -> str:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "account_type": "credit_card",
            "opening_balance": "0.00",
            "opening_outstanding": "0.00",
            "credit_limit": "10000.00",
            "billing_day": 15,
            "due_day": 25,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_commitment(client: TestClient, account_id: str, category_id: str, due_day: int = 10) -> str:
    response = client.post(
        "/api/v1/commitments",
        json={
            "name": "Rent",
            "amount": "6500.00",
            "category_id": category_id,
            "account_id": account_id,
            "commitment_type": "fixed_expense",
            "due_day": due_day,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_emi_plan(
    client: TestClient,
    account_id: str,
    category_id: str,
    monthly_installment: str = "850.00",
    remaining_amount_at_setup: str = "2500.00",
    setup_state: str = "not_posted",
    due_day: int = 12,
) -> str:
    response = client.post(
        "/api/v1/emi-plans",
        json={
            "name": "Tata Neu EMI",
            "account_id": account_id,
            "category_id": category_id,
            "monthly_installment": monthly_installment,
            "remaining_amount_at_setup": remaining_amount_at_setup,
            "due_day": due_day,
            "setup_current_month_state": setup_state,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def post_emi_expense(client: TestClient, card_id: str, category_id: str, emi_plan_id: str, amount: str = "850.00"):
    return client.post(
        "/api/v1/transactions",
        json={
            "transaction_type": "expense",
            "amount": amount,
            "source_account_id": card_id,
            "category_id": category_id,
            "emi_plan_id": emi_plan_id,
            "occurred_at": "2026-07-08T12:00:00+05:30",
        },
    )


def test_one_unit_linked_payment_does_not_fulfill_large_commitment(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500")
    add_transaction(db_session, TransactionType.EXPENSE, "1", source_account=bank, category=category, commitment=commitment)

    summary = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert summary["remaining_fixed_commitments"] == D("6499.00")


def test_partial_payment_reduces_remaining_fixed_commitment_reserve(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500")
    add_transaction(db_session, TransactionType.EXPENSE, "1500", source_account=bank, category=category, commitment=commitment)

    assert SafeToSpendService(db_session).summary(JULY_AS_OF)["remaining_fixed_commitments"] == D("5000.00")


def test_multiple_linked_payments_sum_toward_commitment_fulfillment(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500")
    add_transaction(db_session, TransactionType.EXPENSE, "1000", source_account=bank, category=category, commitment=commitment)
    add_transaction(db_session, TransactionType.EXPENSE, "2500", source_account=bank, category=category, commitment=commitment)

    assert SafeToSpendService(db_session).summary(JULY_AS_OF)["remaining_fixed_commitments"] == D("3000.00")


def test_exact_commitment_payment_marks_commitment_paid(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500")
    add_transaction(db_session, TransactionType.EXPENSE, "6500", source_account=bank, category=category, commitment=commitment)

    status = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)[0]

    assert status["status"] == "paid"
    assert status["remaining_amount_this_month"] == D("0.00")


def test_commitment_overpayment_clamps_remaining_amount_to_zero(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500")
    add_transaction(db_session, TransactionType.EXPENSE, "7000", source_account=bank, category=category, commitment=commitment)

    status = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)[0]

    assert status["remaining_amount_this_month"] == D("0")


def test_upcoming_commitment_status(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    add_commitment(db_session, bank, category, "6500", due_day=10)

    assert CommitmentStatusService(db_session).list_active_fixed_statuses(date(2026, 7, 8))[0]["status"] == "upcoming"


def test_due_today_commitment_status(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    add_commitment(db_session, bank, category, "6500", due_day=10)

    assert CommitmentStatusService(db_session).list_active_fixed_statuses(date(2026, 7, 10))[0]["status"] == "due_today"


def test_overdue_commitment_status(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    add_commitment(db_session, bank, category, "6500", due_day=10)

    assert CommitmentStatusService(db_session).list_active_fixed_statuses(date(2026, 7, 11))[0]["status"] == "overdue"


def test_partial_commitment_status(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500", due_day=10)
    add_transaction(db_session, TransactionType.EXPENSE, "1000", source_account=bank, category=category, commitment=commitment)

    assert CommitmentStatusService(db_session).list_active_fixed_statuses(date(2026, 7, 8))[0]["status"] == "partial"


def test_overdue_partial_commitment_status(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "6500", due_day=10)
    add_transaction(db_session, TransactionType.EXPENSE, "1000", source_account=bank, category=category, commitment=commitment)

    assert CommitmentStatusService(db_session).list_active_fixed_statuses(date(2026, 7, 11))[0]["status"] == "overdue_partial"


def test_fulfilled_at_is_transaction_that_crosses_commitment_threshold(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_bank(db_session)
    commitment = add_commitment(db_session, bank, category, "300", due_day=10)
    first = add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "100",
        occurred_at=at(2026, 7, 2, 9),
        source_account=bank,
        category=category,
        commitment=commitment,
        created_at=at(2026, 7, 2, 9, 1),
    )
    second = add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "250",
        occurred_at=at(2026, 7, 3, 9),
        source_account=bank,
        category=category,
        commitment=commitment,
        created_at=at(2026, 7, 3, 9, 1),
    )
    add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "50",
        occurred_at=at(2026, 7, 4, 9),
        source_account=bank,
        category=category,
        commitment=commitment,
        created_at=at(2026, 7, 4, 9, 1),
    )

    status = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)[0]

    assert first.occurred_at < second.occurred_at
    assert status["fulfilled_at"] == second.occurred_at


def test_non_credit_card_emi_account_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    bank = create_bank(api_client)
    category = create_category(api_client)

    response = api_client.post(
        "/api/v1/emi-plans",
        json={
            "name": "Phone EMI",
            "account_id": bank,
            "category_id": category,
            "monthly_installment": "850.00",
            "remaining_amount_at_setup": "2500.00",
            "due_day": 12,
            "setup_current_month_state": "not_posted",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "EMI plans must use a credit-card account"


def test_not_posted_current_emi_installment_is_reserved(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    add_emi_plan(db_session, card, category, setup_state=EMISetupCurrentMonthState.NOT_POSTED)

    status = EMIService(db_session).list_statuses(JULY_AS_OF)[0]

    assert status["current_month_status"] == "upcoming"
    assert status["current_month_reserve"] == D("850.00")


def test_included_in_opening_liability_current_emi_installment_is_not_reserved(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    add_emi_plan(db_session, card, category, setup_state=EMISetupCurrentMonthState.INCLUDED_IN_OPENING_LIABILITY)

    status = EMIService(db_session).list_statuses(JULY_AS_OF)[0]

    assert status["current_month_status"] == "included_in_card_liability"
    assert status["current_month_reserve"] == D("0")


def test_settled_before_tracking_current_emi_installment_is_not_reserved(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    add_emi_plan(db_session, card, category, setup_state=EMISetupCurrentMonthState.SETTLED_BEFORE_TRACKING)

    status = EMIService(db_session).list_statuses(JULY_AS_OF)[0]

    assert status["current_month_status"] == "settled_before_tracking"
    assert status["current_month_reserve"] == D("0")


def test_setup_recognition_reduces_remaining_unrecognized_amount(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    add_emi_plan(
        db_session,
        card,
        category,
        remaining_amount_at_setup="2500",
        monthly_installment="850",
        setup_state=EMISetupCurrentMonthState.INCLUDED_IN_OPENING_LIABILITY,
    )

    status = EMIService(db_session).list_statuses(JULY_AS_OF)[0]

    assert status["remaining_unrecognized_amount"] == D("1650.00")


def test_emi_expense_linked_to_wrong_card_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client, "Plan Card")
    other_card = create_card(api_client, "Other Card")
    category = create_category(api_client)
    plan = create_emi_plan(api_client, card, category)

    response = post_emi_expense(api_client, other_card, category, plan)

    assert response.status_code == 422
    assert "credit-card account_id" in response.json()["detail"]


def test_emi_expense_linked_to_wrong_category_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    category = create_category(api_client, "EMI")
    other_category = create_category(api_client, "Food")
    plan = create_emi_plan(api_client, card, category)

    response = post_emi_expense(api_client, card, other_category, plan)

    assert response.status_code == 422
    assert response.json()["detail"] == "Linked EMI transaction category_id must match the EMI plan category_id"


def test_non_expense_emi_transaction_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    bank = create_bank(api_client)
    category = create_category(api_client)
    plan = create_emi_plan(api_client, card, category)

    response = api_client.post(
        "/api/v1/transactions",
        json={
            "transaction_type": "income",
            "amount": "850.00",
            "destination_account_id": bank,
            "emi_plan_id": plan,
            "occurred_at": "2026-07-08T12:00:00+05:30",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "EMI plan transactions must be expense transactions"


def test_recurring_commitment_and_emi_plan_together_are_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    category = create_category(api_client)
    commitment = create_commitment(api_client, card, category)
    plan = create_emi_plan(api_client, card, category)

    response = api_client.post(
        "/api/v1/transactions",
        json={
            "transaction_type": "expense",
            "amount": "850.00",
            "source_account_id": card,
            "category_id": category,
            "recurring_commitment_id": commitment,
            "emi_plan_id": plan,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Transactions cannot link to both a recurring commitment and an EMI plan"


def test_unknown_emi_plan_returns_404(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    category = create_category(api_client)

    response = post_emi_expense(api_client, card, category, str(uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"] == "EMI plan not found"


def test_wrong_emi_installment_amount_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    category = create_category(api_client)
    plan = create_emi_plan(api_client, card, category)

    response = post_emi_expense(api_client, card, category, plan, amount="800.00")

    assert response.status_code == 422
    assert "expected installment amount 850.00" in response.json()["detail"]


def test_final_smaller_emi_installment_amount_is_accepted(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    category = create_category(api_client)
    plan = create_emi_plan(api_client, card, category, monthly_installment="850.00", remaining_amount_at_setup="800.00")

    response = post_emi_expense(api_client, card, category, plan, amount="800.00")

    assert response.status_code == 201
    assert response.json()["emi_plan_id"] == plan


def test_duplicate_emi_posting_in_same_app_month_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 20, 8))
    card = create_card(api_client)
    category = create_category(api_client)
    plan = create_emi_plan(api_client, card, category)
    first = post_emi_expense(api_client, card, category, plan)
    assert first.status_code == 201

    response = api_client.post(
        "/api/v1/transactions",
        json={
            "transaction_type": "expense",
            "amount": "850.00",
            "source_account_id": card,
            "category_id": category,
            "emi_plan_id": plan,
            "occurred_at": "2026-07-20T12:00:00+05:30",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "An EMI transaction already exists for this plan in that application-local month"


def test_emi_posting_raises_card_liability(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    plan = add_emi_plan(db_session, card, category)
    add_transaction(db_session, TransactionType.EXPENSE, "850", source_account=card, category=category, emi_plan=plan)

    assert BalanceService(db_session).credit_card_liability(card, JULY_AS_OF) == D("850.00")


def test_emi_posting_removes_current_month_reserve(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    plan = add_emi_plan(db_session, card, category)

    assert SafeToSpendService(db_session).summary(JULY_AS_OF)["remaining_emi_installments"] == D("850.00")
    add_transaction(db_session, TransactionType.EXPENSE, "850", source_account=card, category=category, emi_plan=plan)

    assert SafeToSpendService(db_session).summary(JULY_AS_OF)["remaining_emi_installments"] == D("0")


def test_safe_to_spend_unchanged_when_emi_reserve_becomes_card_expense(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    bank = add_bank(db_session, opening_balance="10000")
    card = add_card(db_session)
    plan = add_emi_plan(db_session, card, category, monthly_installment="850", remaining_amount_at_setup="2500")

    before = SafeToSpendService(db_session).summary(JULY_AS_OF)
    add_transaction(db_session, TransactionType.EXPENSE, "850", source_account=card, category=category, emi_plan=plan)
    after = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert before["liquid_cash"] == D("10000.00")
    assert before["credit_card_liability"] == D("0")
    assert before["remaining_emi_installments"] == D("850.00")
    assert after["credit_card_liability"] == D("850.00")
    assert after["remaining_emi_installments"] == D("0")
    assert before["safe_to_spend"] == after["safe_to_spend"]
    assert bank.id is not None


def test_next_month_reserves_next_emi_installment(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    plan = add_emi_plan(db_session, card, category, monthly_installment="850", remaining_amount_at_setup="2500")
    add_transaction(db_session, TransactionType.EXPENSE, "850", occurred_at=at(2026, 7, 10), source_account=card, category=category, emi_plan=plan)

    status = EMIService(db_session).list_statuses(date(2026, 8, 5))[0]

    assert status["current_month_status"] == "upcoming"
    assert status["current_month_reserve"] == D("850.00")


def test_setup_state_recognition_applies_only_to_tracking_start_month(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    add_emi_plan(db_session, card, category, setup_state=EMISetupCurrentMonthState.INCLUDED_IN_OPENING_LIABILITY)

    july_status = EMIService(db_session).list_statuses(JULY_AS_OF)[0]
    august_status = EMIService(db_session).list_statuses(date(2026, 8, 5))[0]

    assert july_status["current_month_reserve"] == D("0")
    assert august_status["current_month_reserve"] == D("850.00")


def test_completed_emi_has_zero_reserve(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    plan = add_emi_plan(db_session, card, category, monthly_installment="850", remaining_amount_at_setup="850")
    add_transaction(db_session, TransactionType.EXPENSE, "850", occurred_at=at(2026, 7, 10), source_account=card, category=category, emi_plan=plan)

    status = EMIService(db_session).list_statuses(date(2026, 8, 5))[0]

    assert status["current_month_status"] == "completed"
    assert status["current_month_reserve"] == D("0")


def test_emi_local_month_boundaries_use_app_timezone(db_session: Session) -> None:
    category = add_category(db_session, "EMI")
    card = add_card(db_session)
    plan = add_emi_plan(db_session, card, category, tracking_start_month=date(2026, 8, 1))
    add_transaction(db_session, TransactionType.EXPENSE, "850", occurred_at=at(2026, 7, 31, 19), source_account=card, category=category, emi_plan=plan)

    status = EMIService(db_session).list_statuses(date(2026, 8, 7))[0]

    assert status["current_month_status"] == "posted"
    assert status["current_month_reserve"] == D("0")


def test_emi_status_endpoint_respects_explicit_as_of(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card(api_client)
    category = create_category(api_client)
    plan = create_emi_plan(api_client, card, category, due_day=10)

    response = api_client.get("/api/v1/emi-plans/status?as_of=2026-07-10")

    assert response.status_code == 200
    status = response.json()[0]
    assert status["emi_plan_id"] == plan
    assert status["current_month_status"] == "due_today"


def test_commitment_status_endpoint_respects_explicit_as_of(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client, "Housing")
    commitment = create_commitment(api_client, bank, category, due_day=10)

    response = api_client.get("/api/v1/commitments/status?as_of=2026-07-10")

    assert response.status_code == 200
    status = response.json()[0]
    assert status["commitment_id"] == commitment
    assert status["status"] == "due_today"
