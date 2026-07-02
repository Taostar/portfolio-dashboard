# EMA Indicators + VIX Chart — Design Spec
**Date:** 2026-07-02  
**Branch:** feat/21_EMA

---

## Overview

Add two long-term EMA indicators (21-month and 21-quarter) to the holdings table, and a VIX chart to the Portfolio Overview section. These give the user at-a-glance signal of where each holding stands relative to major trend support, and a live read of market sentiment.

---

## Feature 1: EMA(21) Monthly and Quarterly Columns in Holdings Table

### Definition

| Signal | Candle timeframe | Effective lookback | yfinance fetch params |
|---|---|---|---|
| 21M EMA | Monthly (1M) | ~21 months | `period="3y", interval="1mo"` |
| 21Q EMA | Quarterly (3M) | ~5.25 years (~21 quarters) | `period="10y", interval="3mo"` |

Both use EMA(21): `pandas.Series.ewm(span=21, adjust=False).mean()` applied to the monthly/quarterly Close column. The latest (most recently completed candle) value is used.

### Data Source

`yfinance` — already a project dependency, used for exchange rate data. No new library required.

### New function in `utils.py`

```python
@st.cache_data(ttl=86400)
def fetch_ema_indicators(symbols: list[str]) -> dict[str, dict[str, float | None]]:
    """
    Returns {symbol: {"ema_21m": float|None, "ema_21q": float|None}}
    for each symbol in the list.
    """
```

- Downloads monthly and quarterly data per symbol using `yf.download()`
- Computes EMA(21) using `ewm(span=21, adjust=False).mean()` on the Close column
- Returns the last valid EMA value for each timeframe
- Returns `None` for a timeframe if insufficient data (< 21 candles)
- Cached for 1 day — monthly/quarterly candles change slowly

### Holdings table changes (`app.py`)

1. Call `fetch_ema_indicators()` with the list of symbols from `holdings_df`
2. Map returned values into two new columns on `display_df`: `21M EMA` and `21Q EMA`
3. Add these columns to `display_df` between the existing price columns and the % change columns
4. Apply cell-level styling via `.applymap()`:
   - `current_price > ema_value` → green text (`color: #006400`)
   - `current_price < ema_value` → red text (`color: #8B0000`)
   - `None` / NaN → no color, display as `N/A`
5. Add `'{:,.2f}'` formatter for both EMA columns

### Column ordering in display table (after rename)

Symbol | Currency | Quantity | Current Price | Market Value | Portfolio % | **21M EMA** | **21Q EMA** | 1 Day (%) | 1 WK (%) | 1 Month (%) | 6 Months (%) | 1 Year (%)

---

## Feature 2: VIX Chart in Portfolio Overview

### Data

- Ticker: `^VIX` via `yfinance`, `period="1y"`, `interval="1d"`
- Fetched in a new helper inside `app.py` (same pattern as `load_exchange_rate_data`), cached for 1 day

### Chart specification

- Plotly line chart, compact height ~300px, full width
- Three horizontal `add_hline()` reference lines:
  - `y=20`, label "Elevated Fear", color orange, dash="dot"
  - `y=30`, label "High Fear", color darkorange, dash="dash"
  - `y=40`, label "Extreme Fear", color red, dash="solid"
- Background color zones via `add_hrect()`:
  - 0–20: light green, low opacity (~0.05)
  - 20–30: light yellow, low opacity (~0.05)
  - 30–100: light red, low opacity (~0.05)
- Title: `"CBOE Volatility Index (VIX) — Market Mood"`
- Current VIX value displayed as a `st.metric()` above the chart alongside a text label of the zone (Calm / Elevated / High Fear / Extreme Fear)

### Placement

Directly **below the 4-metric portfolio KPI row** in the Portfolio Overview section (before the allocation pie chart). This keeps it within the first screen the user sees.

---

## Architecture

### Files changed

| File | Change |
|---|---|
| `utils.py` | Add `fetch_ema_indicators(symbols)` |
| `app.py` | (1) Call EMA function, extend holdings table; (2) Add VIX fetch + chart in Overview section |

### Caching TTLs

| Data | TTL | Reason |
|---|---|---|
| EMA indicators | 86400s (1 day) | Monthly/quarterly candles don't change intraday |
| VIX daily data | 86400s (1 day) | Consistent with exchange rate caching pattern |

### Error handling

- If yfinance returns empty data for a symbol (e.g., delisted, unsupported ticker), return `None` for that symbol's EMA values — display as `N/A` in the table, no crash
- If VIX data fails to load, show `st.warning()` and skip the chart — do not block the rest of the dashboard

---

## Out of Scope

- Intraday EMA updates (EMAs update once per completed monthly/quarterly candle close)
- Adding EMA lines to the individual candlestick chart (separate feature)
- Alert/notification when price crosses an EMA
