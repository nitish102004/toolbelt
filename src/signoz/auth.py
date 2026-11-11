"""SignOz authentication: credentials, session cache, and auto-login.

Secrets live under ``<SECRETS_DIR>/`` (see ``common.secrets``):

* ``signoz.credentials`` — JSON ``{"email": "...", "password": "..."}`` (shared)
* ``signoz.session``     — juno prod cached tokens (auto-managed)
* ``signoz.preprod.session`` — preprod cached tokens (auto-managed)
* ``signoz.jj.session``  — JJ/common prod cached tokens (auto-managed)
* ``signoz.token``       — optional static API key or manual JWT override

When ``signoz.token`` exists it wins over the session cache. Otherwise the
client reuses ``accessJwt`` until ``accessJwtExpiry``, then re-logins via
``POST /api/v1/login``. Newer SignOz builds may also rotate via
``POST /api/v2/sessions/rotate`` when a refresh token is present.

Use ``--env preprod|jj`` or ``TOOLBELT_SIGNOZ_ENV`` (or ``sozp`` / ``sozj``
wrappers) to target other instances. Default env is juno prod
(``logs.juno.lenskart.com``). JJ/common prod is ``logs-common-sgn.lenskart.com``.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from common import config as _cfg
from common.secrets import SECRETS_DIR

PROD_DEFAULT_URL = "https://logs.juno.lenskart.com"
PREPROD_DEFAULT_URL = "https://logs.preprod.lenskart.com"
JJ_DEFAULT_URL = "https://logs-common-sgn.lenskart.com"

ENVIRONMENTS: dict[str, dict[str, str]] = {
    "prod": {
        "default_url": PROD_DEFAULT_URL,
        "session": "signoz.session",
        "config_section": "signoz",
        "env_url": "TOOLBELT_SIGNOZ_URL",
        "cli_hint": "soz auth login",
    },
    "preprod": {
        "default_url": PREPROD_DEFAULT_URL,
        "session": "signoz.preprod.session",
        "config_section": "signoz_preprod",
        "env_url": "TOOLBELT_SIGNOZ_PREPROD_URL",
        "cli_hint": "sozp auth login",
    },
    "jj": {
        "default_url": JJ_DEFAULT_URL,
        "session": "signoz.jj.session",
        "config_section": "signoz_jj",
        "env_url": "TOOLBELT_SIGNOZ_JJ_URL",
        "cli_hint": "sozj auth login",
    },
}

CREDENTIALS_NAME = "signoz.credentials"
TOKEN_NAME = "signoz.token"

_ACCESS_SKEW_SEC = 60

_current_env = os.environ.get("TOOLBELT_SIGNOZ_ENV", "prod").strip().lower()
if _current_env not in ENVIRONMENTS:
    _current_env = "prod"


def set_env(name: str) -> None:
    """Switch active SignOz instance (prod, preprod, or jj)."""
    global _current_env
    env = name.strip().lower()
    if env not in ENVIRONMENTS:
        known = ", ".join(sorted(ENVIRONMENTS))
        sys.exit(f"[signoz] unknown env {name!r}; use one of: {known}")
    _current_env = env


def get_env() -> str:
    return _current_env


def get_base_url() -> str:
    meta = ENVIRONMENTS[_current_env]
    return _cfg.get(
        meta["config_section"],
        "base_url",
        meta["default_url"],
        env=meta["env_url"],
    )


def _session_name() -> str:
    return ENVIRONMENTS[_current_env]["session"]


def _path(name: str) -> Path:
    return SECRETS_DIR / name


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def load_static_token() -> str | None:
    path = _path(TOKEN_NAME)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def load_credentials() -> dict[str, str]:
    path = _path(CREDENTIALS_NAME)
    if not path.exists():
        sys.exit(
            f"[signoz] missing credentials file: {path}\n"
            f"  create JSON: {{\"email\": \"you@company.com\", \"password\": \"...\"}}\n"
            f"  or place a static token/API key in {_path(TOKEN_NAME)}"
        )
    data = _read_json(path)
    if not data or not data.get("email") or not data.get("password"):
        sys.exit(
            f"[signoz] invalid credentials file: {path}\n"
            f"  expected JSON with \"email\" and \"password\" keys."
        )
    return {"email": str(data["email"]), "password": str(data["password"])}


def load_session() -> dict[str, Any] | None:
    return _read_json(_path(_session_name()))


def save_session(data: dict[str, Any]) -> None:
    _write_json(_path(_session_name()), data)


def clear_session() -> None:
    path = _path(_session_name())
    if path.exists():
        path.unlink()


def _jwt_claims(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(raw)
    except (IndexError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _access_expiry(session: dict[str, Any]) -> int | None:
    exp = session.get("accessJwtExpiry")
    if isinstance(exp, int):
        return exp
    token = session.get("accessJwt")
    if isinstance(token, str):
        claims = _jwt_claims(token)
        if isinstance(claims.get("exp"), int):
            return claims["exp"]
    return None


def access_token_valid(session: dict[str, Any], *, skew_sec: int = _ACCESS_SKEW_SEC) -> bool:
    token = session.get("accessJwt")
    if not isinstance(token, str) or not token:
        return False
    exp = _access_expiry(session)
    if exp is None:
        return False
    return time.time() < exp - skew_sec


def _auth_headers(token: str) -> dict[str, str]:
    if token.startswith("eyJ"):
        return {"Authorization": f"Bearer {token}"}
    return {"SIGNOZ-API-KEY": token}


def _post_json(path: str, body: dict[str, Any], *, headers: dict[str, str] | None = None) -> Any:
    url = f"{get_base_url()}{path}"
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers=hdrs,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code} on POST {path}\n  {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"network error on POST {path}: {e.reason}") from e
    if not raw:
        return None
    return json.loads(raw)


def login_with_credentials() -> dict[str, Any]:
    creds = load_credentials()
    data = _post_json("/api/v1/login", creds)
    if not isinstance(data, dict) or not data.get("accessJwt"):
        sys.exit("[signoz] login succeeded but response missing accessJwt")
    save_session(data)
    return data


def try_rotate_session(session: dict[str, Any]) -> dict[str, Any] | None:
    refresh = session.get("refreshJwt")
    if not isinstance(refresh, str) or not refresh:
        return None
    for path, body in (
        ("/api/v2/sessions/rotate", {"refreshToken": refresh}),
        ("/api/v1/refresh", {"refreshJwt": refresh}),
    ):
        try:
            data = _post_json(path, body)
        except RuntimeError:
            continue
        if not isinstance(data, dict):
            continue
        merged = dict(session)
        if data.get("accessJwt"):
            merged.update(data)
            save_session(merged)
            return merged
        nested = data.get("data")
        if isinstance(nested, dict):
            mapped = dict(session)
            if nested.get("accessToken"):
                mapped["accessJwt"] = nested["accessToken"]
            if nested.get("refreshToken"):
                mapped["refreshJwt"] = nested["refreshToken"]
            if nested.get("expiresIn") and isinstance(mapped.get("accessJwt"), str):
                mapped["accessJwtExpiry"] = int(time.time()) + int(nested["expiresIn"])
            if mapped.get("accessJwt"):
                save_session(mapped)
                return mapped
    return None


def ensure_session(*, force: bool = False) -> dict[str, Any]:
    static = load_static_token()
    if static:
        return {"accessJwt": static, "source": "signoz.token"}

    session = load_session()
    if not force and session and access_token_valid(session):
        return session

    if session and not force:
        rotated = try_rotate_session(session)
        if rotated and access_token_valid(rotated):
            return rotated

    return login_with_credentials()


def get_auth_headers(*, force: bool = False) -> dict[str, str]:
    session = ensure_session(force=force)
    token = session.get("accessJwt")
    if not isinstance(token, str) or not token:
        sys.exit("[signoz] no access token available after login")
    return _auth_headers(token)


def auth_status_lines() -> list[str]:
    session_name = _session_name()
    lines = [
        f"Env     {_current_env}",
        f"SignOz  {get_base_url()}",
    ]
    static = load_static_token()
    if static:
        kind = "Bearer JWT" if static.startswith("eyJ") else "API key"
        lines.append(f"Auth    {kind}  (from {TOKEN_NAME})")
        if static.startswith("eyJ"):
            claims = _jwt_claims(static)
            if claims.get("email"):
                lines.append(f"Email   {claims['email']}")
            exp = claims.get("exp")
            if isinstance(exp, int):
                remaining = exp - int(time.time())
                lines.append(f"Expires {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp))}  ({remaining // 60}m left)")
        return lines

    cred_path = _path(CREDENTIALS_NAME)
    if cred_path.exists():
        lines.append(f"Creds   {cred_path.name}  (present, shared)")
    else:
        lines.append(f"Creds   missing ({CREDENTIALS_NAME})")

    session = load_session()
    if session and session.get("accessJwt"):
        valid = access_token_valid(session)
        lines.append(f"Session {session_name}  ({'valid' if valid else 'expired'})")
        claims = _jwt_claims(str(session.get("accessJwt", "")))
        if claims.get("email"):
            lines.append(f"Email   {claims['email']}")
        exp = _access_expiry(session)
        if isinstance(exp, int):
            remaining = exp - int(time.time())
            lines.append(
                f"Expires {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(exp))}  ({remaining // 60}m left)"
            )
    else:
        hint = ENVIRONMENTS[_current_env].get("cli_hint", "soz auth login")
        lines.append(f"Session not cached — run `{hint}` or `soz --env {_current_env} auth login`")
    return lines
