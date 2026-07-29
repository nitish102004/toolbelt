"""Shared config loader for the ``toolbelt`` repo.

Reads a TOML file with per-user configuration (base URLs, default project
keys, etc). Missing file, missing sections, and missing keys all fall back
silently to whatever built-in defaults the caller supplies -- there is no
mandatory configuration.

Resolution order for the config file:
  1. ``$TOOLBELT_CONFIG`` environment variable (explicit override).
  2. ``<SECRETS_DIR>/config.toml`` -- lives next to token files.

Per-value resolution order inside each tool's ``api.py``:
  1. Tool-specific environment variable (e.g. ``TOOLBELT_JIRA_URL``).
  2. Value from the TOML config file.
  3. Built-in default constant supplied by the caller.

See ``docs/CONFIG.md`` and ``config.toml.example`` for the schema.
"""
from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from .secrets import SECRETS_DIR


def _config_path() -> Path:
    override = os.environ.get("TOOLBELT_CONFIG")
    if override:
        return Path(override)
    return SECRETS_DIR / "config.toml"


def _load_toml() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"[config] failed to parse {path}: {e}")


# Cached at import so repeated ``get(...)`` calls do not re-read the file.
_CONFIG: dict[str, Any] = _load_toml()


def section(name: str) -> dict[str, Any]:
    """Return the ``[<name>]`` TOML section, or an empty dict if absent."""
    val = _CONFIG.get(name, {})
    if not isinstance(val, dict):
        sys.exit(f"[config] section [{name}] must be a table, got {type(val).__name__}")
    return val


def get(tool: str, key: str, default: Any, *, env: str | None = None) -> Any:
    """Look up a value with the standard three-step precedence.

    * If ``env`` is given and that environment variable is set, use it.
    * Else if the TOML section ``[<tool>]`` has ``<key>``, use that.
    * Else return ``default``.

    Numeric defaults are coerced from string env values.
    """
    if env and os.environ.get(env):
        raw = os.environ[env]
        if isinstance(default, bool):
            return raw.lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            try:
                return int(raw)
            except ValueError:
                sys.exit(f"[config] {env} must be an integer, got {raw!r}")
        return raw
    return section(tool).get(key, default)

