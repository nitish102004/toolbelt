# Adding a new tool

This guide walks through adding a hypothetical `slack` tool as a worked
example. The same recipe applies to any REST-based system (Jira,
Confluence, ServiceNow, internal APIs).

## Prerequisites

* You already have `<repo>\bin` on `PATH` (see [INSTALL.md](../INSTALL.md)).
* You have a personal access token for the target system.
* You can hit the target system's REST API with `curl` from your machine.

## Step 1 -- Store the credential

Create the secret file in your `<SECRETS_DIR>` (see
[ARCHITECTURE.md](ARCHITECTURE.md) for how that path is resolved):

```cmd
<nul set /p="<your-raw-token>" > "%USERPROFILE%\.toolbelt\slack.token"
icacls "%USERPROFILE%\.toolbelt\slack.token" /inheritance:r /grant:r "%USERNAME%":F
```

Naming convention: **`<system>.token`**, all lowercase. Single line, no
quotes, no prefix. The `<nul set /p=` trick writes without a trailing
newline.

Nothing else uses that file except `common.secrets.load("slack.token")`.

## Step 2 -- Scaffold the package

```
src\slack\
  __init__.py       # empty
  __main__.py       # copy the gitlab one, change "gitlab" -> "slack"
  api.py            # thin HTTP wrapper
  commands.py       # verb implementations
```

Fastest way from the repo root:

```cmd
xcopy /E /I src\gitlab  src\slack
```

Then edit:

### `__main__.py`
Change the single relative import at the top.

### `api.py`
Only three constants change:

```python
BASE_URL = "https://slack.example.com/api"
DEFAULT_CHANNEL = "#general"
_secret_name = "slack.token"
```

For Bearer-token systems:

```python
def _auth_header() -> dict[str, str]:
    global _token
    if _token is None:
        _token = load_secret(_secret_name)
    return {"Authorization": f"Bearer {_token}"}
```

### `commands.py`
Start with just `me`:

```python
def cmd_me(_: list[str]) -> None:
    '''slack me  -- current user.'''
    u = api.get("/users.profile.get")
    print(f"{u['profile']['real_name']}  <{u['profile'].get('email','?')}>")


VERBS = {"me": cmd_me, "help": cmd_help}
```

## Step 3 -- Add the shim

`bin\slack.cmd`:

```bat
@echo off
setlocal
set "TOOLS_SRC=%~dp0..\src"
set "PYTHONPATH=%TOOLS_SRC%;%PYTHONPATH%"
if defined TOOLBELT_PYTHON (
  "%TOOLBELT_PYTHON%" -m slack %*
) else (
  python -m slack %*
)
```

`%~dp0` makes the shim portable: it resolves `src\` relative to its own
location so the repo works from any clone directory.

## Step 4 -- Smoke test

```cmd
slack me
```

## Verb design conventions

* **One verb = one clear action.**
* **Docstrings drive `help`.** First line = usage.
* **Positional args first, flags second**, parsed with the tiny
  `_flag` / `_has_flag` helpers.
* **Tabular output gets a header + divider row.** See how `gl`, `jira`,
  and `conf` render `KEY  STATUS  ASSIGNEE  SUMMARY` etc. -- consistent
  across tools makes agent piping predictable.
* **Print for humans by default**, respect piping. When
  `sys.stdout.isatty()` is false, turn off colors and prefer
  machine-friendly output.
* **Exit codes:** 0 success, 1 remote/network failure, 2 usage error.
* **No global state beyond the cached token in `api.py`.**

## Step 5 -- Documentation

* Add `docs/<tool>.md` -- full verb reference.
* Add a row to the tool table in `README.md`.
* Add a "daily verbs" cheat-sheet block to `README.md`.

## Common REST-wrapper adjustments per target

| Target       | Auth header                  | Common URL quirks                          |
| ------------ | ---------------------------- | ------------------------------------------ |
| GitLab       | `PRIVATE-TOKEN: <token>`     | Project path is `/projects/<id_or_urlenc>` |
| Jira Server  | `Authorization: Bearer ...`  | Path prefix `/rest/api/2`                  |
| Jira Cloud   | `Authorization: Basic ...`   | Uses `emailAddress:APItoken` base64        |
| Confluence   | `Authorization: Bearer ...`  | Path prefix `/rest/api`                    |
| ServiceNow   | `Authorization: Bearer ...`  | JSON body must include `sysparm_*` params  |
| Slack        | `Authorization: Bearer ...`  | Some verbs need form-urlencoded            |

The wrapper in `gitlab/api.py` is 60 lines. Copying and adjusting takes a
minute per system.

## Testing checklist before you commit

* `tool me` succeeds against a real endpoint.
* `tool help` lists every verb.
* At least one write verb has been dry-run tested against a scratch
  resource.
* No hard-coded credentials or personal paths in the code you added.
