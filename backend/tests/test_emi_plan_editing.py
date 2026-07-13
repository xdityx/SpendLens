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
from app.models.emi_plan import EMIPlan, EMISetupCurrentMonthState
from app.models.transaction import Transaction, TransactionType
from app.services import date_utils
from app.services.emi_service import EMIService
from app.services.safe_to_spend_service import SafeToSpendService


D = Decimal
JULY_AS_OF = date(2026, 7, 8)
AUGUST_AS_OF = date(2026, 8, 8)
LOCKED_ERROR = (
    "EMI financial configuration is locked after the tracking month or installment history begins. "
    "Only name, due day, and active status can be changed."
)


def at(year: int = 2026, month: int = 7, day: int = 8, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, 0, 0)


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


def add_card(db: Session, name: str = "Card") -> Account:
    account = Account(
        name=name,
        account_type=AccountType.CREDIT_CARD,
        opening_balance=D("0"),
        opening_outstanding=D("0"),
        credit_limit=D("10000"),
        billing_day=15,
        due_day=25,
    )
    db.add(account)
    db.flush()
    return account


def add_bank(db: Session, name: str = "Bank") -> Account:
    account = Account(
        name=name,
        account_type=AccountType.BANK,
        opening_balance=D("10000"),
        opening_outstanding=D("0"),
    )
    db.add(account)
    db.flush()
    return account


def add_category(db: Session, name: str = "EMI") -> Category:
    category = Category(name=name)
    db.add(category)
    db.flush()
    return category


def add_plan(
    db: Session,
    account: Account,
    category: Category,
    monthly_installment: str = "850",
    remaining_amount_at_setup: str = "2500",
    setup_state: EMISetupCurrentMonthState = EMISetupCurrentMonthState.NOT_POSTED,
    tracking_start_month: date = date(2026, 7, 1),
    due_day: int = 12,
    is_active: bool = True,
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
        is_active=is_active,
    )
    db.add(plan)
    db.flush()
    return plan


def add_emi_transaction(
    db: Session,
    plan: EMIPlan,
    account: Account,
    category: Category,
    amount: str = "850",
    occurred_at: datetime = at(),
    transaction_type: TransactionType = TransactionType.EXPENSE,
) -> Transaction:
    transaction = Transaction(
        transaction_type=transaction_type,
        amount=D(amount),
        source_account_id=account.id if transaction_type == TransactionType.EXPENSE else None,
        destination_account_id=account.id if transaction_type == TransactionType.INCOME else None,
        category_id=category.id,
        emi_plan_id=plan.id,
        merchant="Original merchant",
        description="Original description",
        occurred_at=occurred_at,
        created_at=occurred_at,
    )
    db.add(transaction)
    db.flush()
    return transaction


def create_card_api(client: TestClient, name: str = "Card") -> str:
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


def create_bank_api(client: TestClient, name: str = "Bank") -> str:
    response = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "bank", "opening_balance": "10000.00"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_category_api(client: TestClient, name: str = "EMI") -> str:
    response = client.post("/api/v1/categories", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_plan_api(client: TestClient, account_id: str, category_id: str, setup_state: str = "not_posted") -> dict[str, object]:
    response = client.post(
        "/api/v1/emi-plans",
        json={
            "name": "Tata Neu EMI",
            "account_id": account_id,
            "category_id": category_id,
            "monthly_installment": "850.00",
            "remaining_amount_at_setup": "2500.00",
            "due_day": 12,
            "setup_current_month_state": setup_state,
        },
    )
    assert response.status_code == 201
    return response.json()


def update_payload_from_api(plan: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = {
        "name": plan["name"],
        "account_id": plan["account_id"],
        "category_id": plan["category_id"],
        "monthly_installment": plan["monthly_installment"],
        "remaining_amount_at_setup": plan["remaining_amount_at_setup"],
        "due_day": plan["due_day"],
        "setup_current_month_state": plan["setup_current_month_state"],
        "is_active": plan["is_active"],
    }
    payload.update(overrides)
    return payload


def update_payload_from_model(plan: EMIPlan, **overrides: object) -> dict[str, object]:
    payload = {
        "name": plan.name,
        "account_id": str(plan.account_id),
        "category_id": str(plan.category_id),
        "monthly_installment": f"{D(plan.monthly_installment):.2f}",
        "remaining_amount_at_setup": f"{D(plan.remaining_amount_at_setup):.2f}",
        "due_day": plan.due_day,
        "setup_current_month_state": plan.setup_current_month_state.value,
        "is_active": plan.is_active,
    }
    payload.update(overrides)
    return payload


def update_plan_in_session(db: Session, plan: EMIPlan, **overrides: object) -> dict[str, object]:
    with api_client_for_session(db) as client:
        response = client.put(f"/api/v1/emi-plans/{plan.id}", json=update_payload_from_model(plan, **overrides))
    assert response.status_code == 200
    db.refresh(plan)
    return response.json()


def post_emi_expense(client: TestClient, card_id: str, category_id: str, plan_id: str, amount: str = "850.00"):
    return client.post(
        "/api/v1/transactions",
        json={
            "transaction_type": "expense",
            "amount": amount,
            "source_account_id": card_id,
            "category_id": category_id,
            "emi_plan_id": plan_id,
            "occurred_at": "2026-07-08T12:00:00+05:30",
        },
    )


def test_emi_update_changes_name(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, name="Phone EMI"))

    assert response.status_code == 200
    assert response.json()["name"] == "Phone EMI"


def test_emi_update_changes_due_day(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, due_day=15))

    assert response.status_code == 200
    assert response.json()["due_day"] == 15


def test_emi_update_deactivates_plan(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, is_active=False))

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_emi_update_reactivates_plan(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)
    inactive = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, is_active=False)).json()

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(inactive, is_active=True))

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_unknown_emi_plan_update_returns_404(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{uuid4()}", json=update_payload_from_api(plan))

    assert response.status_code == 404
    assert response.json()["detail"] == "EMI plan not found"


def test_emi_update_rejects_non_credit_card_account(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    bank = create_bank_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, account_id=bank))

    assert response.status_code == 422
    assert response.json()["detail"] == "EMI plans must use a credit-card account"


def test_emi_update_rejects_unknown_account(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, account_id=str(uuid4())))

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_emi_update_rejects_unknown_category(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, category_id=str(uuid4())))

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


def test_emi_update_rejects_invalid_monthly_installment(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, monthly_installment="0.00"))

    assert response.status_code == 422


def test_emi_update_rejects_invalid_remaining_amount(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, remaining_amount_at_setup="0.00"))

    assert response.status_code == 422


def test_emi_update_rejects_invalid_due_day(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, due_day=29))

    assert response.status_code == 422


def test_tracking_start_month_cannot_be_updated(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)
    payload = update_payload_from_api(plan, tracking_start_month="2026-08-01")

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=payload)

    assert response.status_code == 422
    assert "tracking_start_month" in str(response.json()["detail"])


def test_extra_emi_update_fields_are_forbidden(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)
    payload = update_payload_from_api(plan, financial_configuration_locked=False)

    response = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=payload)

    assert response.status_code == 422
    assert "financial_configuration_locked" in str(response.json()["detail"])


def test_tracking_month_without_history_is_financially_unlocked(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)

    response = api_client.get(f"/api/v1/emi-plans/{plan['id']}")

    assert response.status_code == 200
    assert response.json()["financial_configuration_locked"] is False
    assert response.json()["financial_configuration_lock_reason"] is None


def test_emi_plan_locks_after_any_linked_transaction_exists(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)
    add_emi_transaction(db_session, plan, card, category, transaction_type=TransactionType.INCOME)

    service = EMIService(db_session)

    assert service.is_financial_configuration_locked(plan) is True
    assert service.financial_configuration_lock_reason(plan) == "Installment history has already been recorded."


def test_emi_plan_locks_after_tracking_month_passes_without_history(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category, tracking_start_month=date(2026, 7, 1))

    service = EMIService(db_session)

    assert service.is_financial_configuration_locked(plan) is True
    assert service.financial_configuration_lock_reason(plan) == "The EMI tracking month has passed."


def test_locked_plan_allows_name_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, name="Phone EMI")

    assert response["name"] == "Phone EMI"


def test_locked_plan_allows_due_day_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category, due_day=12)

    response = update_plan_in_session(db_session, plan, due_day=15)

    assert response["due_day"] == 15


def test_locked_plan_allows_deactivation(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, is_active=False)

    assert response["is_active"] is False


def test_locked_plan_rejects_account_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session, "Card")
    other_card = add_card(db_session, "Other Card")
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    with api_client_for_session(db_session) as client:
        response = client.put(f"/api/v1/emi-plans/{plan.id}", json=update_payload_from_model(plan, account_id=str(other_card.id)))

    assert response.status_code == 422
    assert response.json()["detail"] == LOCKED_ERROR


def test_locked_plan_rejects_category_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session, "EMI")
    other_category = add_category(db_session, "Phone")
    plan = add_plan(db_session, card, category)

    with api_client_for_session(db_session) as client:
        response = client.put(f"/api/v1/emi-plans/{plan.id}", json=update_payload_from_model(plan, category_id=str(other_category.id)))

    assert response.status_code == 422
    assert response.json()["detail"] == LOCKED_ERROR


def test_locked_plan_rejects_monthly_installment_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    with api_client_for_session(db_session) as client:
        response = client.put(f"/api/v1/emi-plans/{plan.id}", json=update_payload_from_model(plan, monthly_installment="825.00"))

    assert response.status_code == 422
    assert response.json()["detail"] == LOCKED_ERROR


def test_locked_plan_rejects_remaining_amount_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    with api_client_for_session(db_session) as client:
        response = client.put(f"/api/v1/emi-plans/{plan.id}", json=update_payload_from_model(plan, remaining_amount_at_setup="2400.00"))

    assert response.status_code == 422
    assert response.json()["detail"] == LOCKED_ERROR


def test_locked_plan_rejects_setup_state_change(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    with api_client_for_session(db_session) as client:
        response = client.put(
            f"/api/v1/emi-plans/{plan.id}",
            json=update_payload_from_model(plan, setup_current_month_state="included_in_opening_liability"),
        )

    assert response.status_code == 422
    assert response.json()["detail"] == LOCKED_ERROR


def test_locked_complete_put_with_unchanged_protected_fields_succeeds(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, name="Phone EMI")

    assert response["name"] == "Phone EMI"
    assert response["monthly_installment"] == "850.00"


def test_rejected_locked_edit_does_not_partially_mutate_plan(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category, due_day=12)

    with api_client_for_session(db_session) as client:
        response = client.put(
            f"/api/v1/emi-plans/{plan.id}",
            json=update_payload_from_model(plan, name="Phone EMI", due_day=15, monthly_installment="825.00"),
        )
    db_session.refresh(plan)

    assert response.status_code == 422
    assert plan.name == "Tata Neu EMI"
    assert plan.due_day == 12
    assert plan.monthly_installment == D("850.00")


def test_unlocked_plan_allows_account_correction_to_another_credit_card(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session, "Card")
    other_card = add_card(db_session, "Other Card")
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, account_id=str(other_card.id))

    assert response["account_id"] == str(other_card.id)


def test_unlocked_plan_allows_category_correction(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session, "Wrong")
    corrected = add_category(db_session, "EMI")
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, category_id=str(corrected.id))

    assert response["category_id"] == str(corrected.id)


def test_unlocked_plan_allows_monthly_installment_correction(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, monthly_installment="825.00")

    assert response["monthly_installment"] == "825.00"


def test_unlocked_plan_allows_remaining_amount_correction(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, remaining_amount_at_setup="2400.00")

    assert response["remaining_amount_at_setup"] == "2400.00"


def test_unlocked_plan_allows_setup_state_correction(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    response = update_plan_in_session(db_session, plan, setup_current_month_state="included_in_opening_liability")

    assert response["setup_current_month_state"] == "included_in_opening_liability"


def test_unlocked_not_posted_to_opening_liability_removes_current_emi_reserve(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category, setup_state=EMISetupCurrentMonthState.NOT_POSTED)

    assert SafeToSpendService(db_session).summary(JULY_AS_OF)["remaining_emi_installments"] == D("850.00")
    update_plan_in_session(db_session, plan, setup_current_month_state="included_in_opening_liability")

    assert SafeToSpendService(db_session).summary(JULY_AS_OF)["remaining_emi_installments"] == D("0")


def test_existing_transactions_are_not_mutated_by_plan_editing(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)
    transaction = add_emi_transaction(db_session, plan, card, category)

    update_plan_in_session(db_session, plan, name="Phone EMI")
    db_session.refresh(transaction)

    assert transaction.source_account_id == card.id
    assert transaction.category_id == category.id
    assert transaction.amount == D("850.00")
    assert transaction.occurred_at == at()
    assert transaction.merchant == "Original merchant"
    assert transaction.description == "Original description"


def test_existing_emi_plan_links_remain_unchanged_after_plan_editing(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)
    transaction = add_emi_transaction(db_session, plan, card, category)

    update_plan_in_session(db_session, plan, due_day=15)
    db_session.refresh(transaction)

    assert transaction.emi_plan_id == plan.id


def test_inactive_emi_plan_is_excluded_from_remaining_emi_installments(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category)

    update_plan_in_session(db_session, plan, is_active=False)
    status = EMIService(db_session).list_statuses(JULY_AS_OF)[0]
    summary = SafeToSpendService(db_session).summary(JULY_AS_OF)

    assert status["current_month_reserve"] == D("0")
    assert summary["remaining_emi_installments"] == D("0")


def test_inactive_emi_plan_cannot_record_installment(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)
    inactive = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, is_active=False))
    assert inactive.status_code == 200

    response = post_emi_expense(api_client, card, category, str(plan["id"]))

    assert response.status_code == 422
    assert response.json()["detail"] == "Inactive EMI plans cannot record new installments"


def test_reactivating_emi_plan_preserves_chronological_installment_history(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category, remaining_amount_at_setup="2500")
    add_emi_transaction(db_session, plan, card, category, occurred_at=at(2026, 7, 8))

    update_plan_in_session(db_session, plan, is_active=False)
    update_plan_in_session(db_session, plan, is_active=True)
    status = EMIService(db_session).list_statuses(date(2026, 9, 5))[0]

    assert status["installment_month"] == date(2026, 8, 1)
    assert status["current_month_status"] == "overdue"
    assert status["current_month_reserve"] == D("850.00")


def test_due_day_correction_changes_derived_due_date(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 8, 8, 8))
    card = add_card(db_session)
    category = add_category(db_session)
    plan = add_plan(db_session, card, category, due_day=12)

    update_plan_in_session(db_session, plan, due_day=15)
    status = EMIService(db_session).list_statuses(AUGUST_AS_OF)[0]

    assert status["due_date"] == date(2026, 7, 15)


def test_explicit_emi_status_as_of_remains_deterministic(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: at(2026, 7, 8, 8))
    card = create_card_api(api_client)
    category = create_category_api(api_client)
    plan = create_plan_api(api_client, card, category)
    update = api_client.put(f"/api/v1/emi-plans/{plan['id']}", json=update_payload_from_api(plan, due_day=15))
    assert update.status_code == 200

    first = api_client.get("/api/v1/emi-plans/status?as_of=2026-07-15")
    second = api_client.get("/api/v1/emi-plans/status?as_of=2026-07-15")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.json()[0]["current_month_status"] == "due_today"
    assert first.json()[0]["due_date"] == "2026-07-15"