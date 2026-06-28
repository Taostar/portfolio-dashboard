import logging
import os

import yaml

from app.api.v1.schemas.manual_holdings import ManualHoldingsConfig
from app.config import get_settings

logger = logging.getLogger(__name__)


def load_manual_holdings() -> ManualHoldingsConfig:
    """Load manually-configured holdings from the YAML config file.

    Returns an empty config if the file is missing or invalid, so an
    unconfigured deployment behaves the same as having no manual holdings.
    """
    path = get_settings().MANUAL_HOLDINGS_CONFIG_PATH
    try:
        with open(path, "r") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        logger.warning(f"Could not load manual holdings config at {path}: {e}")
        return ManualHoldingsConfig()
    return ManualHoldingsConfig.model_validate(raw)


def save_manual_holdings(config: ManualHoldingsConfig) -> None:
    """Persist manually-configured holdings to the YAML config file."""
    path = get_settings().MANUAL_HOLDINGS_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(config.model_dump(), f)
