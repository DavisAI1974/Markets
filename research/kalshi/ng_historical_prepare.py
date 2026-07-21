#!/usr/bin/env python3
"""Prepare a READY G15 corpus for deterministic historical replay.

The inventory proves which raw objects were observed. This preparation step then
materializes each exact object, re-verifies its size and SHA-256 against the
manifest, normalizes it into the compact replay contract, and writes a
fingerprinted source index. Nothing is replayed from an arbitrary same-identity
file: normalized data must trace back to the observed manifest object.

Only one raw object is materialized at a time. Normalized outputs are staged and
renamed into place only after the full 12-session corpus succeeds, so a failed
run cannot publish a half-ready index. CME event contracts remain SHADOW and no
execution authority is created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from ng_historical_inventory import materialize
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, SOURCE_KINDS, validate_manifest
from ng_historical_normalize import normalize_file

SCHEMA = "ng_historical_prepared_corpus.v1"
SOURCE_KIND_TO_EVENT = {"l1_trades": "trade", "mbo": "mbo"}
SOURCE_ORDER = {"definition": 0, "l1_trades": 1, "mbo": 2}


class PrepareError(ValueError):
    """Raised when observed corpus provenance cannot be reproduced."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _manifest_entries(manifest: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in manifest.get("entries") or []:
        entry = dict(raw)
        key = (str(entry.get("day") or ""), str(entry.get("source_kind") or ""))
        if key in entries:
            raise PrepareError(f"duplicate manifest entry: {key}")
        entries[key] = entry
    expected = {(day, source_kind) for day in G15_DATES for source_kind in SOURCE_KINDS}
    missing = sorted(expected - set(entries))
    if missing:
        raise PrepareError(f"manifest missing canonical entries: {missing}")
    return entries


def _verify_observed_object(path: Path, entry: Mapping[str, Any]) -> None:
    expected_size = entry.get("size_bytes")
    expected_hash = entry.get("sha256")
    if expected_size in (None, "") or expected_hash in (None, ""):
        raise PrepareError(
            f"{entry.get('day')}:{entry.get('source_kind')}: READY entry lacks observed size/SHA-256"
        )
    actual_size = path.stat().st_size
    if actual_size != int(expected_size):
        raise PrepareError(
            f"{entry.get('day')}:{entry.get('source_kind')}: raw size changed "
            f"{actual_size} != {expected_size}"
        )
    actual_hash = _sha256(path)
    if actual_hash != str(expected_hash):
        raise PrepareError(
            f"{entry.get('day')}:{entry.get('source_kind')}: raw SHA-256 changed"
        )


def _verify_normalization_report(report: Mapping[str, Any], entry: Mapping[str, Any]) -> None:
    identity = dict(report.get("identity") or {})
    expected_identity = {
        "dataset": entry.get("dataset"),
        "publisher_id": entry.get("publisher_id"),
        "instrument_id": entry.get("instrument_id"),
        "raw_symbol": entry.get("raw_symbol"),
        "definition_date": entry.get("definition_date"),
        "session_day": entry.get("day"),
    }
    if identity != expected_identity:
        raise PrepareError(
            f"{entry.get('day')}:{entry.get('source_kind')}: normalization identity mismatch"
        )
    if int(report.get("record_count") or 0) != int(entry.get("record_count") or 0):
        raise PrepareError(
            f"{entry.get('day')}:{entry.get('source_kind')}: normalized record count differs from inventory"
        )
    for field in ("event_start_s", "event_end_s"):
        actual = float(report.get(field))
        expected = float(entry.get(field))
        if abs(actual - expected) > 1e-9:
            raise PrepareError(
                f"{entry.get('day')}:{entry.get('source_kind')}: {field} differs from inventory"
            )


def _definition_sources(manifest: Mapping[str, Any], stage: Path, final: Path) -> list[dict[str, Any]]:
    definitions = dict(manifest.get("definitions") or {})
    sources: list[dict[str, Any]] = []
    for symbol in ("NGJ26", "NGK26"):
        definition = dict(definitions.get(symbol) or {})
        required = (
            "dataset", "publisher_id", "instrument_id", "raw_symbol", "definition_date",
            "definition_start_s", "definition_end_s", "observed_at",
        )
        missing = [name for name in required if definition.get(name) in (None, "")]
        if missing:
            raise PrepareError(f"{symbol} observed definition missing: {', '.join(missing)}")
        if definition["raw_symbol"] != symbol:
            raise PrepareError(f"{symbol} definition identity mismatch")
        event = {
            "schema": "ng_normalized_event.v1",
            "event_type": "definition",
            "dataset": definition["dataset"],
            "publisher_id": int(definition["publisher_id"]),
            "instrument_id": int(definition["instrument_id"]),
            "raw_symbol": definition["raw_symbol"],
            "definition_date": definition["definition_date"],
            "session_day": G15_DATES[0] if symbol == "NGJ26" else "20260320",
            "ts_event_s": float(definition["definition_start_s"]),
            "source_sequence": 1,
            "ingest_sequence": 1,
            "source_id": f"observed-definition:{symbol}:{definition['observed_at']}",
        }
        name = f"definition_{symbol}.jsonl"
        staged_path = stage / name
        staged_path.write_text(_canonical(event) + "\n", encoding="utf-8")
        sources.append(
            {
                "day": event["session_day"],
                "source_kind": "definition",
                "event_type": "definition",
                "path": str(final / name),
                "record_count": 1,
                "event_start_s": event["ts_event_s"],
                "event_end_s": event["ts_event_s"],
                "sha256": _sha256(staged_path),
                "size_bytes": staged_path.stat().st_size,
                "definition_observed_at": definition["observed_at"],
            }
        )
    return sources


def prepare_corpus(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Materialize, verify, and normalize all 24 canonical G15 source objects."""
    report = validate_manifest(manifest)
    if report["status"] != "READY":
        raise PrepareError(f"G15 manifest is {report['status']}; a READY observed corpus is required")
    entries = _manifest_entries(manifest)
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    prepared_sources: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="g15_prepare_", dir=str(output_dir.parent)) as tempdir:
        stage = Path(tempdir)
        prepared_sources.extend(_definition_sources(manifest, stage, output_dir))
        for day in G15_DATES:
            contract = G15_CONTRACT_MAP[day]
            for source_kind in SOURCE_KINDS:
                entry = entries[(day, source_kind)]
                if entry.get("status") != "PRESENT":
                    raise PrepareError(f"{day}:{source_kind}: status changed from READY manifest")
                uri = str(entry.get("location") or "")
                if not uri:
                    raise PrepareError(f"{day}:{source_kind}: PRESENT entry lacks location")
                with materialize(uri) as (raw_path, observation, metadata):
                    if observation != "OBSERVED" or raw_path is None:
                        raise PrepareError(
                            f"{day}:{source_kind}: raw object no longer observable ({observation}): "
                            f"{metadata.get('observation_error')}"
                        )
                    _verify_observed_object(raw_path, entry)
                    name = f"{day}_{source_kind}.jsonl"
                    staged_path = stage / name
                    normalization = normalize_file(
                        raw_path,
                        kind=SOURCE_KIND_TO_EVENT[source_kind],
                        dataset=str(entry["dataset"]),
                        publisher_id=int(entry["publisher_id"]),
                        instrument_id=int(contract["instrument_id"]),
                        raw_symbol=str(contract["raw_symbol"]),
                        definition_date=str(entry["definition_date"]),
                        session_day=day,
                        output=staged_path,
                        skip_nonmatching=source_kind == "l1_trades",
                    )
                    _verify_normalization_report(normalization, entry)
                    normalization.update(
                        source_kind=source_kind,
                        source_uri=uri,
                        observed_raw_size_bytes=int(entry["size_bytes"]),
                        observed_raw_sha256=str(entry["sha256"]),
                        manifest_entry_fingerprint=_fingerprint(entry),
                    )
                    normalization["output"] = str(output_dir / name)
                    prepared_sources.append(
                        {
                            "day": day,
                            "source_kind": source_kind,
                            "event_type": SOURCE_KIND_TO_EVENT[source_kind],
                            "path": str(output_dir / name),
                            "record_count": normalization["record_count"],
                            "event_start_s": normalization["event_start_s"],
                            "event_end_s": normalization["event_end_s"],
                            "sha256": normalization["sha256"],
                            "size_bytes": normalization["size_bytes"],
                            "normalization": normalization,
                        }
                    )

        output_dir.mkdir(parents=True, exist_ok=True)
        for staged_path in sorted(stage.glob("*.jsonl")):
            os.replace(staged_path, output_dir / staged_path.name)

    prepared_sources.sort(
        key=lambda row: (
            str(row.get("day") or ""),
            SOURCE_ORDER.get(str(row.get("source_kind") or ""), 99),
            str(row.get("path") or ""),
        )
    )
    index = {
        "schema": SCHEMA,
        "market": "NG",
        "group": 15,
        "status": "READY",
        "authority": "HISTORICAL_REPLAY_INPUT_ONLY",
        "execution_authority": False,
        "manifest_fingerprint": _fingerprint(manifest),
        "manifest_report": report,
        "output_dir": str(output_dir),
        "source_count": len(prepared_sources),
        "sources": prepared_sources,
        "note": (
            "Every normalized source was re-materialized and matched to the observed manifest size/SHA-256. "
            "Definitions are observed metadata seeds, not price signals. CME event contracts remain SHADOW."
        ),
    }
    index["prepared_corpus_fingerprint"] = _fingerprint(index)
    return index


def validate_prepared_index(index: dict[str, Any], *, verify_files: bool = True) -> None:
    if index.get("schema") != SCHEMA or index.get("status") != "READY":
        raise PrepareError("prepared corpus index is not READY")
    if index.get("execution_authority") is not False:
        raise PrepareError("prepared corpus cannot grant execution authority")
    expected_fingerprint = index.get("prepared_corpus_fingerprint")
    payload = dict(index)
    payload.pop("prepared_corpus_fingerprint", None)
    if _fingerprint(payload) != expected_fingerprint:
        raise PrepareError("prepared corpus fingerprint mismatch")
    if not verify_files:
        return
    for source in index.get("sources") or []:
        path = Path(source["path"])
        if not path.is_file():
            raise PrepareError(f"prepared source missing: {path}")
        if path.stat().st_size != int(source["size_bytes"]):
            raise PrepareError(f"prepared source size mismatch: {path}")
        if _sha256(path) != source["sha256"]:
            raise PrepareError(f"prepared source hash mismatch: {path}")


def selftest() -> int:
    from ng_historical_inventory import build_manifest

    definitions = {
        "NGJ26": {
            "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 1008,
            "raw_symbol": "NGJ26", "definition_date": "2026-03-01",
            "definition_start_s": 0.0, "definition_end_s": 10_000.0,
            "observed_at": "2026-07-21T00:00:00Z",
        },
        "NGK26": {
            "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 996,
            "raw_symbol": "NGK26", "definition_date": "2026-03-20",
            "definition_start_s": 0.0, "definition_end_s": 10_000.0,
            "observed_at": "2026-07-21T00:00:00Z",
        },
    }
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        for index, day in enumerate(G15_DATES, 1):
            contract = G15_CONTRACT_MAP[day]
            definition_date = "2026-03-01" if contract["raw_symbol"] == "NGJ26" else "2026-03-20"
            identity = {
                "dataset": "GLBX.MDP3", "publisher_id": 1,
                "instrument_id": contract["instrument_id"], "raw_symbol": contract["raw_symbol"],
                "definition_date": definition_date, "session_day": day,
            }
            trade = {
                **identity, "ts_event_s": float(index * 10), "price": 3.0,
                "size": 1, "side": "B", "sequence": 1,
            }
            mbo = {
                **identity, "ts_event_s": float(index * 10), "action": "A", "side": "B",
                "price": 3.0, "size": 1, "order_id": index, "flags": 128, "sequence": 1,
            }
            (root / f"l1_{day}.jsonl").write_text(json.dumps(trade) + "\n", encoding="utf-8")
            (root / f"mbo_{day}.jsonl").write_text(json.dumps(mbo) + "\n", encoding="utf-8")
        manifest = build_manifest(
            l1_pattern=str(root / "l1_{day}.jsonl"),
            mbo_pattern=str(root / "mbo_{day}.jsonl"),
            publisher_id=1,
            definitions=definitions,
        )
        assert manifest["report"]["status"] == "READY"
        prepared_dir = root / "prepared"
        index = prepare_corpus(manifest, prepared_dir)
        validate_prepared_index(index)
        assert index["source_count"] == 26
        assert len(list(prepared_dir.glob("*.jsonl"))) == 26
    print("[ng_historical_prepare] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a READY G15 manifest for deterministic replay")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--index-out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.manifest or not args.output_dir or not args.index_out:
        parser.error("--manifest, --output-dir, and --index-out are required")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    index = prepare_corpus(manifest, args.output_dir)
    validate_prepared_index(index)
    _atomic_json(args.index_out, index)
    print(
        json.dumps(
            {
                "status": index["status"],
                "sources": index["source_count"],
                "output_dir": index["output_dir"],
                "fingerprint": index["prepared_corpus_fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
