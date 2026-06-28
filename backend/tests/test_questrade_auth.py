"""TDD tests for _authenticate_one's three-tier fallback chain:
  1. cached access token still valid -> use it as-is
  2. cached access token invalid, but cached refresh_token works -> refresh and save
  3. no usable cache at all -> fall back to the seed refresh token from settings

Live OAuth and the qtrade client are both external dependencies (a real
broker/HTTP service), so they are mocked here — this is the one area the task
brief calls out as unavoidable to mock. Mocks are kept minimal and
behavior-focused: we assert on the returned client / saved YAML content, not
on internal call counts.
"""

import yaml
from unittest.mock import MagicMock, patch

import pytest

from app.providers._questrade_internal.auth import _authenticate_one


class _FakeQuestradeValid:
    """Stand-in for qtrade.Questrade whose cached access token is still valid."""

    def __init__(self, token_yaml=None, access_code=None, save_yaml=True):
        self.token_yaml = token_yaml

    def get_account_id(self):
        return ["12345"]


class _FakeQuestradeInvalidThenValid:
    """First construction (against the stale cache) raises on get_account_id;
    any later construction (after a refresh) is treated as valid."""

    call_count = 0

    def __init__(self, token_yaml=None, access_code=None, save_yaml=True):
        self.token_yaml = token_yaml
        _FakeQuestradeInvalidThenValid.call_count += 1
        self._instance_index = _FakeQuestradeInvalidThenValid.call_count

    def get_account_id(self):
        if self._instance_index == 1:
            raise Exception("401 Unauthorized - access token expired")
        return ["12345"]


@pytest.fixture(autouse=True)
def _reset_fake_counters():
    _FakeQuestradeInvalidThenValid.call_count = 0
    yield


def test_cached_access_token_still_valid_is_used_as_is(tmp_path):
    token_path = tmp_path / "access_token.yml"
    token_path.write_text(yaml.dump({"access_token": "cached-valid", "refresh_token": "r1"}))

    with patch("app.providers._questrade_internal.auth.Questrade", _FakeQuestradeValid):
        client = _authenticate_one("seed-token", token_path)

    assert isinstance(client, _FakeQuestradeValid)
    assert client.token_yaml == str(token_path)
    # File should be untouched (no refresh/seed fetch happened).
    saved = yaml.safe_load(token_path.read_text())
    assert saved["access_token"] == "cached-valid"


def test_cached_access_token_invalid_falls_back_to_cached_refresh_token(tmp_path):
    token_path = tmp_path / "access_token.yml"
    token_path.write_text(yaml.dump({"access_token": "stale", "refresh_token": "cached-refresh-token"}))

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "new-access-from-cached-refresh",
        "refresh_token": "new-refresh-from-cached-refresh",
        "token_type": "Bearer",
        "expires_in": 1800,
        "api_server": "https://api01.iq.questrade.com/",
    }
    fake_response.raise_for_status.return_value = None

    with patch("app.providers._questrade_internal.auth.Questrade", _FakeQuestradeInvalidThenValid), \
         patch("app.providers._questrade_internal.auth.requests.get", return_value=fake_response) as mock_get:
        client = _authenticate_one("seed-token", token_path)

    assert isinstance(client, _FakeQuestradeInvalidThenValid)
    # Confirms the cached refresh_token (not the seed) was used for the OAuth call.
    assert mock_get.call_args.kwargs["params"]["refresh_token"] == "cached-refresh-token"

    saved = yaml.safe_load(token_path.read_text())
    assert saved["access_token"] == "new-access-from-cached-refresh"
    assert saved["api_server"] == "https://api01.iq.questrade.com"  # trailing slash stripped


def test_no_cache_falls_back_to_seed_refresh_token_from_settings(tmp_path):
    token_path = tmp_path / "access_token.yml"
    assert not token_path.exists()

    fake_response = MagicMock()
    fake_response.json.return_value = {
        "access_token": "new-access-from-seed",
        "refresh_token": "new-refresh-from-seed",
        "token_type": "Bearer",
        "expires_in": 1800,
        "api_server": "https://api01.iq.questrade.com",
    }
    fake_response.raise_for_status.return_value = None

    with patch("app.providers._questrade_internal.auth.Questrade", _FakeQuestradeValid), \
         patch("app.providers._questrade_internal.auth.requests.get", return_value=fake_response) as mock_get:
        client = _authenticate_one("seed-token-from-settings", token_path)

    assert isinstance(client, _FakeQuestradeValid)
    assert mock_get.call_args.kwargs["params"]["refresh_token"] == "seed-token-from-settings"

    saved = yaml.safe_load(token_path.read_text())
    assert saved["access_token"] == "new-access-from-seed"
