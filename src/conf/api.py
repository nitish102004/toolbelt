"""Thin Confluence Server REST wrapper.

Mirrors ``jira/api.py``: exposes ``get``/``post``/``put``/``delete`` returning
parsed JSON, plus ``download_binary`` for attachment payloads. All URL
building and pretty-printing lives in ``commands.py`` so this file stays a
mechanical HTTP layer.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from common.secrets import load as load_secret
from common import config as _cfg

HOST = _cfg.get("conf", "host",
                "https://confluence.example.com",
                env="TOOLBELT_CONF_HOST")
BASE_URL = _cfg.get("conf", "base_url",
                    f"{HOST}/rest/api",
                    env="TOOLBELT_CONF_URL")
DEFAULT_SPACE_KEY = _cfg.get("conf", "default_space_key",
                             "MYSPACE",
                             env="TOOLBELT_CONF_SPACE_KEY")

_token: str | None = None


def _auth_header() -> dict[str, str]:
    global _token
    if _token is None:
        _token = load_secret("confluence.token")
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
        sys.exit(f"[conf] HTTP {e.code} on {method} {path}\n  {detail}")
    except urllib.error.URLError as e:
        sys.exit(f"[conf] network error on {method} {path}: {e.reason}")
    if not raw:
        return None
    return json.loads(raw)


def get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params=params)


def post(path: str, json_body: dict | None = None) -> Any:
    return _request("POST", path, json_body=json_body or {})


def put(path: str, json_body: dict | None = None) -> Any:
    return _request("PUT", path, json_body=json_body or {})


def delete(path: str) -> Any:
    return _request("DELETE", path)


def download_binary(absolute_or_relative_url: str, out_path: str) -> int:
    """GET a binary URL (e.g. attachment download link) and write to disk.

    Confluence attachment ``_links.download`` values are host-relative
    (``/download/attachments/...``) so we prepend HOST when needed.
    Returns bytes written.
    """
    url = (absolute_or_relative_url
           if absolute_or_relative_url.startswith("http")
           else f"{HOST}{absolute_or_relative_url}")
    req = urllib.request.Request(url, headers=_auth_header())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(out_path, "wb") as fh:
            data = resp.read()
            fh.write(data)
            return len(data)
    except urllib.error.HTTPError as e:
        sys.exit(f"[conf] HTTP {e.code} downloading {url}")


# --------------------------------------------------------------------------
# URL / ID resolver -- users copy URLs, not IDs.
# --------------------------------------------------------------------------

_PAGE_ID_PATTERNS = (
    re.compile(r"/pages/(\d+)"),
    re.compile(r"[?&]pageId=(\d+)"),
)


def resolve_page_id(url_or_id: str) -> str:
    """Extract a Confluence pageId from a URL or accept a bare numeric id."""
    if url_or_id.isdigit():
        return url_or_id
    for pat in _PAGE_ID_PATTERNS:
        m = pat.search(url_or_id)
        if m:
            return m.group(1)
    sys.exit(f"[conf] could not extract pageId from: {url_or_id}")


def browse_url(page_id: str, title: str | None = None, space_key: str | None = None) -> str:
    if space_key and title:
        slug = urllib.parse.quote(title.replace(" ", "+"), safe="+")
        return f"{HOST}/spaces/{space_key}/pages/{page_id}/{slug}"
    return f"{HOST}/pages/viewpage.action?pageId={page_id}"


