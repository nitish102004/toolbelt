# `gl` -- GitLab CLI reference

A thin, opinionated wrapper over GitLab's REST v4 API for the `myorg/myproj/myrepo`
project (numeric ID **1**). One command per line, sensible defaults, no
config file.

* Base URL: `https://gitlab.example.com/api/v4`
* Credential: `<SECRETS_DIR>\gitlab.token` (PAT with `api` scope). See
  [`INSTALL.md`](../INSTALL.md) for how `<SECRETS_DIR>` is resolved.
* Both hyphenated (`gl mr-status 1`) and two-word (`gl mr status 1`) forms
  work everywhere.

## Discovering how to use `gl` from inside `gl`

You never have to leave the terminal to look up a verb:

```
gl help                     list every verb with a one-line description
gl help <verb>              print the full docstring for one verb
gl help mr diff             two-word form also works
gl docs                     print filesystem paths to this reference
gl docs --open              open this file in the default markdown handler
```

Agents should always start with `gl help` and then `gl help <verb>` on
whichever verb looks relevant, rather than guessing arguments.

## Table of contents

* [Session](#session)
* [Merge requests -- read](#merge-requests----read)
* [Merge requests -- write](#merge-requests----write)
* [Pipelines & branches](#pipelines--branches)
* [Jobs](#jobs)
* [Common workflows](#common-workflows)
* [Exit codes](#exit-codes)
* [Troubleshooting](#troubleshooting)

---

## Session

### `gl me`
Print the identity behind the token. First thing to run after rotating a
credential.

```
> gl me
alice  (Alice User)  <alice@example.com>  id=1
```

---

## Merge requests -- read

### `gl mr list [--all] [--global] [--state opened|merged|closed]`
Default: **your open MRs** in the configured default project, most recently
updated first (up to 30). `--all` drops the author filter; `--global` lists
MRs across every GitLab project you can access (still filtered to your MRs
unless `--all` is also given); `--state` picks a different state.

```
> gl mr list --global
iid   project                         state   branch              title
----  ------------------------------  ------  ------------------  -----
1320  lk-juno/services/juno-customer  opened  isArchived/logs     add logs for archieved file
66    lk-pos/services/nexora          opened  fix-v3-apis         fix for v3 apis
```

### `gl mr status <iid>`
One-liner covering state, branches, URL, and the head pipeline status.

```
> gl mr status 1
MR !1: Remove eve identity and all references
  state       : opened  (draft=False)
  source      : alice/remove-eve -> main
  web_url     : https://gitlab.example.com/myorg/myproj/myrepo/-/merge_requests/1
  head pipeline: #55555555  status=running
```

### `gl mr view <iid>`
Richer than `mr status`: author, discussion count, approval state, and (if
present) the description body.

```
> gl mr view 1
MR !1: Remove eve identity and all references
  state       : opened  (draft=False)
  author      : alice
  source      : alice/remove-eve -> main
  url         : ...
  discussions : 1 note(s)
  pipeline    : #55555555  status=success
  approvals   : 4 left; approved by: bob

--- description ---
...
```

### `gl mr pipeline <iid>`
Job breakdown of the latest pipeline attached to the MR. Prints a per-status
summary and a table of every non-success job so you can jump straight to a
`gl job log`.

```
> gl mr pipeline 1
pipeline #55555555  status=running  https://.../pipelines/55555555
summary: created=4, failed=3, manual=3, running=1, skipped=11, success=10

non-success jobs:
id          name                     stage  status
----------  -----------------------  -----  -------
44444444  passport-inputs-build    build  failed
1131187690  gatekeeper-inputs-build  build  failed
1131187686  diff-outputs             build  failed
```

### `gl mr changes <iid>`
Flag + path for every changed file. Use this when you only care about *which*
files, not their contents.

Flag column: `A` added, `D` deleted, `R` renamed, `M` modified.

### `gl mr commits <iid>`
Short SHA, author, subject line. One row per commit on the MR branch.

### `gl mr diff <iid> [pattern] [--stat|--names] [--no-color]`
The most-used verb. Three output modes:

| Invocation                              | Output                                  |
| --------------------------------------- | --------------------------------------- |
| `gl mr diff 1`                     | full colored unified diff of every file |
| `gl mr diff 1 --stat`              | per-file `+N -N` counts + grand total   |
| `gl mr diff 1 --names`             | filenames only, one per line            |
| `gl mr diff 1 User.java`           | full diff of paths matching `User.java` |
| `gl mr diff 1 xstore --stat`       | stats for paths matching `xstore`       |
| `gl mr diff 1 --no-color > x.diff` | plain patch file (color auto-off on pipe)|

`pattern` is a case-insensitive substring; it matches against both `new_path`
and `old_path`, so renames are matched by either side. All flags compose.

### `gl mr open <iid>`
Print the web URL and launch it in your default browser (Windows only, via
`os.startfile`).

---

## Merge requests -- write

Every write verb hits a REST endpoint that requires the `api` scope on your
token.

### `gl mr create [--title "T"] [--desc "D"] [--desc-file <path>] [--target <branch>] [--draft] [--push]`
Create an MR **from the current git branch**. Every argument is optional --
smart defaults make the zero-flag form usually right.

| Flag                       | Default                                      |
| -------------------------- | -------------------------------------------- |
| `--title "…"`              | subject of the latest commit on the branch   |
| `--desc "…"`               | empty                                        |
| `--desc-file <path>`       | (only used if given; reads UTF-8 file)       |
| `--target <branch>`        | project's default branch (usually `main`)    |
| `--draft`                  | off; when set, title is prefixed `Draft: `   |
| `--push`                   | off; when set, `git push -u origin <src>`    |

Examples:

```
# minimal -- title auto-derived from HEAD commit
gl mr create

# push the branch first, then open the MR against a non-default target
gl mr create --push --target release/2026Q3

# explicit title + description
gl mr create --title "Wire up prober canary" ^
             --desc "Follow-up to !123456 -- enables canary on prober-4."

# long description from a file
gl mr create --desc-file review/description.md

# open as a draft
gl mr create --draft --title "WIP: refactor identity registry"
```

Always sets `remove_source_branch=true` so the branch is auto-deleted on
merge. If your local branch is not yet pushed, add `--push` -- otherwise
GitLab will reject the create call with 404 on the source ref.

### `gl mr note <iid> "<message>"`
Post a comment on the MR discussion. Quote the message; every remaining
argument is joined with spaces.

```
> gl mr note 1 "waiting for source-cleaner-projector-users to merge first"
posted note id=87340221
```

### `gl mr comments <iid> [--human] [--unresolved] [--system]`
List discussion comments on an MR. By default shows all non-system notes;
flags narrow the output.

| Flag            | Effect                                              |
| --------------- | --------------------------------------------------- |
| `--human`       | skip system notes and `codereview` bot posts        |
| `--unresolved`  | only unresolved inline review threads               |
| `--system`      | include system notes (commit pushes, line changes)  |

Discussion ids are printed as an 8-char prefix you can pass to the reply /
resolve verbs.

### `gl mr review <iid>`
Combined MR report: state, pipeline, approvals, description, unresolved
human review comments, and the full human comment thread. This is the
one-shot verb for triaging review feedback.

```
> gl mr review 1320
MR !1320: add logs for archieved file
  state       : opened  (draft=False)
  ...
  comments    : 3 human, 2 unresolved, 17 thread(s)

--- unresolved review comments ---
1. shikharyadav @ CustomerProfileServiceImpl.java:543  (disc=7b1f2554)
   remove
```

### `gl mr comment-reply <iid> <discussion-id> "<message>"`
Reply inside an existing discussion thread. `<discussion-id>` can be the
full UUID or an 8-character prefix shown by `gl mr comments`.

### `gl mr comment-resolve <iid> <discussion-id>`
Mark a review thread as resolved.

### `gl mr comment-unresolve <iid> <discussion-id>`
Reopen a previously resolved review thread.

### `gl mr approve <iid>`
Add your approval. Prints how many approvals are still required.

### `gl mr merge <iid> [--now]`
Default behaviour: **merge when the current pipeline succeeds** and delete the
source branch. Pass `--now` to skip the pipeline-succeeds gate and merge
immediately (subject to project settings).

### `gl mr rebase <iid>`
Ask GitLab to rebase the MR onto its target. The API responds immediately;
poll with `gl mr status` to see when it's done.

### `gl mr close <iid>` / `gl mr reopen <iid>`
Simple state transitions. `close` does not merge -- use `gl mr merge` for
that.

### `gl mr checkout <iid>`
Fetches the MR's source branch and switches your local working copy to it.
Wraps:

```
git fetch origin <source_branch>:<source_branch>
git checkout <source_branch>
```

Great for reviewing an MR locally without hunting for the branch name.

### `gl mr watch <iid> [--interval SEC]`
Long-running verb: polls the head pipeline every `--interval` seconds
(default 30) and prints one line whenever the status changes. Exits when the
pipeline reaches a final state (`success`, `failed`, `canceled`, `skipped`).

```
> gl mr watch 1 --interval 60
[12:12:04] pipeline #55555555 -> running   https://.../pipelines/55555555
[12:13:04] still running ...
[12:14:04] pipeline #55555555 -> success   https://.../pipelines/55555555
```

Ctrl-C to stop early.

---

## Pipelines & branches

### `gl pipeline status <id>`
Detailed status for a single pipeline by ID -- URL, SHA, timestamps.

### `gl pipeline retry <id>`
Retry every failed job in the pipeline in one call. Perfect for flaky
container-registry timeouts.

### `gl branch pipeline [branch]`
Latest pipeline for a branch. When no branch is given, uses the current
branch of the git repository in your CWD, so from within a checkout:

```
> gl branch pipeline
branch=alice/remove-eve  pipeline #55555555  status=running  https://...
```

---

## Jobs

### `gl job log <id> [--tail N]`
Print the last `N` lines of a job's trace (default 80). Use with the IDs
shown by `gl mr pipeline`.

### `gl job retry <id>`
Retry one specific job. Returns the new job's ID and URL.

---

## Issues

### `gl issue list [--mine] [--state opened|closed|all]`
Default: **opened** issues in the project. `--mine` restricts to issues
assigned to you.

### `gl issue view <iid>`
Full issue: state, author, assignees, labels, URL, and the description body.

---

## Repository

### `gl repo view`
Project metadata: default branch, visibility, web URL, clone URLs, description.

---

## Raw API escape hatch

### `gl api <METHOD> <PATH> [--json '<body>'] [--param k=v ...]`
Reach any GitLab REST endpoint that does not have a dedicated verb yet.

* `<METHOD>` is `GET`, `POST`, or `PUT`.
* `<PATH>` starts with `/` and is appended to `/api/v4`. For project-scoped
  endpoints prefix with `/projects/1`.
* `--json` takes a JSON string used as the request body (POST/PUT only).
* `--param k=v` may be repeated to add query-string parameters.

Response is printed as indented JSON.

Examples:

```
# list project labels (raw)
gl api GET /projects/1/labels --param per_page=10

# create an issue
gl api POST /projects/1/issues --json "{\"title\":\"triage me\"}"

# assign a label to an MR
gl api PUT /projects/1/merge_requests/1 --json "{\"add_labels\":\"needs-review\"}"

# GitLab-wide (not project-scoped) call
gl api GET /users --param username=alice
```

Use this to prototype behaviour before deciding whether to promote it to a
dedicated verb.

---

## Common workflows

### "My MR just went red -- what failed and why?"

```cmd
gl mr pipeline 1           :: see which jobs failed
gl job log 44444444 --tail 40 :: tail the first failed job
```

If the failure looks transient (network timeout, image push error):

```cmd
gl pipeline retry 55555555
gl mr watch 1
```

### "Show me exactly what changed to file X in this MR"

```cmd
gl mr diff 1 User.java
```

### "Compare all my open MRs at a glance"

```cmd
gl mr list
```

### "Comment on an MR from the terminal"

```cmd
gl mr note 1 "rebased on latest main, re-triggering pipeline"
```

### "Save the full diff as a review patch"

```cmd
gl mr diff 1 > review.diff
```

Color is auto-disabled because stdout is not a TTY, so the file is a clean
unified diff you can hand to any tool.

### "Merge as soon as CI turns green"

```cmd
gl mr merge 1
```

Then walk away.

---

## Exit codes

| Code | Meaning                                            |
| ---- | -------------------------------------------------- |
| 0    | success                                            |
| 1    | remote or network error (details printed)          |
| 2    | usage error (missing argument, unknown verb, etc.) |

Never a Python traceback -- if you see one, that is a bug in `gl`.

---

## Troubleshooting

### `[secrets] missing file: <SECRETS_DIR>\gitlab.token`
Create the file with your PAT as its only content:

```cmd
<nul set /p="<your-token>" > "%USERPROFILE%\.toolbelt\gitlab.token"
```

(Or wherever your `TOOLBELT_SECRETS` points -- see
[`INSTALL.md`](../INSTALL.md).)

### `[gitlab] HTTP 401 on GET /user`
Token is invalid, expired, or has the wrong scopes. Regenerate at
<https://gitlab.example.com/-/user_settings/personal_access_tokens>
with scope **`api`**, and overwrite the file.

### `[gitlab] HTTP 403 …`
Auth worked but the token lacks permission for that specific resource. For
write verbs (`mr merge`, `mr approve`, `mr rebase`), you also need repo
permissions (Developer or above).

### `[gl] not inside a git repo`
`gl branch pipeline` (with no argument) shells out to `git`. Either `cd` to a
checkout of myrepo or pass the branch name explicitly.

### Color escape codes appear as literal text
Old Windows terminals lack VT100 support. Two options: pass `--no-color`, or
upgrade to Windows Terminal / a recent PowerShell / the terminal built into
VS Code / IntelliJ.

### Token was pasted somewhere it should not have been
Rotate it -- there is no way to un-leak. Steps:

1. GitLab UI → **User Settings → Access Tokens** → revoke the leaked token.
2. Create a fresh one with scope `api`.
3. Overwrite `<SECRETS_DIR>\gitlab.token` with the new value.
4. `gl me` to confirm.

Nothing else needs to change; the token file is the single point of
configuration.

---

## Reference: verbs at a glance

```
me

mr status <iid>
mr view <iid>
mr pipeline <iid>
mr list [--all] [--state STATE]
mr changes <iid>
mr commits <iid>
mr diff <iid> [pattern] [--stat|--names] [--no-color]
mr create [--title T] [--desc D] [--desc-file P] [--target BR] [--draft] [--push]
mr note <iid> "<message>"
mr approve <iid>
mr merge <iid> [--now]
mr rebase <iid>
mr close <iid>
mr reopen <iid>
mr open <iid>
mr checkout <iid>
mr watch <iid> [--interval SEC]

issue list [--mine] [--state STATE]
issue view <iid>

repo view

pipeline status <id>
pipeline retry <id>
branch pipeline [branch]

job log <id> [--tail N]
job retry <id>

api <METHOD> <path> [--json '<json>'] [--param k=v ...]
```


