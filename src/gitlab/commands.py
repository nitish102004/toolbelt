"""Verb implementations for the ``gl`` CLI.

Each function takes the CLI args after the verb and writes human-readable
output to stdout. Add a new verb by:
  1. adding a function ``cmd_<name>`` here, and
  2. registering it in ``VERBS`` at the bottom.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

from . import api

# ---------- helpers ----------------------------------------------------------

FINAL_PIPELINE_STATES = {"success", "failed", "canceled", "skipped"}


def _print_table(rows: list[dict], columns: list[str]) -> None:
    if not rows:
        print("  (no rows)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in columns))


def _tail(text: str, n: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:])


def _current_branch() -> str:
    """Return the current git branch (from cwd). Exits if not in a repo."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        sys.exit("[gl] not inside a git repo; pass a branch name explicitly")


def _flag(args: list[str], name: str, default: str | None = None) -> str | None:
    """Return value for `--name value` if present, else default."""
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _has_flag(args: list[str], name: str) -> bool:
    return name in args


# ---------- verbs ------------------------------------------------------------

def cmd_me(_: list[str]) -> None:
    """gl me  -- current user (sanity-check the token)."""
    u = api.get("/user")
    print(f"{u['username']}  ({u['name']})  <{u.get('email','?')}>  id={u['id']}")


# ----- MR verbs -----

def cmd_mr_status(args: list[str]) -> None:
    """gl mr status <iid>  -- one-line MR + head pipeline summary."""
    if not args:
        sys.exit("usage: gl mr status <iid>")
    mr = api.get(f"{api.project_path()}/merge_requests/{args[0]}")
    print(f"MR !{mr['iid']}: {mr['title']}")
    print(f"  state       : {mr['state']}  (draft={mr.get('draft', False)})")
    print(f"  source      : {mr['source_branch']} -> {mr['target_branch']}")
    print(f"  web_url     : {mr['web_url']}")
    if mr.get("head_pipeline"):
        p = mr["head_pipeline"]
        print(f"  head pipeline: #{p['id']}  status={p['status']}")


def cmd_mr_pipeline(args: list[str]) -> None:
    """gl mr pipeline <iid>  -- job breakdown of latest pipeline on the MR."""
    if not args:
        sys.exit("usage: gl mr pipeline <iid>")
    pipes = api.get(f"{api.project_path()}/merge_requests/{args[0]}/pipelines")
    if not pipes:
        print("(no pipelines yet)")
        return
    latest = pipes[0]
    print(f"pipeline #{latest['id']}  status={latest['status']}  {latest['web_url']}")
    jobs = api.get(f"{api.project_path()}/pipelines/{latest['id']}/jobs", {"per_page": 100})
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["status"]] = counts.get(j["status"], 0) + 1
    print("summary:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    interesting = [j for j in jobs if j["status"] not in ("success", "created", "skipped")]
    if interesting:
        print("\nnon-success jobs:")
        _print_table(
            [{"id": j["id"], "name": j["name"], "stage": j["stage"], "status": j["status"]} for j in interesting],
            ["id", "name", "stage", "status"],
        )


def cmd_mr_list(args: list[str]) -> None:
    """gl mr list [--mine|--all] [--global] [--state opened|merged|closed]  -- list MRs."""
    state = _flag(args, "--state", "opened")
    params: dict = {"state": state, "per_page": 30, "order_by": "updated_at"}
    if not _has_flag(args, "--all"):
        me = api.get("/user")
        params["author_id"] = me["id"]
    if _has_flag(args, "--global"):
        params["scope"] = "all"
        path = "/merge_requests"
        columns = ["iid", "project", "state", "branch", "title"]
    else:
        path = f"{api.project_path()}/merge_requests"
        columns = ["iid", "state", "branch", "title"]
    mrs = api.get(path, params)
    if not mrs:
        print("(no MRs)")
        return
    rows = []
    for m in mrs:
        row = {
            "iid": m["iid"],
            "state": m["state"],
            "branch": m["source_branch"],
            "title": m["title"][:60],
        }
        if _has_flag(args, "--global"):
            refs = m.get("references", {}).get("full", "")
            row["project"] = refs.rsplit("!", 1)[0] if "!" in refs else str(m.get("project_id", "?"))
        rows.append(row)
    _print_table(rows, columns)


def cmd_mr_changes(args: list[str]) -> None:
    """gl mr changes <iid>  -- list files changed."""
    if not args:
        sys.exit("usage: gl mr changes <iid>")
    m = api.get(f"{api.project_path()}/merge_requests/{args[0]}/changes")
    files = m.get("changes", [])
    print(f"{len(files)} file(s) changed:")
    for f in files:
        flag = "A" if f.get("new_file") else ("D" if f.get("deleted_file") else ("R" if f.get("renamed_file") else "M"))
        print(f"  {flag}  {f['new_path']}")


def cmd_mr_commits(args: list[str]) -> None:
    """gl mr commits <iid>  -- list commits on the MR."""
    if not args:
        sys.exit("usage: gl mr commits <iid>")
    cs = api.get(f"{api.project_path()}/merge_requests/{args[0]}/commits")
    if not cs:
        print("(no commits)")
        return
    print(f"  {'SHA':<10}  {'AUTHOR':<20}  TITLE")
    print(f"  {'-'*10}  {'-'*20}  {'-'*40}")
    for c in cs:
        author = c['author_name'][:20]
        print(f"  {c['short_id']:<10}  {author:<20}  {c['title']}")


# ---- diff helpers ----------------------------------------------------------

def _change_flag(f: dict) -> str:
    if f.get("new_file"): return "A"
    if f.get("deleted_file"): return "D"
    if f.get("renamed_file"): return "R"
    return "M"


def _count_diff(diff_text: str) -> tuple[int, int]:
    a = d = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            a += 1
        elif line.startswith("-") and not line.startswith("---"):
            d += 1
    return a, d


def _enable_windows_ansi() -> None:
    """Turn on VT100 sequences in cmd.exe / PowerShell on Windows 10+."""
    if os.name == "nt":
        os.system("")  # no-op that flips ENABLE_VIRTUAL_TERMINAL_PROCESSING


def _print_file_diff(f: dict, color: bool) -> None:
    flag = _change_flag(f)
    if f.get("renamed_file"):
        header = f"=== [{flag}] {f['old_path']} -> {f['new_path']}"
    else:
        header = f"=== [{flag}] {f['new_path']}"
    if color:
        print(f"\033[1m{header}\033[0m")
    else:
        print(header)
    for line in f.get("diff", "").splitlines():
        if not color:
            print(line)
        elif line.startswith("+++") or line.startswith("---"):
            print(f"\033[1m{line}\033[0m")
        elif line.startswith("+"):
            print(f"\033[32m{line}\033[0m")
        elif line.startswith("-"):
            print(f"\033[31m{line}\033[0m")
        elif line.startswith("@@"):
            print(f"\033[36m{line}\033[0m")
        else:
            print(line)
    print()


def cmd_mr_diff(args: list[str]) -> None:
    """gl mr diff <iid> [pattern] [--stat|--names] [--no-color]  -- MR diff, optionally filtered.

    pattern: case-insensitive substring matched against new/old path
    --stat : one-line per file with +/- counts
    --names: filenames only
    """
    if not args:
        sys.exit("usage: gl mr diff <iid> [pattern] [--stat|--names] [--no-color]")
    iid = args[0]
    flags = {"--stat", "--names", "--no-color"}
    positional = [a for a in args[1:] if a not in flags]
    pattern = positional[0].lower() if positional else None
    want_stat = _has_flag(args, "--stat")
    want_names = _has_flag(args, "--names")
    color = not _has_flag(args, "--no-color") and sys.stdout.isatty()
    if color:
        _enable_windows_ansi()

    data = api.get(f"{api.project_path()}/merge_requests/{iid}/changes")
    files = data.get("changes", [])
    if pattern:
        files = [
            f for f in files
            if pattern in f.get("new_path", "").lower()
            or pattern in f.get("old_path", "").lower()
        ]
    if not files:
        print("(no matching files)")
        return

    if want_names:
        for f in files:
            print(f["new_path"])
        return

    if want_stat:
        total_a = total_d = 0
        rows = []
        for f in files:
            a, d = _count_diff(f.get("diff", ""))
            total_a += a
            total_d += d
            rows.append({"flag": _change_flag(f), "add": f"+{a}", "del": f"-{d}", "path": f["new_path"]})
        _print_table(rows, ["flag", "add", "del", "path"])
        print(f"\n{len(files)} file(s), +{total_a}/-{total_d}")
        return

    for f in files:
        _print_file_diff(f, color)


def cmd_mr_note(args: list[str]) -> None:
    """gl mr note <iid> "<message>"  -- add a comment to the MR."""
    if len(args) < 2:
        sys.exit('usage: gl mr note <iid> "<message>"')
    iid, msg = args[0], " ".join(args[1:])
    r = api.post(f"{api.project_path()}/merge_requests/{iid}/notes", {"body": msg})
    print(f"posted note id={r['id']}")


def _mr_discussions(iid: str) -> list[dict]:
    return api.get_all(
        f"{api.project_path()}/merge_requests/{iid}/discussions",
        {"per_page": 100},
    )


def _discussion_id(discussions: list[dict], token: str) -> str:
    """Resolve a full or prefix discussion id."""
    token = token.lower()
    for d in discussions:
        did = d["id"]
        if did == token or did.lower().startswith(token):
            return did
    sys.exit(f"[gl] discussion not found: {token!r}")


def _fmt_ts(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("T", " ")[:19]


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip())


def _note_location(note: dict) -> str:
    pos = note.get("position") or {}
    path = pos.get("new_path") or pos.get("old_path") or ""
    line = pos.get("new_line") or pos.get("old_line") or ""
    if path:
        return f"{path}:{line}" if line else path
    return ""


def _print_note(note: dict, *, discussion_id: str | None = None, resolved: bool = False,
                indent: str = "  ") -> None:
    author = note.get("author", {}).get("username", "?")
    created = _fmt_ts(note.get("created_at"))
    flags: list[str] = []
    if note.get("system"):
        flags.append("system")
    if note.get("resolvable"):
        flags.append("resolved" if (note.get("resolved") or resolved) else "unresolved")
    loc = _note_location(note)
    if loc:
        flags.append(f"@{loc}")
    flag_s = f" [{', '.join(flags)}]" if flags else ""
    did = f" disc={discussion_id[:8]}" if discussion_id else ""
    print(f"{indent}{author} — {created}{flag_s}{did}")
    body = _strip_html((note.get("body") or "").strip())
    if body:
        for line in body.splitlines():
            print(f"{indent}  {line}")
    else:
        print(f"{indent}  (empty)")


def cmd_mr_comments(args: list[str]) -> None:
    """gl mr comments <iid> [--human] [--unresolved] [--system]  -- list MR discussion comments."""
    if not args or args[0].startswith("--"):
        sys.exit("usage: gl mr comments <iid> [--human] [--unresolved] [--system]")
    iid = args[0]
    human_only = _has_flag(args, "--human")
    unresolved_only = _has_flag(args, "--unresolved")
    include_system = _has_flag(args, "--system")

    mr = api.get(f"{api.project_path()}/merge_requests/{iid}")
    discussions = _mr_discussions(iid)
    print(f"MR !{mr['iid']}: {mr['title']}")
    print(f"  url: {mr['web_url']}")

    shown = 0
    for d in discussions:
        notes = d.get("notes", [])
        if not notes:
            continue
        printable = []
        for n in notes:
            if human_only and (n.get("system") or n.get("author", {}).get("username") in ("codereview",)):
                continue
            if not include_system and n.get("system"):
                continue
            if unresolved_only:
                if not (n.get("resolvable") and not n.get("resolved") and not d.get("resolved")):
                    continue
            printable.append(n)
        if not printable:
            continue
        shown += 1
        print(f"\n--- discussion {d['id'][:8]} ---")
        for n in printable:
            _print_note(n, discussion_id=d["id"], resolved=bool(d.get("resolved")))

    if shown == 0:
        print("\n(no matching comments)")


def cmd_mr_review(args: list[str]) -> None:
    """gl mr review <iid>  -- MR report: status, pipeline, approvals, and review comments."""
    if not args:
        sys.exit("usage: gl mr review <iid>")
    iid = args[0]
    mr = api.get(f"{api.project_path()}/merge_requests/{iid}")
    discussions = _mr_discussions(iid)

    print(f"MR !{mr['iid']}: {mr['title']}")
    print(f"  state       : {mr['state']}  (draft={mr.get('draft', False)})")
    print(f"  author      : {mr['author']['username']}")
    print(f"  source      : {mr['source_branch']} -> {mr['target_branch']}")
    print(f"  url         : {mr['web_url']}")
    if mr.get("head_pipeline"):
        p = mr["head_pipeline"]
        print(f"  pipeline    : #{p['id']}  status={p['status']}")
    try:
        ap = api.get(f"{api.project_path()}/merge_requests/{iid}/approvals")
        approvers = [a["user"]["username"] for a in ap.get("approved_by", [])]
        print(f"  approvals   : {ap.get('approvals_left', '?')} left; approved by: {', '.join(approvers) or '-'}")
    except SystemExit:
        pass

    human: list[tuple[dict, dict]] = []
    unresolved: list[tuple[dict, dict]] = []
    for d in discussions:
        for n in d.get("notes", []):
            if n.get("system"):
                continue
            if n.get("author", {}).get("username") == "codereview":
                continue
            human.append((d, n))
            if n.get("resolvable") and not n.get("resolved") and not d.get("resolved"):
                unresolved.append((d, n))

    print(f"  comments    : {len(human)} human, {len(unresolved)} unresolved, {len(discussions)} thread(s)")

    desc = (mr.get("description") or "").strip()
    if desc:
        print("\n--- description ---")
        print(_strip_html(desc))

    if unresolved:
        print("\n--- unresolved review comments ---")
        for i, (d, n) in enumerate(unresolved, 1):
            loc = _note_location(n)
            loc_s = f" @ {loc}" if loc else ""
            print(f"\n{i}. {n['author']['username']}{loc_s}  (disc={d['id'][:8]})")
            body = _strip_html((n.get("body") or "").strip())
            for line in body.splitlines():
                print(f"   {line}")

    if human:
        print("\n--- all human comments ---")
        for d, n in human:
            _print_note(n, discussion_id=d["id"], resolved=bool(d.get("resolved")))
            print()


def cmd_mr_comment_reply(args: list[str]) -> None:
    """gl mr comment-reply <iid> <discussion-id> "<message>"  -- reply in a discussion thread."""
    if len(args) < 3:
        sys.exit('usage: gl mr comment-reply <iid> <discussion-id> "<message>"')
    iid, disc_token, msg = args[0], args[1], " ".join(args[2:])
    discussions = _mr_discussions(iid)
    disc_id = _discussion_id(discussions, disc_token)
    r = api.post(
        f"{api.project_path()}/merge_requests/{iid}/discussions/{disc_id}/notes",
        {"body": msg},
    )
    print(f"posted reply note id={r['id']} in discussion {disc_id[:8]}")


def cmd_mr_comment_resolve(args: list[str]) -> None:
    """gl mr comment-resolve <iid> <discussion-id>  -- resolve a review thread."""
    if len(args) < 2:
        sys.exit("usage: gl mr comment-resolve <iid> <discussion-id>")
    iid, disc_token = args[0], args[1]
    discussions = _mr_discussions(iid)
    disc_id = _discussion_id(discussions, disc_token)
    api.put(
        f"{api.project_path()}/merge_requests/{iid}/discussions/{disc_id}",
        {"resolved": True},
    )
    print(f"resolved discussion {disc_id[:8]}")


def cmd_mr_comment_unresolve(args: list[str]) -> None:
    """gl mr comment-unresolve <iid> <discussion-id>  -- reopen a resolved thread."""
    if len(args) < 2:
        sys.exit("usage: gl mr comment-unresolve <iid> <discussion-id>")
    iid, disc_token = args[0], args[1]
    discussions = _mr_discussions(iid)
    disc_id = _discussion_id(discussions, disc_token)
    api.put(
        f"{api.project_path()}/merge_requests/{iid}/discussions/{disc_id}",
        {"resolved": False},
    )
    print(f"unresolved discussion {disc_id[:8]}")


def cmd_mr_approve(args: list[str]) -> None:
    """gl mr approve <iid>  -- approve the MR."""
    if not args:
        sys.exit("usage: gl mr approve <iid>")
    r = api.post(f"{api.project_path()}/merge_requests/{args[0]}/approve")
    print(f"approved. approvals={r.get('approvals_left','?')} left")


def cmd_mr_merge(args: list[str]) -> None:
    """gl mr merge <iid> [--now]  -- merge (default: when pipeline succeeds)."""
    if not args:
        sys.exit("usage: gl mr merge <iid> [--now]")
    body = {"should_remove_source_branch": True}
    if not _has_flag(args, "--now"):
        body["merge_when_pipeline_succeeds"] = True
    r = api.put(f"{api.project_path()}/merge_requests/{args[0]}/merge", body)
    print(f"state={r['state']}  merged_at={r.get('merged_at','pending')}")


def cmd_mr_rebase(args: list[str]) -> None:
    """gl mr rebase <iid>  -- request a rebase against target branch."""
    if not args:
        sys.exit("usage: gl mr rebase <iid>")
    api.put(f"{api.project_path()}/merge_requests/{args[0]}/rebase")
    print("rebase requested (async; poll with `gl mr status`).")


def cmd_mr_open(args: list[str]) -> None:
    """gl mr open <iid>  -- open MR web url in default browser."""
    if not args:
        sys.exit("usage: gl mr open <iid>")
    mr = api.get(f"{api.project_path()}/merge_requests/{args[0]}")
    print(mr["web_url"])
    os.startfile(mr["web_url"])  # Windows-only; opens in default browser


def cmd_mr_watch(args: list[str]) -> None:
    """gl mr watch <iid> [--interval SEC]  -- poll head pipeline until final."""
    if not args:
        sys.exit("usage: gl mr watch <iid> [--interval SEC]")
    iid = args[0]
    interval = int(_flag(args, "--interval", "30") or 30)
    last = None
    while True:
        pipes = api.get(f"{api.project_path()}/merge_requests/{iid}/pipelines")
        if not pipes:
            print("(no pipeline yet)")
            time.sleep(interval)
            continue
        p = pipes[0]
        status = p["status"]
        ts = time.strftime("%H:%M:%S")
        if status != last:
            print(f"[{ts}] pipeline #{p['id']} -> {status}   {p['web_url']}")
            last = status
        else:
            print(f"[{ts}] still {status} ...")
        if status in FINAL_PIPELINE_STATES:
            return
        time.sleep(interval)


# ----- pipeline / branch -----

def cmd_pipeline_status(args: list[str]) -> None:
    """gl pipeline status <id>  -- summarize a pipeline."""
    if not args:
        sys.exit("usage: gl pipeline status <id>")
    p = api.get(f"{api.project_path()}/pipelines/{args[0]}")
    print(f"pipeline #{p['id']}  status={p['status']}  ref={p['ref']}")
    print(f"  web_url : {p['web_url']}")
    print(f"  sha     : {p['sha']}")
    print(f"  created : {p['created_at']}  updated : {p['updated_at']}")


def cmd_branch_pipeline(args: list[str]) -> None:
    """gl branch pipeline [branch]  -- latest pipeline for a branch (default: current)."""
    branch = args[0] if args else _current_branch()
    pipes = api.get(f"{api.project_path()}/pipelines", {"ref": branch, "per_page": 1})
    if not pipes:
        print(f"(no pipelines on {branch})")
        return
    p = pipes[0]
    print(f"branch={branch}  pipeline #{p['id']}  status={p['status']}  {p['web_url']}")


# ----- job -----

def cmd_job_log(args: list[str]) -> None:
    """gl job log <job-id> [--tail N]  -- print trace (default: last 80 lines)."""
    if not args:
        sys.exit("usage: gl job log <job-id> [--tail N]")
    n = int(_flag(args, "--tail", "80") or 80)
    text = api.raw_get(f"{api.project_path()}/jobs/{args[0]}/trace")
    print(_tail(text, n))


def cmd_job_retry(args: list[str]) -> None:
    """gl job retry <job-id>  -- retry a single job."""
    if not args:
        sys.exit("usage: gl job retry <job-id>")
    r = api.post(f"{api.project_path()}/jobs/{args[0]}/retry")
    print(f"retried: new job #{r['id']}  status={r['status']}  {r['web_url']}")


def cmd_pipeline_retry(args: list[str]) -> None:
    """gl pipeline retry <pipeline-id>  -- retry all failed jobs in pipeline."""
    if not args:
        sys.exit("usage: gl pipeline retry <pipeline-id>")
    r = api.post(f"{api.project_path()}/pipelines/{args[0]}/retry")
    print(f"pipeline #{r['id']} status={r['status']}  {r['web_url']}")


# ----- issues -----

def cmd_issue_list(args: list[str]) -> None:
    """gl issue list [--mine] [--state opened|closed|all]  -- list issues."""
    state = _flag(args, "--state", "opened") or "opened"
    params = {"state": state, "per_page": 30, "order_by": "updated_at"}
    if _has_flag(args, "--mine"):
        me = api.get("/user")
        params["assignee_id"] = me["id"]
    issues = api.get(f"{api.project_path()}/issues", params)
    if not issues:
        print("(no issues)")
        return
    _print_table(
        [{"iid": i["iid"], "state": i["state"], "assignee": (i.get("assignee") or {}).get("username", "-"),
          "title": i["title"][:60]} for i in issues],
        ["iid", "state", "assignee", "title"],
    )


def cmd_issue_view(args: list[str]) -> None:
    """gl issue view <iid>  -- one issue with description and metadata."""
    if not args:
        sys.exit("usage: gl issue view <iid>")
    i = api.get(f"{api.project_path()}/issues/{args[0]}")
    print(f"Issue #{i['iid']}: {i['title']}")
    print(f"  state     : {i['state']}")
    print(f"  author    : {i['author']['username']}")
    print(f"  assignees : {', '.join(a['username'] for a in i.get('assignees', [])) or '-'}")
    print(f"  labels    : {', '.join(i.get('labels', [])) or '-'}")
    print(f"  url       : {i['web_url']}")
    desc = (i.get("description") or "").strip()
    if desc:
        print("\n--- description ---")
        print(desc)


# ----- repo -----

def cmd_repo_view(_: list[str]) -> None:
    """gl repo view  -- project metadata (default branch, URL, description)."""
    p = api.get(api.project_path())
    print(f"{p['path_with_namespace']}  (id={p['id']})")
    print(f"  default_branch : {p['default_branch']}")
    print(f"  visibility     : {p['visibility']}")
    print(f"  web_url        : {p['web_url']}")
    print(f"  ssh_clone      : {p['ssh_url_to_repo']}")
    print(f"  http_clone     : {p['http_url_to_repo']}")
    if p.get("description"):
        print(f"  description    : {p['description']}")


# ----- MR extras (create, view, checkout, close, reopen) -----

def cmd_mr_create(args: list[str]) -> None:
    """gl mr create [--title "T"] [--desc "D"] [--desc-file <path>] [--target <branch>] [--draft] [--push]  -- create MR from current branch.

    Defaults:
      source_branch = current git branch
      target_branch = project's default branch (usually main)
      title         = subject of the latest commit on the source branch
      description   = empty
    Flags:
      --push        run `git push -u origin <source>` before creating
      --draft       prefix the title with "Draft: "
      --desc-file   read description body from a file (UTF-8)
    """
    source = _current_branch()
    target = _flag(args, "--target")
    title = _flag(args, "--title")
    desc = _flag(args, "--desc") or ""
    desc_file = _flag(args, "--desc-file")
    if desc_file:
        import pathlib
        desc = pathlib.Path(desc_file).read_text(encoding="utf-8")

    if _has_flag(args, "--push"):
        print(f"pushing origin/{source} ...")
        subprocess.run(["git", "push", "-u", "origin", source], check=True)

    if not target:
        proj = api.get(api.project_path())
        target = proj["default_branch"]

    if not title:
        r = subprocess.run(
            ["git", "log", "-1", "--pretty=%s", source],
            capture_output=True, text=True, check=True,
        )
        title = r.stdout.strip() or f"Update {source}"

    if _has_flag(args, "--draft") and not title.lower().startswith("draft:"):
        title = "Draft: " + title

    body = {
        "source_branch": source,
        "target_branch": target,
        "title": title,
        "description": desc,
        "remove_source_branch": True,
    }
    print(f"creating MR: {source} -> {target}")
    print(f"  title: {title}")
    r = api.post(f"{api.project_path()}/merge_requests", body)
    print(f"\nMR !{r['iid']} created: {r['web_url']}")


def cmd_mr_view(args: list[str]) -> None:
    """gl mr view <iid>  -- MR with description, approvals, discussion count."""
    if not args:
        sys.exit("usage: gl mr view <iid>")
    iid = args[0]
    mr = api.get(f"{api.project_path()}/merge_requests/{iid}")
    print(f"MR !{mr['iid']}: {mr['title']}")
    print(f"  state       : {mr['state']}  (draft={mr.get('draft', False)})")
    print(f"  author      : {mr['author']['username']}")
    print(f"  source      : {mr['source_branch']} -> {mr['target_branch']}")
    print(f"  url         : {mr['web_url']}")
    print(f"  discussions : {mr.get('user_notes_count', 0)} note(s)")
    if mr.get("head_pipeline"):
        p = mr["head_pipeline"]
        print(f"  pipeline    : #{p['id']}  status={p['status']}")
    # /approvals is a separate endpoint
    try:
        ap = api.get(f"{api.project_path()}/merge_requests/{iid}/approvals")
        approvers = [a["user"]["username"] for a in ap.get("approved_by", [])]
        print(f"  approvals   : {ap.get('approvals_left', '?')} left; approved by: {', '.join(approvers) or '-'}")
    except SystemExit:
        pass
    desc = (mr.get("description") or "").strip()
    if desc:
        print("\n--- description ---")
        print(desc)


def cmd_mr_checkout(args: list[str]) -> None:
    """gl mr checkout <iid>  -- fetch the MR's source branch and switch to it locally."""
    if not args:
        sys.exit("usage: gl mr checkout <iid>")
    iid = args[0]
    mr = api.get(f"{api.project_path()}/merge_requests/{iid}")
    branch = mr["source_branch"]
    print(f"fetching origin/{branch} ...")
    r1 = subprocess.run(["git", "fetch", "origin", f"{branch}:{branch}"], text=True)
    if r1.returncode != 0:
        # branch may already exist locally -- fetch without ref-update
        subprocess.run(["git", "fetch", "origin", branch], check=True)
    subprocess.run(["git", "checkout", branch], check=True)
    print(f"on branch {branch}")


def _mr_state_event(args: list[str], event: str) -> None:
    if not args:
        sys.exit(f"usage: gl mr {event} <iid>")
    r = api.put(
        f"{api.project_path()}/merge_requests/{args[0]}",
        {"state_event": event},
    )
    print(f"state={r['state']}")


def cmd_mr_close(args: list[str]) -> None:
    """gl mr close <iid>  -- close (do not merge) the MR."""
    _mr_state_event(args, "close")


def cmd_mr_reopen(args: list[str]) -> None:
    """gl mr reopen <iid>  -- reopen a closed MR."""
    _mr_state_event(args, "reopen")


# ----- raw API escape hatch -----

def cmd_api(args: list[str]) -> None:
    """gl api <METHOD> <path> [--json '<json>'] [--param k=v ...]  -- raw GitLab API call.

    Prints the JSON response (indented). The path is appended to the base URL
    /api/v4, so include the leading slash: e.g. /projects/1/labels
    Use for endpoints not yet wrapped by a dedicated verb.
    """
    if len(args) < 2:
        sys.exit("usage: gl api <METHOD> <path> [--json '<json>'] [--param k=v ...]")
    method = args[0].upper()
    path = args[1]
    json_body = None
    if "--json" in args:
        import json as _json
        json_body = _json.loads(args[args.index("--json") + 1])
    params: dict[str, str] = {}
    i = 0
    tail = args[2:]
    while i < len(tail):
        if tail[i] == "--param" and i + 1 < len(tail):
            k, _, v = tail[i + 1].partition("=")
            params[k] = v
            i += 2
        else:
            i += 1

    if method == "GET":
        result = api.get(path, params or None)
    elif method == "POST":
        result = api.post(path, json_body)
    elif method == "PUT":
        result = api.put(path, json_body)
    else:
        sys.exit(f"[gl] unsupported method: {method} (add DELETE etc. in api.py if needed)")
    import json as _json
    print(_json.dumps(result, indent=2, ensure_ascii=False))


# ----- help -----

# Path constants for the docs verb -- resolved from this file's location so
# the tool remains self-contained: no env var required.
_DOCS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs"))
_GL_DOC = os.path.join(_DOCS_ROOT, "gitlab.md")
_ARCH_DOC = os.path.join(_DOCS_ROOT, "ARCHITECTURE.md")


def cmd_help(args: list[str]) -> None:
    """gl help [verb]  -- list verbs, or show full docstring for one verb."""
    if args:
        name = args[0].replace(" ", "-")
        # Support both "gl help mr status" and "gl help mr-status"
        if name not in VERBS and len(args) >= 2:
            name = f"{args[0]}-{args[1]}"
        fn = VERBS.get(name)
        if not fn:
            print(f"unknown verb: {name}\n")
            cmd_help([])
            sys.exit(2)
        print((fn.__doc__ or "(no docstring)").strip())
        return
    print("usage: gl <verb> [args]\n")
    print("Run `gl help <verb>` for details on one verb.")
    print("Run `gl docs` to see the full reference documentation path.\n")
    print("verbs:")
    for name, fn in VERBS.items():
        doc = (fn.__doc__ or "").splitlines()
        first = doc[0] if doc else ""
        print(f"  {name:<20} {first}")


def cmd_docs(args: list[str]) -> None:
    """gl docs [--open]  -- print (or open) the full markdown reference."""
    print("Full reference: " + _GL_DOC)
    print("Architecture  : " + _ARCH_DOC)
    if _has_flag(args, "--open"):
        os.startfile(_GL_DOC)  # Windows: opens in the default .md handler


VERBS = {
    # session
    "me": cmd_me,
    # MR read
    "mr-status": cmd_mr_status,
    "mr-view": cmd_mr_view,
    "mr-pipeline": cmd_mr_pipeline,
    "mr-list": cmd_mr_list,
    "mr-changes": cmd_mr_changes,
    "mr-commits": cmd_mr_commits,
    "mr-diff": cmd_mr_diff,
    # MR write
    "mr-create": cmd_mr_create,
    "mr-note": cmd_mr_note,
    "mr-comments": cmd_mr_comments,
    "mr-review": cmd_mr_review,
    "mr-comment-reply": cmd_mr_comment_reply,
    "mr-comment-resolve": cmd_mr_comment_resolve,
    "mr-comment-unresolve": cmd_mr_comment_unresolve,
    "mr-approve": cmd_mr_approve,
    "mr-merge": cmd_mr_merge,
    "mr-rebase": cmd_mr_rebase,
    "mr-close": cmd_mr_close,
    "mr-reopen": cmd_mr_reopen,
    "mr-open": cmd_mr_open,
    "mr-checkout": cmd_mr_checkout,
    "mr-watch": cmd_mr_watch,
    # issues
    "issue-list": cmd_issue_list,
    "issue-view": cmd_issue_view,
    # repo
    "repo-view": cmd_repo_view,
    # pipeline / branch
    "pipeline-status": cmd_pipeline_status,
    "pipeline-retry": cmd_pipeline_retry,
    "branch-pipeline": cmd_branch_pipeline,
    # job
    "job-log": cmd_job_log,
    "job-retry": cmd_job_retry,
    # escape hatch
    "api": cmd_api,
    # misc
    "help": cmd_help,
    "docs": cmd_docs,
}

