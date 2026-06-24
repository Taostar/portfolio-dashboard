"""Endpoint wiring tests for /api/v1/mcp and /api/v1/mcp/functions, with the
handler's internals mocked (no real broker calls)."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_mcp_functions_returns_function_definitions():
    response = client.get("/api/v1/mcp/functions")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 4
    assert {fn["name"] for fn in body} == {
        "get_accounts",
        "get_account_holdings",
        "get_all_holdings",
        "get_market_data",
    }


def test_post_mcp_routes_to_handler():
    fake_response = {
        "type": "function_result",
        "function": "get_accounts",
        "result": [{"number": "123"}],
        "status": "success",
        "error": None,
        "conversation_id": None,
    }
    with patch(
        "app.api.v1.endpoints.mcp._handler.process_request",
        new=AsyncMock(return_value=fake_response),
    ) as mock_process:
        response = client.post("/api/v1/mcp", json={"function": "get_accounts", "arguments": {}})

    assert response.status_code == 200
    assert response.json() == fake_response
    mock_process.assert_awaited_once()
