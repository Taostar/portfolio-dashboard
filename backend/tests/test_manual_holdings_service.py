from app.api.v1.schemas.manual_holdings import ManualHolding, ManualHoldingsConfig
from app.config import Settings
from app.services import manual_holdings_service


def _patch_settings_path(monkeypatch, path):
    monkeypatch.setattr(
        manual_holdings_service,
        "get_settings",
        lambda: Settings(MANUAL_HOLDINGS_CONFIG_PATH=str(path)),
    )


def test_load_manual_holdings_missing_file_returns_empty_config(tmp_path, monkeypatch):
    _patch_settings_path(monkeypatch, tmp_path / "holdings.yaml")

    config = manual_holdings_service.load_manual_holdings()

    assert config == ManualHoldingsConfig()


def test_save_then_load_manual_holdings_roundtrips(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "holdings.yaml"
    _patch_settings_path(monkeypatch, path)

    config = ManualHoldingsConfig(
        holdings=[
            ManualHolding(
                symbol="BDX",
                currency="USD",
                quantity=10,
                open_quantity=10,
                average_entry_price=249.01,
            )
        ]
    )

    manual_holdings_service.save_manual_holdings(config)
    loaded = manual_holdings_service.load_manual_holdings()

    assert loaded == config
