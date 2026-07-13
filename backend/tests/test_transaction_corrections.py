from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.services import date_utils


def create_category(client: TestClient, name: str = "Food") -> str:
    response = client.post("/api/v1/categories", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_bank(client: TestClient, name: str = "Bank", opening_balance: str = "1000.00") -> str:
    response = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "bank", "opening_balance": opening_balance},
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
            "credit_limit": "5000.00",
            "billing_day": 15,
            "due_day": 25,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_expense(
    client: TestClient,
    account_id: str,
    category_id: str,
    amount: str = "100.00",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "transaction_type": "expense",
        "amount": amount,
        "source_account_id": account_id,
        "category_id": category_id,
        "occurred_at": "2026-07-13T12:00:00+05:30",
    }
    payload.update(overrides)
    response = client.post("/api/v1/transactions", json=payload)
    assert response.status_code == 201
    return response.json()


def update_payload(transaction: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = {
        "transaction_type": transaction["transaction_type"],
        "amount": transaction["amount"],
        "source_account_id": transaction["source_account_id"],
        "destination_account_id": transaction["destination_account_id"],
        "category_id": transaction["category_id"],
        "recurring_commitment_id": transaction["recurring_commitment_id"],
        "emi_plan_id": transaction["emi_plan_id"],
        "merchant": transaction["merchant"],
        "description": transaction["description"],
        "occurred_at": transaction["occurred_at"],
    }
    payload.update(overrides)
    return payload


def test_transaction_update_recalculates_balances(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client)
    transaction = create_expense(api_client, bank, category)

    before = api_client.get("/api/v1/dashboard/summary?as_of=2026-07-13")
    assert before.status_code == 200
    assert before.json()["liquid_cash"] == "900.00"

    response = api_client.put(
        f"/api/v1/transactions/{transaction['id']}",
        json=update_payload(transaction, amount="250.00", merchant="Corrected merchant"),
    )

    assert response.status_code == 200
    corrected = response.json()
    assert corrected["amount"] == "250.00"
    assert corrected["merchant"] == "Corrected merchant"
    assert corrected["voided_at"] is None
    assert corrected["updated_at"] >= corrected["created_at"]

    after = api_client.get("/api/v1/dashboard/summary?as_of=2026-07-13")
    assert after.status_code == 200
    assert after.json()["liquid_cash"] == "750.00"


def test_rejected_update_preserves_original_transaction(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    card = create_card(api_client)
    category = create_category(api_client)
    transaction = create_expense(api_client, bank, category)

    response = api_client.put(
        f"/api/v1/transactions/{transaction['id']}",
        json={
            "transaction_type": "income",
            "amount": "500.00",
            "destination_account_id": card,
            "occurred_at": transaction["occurred_at"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Income transactions cannot use a credit-card destination account"

    listed = api_client.get("/api/v1/transactions")
    assert listed.status_code == 200
    assert listed.json()[0]["transaction_type"] == "expense"
    assert listed.json()[0]["amount"] == "100.00"
    assert listed.json()[0]["voided_at"] is None


def test_void_is_idempotent_and_auditable(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client)
    transaction = create_expense(api_client, bank, category)

    first = api_client.delete(f"/api/v1/transactions/{transaction['id']}")
    second = api_client.delete(f"/api/v1/transactions/{transaction['id']}")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["voided_at"] is not None
    assert second.json()["voided_at"] == first.json()["voided_at"]
    assert api_client.get("/api/v1/transactions").json() == []

    audit_history = api_client.get("/api/v1/transactions?include_voided=true")
    assert audit_history.status_code == 200
    assert len(audit_history.json()) == 1
    assert audit_history.json()[0]["voided_at"] == first.json()["voided_at"]

    summary = api_client.get("/api/v1/dashboard/summary?as_of=2026-07-13")
    assert summary.status_code == 200
    assert summary.json()["liquid_cash"] == "1000.00"

    edit = api_client.put(
        f"/api/v1/transactions/{transaction['id']}",
        json=update_payload(transaction, amount="10.00"),
    )
    assert edit.status_code == 409
    assert edit.json()["detail"] == "Voided transactions cannot be edited"


def test_voided_commitment_payment_restores_obligation(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client, "Housing")
    commitment_response = api_client.post(
        "/api/v1/commitments",
        json={
            "name": "Rent",
            "amount": "250.00",
            "category_id": category,
            "account_id": bank,
            "commitment_type": "fixed_expense",
            "due_day": 20,
        },
    )
    assert commitment_response.status_code == 201
    commitment = commitment_response.json()["id"]
    payment = create_expense(
        api_client,
        bank,
        category,
        amount="250.00",
        recurring_commitment_id=commitment,
    )

    paid = api_client.get("/api/v1/commitments/status?as_of=2026-07-13")
    assert paid.status_code == 200
    assert paid.json()[0]["status"] == "paid"

    voided = api_client.delete(f"/api/v1/transactions/{payment['id']}")
    assert voided.status_code == 200

    restored = api_client.get("/api/v1/commitments/status?as_of=2026-07-13")
    assert restored.status_code == 200
    assert restored.json()[0]["status"] == "upcoming"
    assert restored.json()[0]["remaining_amount_this_month"] == "250.00"


def test_voided_investment_and_card_expense_are_ignored(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    card = create_card(api_client)
    investment_category = create_category(api_client, "Investment")
    expense_category = create_category(api_client, "Shopping")
    profile = api_client.put(
        "/api/v1/financial-profile",
        json={"monthly_savings_target": "500.00", "salary_day": 28},
    )
    assert profile.status_code == 200

    investment_response = api_client.post(
        "/api/v1/transactions",
        json={
            "transaction_type": "investment",
            "amount": "200.00",
            "source_account_id": bank,
            "category_id": investment_category,
            "occurred_at": "2026-07-13T12:00:00+05:30",
        },
    )
    assert investment_response.status_code == 201
    investment = investment_response.json()

    card_expense = create_expense(api_client, card, expense_category, amount="100.00")

    before = api_client.get("/api/v1/dashboard/summary?as_of=2026-07-13").json()
    exposure_before = api_client.get("/api/v1/cards/exposure?as_of=2026-07-13").json()[0]
    assert before["savings_completed_this_month"] == "200.00"
    assert exposure_before["outstanding"] == "100.00"
    assert exposure_before["current_cycle_spend"] == "100.00"

    assert api_client.delete(f"/api/v1/transactions/{investment['id']}").status_code == 200
    assert api_client.delete(f"/api/v1/transactions/{card_expense['id']}").status_code == 200

    after = api_client.get("/api/v1/dashboard/summary?as_of=2026-07-13").json()
    exposure_after = api_client.get("/api/v1/cards/exposure?as_of=2026-07-13").json()[0]
    assert Decimal(after["liquid_cash"]) == Decimal("1000.00")
    assert Decimal(after["savings_completed_this_month"]) == Decimal("0.00")
    assert Decimal(after["remaining_savings_target"]) == Decimal("500.00")
    assert Decimal(exposure_after["outstanding"]) == Decimal("0.00")
    assert Decimal(exposure_after["current_cycle_spend"]) == Decimal("0.00")


def test_emi_corrections_preserve_month_chronology(api_client: TestClient, monkeypatch: object) -> None:
    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 7, 13, 18, 0, 0))
    card = create_card(api_client)
    category = create_category(api_client, "EMI")
    plan_response = api_client.post(
        "/api/v1/emi-plans",
        json={
            "name": "Phone EMI",
            "account_id": card,
            "category_id": category,
            "monthly_installment": "850.00",
            "remaining_amount_at_setup": "1700.00",
            "due_day": 12,
            "setup_current_month_state": "not_posted",
        },
    )
    assert plan_response.status_code == 201
    plan = plan_response.json()["id"]

    july = create_expense(
        api_client,
        card,
        category,
        amount="850.00",
        emi_plan_id=plan,
    )
    corrected = api_client.put(
        f"/api/v1/transactions/{july['id']}",
        json=update_payload(july, merchant="Phone lender"),
    )
    assert corrected.status_code == 200
    assert corrected.json()["merchant"] == "Phone lender"

    monkeypatch.setattr(date_utils, "utc_now_naive", lambda: datetime(2026, 8, 13, 18, 0, 0))
    august = create_expense(
        api_client,
        card,
        category,
        amount="850.00",
        emi_plan_id=plan,
        occurred_at="2026-08-13T12:00:00+05:30",
    )

    older_metadata_edit = api_client.put(
        f"/api/v1/transactions/{july['id']}",
        json=update_payload(corrected.json(), description="Corrected after later installment"),
    )
    assert older_metadata_edit.status_code == 200

    blocked = api_client.delete(f"/api/v1/transactions/{july['id']}")
    assert blocked.status_code == 422
    assert blocked.json()["detail"] == (
        "Cannot move, unlink, or void an EMI installment while a later installment exists"
    )

    latest_void = api_client.delete(f"/api/v1/transactions/{august['id']}")
    assert latest_void.status_code == 200

    status = api_client.get("/api/v1/emi-plans/status?as_of=2026-08-13")
    assert status.status_code == 200
    assert status.json()[0]["installment_month"] == "2026-08-01"
    assert status.json()[0]["current_month_reserve"] == "850.00"

    earliest_void = api_client.delete(f"/api/v1/transactions/{july['id']}")
    assert earliest_void.status_code == 200