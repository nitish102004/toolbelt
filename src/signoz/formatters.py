"""Human-readable formatters for SignOz query results."""
from __future__ import annotations

import json
import sys
from typing import Any


def _service_name(data: dict[str, Any]) -> str:
    res = data.get("resources_string") or {}
    return str(res.get("service.name") or "?")


def _truncate(text: str, width: int) -> str:
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) <= width:
        return text
    return text[: width - 1] + "\u2026"


def print_log_rows(rows: list[dict[str, Any]], *, full_body: bool = False, fmt: str = "table") -> None:
    if fmt == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    if not rows:
        print("(no logs)")
        return

    if fmt == "raw":
        for row in rows:
            data = row.get("data") or {}
            print(f"--- {row.get('timestamp')}  [{_service_name(data)}] ---")
            print(data.get("body") or "")
            print()
        return

    width = 120 if full_body else 80
    print(f"{'TIMESTAMP':<28} {'SERVICE':<24} {'SEV':<6} BODY")
    print(f"{'-'*28} {'-'*24} {'-'*6} {'-'*40}")
    for row in rows:
        data = row.get("data") or {}
        ts = str(row.get("timestamp") or "")[:28]
        svc = _truncate(_service_name(data), 24)
        sev = str(data.get("severity_text") or "?")[:6]
        body = _truncate(str(data.get("body") or ""), width)
        print(f"{ts:<28} {svc:<24} {sev:<6} {body}")


def print_trace_rows(rows: list[dict[str, Any]], *, fmt: str = "table") -> None:
    if fmt == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    if not rows:
        print("(no traces)")
        return

    print(f"{'TIMESTAMP':<28} {'SERVICE':<24} {'OPERATION':<30} DURATION")
    print(f"{'-'*28} {'-'*24} {'-'*30} {'-'*10}")
    for row in rows:
        data = row.get("data") or row
        ts = str(row.get("timestamp") or data.get("timestamp") or "")[:28]
        svc = _truncate(_service_name(data), 24)
        attrs = data.get("attributes_string") or {}
        op = _truncate(
            str(attrs.get("name") or data.get("name") or attrs.get("operation") or "?"),
            30,
        )
        dur = data.get("durationNano") or attrs.get("durationNano") or data.get("duration") or "?"
        if isinstance(dur, (int, float)) and dur > 1_000_000:
            dur = f"{dur / 1_000_000:.2f}ms"
        print(f"{ts:<28} {svc:<24} {op:<30} {dur}")


def print_metric_series(data: dict[str, Any]) -> None:
    result = (data.get("data") or {}).get("result") or []
    if not result:
        print("(no metric data)")
        return
    for series in result:
        labels = series.get("labels") or series.get("metric") or {}
        label_str = ", ".join(f"{k}={v}" for k, v in labels.items()) if isinstance(labels, dict) else ""
        values = series.get("values") or []
        print(f"series: {label_str or series.get('queryName', 'A')}")
        for point in values[-10:]:
            if isinstance(point, list) and len(point) >= 2:
                print(f"  t={point[0]}  v={point[1]}")
            else:
                print(f"  {point}")
        if len(values) > 10:
            print(f"  ... ({len(values)} points total, showing last 10)")


def extract_list_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    if response.get("status") == "error":
        sys.exit(f"[signoz] query error: {response.get('error', response)}")
    result = (response.get("data") or {}).get("result") or []
    if not result:
        return []
    return list(result[0].get("list") or [])
