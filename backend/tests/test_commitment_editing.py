from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.account import Account, AccountType
from app.models.category import Category
from app.models.commitment import CommitmentType, RecurringCommitment
from app.models.transaction import Transaction, TransactionType
from app.services.commitment_status_service import CommitmentStatusService
from app.services.safe_to_spend_service import SafeToSpendService


D = Decimal
JULY_AS_OF = date(2026, 7, 8)


def at(year: int = 2026, month: int = 7, day: int = 8) -> datetime:
    return datetime(year, month, day, 12, 0, 0)


@contextmanager
def api_client_for_session(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, headers={"Authorization": "Bearer spendlens-local-development-api-token"}) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def add_account(
    db: Session,
    name: str = "Bank",
    account_type: AccountType = AccountType.BANK,
    opening_balance: str = "10000",
) -> Account:
    account = Account(
        name=name,
        account_type=account_type,
        opening_balance=D("0") if account_type == AccountType.CREDIT_CARD else D(opening_balance),
        opening_outstanding=D("0"),
        credit_limit=D("10000") if account_type == AccountType.CREDIT_CARD else None,
        billing_day=15 if account_type == AccountType.CREDIT_CARD else None,
        due_day=25 if account_type == AccountType.CREDIT_CARD else None,
    )
    db.add(account)
    db.flush()
    return account


def add_category(db: Session, name: str = "Housing") -> Category:
    category = Category(name=name)
    db.add(category)
    db.flush()
    return category


def add_commitment(
    db: Session,
    account: Account,
    category: Category,
    amount: str = "6500",
    due_day: int = 10,
    commitment_type: CommitmentType = CommitmentType.FIXED_EXPENSE,
    is_active: bool = True,
) -> RecurringCommitment:
    commitment = RecurringCommitment(
        name="Rent",
        amount=D(amount),
        account_id=account.id,
        category_id=category.id,
        commitment_type=commitment_type,
        due_day=due_day,
        is_active=is_active,
    )
    db.add(commitment)
    db.flush()
    return commitment


def add_transaction(
    db: Session,
    commitment: RecurringCommitment,
    account: Account,
    category: Category,
    amount: str = "6500",
) -> Transaction:
    transaction = Transaction(
        transaction_type=TransactionType.EXPENSE,
        amount=D(amount),
        source_account_id=account.id,
        category_id=category.id,
        recurring_commitment_id=commitment.id,
        merchant="Original merchant",
        description="Original description",
        occurred_at=at(),
        created_at=at(),
    )
    db.add(transaction)
    db.flush()
    return transaction


def create_account_api(client: TestClient, name: str = "Bank", account_type: str = "bank") -> str:
    payload: dict[str, object] = {
        "name": name,
        "account_type": account_type,
        "opening_balance": "0.00" if account_type == "credit_card" else "10000.00",
    }
    if account_type == "credit_card":
        payload.update(
            {
                "opening_outstanding": "0.00",
                "credit_limit": "10000.00",
                "billing_day": 15,
                "due_day": 25,
            }
        )

    response = client.post("/api/v1/accounts", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def create_category_api(client: TestClient, name: str = "Housing") -> str:
    response = client.post("/api/v1/categories", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_commitment_api(
    client: TestClient,
    account_id: str,
    category_id: str,
    commitment_type: str = "fixed_expense",
    amount: str = "6500.00",
    due_day: int = 10,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/commitments",
        json={
            "name": "Rent",
            "amount": amount,
            "account_id": account_id,
            "category_id": category_id,
            "commitment_type": commitment_type,
            "due_day": due_day,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def update_payload_from_api(commitment: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = {
        "name": commitment["name"],
        "amount": commitment["amount"],
        "account_id": commitment["account_id"],
        "category_id": commitment["category_id"],
        "due_day": commitment["due_day"],
        "is_active": commitment["is_active"],
    }
    payload.update(overrides)
    return payload


def update_payload_from_model(commitment: RecurringCommitment, **overrides: object) -> dict[str, object]:
    payload = {
        "name": commitment.name,
        "amount": f"{D(commitment.amount):.2f}",
        "account_id": str(commitment.account_id),
        "category_id": str(commitment.category_id),
        "due_day": commitment.due_day,
        "is_active": commitment.is_active,
    }
    payload.update(overrides)
    return payload


def update_existing_commitment(
    db: Session,
    commitment: RecurringCommitment,
    **overrides: object,
) -> dict[str, object]:
    with api_client_for_session(db) as client:
        response = client.put(
            f"/api/v1/commitments/{commitment.id}",
            json=update_payload_from_model(commitment, **overrides),
        )
    assert response.status_code == 200
    db.refresh(commitment)
    return response.json()


def test_commitment_update_changes_name(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, name="Corrected rent"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Corrected rent"


def test_commitment_update_changes_amount(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, amount="7000.00"),
    )

    assert response.status_code == 200
    assert response.json()["amount"] == "7000.00"


def test_commitment_update_changes_account(api_client: TestClient) -> None:
    bank = create_account_api(api_client, "Bank")
    wallet = create_account_api(api_client, "Wallet", "wallet")
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, account_id=wallet),
    )

    assert response.status_code == 200
    assert response.json()["account_id"] == wallet


def test_commitment_update_changes_category(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    salary = create_category_api(api_client, "Salary")
    housing = create_category_api(api_client, "Housing")
    commitment = create_commitment_api(api_client, bank, salary)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, category_id=housing),
    )

    assert response.status_code == 200
    assert response.json()["category_id"] == housing


def test_commitment_update_changes_due_day(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, due_day=18),
    )

    assert response.status_code == 200
    assert response.json()["due_day"] == 18


def test_commitment_update_deactivates_commitment(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, is_active=False),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_unknown_commitment_update_returns_404(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{uuid4()}",
        json=update_payload_from_api(commitment),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Recurring commitment not found"


def test_commitment_update_rejects_invalid_amount(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, amount="0.00"),
    )

    assert response.status_code == 422


def test_commitment_update_rejects_invalid_due_day(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, due_day=29),
    )

    assert response.status_code == 422


def test_commitment_update_rejects_unknown_account(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, account_id=str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_commitment_update_rejects_unknown_category(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, category_id=str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


def test_investment_commitment_cannot_be_updated_to_use_credit_card(api_client: TestClient) -> None:
    bank = create_account_api(api_client, "Bank")
    card = create_account_api(api_client, "Card", "credit_card")
    category = create_category_api(api_client, "Investment")
    commitment = create_commitment_api(api_client, bank, category, commitment_type="investment")

    response = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, account_id=card),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Investment commitments cannot use a credit-card account"


def test_investment_commitment_cannot_be_created_with_credit_card(api_client: TestClient) -> None:
    card = create_account_api(api_client, "Card", "credit_card")
    category = create_category_api(api_client, "Investment")

    response = api_client.post(
        "/api/v1/commitments",
        json={
            "name": "SIP",
            "amount": "5000.00",
            "account_id": card,
            "category_id": category,
            "commitment_type": "investment",
            "due_day": 5,
            "is_active": True,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Investment commitments cannot use a credit-card account"


def test_commitment_type_cannot_be_changed_through_update_schema(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category)
    payload = update_payload_from_api(commitment, commitment_type="investment")

    response = api_client.put(f"/api/v1/commitments/{commitment['id']}", json=payload)

    assert response.status_code == 422
    assert "commitment_type" in str(response.json()["detail"])
    commitments = api_client.get("/api/v1/commitments").json()
    assert commitments[0]["commitment_type"] == "fixed_expense"


def test_existing_linked_transaction_remains_linked_after_commitment_edit(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, category)
    transaction = add_transaction(db_session, commitment, bank, category)

    update_existing_commitment(db_session, commitment, name="Corrected rent")
    db_session.refresh(transaction)

    assert transaction.recurring_commitment_id == commitment.id


def test_existing_linked_transaction_is_not_mutated_after_category_correction(db_session: Session) -> None:
    old_category = add_category(db_session, "Salary")
    new_category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, old_category)
    transaction = add_transaction(db_session, commitment, bank, old_category)

    update_existing_commitment(db_session, commitment, category_id=str(new_category.id))
    db_session.refresh(transaction)

    assert commitment.category_id == new_category.id
    assert transaction.category_id == old_category.id
    assert transaction.amount == D("6500.00")
    assert transaction.merchant == "Original merchant"
    assert transaction.description == "Original description"


def test_existing_linked_transaction_is_not_mutated_after_account_correction(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    old_bank = add_account(db_session, "Old bank")
    new_wallet = add_account(db_session, "Wallet", AccountType.WALLET)
    commitment = add_commitment(db_session, old_bank, category)
    transaction = add_transaction(db_session, commitment, old_bank, category)

    update_existing_commitment(db_session, commitment, account_id=str(new_wallet.id))
    db_session.refresh(transaction)

    assert commitment.account_id == new_wallet.id
    assert transaction.source_account_id == old_bank.id
    assert transaction.amount == D("6500.00")
    assert transaction.merchant == "Original merchant"
    assert transaction.description == "Original description"


def test_paid_commitment_remains_paid_after_category_only_correction(db_session: Session) -> None:
    old_category = add_category(db_session, "Salary")
    new_category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, old_category, amount="6500")
    add_transaction(db_session, commitment, bank, old_category, amount="6500")

    update_existing_commitment(db_session, commitment, category_id=str(new_category.id))
    status = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)[0]

    assert status["status"] == "paid"
    assert status["paid_amount_this_month"] == D("6500.00")
    assert status["remaining_amount_this_month"] == D("0")


def test_increasing_commitment_amount_above_paid_amount_creates_remaining_reserve(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, category, amount="6500", due_day=10)
    add_transaction(db_session, commitment, bank, category, amount="6500")

    update_existing_commitment(db_session, commitment, amount="7000.00")
    status = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)[0]
    summary = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert status["paid_amount_this_month"] == D("6500.00")
    assert status["remaining_amount_this_month"] == D("500.00")
    assert status["status"] == "partial"
    assert summary["remaining_fixed_commitments"] == D("500.00")


def test_decreasing_commitment_amount_below_paid_amount_clamps_remaining_reserve_to_zero(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, category, amount="6500")
    add_transaction(db_session, commitment, bank, category, amount="6500")

    update_existing_commitment(db_session, commitment, amount="6000.00")
    status = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)[0]
    summary = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert status["paid_amount_this_month"] == D("6500.00")
    assert status["remaining_amount_this_month"] == D("0")
    assert status["status"] == "paid"
    assert summary["remaining_fixed_commitments"] == D("0")


def test_inactive_commitment_is_excluded_from_active_status(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, category)

    update_existing_commitment(db_session, commitment, is_active=False)

    assert CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF) == []


def test_inactive_commitment_is_excluded_from_remaining_fixed_commitments(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, category, amount="6500")

    update_existing_commitment(db_session, commitment, is_active=False)
    summary = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert summary["remaining_fixed_commitments"] == D("0")


def test_reactivated_commitment_participates_in_status_and_safe_to_spend_again(db_session: Session) -> None:
    category = add_category(db_session, "Housing")
    bank = add_account(db_session)
    commitment = add_commitment(db_session, bank, category, amount="6500")

    update_existing_commitment(db_session, commitment, is_active=False)
    update_existing_commitment(db_session, commitment, is_active=True)
    statuses = CommitmentStatusService(db_session).list_active_fixed_statuses(JULY_AS_OF)
    summary = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert len(statuses) == 1
    assert statuses[0]["commitment_id"] == commitment.id
    assert summary["remaining_fixed_commitments"] == D("6500.00")


def test_explicit_as_of_commitment_status_after_update_remains_deterministic(api_client: TestClient) -> None:
    bank = create_account_api(api_client)
    category = create_category_api(api_client)
    commitment = create_commitment_api(api_client, bank, category, due_day=10)
    update = api_client.put(
        f"/api/v1/commitments/{commitment['id']}",
        json=update_payload_from_api(commitment, due_day=12),
    )
    assert update.status_code == 200

    first = api_client.get("/api/v1/commitments/status?as_of=2026-07-12")
    second = api_client.get("/api/v1/commitments/status?as_of=2026-07-12")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()[0]["status"] == "due_today"
    assert first.json()[0]["due_date"] == "2026-07-12"