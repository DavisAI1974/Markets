#!/usr/bin/env python3
"""Inventory G15 historical L1/trades and MBO objects without inventing presence.

A source is PRESENT only after it is opened and every matching record can be
normalized. Missing local files become MISSING. Remote S3 failures that prevent
observation (credentials, permissions, transient network) become UNKNOWN rather
than false success or false absence. Exact instrument definition periods are
required as observed input; the inventory never substitutes an event range for
a definition period.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse

from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, expected_g15_manifest, validate_manifest
from ng_historical_normalize import (
    NormalizeError,
    iter_dbn,
    iter_jsonl,
    normalize_record,
    record_matches_kind,
)

SCHEMA = "ng_historical_inventory.v1"


class InventoryError(ValueError):
    pass


def _is_s3(uri: str) -> bool:
    return uri.startswith("s3://")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _confirmed_missing_s3(error: Exception) -> bool:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return False
    metadata = response.get("ResponseMetadata") or {}
    status = metadata.get("HTTPStatusCode")
    code = str((response.get("Error") or {}).get("Code") or "")
    return status == 404 or code in {"404", "NoSuchKey", "NotFound"}


@contextlib.contextmanager
def materialize(uri: str) -> Iterator[tuple[Path | None, str, dict[str, Any]]]:
    """Yield ``(local_path, OBSERVED|MISSING|UNKNOWN, metadata)``."""
    if not _is_s3(uri):
        path = Path(uri)
        if not path.exists():
            yield None, "MISSING", {"observation_error": "local path does not exist"}
            return
        yield path, "OBSERVED", {}
        return

    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        yield None, "UNKNOWN", {"observation_error": "invalid S3 URI"}
        return
    try:
        import boto3  # type: ignore
        client = boto3.client("s3")
        head = client.head_object(Bucket=bucket, Key=key)
    except Exception as error:
        status = "MISSING" if _confirmed_missing_s3(error) else "UNKNOWN"
        yield None, status, {"observation_error": repr(error)}
        return

    suffixes = "".join(Path(key).suffixes) or ".bin"
    with tempfile.TemporaryDirectory(prefix="ng_inventory_") as tempdir:
        local = Path(tempdir) / ("source" + suffixes)
        metadata = {
            "s3_etag": str(head.get("ETag") or "").strip('"') or None,
            "s3_content_length": head.get("ContentLength"),
            "s3_last_modified": head.get("LastModified").isoformat() if head.get("LastModified") else None,
        }
        try:
            client.download_file(bucket, key, str(local))
        except Exception as error:
            yield None, "UNKNOWN", {**metadata, "observation_error": repr(error)}
            return
        yield local, "OBSERVED", metadata


def validate_definitions(definitions: Mapping[str, Any], publisher_id: int) -> dict[str, dict[str, Any]]:
    """Validate observed NGJ26/NGK26 definition metadata against canonical G15 identity."""
    result: dict[str, dict[str, Any]] = {}
    for symbol, expected_id in (("NGJ26", 1008), ("NGK26", 996)):
        row = dict(definitions.get(symbol) or {})
        required = (
            "dataset", "publisher_id", "instrument_id", "raw_symbol", "definition_date",
            "definition_start_s", "definition_end_s", "observed_at",
        )
        missing = [name for name in required if row.get(name) in (None, "")]
        if missing:
            raise InventoryError(f"{symbol} definition missing: {', '.join(missing)}")
        if row["dataset"] != "GLBX.MDP3":
            raise InventoryError(f"{symbol} definition dataset must be GLBX.MDP3")
        if int(row["publisher_id"]) != int(publisher_id):
            raise InventoryError(f"{symbol} definition publisher mismatch")
        if int(row["instrument_id"]) != expected_id or row["raw_symbol"] != symbol:
            raise InventoryError(f"{symbol} definition identity mismatch")
        start = float(row["definition_start_s"])
        end = float(row["definition_end_s"])
        if end < start:
            raise InventoryError(f"{symbol} definition period is backwards")
        row["publisher_id"] = int(row["publisher_id"])
        row["instrument_id"] = int(row["instrument_id"])
        row["definition_start_s"] = start
        row["definition_end_s"] = end
        result[symbol] = row
    return result


def inspect_uri(
    uri: str,
    *,
    source_kind: str,
    day: str,
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    if source_kind not in {"l1_trades", "mbo"}:
        raise InventoryError(f"unsupported source_kind: {source_kind}")
    if day not in G15_CONTRACT_MAP:
        raise InventoryError(f"day is not canonical G15: {day}")
    contract = G15_CONTRACT_MAP[day]
    forced_kind = "trade" if source_kind == "l1_trades" else "mbo"
    entry: dict[str, Any] = {
        "day": day,
        "source_kind": source_kind,
        "status": "UNKNOWN",
        "location": uri,
        "dataset": definition["dataset"],
        "publisher_id": int(definition["publisher_id"]),
        "instrument_id": contract["instrument_id"],
        "raw_symbol": contract["raw_symbol"],
        "definition_date": definition["definition_date"],
        "definition_start_s": float(definition["definition_start_s"]),
        "definition_end_s": float(definition["definition_end_s"]),
        "event_start_s": None,
        "event_end_s": None,
        "record_count": None,
        "input_record_count": None,
        "skipped_nonmatching": None,
        "size_bytes": None,
        "sha256": None,
        "inventory_observed_at": None,
        "definition_observed_at": definition["observed_at"],
        "observation_error": None,
    }
    with materialize(uri) as (path, observation, metadata):
        entry.update(metadata)
        if observation == "MISSING":
            entry["status"] = "MISSING"
            return entry
        if observation != "OBSERVED" or path is None:
            entry["status"] = "UNKNOWN"
            return entry
        entry["size_bytes"] = path.stat().st_size
        entry["sha256"] = _sha256(path)
        is_dbn = path.suffix.lower() in {".dbn", ".zst"} or path.name.lower().endswith(".dbn.zst")
        rows = iter_dbn(path) if is_dbn else iter_jsonl(path)
        input_count = 0
        normalized_count = 0
        skipped = 0
        first: float | None = None
        last: float | None = None
        previous: tuple[float, int, int] | None = None
        identities: set[tuple[Any, ...]] = set()
        try:
            for input_count, raw in enumerate(rows, 1):
                if not record_matches_kind(raw, forced_kind):
                    skipped += 1
                    continue
                normalized = normalize_record(
                    raw,
                    event_type=forced_kind,
                    dataset=definition["dataset"],
                    publisher_id=int(definition["publisher_id"]),
                    instrument_id=contract["instrument_id"],
                    raw_symbol=contract["raw_symbol"],
                    definition_date=definition["definition_date"],
                    session_day=day,
                    source_id=uri,
                    ingest_sequence=input_count,
                )
                key = (
                    float(normalized["ts_event_s"]),
                    int(normalized["source_sequence"]),
                    int(normalized["ingest_sequence"]),
                )
                if previous is not None and key < previous:
                    raise NormalizeError(f"source moved backwards at input record {input_count}")
                previous = key
                normalized_count += 1
                first = key[0] if first is None else first
                last = key[0]
                identities.add(
                    (
                        normalized["dataset"], normalized["publisher_id"], normalized["instrument_id"],
                        normalized["raw_symbol"], normalized["definition_date"], normalized["session_day"],
                    )
                )
        except Exception as error:
            entry["status"] = "CORRUPT"
            entry["input_record_count"] = input_count
            entry["record_count"] = normalized_count
            entry["skipped_nonmatching"] = skipped
            entry["observation_error"] = repr(error)
            entry["inventory_observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            return entry
        entry["input_record_count"] = input_count
        entry["skipped_nonmatching"] = skipped
        if normalized_count <= 0:
            entry["status"] = "CORRUPT"
            entry["record_count"] = 0
            entry["observation_error"] = "source contained zero matching normalizable records"
            entry["inventory_observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            return entry
        expected_identity = (
            definition["dataset"], int(definition["publisher_id"]), contract["instrument_id"],
            contract["raw_symbol"], definition["definition_date"], day,
        )
        if identities != {expected_identity}:
            entry["status"] = "CORRUPT"
            entry["record_count"] = normalized_count
            entry["event_start_s"] = first
            entry["event_end_s"] = last
            entry["observation_error"] = f"identity mismatch: {sorted(identities)!r}"
            entry["inventory_observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            return entry
        if first is None or last is None or first < entry["definition_start_s"] or last > entry["definition_end_s"]:
            entry["status"] = "CORRUPT"
            entry["record_count"] = normalized_count
            entry["event_start_s"] = first
            entry["event_end_s"] = last
            entry["observation_error"] = "event range falls outside observed definition period"
            entry["inventory_observed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            return entry
        entry.update(
            status="PRESENT",
            event_start_s=first,
            event_end_s=last,
            record_count=normalized_count,
            inventory_observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        return entry


def build_manifest(
    *,
    l1_pattern: str,
    mbo_pattern: str,
    publisher_id: int,
    definitions: Mapping[str, Any],
) -> dict[str, Any]:
    checked_definitions = validate_definitions(definitions, publisher_id)
    manifest = expected_g15_manifest(publisher_id=publisher_id)
    entries = []
    for day in G15_DATES:
        symbol = G15_CONTRACT_MAP[day]["raw_symbol"]
        definition = checked_definitions[symbol]
        entries.append(
            inspect_uri(
                l1_pattern.format(day=day, raw_symbol=symbol),
                source_kind="l1_trades", day=day, definition=definition,
            )
        )
        entries.append(
            inspect_uri(
                mbo_pattern.format(day=day, raw_symbol=symbol),
                source_kind="mbo", day=day, definition=definition,
            )
        )
    manifest["entries"] = entries
    manifest["remote_inventory_verified"] = all(entry["status"] != "UNKNOWN" for entry in entries)
    manifest["definitions"] = checked_definitions
    manifest["inventory"] = {
        "schema": SCHEMA,
        "l1_pattern": l1_pattern,
        "mbo_pattern": mbo_pattern,
        "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "unknown_is_not_present": True,
    }
    manifest["report"] = validate_manifest(manifest)
    return manifest


def selftest() -> int:
    definition = {
        "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 1008, "raw_symbol": "NGJ26",
        "definition_date": "2026-03-01", "definition_start_s": 0.0, "definition_end_s": 10.0,
        "observed_at": "2026-07-21T00:00:00Z",
    }
    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir) / "trades.jsonl"
        base = {
            "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 1008,
            "raw_symbol": "NGJ26", "definition_date": "2026-03-01", "session_day": "20260316",
            "event_type": "trade", "price": 3.0, "size": 1, "side": "B",
        }
        path.write_text(
            "\n".join(json.dumps({**base, "ts_event_s": float(i), "sequence": i}) for i in range(1, 4)) + "\n",
            encoding="utf-8",
        )
        entry = inspect_uri(str(path), source_kind="l1_trades", day="20260316", definition=definition)
        assert entry["status"] == "PRESENT" and entry["record_count"] == 3
        missing = inspect_uri(
            str(Path(tempdir) / "missing.jsonl"), source_kind="mbo", day="20260316", definition=definition,
        )
        assert missing["status"] == "MISSING"
    print("[ng_historical_inventory] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory and validate G15 historical L1/MBO corpus")
    parser.add_argument("--l1-pattern", help="path or s3 URI pattern with {day} and optional {raw_symbol}")
    parser.add_argument("--mbo-pattern", help="path or s3 URI pattern with {day} and optional {raw_symbol}")
    parser.add_argument("--definitions", type=Path, help="observed NGJ26/NGK26 definition metadata JSON")
    parser.add_argument("--publisher-id", type=int)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    missing = [
        name for name, value in {
            "l1-pattern": args.l1_pattern, "mbo-pattern": args.mbo_pattern,
            "definitions": args.definitions, "publisher-id": args.publisher_id, "out": args.out,
        }.items() if value in (None, "")
    ]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))
    if not args.definitions.exists():
        parser.error(f"definitions file does not exist: {args.definitions}")
    definitions = json.loads(args.definitions.read_text(encoding="utf-8"))
    manifest = build_manifest(
        l1_pattern=args.l1_pattern, mbo_pattern=args.mbo_pattern,
        publisher_id=args.publisher_id, definitions=definitions,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["report"], indent=2, sort_keys=True))
    return 0 if manifest["report"]["status"] in {"READY", "UNKNOWN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
