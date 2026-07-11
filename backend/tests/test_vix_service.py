"""Tests for app.services.vix_service — VIX daily closes + fear-zone label.
yf.download is mocked (I/O boundary); zone classification runs for real."""

from unittest.mock import patch

import pandas as pd
import pytest

from app.core.cache import clear_cache
from app.services.vix_service import classify_vix_zone, load_vix_data


@pytest.fixture(autouse=True)
def _clear_vix_cache():
    clear_cache("vix")
    yield
    clear_cache("vix")


@pytest.mark.parametrize(
    "value,zone",
    [
        (12.5, "Calm"),
        (19.99, "Calm"),
        (20.0, "Elevated Fear"),
        (29.99, "Elevated Fear"),
        (30.0, "High Fear"),
        (39.99, "High Fear"),
        (40.0, "Extreme Fear"),
        (80.0, "Extreme Fear"),
    ],
)
def test_classify_vix_zone_boundaries(value, zone):
    assert classify_vix_zone(value) == zone


def _vix_download(closes, multiindex=False):
    dates = pd.date_range("2025-01-01", periods=len(closes), freq="D")
    if multiindex:
        cols = pd.MultiIndex.from_tuples([("Close", "^VIX"), ("Open", "^VIX")])
        return pd.DataFrame(
            {cols[0]: closes, cols[1]: closes}, index=dates, columns=cols
        )
    return pd.DataFrame({"Close": closes, "Open": closes}, index=dates)


def test_load_vix_data_returns_series_and_zone():
    with patch(
        "app.services.vix_service.yf.download",
        return_value=_vix_download([15.0, 16.0, 17.5]),
    ):
        data = load_vix_data()

    assert data["close_prices"] == [15.0, 16.0, 17.5]
    assert len(data["dates"]) == 3
    assert data["current"] == 17.5
    assert data["zone"] == "Calm"


def test_load_vix_data_handles_multiindex_columns():
    with patch(
        "app.services.vix_service.yf.download",
        return_value=_vix_download([32.0, 35.0], multiindex=True),
    ):
        data = load_vix_data()

    assert data["current"] == 35.0
    assert data["zone"] == "High Fear"


def test_load_vix_data_returns_none_on_empty_download():
    with patch(
        "app.services.vix_service.yf.download", return_value=pd.DataFrame()
    ):
        assert load_vix_data() is None


def test_load_vix_data_returns_none_on_download_error():
    with patch(
        "app.services.vix_service.yf.download", side_effect=Exception("network down")
    ):
        assert load_vix_data() is None
