from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient


def create_category(client: TestClient, name: str = "Food") -> str:
    response = client.post("/api/v1/categories", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_bank(client: TestClient, name: str = "Bank") -> str:
    response = client.post(
        "/api/v1/accounts",
        json={
            "name": name,
            "account_type": "bank",
            "opening_balance": "1000.00",
        },
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


def create_commitment(
    client: TestClient,
    account_id: str,
    category_id: str,
    commitment_type: str = "fixed_expense",
) -> str:
    response = client.post(
        "/api/v1/commitments",
        json={
            "name": f"{commitment_type} commitment",
            "amount": "250.00",
            "category_id": category_id,
            "account_id": account_id,
            "commitment_type": commitment_type,
            "due_day": 10,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def post_transaction(client: TestClient, payload: dict[str, Any]) -> Any:
    return client.post("/api/v1/transactions", json=payload)


def expense_payload(source_account_id: str, category_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "transaction_type": "expense",
        "amount": "100.00",
        "source_account_id": source_account_id,
        "category_id": category_id,
    }
    payload.update(overrides)
    return payload


def investment_payload(source_account_id: str, category_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "transaction_type": "investment",
        "amount": "100.00",
        "source_account_id": source_account_id,
        "category_id": category_id,
    }
    payload.update(overrides)
    return payload


def transfer_payload(source_account_id: str, destination_account_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "transaction_type": "transfer",
        "amount": "100.00",
        "source_account_id": source_account_id,
        "destination_account_id": destination_account_id,
    }
    payload.update(overrides)
    return payload


def income_payload(destination_account_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "transaction_type": "income",
        "amount": "100.00",
        "destination_account_id": destination_account_id,
    }
    payload.update(overrides)
    return payload


def refund_payload(destination_account_id: str, **overrides: Any) -> dict[str, Any]:
    payload = {
        "transaction_type": "refund",
        "amount": "100.00",
        "destination_account_id": destination_account_id,
    }
    payload.update(overrides)
    return payload


def test_credit_card_source_transfer_is_rejected(api_client: TestClient) -> None:
    card = create_card(api_client)
    bank = create_bank(api_client)

    response = post_transaction(api_client, transfer_payload(card, bank))

    assert response.status_code == 422
    assert response.json()["detail"] == "Credit cards cannot be used as the source account for transfers"


def test_bank_to_credit_card_transfer_is_accepted(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    card = create_card(api_client)

    response = post_transaction(api_client, transfer_payload(bank, card))

    assert response.status_code == 201
    assert response.json()["destination_account_id"] == card


def test_bank_to_bank_transfer_is_accepted(api_client: TestClient) -> None:
    source = create_bank(api_client, "Source Bank")
    destination = create_bank(api_client, "Destination Bank")

    response = post_transaction(api_client, transfer_payload(source, destination))

    assert response.status_code == 201
    assert response.json()["source_account_id"] == source


def test_income_to_bank_is_accepted(api_client: TestClient) -> None:
    bank = create_bank(api_client)

    response = post_transaction(api_client, income_payload(bank))

    assert response.status_code == 201
    assert response.json()["destination_account_id"] == bank


def test_income_to_credit_card_is_rejected(api_client: TestClient) -> None:
    card = create_card(api_client)

    response = post_transaction(api_client, income_payload(card))

    assert response.status_code == 422
    assert response.json()["detail"] == "Income transactions cannot use a credit-card destination account"


def test_refund_to_credit_card_is_accepted(api_client: TestClient) -> None:
    card = create_card(api_client)

    response = post_transaction(api_client, refund_payload(card))

    assert response.status_code == 201
    assert response.json()["destination_account_id"] == card


def test_credit_card_expense_is_accepted(api_client: TestClient) -> None:
    card = create_card(api_client)
    category = create_category(api_client)

    response = post_transaction(api_client, expense_payload(card, category))

    assert response.status_code == 201
    assert response.json()["transaction_type"] == "expense"


def test_credit_card_investment_is_rejected(api_client: TestClient) -> None:
    card = create_card(api_client)
    category = create_category(api_client, "Investment")

    response = post_transaction(api_client, investment_payload(card, category))

    assert response.status_code == 422
    assert response.json()["detail"] == "Credit cards cannot be used as the source account for an investment"


def test_future_dated_transaction_is_rejected(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client)
    future = datetime.now(timezone.utc) + timedelta(days=1)

    response = post_transaction(api_client, expense_payload(bank, category, occurred_at=future.isoformat()))

    assert response.status_code == 422
    assert response.json()["detail"] == "Transactions cannot be future-dated"


def test_fixed_expense_commitment_linked_to_matching_expense_is_accepted(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client, "EMI")
    commitment = create_commitment(api_client, bank, category, "fixed_expense")

    response = post_transaction(api_client, expense_payload(bank, category, recurring_commitment_id=commitment))

    assert response.status_code == 201
    assert response.json()["recurring_commitment_id"] == commitment


def test_fixed_expense_commitment_linked_to_investment_is_rejected(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client, "EMI")
    commitment = create_commitment(api_client, bank, category, "fixed_expense")

    response = post_transaction(api_client, investment_payload(bank, category, recurring_commitment_id=commitment))

    assert response.status_code == 422
    assert response.json()["detail"] == "Fixed expense commitments can only be linked to expense transactions"


def test_investment_commitment_linked_to_matching_investment_is_accepted(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client, "Investment")
    commitment = create_commitment(api_client, bank, category, "investment")

    response = post_transaction(api_client, investment_payload(bank, category, recurring_commitment_id=commitment))

    assert response.status_code == 201
    assert response.json()["recurring_commitment_id"] == commitment


def test_investment_commitment_linked_to_expense_is_rejected(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client, "Investment")
    commitment = create_commitment(api_client, bank, category, "investment")

    response = post_transaction(api_client, expense_payload(bank, category, recurring_commitment_id=commitment))

    assert response.status_code == 422
    assert response.json()["detail"] == "Investment commitments can only be linked to investment transactions"


def test_commitment_category_mismatch_is_rejected(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    commitment_category = create_category(api_client, "EMI")
    transaction_category = create_category(api_client, "Food")
    commitment = create_commitment(api_client, bank, commitment_category, "fixed_expense")

    response = post_transaction(
        api_client,
        expense_payload(bank, transaction_category, recurring_commitment_id=commitment),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Linked transaction category_id must match the recurring commitment category_id"


def test_commitment_account_mismatch_is_rejected(api_client: TestClient) -> None:
    commitment_bank = create_bank(api_client, "Commitment Bank")
    transaction_bank = create_bank(api_client, "Transaction Bank")
    category = create_category(api_client, "EMI")
    commitment = create_commitment(api_client, commitment_bank, category, "fixed_expense")

    response = post_transaction(api_client, expense_payload(transaction_bank, category, recurring_commitment_id=commitment))

    assert response.status_code == 422
    assert response.json()["detail"] == "Linked transaction source_account_id must match the recurring commitment account_id"


def test_transfer_linked_to_commitment_is_rejected(api_client: TestClient) -> None:
    source = create_bank(api_client, "Source Bank")
    destination = create_bank(api_client, "Destination Bank")
    category = create_category(api_client, "EMI")
    commitment = create_commitment(api_client, source, category, "fixed_expense")

    response = post_transaction(api_client, transfer_payload(source, destination, recurring_commitment_id=commitment))

    assert response.status_code == 422
    assert response.json()["detail"] == "Transfers cannot be linked to recurring commitments"


def test_unknown_source_account_returns_404(api_client: TestClient) -> None:
    category = create_category(api_client)

    response = post_transaction(api_client, expense_payload(str(uuid4()), category))

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_unknown_destination_account_returns_404(api_client: TestClient) -> None:
    source = create_bank(api_client)

    response = post_transaction(api_client, transfer_payload(source, str(uuid4())))

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_unknown_category_returns_404(api_client: TestClient) -> None:
    bank = create_bank(api_client)

    response = post_transaction(api_client, expense_payload(bank, str(uuid4())))

    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


def test_unknown_recurring_commitment_returns_404(api_client: TestClient) -> None:
    bank = create_bank(api_client)
    category = create_category(api_client)

    response = post_transaction(api_client, expense_payload(bank, category, recurring_commitment_id=str(uuid4())))

    assert response.status_code == 404
    assert response.json()["detail"] == "Recurring commitment not found"
