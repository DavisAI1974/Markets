#!/usr/bin/env python3
"""Markets Terminal - a READ-ONLY MCP server over the Markets repository. (C2C-004.)

Two tools, nothing else:
  markets_repo_status  - repo path, branch, HEAD, and worktree status
  markets_read_file    - UTF-8 text read of a path INSIDE the Markets repository

DELIBERATELY ABSENT, and this is the security posture rather than an oversight: no command
execution, no writes of any kind, no git mutation, no AWS or IAM surface, no secret retrieval, no
unrestricted filesystem access, and no network listener. Transport is stdio only - the process
speaks to whatever launched it and to nothing else, so running the file exposes nothing on its
own.

WHY THE READ TOOL IS THE RISKY ONE, and what actually stops it. A read tool over a repository is an
exfiltration path if its boundary check is wrong, so the check does not trust the string it is
given:

  * the path is resolved with `os.path.realpath` FIRST, which collapses `..` and follows symlinks,
    and only then compared against the realpath of the repo root. Comparing before resolution is
    the classic hole - `repo/../../etc/passwd` starts with the repo prefix as a string.
  * the comparison is on path COMPONENTS (`os.path.commonpath`), not a `startswith` on the raw
    string, so a sibling directory named `Markets-secrets` cannot pass by sharing a prefix.
  * a deny list runs after containment, on the repo-relative path, for names that carry secrets even
    when they live inside the repo.
  * binary is refused by decoding as UTF-8 strictly and failing closed, not by extension guessing.
  * size is capped so a single call cannot drain a large artifact.

The credential files this project actually uses (`~/.config/markets/env`, `~/.aws/credentials`)
live OUTSIDE the repository by design (D34/D48), so containment alone already excludes them; the
deny list is the second layer for anything that later lands inside.
"""
from __future__ import annotations

import json
import os
import subprocess

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

# The repo root is derived from THIS FILE's own location - the file lives at <repo>/mcp_server/, so
# one level up from its directory is the root. Deriving it beats hardcoding `/home/user/Markets`
# because the same file has to run on the EC2 box, where the checkout path differs; a hardcoded
# root would silently serve the wrong tree (or nothing) there. MARKETS_REPO overrides for the case
# where the server is deliberately pointed at a checkout other than its own.
_DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.realpath(os.environ.get("MARKETS_REPO", _DEFAULT_REPO))
MAX_BYTES = 256 * 1024

# Names that carry secrets even inside the repo. Matched case-insensitively against the
# repo-relative path, AFTER containment has already passed.
DENY_SUBSTRINGS = (
    ".env", "credentials", "id_rsa", "id_ed25519", ".pem", ".key", ".p12", ".pfx",
    "secret", "aws.env", "bento.env", ".netrc", ".npmrc", ".pypirc", ".git/config",
)

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True,
                             timeout=20, check=False)
        return (out.stdout or out.stderr or "").strip()
    except Exception as exc:  # a broken git must not take the server down
        return "git error: %s: %s" % (type(exc).__name__, exc)


def _read_file_impl(path: str) -> str:
    """Containment first, then content. Every rejection names its reason."""
    if not isinstance(path, str) or not path.strip():
        return "REFUSED: empty path"

    candidate = path if os.path.isabs(path) else os.path.join(REPO, path)
    real = os.path.realpath(candidate)          # resolves .. and symlinks BEFORE any comparison

    try:
        # component-wise containment; a string prefix test would admit sibling dirs
        if os.path.commonpath([real, REPO]) != REPO:
            return "REFUSED: path resolves outside the Markets repository"
    except ValueError:
        return "REFUSED: path is not comparable to the repository root (different drive/root)"

    rel = os.path.relpath(real, REPO)
    low = rel.lower()
    for bad in DENY_SUBSTRINGS:
        if bad in low:
            return "REFUSED: path matches a credential/secret deny rule (%r)" % bad

    if not os.path.isfile(real):
        return "REFUSED: not a regular file"

    size = os.path.getsize(real)
    if size > MAX_BYTES:
        return "REFUSED: file is %d bytes, over the %d-byte read cap" % (size, MAX_BYTES)

    try:
        with open(real, "rb") as fh:
            raw = fh.read()
        return raw.decode("utf-8")               # strict: binary fails closed here
    except UnicodeDecodeError:
        return "REFUSED: file is not valid UTF-8 text (binary refused)"
    except OSError as exc:
        return "REFUSED: unreadable (%s)" % type(exc).__name__


app = MCPServer("markets-terminal")


@app.tool(
    description="Report the Markets repository path, current branch, HEAD commit and worktree status. Read-only.",
    annotations=READ_ONLY_ANNOTATIONS,
)
def markets_repo_status() -> str:
    return json.dumps({
        "repo_path": REPO,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": _git("rev-parse", "HEAD"),
        "head_subject": _git("log", "-1", "--format=%s"),
        "status_short": _git("status", "--short"),
        "read_only": True,
    }, indent=2)


@app.tool(
    description=(
        "Read UTF-8 text from a path inside the Markets repository. Rejects path traversal, paths "
        "outside the repo, credential-bearing paths, binary files, and files over 256KB. Read-only."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
)
def markets_read_file(path: str) -> str:
    return _read_file_impl(path)


if __name__ == "__main__":
    app.run(transport="stdio")
