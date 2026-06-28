# Portfolio Dashboard

A portfolio visualization dashboard with a React/TypeScript frontend and a FastAPI backend. Displays stock/ETF holdings, performance analytics, correlation matrices, exchange rates, and benchmark comparisons.

## Architecture

```
Questrade API (direct, via qtrade)
    └── account holdings, positions, quotes
yfinance
    └── historical OHLCV price data
            ↓
    FastAPI Backend (backend/)
        ├── /api/v1/portfolio   → portfolio overview & metrics
        ├── /api/v1/holdings    → current holdings table (stocks/ETFs + options split)
        ├── /api/v1/correlation → correlation matrix
        ├── /api/v1/exchange    → exchange rates (USD/CAD, CAD/CNY, BTC/USD)
        ├── /api/v1/benchmark   → benchmark comparison
        ├── /api/v1/performance → individual asset candlestick data
        └── /api/v1/mcp        → MCP interface for AI agents
            ↓
    React Frontend (frontend/)
        └── Vite + React 19 + TailwindCSS + Plotly.js dashboard
```

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Settings (external API URL, CORS, cache TTLs)
│   │   ├── api/v1/
│   │   │   ├── router.py        # API router
│   │   │   ├── endpoints/       # portfolio, holdings, correlation, exchange, benchmark, performance
│   │   │   └── schemas/         # Pydantic request/response models
│   │   ├── services/            # Business logic & data processing
│   │   └── core/cache.py        # Caching layer
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx             # React entry point
│   │   ├── App.tsx              # Root component (React Query provider)
│   │   ├── pages/Dashboard.tsx  # Main dashboard page
│   │   ├── api/                 # Axios client & API calls
│   │   ├── components/
│   │   │   ├── charts/          # BarChart, CandlestickChart, HeatmapChart, LineChart, PieChart
│   │   │   ├── common/          # Layout, MetricCard
│   │   │   ├── sections/        # Dashboard sections (PortfolioOverview, AssetAllocation, etc.)
│   │   │   └── tables/          # HoldingsTable
│   │   ├── hooks/usePortfolio.ts
│   │   ├── types/portfolio.ts
│   │   └── utils/               # formatters, colorUtils
│   └── package.json
├── config.json                  # Legacy: ngrok API_URL (used by old Streamlit app)
└── requirements.txt             # Legacy: Streamlit dependencies
```

## Setup

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure Questrade credentials
echo "QUESTRADE_REFRESH_TOKEN=your-refresh-token" > .env
echo "QUESTRADE_TOKEN_DIR=/data/questrade_tokens" >> .env  # optional, defaults to /data/questrade_tokens

# Start the server
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure the backend URL (optional — defaults to http://localhost:8000/api/v1)
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env

# Start the dev server
npm run dev
```

Opens at `http://localhost:5173`.

## Configuration

| Location | Variable | Default | Description |
|---|---|---|---|
| `backend/.env` | `QUESTRADE_REFRESH_TOKEN` | *(required)* | Questrade OAuth refresh token |
| `backend/.env` | `QUESTRADE_TOKEN_DIR` | `/data/questrade_tokens` | Directory for cached Questrade tokens |
| `backend/.env` | `CORS_ORIGINS` | `localhost:5173,3000` | Allowed frontend origins (JSON array string) |
| `frontend/.env` | `VITE_API_URL` | `http://localhost:8000/api/v1` | Backend API base URL |

## Dashboard Sections

- **Portfolio Overview** — total market value (CAD), cumulative return, Sharpe ratio, daily return
- **Asset Allocation** — pie chart of portfolio weights
- **Current Holdings** — sortable holdings tables: Stocks & ETFs, and Options (when present)
- **Holdings Bar Chart** — bar chart of position sizes
- **Correlation Matrix** — heatmap of pairwise asset correlations
- **Exchange Rates** — USD/CAD, CAD/CNY, USD/CNY, BTC/USD live rates
- **Benchmark Comparison** — portfolio vs. benchmark (e.g. SPY) performance
- **Individual Asset** — candlestick OHLCV chart per symbol

## Tech Stack

**Backend:** Python, FastAPI, Uvicorn, Pydantic v2, yfinance, pandas, cachetools

**Frontend:** React 19, TypeScript, Vite, TailwindCSS 4, Plotly.js, TanStack Query, TanStack Table, Axios
