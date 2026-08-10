#!/usr/bin/env python3
"""Markets Terminal - a READ-ONLY MCP server over the Markets repository. (C2C-004.)

Two tools, nothing else:
  markets_repo_status  - repo path, branch, HEAD, and worktree status
  markets_read_file    - UTF-8 text read of a path INSIDE the Markets repository

DELIBERATELY ABSENT, and this is the security posture rather than an oversight: no command
execution, no writes of any kind, no git mutation, no AWS or IAM surface, no secret retrieval, no
unrestricted filesystem access, and no network listener. Transport is stdio only - the process
speaks to whatever launched it and to nothing else, so running this file exposes nothing on its
own.
"""
from __future__ import annotations

import json
import os
import subprocess

from mcp.server import MCPServer

_DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.realpath(os.environ.get("MARKETS_REPO", _DEFAULT_REPO))
MAX_BYTES = 256 * 1024

DENY_SUBSTRINGS = (
    ".env", "credentials", "id_rsa", "id_ed25519", ".pem", ".key", ".p12", ".pfx",
    "secret", "aws.env", "bento.env", ".netrc", ".npmrc", ".pypirc", ".git/config",
)


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True,
                             timeout=20, check=False)
        return (out.stdout or out.stderr or "").strip()
    except Exception as exc:
        return "git error: %s: %s" % (type(exc).__name__, exc)


def _read_file_impl(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        return "REFUSED: empty path"

    candidate = path if os.path.isabs(path) else os.path.join(REPO, path)
    real = os.path.realpath(candidate)

    try:
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
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return "REFUSED: file is not valid UTF-8 text (binary refused)"
    except OSError as exc:
        return "REFUSED: unreadable (%s)" % type(exc).__name__


app = MCPServer("markets-terminal")


@app.tool(description="Report the Markets repository path, current branch, HEAD commit and worktree status. Read-only.")
def markets_repo_status() -> str:
    return json.dumps({
        "repo_path": REPO,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": _git("rev-parse", "HEAD"),
        "head_subject": _git("log", "-1", "--format=%s"),
        "status_short": _git("status", "--short"),
        "read_only": True,
    }, indent=2)


@app.tool(description="Read UTF-8 text from a path inside the Markets repository. Rejects path traversal, paths outside the repo, credential-bearing paths, binary files, and files over 256KB. Read-only.")
def markets_read_file(path: str) -> str:
    return _read_file_impl(path)


if __name__ == "__main__":
    app.run(transport="stdio")
