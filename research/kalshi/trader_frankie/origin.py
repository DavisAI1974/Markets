"""Frankie 1 freeze verification and descendant write-boundary enforcement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
MANIFEST_PATH = HERE / "freeze_manifest.json"


class FreezeViolation(RuntimeError):
    pass


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("protected_files"), list):
        raise FreezeViolation("invalid Frankie 1 freeze manifest")
    return value


def verify_freeze() -> dict[str, Any]:
    manifest = load_manifest()
    changed: list[dict[str, str]] = []
    missing: list[str] = []
    for entry in manifest["protected_files"]:
        path = ROOT / entry["path"]
        if not path.is_file():
            missing.append(entry["path"])
            continue
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if observed != entry["sha256"]:
            changed.append({"path": entry["path"], "expected": entry["sha256"], "observed": observed})
    if missing or changed:
        raise FreezeViolation(f"Frankie 1 freeze violated: missing={missing}, changed={changed}")
    return {
        "verified": True,
        "starting_commit": manifest["starting_commit"],
        "protected_file_count": len(manifest["protected_files"]),
        "spawn": manifest["spawn"],
    }


def assert_descendant_write_path(path: str | Path) -> Path:
    """Allow state writes only in a venue evidence/outcomes/proposals store."""
    resolved = Path(path).resolve()
    allowed_roots = tuple(
        (HERE / venue / kind).resolve()
        for venue in ("kalshi", "tasty")
        for kind in ("evidence", "outcomes", "proposals")
    )
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise FreezeViolation(f"Trader Frankie state path is outside isolated stores: {resolved}")
    protected = {(ROOT / item["path"]).resolve() for item in load_manifest()["protected_files"]}
    if resolved in protected:
        raise FreezeViolation(f"write targets frozen Frankie 1 file: {resolved}")
    return resolved
