#!/usr/bin/env python3
"""Fail-closed AWS/S3 source resolver for the five-year NG MBO V4 census.

This module is source plumbing only. It does not launch the exhaustion census,
group chains, mutate the frozen detector/runway, or expose/mutate Frankie.

The five-year native DBN corpus lives in S3. Because the archive audit records
duplicate intervals and unexpected partial overlaps, prefix-wide enumeration is
intentionally forbidden. Exact canonical object keys must come from the
consolidation manifest or an explicit operator-supplied object manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

DEFAULT_REGION = "us-east-2"
DEFAULT_BUCKET = "bento-568968024170-us-east-2-an"
DEFAULT_PREFIX = "nymex/ng_mbo_5y_v0/"
DEFAULT_CONSOLIDATION_KEY = DEFAULT_PREFIX + "_consolidation/COMPLETE.json"
DEFAULT_STAGE_DIR = "/mnt/markets/ng_mbo_5y_v0"
REVISION = "NG_EXHAUSTION_MBO_5Y_AWS_SOURCE_V1_20260820"

# Ordered from strongest/most explicit to weaker but still deliberate field names.
CANONICAL_FIELD_PRIORITIES = (
    ("canonical_dbn_keys", "canonical_dbn_objects", "canonical_objects"),
    ("selected_dbn_keys", "selected_dbn_objects", "selected_objects"),
    ("native_dbn_keys", "native_dbn_objects"),
)


class SourceSelectionError(RuntimeError):
    pass


def _walk(obj: Any) -> Iterable[tuple[str | None, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key), value
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield None, value
            yield from _walk(value)


def _strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _strings(value)


def normalize_dbn_key(value: str, bucket: str, prefix: str) -> str | None:
    text = str(value).strip()
    s3_prefix = f"s3://{bucket}/"
    if text.startswith("s3://"):
        if not text.startswith(s3_prefix):
            return None
        text = text[len(s3_prefix):]
    text = text.lstrip("/")
    if not text.startswith(prefix):
        return None
    if not (text.endswith(".dbn") or text.endswith(".dbn.zst")):
        return None
    if "/_consolidation/" in f"/{text}":
        return None
    return text


def _extract_from_subtree(obj: Any, bucket: str, prefix: str) -> list[str]:
    keys = []
    for value in _strings(obj):
        key = normalize_dbn_key(value, bucket, prefix)
        if key is not None:
            keys.append(key)
    return keys


def resolve_canonical_keys(manifest: Any, bucket: str, prefix: str) -> tuple[list[str], str]:
    """Resolve an explicit canonical DBN set; never fall back to prefix listing."""
    candidates: dict[str, list[list[str]]] = {}
    for field, value in _walk(manifest):
        if field is None:
            continue
        lname = field.lower()
        for tier in CANONICAL_FIELD_PRIORITIES:
            if lname in tier:
                found = _extract_from_subtree(value, bucket, prefix)
                if found:
                    candidates.setdefault(lname, []).append(found)

    for tier in CANONICAL_FIELD_PRIORITIES:
        tier_sets: list[tuple[str, list[str]]] = []
        for field in tier:
            for found in candidates.get(field, []):
                tier_sets.append((field, sorted(set(found))))
        if not tier_sets:
            continue
        unique_sets = {tuple(keys) for _, keys in tier_sets}
        if len(unique_sets) != 1:
            detail = {field: len(keys) for field, keys in tier_sets}
            raise SourceSelectionError(
                f"conflicting canonical DBN selections at the same priority tier: {detail}"
            )
        field = tier_sets[0][0]
        keys = list(next(iter(unique_sets)))
        validate_canonical_keys(keys, bucket, prefix)
        return keys, field

    raise SourceSelectionError(
        "no explicit canonical/selected/native DBN object list found; refusing "
        "prefix-wide enumeration because the five-year archive audit records "
        "duplicate intervals and unexpected partial overlaps"
    )


def validate_canonical_keys(keys: list[str], bucket: str, prefix: str) -> None:
    if not keys:
        raise SourceSelectionError("canonical DBN object list is empty")
    if len(keys) != len(set(keys)):
        raise SourceSelectionError("canonical DBN object list contains duplicate keys")
    bad = [k for k in keys if normalize_dbn_key(k, bucket, prefix) != k]
    if bad:
        raise SourceSelectionError(f"invalid/out-of-scope DBN keys: {bad[:3]}")


def _aws_json(args: list[str], region: str) -> Any:
    cmd = ["aws", *args, "--region", region, "--output", "json"]
    proc = subprocess.run(cmd, check=True, text=True, capture_output=True)
    return json.loads(proc.stdout)


def _aws_cp(src: str, dst: str, region: str) -> None:
    subprocess.run(
        ["aws", "s3", "cp", src, dst, "--region", region, "--only-show-errors"],
        check=True,
    )


def read_s3_json(bucket: str, key: str, region: str) -> Any:
    proc = subprocess.run(
        ["aws", "s3", "cp", f"s3://{bucket}/{key}", "-", "--region", region, "--only-show-errors"],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout)


def load_object_manifest(path_or_uri: str, region: str) -> Any:
    if path_or_uri.startswith("s3://"):
        without = path_or_uri[5:]
        bucket, key = without.split("/", 1)
        return read_s3_json(bucket, key, region)
    return json.loads(Path(path_or_uri).read_text())


def _local_path(stage_dir: Path, key: str, prefix: str) -> Path:
    rel = PurePosixPath(key).relative_to(PurePosixPath(prefix))
    if any(part in ("", ".", "..") for part in rel.parts):
        raise SourceSelectionError(f"unsafe S3 key path: {key}")
    return stage_dir.joinpath(*rel.parts)


def remote_inventory(bucket: str, keys: list[str], region: str) -> list[dict[str, Any]]:
    rows = []
    for key in keys:
        meta = _aws_json(["s3api", "head-object", "--bucket", bucket, "--key", key], region)
        rows.append(
            {
                "bucket": bucket,
                "key": key,
                "content_length": int(meta.get("ContentLength", 0)),
                "etag": str(meta.get("ETag", "")).strip('"'),
                "last_modified": meta.get("LastModified"),
            }
        )
    return rows


def stage_objects(
    bucket: str,
    keys: list[str],
    prefix: str,
    stage_dir: Path,
    region: str,
) -> list[dict[str, Any]]:
    staged = []
    for key in keys:
        dst = _local_path(stage_dir, key, prefix)
        dst.parent.mkdir(parents=True, exist_ok=True)
        _aws_cp(f"s3://{bucket}/{key}", str(dst), region)
        staged.append({"key": key, "local_path": str(dst), "local_bytes": dst.stat().st_size})
    return staged


def receipt_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    ap.add_argument("--consolidation-key", default=DEFAULT_CONSOLIDATION_KEY)
    ap.add_argument(
        "--object-manifest",
        help="Explicit local or s3:// JSON object manifest. If omitted, use consolidation manifest.",
    )
    ap.add_argument("--stage-dir", default=DEFAULT_STAGE_DIR)
    ap.add_argument("--receipt", default="NG_EXHAUSTION_MBO_5Y_AWS_SOURCE_RECEIPT_20260820.json")
    ap.add_argument("--inventory-only", action="store_true")
    args = ap.parse_args()

    if args.object_manifest:
        manifest = load_object_manifest(args.object_manifest, args.region)
        manifest_source = args.object_manifest
    else:
        manifest = read_s3_json(args.bucket, args.consolidation_key, args.region)
        manifest_source = f"s3://{args.bucket}/{args.consolidation_key}"

    keys, selection_field = resolve_canonical_keys(manifest, args.bucket, args.prefix)
    inventory = remote_inventory(args.bucket, keys, args.region)
    staged = []
    if not args.inventory_only:
        staged = stage_objects(
            args.bucket, keys, args.prefix, Path(args.stage_dir), args.region
        )

    receipt = {
        "status": "INVENTORY_COMPLETE" if args.inventory_only else "SOURCE_STAGING_COMPLETE",
        "revision": REVISION,
        "scientific_scope": (
            "source plumbing for five-year V4 chain-family exhaustion architecture research"
        ),
        "empirical_census_launched": False,
        "frankie_exposed": False,
        "frankie_mutated": False,
        "legacy_54_55_week_corpus_used": False,
        "prefix_wide_enumeration_used": False,
        "region": args.region,
        "bucket": args.bucket,
        "prefix": args.prefix,
        "manifest_source": manifest_source,
        "selection_field": selection_field,
        "canonical_object_count": len(keys),
        "canonical_total_bytes": sum(r["content_length"] for r in inventory),
        "canonical_keys": keys,
        "remote_inventory": inventory,
        "staged": staged,
        "stage_dir": None if args.inventory_only else args.stage_dir,
    }
    receipt["receipt_sha256"] = receipt_hash(receipt)
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
