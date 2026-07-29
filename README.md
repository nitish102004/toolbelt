# toolbelt

Small, personal CLI utilities for talking to internal systems that
require credentials (GitLab, Jira, Confluence today; more later). Kept as
a **stand-alone repo** so nothing here can be accidentally committed to a
project repo, and so teammates can clone and use it too.

Callers -- you at a prompt or an AI agent -- see only high-level verbs
like `gl mr status 1`. Tokens, URLs, and HTTP details live behind
the tool and are never passed on the command line.

## Quick start

1. **[Install](INSTALL.md)** -- clone, put `bin\` on `PATH`, drop tokens
   into your secrets directory. Five commands, no build step.

2. **Verify:**

   ```cmd
   gl me
   jira me
   conf me
   ```

3. **Explore:**

   ```cmd
   gl help
   jira help
   conf help
   ```

Every verb self-documents via `<tool> help <verb>`.

## Tools

| Tool   | What it does                                    | Reference                                |
| ------ | ----------------------------------------------- | ---------------------------------------- |
| `gl`   | GitLab merge requests, pipelines, jobs, diffs   | [`docs/gitlab.md`](docs/gitlab.md)       |
| `jira` | Jira Server issues, comments, transitions, JQL  | [`docs/jira.md`](docs/jira.md)           |
| `conf` | Confluence pages, attachments, CQL search       | [`docs/confluence.md`](docs/confluence.md) |

## Cheat sheets

### GitLab -- daily verbs

```
gl me                                  who am I?
gl mr list                             my open MRs
gl mr status 1                    state + head pipeline
gl mr diff 1 --stat               per-file +/- summary
gl mr diff 1 User.java            diff of matching files only
gl mr pipeline 1                  job breakdown of latest pipeline
gl mr create --push --target main      create MR from current branch
gl job log 44444444 --tail 40        tail a failed job's trace
gl pipeline retry 55555555             retry all failed jobs (flaky CI)
gl mr watch 1                     poll until pipeline finishes
gl mr merge 1                     merge when pipeline succeeds
```

Both hyphenated (`gl mr-status 1`) and two-word (`gl mr status
1`) forms work everywhere.

### Jira -- daily verbs

```
jira me                                who am I?
jira issue mine                        my unresolved tickets
jira issue recent --days 1             what changed today
jira issue view MYPROJ-5678 --comments   full ticket + discussion
jira issue transitions MYPROJ-5678       what states can I move it to?
jira issue transition MYPROJ-5678 "Start Progress" --comment "..."
jira issue comment MYPROJ-5678 "..."     add a comment
jira issue assign MYPROJ-5678 @me        take ownership
jira issue create --summary "..." --assign @me
jira issue link MYPROJ-5678 MYPROJ-9999 --type Relates
jira issue watch MYPROJ-5678             follow the ticket
jira issue attach MYPROJ-5678 log.txt    upload an attachment
```

### Confluence -- daily verbs

```
conf me                                   who am I?
conf page view <id-or-url>                title + breadcrumb + body as text
conf page view <id-or-url> --html         rendered HTML instead
conf page open <id-or-url>                open in browser
conf page children 12345678              list sub-pages
conf page attachments 12345678           list attachments
conf page comments 12345678              list comments
conf page download 12345678 --out .      save page + attachments to disk
conf recent --days 3                      what changed recently
conf search "space = MYSPACE AND title ~ Onboarding"
conf space view MYSPACE
```

## Documentation

* [`INSTALL.md`](INSTALL.md) -- fresh-machine setup and troubleshooting.
* [`docs/CONFIG.md`](docs/CONFIG.md) -- per-user config file (URLs,
  default project / space); optional, everything works without it.
* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) -- three-layer model,
  secret-handling rules, error contract.
* [`docs/ADDING_A_TOOL.md`](docs/ADDING_A_TOOL.md) -- copy-paste recipe
  for a new tool.
* [`docs/gitlab.md`](docs/gitlab.md) / [`docs/jira.md`](docs/jira.md) /
  [`docs/confluence.md`](docs/confluence.md) -- full per-tool references.
* [`LICENSE.md`](LICENSE.md) -- ownership + contribution rules.

## Runtime

* **Python 3.11 or newer** on `PATH`, or the interpreter pointed at by
  `TOOLBELT_PYTHON`.
* **Standard library only** -- no `pip install` needed.

## Design in one paragraph

Every tool is a tiny Python package under `src\<tool>\` with three files:
`__main__.py` (dispatcher), `api.py` (thin HTTP wrapper), `commands.py`
(verb implementations). Every tool reads its credential through
`common.secrets.load("<name>")`, which is the single place that touches
`<SECRETS_DIR>`. Callers invoke a `.cmd` shim in `bin\` -- they never see
a token, a URL, or a REST endpoint. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full story.
