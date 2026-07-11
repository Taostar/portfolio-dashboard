# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (FastAPI)

```bash
cd backend

# Install dependencies (use a virtualenv)
pip install -r requirements.txt

# Run the dev server
uvicorn app.main:app --reload --port 8000

# Run tests
python -m pytest tests/
```

API docs at `http://localhost:8000/docs`.

### Frontend (React + Vite)

```bash
cd frontend

npm install
npm run dev        # dev server at http://localhost:5173
npm run build      # tsc -b + vite build (strict type-check; must pass before deploy)
npm run lint
```

### Deployment (Docker + Cloudflare Tunnel)

```bash
cp .env.example .env   # fill in QUESTRADE_REFRESH_TOKEN, CORS_ORIGINS, VITE_API_URL, TUNNEL_TOKEN
sh scripts/deploy.sh   # NAS (Docker needs sudo): DOCKER="sudo docker" sh scripts/deploy.sh
```

See the README "Deployment" section for details. `Agent.md` is a historical deployment log.

## Architecture

```
Questrade API (direct, via token refresh)      yfinance (historical OHLCV, FX)
            ↓                                        ↓
    FastAPI Backend (backend/) — all routes under /api/v1
            ↓
    React Frontend (frontend/) — Vite + React 19 + TailwindCSS + Plotly.js
```

- **backend/app/providers/**: data providers — `questrade.py` (auth, holdings, quotes via refresh-token flow), `base.py`, `classifier.py` (stock/ETF vs option split)
- **backend/app/services/**: business logic — holdings, correlation, benchmark, exchange, market value, manual holdings (YAML-configured accounts not reachable via Questrade)
- **backend/app/api/v1/**: routers (`endpoints/`) and Pydantic schemas (`schemas/`); includes an MCP interface at `/api/v1/mcp` for AI agents
- **backend/app/core/cache.py**: caching layer; TTLs configured in `app/config.py`
- **frontend/src/**: `pages/Dashboard.tsx` composes section components (`components/sections/`), which use TanStack Query hooks (`hooks/`) over an Axios client (`api/`); charts are Plotly (`components/charts/`), tables TanStack Table (`components/tables/`)

## Configuration

| Location | Variable | Notes |
|---|---|---|
| `backend/.env` | `QUESTRADE_REFRESH_TOKEN` | required |
| `backend/.env` | `QUESTRADE_TOKEN_DIR` | default `/data/questrade_tokens` |
| `backend/.env` | `CORS_ORIGINS` | must be a JSON array string (pydantic-settings `list[str]`) |
| `frontend/.env` | `VITE_API_URL` | default `http://localhost:8000/api/v1`; baked in at build time |
| root `.env` | all of the above + `TUNNEL_TOKEN` | used only by `docker-compose.yml` / `scripts/deploy.sh` |

## Notes

- The legacy Streamlit app (`app.py`, `utils.py`, `config.json`, root `requirements.txt`) was removed in July 2026; the React/FastAPI stack is the only dashboard. Don't resurrect Streamlit patterns from old commits.
- `frontend/npm run build` runs `tsc -b` strict type-checking that `npm run dev` does not — always build before considering frontend work done.
- Vite env vars are resolved at build time: changing `VITE_API_URL` requires rebuilding the frontend image.
