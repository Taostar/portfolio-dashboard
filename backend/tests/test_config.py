from app.config import Settings


def test_questrade_settings_have_safe_defaults():
    settings = Settings()
    assert settings.QUESTRADE_REFRESH_TOKEN == ""
    assert settings.QUESTRADE_TOKEN_DIR == "/data/questrade_tokens"
