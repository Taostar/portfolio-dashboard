# Deployment Log: Portfolio Dashboard on NAS via Docker + Cloudflare Tunnel

## Goal

Run the FastAPI backend + React frontend persistently on a home NAS, reachable from the public internet, without port-forwarding or opening firewall holes on the home router.

## Architecture

```
Internet → Cloudflare DNS/Tunnel → cloudflared (container, on NAS)
                                       ├── app.gotaogoportfolio.com → frontend:80 (nginx, serves React build)
                                       └── api.gotaogoportfolio.com → backend:8000 (FastAPI/uvicorn)
```

All three services run via a single `docker-compose.yml` at the repo root, on one bridge network (`portfolio-net`). No host ports are published — `cloudflared` reaches `frontend` and `backend` purely by Docker Compose service-name DNS.

Scope: only the FastAPI (`backend/`) + React (`frontend/`) stack. The legacy root-level Streamlit app (`app.py`, `utils.py`, `config.json`, `start_streamlit.sh`) was explicitly excluded and untouched.

## Exposure mechanism: Cloudflare Tunnel (decided, not revisited)

Chosen specifically to avoid port-forwarding/opening the home router's firewall. Tunnel uses token-based auth (`TUNNEL_TOKEN` in `.env`) — no `cloudflared/config.yml` in the repo; routing ("Public Hostnames") lives in the Cloudflare Zero Trust dashboard against the tunnel itself.

Domain: `gotaogoportfolio.com`, registered via Namecheap, nameservers pointed at Cloudflare.

## Files created

- `backend/Dockerfile` — `python:3.11-slim`, installs `backend/requirements.txt`, runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `backend/.dockerignore`
- `frontend/Dockerfile` — multi-stage: `node:20-slim` build stage (bakes `VITE_API_URL` in as a build **arg**, since Vite resolves `import.meta.env.*` at build time, not runtime) → `nginx:1.27-alpine` serve stage.
- `frontend/.dockerignore`
- `frontend/nginx.conf` — SPA fallback (`try_files $uri $uri/ /index.html`) + static asset caching.
- `docker-compose.yml` (repo root) — `backend`, `frontend`, `cloudflared` services.
- `.env.example` (repo root) — documents `EXTERNAL_API_URL`, `CORS_ORIGINS` (must be a JSON array string — `CORS_ORIGINS` is `list[str]` in pydantic-settings, so `["https://app.gotaogoportfolio.com"]`, not comma-separated), `VITE_API_URL`, `TUNNEL_TOKEN`.
- `.env` (gitignored, real secrets) — created locally, then copied to the NAS manually (not via git, since it's ignored).

No backend Python source was changed — `backend/app/config.py`'s `Settings(BaseSettings)` already reads real environment variables (which take precedence over the `.env` file), and `backend/app/main.py`'s `CORSMiddleware` already reads `settings.CORS_ORIGINS` dynamically.

## Pre-existing bugs fixed (blocking the production build, unrelated to Docker setup)

`npm run build` runs `tsc -b` (strict type-check), which had apparently never been run cleanly before (only `npm run dev` had been used, which doesn't block on type errors). Fixed in `frontend/src/components/charts/*.tsx` and `HoldingsTable.tsx`:

- Plotly.js v3 axis title type changed from a plain string to `{ text: string }` — fixed in `BarChart.tsx`, `CandlestickChart.tsx`, `LineChart.tsx`.
- `colorbar.title`/`titleside` merged into `colorbar.title.side` — fixed in `HeatmapChart.tsx`.
- Invalid `textinfo` literal `'percent+label'` → `'label+percent'` — fixed in `PieChart.tsx`.
- Per-point `customdata` arrays aren't representable in react-plotly.js's flat `Datum[]` type — cast `as never` with a comment explaining why, in `PieChart.tsx`.
- Unused import `formatCurrency` removed from `HoldingsTable.tsx`.

## Cloudflare setup steps (manual, dashboard)

1. Registered `gotaogoportfolio.com` on Namecheap.
2. Added the domain to Cloudflare ("Add a Site"), switched Namecheap nameservers to Cloudflare's via Namecheap's **Domain List → Manage → Nameservers → Custom DNS**.
3. Created a Tunnel in Zero Trust → Networks → Tunnels (connector type Cloudflared, **Zero Trust Free** plan — sufficient for personal use, free up to 50 Access seats), copied the `TUNNEL_TOKEN`.
4. Added two Public Hostname routes on the tunnel:
   - `app.gotaogoportfolio.com` → `http://frontend:80`
   - `api.gotaogoportfolio.com` → `http://backend:8000`

## Local verification (before touching the NAS)

Ran the full stack locally first as a sanity check — `docker compose build && docker compose up -d` — and confirmed, using the **real** Cloudflare token, that `https://app.gotaogoportfolio.com` (200) and `https://api.gotaogoportfolio.com/health` (`{"status":"ok"}`) worked end-to-end, including a CORS check (`access-control-allow-origin` header present, matching the frontend's public origin) and a real data endpoint (`/api/v1/portfolio/overview`) returning live portfolio data. Then ran `docker compose down` locally — the stack is meant to live on the NAS, not a dev machine.

## NAS-specific deployment notes (极空间 / ZSpace NAS, not Synology)

The original plan assumed Synology (Container Manager GUI). The actual NAS is a 极空间 (ZSpace) NAS, which is Linux-based (arm64) but doesn't ship Synology's tooling. Adjustments made:

- **SSH**: enabled in NAS settings; non-default port (`10000`, not 22) — found by checking the settings panel after an initial connection attempt failed.
- **Docker permissions**: the SSH user isn't in the `docker` group; used `sudo docker ...` for every command instead of fixing group membership.
- **Repo location on NAS**: `/tmp/zfsv3/sata11/17318045377/data/Docker/portfolio-dashboard` (ZSpace's storage path convention — not `/volume1/...` like Synology). `git clone` was run directly on the NAS over SSH; `.env` was copied separately afterward (since it's gitignored).
- **`docker compose` plugin missing**: `apt-get install docker-compose-plugin` is not available on this vendor OS. Fixed by downloading the official static binary directly:
  ```bash
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" -o "/usr/local/lib/docker/cli-plugins/docker-compose"
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  ```
  Installed to a system-wide plugin path (`/usr/local/lib/docker/cli-plugins/`), not the user's `~/.docker/cli-plugins/`, since commands are run via `sudo` (different `$HOME`). Resulted in Compose v5.1.4. Note the binary is **arm64** (`-linux-aarch64`) — matches the NAS's `linux/arm64` Docker daemon.
- **Build performance**: backend image built in ~4 min, frontend in ~10 min (mostly `npm ci` + `npm run build` on arm64) — slower than the dev machine but acceptable for a one-time deploy.

## Final state (as of last verification)

- All three containers (`portfolio-backend`, `portfolio-frontend`, `portfolio-cloudflared`) running on the NAS via `docker compose up -d`.
- `https://app.gotaogoportfolio.com` → 200.
- `https://api.gotaogoportfolio.com/health` → `{"status":"ok"}`.

## Outstanding / not yet done

- **No access control yet.** Both public URLs are open to anyone on the internet who finds them — including live portfolio values, allocations, and Sharpe ratio. Decision was made to add **Cloudflare Access** (Zero Trust → Access → Applications → Add an application → Self-hosted, one policy restricting to the owner's email via one-time PIN) — **this has not been configured yet** and should be done before treating this deployment as final.
- `EXTERNAL_API_URL` in `.env` is still the same rotating ngrok free-tier URL used during local development. If that ngrok tunnel restarts, its URL changes and the backend will silently fail to fetch upstream data even though the NAS/Cloudflare layer stays healthy. A stable replacement for the upstream data API is a known gap, separate from this deployment work.
- Frontend production bundle is ~5.2MB (1.57MB gzipped) — Vite warns about chunk size (Plotly.js is large). Not addressed; purely a performance/cosmetic item, not a blocker.
