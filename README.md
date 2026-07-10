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
├── docker-compose.yml           # Production stack: backend + frontend + cloudflared
├── .env.example                 # Template for deployment environment variables
├── scripts/
│   ├── deploy.sh                # Build & (re)start the production stack
│   └── test_upstream_connectivity.sh  # Diagnose backend/Questrade connectivity
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

## Deployment

Production runs as three Docker containers defined in `docker-compose.yml`:

| Service | Image | Role |
|---|---|---|
| `backend` | built from `backend/Dockerfile` | FastAPI + Uvicorn on internal port 8000 |
| `frontend` | built from `frontend/Dockerfile` | Vite production build served by nginx on internal port 80 |
| `cloudflared` | `cloudflare/cloudflared:latest` | Cloudflare Tunnel exposing both services to the internet |

No ports are published on the host — the services talk over the internal `portfolio-net` network, and all public traffic enters through the Cloudflare Tunnel. Named volumes persist Questrade tokens (`questrade-tokens`) and the manual holdings config (`manual-holdings-config`) across restarts.

### Prerequisites

- Docker Engine with the Compose plugin (`docker compose version` must work)
- A Questrade OAuth refresh token
- A Cloudflare Zero Trust tunnel with its connector token, and two public hostnames routed to the internal services:
  - `app.yourdomain.com` → `http://frontend:80`
  - `api.yourdomain.com` → `http://backend:8000`

  (configured under Zero Trust → Networks → Tunnels → your tunnel → Public Hostname)

### Deploy

```bash
# 1. Create the environment file at the repo root
cp .env.example .env
# Edit .env and fill in all four values (see table below)

# 2. Build and start everything
sh scripts/deploy.sh
```

`deploy.sh` pulls the latest code, builds both images, restarts the containers, and waits for the backend `/health` endpoint to respond. On hosts where Docker needs sudo (e.g. a NAS):

```bash
DOCKER="sudo docker" sh scripts/deploy.sh
```

To run the steps manually instead:

```bash
docker compose build --pull
docker compose up -d --remove-orphans
```

### Deployment environment variables (root `.env`)

| Variable | Example | Description |
|---|---|---|
| `QUESTRADE_REFRESH_TOKEN` | `abc123...` | Questrade OAuth refresh token |
| `CORS_ORIGINS` | `["https://app.yourdomain.com"]` | Allowed frontend origins — must be a JSON array string |
| `VITE_API_URL` | `https://api.yourdomain.com/api/v1` | Public backend URL, baked into the frontend at **build time** — changing it requires rebuilding the frontend image |
| `TUNNEL_TOKEN` | `eyJh...` | Cloudflare Tunnel connector token (token value only, not the full `docker run` command) |

### Verify & troubleshoot

```bash
# Container status
docker compose ps

# Backend health from inside the container
docker compose exec backend wget -qO- http://localhost:8000/health

# Full diagnostic: health endpoint + Questrade auth from inside the backend container
sh scripts/test_upstream_connectivity.sh

# Logs
docker compose logs -f backend
```

For quick LAN testing without the tunnel, uncomment the `ports:` mappings in `docker-compose.yml` (`8000:8000` for the backend, `8080:80` for the frontend) and browse to `http://<host>:8080`.

### Updating a running deployment

Re-run `sh scripts/deploy.sh` — it pulls the latest code, rebuilds, and restarts with a health check. Questrade tokens and the manual holdings config live in named volumes, so they survive rebuilds.

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
