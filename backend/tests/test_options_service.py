import pandas as pd
import pytest

from app.services.options_service import (
    calculate_notional_exposure_cad,
    get_cash_like_reserves_cad,
)


def test_calculate_notional_exposure_cad_single_usd_put():
    options_df = pd.DataFrame(
        [{"symbol": "NVDA10Jul26P180.00", "currency": "USD", "quantity": -1, "strike": 180.0}]
    )

    notional = calculate_notional_exposure_cad(options_df, fx_rate_usd_to_cad=1.35)

    # 180 * 100 * 1 * 1.35
    assert notional == pytest.approx(24300.0)


def test_calculate_notional_exposure_cad_cad_contract_not_converted():
    options_df = pd.DataFrame(
        [{"symbol": "IFC2Jul26C60.00", "currency": "CAD", "quantity": 2, "strike": 60.0}]
    )

    notional = calculate_notional_exposure_cad(options_df, fx_rate_usd_to_cad=1.35)

    # 60 * 100 * 2, no FX conversion applied to a CAD contract.
    assert notional == pytest.approx(12000.0)


def test_calculate_notional_exposure_cad_sums_multiple_positions():
    options_df = pd.DataFrame(
        [
            {"symbol": "NVDA10Jul26P180.00", "currency": "USD", "quantity": -1, "strike": 180.0},
            {"symbol": "IFC2Jul26C60.00", "currency": "CAD", "quantity": 2, "strike": 60.0},
        ]
    )

    notional = calculate_notional_exposure_cad(options_df, fx_rate_usd_to_cad=1.35)

    assert notional == pytest.approx(24300.0 + 12000.0)


def test_calculate_notional_exposure_cad_empty_df_returns_zero():
    assert calculate_notional_exposure_cad(pd.DataFrame(), fx_rate_usd_to_cad=1.35) == 0.0


def test_get_cash_like_reserves_cad_with_both_symbols_present():
    df = pd.DataFrame(
        [
            {"symbol": "SGOV", "current_market_value_CAD": 5000.0},
            {"symbol": "PSA.TO", "current_market_value_CAD": 3000.0},
            {"symbol": "AAPL", "current_market_value_CAD": 1500.0},
        ]
    )

    reserves = get_cash_like_reserves_cad(df)

    assert reserves == {
        "sgov_value_cad": 5000.0,
        "psa_to_value_cad": 3000.0,
        "total_cad": 8000.0,
    }


def test_get_cash_like_reserves_cad_missing_symbols_default_to_zero():
    df = pd.DataFrame([{"symbol": "AAPL", "current_market_value_CAD": 1500.0}])

    reserves = get_cash_like_reserves_cad(df)

    assert reserves == {"sgov_value_cad": 0.0, "psa_to_value_cad": 0.0, "total_cad": 0.0}


def test_get_cash_like_reserves_cad_empty_df():
    reserves = get_cash_like_reserves_cad(pd.DataFrame())

    assert reserves == {"sgov_value_cad": 0.0, "psa_to_value_cad": 0.0, "total_cad": 0.0}
