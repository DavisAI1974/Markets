"""Inventory/hash the old Sunday configuration dependencies for GitHub restoration.

Run this on the machine that still has the authoritative files. It never copies, edits or
opens SQLite logically; it hashes bytes only. The active source-recovery tree must be
passed via --off-limits and is refused before traversal. New run_directory and repository
paths are metadata only, not restoration payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

DIRECTORY_KEYS = {"source_directory", "schedule_directory", "tokenizer_directory", "receiver_root"}
METADATA_ONLY_KEYS = {"run_directory", "repository"}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _touches_off_limits(path, off_limits):
    resolved = Path(path).resolve()
    return any(_is_within(resolved, root) or _is_within(root, resolved) for root in off_limits)


def _configured_paths(value, location="configuration"):
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{location}.{key}"
            if isinstance(item, str) and (key == "path" or key.endswith("_path")
                                          or key in DIRECTORY_KEYS or key in METADATA_ONLY_KEYS):
                yield child, key, item, value.get("sha256") if key == "path" else None
            yield from _configured_paths(item, child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _configured_paths(item, f"{location}[{index}]")


def _directory_receipt(path):
    path = Path(path).resolve()
    rows = []
    for member in sorted(path.rglob("*")):
        if member.is_symlink():
            raise ValueError(f"symlink not admitted in restoration directory: {member}")
        if member.is_file():
            digest = sha256_file(member)
            rows.append(dict(path=member.relative_to(path).as_posix(), bytes=member.stat().st_size,
                             sha256=digest))
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return dict(kind="directory", path=str(path), files=rows,
                manifest_sha256=hashlib.sha256(canonical).hexdigest())


def build_manifest(configuration_path, off_limits):
    configuration_path = Path(configuration_path).resolve()
    raw = configuration_path.read_bytes()
    configuration = json.loads(raw)
    roots = tuple(Path(value).resolve() for value in off_limits)
    if not roots:
        raise ValueError("at least one explicit --off-limits path is required for this recovery inventory")
    artifacts, metadata, seen = [], [], {}
    for location, key, text, declared_sha in _configured_paths(configuration):
        path = Path(text)
        if not path.is_absolute():
            path = (configuration_path.parent / path).resolve()
        else:
            path = path.resolve()
        if key in METADATA_ONLY_KEYS:
            metadata.append(dict(location=location, key=key, original=text, resolved=str(path)))
            continue
        if _touches_off_limits(path, roots):
            raise ValueError(f"configured restoration path touches off-limits recovery state: {location}")
        identity = str(path)
        entry = seen.get(identity)
        if entry is None:
            if path.is_symlink() or not path.exists():
                raise ValueError(f"configured restoration path is missing or symlinked: {location}")
            if path.is_file():
                digest = sha256_file(path)
                entry = dict(kind="file", path=str(path), bytes=path.stat().st_size, sha256=digest)
            elif path.is_dir():
                entry = _directory_receipt(path)
            else:
                raise ValueError(f"unsupported configured restoration path: {location}")
            entry["locations"] = []
            seen[identity] = entry
            artifacts.append(entry)
        entry["locations"].append(location)
        if declared_sha is not None and entry.get("sha256") != declared_sha:
            raise ValueError(f"configured SHA-256 differs from current authoritative bytes: {location}")
    return dict(schema="FRANKIE_SUNDAY_GITHUB_RESTORE_MANIFEST_V1",
        configuration_path=str(configuration_path),
        configuration_sha256=hashlib.sha256(raw).hexdigest(),
        off_limits=[str(path) for path in roots], metadata_only=metadata, artifacts=artifacts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--off-limits", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.configuration, args.off_limits)
    raw = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    Path(args.output).write_text(raw, encoding="utf-8")
    print(raw, end="", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
