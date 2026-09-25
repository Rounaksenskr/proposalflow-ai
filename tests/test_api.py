import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from proposal_bot.api.app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_submit_lead_validation_error():
    # Submit invalid payload missing required fields
    response = client.post("/api/leads/submit", json={"client_name": "Incomplete Client"})
    assert response.status_code == 422
    