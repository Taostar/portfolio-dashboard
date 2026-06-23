"""Tests for app/services/holdings_service.py — the feature-flag routing layer
introduced in Task 4. These tests verify *routing*, not the internals of either
side: external_api's HTTP calls are mocked, and QuestradeProvider's methods are
mocked. No real network/Questrade calls happen here.
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
# 1. Flag off -> delegates to external_api
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_portfolio_data_flag_off_delegates_to_external_api(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", False)

    async def fake_fetch():
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service.external_api, "fetch_portfolio_data", fake_fetch)

    holdings, metrics = await holdings_service.fetch_portfolio_data()

    assert holdings == FAKE_HOLDINGS
    assert metrics == FAKE_METRICS


@pytest.mark.asyncio
async def test_load_performance_flag_off_delegates_to_external_api(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", False)

    async def fake_load_performance():
        return FAKE_PERFORMANCE_DF

    monkeypatch.setattr(holdings_service.external_api, "load_performance", fake_load_performance)

    df = await holdings_service.load_performance()

    pd.testing.assert_frame_equal(df, FAKE_PERFORMANCE_DF)


# ---------------------------------------------------------------------------
# 2. Flag on -> delegates to QuestradeProvider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_portfolio_data_flag_on_delegates_to_provider(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", True)

    provider_holdings = [{"symbol": "MSFT", "current_market_value_CAD": 5000.0}]
    provider_metrics = {"Total Market Value (CAD)": 5000.0, "Symbols": ["MSFT"]}

    async def fake_get_holdings():
        return provider_holdings, provider_metrics

    monkeypatch.setattr(holdings_service._provider, "get_holdings", fake_get_holdings)

    # Sanity: external_api must NOT be the source of truth here.
    async def boom():
        raise AssertionError("external_api.fetch_portfolio_data should not be called when flag is on")

    monkeypatch.setattr(holdings_service.external_api, "fetch_portfolio_data", boom)

    holdings, metrics = await holdings_service.fetch_portfolio_data()

    assert holdings == provider_holdings
    assert metrics == provider_metrics


@pytest.mark.asyncio
async def test_load_performance_flag_on_delegates_to_provider(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", True)

    provider_df = pd.DataFrame(
        [
            {"symbol": "MSFT", "date": "2024-01-01", "open": 2, "high": 2, "low": 2, "close": 200.0, "volume": 20},
        ]
    )

    async def fake_fetch_portfolio_data():
        return [{"symbol": "MSFT"}], {"Symbols": ["MSFT"]}

    captured = {}

    async def fake_get_market_data(symbols, days=365):
        captured["symbols"] = symbols
        captured["days"] = days
        return provider_df

    # fetch_portfolio_data is this module's own (routed) version, used to derive symbols.
    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch_portfolio_data)
    monkeypatch.setattr(holdings_service._provider, "get_market_data", fake_get_market_data)

    async def boom():
        raise AssertionError("external_api.load_performance should not be called when flag is on")

    monkeypatch.setattr(holdings_service.external_api, "load_performance", boom)

    df = await holdings_service.load_performance()

    pd.testing.assert_frame_equal(df, provider_df)
    assert captured["symbols"] == ["MSFT"]


# ---------------------------------------------------------------------------
# 3. get_holdings_dataframe / get_portfolio_metrics build on fetch_portfolio_data's routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_holdings_dataframe_and_metrics_flag_off(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", False)

    async def fake_fetch():
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch)

    df = await holdings_service.get_holdings_dataframe()
    metrics = await holdings_service.get_portfolio_metrics()

    pd.testing.assert_frame_equal(df, pd.DataFrame(FAKE_HOLDINGS))
    assert metrics == FAKE_METRICS


@pytest.mark.asyncio
async def test_get_holdings_dataframe_and_metrics_flag_on(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", True)

    provider_holdings = [{"symbol": "MSFT", "current_market_value_CAD": 5000.0}]
    provider_metrics = {"Total Market Value (CAD)": 5000.0}

    async def fake_fetch():
        return provider_holdings, provider_metrics

    monkeypatch.setattr(holdings_service, "fetch_portfolio_data", fake_fetch)

    df = await holdings_service.get_holdings_dataframe()
    metrics = await holdings_service.get_portfolio_metrics()

    pd.testing.assert_frame_equal(df, pd.DataFrame(provider_holdings))
    assert metrics == provider_metrics


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
# 4. Caching is preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_portfolio_data_is_cached(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", False)

    call_count = {"n": 0}

    async def fake_fetch():
        call_count["n"] += 1
        return FAKE_HOLDINGS, FAKE_METRICS

    monkeypatch.setattr(holdings_service.external_api, "fetch_portfolio_data", fake_fetch)

    await holdings_service.fetch_portfolio_data()
    await holdings_service.fetch_portfolio_data()

    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_load_performance_is_cached(monkeypatch):
    monkeypatch.setattr(holdings_service.settings, "FEATURE_USE_QUESTRADE_PROVIDER", False)

    call_count = {"n": 0}

    async def fake_load_performance():
        call_count["n"] += 1
        return FAKE_PERFORMANCE_DF

    monkeypatch.setattr(holdings_service.external_api, "load_performance", fake_load_performance)

    await holdings_service.load_performance()
    await holdings_service.load_performance()

    assert call_count["n"] == 1


def test_fetch_portfolio_data_has_holdings_cache_decorator():
    # @cached wraps with functools.wraps, so __wrapped__ should point at the
    # inner coroutine function; presence of caching behavior is asserted above,
    # this just checks the decoration didn't get dropped.
    assert hasattr(holdings_service.fetch_portfolio_data, "__wrapped__")


def test_load_performance_has_performance_cache_decorator():
    assert hasattr(holdings_service.load_performance, "__wrapped__")


# ---------------------------------------------------------------------------
# 5. Endpoint imports
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
