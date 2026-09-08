# Installing the tools on a fresh machine

Everything here is stdlib-only Python plus a handful of `.cmd` shims. No
build step, no `pip install`. Setup is five commands.

## 1. Prerequisites

* **Windows** with `cmd.exe` (PowerShell also fine).
* **Python 3.11 or newer** somewhere on your machine. Any of these works:
  * `python` on your `PATH` (recommended), or
  * a virtual-env / specific interpreter -- point at it with the
    `TOOLBELT_PYTHON` environment variable.
* **`git`** (only if you want to clone this repo -- you can also copy the
  folder).
* Network access to your GitLab / Jira / Confluence hosts.
* A **personal access token** for each system you plan to use.

## 2. Clone (or copy) the repo

```cmd
git clone <your-internal-git-url>  C:\path\to\tools
```

There is no build step. The clone is ready to run.

## 3. Put `bin\` on your `PATH`

Start menu -> "Edit the system environment variables" -> *Environment
Variables* -> edit `Path` -> *New* -> paste the absolute path to your
`<clone>\bin` directory. Open a fresh terminal.

Verify:

```cmd
gl help
jira help
conf help
```

Each should print a list of verbs. If Python is not on your `PATH`, set
`TOOLBELT_PYTHON` to the interpreter you want the tools to use:

```cmd
setx TOOLBELT_PYTHON "C:\Python311\python.exe"
```

Open a new terminal after `setx` for the change to take effect.

## 4. Choose (or accept) a secrets directory

By default, tokens are read from
`%USERPROFILE%\.toolbelt\` on Windows,
`~/.toolbelt/` on Linux/macOS.

To use a different location, set `TOOLBELT_SECRETS`:

```cmd
setx TOOLBELT_SECRETS "%USERPROFILE%\my-secrets"
```

Open a new terminal after `setx`. The directory is created on first token
you store.

## 5. (Optional) Customise URLs and defaults

Every tool ships with built-in defaults for its base URL and default
project / space. If those match your organisation, skip this step.

Otherwise, copy [`config.toml.example`](config.toml.example) into your
secrets directory and edit whatever you need:

```cmd
copy config.toml.example "%USERPROFILE%\.toolbelt\config.toml"
notepad "%USERPROFILE%\.toolbelt\config.toml"
```

See [`docs/CONFIG.md`](docs/CONFIG.md) for the full schema and the
environment-variable overrides for each field.

## 6. Store your tokens

Create one file per system. **One line, no trailing newline, no quotes.**

```cmd
mkdir "%USERPROFILE%\.toolbelt"  2>nul

<nul set /p="<your-gitlab-PAT>"    > "%USERPROFILE%\.toolbelt\gitlab.token"
<nul set /p="<your-jira-PAT>"      > "%USERPROFILE%\.toolbelt\jira.token"
<nul set /p="<your-confluence-PAT>"> "%USERPROFILE%\.toolbelt\confluence.token"

rem SignOz: JSON credentials file (email + password), not a one-line token
notepad "%USERPROFILE%\.toolbelt\signoz.credentials"
rem paste: {"email":"you@lenskart.com","password":"..."}

icacls "%USERPROFILE%\.toolbelt\*.token" /inheritance:r /grant:r "%USERNAME%":F
icacls "%USERPROFILE%\.toolbelt\signoz.credentials" /inheritance:r /grant:r "%USERNAME%":F
```

The `icacls` line restricts the files to your account only. The
`<nul set /p=` trick writes without a trailing newline (important for
Bearer tokens).

## 7. Verify

```cmd
gl me
jira me
conf me
soz auth login
soz me
```

Each should print your username. Done.

## Alternative: if `setx` is blocked by policy

Corporate machines sometimes block `setx`. In that case, put your
personal settings in a local file that the shims read at startup:

```cmd
copy bin\env.cmd.example bin\env.cmd
notepad bin\env.cmd
```

Uncomment and edit the `TOOLBELT_PYTHON`, `TOOLBELT_SECRETS`, etc. lines
as needed. The file is `.gitignore`-d so it never gets committed.

Every `gl` / `jira` / `conf` invocation sources this file if it exists,
so no `setx`, no registry edit, no admin rights are required. Settings
take effect immediately -- no need for a fresh terminal.

Environment variables you already have set globally still win over the
file (the file only sets values that are not already defined).

## Rotating a token

Overwrite the corresponding file with a fresh PAT. Nothing else changes.

## Uninstall

Delete the clone, remove `bin\` from `PATH`, delete
`%USERPROFILE%\.toolbelt\`. That is the complete footprint.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `gl` / `jira` / `conf` not recognised | `bin\` not on `PATH`, or terminal predates the change | new terminal, or restart the shell |
| `[toolbelt] Python 3.11+ was not found on PATH.` | No Python on `PATH` and `TOOLBELT_PYTHON` not set | install Python 3.11, or `setx TOOLBELT_PYTHON "C:\path\to\python.exe"` and open a fresh terminal |
| `[toolbelt] TOOLBELT_PYTHON points to a file that does not exist` | `TOOLBELT_PYTHON` is set but the file is missing or you typed the path wrong | `setx TOOLBELT_PYTHON "..."` with the correct path, or `setx TOOLBELT_PYTHON ""` to unset |
| `[secrets] missing file: ...token` | Token file not created yet, or `TOOLBELT_SECRETS` points somewhere else | see step 5, or `echo %TOOLBELT_SECRETS%` |
| `HTTP 401` on `me` | Expired / mistyped token | regenerate PAT in the source system, overwrite the file |
| `HTTP 403` on some verbs | PAT lacks required scope, or you lack access to that resource | fix at the source system |

## macOS / Linux

The repo ships both Windows (`.cmd`) and Unix (shell) shims in `bin/`.

```bash
git clone https://github.com/TheShahnawaaz/toolbelt.git ~/toolbelt
export PATH="$HOME/toolbelt/bin:$PATH"    # add to ~/.zshrc or ~/.bashrc

# optional per-machine overrides (see bin/env.sh.example)
cp ~/toolbelt/bin/env.sh.example ~/toolbelt/bin/env.sh

mkdir -p ~/.toolbelt
printf '%s' '<your-gitlab-PAT>' > ~/.toolbelt/gitlab.token
chmod 600 ~/.toolbelt/gitlab.token

gl me
```

If Python's SSL verification fails against a corporate GitLab host, set
`SSL_CERT_FILE` in `bin/env.sh` (see `bin/env.sh.example`).

**oh-my-zsh users:** the git plugin aliases `gl` to `git pull`. Add
`unalias gl 2>/dev/null` after your `PATH` export, or call the shim by
full path.

