# SignOz (`soz` / `sozp` / `sozj`)

CLI for [SignOz](https://signoz.io/) — logs, traces, metrics, alerts, and
dashboards. Supports automatic login from locally stored credentials and
transparent re-login on API `401` responses.

| Env | URL | CLI |
|-----|-----|-----|
| **prod** (default, juno) | `logs.juno.lenskart.com` | `soz` |
| **preprod** | `logs.preprod.lenskart.com` | `sozp` or `soz --env preprod` |
| **jj** (JJ/common prod) | `logs-common-sgn.lenskart.com` | `sozj` or `soz --env jj` |

All envs share `signoz.credentials` but keep separate session caches.

## Setup

1. Add `bin/` to your `PATH` (see [INSTALL.md](../INSTALL.md)).

2. Create credentials in your secrets directory (default `~/.toolbelt/`):

```json
{
  "email": "you@example.com",
  "password": "your-password"
}
```

Save as `~/.toolbelt/signoz.credentials` and restrict permissions:

```bash
chmod 600 ~/.toolbelt/signoz.credentials
```

3. Point at your instance (optional if the built-in default matches):

```toml
# ~/.toolbelt/config.toml
[signoz]
base_url = "https://signoz.example.com"
```

4. Login once (optional — any command auto-logins if needed):

```bash
soz auth login
soz me
```

### Optional: static token / API key

If you have a long-lived `SIGNOZ-API-KEY` or manual JWT, put it in
`~/.toolbelt/signoz.token` (one line). This overrides the credentials flow.

## Auth behaviour

| File | Purpose |
|------|---------|
| `signoz.credentials` | Email + password JSON for `POST /api/v1/login` (shared all envs) |
| `signoz.session` | Juno prod cached `accessJwt`, `refreshJwt`, expiry (auto-written) |
| `signoz.preprod.session` | Preprod cached session (auto-written) |
| `signoz.jj.session` | JJ/common prod cached session (auto-written) |
| `signoz.token` | Optional static API key or JWT override |

On each API call:

1. Use `signoz.token` if present.
2. Else reuse cached `accessJwt` if not expired.
3. Else try refresh (`/api/v2/sessions/rotate` when available).
4. Else re-login with `signoz.credentials`.
5. On HTTP `401`, clear session and repeat from step 2 once.

## Verbs

### Meta / auth

```
soz me                     current user (JWT claims)
soz health                 GET /api/v1/health
soz version                GET /api/v1/version
soz auth status            credential + session state
soz auth login             force login, update signoz.session
soz auth logout            delete cached session
soz api <METHOD> <path>    raw REST call
soz help [verb]
soz docs [--open]
```

### Logs

```
soz logs tail [--service S] [--exclude-service S] [--since 15m] [--limit N]
soz logs search <text> [--service S] [--since 1h] [--limit N]
soz logs errors [--service S] [--since 30m] [--limit N]
soz logs trace <traceId> [--since 6h] [--limit N]
soz logs services [--search text]
soz autocomplete values <key> [--data-source logs] [--search text]
```

Shared flags: `--format table|json|raw`, `--full-body`, `--start`, `--end`

### Traces

```
soz traces search [--service S] [--since 1h] [--limit N]
soz traces view <traceId> [--since 6h]
```

### Metrics

```
soz metrics query <metricName> [--since 6h] [--step 60]
```

### Alerts & dashboards

```
soz rule list [--search text]
soz alert list
soz dashboard list
```

## Examples

```bash
soz auth status
soz logs tail --service my-api --since 15m
soz logs search "error" --service checkout --since 1h
soz api POST /api/v3/query_range --file query.json
```

## Config

Optional sections in `~/.toolbelt/config.toml`:

```toml
[signoz]
base_url = "https://logs.juno.lenskart.com"

[signoz_preprod]
base_url = "https://logs.preprod.lenskart.com"

[signoz_jj]
base_url = "https://logs-common-sgn.lenskart.com"
```

Overrides:

* `TOOLBELT_SIGNOZ_URL` — juno prod base URL
* `TOOLBELT_SIGNOZ_PREPROD_URL` — preprod base URL
* `TOOLBELT_SIGNOZ_JJ_URL` — JJ/common prod base URL
* `TOOLBELT_SIGNOZ_ENV=preprod|jj` — switch env (same as `sozp` / `sozj` or `--env`)

## Security

* Never commit `signoz.credentials` or session files.
* Prefer a SignOz API key in `signoz.token` for automation when available.
