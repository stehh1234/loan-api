"""The API must return the model's probability of DEFAULT, not some other number in [0, 1].

Added after the bad-release drill: `round(1 - probability, 3)` passed every older test,
because they only checked that the answer was between 0 and 1.
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main

SAFE = {"amount_usd": 1500, "term_months": 12, "monthly_income_usd": 350.0, "previous_loans": 1, "late_payments": 0}
RISKY = {"amount_usd": 4800, "term_months": 6, "monthly_income_usd": 250.0, "previous_loans": 0, "late_payments": 3}


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def model_default_probability(features):
    X = pd.DataFrame([features])[main.ml["features"]]
    return float(main.ml["model"].predict_proba(X)[0, 1])  # column 1 = probability of default


def test_prediction_equals_model_default_probability(client):
    body = client.post("/api/v1/predictions", json=SAFE).json()
    assert body["default_probability"] == round(model_default_probability(SAFE), 3)


def test_safe_applicant_scores_low_and_risky_scores_high(client):
    safe = client.post("/api/v1/predictions", json=SAFE).json()
    risky = client.post("/api/v1/predictions", json=RISKY).json()
    assert safe["default_probability"] < 0.2 and safe["risk_band"] == "low"
    assert risky["default_probability"] > 0.5 and risky["risk_band"] == "high"
