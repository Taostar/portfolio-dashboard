"""Portfolio performance metrics — ported from
Questrade-API/utils/calc_portfolio_metrics.py.

`calc_metrics` is ported verbatim (pure numpy/pandas math, no I/O).

`read_prepare_prices` (the original CSV-reading helper) is replaced by
`prepare_prices_from_df`, which performs the same pivot/ffill/bfill shape on an
in-memory long-format DataFrame (the one `QuestradeProvider.get_market_data()`
produces) instead of reading a CSV off disk via `glob.glob`/`pd.read_csv`.

`calc_portfolio_metrics` keeps the original's symbol-filtering behavior (drop
holdings whose symbol has no price history) and output dict shape, but now
takes the in-memory performance DataFrame as an argument instead of implicitly
reading it from disk.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# The real risk free rate daily is around 1.19*10-4 with annual 3% 3-months US treasury bill
def calc_metrics(prices: pd.DataFrame, allocs, risk_free_rate: float = 0, sample_freq: int = 252):
    """compute portfolio metrics, cumulative return, average daily return, standard deviation of daily return, Sharpe ratio"""
    normalized_allocs_positions = prices / prices.iloc[0] * allocs
    normalized_allocs_positions = normalized_allocs_positions.sum(axis=1)
    cr = normalized_allocs_positions.iloc[-1] / normalized_allocs_positions.iloc[0] - 1
    dr = (normalized_allocs_positions[1:] / normalized_allocs_positions[:-1].values) - 1
    adr = dr.mean()
    sddr = dr.std()
    sr = np.sqrt(sample_freq) * ((adr - risk_free_rate) / sddr)
    return cr, adr, sddr, sr


def prepare_prices_from_df(
    performance_df: pd.DataFrame, selected_symbols: Optional[list] = None
) -> pd.DataFrame:
    """In-memory replacement for the old `read_prepare_prices()`, which read a
    CSV off disk. Takes the long-format performance DataFrame (symbol, date,
    close, ...) produced by `QuestradeProvider.get_market_data()` and returns
    the same pivoted/filled wide-format prices DataFrame the old function did:
    one column per symbol, one row per date, ffill then bfill to patch gaps.
    """
    df = performance_df
    if selected_symbols:
        all_symbols = set(df["symbol"].unique())
        missing_symbols = set(selected_symbols) - all_symbols
        if missing_symbols:
            raise ValueError(
                f"Selected symbols not found in performance data: {', '.join(missing_symbols)}"
            )
        df = df[df["symbol"].isin(selected_symbols)]

    sort_by_cols = ["symbol", "date"]
    df = df.sort_values(by=sort_by_cols).reset_index(drop=True)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    prices_df = df.pivot(index="date", columns="symbol", values="close")
    prices_df = prices_df.ffill().bfill()
    return prices_df


def calc_portfolio_metrics(
    performance_df: pd.DataFrame,
    annual_risk_free_rate: float = 0.03,
    holdings_df: Optional[pd.DataFrame] = None,
    symbols_allocs: Optional[dict] = None,
) -> dict:
    """compute portfolio metrics, cumulative return, average daily return, standard deviation of daily return, Sharpe ratio

    `performance_df` is the in-memory long-format performance DataFrame
    (symbol, date, close, ...) used to look up prices — the caller is
    responsible for fetching it (e.g. via `get_market_data()`), mirroring how
    the old code implicitly depended on the daily-collected CSV being fresh.
    """
    if symbols_allocs:
        symbols, allocs = symbols_allocs.keys(), symbols_allocs.values()
        prices = prepare_prices_from_df(performance_df, selected_symbols=list(symbols))
    else:
        symbols = [str(symbol) for symbol in holdings_df["symbol"].tolist()]
        allocs = [str(p) for p in holdings_df["percentage"].tolist()]

        # First, get all available symbols from the performance data to
        # filter out any holdings that don't have historical data.
        all_prices = prepare_prices_from_df(performance_df)
        available_symbols = set(all_prices.columns.tolist())

        filtered_data = [(s, a) for s, a in zip(symbols, allocs) if s in available_symbols]

        if not filtered_data:
            raise ValueError("No holdings have historical performance data available")

        symbols, allocs = zip(*filtered_data)
        symbols = list(symbols)
        allocs = list(allocs)

        prices = prepare_prices_from_df(performance_df, selected_symbols=symbols)

    risk_free_rate = annual_risk_free_rate / 252
    portfolio_dict = dict(zip(symbols, allocs))
    sorted_symbols = sorted(symbols)
    sorted_portfolio = {symbol: portfolio_dict[symbol] for symbol in sorted_symbols}
    allocations = [float(alloc) / 100 for alloc in sorted_portfolio.values()]

    cr, adr, sddr, sr = calc_metrics(prices, allocations, risk_free_rate)
    metrics = {
        "Symbols": list(portfolio_dict.keys()),
        "Allocations": [f"{float(alloc) / 100:.2%}" for alloc in portfolio_dict.values()],
        "Cumulative Return": cr,
        "Average Daily Return": adr,
        "Standard Deviation of Daily Return": sddr,
        "Sharpe Ratio": sr,
    }
    return metrics
