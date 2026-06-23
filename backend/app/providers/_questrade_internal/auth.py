"""Authentication utilities for the Questrade API — ported from
Questrade-API/utils/auth.py.

Supports one or many Questrade logins via QUESTRADE_REFRESH_TOKEN
(comma-separated list of refresh tokens), read from this codebase's
`Settings` (pydantic-settings, `.env`-backed) via `get_settings()` instead of
`os.getenv` + `load_dotenv()`.

Token YAML cache files resolve against `settings.QUESTRADE_TOKEN_DIR` instead
of the original `_project_root()` (two dirs up from the old file) — that's the
one real behavior change from the original. `QUESTRADE_TOKEN_DIR` is created
if missing before any read/write, since (unlike the old project root) it
isn't guaranteed to already exist.

For each token (by position in the list):
1. Try the access_token from access_token.yml (index 0) / access_token_<i>.yml
2. If expired (401) -> use the refresh_token from the same file to get new tokens
3. If that fails -> use the corresponding seed token from settings to get new tokens
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml
from qtrade import Questrade

from app.config import get_settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://login.questrade.com/oauth2/token"


def _token_dir() -> Path:
    """Return the configured Questrade token cache directory, creating it if
    it doesn't already exist."""
    settings = get_settings()
    token_dir = Path(settings.QUESTRADE_TOKEN_DIR)
    token_dir.mkdir(parents=True, exist_ok=True)
    return token_dir


def _token_path_for_index(i: int) -> Path:
    """Return the cache file path for the i-th refresh token.
    Index 0 keeps the legacy filename so existing single-account users
    don't need to re-authenticate.
    """
    base = _token_dir()
    return base / "access_token.yml" if i == 0 else base / f"access_token_{i}.yml"


def _parse_refresh_tokens() -> List[str]:
    """Read QUESTRADE_REFRESH_TOKEN and split into a non-empty list of seed tokens."""
    settings = get_settings()
    raw = settings.QUESTRADE_REFRESH_TOKEN or ""
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if not tokens:
        raise ValueError("QUESTRADE_REFRESH_TOKEN setting is required")
    return tokens


def _load_yaml(token_path: Path) -> Optional[Dict[str, Any]]:
    """Load the token yaml file, return None if missing or unreadable."""
    try:
        with open(token_path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def _save_yaml(token_data: Dict[str, Any], token_path: Path) -> None:
    """Save token data to yaml. Only writes standard Questrade fields so qtrade doesn't crash."""
    if token_path.is_dir():
        raise IsADirectoryError(
            f"{token_path} is a directory. Run `rm -rf {token_path} && touch {token_path}` on the host and redeploy."
        )
    STANDARD_FIELDS = {"access_token", "token_type", "expires_in", "refresh_token", "api_server"}
    clean_data = {k: v for k, v in token_data.items() if k in STANDARD_FIELDS}
    with open(token_path, "w") as f:
        yaml.dump(clean_data, f)
    logger.info(f"Saved new token to {token_path}")


def _fetch_tokens(refresh_token: str) -> Dict[str, Any]:
    """Exchange a refresh token for a new token pair via Questrade OAuth.
    Questrade uses GET with query params (not POST with form body).
    """
    logger.info("Fetching new tokens from Questrade API...")
    resp = requests.get(
        TOKEN_URL,
        params={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=30,
    )
    resp.raise_for_status()
    token_data = resp.json()
    if "api_server" in token_data:
        token_data["api_server"] = token_data["api_server"].rstrip("/")
    return token_data


def _authenticate_one(seed_refresh_token: str, token_path: Path) -> Questrade:
    """Authenticate a single Questrade login.

    1. If token_path exists -> try it.
       - Access token still valid -> return client.
       - Access token expired (401) -> use refresh_token from the same file
         to fetch new tokens, save, return client.
    2. If no yaml or refresh also failed -> use the provided seed refresh token
       to fetch new tokens, save, return client.
    """
    # Step 1: Try the cached access_token.yml
    if token_path.exists() and not token_path.is_dir():
        try:
            client = Questrade(token_yaml=str(token_path))
            client.get_account_id()  # test if access token is still valid
            logger.info(f"Authenticated with cached access token ({token_path.name})")
            return client
        except Exception as e:
            logger.warning(f"Cached access token at {token_path.name} invalid ({e}). Trying refresh...")

            # Step 2: Access token expired - use yaml's refresh_token
            cached = _load_yaml(token_path)
            cached_refresh = (cached or {}).get("refresh_token", "")
            if cached_refresh:
                try:
                    token_data = _fetch_tokens(cached_refresh)
                    _save_yaml(token_data, token_path)
                    client = Questrade(token_yaml=str(token_path))
                    logger.info(f"Authenticated with refreshed token ({token_path.name})")
                    return client
                except Exception as e2:
                    logger.warning(f"Refresh with yaml token failed ({e2}). Trying seed token...")

    # Step 3: Fallback - use the seed refresh token from settings
    logger.info(f"Authenticating {token_path.name} with seed refresh token from settings...")
    token_data = _fetch_tokens(seed_refresh_token)
    _save_yaml(token_data, token_path)
    client = Questrade(token_yaml=str(token_path))
    logger.info(f"Authenticated with new token from settings ({token_path.name})")
    return client


def get_questrade_client() -> Questrade:
    """Return the first authenticated Questrade client.

    Backward-compatible entry point: callers that only need one login keep
    working unchanged. When multiple tokens are configured this returns the
    first one (index 0). Use get_questrade_clients() to span all logins.
    """
    tokens = _parse_refresh_tokens()
    return _authenticate_one(tokens[0], _token_path_for_index(0))


def get_questrade_clients() -> List[Questrade]:
    """Return one authenticated Questrade client per refresh token in settings.

    Each token is authenticated independently against its own cache file.
    Tokens that fail to authenticate are skipped (with a warning) so a single
    bad token doesn't take down the whole call. Raises if zero clients are
    successfully authenticated.
    """
    tokens = _parse_refresh_tokens()
    clients: List[Questrade] = []
    for i, token in enumerate(tokens):
        try:
            clients.append(_authenticate_one(token, _token_path_for_index(i)))
        except Exception as e:
            logger.warning(f"Failed to authenticate token at index {i}: {e}")
    if not clients:
        raise ValueError("Could not authenticate any Questrade refresh token")
    return clients
