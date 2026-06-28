# scripts/

## `deploy.sh`

Build images and (re)start all three containers (backend, frontend, cloudflared).
Run from the repo root:

```bash
sh scripts/deploy.sh
```

On the NAS (where Docker requires sudo):

```bash
DOCKER="sudo docker" sh scripts/deploy.sh
```

Requires a `.env` file at the repo root with:
- `QUESTRADE_REFRESH_TOKEN`
- `CORS_ORIGINS` (JSON array string, e.g. `["https://app.yourdomain.com"]`)
- `VITE_API_URL`
- `TUNNEL_TOKEN`

## `test_upstream_connectivity.sh`

Diagnose a non-responding backend by checking the health endpoint and testing
Questrade auth from inside the running `portfolio-backend` container.

```bash
sh scripts/test_upstream_connectivity.sh
```

On the NAS:

```bash
DOCKER="sudo docker" sh scripts/test_upstream_connectivity.sh
```
