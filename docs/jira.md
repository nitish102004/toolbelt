# `jira` -- Jira Server 9.x CLI

Thin Python wrapper around the Jira Server REST v2 API at
`https://jira.example.com`. Same architecture as `gl`:

* Token lives in `<SECRETS_DIR>\jira.token` (owner-only ACL). See
  [`INSTALL.md`](../INSTALL.md) for how `<SECRETS_DIR>` is resolved.
* Auth header is `Authorization: Bearer <PAT>` -- Jira Data Center /
  Server PAT format. Never appears on the command line.
* No third-party dependencies. Python 3.11 stdlib only.

Run `jira help` any time to list verbs, `jira help <verb>` for one verb.

## Setup

```cmd
rem 1. Store the PAT (one line, no newline, owner-only ACL)
<nul set /p="<your-jira-PAT>" > "%USERPROFILE%\.toolbelt\jira.token"
icacls "%USERPROFILE%\.toolbelt\jira.token" /inheritance:r /grant:r "%USERNAME%":F

rem 2. Verify
jira me
```

Rotate the token in the Jira UI (Profile -> Personal Access Tokens) and
overwrite the file. Nothing else changes.

**Jira Cloud (Atlassian):** store `email@company.com:API_TOKEN` in
`jira.token` (one line). The tool detects the `:` and uses Basic auth
automatically. Jira Server / Data Center PATs stay as a plain token (Bearer).

```
# Jira Cloud
<nul set /p="you@example.com:ATATT..." > "%USERPROFILE%\.toolbelt\jira.token"

# macOS / Linux
printf '%s' 'you@example.com:ATATT...' > ~/.toolbelt/jira.token
chmod 600 ~/.toolbelt/jira.token
```

## Verb reference

### Identity

```
jira me
```
Prints the authenticated user's name, email, display name, active flag, and
time zone. Use this to sanity-check the token after rotation.

### Reading issues

```
jira issue view <KEY> [--comments]
jira issue list [--mine] [--project KEY] [--status "In Progress"] [--limit N]
jira issue mine [--project KEY] [--limit N]
jira issue recent [--project KEY] [--days N] [--limit N]
jira search "<JQL>" [--limit N]
```

* `issue view` prints one issue with summary, status, priority, assignee,
  reporter, timestamps, labels, components, fix versions, URL, and full
  description. Add `--comments` to append the discussion thread.
* `issue list` is a convenience wrapper over `search`. Defaults to project
  `MYPROJ`, no assignee filter, `--limit 30`.
* `issue mine` = shortcut for `assignee = currentUser() AND resolution =
  Unresolved`. No project filter by default (spans everything).
* `issue recent` = shortcut for `project = X AND updated >= -Nd`. Defaults
  to project `MYPROJ`, last 1 day.
* `search` runs any JQL you can write in the web UI.

Output rows are `KEY  [STATUS]  ASSIGNEE  SUMMARY` -- one issue per line,
grep-friendly.

### Writing / workflow

```
jira issue create --summary "T" [--project MYPROJ] [--type Task] \
                  [--desc "..."] [--desc-file f] [--assign @me|user]
jira issue comment <KEY> "<message>"
jira issue transitions <KEY>
jira issue transition <KEY> <name-or-id> [--comment "..."]
jira issue assign <KEY> <username | @me | --none>
jira issue link <KEY> <target-KEY> [--type "Relates"]
jira issue watch <KEY>
jira issue unwatch <KEY>
jira issue attach <KEY> <file-path>
```

* `issue create` returns the new key + browse URL. `--type` defaults to
  `Task`; use `Bug`, `Story`, `Alert`, etc. as needed. Pass long
  descriptions via `--desc-file` to avoid shell-quoting pain.
* `issue transitions` lists the workflow transitions available *right now*
  for that issue -- names vary per project workflow.
* `issue transition` accepts either the transition id or its display name
  (case-insensitive). Optional `--comment` posts a comment as part of the
  transition, which shows up in the issue history.
* `issue assign` accepts a raw username, `@me` (shortcut for the token
  owner), or `--none` to clear the assignee.
* `issue link` connects two issues. `--type` names come from your Jira
  admin config; common values: `Relates`, `Blocks`, `Duplicate`,
  `Cloners`. First arg is the *inward* side, second is *outward*.
* `issue watch` / `unwatch` toggle your own watcher status.
* `issue attach` uploads any file as an attachment (uses
  `multipart/form-data` with the `X-Atlassian-Token: no-check` header
  Jira requires).

### Utility

```
jira issue open <KEY>          open browse URL in default browser
jira api <METHOD> <path> [--json '<json>']   raw REST call, prints JSON
jira docs [--open]             print / open this file
jira help [verb]               list verbs or show one full docstring
```

`jira api` is an escape hatch when you need an endpoint the wrapper does not
model. Example:

```cmd
jira api GET /project/MYPROJ
jira api POST /issue --json "{\"fields\":{\"project\":{\"key\":\"MYPROJ\"},\"summary\":\"...\",\"issuetype\":{\"name\":\"Task\"}}}"
```

## Common workflows

### Triage an alert ticket

```cmd
jira issue view MYPROJ-5678 --comments
jira issue transitions MYPROJ-5678
jira issue transition MYPROJ-5678 "In Progress" --comment "Investigating."
```

### My open work

```cmd
jira issue mine
jira issue mine --project MYPROJ
```

### File a follow-up ticket from an alert and link it

```cmd
jira issue create --summary "Fix stale probe on source-cleaner-projector-users" ^
                  --type Task --assign @me ^
                  --desc-file notes.md
jira issue link MYPROJ-5678 MYPROJ-9999 --type "Relates"
jira issue watch MYPROJ-9999
```

### Attach a log to an alert ticket

```cmd
jira issue attach MYPROJ-5678 C:\tmp\probe-debug.log
```

### What changed on MYPROJ today

```cmd
jira issue recent --days 1 --limit 50
```

## Exit codes

* `0` -- success
* `1` -- remote/network failure (surfaced via `[jira] HTTP <code> ...`)
* `2` -- usage error (missing args, unknown verb)

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `[secrets] missing file` | PAT not stored yet | run the setup step |
| `HTTP 401` `AUTHENTICATED_FAILED` | expired / revoked PAT | regenerate PAT in Jira, overwrite `jira.token` |
| `HTTP 403` on an endpoint | PAT lacks scope for that project | Jira project permissions issue, not tooling |
| `HTTP 404` on `/issue/MYPROJ-XXX` | wrong key or issue is in a project you cannot browse | verify via web UI first |

## Design notes

* The wrapper is deliberately **thin**: it does not model epics, sprints,
  boards, or worklogs. When you need those, use `jira api` or extend
  `commands.py` (a new verb is ~15 lines).
* Output is designed for humans **and** AI agents: no ANSI colors, one row
  per line, stable field order. Piping to `findstr` / `grep` works.
* No local state, no config file. Every invocation is stateless except for
  reading `jira.token` once per process.





