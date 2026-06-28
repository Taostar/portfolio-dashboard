"""Tests for MCPHandler: dispatch/error-wrapping logic (mocked _get_* methods)
and the 4 rewired _get_* methods (mocked at the _questrade_internal /
QuestradeProvider import boundary used by app.mcp.handler)."""

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.mcp.handler import MCPHandler


# ---------------------------------------------------------------------------
# process_request() routing/error paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_request_invalid_json_string():
    handler = MCPHandler()
    response = await handler.process_request("not valid json{")
    assert response["status"] == "error"
    assert "invalid_request" in response["error"]


@pytest.mark.asyncio
async def test_process_request_unknown_function():
    handler = MCPHandler()
    response = await handler.process_request({"function": "not_a_real_function", "arguments": {}})
    assert response["status"] == "error"
    assert "unknown_function" in response["error"]
    assert response["function"] == "not_a_real_function"


@pytest.mark.asyncio
async def test_process_request_function_raises_returns_execution_error():
    handler = MCPHandler()
    handler._get_accounts = AsyncMock(side_effect=RuntimeError("boom"))
    handler.function_map["get_accounts"] = handler._get_accounts

    response = await handler.process_request({"function": "get_accounts", "arguments": {}})

    assert response["status"] == "error"
    assert "execution_error" in response["error"]
    assert "boom" in response["error"]


@pytest.mark.asyncio
async def test_process_request_success_path():
    handler = MCPHandler()
    handler._get_accounts = AsyncMock(return_value=[{"number": "123"}])
    handler.function_map["get_accounts"] = handler._get_accounts

    response = await handler.process_request({"function": "get_accounts", "arguments": {}})

    assert response["status"] == "success"
    assert response["result"] == [{"number": "123"}]
    assert response["function"] == "get_accounts"


# ---------------------------------------------------------------------------
# _get_accounts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_accounts_dedups_across_clients():
    """qtrade's Questrade client exposes get_account_id() (a plain list of
    account ID strings/ints), not a get_accounts() method — confirmed live,
    where a get_accounts() call raised AttributeError and the handler's
    except-and-warn fallback silently returned []. _get_accounts must go
    through the already-correct app.providers._questrade_internal.holdings
    .get_account_list() helper, which wraps get_account_id() into the right
    dict shape."""
    client_a = type("C", (), {"get_account_id": lambda self: ["1", "2"]})()
    client_b = type("C", (), {"get_account_id": lambda self: ["2", "3"]})()

    with patch("app.mcp.handler.get_questrade_clients", return_value=[client_a, client_b]):
        handler = MCPHandler()
        result = await handler._get_accounts({})

    numbers = [acc["number"] for acc in result]
    assert numbers == ["1", "2", "3"]


# ---------------------------------------------------------------------------
# _get_account_holdings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_account_holdings_finds_owning_client():
    client_a = type("C", (), {"get_account_id": lambda self: [111]})()
    client_b = type("C", (), {"get_account_id": lambda self: [222]})()

    fake_positions = {
        "account_id": "222",
        "account_name": "Margin",
        "account_type": "Individual",
        "holdings": [{"symbol": "AAPL"}],
    }

    with patch("app.mcp.handler.get_questrade_clients", return_value=[client_a, client_b]), \
         patch("app.mcp.handler.get_account_positions", return_value=fake_positions) as mock_positions:
        handler = MCPHandler()
        result = await handler._get_account_holdings({"account_id": "222"})

    mock_positions.assert_called_once_with(client_b, "222")
    assert result == fake_positions


@pytest.mark.asyncio
async def test_get_account_holdings_raises_when_not_found():
    client_a = type("C", (), {"get_account_id": lambda self: [111]})()

    with patch("app.mcp.handler.get_questrade_clients", return_value=[client_a]):
        handler = MCPHandler()
        with pytest.raises(ValueError):
            await handler._get_account_holdings({"account_id": "999"})


# ---------------------------------------------------------------------------
# _get_all_holdings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_holdings_returns_flat_per_account_list():
    fake_all_positions = [
        {"account_id": "111", "account_name": "RRSP", "account_type": "Individual", "holdings": [{"symbol": "AAPL"}]},
        {"account_id": "222", "account_name": "Margin", "account_type": "Individual", "holdings": [{"symbol": "MSFT"}]},
    ]

    with patch("app.mcp.handler.get_questrade_clients", return_value=["client-a"]), \
         patch("app.mcp.handler.get_all_account_positions_multi", return_value=fake_all_positions):
        handler = MCPHandler()
        result = await handler._get_all_holdings({})

    assert result == fake_all_positions


# ---------------------------------------------------------------------------
# _get_market_data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_market_data_builds_metrics_and_candles():
    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "date": "2024-01-01", "open": 100, "high": 101, "low": 99, "close": 100.0, "volume": 1000},
            {"symbol": "AAPL", "date": "2024-01-02", "open": 100, "high": 102, "low": 99, "close": 102.0, "volume": 1100},
            {"symbol": "AAPL", "date": "2024-01-03", "open": 102, "high": 105, "low": 101, "close": 104.0, "volume": 1200},
        ]
    )

    with patch("app.mcp.handler.QuestradeProvider") as MockProvider:
        instance = MockProvider.return_value
        instance.get_market_data = AsyncMock(return_value=df)

        handler = MCPHandler()
        result = await handler._get_market_data({"symbol": "AAPL", "days": 30, "interval": "OneDay"})

    instance.get_market_data.assert_awaited_once_with(["AAPL"], days=30, interval="OneDay")

    assert result["symbol"] == "AAPL"
    assert result["name"] == ""
    assert len(result["candles"]) == 3
    assert result["candles"][0]["date"] == "2024-01-01"
    assert result["candles"][0]["close"] == 100.0

    metrics = result["metrics"]
    # Sorted descending by date: latest=104.0 (1/3), then 102.0 (1/2), then 100.0 (1/1)
    assert metrics["performance_1d"] == pytest.approx((104.0 - 102.0) / 102.0 * 100)
    # Only 3 candles available, so week_index = min(5, 2) = 2 -> compares against oldest (100.0)
    assert metrics["performance_1w"] == pytest.approx((104.0 - 100.0) / 100.0 * 100)
    assert metrics["performance_1m"] == pytest.approx((104.0 - 100.0) / 100.0 * 100)
    assert metrics["average_volume"] == pytest.approx((1000 + 1100 + 1200) / 3)


@pytest.mark.asyncio
async def test_get_market_data_requires_symbol_argument():
    handler = MCPHandler()
    with pytest.raises(ValueError):
        await handler._get_market_data({})
