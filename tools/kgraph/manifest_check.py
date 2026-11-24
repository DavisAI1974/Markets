"""Which files added to a markets-data range have an entry in a MANIFEST.json, read only through git.

    python3 -m tools.kgraph.manifest_check --data <markets-data checkout> --range <A>..<B>

For the commits after A up to B it prints one line for every file added by any commit of the range:
its path, whether it still exists at B, its bytes at B, and either each manifest holding an entry for it
(with whether the entry's bytes and sha256 equal the file's at B, compared only where the entry carries
them, and which way the entry's path matched) or the words that no manifest holds an entry for it.
The manifests are the files at B whose name holds "manifest" (any case) and ends ".json", each read with
`git show B:<path>`. A manifest whose shape is not read is named. Nothing is written. It gives no verdict.

An entry's path is read two ways, after a leading "./" is dropped: as written, from the repository's root
("path as written"); and joined to the folder the manifest sits in ("path relative to the manifest's
folder"). An entry whose path ends with "/" names a folder and is not an entry for a file: a file under it
is printed with the words that the manifest names its folder and is counted apart (under_a_folder_entry).
Entries that are not objects, or carry neither "path" nor "markets_data_path", are named for each manifest
(how many of how many, and the keys they do carry); those keys are not read as paths.
A file is gone at B when `git ls-tree` at B does not list it; any other failure of `git show` ends the
command with exit 2 and a sentence naming the path.
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
AS_WRITTEN = "path as written"
RELATIVE = "path relative to the manifest's folder"


class Unreadable(Exception):
    pass


def _git(data: Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(data), *args], capture_output=True)
    if r.returncode:
        raise Unreadable(r.stderr.decode("utf-8", "replace").strip())
    return r.stdout


def _blob(data: Path, commit: str, path: str) -> bytes:
    """The file's bytes at commit. The caller knows the path is listed at commit; a failure here is a failed read."""
    r = subprocess.run(["git", "-C", str(data), "show", f"{commit}:{path}"], capture_output=True)
    if r.returncode:
        raise Unreadable(f"the file {path} is listed at {commit} but could not be read: "
                         + r.stderr.decode("utf-8", "replace").strip())
    return r.stdout


def _tree(data: Path, b: str) -> set[str]:
    names = _git(data, "ls-tree", "-r", "-z", "--name-only", b).decode("utf-8", "surrogateescape").split("\0")
    return {n for n in names if n}


def _entries(doc) -> list | None:
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for k in LIST_KEYS:
            if isinstance(doc.get(k), list):
                return doc[k]
    return None


def _manifests(data: Path, b: str, names: set[str]) -> tuple[dict[str, list], list[str]]:
    read: dict[str, list] = {}
    not_read: list[str] = []
    for p in sorted(names):
        base = p.rsplit("/", 1)[-1].lower()
        if "manifest" not in base or not base.endswith(".json"):
            continue
        raw = _blob(data, b, p)
        try:
            ents = _entries(json.loads(raw))
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


def _spellings(manifest: str, raw: str) -> list[tuple[str, str]]:
    """The two readings of an entry's path: (path from the repository's root, how it was read)."""
    while raw.startswith("./"):
        raw = raw[2:]
    folder = manifest.rsplit("/", 1)[0] if "/" in manifest else ""
    out = [(raw, AS_WRITTEN)]
    joined = f"{folder}/{raw}" if folder else raw
    if joined != raw:
        out.append((joined, RELATIVE))
    return out


def _is_path_entry(e) -> bool:
    return isinstance(e, dict) and any(k in e for k in PATH_KEYS)


def _manifests_not_path_read(read: dict[str, list]) -> list[str]:
    lines = []
    for m, ents in read.items():
        bad = [e for e in ents if not _is_path_entry(e)]
        if not bad:
            continue
        keys = sorted({k for e in bad if isinstance(e, dict) for k in e})
        not_objects = sum(1 for e in bad if not isinstance(e, dict))
        line = (f"manifest {m}: {len(bad)} of {len(ents)} entries carry neither \"path\" nor "
                f"\"markets_data_path\"; the keys those entries carry: {', '.join(keys) if keys else 'none'}")
        if not_objects:
            line += f"; {not_objects} of them are not objects"
        lines.append(line + "; those keys are not read as paths")
    return lines


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
        names = _tree(data, b)
        read, not_read = _manifests(data, b, names)
    except Unreadable as e:
        print(f"cannot read the range {a.rng} in {data}: {e}")
        return 2
    for p in not_read:
        print(f"manifest {p}: its shape was not read")
    unread = _manifests_not_path_read(read)
    for line in unread:
        print(line)
    with_entry = no_entry = under_folder = gone = 0
    for p in added:
        try:
            exists = p in names
            blob = _blob(data, b, p) if exists else None
        except Unreadable as e:
            print(f"cannot read {p} at {b} in {data}: {e}")
            return 2
        if blob is None:
            gone += 1
        held, folders, passed = [], [], []
        for m, ents in read.items():
            for e in ents:
                if not isinstance(e, dict):
                    continue
                file_hows, folder_hows = [], []
                for k in PATH_KEYS:
                    v = e.get(k)
                    if not isinstance(v, str):
                        continue
                    spell = _spellings(m, v)
                    if not v.endswith("/") and len(spell) == 2 and spell[1][0] in names:
                        # both readings name a file: the entry means the one in the manifest's folder
                        if spell[0][0] == p:
                            passed.append(f"{m}: a manifest names the same path in another folder, its entry "
                                          f"\"{v}\" is the file {spell[1][0]}; not counted as its entry")
                        spell = spell[1:]
                    for full, how in spell:
                        if v.endswith("/"):
                            if full != "" and p.startswith(full) and how not in folder_hows:
                                folder_hows.append(how)
                        elif full == p and how not in file_hows:
                            file_hows.append(how)
                if file_hows:
                    what = _compare(e, blob) if blob is not None else "file gone at B, nothing compared"
                    held.append(f"{m}: {what} ({' and '.join(file_hows)})")
                elif folder_hows:
                    folders.append(f"{m}: this manifest names its folder in an entry "
                                   f"({' and '.join(folder_hows)}), not this file")
        where = "gone at B | bytes at B none" if blob is None else f"exists at B | bytes at B {len(blob)}"
        if held:
            with_entry += 1
            tail = " | ".join(held)
        elif folders:
            under_folder += 1
            tail = " | ".join(folders)
        else:
            no_entry += 1
            tail = "no manifest holds an entry for it"
        if passed:
            tail += " | " + " | ".join(passed)
        print(f"{p} | {where} | {tail}")
    print(f"COUNTS added={len(added)} with_entry={with_entry} no_entry={no_entry} "
          f"under_a_folder_entry={under_folder} gone_at_B={gone} "
          f"manifests_read={len(read)} manifests_shape_not_read={len(not_read)} "
          f"manifests_with_entries_not_read={len(unread)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
