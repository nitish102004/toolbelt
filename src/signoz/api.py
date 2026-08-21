"""Thin SignOz REST wrapper with automatic login and 401 retry."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import auth

BASE_URL = auth.BASE_URL


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: Any = None,
    headers: dict[str, str] | None = None,
    _retried: bool = False,
) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

    hdrs = auth.get_auth_headers(force=False)
    hdrs["Accept"] = "application/json"
    if headers:
        hdrs.update(headers)

    body: bytes | None = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 401 and not _retried and auth.load_static_token() is None:
            auth.clear_session()
            return _request(
                method,
                path,
                params=params,
                json_body=json_body,
                headers=headers,
                _retried=True,
            )
        detail = e.read().decode("utf-8", errors="replace")[:500]
        sys.exit(f"[signoz] HTTP {e.code} on {method} {path}\n  {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"[signoz] network error on {method} {path}: {e.reason}")

    if not raw:
        return None
    return json.loads(raw)


def get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def post(path: str, json_body: Any = None) -> Any:
    return _request("POST", path, json_body=json_body if json_body is not None else {})


def put(path: str, json_body: Any = None) -> Any:
    return _request("PUT", path, json_body=json_body if json_body is not None else {})


def patch(path: str, json_body: Any = None) -> Any:
    return _request("PATCH", path, json_body=json_body if json_body is not None else {})


def delete(path: str) -> Any:
    return _request("DELETE", path)


def query_range(body: dict[str, Any]) -> Any:
    """Run a v3 builder query (logs, traces, metrics on v0.73.x)."""
    return post("/api/v3/query_range", body)
