# scripts/

## `test_upstream_connectivity.sh`

Run on the NAS when the frontend shows "Failed to load the allocation data" or
the backend API returns `503 {"detail":"Unable to fetch holdings data"}`. It
execs into the running `portfolio-backend` container and makes the same
request the backend itself would make to `EXTERNAL_API_URL`, isolating
whether the failure is upstream connectivity (this script) vs. the
tunnel/CORS/frontend layer.

```bash
cd /path/to/portfolio-dashboard   # wherever you cloned it on the NAS
sh scripts/test_upstream_connectivity.sh
```

Reads `EXTERNAL_API_URL` from the repo's `.env`. Pass a URL explicitly to
override:

```bash
sh scripts/test_upstream_connectivity.sh https://your-ngrok-url.ngrok-free.app
```

Requires the `portfolio-backend` container to already be running
(`sudo docker compose up -d`).
