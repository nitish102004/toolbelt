"""Parse --since / --start / --end into millisecond epoch bounds."""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone

_SINCE_RE = re.compile(r"^(\d+)(m|h|d)$", re.IGNORECASE)


def _parse_epoch_ms(value: str) -> int:
    if value.isdigit():
        n = int(value)
        return n if n > 10_000_000_000 else n * 1000
    try:
        if value.endswith("Z"):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError as exc:
        sys.exit(f"[signoz] invalid time value: {value!r} ({exc})")


def parse_since(since: str) -> tuple[int, int]:
    m = _SINCE_RE.match(since.strip())
    if not m:
        sys.exit(f"[signoz] invalid --since {since!r}; use e.g. 15m, 1h, 6h, 24h, 7d")
    amount, unit = int(m.group(1)), m.group(2).lower()
    seconds = amount * {"m": 60, "h": 3600, "d": 86400}[unit]
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - seconds * 1000
    return start_ms, end_ms


def resolve_range(
    *,
    since: str | None = None,
    start: str | None = None,
    end: str | None = None,
    default_since: str = "15m",
) -> tuple[int, int]:
    if start or end:
        if not start or not end:
            sys.exit("[signoz] --start and --end must be used together")
        return _parse_epoch_ms(start), _parse_epoch_ms(end)
    return parse_since(since or default_since)
