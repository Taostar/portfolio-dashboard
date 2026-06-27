"""Tests for app/services/holdings_service.py.

holdings_service is now unconditionally backed by QuestradeProvider — the
legacy external_api.py path and its feature flag have been removed.
Tests verify that the service correctly delegates to _provider and that
caching is preserved.
"""

import pandas as pd
import pytest

from app.services import holdings_service


FAKE_HOLDINGS = [{"symbol": "AAPL", "current_market_value_CAD": 1000.0}]
FAKE_METRICS = {"Total Market Value (CAD)": 1000.0, "Symbols": ["AAPL"]}

FAKE_PERFORMANCE_DF = pd.DataFrame(
    [
        {"symbol": "AAPL", "date": "2024-01-01", "open": 1, "high": 1, "low": 1, "close": 100.0, "volume": 10},
    ]
)


def _clear_caches():
    from app.core.cache import clear_cache
    clear_cache("holdings")
    clear_cache("performance")


@pytest.fixture(autouse=True)
def clear_caches_around_test():
    _clear_caches()
    yield
    _clear_caches()


# ---------------------------------------------------------------------------
# 1. fetch_portfolio_data delegates to QuestradeProvider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_portfolio_data_delegates_to_provider(monkeypatch):
    async def fake_get_holdings():
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service._provider, "get_holdings", fake_get_holdings)

    holdings, metrics = await holdings_service.fetch_portfolio_data()

    assert holdings == FAKE_HOLDINGS
    assert metrics == FAKE_METRICS


@pytest.mark.asyncio
async def test_load_performance_delegates_to_provider(monkeypatch):
    async def fake_fetch_portfolio_data():
        return [{"symbol": "AAPL"}], {"Symbols": ["AAPL"]}

    captured = {}

    async def fake_get_market_data(symbols, days=365):
        captured["symbols"] = symbols
        return FAKE_PERFORMANCE_DF

    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch_portfolio_data)
    monkeypatch.setattr(holdings_service._provider, "get_market_data", fake_get_market_data)

    df = await holdings_service.load_performance()

    pd.testing.assert_frame_equal(df, FAKE_PERFORMANCE_DF)
    assert captured["symbols"] == ["AAPL"]


# ---------------------------------------------------------------------------
# 2. get_holdings_dataframe / get_portfolio_metrics build on fetch_portfolio_data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_holdings_dataframe_wraps_holdings_list(monkeypatch):
    async def fake_fetch():
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch)

    df = await holdings_service.get_holdings_dataframe()

    pd.testing.assert_frame_equal(df, pd.DataFrame(FAKE_HOLDINGS))


@pytest.mark.asyncio
async def test_get_portfolio_metrics_returns_metrics(monkeypatch):
    async def fake_fetch():
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch)

    metrics = await holdings_service.get_portfolio_metrics()

    assert metrics == FAKE_METRICS


@pytest.mark.asyncio
async def test_get_holdings_dataframe_handles_none():
    async def fake_fetch():
        return None, None

    import app.services.holdings_service as hs
    original = hs.fetch_portfolio_data
    hs.fetch_portfolio_data = fake_fetch
    try:
        df = await hs.get_holdings_dataframe()
        assert df.empty
    finally:
        hs.fetch_portfolio_data = original


# ---------------------------------------------------------------------------
# 3. Caching is preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_portfolio_data_is_cached(monkeypatch):
    call_count = {"n": 0}

    async def fake_get_holdings():
        call_count["n"] += 1
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service._provider, "get_holdings", fake_get_holdings)

    await holdings_service.fetch_portfolio_data()
    await holdings_service.fetch_portfolio_data()

    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_load_performance_is_cached(monkeypatch):
    call_count = {"n": 0}

    async def fake_fetch_portfolio_data():
        return [{"symbol": "AAPL"}], {}

    async def fake_get_market_data(symbols, days=365):
        call_count["n"] += 1
        return FAKE_PERFORMANCE_DF

    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch_portfolio_data)
    monkeypatch.setattr(holdings_service._provider, "get_market_data", fake_get_market_data)

    await holdings_service.load_performance()
    await holdings_service.load_performance()

    assert call_count["n"] == 1


def test_fetch_portfolio_data_has_holdings_cache_decorator():
    assert hasattr(holdings_service.fetch_portfolio_data, "__wrapped__")


def test_load_performance_has_performance_cache_decorator():
    assert hasattr(holdings_service.load_performance, "__wrapped__")


# ---------------------------------------------------------------------------
# 4. Endpoint imports
# ---------------------------------------------------------------------------

def test_endpoint_modules_import_cleanly_from_holdings_service():
    import importlib

    modules = [
        "app.api.v1.endpoints.benchmark",
        "app.api.v1.endpoints.correlation",
        "app.api.v1.endpoints.holdings",
        "app.api.v1.endpoints.performance",
        "app.api.v1.endpoints.portfolio",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        importlib.reload(mod)
