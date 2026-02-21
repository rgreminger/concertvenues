import os
import tomllib
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path("config.toml")
_DEFAULT_ENV_PATH = Path("secrets")


def load(path: Path = _DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load config from TOML, then overlay any secrets from .env."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    _load_env(_DEFAULT_ENV_PATH, cfg)
    return cfg


def _load_env(env_path: Path, cfg: dict) -> None:
    """
    Parse a .env file and inject values into the config dict.

    Supported variable names:
      TICKETMASTER_API_KEY  -> cfg["secrets"]["ticketmaster_api_key"]

    Shell environment variables take precedence over .env values.
    """
    # Pick up anything already set in the shell first
    _apply_env_vars(cfg)

    if not env_path.exists():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Shell environment takes precedence over .env file
            if key not in os.environ:
                os.environ[key] = value

    _apply_env_vars(cfg)


def _apply_env_vars(cfg: dict) -> None:
    secrets = cfg.setdefault("secrets", {})
    if v := os.environ.get("TICKETMASTER_API_KEY"):
        secrets["ticketmaster_api_key"] = v


def get_site(cfg: dict) -> dict:
    return cfg.get("site", {})


def get_database_path(cfg: dict) -> Path:
    return Path(cfg.get("database", {}).get("path", "data/events.db"))


def get_venues(cfg: dict) -> dict[str, dict]:
    """Return the venues section, filtering to only enabled venues."""
    venues = cfg.get("venues", {})
    return {key: v for key, v in venues.items() if v.get("enabled", True)}
