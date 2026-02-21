import tomllib
from pathlib import Path
from typing import Any


_DEFAULT_CONFIG_PATH = Path("config.toml")


def load(path: Path = _DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load and return the configuration from a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def get_site(cfg: dict) -> dict:
    return cfg.get("site", {})


def get_database_path(cfg: dict) -> Path:
    return Path(cfg.get("database", {}).get("path", "data/events.db"))


def get_venues(cfg: dict) -> dict[str, dict]:
    """Return the venues section, filtering to only enabled venues."""
    venues = cfg.get("venues", {})
    return {key: v for key, v in venues.items() if v.get("enabled", True)}
