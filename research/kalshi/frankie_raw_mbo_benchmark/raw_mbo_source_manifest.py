"""Hash-bound native raw-MBO source manifest and exact progress denominator.

All four sources carry one role. The earlier WARMUP_DEVELOPMENT / HELD_OUT_BLIND split
described a design in which October 1 and 3 were context and only October 4 and 5 produced
findings; every day is now scored and every day produces findings, so a role that divides
them describes nothing and would license pooling two days that should never pool.

What the split actually carried - that some days are seen with less accumulated knowledge
than others - is a property of stream position, not of role, so `roster_position` records it
explicitly. In ts_recv_ns order October 1 is first and October 5 last, which is what makes
an in-stream learning gradient measurable within a single arm.

There are two hashes, and the distinction matters. `source_identity_hash` covers only the
immutable identity of the roster - names, dates, roles, positions, URIs, byte lengths,
object digests and record counts - so it is constant across runs and can be pinned in code
and in a workflow. `manifest_hash` additionally covers the staging fields section 5.1
requires (download receipt, local staged path, staged-file digest), which are produced at
stage time and necessarily differ per run. Pinning the whole manifest would have made those
fields unaddable; pinning identity alone keeps both properties.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA = "FRANKIE_RAW_MBO_SOURCE_MANIFEST_V1"
SOURCE_KIND = "NATIVE_DBN_MBO"
CAUSAL_CLOCK = "ts_recv_ns"
SCORED_FINDINGS_DAY = "SCORED_FINDINGS_DAY"
EXPECTED_ROSTER = (
    ("20211001", SCORED_FINDINGS_DAY),
    ("20211003", SCORED_FINDINGS_DAY),
    ("20211004", SCORED_FINDINGS_DAY),
    ("20211005", SCORED_FINDINGS_DAY),
)
EXPECTED_NAMES = tuple(f"glbx-mdp3-{date}.mbo.dbn.zst" for date, _ in EXPECTED_ROSTER)
_MANIFEST_KEYS = frozenset({
    "schema",
    "source_kind",
    "causal_clock",
    "canonical_source_rewritten",
    "sources",
    "total_mbo_records",
    "source_identity_hash",
    "manifest_hash",
})
# Identity fields are immutable across runs and feed source_identity_hash.
_IDENTITY_SOURCE_KEYS = ("name", "date", "role", "roster_position", "uri", "bytes", "sha256", "mbo_records")
# Staging fields are produced at stage time and feed manifest_hash only.
_STAGING_SOURCE_KEYS = ("download_receipt", "staged_path", "staged_sha256")
_SOURCE_KEYS = frozenset(_IDENTITY_SOURCE_KEYS + _STAGING_SOURCE_KEYS)


class ManifestError(ValueError):
    """Raw-MBO source manifest contract violation."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(body: Mapping[str, Any]) -> bytes:
    return json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _canonical_payload(manifest: Mapping[str, Any]) -> bytes:
    body = {key: value for key, value in manifest.items() if key != "manifest_hash"}
    return _canonical(body)


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    """Covers identity and staging. Run-specific; do not pin."""
    if not isinstance(manifest, Mapping):
        raise ManifestError("manifest must be an object")
    return hashlib.sha256(_canonical_payload(manifest)).hexdigest()


def source_identity_hash(manifest: Mapping[str, Any]) -> str:
    """Covers roster identity only. Constant across runs; safe to pin."""
    if not isinstance(manifest, Mapping):
        raise ManifestError("manifest must be an object")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise ManifestError("manifest sources must be a list")
    body = {
        "schema": manifest.get("schema"),
        "source_kind": manifest.get("source_kind"),
        "causal_clock": manifest.get("causal_clock"),
        "canonical_source_rewritten": manifest.get("canonical_source_rewritten"),
        "total_mbo_records": manifest.get("total_mbo_records"),
        "sources": [
            {key: row.get(key) for key in _IDENTITY_SOURCE_KEYS} for row in sources
        ],
    }
    return hashlib.sha256(_canonical(body)).hexdigest()


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
    if manifest["source_identity_hash"] != source_identity_hash(manifest):
        raise ManifestError("source identity hash mismatch")
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

    total = 0
    names: list[str] = []
    for index, raw in enumerate(manifest["sources"]):
        if not isinstance(raw, Mapping) or set(raw) != _SOURCE_KEYS:
            raise ManifestError("unknown or missing source fields")
        date, role = EXPECTED_ROSTER[index]
        expected_name = EXPECTED_NAMES[index]
        if raw["name"] != expected_name or raw["date"] != date or raw["role"] != role:
            raise ManifestError("native raw-MBO roster/date/role drift")
        if raw["roster_position"] != index:
            raise ManifestError(
                f"roster position drift for {expected_name}: stream order is the causal order"
            )
        if not isinstance(raw["uri"], str) or not raw["uri"].startswith("s3://"):
            raise ManifestError(f"external source URI for {expected_name} must be an s3:// URI")
        names.append(raw["name"])
        _positive_int(raw["bytes"], f"bytes for {expected_name}")
        total += _positive_int(raw["mbo_records"], f"mbo_records for {expected_name}")
        for field in ("sha256", "staged_sha256"):
            digest = raw[field]
            if digest is None and field == "staged_sha256":
                continue  # not yet staged; manifest_hash still binds its absence
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest.lower())
            ):
                raise ManifestError(f"{field} for {expected_name} is invalid")
    if len(set(names)) != len(names):
        raise ManifestError("duplicate native raw-MBO source")
    if manifest["total_mbo_records"] != total:
        raise ManifestError("total MBO record count does not reconcile")


DEFAULT_SOURCE_URI_PREFIX = (
    "s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/20211001_20211101"
)


def build_source_manifest(
    paths: Sequence[Path | str],
    *,
    count_records: Callable[[Path], int] = count_native_mbo_records,
    source_uri_prefix: str = DEFAULT_SOURCE_URI_PREFIX,
    staging: Mapping[str, Mapping[str, Any]] | None = None,
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
    for position, (date, role) in enumerate(EXPECTED_ROSTER):
        name = f"glbx-mdp3-{date}.mbo.dbn.zst"
        path = by_name[name]
        staged = staging.get(name, {}) if staging else {}
        sources.append({
            "name": name,
            "date": date,
            "role": role,
            "roster_position": position,
            "uri": f"{source_uri_prefix.rstrip('/')}/{name}",
            "bytes": int(path.stat().st_size),
            "sha256": _sha256_file(path),
            "mbo_records": _positive_int(count_records(path), f"mbo_records for {name}"),
            "download_receipt": staged.get("download_receipt"),
            "staged_path": staged.get("staged_path", str(path)),
            "staged_sha256": staged.get("staged_sha256"),
        })

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "source_kind": SOURCE_KIND,
        "causal_clock": CAUSAL_CLOCK,
        "canonical_source_rewritten": False,
        "sources": sources,
        "total_mbo_records": sum(row["mbo_records"] for row in sources),
        "source_identity_hash": "",
        "manifest_hash": "",
    }
    manifest["source_identity_hash"] = source_identity_hash(manifest)
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
