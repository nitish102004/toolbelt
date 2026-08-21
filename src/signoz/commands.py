"""Verb implementations for the ``soz`` CLI."""
from __future__ import annotations

import json
import os
import sys

from typing import Any

from . import api, auth
from . import formatters as fmt
from . import query_v3 as qv
from . import autocomplete as ac
from .time_range import resolve_range


def _flag(args: list[str], name: str, default: str | None = None) -> str | None:
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            val = args[i + 1]
            del args[i:i + 2]
            return val
        if a.startswith(name + "="):
            val = a.split("=", 1)[1]
            del args[i]
            return val
    return default


def _has_flag(args: list[str], name: str) -> bool:
    if name in args:
        args.remove(name)
        return True
    return False


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _output_fmt(args: list[str]) -> str:
    return _flag(args, "--format", "table") or "table"


def _query_common_flags(args: list[str], *, default_since: str) -> tuple[int, int, int, str, bool]:
    since = _flag(args, "--since", default_since)
    start = _flag(args, "--start")
    end = _flag(args, "--end")
    limit = int(_flag(args, "--limit", "50") or 50)
    fmt = _output_fmt(args)
    full_body = _has_flag(args, "--full-body")
    start_ms, end_ms = resolve_range(since=since, start=start, end=end, default_since=default_since)
    return start_ms, end_ms, limit, fmt, full_body


def _service_filters(args: list[str]) -> list[dict]:
    filters: list[dict] = []
    service = _flag(args, "--service")
    exclude = _flag(args, "--exclude-service")
    if service:
        filters.append(qv.service_equals(service))
    if exclude:
        filters.extend(qv.service_not_in([s.strip() for s in exclude.split(",") if s.strip()]))
    return filters


def _run_logs_query(
    args: list[str],
    *,
    default_since: str,
    extra_filters: list[dict] | None = None,
) -> None:
    start_ms, end_ms, limit, out_fmt, full_body = _query_common_flags(args, default_since=default_since)
    filters = _service_filters(args) + list(extra_filters or [])
    body = qv.logs_list_query(start_ms, end_ms, filters=filters, limit=limit)
    resp = api.query_range(body)
    rows = fmt.extract_list_rows(resp)
    print(f"found: {len(rows)} log(s)\n")
    fmt.print_log_rows(rows, full_body=full_body, fmt=out_fmt)


# ---------- meta -------------------------------------------------------------

def cmd_me(_: list[str]) -> None:
    """soz me  -- current user (sanity-check auth)."""
    session = auth.ensure_session()
    token = session.get("accessJwt", "")
    claims = auth._jwt_claims(str(token)) if isinstance(token, str) else {}
    if claims.get("email"):
        print(
            f"{claims.get('email')}  orgId={claims.get('orgId', '?')}  "
            f"userId={claims.get('id', session.get('userId', '?'))}"
        )
        return
    for path in ("/api/v1/user", "/api/v1/user/me"):
        try:
            u = api.get(path)
        except SystemExit:
            continue
        if isinstance(u, dict):
            data = u.get("data", u)
            if isinstance(data, dict):
                print(json.dumps(data, indent=2))
                return
    print(f"userId={session.get('userId', '?')}  (JWT claims unavailable)")


def cmd_health(_: list[str]) -> None:
    """soz health  -- SignOz health check."""
    data = api.get("/api/v1/health")
    print(json.dumps(data, indent=2))


def cmd_version(_: list[str]) -> None:
    """soz version  -- SignOz server version."""
    data = api.get("/api/v1/version")
    if isinstance(data, dict):
        print(f"version={data.get('version')}  ee={data.get('ee')}  setupCompleted={data.get('setupCompleted')}")
    else:
        print(json.dumps(data, indent=2))


def cmd_auth_status(_: list[str]) -> None:
    """soz auth status  -- show credential/session state and token expiry."""
    for line in auth.auth_status_lines():
        print(line)


def cmd_auth_login(_: list[str]) -> None:
    """soz auth login  -- login with signoz.credentials and cache session."""
    import time

    session = auth.login_with_credentials()
    exp = auth._access_expiry(session)
    print("login OK")
    if isinstance(exp, int):
        print(f"access token expires: {exp}  (~{(exp - int(time.time())) // 60}m)")


def cmd_auth_logout(_: list[str]) -> None:
    """soz auth logout  -- delete cached session (credentials file kept)."""
    auth.clear_session()
    print("session cleared")


def cmd_api(args: list[str]) -> None:
    """soz api <METHOD> <path> [--json '{...}' | --file path] [--param k=v ...]

    Raw REST call against SignOz. Path must start with '/'.
    Auth is applied automatically; on 401 the client re-logins once.
    """
    if len(args) < 2:
        _die("usage: soz api <GET|POST|PUT|PATCH|DELETE> <path> [--json '{...}' | --file path]")

    method = args[0].upper()
    path = args[1]
    json_body = None

    if "--file" in args:
        file_path = _flag(args, "--file")
        if not file_path:
            _die("usage: --file requires a path")
        with open(file_path, encoding="utf-8") as fh:
            json_body = json.load(fh)
    elif "--json" in args:
        raw = _flag(args, "--json")
        if raw is None:
            _die("usage: --json requires a JSON string")
        json_body = json.loads(raw)

    params: dict[str, str] = {}
    i = 0
    tail = args[2:]
    while i < len(tail):
        if tail[i] == "--param" and i + 1 < len(tail):
            k, _, v = tail[i + 1].partition("=")
            params[k] = v
            i += 2
        else:
            i += 1

    if method == "GET":
        result = api.get(path, params or None)
    elif method == "POST":
        result = api.post(path, json_body)
    elif method == "PUT":
        result = api.put(path, json_body)
    elif method == "PATCH":
        result = api.patch(path, json_body)
    elif method == "DELETE":
        result = api.delete(path)
    else:
        _die(f"unsupported method: {method}")

    print(json.dumps(result, indent=2, ensure_ascii=False) if result is not None else "(no body)")


# ---------- logs -------------------------------------------------------------

def cmd_logs_tail(args: list[str]) -> None:
    """soz logs tail [--service S] [--exclude-service S] [--since 15m] [--limit N] [--format table|json|raw]"""
    _run_logs_query(args, default_since="15m")


def cmd_logs_search(args: list[str]) -> None:
    """soz logs search <text> [--service S] [--since 1h] [--limit N] [--format table|json|raw]"""
    if not args or args[0].startswith("-"):
        _die("usage: soz logs search <text> [--service S] [--since 1h]")
    text = args[0]
    del args[0]
    _run_logs_query(args, default_since="1h", extra_filters=[qv.body_contains(text)])


def cmd_logs_errors(args: list[str]) -> None:
    """soz logs errors [--service S] [--since 30m] [--limit N] [--format table|json|raw]"""
    _run_logs_query(
        args,
        default_since="30m",
        extra_filters=[qv.severity_in(["ERROR", "FATAL", "CRITICAL"])],
    )


def cmd_logs_trace(args: list[str]) -> None:
    """soz logs trace <traceId> [--since 6h] [--limit N] [--format table|json|raw]"""
    if not args or args[0].startswith("-"):
        _die("usage: soz logs trace <traceId> [--since 6h]")
    trace_id = args[0]
    del args[0]
    _run_logs_query(
        args,
        default_since="6h",
        extra_filters=[qv.trace_id_attr_equals(trace_id)],
    )


def cmd_logs_services(args: list[str]) -> None:
    """soz logs services [--search text] [--format table|json]

    List distinct service.name values for logs (SignOz autocomplete API).
    """
    search = _flag(args, "--search", "") or ""
    out_fmt = _output_fmt(args)
    try:
        values = ac.attribute_values(
            "service.name",
            data_source="logs",
            search_text=search,
            tag_type="resource",
        )
    except RuntimeError as exc:
        _die(f"[signoz] autocomplete failed: {exc}", code=1)
    print(f"found: {len(values)} service(s)\n")
    if out_fmt == "json":
        print(json.dumps(values, indent=2))
        return
    if not values:
        print("(none)")
        return
    for name in values:
        print(name)


def cmd_autocomplete_values(args: list[str]) -> None:
    """soz autocomplete values <attributeKey> [--data-source logs|traces|metrics] [--search text] [--tag-type resource|tag] [--format table|json]

    List autocomplete values for any attribute key.
    """
    if not args or args[0].startswith("-"):
        _die("usage: soz autocomplete values <attributeKey> [--data-source logs] [--search text]")
    key = args[0]
    del args[0]
    data_source = _flag(args, "--data-source", "logs") or "logs"
    search = _flag(args, "--search", "") or ""
    tag_type = _flag(args, "--tag-type", "resource") or "resource"
    out_fmt = _output_fmt(args)
    try:
        values = ac.attribute_values(
            key,
            data_source=data_source,
            search_text=search,
            tag_type=tag_type,
        )
    except RuntimeError as exc:
        _die(f"[signoz] autocomplete failed: {exc}", code=1)
    print(f"found: {len(values)} value(s) for {key!r}\n")
    if out_fmt == "json":
        print(json.dumps(values, indent=2))
        return
    for val in values:
        print(val)


# ---------- traces -----------------------------------------------------------

def cmd_traces_search(args: list[str]) -> None:
    """soz traces search [--service S] [--since 1h] [--limit N] [--format table|json]"""
    start_ms, end_ms, limit, out_fmt, _ = _query_common_flags(args, default_since="1h")
    filters = _service_filters(args)
    body = qv.traces_list_query(start_ms, end_ms, filters=filters, limit=limit)
    resp = api.query_range(body)
    rows = fmt.extract_list_rows(resp)
    print(f"found: {len(rows)} trace span(s)\n")
    fmt.print_trace_rows(rows, fmt=out_fmt)


def cmd_traces_view(args: list[str]) -> None:
    """soz traces view <traceId> [--since 6h] [--format table|json]"""
    if not args or args[0].startswith("-"):
        _die("usage: soz traces view <traceId> [--since 6h]")
    trace_id = args[0]
    del args[0]
    start_ms, end_ms, limit, out_fmt, _ = _query_common_flags(args, default_since="6h")
    filters = [qv.trace_id_equals(trace_id)] + _service_filters(args)
    body = qv.traces_list_query(start_ms, end_ms, filters=filters, limit=limit)
    resp = api.query_range(body)
    rows = fmt.extract_list_rows(resp)
    print(f"trace {trace_id}: {len(rows)} span(s)\n")
    fmt.print_trace_rows(rows, fmt=out_fmt)


# ---------- metrics ----------------------------------------------------------

def cmd_metrics_query(args: list[str]) -> None:
    """soz metrics query <metricName> [--since 6h] [--step 60] [--format json]"""
    if not args or args[0].startswith("-"):
        _die("usage: soz metrics query <metricName> [--since 6h] [--step 60]")
    metric = args[0]
    del args[0]
    since = _flag(args, "--since", "6h")
    step = int(_flag(args, "--step", "60") or 60)
    out_fmt = _output_fmt(args)
    start_ms, end_ms = resolve_range(since=since, default_since="6h")
    body = qv.metrics_graph_query(start_ms, end_ms, metric, step_interval=step)
    resp = api.query_range(body)
    if out_fmt == "json":
        print(json.dumps(resp, indent=2, ensure_ascii=False))
    else:
        fmt.print_metric_series(resp)


# ---------- alerts / dashboards ----------------------------------------------

def _unwrap_list(data: Any, *keys: str) -> list[Any]:
    cur: Any = data
    if isinstance(cur, dict) and "data" in cur:
        cur = cur["data"]
    if isinstance(cur, str):
        try:
            cur = json.loads(cur)
        except json.JSONDecodeError:
            return []
    if isinstance(cur, dict):
        for key in keys:
            if key in cur and isinstance(cur[key], list):
                return cur[key]
        if "rules" in cur:
            return cur["rules"]
    if isinstance(cur, list):
        return cur
    return []


def cmd_rule_list(args: list[str]) -> None:
    """soz rule list [--search text] [--format table|json]"""
    search = (_flag(args, "--search") or "").lower()
    out_fmt = _output_fmt(args)
    data = api.get("/api/v1/rules")
    rules = _unwrap_list(data, "rules")
    if search:
        rules = [
            r for r in rules
            if search in str(r.get("alert", r.get("alertName", ""))).lower()
            or search in str(r.get("alertType", "")).lower()
        ]
    print(f"found: {len(rules)} rule(s)\n")
    if out_fmt == "json":
        print(json.dumps(rules, indent=2, ensure_ascii=False))
        return
    if not rules:
        print("(no rules)")
        return
    print(f"{'ID':<38} {'STATE':<10} {'SEVERITY':<10} ALERT")
    print(f"{'-'*38} {'-'*10} {'-'*10} {'-'*30}")
    for r in rules:
        rid = str(r.get("id", "?"))[:38]
        state = str(r.get("state", r.get("status", "?")))[:10]
        labels = r.get("labels") or {}
        sev = str(r.get("severity", labels.get("severity", "?")))[:10]
        name = str(r.get("alert", r.get("alertName", "?")))[:60]
        print(f"{rid:<38} {state:<10} {sev:<10} {name}")


def cmd_alert_list(args: list[str]) -> None:
    """soz alert list [--format table|json]  -- currently firing alerts."""
    out_fmt = _output_fmt(args)
    data = api.get("/api/v1/alerts")
    alerts = _unwrap_list(data, "data")
    print(f"firing: {len(alerts)} alert(s)\n")
    if out_fmt == "json":
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
        return
    if not alerts:
        print("(none firing)")
        return
    for a in alerts:
        labels = a.get("labels") or {}
        status = a.get("status") or {}
        state = status.get("state") if isinstance(status, dict) else status
        print(f"- {labels.get('alertname', '?')}  severity={labels.get('severity', '?')}  state={state}")


def cmd_dashboard_list(args: list[str]) -> None:
    """soz dashboard list [--format table|json]"""
    out_fmt = _output_fmt(args)
    data = api.get("/api/v1/dashboards")
    boards = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else [])
    if not isinstance(boards, list):
        print(json.dumps(data, indent=2))
        return
    print(f"found: {len(boards)} dashboard(s)\n")
    if out_fmt == "json":
        print(json.dumps(boards, indent=2, ensure_ascii=False))
        return
    if not boards:
        print("(no dashboards)")
        return
    print(f"{'UUID':<38} TITLE")
    print(f"{'-'*38} {'-'*40}")
    for d in boards:
        uid = str(d.get("uuid", d.get("id", "?")))[:38]
        title = str(d.get("title", d.get("data", {}).get("title", "?")))[:60]
        print(f"{uid:<38} {title}")


# ---------- help / docs ------------------------------------------------------

def cmd_help(args: list[str]) -> None:
    """soz help [verb]  -- list verbs or show usage for one verb."""
    if args:
        name = args[0].replace(" ", "-")
        if name not in VERBS and len(args) >= 2:
            name = f"{args[0]}-{args[1]}"
        if name not in VERBS and len(args) >= 3:
            name = f"{args[0]}-{args[1]}-{args[2]}"
        fn = VERBS.get(name)
        if fn and fn.__doc__:
            print(fn.__doc__.strip())
            return
        _die(f"unknown verb: {name}")

    print("SignOz CLI (soz)\n")
    for key in sorted(k for k in VERBS if k != "help"):
        fn = VERBS[key]
        first = (fn.__doc__ or key).strip().splitlines()[0]
        print(f"  {first}")


def cmd_docs(args: list[str]) -> None:
    """soz docs [--open]  -- print path to docs/signoz.md."""
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs", "signoz.md")
    )
    print(path)
    if "--open" in args and os.name == "nt":
        os.startfile(path)  # noqa: S606


VERBS = {
    "me": cmd_me,
    "health": cmd_health,
    "version": cmd_version,
    "auth-status": cmd_auth_status,
    "auth-login": cmd_auth_login,
    "auth-logout": cmd_auth_logout,
    "api": cmd_api,
    "logs-tail": cmd_logs_tail,
    "logs-search": cmd_logs_search,
    "logs-errors": cmd_logs_errors,
    "logs-trace": cmd_logs_trace,
    "logs-services": cmd_logs_services,
    "autocomplete-values": cmd_autocomplete_values,
    "traces-search": cmd_traces_search,
    "traces-view": cmd_traces_view,
    "metrics-query": cmd_metrics_query,
    "rule-list": cmd_rule_list,
    "alert-list": cmd_alert_list,
    "dashboard-list": cmd_dashboard_list,
    "help": cmd_help,
    "docs": cmd_docs,
}
