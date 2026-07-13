from datetime import date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.services.card_service import CardService
from app.services.safe_to_spend_service import SafeToSpendService


D = Decimal
AS_OF = date(2026, 7, 7)


def add_card(db: Session, opening_outstanding: str = "1000") -> Account:
    card = Account(
        name="Card",
        account_type=AccountType.CREDIT_CARD,
        opening_balance=D("0"),
        opening_outstanding=D(opening_outstanding),
        credit_limit=D("50000"),
        billing_day=12,
        due_day=1,
    )
    db.add(card)
    db.flush()
    return card


def add_category(db: Session) -> Category:
    category = Category(name="Food")
    db.add(category)
    db.flush()
    return category


def add_card_transaction(
    db: Session,
    card: Account,
    transaction_type: TransactionType,
    amount: str,
    occurred_at: datetime,
    category: Category | None = None,
    destination: bool = False,
) -> None:
    transaction = Transaction(
        transaction_type=transaction_type,
        amount=D(amount),
        source_account_id=None if destination else card.id,
        destination_account_id=card.id if destination else None,
        category_id=category.id if category else None,
        occurred_at=occurred_at,
    )
    db.add(transaction)
    db.flush()


def test_statement_snapshot_separates_due_and_unbilled_balances(db_session: Session) -> None:
    card = add_card(db_session)
    category = add_category(db_session)
    card.statement_balance = D("700")
    card.statement_due_date = date(2026, 8, 1)
    card.statement_balance_as_of = datetime(2026, 7, 1, 0, 0)

    add_card_transaction(
        db_session,
        card,
        TransactionType.EXPENSE,
        "200",
        datetime(2026, 7, 2, 12, 0),
        category=category,
    )
    add_card_transaction(
        db_session,
        card,
        TransactionType.TRANSFER,
        "300",
        datetime(2026, 7, 3, 12, 0),
        destination=True,
    )

    exposure = CardService(db_session).credit_card_exposure(card, AS_OF)

    assert exposure["outstanding"] == D("900.00")
    assert exposure["statement_balance_due"] == D("400.00")
    assert exposure["unbilled_balance"] == D("500.00")
    assert exposure["statement_due_date"] == date(2026, 8, 1)


def test_refund_after_snapshot_reduces_statement_due_first(db_session: Session) -> None:
    card = add_card(db_session)
    card.statement_balance = D("700")
    card.statement_due_date = date(2026, 8, 1)
    card.statement_balance_as_of = datetime(2026, 7, 1, 0, 0)

    add_card_transaction(
        db_session,
        card,
        TransactionType.REFUND,
        "100",
        datetime(2026, 7, 2, 12, 0),
        destination=True,
    )

    exposure = CardService(db_session).credit_card_exposure(card, AS_OF)

    assert exposure["outstanding"] == D("900.00")
    assert exposure["statement_balance_due"] == D("600.00")
    assert exposure["unbilled_balance"] == D("300.00")


def test_due_soon_position_does_not_change_safe_to_spend_formula(db_session: Session) -> None:
    card = add_card(db_session)
    card.statement_balance = D("700")
    card.statement_due_date = date(2026, 8, 1)
    card.statement_balance_as_of = datetime(2026, 7, 1, 0, 0)

    summary = SafeToSpendService(db_session).summary(AS_OF)

    assert summary["credit_card_liability"] == D("1000.00")
    assert summary["statement_balance_due"] == D("700.00")
    assert summary["unbilled_card_liability"] == D("300.00")
    assert summary["safe_to_spend"] == D("-1000.00")
    assert summary["due_soon_cash_position"] == D("-700.00")


def create_api_account(client: TestClient, account_type: str, opening_outstanding: str = "0") -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "Account",
        "account_type": account_type,
        "opening_balance": "1000" if account_type == "bank" else "0",
        "opening_outstanding": opening_outstanding,
    }
    if account_type == "credit_card":
        payload.update({"credit_limit": "50000", "billing_day": 12, "due_day": 1})

    response = client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201
    return response.json()


def test_statement_endpoint_updates_credit_card_snapshot(api_client: TestClient) -> None:
    card = create_api_account(api_client, "credit_card", opening_outstanding="1000")

    response = api_client.put(
        f"/api/v1/accounts/{card['id']}/statement",
        json={"statement_balance": "700", "statement_due_date": "2026-08-01"},
    )

    assert response.status_code == 200
    body = response.json()
    assert D(body["statement_balance"]) == D("700.00")
    assert body["statement_due_date"] == "2026-08-01"
    assert body["statement_balance_as_of"] is not None


def test_statement_endpoint_rejects_amount_above_outstanding(api_client: TestClient) -> None:
    card = create_api_account(api_client, "credit_card", opening_outstanding="1000")

    response = api_client.put(
        f"/api/v1/accounts/{card['id']}/statement",
        json={"statement_balance": "1000.01", "statement_due_date": "2026-08-01"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Statement balance cannot exceed the card's current outstanding balance"


def test_statement_endpoint_rejects_non_card_account(api_client: TestClient) -> None:
    bank = create_api_account(api_client, "bank")

    response = api_client.put(
        f"/api/v1/accounts/{bank['id']}/statement",
        json={"statement_balance": "100", "statement_due_date": "2026-08-01"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Statement balances can only be set for credit-card accounts"


def test_positive_statement_requires_due_date(api_client: TestClient) -> None:
    card = create_api_account(api_client, "credit_card", opening_outstanding="1000")

    response = api_client.put(
        f"/api/v1/accounts/{card['id']}/statement",
        json={"statement_balance": "700", "statement_due_date": None},
    )

    assert response.status_code == 422
