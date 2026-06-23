import pandas as pd

from app.providers.classifier import is_option_symbol, split_holdings


def test_option_symbol_regex_fallback_matches():
    assert is_option_symbol("NVDA10Jul26P180.00") is True


def test_plain_ticker_regex_fallback_no_match():
    assert is_option_symbol("AAPL") is False


def test_dotted_tickers_not_misclassified_as_options():
    assert is_option_symbol("IFC.TO") is False
    assert is_option_symbol("QQC.F.TO") is False


def test_security_type_option_wins_over_stock_looking_symbol():
    assert is_option_symbol("AAPL", {"security_type": "Option"}) is True


def test_security_type_stock_overrides_option_looking_symbol():
    assert is_option_symbol("NVDA10Jul26P180.00", {"security_type": "Stock"}) is False


def test_security_type_none_falls_back_to_regex():
    assert is_option_symbol("AAPL", {"security_type": None}) is False


def test_empty_symbol_info_falls_back_to_regex():
    assert is_option_symbol("AAPL", {}) is False


def test_split_holdings_splits_stocks_and_options_using_security_type_and_regex():
    df = pd.DataFrame(
        [
            {"symbol": "AAPL", "quantity": 10, "security_type": "Stock"},
            {"symbol": "IFC.TO", "quantity": 5, "security_type": "Stock"},
            {"symbol": "NVDA10Jul26P180.00", "quantity": 1, "security_type": "Option"},
            # No security_type populated -> falls back to regex.
            {"symbol": "GOOG2Jul26P345.00", "quantity": 2, "security_type": None},
            {"symbol": "QQC.F.TO", "quantity": 3, "security_type": None},
        ]
    )

    stocks_etfs_df, options_df = split_holdings(df)

    assert sorted(stocks_etfs_df["symbol"].tolist()) == ["AAPL", "IFC.TO", "QQC.F.TO"]
    assert sorted(options_df["symbol"].tolist()) == ["GOOG2Jul26P345.00", "NVDA10Jul26P180.00"]

    # Original columns must remain intact (not dropped/renamed).
    assert list(stocks_etfs_df.columns) == list(df.columns)
    assert list(options_df.columns) == list(df.columns)
