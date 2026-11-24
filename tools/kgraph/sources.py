"""Source and Commit nodes: the file a thing was read from.

One file, one id: `src:<repo>:<path>`. The node carries the commit that last changed the file, its
bytes and its sha256. When the file changes, the node is written again as its next revision and the
earlier revision stays in the graph, so nothing that pointed at the file is orphaned or doubled.
What was read at which wording is kept on the reader's own line (a claim stores `source_commit`, its
lines and its quote), and the quote can be checked against the file again at any time.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .store import edge_id

REPOS = {  # the names used in ids
    "markets-data": "DavisAI1974/markets-data",
    "Markets": "DavisAI1974/Markets",
    "paper-trading-platform": "DavisAI1974/paper-trading-platform",
}


def git(repo_dir, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {repo_dir}: {r.stderr.strip()}")
    return r.stdout.strip()


def head(repo_dir) -> str:
    return git(repo_dir, "rev-parse", "HEAD")


def code_stamp(module: str) -> str:
    """`code:<module>@<commit>` of the Markets checkout this code runs from: who wrote a line."""
    here = Path(__file__).resolve().parents[2]
    try:
        commit = git(here, "rev-parse", "--short=10", "HEAD")
        dirty = "+uncommitted" if git(here, "status", "--porcelain", "--", "tools") else ""
    except RuntimeError:
        commit, dirty = "unknown", ""
    return f"code:{module}@{commit}{dirty}"


def last_commit(repo_dir, rel_path: str) -> str | None:
    """The commit that last changed the file, or None if the file is not committed yet."""
    out = git(repo_dir, "log", "-1", "--format=%H", "--", rel_path)
    return out or None


NOT_IN_CHECKOUT = "listed_file_not_in_checkout"


def kind_of(rel_path: str, in_checkout: bool = True) -> str:
    """The one place that decides a Source's `kind` from its path, so two writers can never flip one
    Source back and forth: a name starting "MANIFEST" or ending "MANIFEST.json" is a manifest, ".xlsx" a
    workbook, any other file "file"; a listed file that is not in the checkout keeps its own kind."""
    if not in_checkout:
        return NOT_IN_CHECKOUT
    name = rel_path.rsplit("/", 1)[-1]
    if name.startswith("MANIFEST") or name.endswith("MANIFEST.json"):
        return "manifest"
    if name.endswith(".xlsx"):
        return "workbook"
    return "file"


def listed_node(repo: str, rel_path: str, extra: dict | None = None) -> dict:
    """The Source node of a file a manifest lists that this checkout does not hold."""
    attrs = {"kind": kind_of(rel_path, False), "repo": REPOS.get(repo, repo), "path": rel_path}
    attrs.update(extra or {})
    return {"id": source_id(repo, rel_path), "type": "Source", "attrs": attrs}


def source_node(repo: str, repo_dir, rel_path: str, *, extra: dict | None = None) -> dict:
    """The Source node of one file as it stands in the checkout. Refuses a file with uncommitted
    changes: a source is always a committed wording."""
    p = Path(repo_dir) / rel_path
    raw = p.read_bytes()
    commit = last_commit(repo_dir, rel_path)
    if commit is None:
        raise RuntimeError(f"{rel_path} is not committed in {repo}: commit it before it is a source")
    if git(repo_dir, "status", "--porcelain", "--", rel_path):
        raise RuntimeError(f"{rel_path} has uncommitted changes in {repo}: commit it before it is a source")
    kind = kind_of(rel_path)
    attrs = {"kind": kind, "repo": REPOS.get(repo, repo), "path": rel_path, "commit": commit,
             "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if kind == "file" and not rel_path.endswith((".xlsx", ".parquet", ".gz", ".zst", ".npz", ".sqlite")):
        attrs["lines"] = raw.count(b"\n")
    attrs.update(extra or {})
    return {"id": source_id(repo, rel_path), "type": "Source", "attrs": attrs}


def source_id(repo: str, rel_path: str, branch: str | None = None) -> str:
    """`src:<repo>:<path>`, or `src:<repo>@<branch>:<path>` for a file that lives on another branch."""
    return f"src:{repo}@{branch}:{rel_path}" if branch else f"src:{repo}:{rel_path}"


def commit_node(repo: str, repo_dir, sha: str) -> dict:
    full = git(repo_dir, "rev-parse", sha)
    subject, date = git(repo_dir, "log", "-1", "--format=%s%x00%cI", full).split("\x00")
    return {"id": f"commit:{repo}:{full[:10]}", "type": "Commit",
            "attrs": {"repo": REPOS.get(repo, repo), "sha": full, "subject": subject, "date": date}}


def link(etype: str, src: str, dst: str, key: str = "", **attrs) -> dict:
    return {"id": edge_id(etype, src, dst, key), "type": etype, "src": src, "dst": dst, "attrs": attrs}
