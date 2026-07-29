# `conf` -- Confluence Server 7.x CLI

Thin Python wrapper around the Confluence Server REST API. Same
architecture as `gl` and `jira`:

* Token lives in `<SECRETS_DIR>\confluence.token` (owner-only ACL).
  See [`INSTALL.md`](../INSTALL.md) and
  [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) for how `<SECRETS_DIR>` is
  resolved.
* Auth header is `Authorization: Bearer <PAT>`. Never appears on the
  command line.
* No third-party dependencies. Python 3.11 stdlib only. HTML -> text
  rendering uses `html.parser`.

Run `conf help` any time to list verbs, `conf help <verb>` for one verb.

## URL / page-id resolution

Every verb that takes `<id-or-url>` accepts any of these:

```
12345678
https://<confluence-host>/spaces/MYSPACE/pages/12345678/New+Joiners+Onboarding
https://<confluence-host>/spaces/MYSPACE/pages/12345678/foo#anchor
https://<confluence-host>/pages/viewpage.action?pageId=12345678
```

Copy the URL from your browser and paste -- the tool extracts the id.

## Verb reference

### Identity

```
conf me
```

### Reading pages

```
conf page view <id-or-url> [--html|--storage|--raw] [--width N]
conf page url <id-or-url>
conf page open <id-or-url>
conf page children <id-or-url> [--limit N]
conf page comments <id-or-url> [--limit N]
conf page labels <id-or-url>
conf page attachments <id-or-url> [--limit N]
```

* `page view` prints title, id, space, version, breadcrumb, URL, then the
  body rendered to plain text. Flags:
  * `--html` -- raw rendered HTML (`body.view`).
  * `--storage` -- editable XHTML source (`body.storage`).
  * `--raw` -- the full JSON blob from the API.
  * `--width N` -- word-wrap the plain-text output.
* `page url` / `page open` compute or launch the canonical browser URL.
* `page children` lists sub-pages: `ID  TITLE` per line.
* `page comments` prints each comment with author + timestamp, body
  extracted to plain text.
* `page labels` prints comma-separated labels or `(no labels)`.
* `page attachments` prints `ID  SIZE  FILENAME  DOWNLOAD-PATH`.

### Bulk / offline dump

```
conf page download <id-or-url> [--out DIR] [--no-attachments]
```

Creates a directory `<pageId>_<slug>/` under `--out` containing:

| File | Contents |
|---|---|
| `page.txt` | plain-text rendering (best for AI ingestion) |
| `page.html` | rendered HTML (`body.view`) |
| `page.storage.xhtml` | editable storage-format markup |
| `meta.json` | id, title, space, version, timestamp, breadcrumb, URL |
| `attachments/*` | every attachment on the page (skip with `--no-attachments`) |

Filenames are sanitised. Safe to re-run; existing files are overwritten.

### Search

```
conf search "<CQL>" [--limit N]
conf recent [--space KEY] [--days N] [--limit N]
```

* `search` runs any CQL you can write in the Confluence UI advanced
  search. Output rows: `ID  SPACE  MODIFIED  TITLE` with a header.
* `recent` is a shortcut for
  `space = KEY AND type = page AND lastmodified >= now("-Nd")`.
  Defaults: space `MYSPACE`, days `1`, limit `20` -- change the default
  space in `src/conf/api.py` (`DEFAULT_SPACE_KEY`) if yours differs.

**CQL examples that work today:**

```cmd
conf search "space = MYSPACE AND title ~ \"Onboarding\""
conf search "label = runbook AND space = MYSPACE ORDER BY lastmodified DESC"
conf search "creator = currentUser() ORDER BY created DESC" --limit 20
conf search "text ~ \"Cloud Spanner\" AND space = MYSPACE"
conf search "type = blogpost AND space = MYSPACE AND created >= now(\"-30d\")"
```

### Spaces

```
conf space view <KEY>
conf space list [--limit N]
```

### Utility

```
conf api <METHOD> <path> [--json '<json>']   raw REST call, prints JSON
conf docs [--open]              print / open this file
conf help [verb]                list verbs or show one full docstring
```

`conf api` is the escape hatch when you need an endpoint not modeled by
a verb. Path starts with `/`, e.g. `conf api GET /content/12345678`.

## Common workflows

### Read a page from a URL

```cmd
conf page view "https://<confluence-host>/spaces/MYSPACE/pages/12345678/..."
```

### Save a page and all attachments for offline / AI use

```cmd
conf page download 12345678 --out C:\tmp\onboarding
```

### What changed recently

```cmd
conf recent --days 3
conf recent --space MYPROJ --days 7 --limit 50
```

### Find pages by title / label / author

```cmd
conf search "space = MYSPACE AND title ~ \"Onboarding\""
conf search "label = runbook AND space = MYSPACE ORDER BY lastmodified DESC"
conf search "creator = currentUser() ORDER BY created DESC" --limit 20
```

### Walk a page tree

```cmd
conf page children 12345678
```

## Exit codes

* `0` -- success
* `1` -- remote/network failure (surfaced via `[conf] HTTP <code> ...`)
* `2` -- usage error (missing args, unknown verb)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `[secrets] missing file` | PAT not stored yet | run the setup step in [INSTALL.md](../INSTALL.md) |
| `HTTP 401` `Client must be authenticated` | expired / revoked PAT | regenerate PAT in Confluence, overwrite `confluence.token` |
| `HTTP 403` on a page | ACL blocks your account | request access in the Confluence UI |
| `HTTP 404` on `/content/<id>` | wrong id, or page moved / deleted | verify via web UI first |
| Body text looks garbled | Confluence markup uses macros the extractor can't render | fall back to `--html` or `--storage` |

## Design notes

* Deliberately **read-only** in v1. Endpoints for `create` / `update` /
  attach exist and could be added the same way `jira issue create` was
  (~15 LOC), but Confluence storage-format XHTML is finicky; better to
  edit in the web UI until we have a real need.
* Output is designed for humans **and** AI agents: no ANSI colors, one
  row per line, stable field order. Piping to `findstr` / `grep` works.
* No local state, no config file. Every invocation is stateless except
  for reading `confluence.token` once per process.
* HTML -> text is intentionally a small `HTMLParser` subclass (~40 lines)
  rather than pulling in `beautifulsoup4` / `html2text`. Good enough for
  reading; use `--html` for pixel-perfect content.

