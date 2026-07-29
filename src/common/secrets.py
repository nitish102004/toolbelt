"""Shared secret loader for the ``toolbelt`` repo.

Every tool reads its secrets through this module so that:
  * the on-disk location is defined in ONE place,
  * secrets never appear in shell history, env vars, or command lines,
  * a fresh clone works on any machine without editing code.

Resolution order for the secrets directory:
  1. ``$TOOLBELT_SECRETS`` environment variable (explicit override).
  2. ``%USERPROFILE%\\.toolbelt`` on Windows.
  3. ``~/.toolbelt`` elsewhere.

Each secret is a single-line file whose name matches ``load(name)``.
See ``INSTALL.md`` for setup and ``docs/ARCHITECTURE.md`` for rationale.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _default_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("USERPROFILE") or str(Path.home())
    else:
        base = str(Path.home())
    return Path(base) / ".toolbelt"


SECRETS_DIR = (
    Path(os.environ["TOOLBELT_SECRETS"])
    if os.environ.get("TOOLBELT_SECRETS")
    else _default_dir()
)


def load(name: str) -> str:
    """Return the raw secret stored in ``<SECRETS_DIR>/<name>``.

    Exits with a clear message if the file is missing or empty so that the
    caller (and any agent invoking the tool) sees a human-actionable error
    instead of a stack trace.
    """
    path = SECRETS_DIR / name
    if not path.exists():
        sys.exit(
            f"[secrets] missing file: {path}\n"
            f"  create it with the raw secret value (one line, no quotes).\n"
            f"  see INSTALL.md, or set TOOLBELT_SECRETS to a different directory."
        )
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        sys.exit(f"[secrets] file is empty: {path}")
    return value

