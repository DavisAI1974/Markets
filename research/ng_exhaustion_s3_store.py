"""Hash-verified S3 read/cache layer for NG exhaustion V0.

Canonical data lives in S3. Local files are disposable cache entries and are
never trusted without byte-size + SHA-256 verification against the frozen
content manifest. The reader only pulls the requested day partition.
"""
from __future__ import annotations

from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterator

BUCKET = "bento-568968024170-us-east-2-an"
PREFIX = "nymex/ng_exhaustion/v0/"
CONTENT_MANIFEST_KEY = PREFIX + "content_manifest.json"
EXPECTED_CONTENT_MANIFEST_SHA256 = "0ee7841cdc08e49454d3eb0af936102f82b76c72f2b49c1b4ba01fd06e7c4128"
EXPECTED_ARTIFACT_SHA256 = "224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39"
EXPECTED_CLASSIFIER_SHA256 = "698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9"
EXPECTED_DAYS = {"20250717": 420, "20250923": 446, "20250930": 428, "20251001": 417}
EXPECTED_FAMILY_COUNTS = {"A": 1616, "B": 35, "C": 60}
DEFAULT_CACHE_DIR = Path(os.environ.get("NG_EXHAUSTION_CACHE_DIR", "/var/lib/markets/ng_exhaustion/cache/v0"))


class S3StoreError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _default_s3_client():
    """Prefer Markets' credential resolver; fall back to normal boto3 resolution."""
    try:
        kalshi_dir = Path(__file__).resolve().parent / "kalshi"
        if kalshi_dir.exists():
            sys.path.insert(0, str(kalshi_dir))
            import creds  # type: ignore
            return creds.aws_client("s3", "us-east-2")
    except Exception:
        pass
    import boto3
    return boto3.client("s3", region_name="us-east-2")


class NGExhaustionS3Store:
    def __init__(self, *, s3=None, cache_dir: str | Path | None = None, bucket: str = BUCKET, prefix: str = PREFIX):
        self.s3 = s3 or _default_s3_client()
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
        self.bucket = bucket
        self.prefix = prefix
        if bucket != BUCKET or prefix != PREFIX:
            raise S3StoreError("V0 bucket/prefix drift")
        self._manifest: dict[str, Any] | None = None

    def _get_bytes(self, key: str) -> bytes:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as exc:
            raise S3StoreError(f"S3 read failed for {key}: {exc}") from exc

    def load_manifest(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._manifest is not None and not refresh:
            return self._manifest
        raw = self._get_bytes(self.prefix + "content_manifest.json")
        digest = sha256_bytes(raw)
        if digest != EXPECTED_CONTENT_MANIFEST_SHA256:
            raise S3StoreError(f"content manifest SHA drift: {digest}")
        try:
            m = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise S3StoreError(f"content manifest JSON invalid: {exc}") from exc
        if m.get("schema") != "markets.ng_exhaustion.s3_stage.v1":
            raise S3StoreError("content manifest schema drift")
        if m.get("s3_bucket") != BUCKET or m.get("s3_prefix") != PREFIX:
            raise S3StoreError("content manifest location drift")
        src = m.get("canonical_source", {})
        if src.get("artifact_sha256") != EXPECTED_ARTIFACT_SHA256:
            raise S3StoreError("canonical artifact SHA drift")
        inv = m.get("frozen_invariants", {})
        if inv.get("classifier_sha256") != EXPECTED_CLASSIFIER_SHA256:
            raise S3StoreError("classifier SHA drift")
        if inv.get("future_price_or_price_bearing_window_served") is not False:
            raise S3StoreError("future-price wall drift")
        if inv.get("blind_record_outcome_wall_scan") != "PASS":
            raise S3StoreError("outcome wall drift")
        if inv.get("day_counts") != EXPECTED_DAYS:
            raise S3StoreError("day count drift")
        if inv.get("family_counts") != EXPECTED_FAMILY_COUNTS:
            raise S3StoreError("family count drift")
        if int(inv.get("records", -1)) != sum(EXPECTED_DAYS.values()):
            raise S3StoreError("record total drift")
        if set(m.get("partitions", {})) != set(EXPECTED_DAYS):
            raise S3StoreError("partition inventory drift")
        self._manifest = m
        return m

    def partition_info(self, day: str) -> dict[str, Any]:
        day = str(day)
        m = self.load_manifest()
        try:
            info = dict(m["partitions"][day])
        except KeyError as exc:
            raise S3StoreError(f"unknown V0 day {day}") from exc
        if int(info.get("records", -1)) != EXPECTED_DAYS[day]:
            raise S3StoreError(f"partition record count drift for {day}")
        return info

    def cached_partition_path(self, day: str) -> Path:
        return self.cache_dir / f"day={day}" / "records.jsonl.gz"

    def ensure_day_cached(self, day: str) -> tuple[Path, bool]:
        """Return (path, cache_hit). A bad cache entry is deleted and re-fetched atomically."""
        info = self.partition_info(day)
        dest = self.cached_partition_path(day)
        dest.parent.mkdir(parents=True, exist_ok=True)

        def good(path: Path) -> bool:
            return path.exists() and path.stat().st_size == int(info["compressed_bytes"]) and sha256_file(path) == info["compressed_sha256"]

        if good(dest):
            return dest, True
        if dest.exists():
            dest.unlink()
        tmp = dest.with_suffix(dest.suffix + ".part")
        if tmp.exists():
            tmp.unlink()
        key = self.prefix + info["path"]
        try:
            self.s3.download_file(self.bucket, key, str(tmp))
        except Exception as exc:
            if tmp.exists():
                tmp.unlink()
            raise S3StoreError(f"S3 download failed for {key}: {exc}") from exc
        if not good(tmp):
            got_size = tmp.stat().st_size if tmp.exists() else None
            got_sha = sha256_file(tmp) if tmp.exists() else None
            if tmp.exists():
                tmp.unlink()
            raise S3StoreError(f"download verification failed for {day}: bytes={got_size} sha={got_sha}")
        os.replace(tmp, dest)
        return dest, False

    def iter_day_records(self, day: str) -> Iterator[dict[str, Any]]:
        day = str(day)
        info = self.partition_info(day)
        path, _ = self.ensure_day_cached(day)
        n = 0
        fam = Counter()
        seen = set()
        uncompressed = hashlib.sha256()
        uncompressed_n = 0
        with gzip.open(path, "rb") as fh:
            for raw in fh:
                uncompressed.update(raw)
                uncompressed_n += len(raw)
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise S3StoreError(f"partition JSON decode failure {day} row {n}: {exc}") from exc
                if str(row.get("day")) != day:
                    raise S3StoreError(f"cross-day row in {day}: {row.get('day')}")
                blind_id = row.get("blind_id")
                if not blind_id or blind_id in seen:
                    raise S3StoreError(f"missing/duplicate blind_id in {day}: {blind_id}")
                seen.add(blind_id)
                family = row.get("family")
                if family not in {"A", "B", "C"}:
                    raise S3StoreError(f"invalid family in {day}: {family}")
                forbidden = {"future_price", "actual_price", "realized_price", "outcome", "actual_outcome"}.intersection(row)
                if forbidden:
                    raise S3StoreError(f"forbidden outcome fields in {day}: {sorted(forbidden)}")
                n += 1
                fam[family] += 1
                yield row
        if n != int(info["records"]):
            raise S3StoreError(f"decoded record count drift for {day}: {n}")
        if uncompressed_n != int(info["uncompressed_bytes"]):
            raise S3StoreError(f"uncompressed byte count drift for {day}: {uncompressed_n}")
        if uncompressed.hexdigest() != info["uncompressed_sha256"]:
            raise S3StoreError(f"uncompressed SHA drift for {day}")
        if dict(sorted(fam.items())) != info.get("families"):
            raise S3StoreError(f"family count drift inside {day}: {dict(fam)}")

    def day_records(self, day: str) -> list[dict[str, Any]]:
        return list(self.iter_day_records(day))

    def provenance(self, day: str) -> dict[str, str]:
        info = self.partition_info(day)
        return {
            "bucket": self.bucket,
            "key": self.prefix + info["path"],
            "sha256": info["compressed_sha256"],
            "classifier_sha256": EXPECTED_CLASSIFIER_SHA256,
        }
