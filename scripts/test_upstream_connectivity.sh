#!/usr/bin/env sh
# Diagnose a non-responding backend by hitting key endpoints from inside the
# running portfolio-backend container.
#
# Run on the NAS (or locally) from the repo root when the frontend shows
# "Failed to load data" errors:
#
#   sh scripts/test_upstream_connectivity.sh
#
# Set DOCKER if the daemon requires sudo:
#   DOCKER="sudo docker" sh scripts/test_upstream_connectivity.sh

set -eu

DOCKER="${DOCKER:-docker}"

echo "==> Backend health check"
$DOCKER exec portfolio-backend wget -qO- http://localhost:8000/health && echo ""

echo ""
echo "==> Questrade auth / holdings fetch (may take a few seconds)"
$DOCKER exec portfolio-backend python3 -c "
import asyncio
from app.providers._questrade_internal.auth import get_questrade_clients

async def check():
    try:
        clients = get_questrade_clients()
        print(f'  Clients initialised: {len(clients)}')
        for i, c in enumerate(clients):
            ids = c.get_account_id()
            print(f'  Client {i}: accounts {ids}')
    except Exception as e:
        print(f'  ERROR: {type(e).__name__}: {e}')

asyncio.run(check())
"
