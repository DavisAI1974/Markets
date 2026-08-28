"""Hash-bound native raw-MBO source manifest and exact progress denominator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "FRANKIE_RAW_MBO_SOURCE_MANIFEST_V1"
SOURCE_KIND = "NATIVE_DBN_MBO"
CAUSAL_CLOCK = "ts_recv_ns"
EXPECTED_ROSTER = (
    ("20211001", "WARMUP_DEVELOPMENT"),
    ("20211003", "WARMUP_DEVELOPMENT"),
    ("20211004", "HELD_OUT_BLIND"),
    ("20211005", "HELD_OUT_BLIND"),
)
EXPECTED_NAMES = tuple(f"glbx-mdp3-{date}.mbo.dbn.zst" for date, _ in EXPECTED_ROSTER)
_MANIFEST_KEYS = frozenset({
    "schema",
    "source_kind",
    "causal_clock",
    "canonical_source_rewritten",
    "sources",
    "warmup_mbo_records",
    "held_out_mbo_records",
    "total_mbo_records",
    "manifest_hash",
})
_SOURCE_KEYS = frozenset({"name", "date", "role", "bytes", "sha256", "mbo_records"})


class ManifestError(ValueError):
    """Raw-MBO source manifest contract violation."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_payload(manifest: Mapping[str, Any]) -> bytes:
    body = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    if not isinstance(manifest, Mapping):
        raise ManifestError("manifest must be an object")
    return hashlib.sha256(_canonical_payload(manifest)).hexdigest()


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ManifestError(f"{label} must be a positive integer")
    return value


def count_native_mbo_records(path: Path) -> int:
    """Count native MBO records directly from a Databento DBN object."""
    try:
        import databento as db
    except ImportError as exc:
        raise ManifestError("databento package is required to count native DBN MBO records") from exc
    count = 0
    store = db.DBNStore.from_file(str(path))
    for record in store:
        if type(record).__name__ in {"MboMsg", "MBOMsg"}:
            count += 1
    return _positive_int(count, f"MBO record count for {path.name}")


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if not isinstance(manifest, Mapping):
        raise ManifestError("manifest must be an object")
    actual = set(manifest)
    if actual != _MANIFEST_KEYS:
        raise ManifestError(
            f"unknown or missing manifest fields: unknown={sorted(actual - _MANIFEST_KEYS)}, "
            f"missing={sorted(_MANIFEST_KEYS - actual)}"
        )
    if manifest["manifest_hash"] != manifest_hash(manifest):
        raise ManifestError("manifest hash mismatch")
    if manifest["schema"] != SCHEMA:
        raise ManifestError("unsupported manifest schema")
    if manifest["source_kind"] != SOURCE_KIND:
        raise ManifestError("source kind is not native DBN MBO")
    if manifest["causal_clock"] != CAUSAL_CLOCK:
        raise ManifestError("causal clock must be ts_recv_ns")
    if manifest["canonical_source_rewritten"] is not False:
        raise ManifestError("canonical native source must not be rewritten")
    if not isinstance(manifest["sources"], list) or len(manifest["sources"]) != len(EXPECTED_ROSTER):
        raise ManifestError("source roster must contain exactly four raw DBN objects")

    warmup = 0
    held_out = 0
    names: list[str] = []
    for index, raw in enumerate(manifest["sources"]):
        if not isinstance(raw, Mapping) or set(raw) != _SOURCE_KEYS:
            raise ManifestError("unknown or missing source fields")
        date, role = EXPECTED_ROSTER[index]
        expected_name = EXPECTED_NAMES[index]
        if raw["name"] != expected_name or raw["date"] != date or raw["role"] != role:
            raise ManifestError("native raw-MBO roster/date/role drift")
        names.append(raw["name"])
        _positive_int(raw["bytes"], f"bytes for {expected_name}")
        records = _positive_int(raw["mbo_records"], f"mbo_records for {expected_name}")
        digest = raw["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ManifestError(f"sha256 for {expected_name} is invalid")
        if role == "HELD_OUT_BLIND":
            held_out += records
        else:
            warmup += records
    if len(set(names)) != len(names):
        raise ManifestError("duplicate native raw-MBO source")
    total = warmup + held_out
    if manifest["warmup_mbo_records"] != warmup:
        raise ManifestError("warmup MBO record count does not reconcile")
    if manifest["held_out_mbo_records"] != held_out:
        raise ManifestError("held-out MBO record count does not reconcile")
    if manifest["total_mbo_records"] != total:
        raise ManifestError("total MBO record count does not reconcile")


def build_source_manifest(
    paths: Sequence[Path | str],
    *,
    count_records: Callable[[Path], int] = count_native_mbo_records,
) -> dict[str, Any]:
    materialized = [Path(path) for path in paths]
    if len(materialized) != len(EXPECTED_NAMES):
        raise ManifestError("exactly four native raw-MBO files are required")
    by_name: dict[str, Path] = {}
    for path in materialized:
        if path.name not in EXPECTED_NAMES or not path.name.endswith(".mbo.dbn.zst"):
            raise ManifestError(f"forbidden non-native or unexpected benchmark source: {path.name}")
        if path.name in by_name:
            raise ManifestError(f"duplicate native raw-MBO source: {path.name}")
        if not path.is_file():
            raise ManifestError(f"native raw-MBO source is missing: {path}")
        by_name[path.name] = path
    if set(by_name) != set(EXPECTED_NAMES):
        raise ManifestError("native raw-MBO source roster is incomplete or drifted")

    sources: list[dict[str, Any]] = []
    for date, role in EXPECTED_ROSTER:
        name = f"glbx-mdp3-{date}.mbo.dbn.zst"
        path = by_name[name]
        records = _positive_int(count_records(path), f"mbo_records for {name}")
        sources.append({
            "name": name,
            "date": date,
            "role": role,
            "bytes": int(path.stat().st_size),
            "sha256": _sha256_file(path),
            "mbo_records": records,
        })

    warmup = sum(row["mbo_records"] for row in sources if row["role"] == "WARMUP_DEVELOPMENT")
    held_out = sum(row["mbo_records"] for row in sources if row["role"] == "HELD_OUT_BLIND")
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "source_kind": SOURCE_KIND,
        "causal_clock": CAUSAL_CLOCK,
        "canonical_source_rewritten": False,
        "sources": sources,
        "warmup_mbo_records": warmup,
        "held_out_mbo_records": held_out,
        "total_mbo_records": warmup + held_out,
        "manifest_hash": "",
    }
    manifest["manifest_hash"] = manifest_hash(manifest)
    _validate_manifest(manifest)
    return manifest


def progress_snapshot(
    manifest: Mapping[str, Any],
    *,
    completed_mbo_records: int,
    phase: str,
) -> dict[str, Any]:
    _validate_manifest(manifest)
    if isinstance(completed_mbo_records, bool) or not isinstance(completed_mbo_records, int):
        raise ManifestError("completed_mbo_records must be an integer")
    total = int(manifest["total_mbo_records"])
    if completed_mbo_records < 0 or completed_mbo_records > total:
        raise ManifestError("completed_mbo_records must be within the declared raw-MBO roster")
    if not isinstance(phase, str) or not phase:
        raise ManifestError("phase must be a non-empty string")
    return {
        "schema": "FRANKIE_RAW_MBO_PROGRESS_V1",
        "source_manifest_hash": manifest["manifest_hash"],
        "phase": phase,
        "completed_mbo_records": completed_mbo_records,
        "total_mbo_records": total,
        "percent_complete": round(completed_mbo_records * 100.0 / total, 9),
        "denominator": "HASH_BOUND_NATIVE_MBO_RECORD_COUNT",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a truth-free native raw-MBO benchmark manifest.")
    parser.add_argument("--output", required=True)
    parser.add_argument("dbn", nargs=4)
    args = parser.parse_args()
    manifest = build_source_manifest([Path(value) for value in args.dbn])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
