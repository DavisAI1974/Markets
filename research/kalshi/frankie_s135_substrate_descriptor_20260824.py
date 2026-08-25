#!/usr/bin/env python3
"""Seal and validate the complete restore_substrate S135 data-plane staging receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from research.kalshi.frankie_causal_operational_context_20260824 import RegistryCoverageOracle
from research.kalshi.restore_substrate import PREFIXES, SINGLES


SCHEMA = "FRANKIE_S135_SUBSTRATE_DESCRIPTOR_V1_20260824"


class SubstrateDescriptorError(ValueError):
    pass


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_sha(root: Path, files: Sequence[Path]) -> str:
    rows = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": _file_sha(path),
        }
        for path in sorted(files)
    ]
    return _hash(rows)


def build_substrate_descriptor(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    entries: list[dict[str, Any]] = []
    missing: list[str] = []
    for prefix, relative in PREFIXES:
        target = root / relative
        files = tuple(path for path in target.rglob("*") if path.is_file()) if target.is_dir() else ()
        if not files:
            missing.append(relative)
        entries.append(
            {"source": prefix, "destination": relative, "file_count": len(files),
             "byte_count": sum(path.stat().st_size for path in files),
             "content_tree_sha256": _tree_sha(target, files)}
        )
    for source, relative in SINGLES:
        target = root / relative
        if not target.is_file() or target.stat().st_size <= 0:
            missing.append(relative)
        entries.append(
            {"source": source, "destination": relative,
             "file_count": int(target.is_file()),
             "byte_count": target.stat().st_size if target.is_file() else 0,
             "content_tree_sha256": _file_sha(target) if target.is_file() else _hash([])}
        )
    oracle = RegistryCoverageOracle.from_repo(root)
    core = {
        "schema": SCHEMA,
        "status": "ACCEPTED" if not missing else "INCOMPLETE",
        "registry_receipt_hash": oracle.receipt_hash,
        "registry_path_count": oracle.path_count,
        "registry_block_count": oracle.block_count,
        "entries": entries,
        "missing_destinations": sorted(missing),
    }
    return {**core, "descriptor_hash": _hash(core)}


def validate_substrate_descriptor(
    descriptor: Mapping[str, Any], *, oracle: RegistryCoverageOracle
) -> dict[str, Any]:
    if not isinstance(descriptor, Mapping) or descriptor.get("schema") != SCHEMA:
        raise SubstrateDescriptorError("S135 substrate descriptor schema mismatch")
    core = dict(descriptor)
    claimed_hash = str(core.pop("descriptor_hash", ""))
    if claimed_hash != _hash(core):
        raise SubstrateDescriptorError("S135 substrate descriptor hash mismatch")
    if descriptor.get("status") != "ACCEPTED" or descriptor.get("missing_destinations") != []:
        raise SubstrateDescriptorError("S135 substrate descriptor is incomplete")
    if (
        descriptor.get("registry_receipt_hash") != oracle.receipt_hash
        or descriptor.get("registry_path_count") != oracle.path_count
        or descriptor.get("registry_block_count") != oracle.block_count
    ):
        raise SubstrateDescriptorError("S135 substrate descriptor registry identity drift")
    return dict(descriptor)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    descriptor = build_substrate_descriptor(args.repo_root)
    if descriptor["status"] != "ACCEPTED":
        raise SubstrateDescriptorError(
            f"S135 substrate staging incomplete: {descriptor['missing_destinations']}"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    fd = os.open(args.out, flags, 0o600)
    try:
        os.write(fd, (json.dumps(descriptor, sort_keys=True, indent=2) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
