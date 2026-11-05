"""The API key protects /api/ routes in production, while /health and /docs stay open."""
import pytest
from fastapi.testclient import TestClient

import main

GOOD = {"amount_usd": 1500, "term_months": 12, "monthly_income_usd": 350.0, "previous_loans": 1, "late_payments": 0}


@pytest.fixture
def secured_client(monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "test-key")  # as if API_KEY were set in Render
    with TestClient(main.app) as c:
        yield c


def test_api_route_without_key_is_401(secured_client):
    response = secured_client.post("/api/v1/predictions", json=GOOD)
    assert response.status_code == 401
    assert response.json() == {"detail": "Missing or invalid API key"}


def test_api_route_with_wrong_key_is_401(secured_client):
    response = secured_client.get("/api/v1/applications", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_api_route_with_key_is_allowed(secured_client):
    response = secured_client.post("/api/v1/predictions", json=GOOD, headers={"X-API-Key": "test-key"})
    assert response.status_code == 200


def test_health_and_docs_stay_open(secured_client):
    assert secured_client.get("/health").status_code == 200  # Render's health check has no key
    assert secured_client.get("/docs").status_code == 200
