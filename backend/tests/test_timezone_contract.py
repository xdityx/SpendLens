from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.category import Category
from app.models.commitment import CommitmentType, RecurringCommitment
from app.models.financial_profile import FinancialProfile
from app.models.transaction import Transaction, TransactionType
from app.services import date_utils
from app.services.balance_service import BalanceService
from app.services.card_service import CardService
from app.services.safe_to_spend_service import SafeToSpendService

D = Decimal


def add_category(db: Session, name: str = "Food") -> Category:
    category = Category(name=name)
    db.add(category)
    db.flush()
    return category


def add_bank(db: Session, name: str = "Bank", opening_balance: str = "0") -> Account:
    account = Account(
        name=name,
        account_type=AccountType.BANK,
        opening_balance=D(opening_balance),
        opening_outstanding=D("0"),
    )
    db.add(account)
    db.flush()
    return account


def add_card(db: Session, billing_day: int = 15) -> Account:
    account = Account(
        name="Card",
        account_type=AccountType.CREDIT_CARD,
        opening_balance=D("0"),
        opening_outstanding=D("0"),
        credit_limit=D("1000"),
        billing_day=billing_day,
        due_day=25,
    )
    db.add(account)
    db.flush()
    return account


def add_profile(db: Session, target: str = "0") -> FinancialProfile:
    profile = FinancialProfile(monthly_savings_target=D(target), salary_day=1)
    db.add(profile)
    db.flush()
    return profile


def add_commitment(db: Session, account: Account, category: Category, amount: str = "300") -> RecurringCommitment:
    commitment = RecurringCommitment(
        name="Rent",
        amount=D(amount),
        category_id=category.id,
        account_id=account.id,
        commitment_type=CommitmentType.FIXED_EXPENSE,
        due_day=10,
        is_active=True,
    )
    db.add(commitment)
    db.flush()
    return commitment


def add_transaction(
    db: Session,
    transaction_type: TransactionType,
    amount: str,
    occurred_at: datetime,
    source_account: Account | None = None,
    destination_account: Account | None = None,
    category: Category | None = None,
    commitment: RecurringCommitment | None = None,
) -> Transaction:
    transaction = Transaction(
        transaction_type=transaction_type,
        amount=D(amount),
        source_account_id=source_account.id if source_account else None,
        destination_account_id=destination_account.id if destination_account else None,
        category_id=category.id if category else None,
        recurring_commitment_id=commitment.id if commitment else None,
        occurred_at=occurred_at,
    )
    db.add(transaction)
    db.flush()
    return transaction


def create_category(client: TestClient) -> str:
    response = client.post("/api/v1/categories", json={"name": "Food"})
    assert response.status_code == 201
    return response.json()["id"]


def create_bank(client: TestClient) -> str:
    response = client.post(
        "/api/v1/accounts",
        json={"name": "Bank", "account_type": "bank", "opening_balance": "1000.00"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def expense_payload(account_id: str, category_id: str, occurred_at: str) -> dict[str, Any]:
    return {
        "transaction_type": "expense",
        "amount": "100.00",
        "source_account_id": account_id,
        "category_id": category_id,
        "occurred_at": occurred_at,
    }


def test_timezone_aware_transaction_input_is_stored_utc_naive(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 7, 7, 13, 0, 0))
    account = create_bank(api_client)
    category = create_category(api_client)

    response = api_client.post(
        "/api/v1/transactions",
        json=expense_payload(account, category, "2026-07-07T18:00:00+05:30"),
    )

    assert response.status_code == 201
    assert response.json()["occurred_at"] == "2026-07-07T12:30:00"


def test_timezone_naive_transaction_input_is_interpreted_in_app_timezone(
    api_client: TestClient,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 7, 7, 13, 0, 0))
    account = create_bank(api_client)
    category = create_category(api_client)

    response = api_client.post(
        "/api/v1/transactions",
        json=expense_payload(account, category, "2026-07-07T18:00:00"),
    )

    assert response.status_code == 201
    assert response.json()["occurred_at"] == "2026-07-07T12:30:00"


def test_current_local_transaction_is_not_rejected_as_future(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 7, 7, 12, 31, 0))
    account = create_bank(api_client)
    category = create_category(api_client)

    response = api_client.post(
        "/api/v1/transactions",
        json=expense_payload(account, category, "2026-07-07T18:00:00"),
    )

    assert response.status_code == 201


def test_genuinely_future_local_transaction_is_rejected(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 7, 7, 12, 31, 0))
    account = create_bank(api_client)
    category = create_category(api_client)

    response = api_client.post(
        "/api/v1/transactions",
        json=expense_payload(account, category, "2026-07-07T18:02:00"),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Transactions cannot be future-dated"


def test_current_app_date_uses_configured_timezone(monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 7, 31, 20, 0, 0))

    assert date_utils.current_app_date() == date(2026, 8, 1)


def test_app_local_month_start_converts_to_utc_naive_boundary() -> None:
    start, end = date_utils.current_month_utc_bounds(date(2026, 8, 7))

    assert start == datetime(2026, 7, 31, 18, 30, 0)
    assert end == datetime(2026, 8, 7, 18, 30, 0)


def test_monthly_investment_after_local_month_start_on_previous_utc_date_is_included(
    db_session: Session,
) -> None:
    category = add_category(db_session, "Investment")
    bank = add_bank(db_session, opening_balance="1000")
    add_profile(db_session, target="500")
    add_transaction(
        db_session,
        TransactionType.INVESTMENT,
        "200",
        datetime(2026, 7, 31, 19, 0, 0),
        source_account=bank,
        category=category,
    )

    summary = SafeToSpendService(db_session).summary(date(2026, 8, 7))

    assert summary["savings_completed_this_month"] == D("200.00")


def test_monthly_investment_before_local_month_start_is_excluded(db_session: Session) -> None:
    category = add_category(db_session, "Investment")
    bank = add_bank(db_session, opening_balance="1000")
    add_profile(db_session, target="500")
    add_transaction(
        db_session,
        TransactionType.INVESTMENT,
        "200",
        datetime(2026, 7, 31, 18, 29, 0),
        source_account=bank,
        category=category,
    )

    summary = SafeToSpendService(db_session).summary(date(2026, 8, 7))

    assert summary["savings_completed_this_month"] == D("0")


def test_recurring_commitment_fulfillment_uses_app_local_month_boundaries(db_session: Session) -> None:
    category = add_category(db_session)
    bank = add_bank(db_session, opening_balance="1000")
    commitment = add_commitment(db_session, bank, category, "300")
    add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "300",
        datetime(2026, 7, 31, 19, 0, 0),
        source_account=bank,
        category=category,
        commitment=commitment,
    )

    summary = SafeToSpendService(db_session).summary(date(2026, 8, 7))

    assert summary["remaining_fixed_commitments"] == D("0")


def test_balance_as_of_end_of_day_uses_app_local_boundary(db_session: Session) -> None:
    bank = add_bank(db_session, opening_balance="0")
    add_transaction(db_session, TransactionType.INCOME, "100", datetime(2026, 8, 1, 18, 0, 0), destination_account=bank)
    add_transaction(db_session, TransactionType.INCOME, "50", datetime(2026, 8, 1, 19, 0, 0), destination_account=bank)

    assert BalanceService(db_session).current_balance(bank, date(2026, 8, 1)) == D("100.00")


def test_card_billing_cycle_spend_uses_app_local_cycle_boundary(db_session: Session) -> None:
    category = add_category(db_session)
    card = add_card(db_session, billing_day=15)
    add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "75",
        datetime(2026, 7, 15, 18, 0, 0),
        source_account=card,
        category=category,
    )
    add_transaction(
        db_session,
        TransactionType.EXPENSE,
        "100",
        datetime(2026, 7, 15, 19, 0, 0),
        source_account=card,
        category=category,
    )

    assert CardService(db_session).current_cycle_spend(card, date(2026, 7, 20)) == D("100.00")


def test_transaction_date_filters_use_app_local_calendar_dates(api_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 8, 3, 0, 0, 0))
    account = create_bank(api_client)
    category = create_category(api_client)
    first = api_client.post(
        "/api/v1/transactions",
        json=expense_payload(account, category, "2026-07-31T18:00:00+00:00"),
    )
    second = api_client.post(
        "/api/v1/transactions",
        json=expense_payload(account, category, "2026-07-31T19:00:00+00:00"),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    response = api_client.get("/api/v1/transactions?date_from=2026-08-01&date_to=2026-08-01")

    assert response.status_code == 200
    transactions = response.json()
    assert len(transactions) == 1
    assert transactions[0]["occurred_at"] == "2026-07-31T19:00:00"


def test_explicit_as_of_behavior_remains_deterministic(db_session: Session) -> None:
    bank = add_bank(db_session, opening_balance="0")
    add_transaction(db_session, TransactionType.INCOME, "100", datetime(2026, 8, 1, 18, 0, 0), destination_account=bank)
    add_transaction(db_session, TransactionType.INCOME, "50", datetime(2026, 8, 1, 19, 0, 0), destination_account=bank)

    summary = SafeToSpendService(db_session).summary(date(2026, 8, 1))

    assert summary["liquid_cash"] == D("100.00")
