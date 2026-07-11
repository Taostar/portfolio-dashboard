"""Endpoint tests for GET /market/vix — load_vix_data is mocked (I/O boundary)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_vix_returns_payload():
    payload = {
        "dates": ["2025-01-01", "2025-01-02"],
        "close_prices": [15.0, 22.5],
        "current": 22.5,
        "zone": "Elevated Fear",
    }
    with patch("app.api.v1.endpoints.market.load_vix_data", return_value=payload):
        response = client.get("/api/v1/market/vix")

    assert response.status_code == 200
    assert response.json() == payload


def test_get_vix_returns_503_when_unavailable():
    with patch("app.api.v1.endpoints.market.load_vix_data", return_value=None):
        response = client.get("/api/v1/market/vix")

    assert response.status_code == 503
