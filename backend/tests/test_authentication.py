from fastapi.testclient import TestClient


def test_api_rejects_missing_token(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/accounts", headers={"Authorization": ""})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API token"


def test_api_rejects_wrong_token(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/accounts", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401


def test_api_accepts_configured_token(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/accounts")

    assert response.status_code == 200


def test_health_check_remains_public(api_client: TestClient) -> None:
    response = api_client.get("/health", headers={"Authorization": ""})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
