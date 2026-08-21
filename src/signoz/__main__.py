"""Entry point: ``python -m signoz <verb> [args]``.

Supports multi-word verbs: ``logs tail``, ``logs-tail``, ``traces view``, etc.
"""
from __future__ import annotations

import sys

from .commands import VERBS, cmd_help


def _resolve_verb(argv: list[str]) -> tuple[str, list[str]] | None:
    """Return (verb_key, remaining_args) for the longest registered match."""
    for n in (3, 2, 1):
        if len(argv) >= n:
            key = "-".join(argv[:n])
            if key in VERBS:
                return key, argv[n:]
    return None


def main(argv: list[str]) -> None:
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
