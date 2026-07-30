"""Thin GitLab REST v4 wrapper.

Intentionally small: exposes ``get``/``post``/``put`` returning parsed JSON.
All URL building and pretty-printing lives in ``commands.py`` so this file
stays a mechanical HTTP layer.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from common.secrets import load as load_secret
from common import config as _cfg

BASE_URL = _cfg.get("gitlab", "base_url",
                    "https://gitlab.example.com/api/v4",
                    env="TOOLBELT_GITLAB_URL")
DEFAULT_PROJECT_ID = _cfg.get("gitlab", "default_project_id",
                              1,  # myorg/myproj/myrepo
                              env="TOOLBELT_GITLAB_PROJECT_ID")

_token: str | None = None


def _auth_header() -> dict[str, str]:
    global _token
    if _token is None:
        _token = load_secret("gitlab.token")
    return {"PRIVATE-TOKEN": _token}


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = _auth_header()
    body: bytes | None = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        sys.exit(f"[gitlab] HTTP {e.code} on {method} {path}\n  {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"[gitlab] network error on {method} {path}: {e.reason}")
    if not raw:
        return None
    return json.loads(raw)


def get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def get_all(path: str, params: dict | None = None, *, per_page: int = 100) -> list[Any]:
    """Paginate a list endpoint until all pages are fetched."""
    base = dict(params or {})
    base.setdefault("per_page", per_page)
    results: list[Any] = []
    page = 1
    while True:
        batch = get(path, {**base, "page": page})
        if not batch:
            break
        if not isinstance(batch, list):
            sys.exit(f"[gitlab] expected list from GET {path}, got {type(batch).__name__}")
        results.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return results


def post(path: str, json_body: dict | None = None) -> Any:
    return _request("POST", path, json_body=json_body or {})


def put(path: str, json_body: dict | None = None) -> Any:
    return _request("PUT", path, json_body=json_body or {})


def raw_get(path: str) -> str:
    """GET returning raw text (for /trace endpoints)."""
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=_auth_header())
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def project_path(project_id: int | None = None) -> str:
    return f"/projects/{project_id or DEFAULT_PROJECT_ID}"


