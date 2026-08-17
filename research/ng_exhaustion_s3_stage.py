#!/usr/bin/env python3
"""Stage NG exhaustion artifacts for the canonical Markets S3 data plane.

This script never uploads directly. Markets doctrine says research/kalshi/platform_sync.py
is the ONE door between local cache and S3. This module prepares a deterministic, hash-
verified directory that platform_sync can push under nymex/ng_exhaustion/v0/.

Canonical source remains the exact frozen GitHub Actions ZIP. Read-optimized day partitions
are deterministic JSONL.GZ derivatives with hashes recorded in content_manifest.json.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

EXPECTED_ARTIFACT_SHA256 = "224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39"
EXPECTED_CLASSIFIER_SHA256 = "698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9"
EXPECTED_RECORDS = 1711
EXPECTED_FAMILY_COUNTS = {"A": 1616, "B": 35, "C": 60}
EXPECTED_DAY_COUNTS = {"20250717": 420, "20250923": 446, "20250930": 428, "20251001": 417}
# Frozen V0 compressed derivatives after canonical JSON sorting + gzip mtime=0 + OS=255.
# Pinning these makes Python/zlib runtime drift fail closed rather than silently changing S3 bytes.
EXPECTED_PARTITION_SHA256 = {
    "20250717": "5a475a45629fe25fb1b782b0ed79b9cfec68daa8b67c080b22eddb9af22b419b",
    "20250923": "e7149ce7967ca6251928a41ca45197b47fcee00f926484adac8c7895bcddf6c2",
    "20250930": "41086c62725b26f1eef80c405bc4ebc49feebaf9db49f6f49ead1e6e3fbcc102",
    "20251001": "739a352e03b0da9dffa0177251ceab6a7f18e73b48da35b29ff79975388da6e7",
}
S3_BUCKET = "bento-568968024170-us-east-2-an"
S3_PREFIX = "nymex/ng_exhaustion/v0/"


class StageError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_line(row: dict) -> bytes:
    return (json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def deterministic_gzip(data: bytes) -> bytes:
    """Return the frozen V0 gzip representation.

    Python 3.11 and 3.13 differ in the gzip OS header byte when mtime=0 even when the
    deflate payload is identical. Normalize byte 9 to RFC 1952 OS=255 (unknown) so the
    same V0 input produces the same compressed bytes across those runtimes. The final
    partition SHA is also pinned, so any future zlib payload drift fails closed.
    """
    out = bytearray(gzip.compress(data, compresslevel=9, mtime=0))
    if len(out) < 18 or out[0:3] != b"\x1f\x8b\x08":
        raise StageError("gzip encoder produced an invalid header")
    out[9] = 255
    return bytes(out)


def _load_member(zf: zipfile.ZipFile, name: str) -> bytes:
    try:
        return zf.read(name)
    except KeyError as exc:
        raise StageError(f"required artifact member missing: {name}") from exc


def validate_source(artifact_zip: Path, classifier_path: Path) -> tuple[list[dict], dict, dict]:
    artifact_sha = sha256_file(artifact_zip)
    if artifact_sha != EXPECTED_ARTIFACT_SHA256:
        raise StageError(f"artifact SHA drift: {artifact_sha}")
    classifier_sha = sha256_file(classifier_path)
    if classifier_sha != EXPECTED_CLASSIFIER_SHA256:
        raise StageError(f"classifier SHA drift: {classifier_sha}")

    with zipfile.ZipFile(artifact_zip) as zf:
        records_raw = _load_member(zf, "ng_frankie_blind_records.json")
        blind_manifest = json.loads(_load_member(zf, "ng_frankie_blind_manifest.json"))
        rows = json.loads(records_raw)

    if len(rows) != EXPECTED_RECORDS:
        raise StageError(f"record count drift: {len(rows)}")
    fam = dict(Counter(r.get("family") for r in rows))
    if fam != EXPECTED_FAMILY_COUNTS:
        raise StageError(f"family count drift: {fam}")
    days = dict(Counter(str(r.get("day")) for r in rows))
    if days != EXPECTED_DAY_COUNTS:
        raise StageError(f"day count drift: {days}")
    if len({r.get("blind_id") for r in rows}) != len(rows):
        raise StageError("blind_id uniqueness failure")

    if blind_manifest.get("blind_n") != EXPECTED_RECORDS:
        raise StageError("blind manifest blind_n drift")
    if blind_manifest.get("future_price_or_price_bearing_window_served") is not False:
        raise StageError("blind manifest future-price wall failed")
    if blind_manifest.get("blind_record_outcome_wall_scan") != "PASS":
        raise StageError("blind manifest outcome-wall scan failed")
    if blind_manifest.get("a_classifier_sha256") != EXPECTED_CLASSIFIER_SHA256:
        raise StageError("blind manifest classifier SHA drift")

    forbidden_exact = {"future_price", "actual_price", "realized_price", "outcome", "actual_outcome"}
    for i, row in enumerate(rows):
        hit = forbidden_exact.intersection(row)
        if hit:
            raise StageError(f"forbidden outcome/future field at row {i}: {sorted(hit)}")
        anchor = row.get("causal_price_anchor")
        if not isinstance(anchor, dict) or "value" not in anchor:
            raise StageError(f"missing causal price anchor at row {i}")

    source_meta = {
        "artifact_sha256": artifact_sha,
        "artifact_bytes": artifact_zip.stat().st_size,
        "records_member_sha256": sha256_bytes(records_raw),
        "records_member_bytes": len(records_raw),
        "classifier_sha256": classifier_sha,
    }
    return rows, blind_manifest, source_meta


def stage(artifact_zip: Path, classifier_path: Path, output_dir: Path) -> dict:
    rows, blind_manifest, source = validate_source(artifact_zip, classifier_path)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "canonical").mkdir(parents=True)
    (output_dir / "partitions").mkdir(parents=True)

    canonical_name = "ng_exhaustion_blind_input_artifact_9274443976.zip"
    canonical_dst = output_dir / "canonical" / canonical_name
    shutil.copyfile(artifact_zip, canonical_dst)
    if sha256_file(canonical_dst) != EXPECTED_ARTIFACT_SHA256:
        raise StageError("canonical copy checksum mismatch")

    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_day[str(row["day"])].append(row)

    partition_manifest = {}
    total_uncompressed = total_compressed = 0
    for day in sorted(by_day):
        day_rows = sorted(by_day[day], key=lambda r: (int(r["t0_second_utc"]), str(r["blind_id"])))
        raw = b"".join(canonical_json_line(r) for r in day_rows)
        gz = deterministic_gzip(raw)
        gz_sha = sha256_bytes(gz)
        if gz_sha != EXPECTED_PARTITION_SHA256[day]:
            raise StageError(f"frozen partition SHA drift at {day}: {gz_sha}")
        rel = Path("partitions") / f"day={day}" / "records.jsonl.gz"
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(gz)
        if deterministic_gzip(raw) != gz:
            raise StageError(f"non-deterministic gzip at {day}")
        partition_manifest[day] = {
            "path": rel.as_posix(),
            "records": len(day_rows),
            "compressed_bytes": len(gz),
            "compressed_sha256": gz_sha,
            "uncompressed_bytes": len(raw),
            "uncompressed_sha256": sha256_bytes(raw),
            "families": dict(sorted(Counter(r["family"] for r in day_rows).items())),
            "min_t0_second_utc": min(int(r["t0_second_utc"]) for r in day_rows),
            "max_t0_second_utc": max(int(r["t0_second_utc"]) for r in day_rows),
        }
        total_uncompressed += len(raw)
        total_compressed += len(gz)

    if {d: x["records"] for d, x in partition_manifest.items()} != EXPECTED_DAY_COUNTS:
        raise StageError("partition record counts drift")

    content_manifest = {
        "schema": "markets.ng_exhaustion.s3_stage.v1",
        "status": "READY_FOR_PLATFORM_SYNC",
        "s3_bucket": S3_BUCKET,
        "s3_prefix": S3_PREFIX,
        "canonical_source": {
            "path": f"canonical/{canonical_name}",
            **source,
            "github_actions_artifact_id": 9274443976,
        },
        "frozen_invariants": {
            "records": EXPECTED_RECORDS,
            "family_counts": EXPECTED_FAMILY_COUNTS,
            "day_counts": EXPECTED_DAY_COUNTS,
            "future_price_or_price_bearing_window_served": False,
            "blind_record_outcome_wall_scan": "PASS",
            "classifier_sha256": EXPECTED_CLASSIFIER_SHA256,
            "partition_sha256": EXPECTED_PARTITION_SHA256,
        },
        "partitions": partition_manifest,
        "partition_totals": {
            "compressed_bytes": total_compressed,
            "uncompressed_bytes": total_uncompressed,
            "records": sum(x["records"] for x in partition_manifest.values()),
        },
        "blind_manifest_snapshot": blind_manifest,
        "upload_door": "research/kalshi/platform_sync.py",
        "upload_command": (
            "python research/kalshi/platform_sync.py push "
            f"--prefix {S3_PREFIX} --src data/ng_exhaustion_s3_stage --execute "
            "--note 'NG exhaustion V0 canonical blind source + deterministic day partitions'"
        ),
        "notes": [
            "canonical ZIP is immutable source truth",
            "partitions are read-optimized frozen deterministic derivatives",
            "gzip OS header is normalized to 255 and compressed SHAs are pinned across Python runtimes",
            "content_manifest.json carries hashes; platform_sync writes the prefix inventory manifest.json",
            "NOVA model packets are derived views and must never replace canonical source objects",
        ],
    }
    manifest_path = output_dir / "content_manifest.json"
    manifest_path.write_text(json.dumps(content_manifest, indent=2, sort_keys=True) + "\n")

    if sha256_file(canonical_dst) != content_manifest["canonical_source"]["artifact_sha256"]:
        raise StageError("final canonical verification failed")
    for day, info in partition_manifest.items():
        p = output_dir / info["path"]
        if sha256_file(p) != info["compressed_sha256"] or p.stat().st_size != info["compressed_bytes"]:
            raise StageError(f"final partition verification failed: {day}")
    return content_manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", required=True)
    ap.add_argument("--classifier", required=True)
    ap.add_argument("--output-dir", default="data/ng_exhaustion_s3_stage")
    a = ap.parse_args()
    try:
        manifest = stage(Path(a.artifact), Path(a.classifier), Path(a.output_dir))
    except StageError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "output_dir": a.output_dir,
        "s3_bucket": manifest["s3_bucket"],
        "s3_prefix": manifest["s3_prefix"],
        "records": manifest["partition_totals"]["records"],
        "partition_bytes": manifest["partition_totals"]["compressed_bytes"],
        "canonical_artifact_sha256": manifest["canonical_source"]["artifact_sha256"],
        "upload_command": manifest["upload_command"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
