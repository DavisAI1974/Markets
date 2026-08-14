#!/usr/bin/env python3
"""S126 metadata-only repair for the already-verified S114 GEFS forcing store.

The S114 store was proven intact on the Markets S3 plane and carries separate
`wind_cf_proxy` and `solar_irradiance_proxy` values. The S126 end-to-end verifier requires the
explicit machine-readable contract metadata `served_separately is True`.

Legacy S114 records use two representations of that same contract:
- the key may be absent even though the two proxy fields are physically separate; or
- `served_separately` may contain the canonical D37 prose explaining that wind and solar are NEVER
  summed because a single renewables term would combine opposite annual cycles.

This tool does NOT rebuild, recompute, rescale, sum, or otherwise alter either forcing. It may only
normalize `served_separately` to boolean true when BOTH separate proxy keys already exist and are
non-null AND the existing metadata is either absent, already True, or exactly the canonical D37
legacy marker (whitespace-insensitive). False, None, or any other string/value fails closed.

With --execute it writes the local JSON atomically, pushes through the sanctioned platform_sync S3
door, and performs byte-identical SHA256 + manifest read-back using the existing D47 verifier.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STORE_DIR = REPO / "data" / "gefs_forcing"
STORE_PATH = STORE_DIR / "gefs_forcing.json"
PREFIX = "nymex/gefs_forcing/"

# This is not a fuzzy semantic parser. It is the exact historical S114/D37 representation observed
# in the authoritative store, compared after whitespace normalization only so terminal/file wrapping
# cannot change its meaning. No other prose string is accepted as an affirmative contract value.
LEGACY_D37_SEPARATION = (
    "wind and solar are NEVER summed - they are seasonally ANTI-correlated (wind peaks "
    "spring/autumn, solar at the solstice), so one 'renewables' term is a composite of two "
    "opposite annual cycles (D37)."
)


class SeparationMetadataError(RuntimeError):
    pass


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _is_legacy_d37_separation(value: object) -> bool:
    return isinstance(value, str) and _normalized_text(value) == _normalized_text(LEGACY_D37_SEPARATION)


def normalize_store(store: dict, required_days: list[str] | tuple[str, ...] = ()) -> tuple[dict, list[str]]:
    if not isinstance(store, dict):
        raise SeparationMetadataError("GEFS forcing store root is not a dict")
    out = json.loads(json.dumps(store))
    changed: list[str] = []
    days = list(required_days) if required_days else sorted(out)
    for day in days:
        rec = out.get(day)
        if not isinstance(rec, dict):
            raise SeparationMetadataError(f"{day}: forcing record missing")
        for key in ("wind_cf_proxy", "solar_irradiance_proxy"):
            if key not in rec or rec.get(key) is None:
                raise SeparationMetadataError(
                    f"{day}: cannot assert separation because {key} is missing/null"
                )

        if "served_separately" in rec:
            value = rec.get("served_separately")
            if value is True:
                continue
            if _is_legacy_d37_separation(value):
                rec["served_separately"] = True
                changed.append(day)
                continue
            raise SeparationMetadataError(
                f"{day}: explicit served_separately={value!r}; refusing metadata repair"
            )

        rec["served_separately"] = True
        changed.append(day)
    return out, changed


def _atomic_write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def run(gid: str, execute: bool) -> dict:
    if not execute:
        raise SeparationMetadataError("refusing S3 mutation without --execute")
    os.chdir(REPO)
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))

    import group_config as gc
    if gid not in gc.GROUPS:
        raise SeparationMetadataError(f"unknown group {gid}")
    days = list(gc.GROUPS[gid]["days"])

    # Restore the authoritative store first. This is pull-only; no staging is requested here.
    subprocess.run([sys.executable, str(HERE / "restore_substrate.py")], check=True)
    if not STORE_PATH.exists():
        raise SeparationMetadataError(f"authoritative store did not restore: {STORE_PATH}")

    store = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    normalized, changed = normalize_store(store, days)
    _atomic_write(STORE_PATH, normalized)

    # Re-read local bytes before pushing; the two numeric proxy fields must be identical to source.
    reread = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    for day in days:
        before, after = store[day], reread[day]
        if before.get("wind_cf_proxy") != after.get("wind_cf_proxy"):
            raise SeparationMetadataError(f"{day}: wind_cf_proxy changed during metadata repair")
        if before.get("solar_irradiance_proxy") != after.get("solar_irradiance_proxy"):
            raise SeparationMetadataError(f"{day}: solar_irradiance_proxy changed during metadata repair")
        if after.get("served_separately") is not True:
            raise SeparationMetadataError(f"{day}: served_separately still not true")

    subprocess.run(
        [
            sys.executable,
            str(HERE / "platform_sync.py"),
            "push",
            "--prefix",
            PREFIX,
            "--src",
            str(STORE_DIR),
            "--execute",
            "--note",
            "S126 metadata-only repair: S114 wind/solar already separate; no proxy values changed",
        ],
        check=True,
    )

    from frankie_m13_recover_s126 import verify_s3_readback
    import creds
    s3 = creds.aws_client("s3", "us-east-2")
    readback = verify_s3_readback(PREFIX, STORE_DIR, s3)
    result = {"gid": gid, "days": len(days), "metadata_added": changed, "readback": readback}
    print(
        f"PASS: S114 {gid} separation metadata repaired/verified; "
        f"wind and solar proxy values unchanged; metadata_added={len(changed)}",
        flush=True,
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="S126 S114 legacy separation-metadata repair")
    ap.add_argument("gid", nargs="?", default="g24")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    try:
        run(args.gid, args.execute)
    except (SeparationMetadataError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: S114 separation metadata repair stopped: {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
