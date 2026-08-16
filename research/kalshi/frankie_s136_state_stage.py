#!/usr/bin/env python3
"""Targeted S136 state-plane staging for date-driven Frankie runs.

This is deliberately smaller than restore_substrate.py.  It restores the canonical compact/as-of
state stores that current Frankie already consumes, but never restores the full continuous n0 tape.
For volatility state it lists the canonical n0 archive and pulls only a bounded set of sessions
strictly before the requested window.  The S135 session stager separately pulls the anchor/window
n0/n1/L1 files it legally needs.

Nothing is synthesized.  An expected canonical prefix/object that is absent from S3 is a staging
failure, not evidence that the historical family did not exist.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import creds
import restore_substrate

BUCKET = restore_substrate.BUCKET
REGION = restore_substrate.REGION
FULL_N0_PREFIX = "nymex/nymex_cont_n0/"
N0_LOCAL = ROOT / "data" / "nymex_cont_n0"
N0_LOOKBACK = 80
N0_REQUIRED_PRIOR = 60
_N0_RE = re.compile(r"NG_(20\d{6})\.jsonl\.gz$")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry(*, kind: str, key: str, dest: Path, remote: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "bucket": BUCKET,
        "key": key,
        "local_dest": str(dest.relative_to(ROOT)),
        "remote_size": int(remote.get("Size") or 0),
        "remote_etag": str(remote.get("ETag") or "").strip('"'),
        "remote_last_modified": (
            remote.get("LastModified").isoformat()
            if getattr(remote.get("LastModified"), "isoformat", None)
            else str(remote.get("LastModified") or "")
        ),
        "status": status,
        "local_size": dest.stat().st_size,
        "local_sha256": _sha256(dest),
    }


def _download(s3, key: str, dest: Path, remote: dict[str, Any], *, kind: str) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    remote_size = int(remote.get("Size") or 0)
    if dest.exists() and dest.stat().st_size == remote_size and remote_size > 0:
        status = "present_remote_size_match"
    else:
        s3.download_file(BUCKET, key, str(dest))
        status = "downloaded"
    if not dest.is_file() or dest.stat().st_size != remote_size or remote_size <= 0:
        raise SystemExit(
            f"S136 state staging integrity failure for s3://{BUCKET}/{key}: "
            f"remote_size={remote_size}, local={dest if dest.exists() else 'MISSING'}"
        )
    return _entry(kind=kind, key=key, dest=dest, remote=remote, status=status)


def _list_prefix(s3, prefix: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        rows.extend(
            obj for obj in page.get("Contents", [])
            if obj.get("Key") and not str(obj["Key"]).endswith("/")
        )
    return rows


def _head(s3, key: str) -> dict[str, Any]:
    try:
        return s3.head_object(Bucket=BUCKET, Key=key)
    except Exception as exc:
        raise SystemExit(
            f"S136 expected canonical state object missing/unreadable: "
            f"s3://{BUCKET}/{key} ({type(exc).__name__}: {exc})"
        ) from exc


def stage_compact_state(start_day: str, manifest_path: Path) -> dict[str, Any]:
    """Restore canonical compact state plus bounded strictly-prior n0 history."""
    start = str(start_day).replace("-", "")
    if len(start) != 8 or not start.isdigit():
        raise SystemExit(f"S136 invalid staging start day {start_day!r}")

    s3 = creds.aws_client("s3", REGION)
    try:
        s3.list_objects_v2(Bucket=BUCKET, MaxKeys=1)
    except Exception as exc:
        raise SystemExit(
            f"S136 S3 unreachable for canonical state staging "
            f"({type(exc).__name__}: {exc})"
        ) from exc

    entries: list[dict[str, Any]] = []
    prefixes = [
        (prefix, dest)
        for prefix, dest in restore_substrate.PREFIXES
        if prefix != FULL_N0_PREFIX
    ]
    for prefix, dest_rel in prefixes:
        objects = _list_prefix(s3, prefix)
        if not objects:
            raise SystemExit(
                f"S136 expected canonical state prefix is empty/missing: s3://{BUCKET}/{prefix}"
            )
        base = ROOT / dest_rel
        for obj in objects:
            key = str(obj["Key"])
            rel = key[len(prefix):]
            dest = base / Path(rel)
            entries.append(_download(s3, key, dest, obj, kind="canonical_state"))

    for key, dest_rel in restore_substrate.SINGLES:
        head = _head(s3, key)
        remote = {
            "Size": head.get("ContentLength"),
            "ETag": head.get("ETag"),
            "LastModified": head.get("LastModified"),
        }
        entries.append(
            _download(s3, key, ROOT / dest_rel, remote, kind="canonical_state_single")
        )

    n0_all: list[tuple[str, dict[str, Any]]] = []
    for obj in _list_prefix(s3, FULL_N0_PREFIX):
        m = _N0_RE.search(str(obj["Key"]))
        if not m:
            continue
        day = m.group(1)
        if day < start:
            n0_all.append((day, obj))
    n0_all.sort(key=lambda x: x[0])
    selected = n0_all[-N0_LOOKBACK:]
    if len(selected) < N0_REQUIRED_PRIOR:
        raise SystemExit(
            f"S136 bounded n0 history has only {len(selected)} strictly-prior sessions before {start}; "
            f"{N0_REQUIRED_PRIOR} required for Frankie's 60-session vol conditioner"
        )
    N0_LOCAL.mkdir(parents=True, exist_ok=True)
    for day, obj in selected:
        key = str(obj["Key"])
        dest = N0_LOCAL / f"NG_{day}.jsonl.gz"
        entries.append(_download(s3, key, dest, obj, kind="bounded_prior_n0"))

    manifest = {
        "version": "S136_TARGETED_STATE_STAGE_V1",
        "bucket": BUCKET,
        "region": REGION,
        "start_day": start,
        "hydration": "REJECTED_NOT_USED",
        "synthetic_history": False,
        "full_n0_restore": False,
        "compact_prefixes": [p for p, _ in prefixes],
        "single_objects": [k for k, _ in restore_substrate.SINGLES],
        "bounded_prior_n0": {
            "prefix": FULL_N0_PREFIX,
            "requested_max_sessions": N0_LOOKBACK,
            "required_prior_sessions": N0_REQUIRED_PRIOR,
            "selected_count": len(selected),
            "first_selected_day": selected[0][0],
            "last_selected_day": selected[-1][0],
            "strictly_before_start": True,
        },
        "objects": entries,
        "object_count": len(entries),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def rebuild_vol_regime() -> dict[str, Any]:
    """Rebuild derived vol state after bounded history + session-specific n0 have landed."""
    cmd = [sys.executable, str(HERE / "vol_regime.py"), "--build"]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(
            "S136 vol_regime rebuild failed after targeted n0 staging:\n"
            + (proc.stdout or "")
            + (proc.stderr or "")
        )
    store = ROOT / "data" / "vol_regime" / "vol_regime.json"
    if not store.is_file() or store.stat().st_size <= 0:
        raise SystemExit(f"S136 vol_regime rebuild produced no store at {store}")
    return {
        "status": "rebuilt",
        "path": str(store.relative_to(ROOT)),
        "size": store.stat().st_size,
        "sha256": _sha256(store),
    }
