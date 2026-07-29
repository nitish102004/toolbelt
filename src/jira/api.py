"""Thin Jira Server REST v2 wrapper.

Mirrors ``gitlab/api.py``: exposes ``get``/``post``/``put`` returning parsed
JSON. All URL building and pretty-printing lives in ``commands.py`` so this
file stays a mechanical HTTP layer.
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

BASE_URL = _cfg.get("jira", "base_url",
                    "https://jira.example.com/rest/api/2",
                    env="TOOLBELT_JIRA_URL")
BROWSE_URL = _cfg.get("jira", "browse_url",
                      "https://jira.example.com/browse",
                      env="TOOLBELT_JIRA_BROWSE_URL")
DEFAULT_PROJECT_KEY = _cfg.get("jira", "default_project_key",
                               "MYPROJ",
                               env="TOOLBELT_JIRA_PROJECT_KEY")

_token: str | None = None


def _auth_header() -> dict[str, str]:
    global _token
    if _token is None:
        _token = load_secret("jira.token")
    return {"Authorization": f"Bearer {_token}"}


def _request(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json_body: Any = None,
) -> Any:
    url = f"{BASE_URL}{path}"
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = _auth_header()
    headers["Accept"] = "application/json"
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
        sys.exit(f"[jira] HTTP {e.code} on {method} {path}\n  {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"[jira] network error on {method} {path}: {e.reason}")
    if not raw:
        return None
    return json.loads(raw)


def get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def post(path: str, json_body: dict | None = None) -> Any:
    return _request("POST", path, json_body=json_body or {})


def post_json(path: str, json_value: Any) -> Any:
    """POST an arbitrary JSON value (string / list / dict). Jira's watchers
    endpoint takes a bare quoted username string, not an object."""
    return _request("POST", path, json_body=json_value)


def put(path: str, json_body: dict | None = None) -> Any:
    return _request("PUT", path, json_body=json_body or {})


def delete(path: str) -> Any:
    return _request("DELETE", path)


def upload(path: str, file_path: str) -> Any:
    """POST a file as ``multipart/form-data`` (Jira attachment endpoint).

    Jira requires the ``X-Atlassian-Token: no-check`` header to bypass XSRF
    on file uploads. Uses a hand-rolled multipart body to avoid a
    ``requests`` dependency.
    """
    import os
    import uuid
    boundary = f"----jiraCliBoundary{uuid.uuid4().hex}"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as fh:
        file_bytes = fh.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    headers = _auth_header()
    headers["Accept"] = "application/json"
    headers["X-Atlassian-Token"] = "no-check"
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, method="POST",
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        sys.exit(f"[jira] HTTP {e.code} on POST {path}\n  {detail}")
    return json.loads(raw) if raw else None


def browse_url(key: str) -> str:
    return f"{BROWSE_URL}/{key}"





