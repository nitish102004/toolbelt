"""Entry point: ``python -m conf <verb> [args]``.

Supports both hyphenated (``page-view``) and two-word (``page view``) forms so
the CLI reads naturally either way.
"""
from __future__ import annotations

import sys

from .commands import VERBS, cmd_help


def main(argv: list[str]) -> None:
    if not argv or argv[0] in ("-h", "--help"):
        cmd_help([])
        return

    if len(argv) >= 2:
        two_word = f"{argv[0]}-{argv[1]}"
        if two_word in VERBS:
            VERBS[two_word](argv[2:])
            return

    verb = argv[0]
    if verb not in VERBS:
        print(f"unknown verb: {verb}\n")
        cmd_help([])
        sys.exit(2)
    VERBS[verb](argv[1:])


if __name__ == "__main__":
    main(sys.argv[1:])

