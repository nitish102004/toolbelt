"""Entry point: ``python -m signoz <verb> [args]``.

Supports multi-word verbs: ``logs tail``, ``logs-tail``, ``traces view``, etc.

Global flags (before verb):
  ``--env prod|preprod``  — target prod (default) or preprod SignOz instance.
"""
from __future__ import annotations

import os
import sys

from . import auth
from .commands import VERBS, cmd_help


def _parse_global_flags(argv: list[str]) -> list[str]:
    env = os.environ.get("TOOLBELT_SIGNOZ_ENV")
    if env:
        auth.set_env(env)

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--env" and i + 1 < len(argv):
            auth.set_env(argv[i + 1])
            del argv[i : i + 2]
            continue
        if arg.startswith("--env="):
            auth.set_env(arg.split("=", 1)[1])
            del argv[i]
            continue
        i += 1
    return argv


def _resolve_verb(argv: list[str]) -> tuple[str, list[str]] | None:
    """Return (verb_key, remaining_args) for the longest registered match."""
    for n in (3, 2, 1):
        if len(argv) >= n:
            key = "-".join(argv[:n])
            if key in VERBS:
                return key, argv[n:]
    return None


def main(argv: list[str]) -> None:
    argv = _parse_global_flags(list(argv))

    if not argv or argv[0] in ("-h", "--help"):
        cmd_help([])
        return

    resolved = _resolve_verb(argv)
    if resolved:
        verb, rest = resolved
        VERBS[verb](rest)
        return

    print(f"unknown verb: {argv[0]}\n")
    cmd_help([])
    sys.exit(2)


if __name__ == "__main__":
    main(sys.argv[1:])
