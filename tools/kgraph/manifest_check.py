"""Which files added to a markets-data range have an entry in a MANIFEST.json, read only through git.

    python3 -m tools.kgraph.manifest_check --data <markets-data checkout> --range <A>..<B>

For the commits after A up to B it prints one line for every file added by any commit of the range:
its path, whether it still exists at B, its bytes at B, and either each manifest holding an entry for it
(with whether the entry's bytes and sha256 equal the file's at B, compared only where the entry carries
them) or the words that no manifest holds an entry for it. The manifests are the files at B whose name
holds "manifest" (any case) and ends ".json", each read with `git show B:<path>`. A manifest whose shape
is not read is named. Nothing is written. It gives no verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

LIST_KEYS = ("entries", "files")
PATH_KEYS = ("path", "markets_data_path")


class Unreadable(Exception):
    pass


def _git(data: Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(data), *args], capture_output=True)
    if r.returncode:
        raise Unreadable(r.stderr.decode("utf-8", "replace").strip())
    return r.stdout


def _blob(data: Path, commit: str, path: str) -> bytes | None:
    r = subprocess.run(["git", "-C", str(data), "show", f"{commit}:{path}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def _entries(doc) -> list | None:
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for k in LIST_KEYS:
            if isinstance(doc.get(k), list):
                return doc[k]
    return None


def _manifests(data: Path, b: str) -> tuple[dict[str, list], list[str]]:
    read: dict[str, list] = {}
    not_read: list[str] = []
    names = _git(data, "ls-tree", "-r", "-z", "--name-only", b).decode("utf-8", "surrogateescape").split("\0")
    for p in sorted(n for n in names if n):
        base = p.rsplit("/", 1)[-1].lower()
        if "manifest" not in base or not base.endswith(".json"):
            continue
        raw = _blob(data, b, p)
        try:
            ents = _entries(json.loads(raw)) if raw is not None else None
        except ValueError:
            ents = None
        if ents is None:
            not_read.append(p)
        else:
            read[p] = ents
    return read, not_read


def _added(data: Path, a: str, b: str) -> list[str]:
    out = _git(data, "log", "--diff-filter=A", "--no-renames", "--name-only", "-z", "--format=", f"{a}..{b}")
    seen: dict[str, None] = {}
    for p in out.decode("utf-8", "surrogateescape").split("\0"):
        if p.strip("\n"):
            seen.setdefault(p.strip("\n"), None)
    return list(seen)


def _compare(entry: dict, blob: bytes) -> str:
    parts = []
    if "bytes" in entry:
        parts.append("bytes equal" if entry["bytes"] == len(blob) else "bytes not equal")
    else:
        parts.append("bytes not in entry")
    if "sha256" in entry:
        parts.append("sha256 equal" if entry["sha256"] == hashlib.sha256(blob).hexdigest() else "sha256 not equal")
    else:
        parts.append("sha256 not in entry")
    return ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="which files added in a markets-data range have a manifest entry")
    ap.add_argument("--data", required=True, help="a markets-data checkout")
    ap.add_argument("--range", required=True, dest="rng", help="A..B: the commits after A up to B")
    a = ap.parse_args(argv)
    data = Path(a.data)
    try:
        _git(data, "rev-parse", "--git-dir")
    except Unreadable as e:
        print(f"cannot read the checkout {data}: {e}")
        return 2
    if ".." not in a.rng or a.rng.count("..") != 1 or "..." in a.rng:
        print(f"cannot read the range {a.rng!r}: it must be written A..B")
        return 2
    lo, hi = a.rng.split("..")
    try:
        _git(data, "rev-parse", "--verify", lo + "^{commit}")
        b = _git(data, "rev-parse", "--verify", hi + "^{commit}").decode().strip()
        added = _added(data, lo, hi)
        read, not_read = _manifests(data, b)
    except Unreadable as e:
        print(f"cannot read the range {a.rng} in {data}: {e}")
        return 2
    for p in not_read:
        print(f"manifest {p}: its shape was not read")
    with_entry = no_entry = gone = 0
    for p in added:
        blob = _blob(data, b, p)
        if blob is None:
            gone += 1
        held = []
        for m, ents in read.items():
            for e in ents:
                if isinstance(e, dict) and any(e.get(k) == p for k in PATH_KEYS):
                    held.append(f"{m}: " + (_compare(e, blob) if blob is not None else "file gone at B, nothing compared"))
        where = "gone at B | bytes at B none" if blob is None else f"exists at B | bytes at B {len(blob)}"
        if held:
            with_entry += 1
            tail = " | ".join(held)
        else:
            no_entry += 1
            tail = "no manifest holds an entry for it"
        print(f"{p} | {where} | {tail}")
    print(f"COUNTS added={len(added)} with_entry={with_entry} no_entry={no_entry} gone_at_B={gone} "
          f"manifests_read={len(read)} manifests_shape_not_read={len(not_read)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
