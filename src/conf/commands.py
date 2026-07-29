"""Verb implementations for ``conf`` (Confluence Server).

Same conventions as ``jira/commands.py``: one verb == one action, positional
args first then flags, first docstring line is the usage summary that drives
``conf help``.
"""
from __future__ import annotations

import os
import re
import sys
import textwrap
import webbrowser
from html.parser import HTMLParser
from typing import Callable

from . import api


# ---------------------------------------------------------------------------
# tiny arg helpers (same style as gitlab/jira -- no argparse)
# ---------------------------------------------------------------------------

def _flag(args: list[str], name: str, default: str | None = None) -> str | None:
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


# ---------------------------------------------------------------------------
# HTML -> text (stdlib only). Enough for reading, not for round-tripping.
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    _BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "pre", "blockquote", "section", "article", "hr"}
    _HEADING = {"h1", "h2", "h3", "h4", "h5", "h6"}
    _SKIP = {"script", "style"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag in self._HEADING:
            self._heading = tag
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in self._BLOCK:
            self.parts.append("\n")
        elif tag == "li":
            self.parts.append("\n* ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag in self._HEADING:
            self._heading = None
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        # collapse >2 blank lines to exactly 2; trim trailing ws per line
        lines = [ln.rstrip() for ln in raw.splitlines()]
        out: list[str] = []
        blank = 0
        for ln in lines:
            if not ln.strip():
                blank += 1
                if blank <= 1:
                    out.append("")
                continue
            blank = 0
            out.append(ln)
        return "\n".join(out).strip()


def _html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return p.text()


def _first_line(s: str | None, width: int = 90) -> str:
    if not s:
        return ""
    first = s.strip().splitlines()[0]
    return first if len(first) <= width else first[: width - 1] + "\u2026"


# ---------------------------------------------------------------------------
# verbs
# ---------------------------------------------------------------------------

def cmd_me(_: list[str]) -> None:
    """conf me  -- current user (sanity-check the token)."""
    u = api.get("/user/current")
    print(f"{u.get('username')}  <{u.get('email','?')}>  "
          f"displayName={u.get('displayName')}  type={u.get('type')}")


def cmd_page_view(args: list[str]) -> None:
    """conf page view <id-or-url> [--html|--storage|--raw] [--width N]  -- print a page."""
    as_html = _has_flag(args, "--html")
    as_storage = _has_flag(args, "--storage")
    as_raw = _has_flag(args, "--raw")
    width = int(_flag(args, "--width", "0") or 0)
    if not args:
        _die("usage: conf page view <id-or-url> [--html|--storage|--raw]")
    pid = api.resolve_page_id(args[0])
    expand = "body.storage" if as_storage else "body.view"
    d = api.get(f"/content/{pid}",
                params={"expand": f"{expand},space,version,ancestors"})
    if as_raw:
        import json as _json
        print(_json.dumps(d, indent=2))
        return
    space = d.get("space") or {}
    v = d.get("version") or {}
    ancestors = [a.get("title") for a in d.get("ancestors", [])]
    print(f"{d.get('title')}")
    print(f"  id       : {d.get('id')}")
    print(f"  space    : {space.get('key')} - {space.get('name')}")
    print(f"  version  : {v.get('number')} by {v.get('by',{}).get('displayName')} at {v.get('when')}")
    if ancestors:
        print(f"  path     : {' > '.join(ancestors)} > {d.get('title')}")
    print(f"  url      : {api.browse_url(pid, d.get('title'), space.get('key'))}")
    body = d.get("body", {}).get("storage" if as_storage else "view", {}).get("value", "")
    print(f"\n--- body ({'storage/xhtml' if as_storage else 'rendered'}, {len(body)} bytes) ---\n")
    if as_html or as_storage:
        print(body)
    else:
        text = _html_to_text(body)
        if width:
            wrapped = []
            for para in text.split("\n"):
                if not para.strip() or para.lstrip().startswith(("*", "#")):
                    wrapped.append(para)
                else:
                    wrapped.extend(textwrap.wrap(para, width=width) or [""])
            text = "\n".join(wrapped)
        print(text)


def cmd_page_url(args: list[str]) -> None:
    """conf page url <id-or-url>  -- print the canonical browse URL."""
    if not args:
        _die("usage: conf page url <id-or-url>")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}", params={"expand": "space"})
    print(api.browse_url(pid, d.get("title"), (d.get("space") or {}).get("key")))


def cmd_page_open(args: list[str]) -> None:
    """conf page open <id-or-url>  -- open in the default browser."""
    if not args:
        _die("usage: conf page open <id-or-url>")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}", params={"expand": "space"})
    url = api.browse_url(pid, d.get("title"), (d.get("space") or {}).get("key"))
    print(url)
    webbrowser.open(url)


def cmd_page_children(args: list[str]) -> None:
    """conf page children <id-or-url> [--limit N]  -- list child pages."""
    limit = int(_flag(args, "--limit", "50") or 50)
    if not args:
        _die("usage: conf page children <id-or-url>")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}/child/page", params={"limit": limit})
    results = d.get("results", [])
    if results:
        print(f"{'ID':<12} TITLE")
        print(f"{'-'*12} {'-'*40}")
    for r in results:
        print(f"{r.get('id'):<12} {r.get('title')}")
    print(f"\n-- {len(results)} child pages of {pid} --")


def cmd_page_attachments(args: list[str]) -> None:
    """conf page attachments <id-or-url> [--limit N]  -- list attachments with download URLs."""
    limit = int(_flag(args, "--limit", "50") or 50)
    if not args:
        _die("usage: conf page attachments <id-or-url>")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}/child/attachment", params={"limit": limit})
    results = d.get("results", [])
    if results:
        print(f"{'ID':<14} {'SIZE':>10}  {'FILENAME':<40}  DOWNLOAD-PATH")
        print(f"{'-'*14} {'-'*10}  {'-'*40}  {'-'*13}")
    for r in results:
        ext = r.get("extensions") or {}
        size = ext.get("fileSize", "?")
        dl = (r.get("_links") or {}).get("download", "")
        title = r.get("title", "")
        print(f"{r.get('id'):<14} {size:>10}  {title:<40}  {dl}")
    print(f"\n-- {len(results)} attachments on {pid} --")


def cmd_page_download(args: list[str]) -> None:
    """conf page download <id-or-url> [--out DIR] [--no-attachments]  -- save page body + attachments to disk."""
    out = _flag(args, "--out", ".") or "."
    skip_att = _has_flag(args, "--no-attachments")
    if not args:
        _die("usage: conf page download <id-or-url> [--out DIR] [--no-attachments]")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}",
                params={"expand": "body.storage,body.view,space,version,ancestors"})
    safe = re.sub(r"[^\w\-]+", "_", d.get("title", pid))[:80] or pid
    base = os.path.join(out, f"{pid}_{safe}")
    os.makedirs(base, exist_ok=True)

    html = d.get("body", {}).get("view", {}).get("value", "") or ""
    storage = d.get("body", {}).get("storage", {}).get("value", "") or ""
    text = _html_to_text(html)

    _write(os.path.join(base, "page.html"), html)
    _write(os.path.join(base, "page.storage.xhtml"), storage)
    _write(os.path.join(base, "page.txt"), text)
    _write(os.path.join(base, "meta.json"),
           _dumps({
               "id": d.get("id"),
               "title": d.get("title"),
               "space": (d.get("space") or {}).get("key"),
               "version": (d.get("version") or {}).get("number"),
               "when": (d.get("version") or {}).get("when"),
               "ancestors": [a.get("title") for a in d.get("ancestors", [])],
               "url": api.browse_url(pid, d.get("title"), (d.get("space") or {}).get("key")),
           }))
    print(f"saved page files to {base}\\")

    if skip_att:
        return
    att = api.get(f"/content/{pid}/child/attachment", params={"limit": 200})
    results = att.get("results", [])
    if not results:
        print("(no attachments)")
        return
    att_dir = os.path.join(base, "attachments")
    os.makedirs(att_dir, exist_ok=True)
    for r in results:
        dl = (r.get("_links") or {}).get("download")
        if not dl:
            continue
        fname = re.sub(r"[^\w\-. ]+", "_", r.get("title", r["id"]))
        target = os.path.join(att_dir, fname)
        n = api.download_binary(dl, target)
        print(f"  attachment: {fname}  ({n} bytes)")


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _dumps(obj: object) -> str:
    import json as _json
    return _json.dumps(obj, indent=2)


def cmd_page_comments(args: list[str]) -> None:
    """conf page comments <id-or-url> [--limit N]  -- list comments on a page."""
    limit = int(_flag(args, "--limit", "50") or 50)
    if not args:
        _die("usage: conf page comments <id-or-url>")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}/child/comment",
                params={"limit": limit, "expand": "body.view,version"})
    results = d.get("results", [])
    for c in results:
        v = c.get("version") or {}
        author = v.get("by", {}).get("displayName", "?")
        when = v.get("when", "?")
        html = c.get("body", {}).get("view", {}).get("value", "")
        text = _html_to_text(html)
        print(f"--- {when}  {author}  (id={c.get('id')})")
        for line in text.splitlines():
            print(f"  {line}")
    print(f"\n-- {len(results)} comments on {pid} --")


def cmd_page_labels(args: list[str]) -> None:
    """conf page labels <id-or-url>  -- list labels on a page."""
    if not args:
        _die("usage: conf page labels <id-or-url>")
    pid = api.resolve_page_id(args[0])
    d = api.get(f"/content/{pid}/label")
    labels = [r.get("name") for r in d.get("results", [])]
    print(", ".join(labels) if labels else "(no labels)")


def cmd_search(args: list[str]) -> None:
    """conf search "<CQL>" [--limit N]  -- CQL content search."""
    limit = int(_flag(args, "--limit", "20") or 20)
    if not args:
        _die('usage: conf search "<CQL>" [--limit N]')
    cql = " ".join(args)
    _print_search(cql, limit)


def cmd_recent(args: list[str]) -> None:
    """conf recent [--space KEY] [--days N] [--limit N]  -- pages recently modified."""
    space = _flag(args, "--space", api.DEFAULT_SPACE_KEY)
    days = int(_flag(args, "--days", "1") or 1)
    limit = int(_flag(args, "--limit", "20") or 20)
    cql = (f'space = {space} AND type = page '
           f'AND lastmodified >= now("-{days}d") ORDER BY lastmodified DESC')
    _print_search(cql, limit)


def _print_search(cql: str, limit: int) -> None:
    r = api.get("/content/search",
                params={"cql": cql, "limit": limit, "expand": "space,version"})
    results = r.get("results", [])
    if not results:
        print(f"no results  cql: {cql}")
        return
    print(f"{'ID':<12} {'SPACE':<8} {'MODIFIED':<10}  TITLE")
    print(f"{'-'*12} {'-'*8} {'-'*10}  {'-'*40}")
    for p in results:
        space = (p.get("space") or {}).get("key", "?")
        v = (p.get("version") or {}).get("when", "?")[:10]
        print(f"{p.get('id'):<12} {space:<8} {v:<10}  {_first_line(p.get('title'), 90)}")
    print(f"\n-- {len(results)}/{r.get('size', len(results))} shown  --  cql: {cql}")


def cmd_space_view(args: list[str]) -> None:
    """conf space view <KEY>  -- space metadata."""
    if not args:
        _die("usage: conf space view <KEY>")
    key = args[0]
    d = api.get(f"/space/{key}", params={"expand": "description.plain,homepage"})
    print(f"{d.get('key')}  {d.get('name')}  type={d.get('type')}")
    desc = (d.get("description") or {}).get("plain", {}).get("value", "")
    if desc:
        print(f"  description: {desc}")
    hp = d.get("homepage") or {}
    if hp:
        print(f"  homepage   : id={hp.get('id')}  title={hp.get('title')}")


def cmd_space_list(args: list[str]) -> None:
    """conf space list [--limit N]  -- list spaces (paginated)."""
    limit = int(_flag(args, "--limit", "50") or 50)
    d = api.get("/space", params={"limit": limit})
    results = d.get("results", [])
    if results:
        print(f"{'KEY':<20} {'TYPE':<10} NAME")
        print(f"{'-'*20} {'-'*10} {'-'*40}")
    for s in results:
        print(f"{s.get('key'):<20} {s.get('type'):<10} {s.get('name')}")
    print(f"\n-- {len(results)} spaces shown --")


def cmd_api(args: list[str]) -> None:
    """conf api <METHOD> <path> [--json '<json>']  -- raw REST call. Path starts with '/'."""
    import json as _json
    body_str = _flag(args, "--json")
    if len(args) < 2:
        _die("usage: conf api <GET|POST|PUT|DELETE> <path> [--json '<json>']")
    method, path = args[0].upper(), args[1]
    body = _json.loads(body_str) if body_str else None
    if method == "GET":
        r = api.get(path)
    elif method == "POST":
        r = api.post(path, body)
    elif method == "PUT":
        r = api.put(path, body)
    elif method == "DELETE":
        r = api.delete(path)
    else:
        _die(f"unsupported method: {method}")
    print(_json.dumps(r, indent=2) if r is not None else "(no body)")


def cmd_docs(args: list[str]) -> None:
    """conf docs [--open]  -- print (or open) the full markdown reference path."""
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "docs", "confluence.md")
    )
    print(path)
    if "--open" in args:
        os.startfile(path)  # noqa: S606


def cmd_help(args: list[str]) -> None:
    """conf help [verb]  -- list verbs, or show full docstring for one verb."""
    if args:
        candidate = "-".join(args)
        if candidate not in VERBS and len(args) >= 2:
            candidate = f"{args[0]}-{args[1]}"
        fn = VERBS.get(candidate) or VERBS.get(args[0])
        if not fn:
            print(f"unknown verb: {' '.join(args)}")
            sys.exit(2)
        print(textwrap.dedent(fn.__doc__ or "(no docstring)").strip())
        return
    print("usage: conf <verb> [args]\n")
    print("Run `conf help <verb>` for details on one verb.")
    print("Run `conf docs` to see the full reference documentation path.\n")
    print("verbs:")
    for name, fn in VERBS.items():
        first = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
        print(f"  {name:<20} {first}")


VERBS: dict[str, Callable[[list[str]], None]] = {
    "me": cmd_me,
    "page-view": cmd_page_view,
    "page-url": cmd_page_url,
    "page-open": cmd_page_open,
    "page-children": cmd_page_children,
    "page-attachments": cmd_page_attachments,
    "page-comments": cmd_page_comments,
    "page-labels": cmd_page_labels,
    "page-download": cmd_page_download,
    "search": cmd_search,
    "recent": cmd_recent,
    "space-view": cmd_space_view,
    "space-list": cmd_space_list,
    "api": cmd_api,
    "docs": cmd_docs,
    "help": cmd_help,
}






