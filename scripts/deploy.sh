#!/usr/bin/env sh
# deploy.sh — build and (re)start the backend, frontend, and Cloudflare tunnel.
#
# Usage:
#   sh scripts/deploy.sh          # from the repo root
#
# On the NAS the Docker daemon requires sudo.  Set DOCKER if needed:
#   DOCKER="sudo docker" sh scripts/deploy.sh
#
# All required variables must be present in a .env file at the repo root:
#   QUESTRADE_REFRESH_TOKEN=...
#   CORS_ORIGINS=["https://app.yourdomain.com"]
#   VITE_API_URL=https://api.yourdomain.com/api/v1
#   TUNNEL_TOKEN=...

set -eu

# ── Locate repo root ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── Docker command (override via DOCKER env var for sudo-required setups) ───
DOCKER="${DOCKER:-docker}"

# ── Verify prerequisites ─────────────────────────────────────────────────────
if ! $DOCKER compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' not available. Install the Compose plugin or set DOCKER."
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env file not found at $REPO_ROOT/.env"
  echo "  Copy .env.example and fill in the required values:"
  echo "    cp .env.example .env"
  exit 1
fi

for var in QUESTRADE_REFRESH_TOKEN CORS_ORIGINS VITE_API_URL TUNNEL_TOKEN; do
  if ! grep -q "^${var}=" .env; then
    echo "ERROR: $var is not set in .env"
    exit 1
  fi
done

# ── Pull latest code ─────────────────────────────────────────────────────────
echo "==> Pulling latest code..."
git pull

# ── Build images ─────────────────────────────────────────────────────────────
echo "==> Building images..."
$DOCKER compose build --pull

# ── Restart containers ───────────────────────────────────────────────────────
echo "==> Restarting containers..."
$DOCKER compose up -d --remove-orphans

# ── Health check ─────────────────────────────────────────────────────────────
echo "==> Waiting for backend to become healthy..."
i=0
until $DOCKER compose exec -T backend wget -qO- http://localhost:8000/health >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "ERROR: Backend did not become healthy after 30 seconds."
    $DOCKER compose logs --tail=40 backend
    exit 1
  fi
  sleep 1
done

echo ""
echo "==> Deploy complete."
$DOCKER compose ps
