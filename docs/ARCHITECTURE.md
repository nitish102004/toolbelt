# Architecture

## Why this exists

MCP servers are not permitted in this environment, but agents (and humans)
still need a safe, uniform way to reach systems that require credentials --
GitLab, Jira, Confluence today; more later. Copy-pasting tokens into
terminals leaks them into shell history, `.bash_history`, screenshots, chat
transcripts, and process listings. This toolset is the local, offline
replacement: a single credential-handling layer, small tool binaries on top
of it, and a caller (you or an agent) that never sees a secret.

## The three layers

```
+---------------------------------------------------------+
|  Caller  (you at a prompt, or an AI agent)              |
|  Sees only:   gl mr status 1                       |
+----------------------------+----------------------------+
                             |  (no auth args, no URLs)
+----------------------------v----------------------------+
|  Tool wrapper  (bin\<tool>.cmd + src\<tool>\...)        |
|  - parses the verb                                      |
|  - talks to the remote API                              |
|  - prints human-friendly output                         |
+----------------------------+----------------------------+
                             |  common.secrets.load("...")
+----------------------------v----------------------------+
|  Secret store  (<SECRETS_DIR>\<name>.token)             |
|  - plain files, owner-only NTFS ACL                     |
|  - one file per credential, contents = raw token        |
|  - <SECRETS_DIR> resolved from $TOOLBELT_SECRETS or    |
|    %USERPROFILE%\.toolbelt by default          |
+---------------------------------------------------------+
```

Each layer only knows about the layer immediately below it. That is what
lets you add a new tool without changing anything about the existing ones,
and lets you rotate a token by editing exactly one file.

## Secret handling rules

1. **One file per credential**, name matches the tool
   (`gitlab.token`, `jira.token`, `confluence.token`, ...).
2. **Contents = the raw value on a single line** -- no `TOKEN=` prefix, no
   quotes, no trailing newline.
3. **Owner-only ACL** applied via
   `icacls "<file>" /inheritance:r /grant:r "%USERNAME%":F`.
4. **Never accept a token via env var, CLI arg, or command line** -- those
   channels leak into logs. Secrets always come from disk via
   `common.secrets.load(name)`.
5. **The secrets directory lives *outside* this repo.** The `.gitignore`
   refuses `*.token`, `*.pat`, `.secrets/`, and `.toolbelt/`
   anywhere in the tree as a belt-and-braces defence.
6. **If a secret was pasted anywhere it should not have been** (chat, MR
   description, log file), treat it as compromised: rotate in the source
   system, overwrite the local file, done.

## Directory layout

Portable -- the repo works from any clone location.

```
<SECRETS_DIR>\                      # off-repo; owner-only ACL
  gitlab.token
  jira.token
  confluence.token

<REPO>\                             # this repo -- safe to commit
  README.md
  INSTALL.md
  LICENSE.md
  .gitignore
  docs\
    ARCHITECTURE.md
    ADDING_A_TOOL.md
    gitlab.md
    jira.md
    confluence.md
  bin\                              # add to PATH
    gl.cmd
    jira.cmd
    conf.cmd
  src\
    common\
      __init__.py
      secrets.py                    # THE ONE place that reads <SECRETS_DIR>
    gitlab\
      __init__.py
      __main__.py
      api.py
      commands.py
    jira\
      ...
    conf\
      ...
```

`<SECRETS_DIR>` resolves in this order:

1. `$TOOLBELT_SECRETS` (explicit override)
2. `%USERPROFILE%\.toolbelt` on Windows
3. `~/.toolbelt` elsewhere

The `src/<tool>/` mini-package is the extension point. Copy it, rename it,
register a new `.cmd` shim, and the new tool inherits the same
secret-loading and error-handling story for free. See
[ADDING_A_TOOL.md](ADDING_A_TOOL.md).

## Runtime dependencies

* **Python 3.11 or newer.** The `.cmd` shims run whatever `python` resolves
  to on `PATH`, or the interpreter pointed at by `TOOLBELT_PYTHON` if set.
* **Standard library only** -- no `pip install` needed. All HTTP goes
  through `urllib`.
* `git` on `PATH` is used only by verbs that default to "current branch"
  (like `gl branch pipeline`).

## Error handling contract

Callers see one of exactly two things when something goes wrong:

* **User-fixable error** -- e.g. missing secret file, unknown verb, wrong
  argument count. Printed as `[secrets] missing file: ...`, exit code 2.
* **Remote error** -- HTTP failure. Printed as `[<tool>] HTTP 401 on GET ...`
  with the first 500 bytes of the server's response body, exit code 1.

No Python tracebacks reach the caller. If you ever see one, that is a bug.

## Non-goals

* **No caching.** Every call is a live API call.
* **No config file.** Defaults (base URLs, default project keys) are code
  constants in each `api.py`.
* **No plugin system, no dynamic verb loading.** Verbs live in a plain
  dict; the file that adds a verb is the file you read to understand it.
* **No third-party dependencies.** Everything is Python stdlib.
