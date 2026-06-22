#!/bin/sh
# Checks whether the backend container can reach EXTERNAL_API_URL (the upstream
# holdings/market-data API). Run this on the NAS when the frontend shows
# "Failed to load the allocation data" or the API returns 503
# "Unable to fetch holdings data" -- it isolates whether the problem is
# upstream connectivity (this script) vs. the tunnel/CORS/frontend layer.
#
# Usage (on the NAS, from the repo root):
#   sh scripts/test_upstream_connectivity.sh
#
# Reads EXTERNAL_API_URL from .env in the repo root; override by passing it
# as the first argument instead:
#   sh scripts/test_upstream_connectivity.sh https://your-ngrok-url.ngrok-free.app

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [ "${1:-}" != "" ]; then
  EXTERNAL_API_URL="$1"
elif [ -f "$REPO_ROOT/.env" ]; then
  EXTERNAL_API_URL="$(grep '^EXTERNAL_API_URL=' "$REPO_ROOT/.env" | cut -d= -f2-)"
fi

if [ "${EXTERNAL_API_URL:-}" = "" ]; then
  echo "Could not determine EXTERNAL_API_URL (no .env found and no argument given)." >&2
  exit 1
fi

echo "Testing from inside the portfolio-backend container -> ${EXTERNAL_API_URL}/accounts/holdings"
echo

sudo docker exec portfolio-backend python3 -c "
import httpx
try:
    r = httpx.get('${EXTERNAL_API_URL}/accounts/holdings', timeout=10)
    print('STATUS', r.status_code)
    print(r.text[:200])
except Exception as e:
    print('ERROR', type(e).__name__, e)
"
