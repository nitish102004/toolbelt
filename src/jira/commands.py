"""Verb implementations for ``jira``.

Design goals (mirrors ``gitlab/commands.py``):
  * One verb == one action, positional args first then flags.
  * First line of each docstring is the usage string driving ``jira help``.
  * Output is human-readable but grep-friendly (one row per line, no tables
    that break when piped).
"""
from __future__ import annotations

import os
import sys
import textwrap
import webbrowser
from typing import Callable

from . import api


# ---------------------------------------------------------------------------
# tiny arg helpers (same style as gitlab/commands.py -- no argparse)
# ---------------------------------------------------------------------------

def _flag(args: list[str], name: str, default: str | None = None) -> str | None:
    """Return value for ``--name VALUE`` or ``--name=VALUE`` and drop it from args."""
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            val = args[i + 1]
            del args[i:i + 2]
            return val
        if a.startswith(name + "="):
            val = a.split("=", 1)[1]
            del args[i]
            return val
    return default


def _has_flag(args: list[str], name: str) -> bool:
    if name in args:
        args.remove(name)
        return True
    return False


def _die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _first_line(text: str | None, width: int = 100) -> str:
    if not text:
        return ""
    line = text.strip().splitlines()[0]
    return line if len(line) <= width else line[: width - 1] + "\u2026"


def _fmt_user(u: dict | None) -> str:
    if not u:
        return "unassigned"
    return u.get("displayName") or u.get("name") or "?"


# ---------------------------------------------------------------------------
# verbs
# ---------------------------------------------------------------------------

def cmd_me(_: list[str]) -> None:
    """jira me  -- current user (sanity-check the token)."""
    u = api.get("/myself")
    print(f"{u.get('name')}  <{u.get('emailAddress','?')}>  "
          f"displayName={u.get('displayName')}  active={u.get('active')}  "
          f"tz={u.get('timeZone')}")


def cmd_issue_view(args: list[str]) -> None:
    """jira issue view <KEY> [--comments]  -- issue with metadata (and optional comments)."""
    show_comments = _has_flag(args, "--comments")
    if not args:
        _die("usage: jira issue view <KEY> [--comments]")
    key = args[0].upper()
    fields = "summary,status,assignee,reporter,priority,issuetype,created,updated," \
             "labels,components,fixVersions,description,resolution"
    issue = api.get(f"/issue/{key}", params={"fields": fields})
    f = issue["fields"]
    print(f"{key}  {f['issuetype']['name']}  [{f['status']['name']}]  "
          f"P={f['priority']['name'] if f.get('priority') else '?'}")
    print(f"  summary   : {f.get('summary','')}")
    print(f"  assignee  : {_fmt_user(f.get('assignee'))}")
    print(f"  reporter  : {_fmt_user(f.get('reporter'))}")
    print(f"  created   : {f.get('created')}")
    print(f"  updated   : {f.get('updated')}")
    if f.get("resolution"):
        print(f"  resolution: {f['resolution'].get('name')}")
    if f.get("labels"):
        print(f"  labels    : {', '.join(f['labels'])}")
    if f.get("components"):
        print(f"  components: {', '.join(c['name'] for c in f['components'])}")
    if f.get("fixVersions"):
        print(f"  fixVers   : {', '.join(v['name'] for v in f['fixVersions'])}")
    print(f"  url       : {api.browse_url(key)}")
    desc = f.get("description") or ""
    if desc.strip():
        print("\ndescription:")
        for line in desc.splitlines():
            print(f"  {line}")
    if show_comments:
        c = api.get(f"/issue/{key}/comment", params={"orderBy": "created"})
        comments = c.get("comments", [])
        print(f"\ncomments ({len(comments)}):")
        for cm in comments:
            author = _fmt_user(cm.get("author"))
            print(f"  --- {cm.get('created','?')}  {author}  (id={cm.get('id')})")
            for line in (cm.get("body") or "").splitlines():
                print(f"    {line}")


def cmd_issue_list(args: list[str]) -> None:
    """jira issue list [--mine] [--project KEY] [--status S] [--limit N]  -- list issues."""
    mine = _has_flag(args, "--mine")
    project = _flag(args, "--project", api.DEFAULT_PROJECT_KEY)
    status = _flag(args, "--status")
    limit = int(_flag(args, "--limit", "30") or 30)

    jql_parts = [f'project = "{project}"']
    if mine:
        jql_parts.append("assignee = currentUser()")
    if status:
        jql_parts.append(f'status = "{status}"')
    jql_parts.append("ORDER BY updated DESC")
    jql = " AND ".join(jql_parts[:-1]) + " " + jql_parts[-1]
    _print_search(jql, limit)


def cmd_search(args: list[str]) -> None:
    """jira search "<JQL>" [--limit N]  -- raw JQL search."""
    limit = int(_flag(args, "--limit", "30") or 30)
    if not args:
        _die('usage: jira search "<JQL>" [--limit N]')
    _print_search(" ".join(args), limit)


def _print_search(jql: str, limit: int) -> None:
    res = api.get(
        "/search",
        params={
            "jql": jql,
            "maxResults": limit,
            "fields": "summary,status,assignee,priority,issuetype,updated",
        },
    )
    issues = res.get("issues", [])
    total = res.get("total", len(issues))
    if not issues:
        print(f"no issues match: {jql}")
        return
    print(f"{'KEY':<12} {'STATUS':<14} {'ASSIGNEE':<14} SUMMARY")
    print(f"{'-'*12} {'-'*14} {'-'*14} {'-'*40}")
    for iss in issues:
        f = iss["fields"]
        status = f['status']['name'][:12]
        assignee = _fmt_user(f.get('assignee'))[:14]
        print(
            f"{iss['key']:<12} "
            f"[{status:<12}] "
            f"{assignee:<14} "
            f"{_first_line(f.get('summary',''), 80)}"
        )
    print(f"\n-- {len(issues)}/{total} shown  --  jql: {jql}")


def cmd_issue_comment(args: list[str]) -> None:
    """jira issue comment <KEY> "<message>"  -- add a comment."""
    if len(args) < 2:
        _die('usage: jira issue comment <KEY> "<message>"')
    key = args[0].upper()
    body = " ".join(args[1:])
    r = api.post(f"/issue/{key}/comment", {"body": body})
    print(f"posted comment id={r.get('id')} on {key}")


def cmd_issue_transitions(args: list[str]) -> None:
    """jira issue transitions <KEY>  -- list available transitions and their target state."""
    if not args:
        _die("usage: jira issue transitions <KEY>")
    key = args[0].upper()
    r = api.get(f"/issue/{key}/transitions")
    transitions = r.get("transitions", [])
    if not transitions:
        print("(no transitions available)")
        return
    print(f"  {'ID':<6} {'NAME':<24} -> TARGET STATE")
    print(f"  {'-'*6} {'-'*24}    {'-'*20}")
    for t in transitions:
        to = t.get("to", {}).get("name", "?")
        print(f"  {t['id']:<6} {t['name']:<24} -> {to}")


def cmd_issue_transition(args: list[str]) -> None:
    """jira issue transition <KEY> <name-or-id> [--comment "..."]  -- transition an issue."""
    comment = _flag(args, "--comment")
    if len(args) < 2:
        _die('usage: jira issue transition <KEY> <name-or-id> [--comment "..."]')
    key = args[0].upper()
    target = args[1]
    r = api.get(f"/issue/{key}/transitions")
    match = None
    for t in r.get("transitions", []):
        if t["id"] == target or t["name"].lower() == target.lower():
            match = t
            break
    if not match:
        names = ", ".join(t["name"] for t in r.get("transitions", []))
        _die(f"no transition matching {target!r}. available: {names}", 1)
    body: dict = {"transition": {"id": match["id"]}}
    if comment:
        body["update"] = {"comment": [{"add": {"body": comment}}]}
    api.post(f"/issue/{key}/transitions", body)
    print(f"{key} transitioned via {match['name']!r} -> {match['to']['name']}")


def cmd_issue_assign(args: list[str]) -> None:
    """jira issue assign <KEY> <username-or-@me-or---none>  -- reassign an issue."""
    if len(args) < 2:
        _die("usage: jira issue assign <KEY> <username|@me|--none>")
    key = args[0].upper()
    who = args[1]
    if who == "--none":
        name = None
    elif who == "@me":
        name = api.get("/myself")["name"]
    else:
        name = who
    api.put(f"/issue/{key}/assignee", {"name": name})
    print(f"{key} assignee = {name or 'unassigned'}")


def cmd_issue_open(args: list[str]) -> None:
    """jira issue open <KEY>  -- open the issue's web URL in the default browser."""
    if not args:
        _die("usage: jira issue open <KEY>")
    url = api.browse_url(args[0].upper())
    print(url)
    webbrowser.open(url)


def cmd_issue_mine(args: list[str]) -> None:
    """jira issue mine [--project KEY] [--limit N]  -- unresolved issues assigned to me."""
    project = _flag(args, "--project")
    limit = int(_flag(args, "--limit", "30") or 30)
    jql = "assignee = currentUser() AND resolution = Unresolved"
    if project:
        jql = f'project = "{project}" AND ' + jql
    jql += " ORDER BY updated DESC"
    _print_search(jql, limit)


def cmd_issue_recent(args: list[str]) -> None:
    """jira issue recent [--project KEY] [--days N] [--limit N]  -- issues updated in the last N days."""
    project = _flag(args, "--project", api.DEFAULT_PROJECT_KEY)
    days = int(_flag(args, "--days", "1") or 1)
    limit = int(_flag(args, "--limit", "30") or 30)
    jql = f'project = "{project}" AND updated >= -{days}d ORDER BY updated DESC'
    _print_search(jql, limit)


def cmd_issue_create(args: list[str]) -> None:
    """jira issue create --summary "T" [--project MYPROJ] [--type Task] [--desc "..."] [--desc-file f] [--assign @me|user]  -- create an issue."""
    summary = _flag(args, "--summary")
    project = _flag(args, "--project", api.DEFAULT_PROJECT_KEY)
    itype = _flag(args, "--type", "Task")
    desc = _flag(args, "--desc")
    desc_file = _flag(args, "--desc-file")
    assign = _flag(args, "--assign")
    if not summary:
        _die('usage: jira issue create --summary "T" [--project MYPROJ] [--type Task] '
             '[--desc "..."] [--desc-file f] [--assign @me|user]')
    if desc_file:
        with open(desc_file, encoding="utf-8") as fh:
            desc = fh.read()
    fields: dict = {
        "project": {"key": project},
        "summary": summary,
        "issuetype": {"name": itype},
    }
    if desc:
        fields["description"] = desc
    if assign:
        name = api.get("/myself")["name"] if assign == "@me" else assign
        fields["assignee"] = {"name": name}
    r = api.post("/issue", {"fields": fields})
    key = r.get("key")
    print(f"created {key}  {api.browse_url(key)}")


def cmd_issue_link(args: list[str]) -> None:
    """jira issue link <KEY> <target-KEY> [--type "Relates"]  -- create an issue link."""
    link_type = _flag(args, "--type", "Relates")
    if len(args) < 2:
        _die('usage: jira issue link <KEY> <target-KEY> [--type "Relates"]')
    inward, outward = args[0].upper(), args[1].upper()
    body = {
        "type": {"name": link_type},
        "inwardIssue": {"key": inward},
        "outwardIssue": {"key": outward},
    }
    api.post("/issueLink", body)
    print(f"linked {inward} <-[{link_type}]-> {outward}")


def cmd_issue_watch(args: list[str]) -> None:
    """jira issue watch <KEY>  -- add yourself as a watcher."""
    if not args:
        _die("usage: jira issue watch <KEY>")
    key = args[0].upper()
    me = api.get("/myself")["name"]
    api.post_json(f"/issue/{key}/watchers", me)
    print(f"watching {key} as {me}")


def cmd_issue_unwatch(args: list[str]) -> None:
    """jira issue unwatch <KEY>  -- remove yourself from watchers."""
    if not args:
        _die("usage: jira issue unwatch <KEY>")
    key = args[0].upper()
    me = api.get("/myself")["name"]
    api.delete(f"/issue/{key}/watchers?username={me}")
    print(f"no longer watching {key}")


def cmd_issue_attach(args: list[str]) -> None:
    """jira issue attach <KEY> <file-path>  -- upload an attachment."""
    if len(args) < 2:
        _die("usage: jira issue attach <KEY> <file-path>")
    key = args[0].upper()
    path = args[1]
    r = api.upload(f"/issue/{key}/attachments", path)
    if isinstance(r, list) and r:
        print(f"attached: {r[0].get('filename')} (id={r[0].get('id')}) on {key}")
    else:
        print(f"attached file on {key}")


def cmd_api(args: list[str]) -> None:
    """jira api <METHOD> <path> [--json '<json>']  -- raw Jira REST call. Path starts with '/'."""
    import json as _json
    body_str = _flag(args, "--json")
    if len(args) < 2:
        _die("usage: jira api <GET|POST|PUT> <path> [--json '<json>']")
    method, path = args[0].upper(), args[1]
    body = _json.loads(body_str) if body_str else None
    if method == "GET":
        r = api.get(path)
    elif method == "POST":
        r = api.post(path, body)
    elif method == "PUT":
        r = api.put(path, body)
    else:
        _die(f"unsupported method: {method}")
    print(_json.dumps(r, indent=2) if r is not None else "(no body)")


def cmd_docs(args: list[str]) -> None:
    """jira docs [--open]  -- print (or open) the full markdown reference path."""
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs", "jira.md")
    )
    print(path)
    if "--open" in args:
        os.startfile(path)  # noqa: S606 -- Windows convenience


def cmd_help(args: list[str]) -> None:
    """jira help [verb]  -- list verbs, or show full docstring for one verb."""
    if args:
        # two-word form: "help issue view" -> "issue-view"
        candidate = "-".join(args)
        if candidate not in VERBS and len(args) >= 2:
            candidate = f"{args[0]}-{args[1]}"
        fn = VERBS.get(candidate) or VERBS.get(args[0])
        if not fn:
            print(f"unknown verb: {' '.join(args)}")
            sys.exit(2)
        print(textwrap.dedent(fn.__doc__ or "(no docstring)").strip())
        return
    print("usage: jira <verb> [args]\n")
    print("Run `jira help <verb>` for details on one verb.")
    print("Run `jira docs` to see the full reference documentation path.\n")
    print("verbs:")
    for name, fn in VERBS.items():
        first = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
        print(f"  {name:<20} {first}")


VERBS: dict[str, Callable[[list[str]], None]] = {
    "me": cmd_me,
    "issue-view": cmd_issue_view,
    "issue-list": cmd_issue_list,
    "issue-mine": cmd_issue_mine,
    "issue-recent": cmd_issue_recent,
    "issue-create": cmd_issue_create,
    "issue-comment": cmd_issue_comment,
    "issue-transitions": cmd_issue_transitions,
    "issue-transition": cmd_issue_transition,
    "issue-assign": cmd_issue_assign,
    "issue-link": cmd_issue_link,
    "issue-watch": cmd_issue_watch,
    "issue-unwatch": cmd_issue_unwatch,
    "issue-attach": cmd_issue_attach,
    "issue-open": cmd_issue_open,
    "search": cmd_search,
    "api": cmd_api,
    "docs": cmd_docs,
    "help": cmd_help,
}








