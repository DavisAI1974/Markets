#!/usr/bin/env python3
"""Prepare and replay the exact-basis G16 historical L1 + MBO corpus.

This module is the G16 bridge between ``ng_g16_corpus_basis_gate.v1`` and the
shared live-causal feature path. It never invents AWS/S3 presence: every replay
lane must be an observed object with size and SHA-256 provenance, then must be
re-materialized and normalized before replay.

Replay uses the same ``NGLiveOperator`` and ``ng_rt_feature_state`` contracts as
live mode. States emit only on completed MBO event boundaries (F_LAST). G16
outcomes are unavailable here, the blind prior is immutable, CME event
contracts remain SHADOW, and no paid live-data assumption is made.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from ng_g16_corpus_basis_gate import (
    CANONICAL_DATES,
    DATASET,
    EXPECTED,
    INSTRUMENT_ID,
    RAW_SYMBOL,
    evaluate_manifest as evaluate_basis,
    validate_report as validate_basis_report,
)
from ng_historical_inventory import materialize
from ng_historical_normalize import normalize_file
from ng_historical_replay import (
    SourceContinuity,
    _event_key,
    _identity,
    merge_sorted_sources,
    read_jsonl,
    validate_normalized_event,
)
from ng_live_operator import F_LAST, NGLiveOperator
from ng_rt_feature_state import build_feature_state, validate_chronological

CATALOG_SCHEMA = "ng_g16_replay_source_catalog.v1"
MANIFEST_SCHEMA = "ng_g16_historical_manifest.v1"
PREPARED_SCHEMA = "ng_g16_prepared_corpus.v1"
REPLAY_SCHEMA = "ng_g16_historical_replay.v1"
SOURCE_KINDS = ("l1_trades", "mbo")
SOURCE_KIND_TO_EVENT = {"l1_trades": "trade", "mbo": "mbo"}
SOURCE_ORDER = {"definition": 0, "l1_trades": 1, "mbo": 2}


class G16HistoricalReplayError(ValueError):
    """Raised when exact G16 provenance or causal replay is invalid."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise G16HistoricalReplayError(f"invalid {name}: {value!r}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise G16HistoricalReplayError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(number):
        raise G16HistoricalReplayError(f"invalid {name}: {value!r}")
    return number


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise G16HistoricalReplayError(f"invalid {name}: {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise G16HistoricalReplayError(f"invalid {name}: {value!r}") from error
    if number <= 0:
        raise G16HistoricalReplayError(f"{name} must be positive")
    return number


def _inventory_rows(inventory: Any) -> dict[str, dict[str, Any]]:
    if isinstance(inventory, list):
        rows = inventory
    elif isinstance(inventory, Mapping):
        rows = inventory.get("rows")
        if rows is None:
            rows = inventory.get("entries")
    else:
        rows = None
    if not isinstance(rows, list):
        raise G16HistoricalReplayError("G16 inventory must contain rows/entries")
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise G16HistoricalReplayError("G16 inventory contains a non-object row")
        day = str(raw.get("date") or raw.get("day") or "").replace("-", "")
        if day not in EXPECTED:
            raise G16HistoricalReplayError(f"unexpected G16 inventory day: {day!r}")
        if day in result:
            raise G16HistoricalReplayError(f"duplicate G16 inventory day: {day}")
        result[day] = copy.deepcopy(raw)
    missing = sorted(set(CANONICAL_DATES) - set(result))
    if missing:
        raise G16HistoricalReplayError("G16 inventory missing days: " + ", ".join(missing))
    return result


def _inventory_range(row: Mapping[str, Any], source_kind: str) -> tuple[float, float]:
    if source_kind == "l1_trades":
        start = row.get("l1_first_event_s", row.get("l1_first_event_utc"))
        end = row.get("l1_last_event_s", row.get("l1_last_event_utc"))
    else:
        start = row.get("mbo_first_event_s", row.get("mbo_first_event_utc", row.get("first_event_utc")))
        end = row.get("mbo_last_event_s", row.get("mbo_last_event_utc", row.get("last_event_utc")))
    return _finite(start, f"{source_kind}.event_start"), _finite(end, f"{source_kind}.event_end")


def _expected_count(row: Mapping[str, Any], source_kind: str) -> int:
    field = "l1_n_trades" if source_kind == "l1_trades" else "n_mbo"
    return _positive_int(row.get(field), field)


def build_catalog_template(inventory: Any) -> dict[str, Any]:
    """Build a fail-closed UNKNOWN catalog; no object presence is inferred."""
    rows = _inventory_rows(inventory)
    basis = evaluate_basis(copy.deepcopy(inventory))
    validate_basis_report(basis)
    sources = []
    for day in CANONICAL_DATES:
        for source_kind in SOURCE_KINDS:
            sources.append(
                {
                    "day": day,
                    "source_kind": source_kind,
                    "status": "UNKNOWN",
                    "location": None,
                    "dataset": DATASET,
                    "publisher_id": rows[day].get("publisher_id"),
                    "instrument_id": INSTRUMENT_ID,
                    "raw_symbol": RAW_SYMBOL,
                    "definition_date": None,
                    "definition_start_s": None,
                    "definition_end_s": None,
                    "event_start_s": None,
                    "event_end_s": None,
                    "record_count": None,
                    "size_bytes": None,
                    "sha256": None,
                    "inventory_observed_at": None,
                    "basis_row_fingerprint": _sha(rows[day]),
                }
            )
    catalog = {
        "schema": CATALOG_SCHEMA,
        "market": "NG",
        "group": 16,
        "status": "UNKNOWN",
        "basis_inventory_fingerprint": _sha(inventory),
        "basis_report_fingerprint": basis["fingerprint"],
        "definition": None,
        "sources": sources,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_relabel_wrong_leg_l1": False,
        "may_change_g16_blind_prior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "note": "UNKNOWN is intentional until exact NGK26 objects and definition metadata are observed.",
    }
    catalog["fingerprint"] = _sha(catalog)
    return catalog


def _validate_definition(raw: Mapping[str, Any]) -> dict[str, Any]:
    definition = dict(raw)
    required = (
        "dataset", "publisher_id", "instrument_id", "raw_symbol", "definition_date",
        "definition_start_s", "definition_end_s", "observed_at",
    )
    missing = [name for name in required if definition.get(name) in (None, "")]
    if missing:
        raise G16HistoricalReplayError("NGK26 definition missing: " + ", ".join(missing))
    if definition["dataset"] != DATASET:
        raise G16HistoricalReplayError(f"definition dataset must be {DATASET}")
    _positive_int(definition["publisher_id"], "definition.publisher_id")
    if _positive_int(definition["instrument_id"], "definition.instrument_id") != INSTRUMENT_ID:
        raise G16HistoricalReplayError("definition instrument_id is not NGK26")
    if str(definition["raw_symbol"]) != RAW_SYMBOL:
        raise G16HistoricalReplayError("definition raw_symbol is not NGK26")
    start = _finite(definition["definition_start_s"], "definition_start_s")
    end = _finite(definition["definition_end_s"], "definition_end_s")
    if end < start:
        raise G16HistoricalReplayError("definition period moves backward")
    return {
        "dataset": DATASET,
        "publisher_id": int(definition["publisher_id"]),
        "instrument_id": INSTRUMENT_ID,
        "raw_symbol": RAW_SYMBOL,
        "definition_date": str(definition["definition_date"]),
        "definition_start_s": start,
        "definition_end_s": end,
        "observed_at": str(definition["observed_at"]),
        "source": definition.get("source"),
        "source_fingerprint": _sha(definition),
    }


def _validate_catalog(
    inventory: Any,
    catalog: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    rows = _inventory_rows(inventory)
    basis = evaluate_basis(copy.deepcopy(inventory))
    validate_basis_report(basis)
    if basis.get("status") != "MATCHED_L1_MBO_READY":
        raise G16HistoricalReplayError(
            f"G16 source preparation requires MATCHED_L1_MBO_READY; got {basis.get('status')}"
        )
    candidate = copy.deepcopy(catalog)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != CATALOG_SCHEMA:
        raise G16HistoricalReplayError("unexpected G16 source-catalog schema")
    if observed != _sha(candidate):
        raise G16HistoricalReplayError("G16 source-catalog fingerprint mismatch")
    if candidate.get("group") != 16 or candidate.get("market") != "NG":
        raise G16HistoricalReplayError("source catalog must describe G16 NG")
    if candidate.get("basis_inventory_fingerprint") != _sha(inventory):
        raise G16HistoricalReplayError("source catalog references a different G16 inventory")
    if candidate.get("basis_report_fingerprint") != basis.get("fingerprint"):
        raise G16HistoricalReplayError("source catalog references a different basis report")
    for field in (
        "actual_outcomes_used", "paid_live_data_assumed", "may_relabel_wrong_leg_l1",
        "may_change_g16_blind_prior", "may_update_ng_brain", "execution_authority",
    ):
        if candidate.get(field) is not False:
            raise G16HistoricalReplayError(f"source catalog must keep {field}=false")
    definition = _validate_definition(candidate.get("definition") or {})
    raw_sources = candidate.get("sources")
    if not isinstance(raw_sources, list):
        raise G16HistoricalReplayError("source catalog sources must be a list")
    sources: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise G16HistoricalReplayError("source catalog contains a non-object source")
        key = (str(raw.get("day") or ""), str(raw.get("source_kind") or ""))
        if key in sources:
            raise G16HistoricalReplayError(f"duplicate G16 source lane: {key[0]}:{key[1]}")
        sources[key] = copy.deepcopy(raw)
    expected = {(day, kind) for day in CANONICAL_DATES for kind in SOURCE_KINDS}
    if set(sources) != expected:
        raise G16HistoricalReplayError(
            f"G16 source lanes mismatch; missing={sorted(expected-set(sources))} extra={sorted(set(sources)-expected)}"
        )
    return candidate, basis, rows, sources


def build_manifest(inventory: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    """Bind exact-basis metadata to all 22 observed G16 replay lanes."""
    inventory_before = copy.deepcopy(inventory)
    catalog_before = copy.deepcopy(catalog)
    candidate, basis, rows, sources = _validate_catalog(inventory, catalog)
    definition = _validate_definition(candidate["definition"])
    entries: list[dict[str, Any]] = []
    for day in CANONICAL_DATES:
        day_entries = []
        for source_kind in SOURCE_KINDS:
            source = sources[(day, source_kind)]
            prefix = f"{day}:{source_kind}"
            if str(source.get("status") or "").upper() != "PRESENT":
                raise G16HistoricalReplayError(f"{prefix}: source is not observed PRESENT")
            if source.get("basis_row_fingerprint") != _sha(rows[day]):
                raise G16HistoricalReplayError(f"{prefix}: basis-row fingerprint mismatch")
            if source.get("dataset") != DATASET:
                raise G16HistoricalReplayError(f"{prefix}: dataset mismatch")
            if _positive_int(source.get("publisher_id"), f"{prefix}.publisher_id") != int(rows[day]["publisher_id"]):
                raise G16HistoricalReplayError(f"{prefix}: publisher differs from basis inventory")
            if _positive_int(source.get("instrument_id"), f"{prefix}.instrument_id") != INSTRUMENT_ID:
                raise G16HistoricalReplayError(f"{prefix}: wrong instrument_id")
            if str(source.get("raw_symbol") or "") != RAW_SYMBOL:
                raise G16HistoricalReplayError(f"{prefix}: wrong raw_symbol")
            if str(source.get("definition_date") or "") != definition["definition_date"]:
                raise G16HistoricalReplayError(f"{prefix}: definition_date mismatch")
            def_start = _finite(source.get("definition_start_s"), f"{prefix}.definition_start_s")
            def_end = _finite(source.get("definition_end_s"), f"{prefix}.definition_end_s")
            if def_start != definition["definition_start_s"] or def_end != definition["definition_end_s"]:
                raise G16HistoricalReplayError(f"{prefix}: definition period mismatch")
            event_start = _finite(source.get("event_start_s"), f"{prefix}.event_start_s")
            event_end = _finite(source.get("event_end_s"), f"{prefix}.event_end_s")
            if event_end < event_start or event_start < def_start or event_end > def_end:
                raise G16HistoricalReplayError(f"{prefix}: invalid event range")
            inv_start, inv_end = _inventory_range(rows[day], source_kind)
            if abs(event_start - inv_start) > 1e-6 or abs(event_end - inv_end) > 1e-6:
                raise G16HistoricalReplayError(f"{prefix}: event range differs from basis inventory")
            record_count = _positive_int(source.get("record_count"), f"{prefix}.record_count")
            if record_count != _expected_count(rows[day], source_kind):
                raise G16HistoricalReplayError(f"{prefix}: record_count differs from basis inventory")
            location = str(source.get("location") or "")
            sha256 = str(source.get("sha256") or "").lower()
            if not location or len(sha256) != 64 or any(ch not in "0123456789abcdef" for ch in sha256):
                raise G16HistoricalReplayError(f"{prefix}: observed location/SHA-256 is invalid")
            entry = {
                "day": day,
                "source_kind": source_kind,
                "status": "PRESENT",
                "location": location,
                "dataset": DATASET,
                "publisher_id": int(source["publisher_id"]),
                "instrument_id": INSTRUMENT_ID,
                "raw_symbol": RAW_SYMBOL,
                "definition_date": definition["definition_date"],
                "definition_start_s": def_start,
                "definition_end_s": def_end,
                "event_start_s": event_start,
                "event_end_s": event_end,
                "record_count": record_count,
                "size_bytes": _positive_int(source.get("size_bytes"), f"{prefix}.size_bytes"),
                "sha256": sha256,
                "inventory_observed_at": str(source.get("inventory_observed_at") or ""),
                "basis_row_fingerprint": _sha(rows[day]),
                "catalog_source_fingerprint": _sha(source),
            }
            if not entry["inventory_observed_at"]:
                raise G16HistoricalReplayError(f"{prefix}: inventory_observed_at is required")
            entries.append(entry)
            day_entries.append(entry)
        if min(row["event_end_s"] for row in day_entries) < max(row["event_start_s"] for row in day_entries):
            raise G16HistoricalReplayError(f"{day}: L1 and MBO event ranges do not overlap")
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "market": "NG",
        "group": 16,
        "status": "READY",
        "coverage": {"start": CANONICAL_DATES[0], "end": CANONICAL_DATES[-1]},
        "dataset": DATASET,
        "contract": RAW_SYMBOL,
        "instrument_id": INSTRUMENT_ID,
        "basis_status": basis["status"],
        "basis_inventory_fingerprint": _sha(inventory),
        "basis_report_fingerprint": basis["fingerprint"],
        "source_catalog_fingerprint": catalog["fingerprint"],
        "definition": definition,
        "entries": entries,
        "queue_stand_down_days": list(basis.get("queue_stand_down_days") or []),
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_change_g16_blind_prior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    manifest["fingerprint"] = _sha(manifest)
    validate_manifest(manifest)
    if inventory != inventory_before or catalog != catalog_before:
        raise G16HistoricalReplayError("manifest build mutated source artifacts")
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(manifest))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != MANIFEST_SCHEMA or candidate.get("status") != "READY":
        raise G16HistoricalReplayError("G16 historical manifest is not READY")
    if observed != _sha(candidate):
        raise G16HistoricalReplayError("G16 historical manifest fingerprint mismatch")
    if candidate.get("group") != 16 or candidate.get("contract") != RAW_SYMBOL:
        raise G16HistoricalReplayError("G16 historical manifest identity mismatch")
    for field in (
        "actual_outcomes_used", "paid_live_data_assumed", "may_change_g16_blind_prior",
        "may_update_ng_brain", "execution_authority",
    ):
        if candidate.get(field) is not False:
            raise G16HistoricalReplayError(f"manifest must keep {field}=false")
    definition = _validate_definition(candidate.get("definition") or {})
    entries = candidate.get("entries")
    if not isinstance(entries, list):
        raise G16HistoricalReplayError("manifest entries must be a list")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise G16HistoricalReplayError("manifest contains a non-object entry")
        key = (str(raw.get("day") or ""), str(raw.get("source_kind") or ""))
        if key in by_key:
            raise G16HistoricalReplayError(f"duplicate manifest lane: {key}")
        by_key[key] = raw
    expected = {(day, kind) for day in CANONICAL_DATES for kind in SOURCE_KINDS}
    if set(by_key) != expected:
        raise G16HistoricalReplayError("manifest does not contain the canonical 22 lanes")
    coverage = []
    for day in CANONICAL_DATES:
        pair = [by_key[(day, kind)] for kind in SOURCE_KINDS]
        for entry in pair:
            if entry.get("status") != "PRESENT":
                raise G16HistoricalReplayError(f"{day}: non-PRESENT manifest lane")
            if entry.get("dataset") != DATASET or int(entry.get("instrument_id") or 0) != INSTRUMENT_ID:
                raise G16HistoricalReplayError(f"{day}: manifest lane identity mismatch")
            if entry.get("raw_symbol") != RAW_SYMBOL or entry.get("definition_date") != definition["definition_date"]:
                raise G16HistoricalReplayError(f"{day}: manifest definition identity mismatch")
        overlap_start = max(float(row["event_start_s"]) for row in pair)
        overlap_end = min(float(row["event_end_s"]) for row in pair)
        if overlap_end < overlap_start:
            raise G16HistoricalReplayError(f"{day}: manifest source ranges do not overlap")
        coverage.append({"day": day, "overlap_start_s": overlap_start, "overlap_end_s": overlap_end})
    return {
        "schema": "ng_g16_historical_manifest_report.v1",
        "group": 16,
        "status": "READY",
        "ready_days": list(CANONICAL_DATES),
        "source_coverage": coverage,
        "queue_stand_down_days": list(candidate.get("queue_stand_down_days") or []),
        "can_replay_all_g16": True,
        "execution_authority": False,
    }


def _verify_raw(path: Path, entry: Mapping[str, Any]) -> None:
    if path.stat().st_size != int(entry["size_bytes"]):
        raise G16HistoricalReplayError(f"{entry['day']}:{entry['source_kind']}: raw size changed")
    if _sha256(path) != entry["sha256"]:
        raise G16HistoricalReplayError(f"{entry['day']}:{entry['source_kind']}: raw SHA-256 changed")


def prepare_corpus(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Re-materialize and normalize all 22 lanes plus one observed definition."""
    report = validate_manifest(manifest)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise G16HistoricalReplayError(f"prepared output already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    entries = {(row["day"], row["source_kind"]): row for row in manifest["entries"]}
    stage: Path | None = Path(tempfile.mkdtemp(prefix="g16_prepare_", dir=str(output_dir.parent)))
    sources: list[dict[str, Any]] = []
    try:
        definition = manifest["definition"]
        definition_event = {
            "schema": "ng_normalized_event.v1",
            "event_type": "definition",
            "dataset": DATASET,
            "publisher_id": int(definition["publisher_id"]),
            "instrument_id": INSTRUMENT_ID,
            "raw_symbol": RAW_SYMBOL,
            "definition_date": definition["definition_date"],
            "session_day": CANONICAL_DATES[0],
            "ts_event_s": float(definition["definition_start_s"]),
            "source_sequence": 1,
            "ingest_sequence": 1,
            "source_id": f"observed-definition:{RAW_SYMBOL}:{definition['observed_at']}",
        }
        definition_path = stage / f"definition_{RAW_SYMBOL}.jsonl"
        definition_path.write_text(_canonical(definition_event) + "\n", encoding="utf-8")
        sources.append(
            {
                "day": CANONICAL_DATES[0],
                "source_kind": "definition",
                "event_type": "definition",
                "path": str(output_dir / definition_path.name),
                "record_count": 1,
                "event_start_s": definition_event["ts_event_s"],
                "event_end_s": definition_event["ts_event_s"],
                "size_bytes": definition_path.stat().st_size,
                "sha256": _sha256(definition_path),
            }
        )
        for day in CANONICAL_DATES:
            for source_kind in SOURCE_KINDS:
                entry = entries[(day, source_kind)]
                with materialize(str(entry["location"])) as (raw_path, observation, metadata):
                    if observation != "OBSERVED" or raw_path is None:
                        raise G16HistoricalReplayError(
                            f"{day}:{source_kind}: raw object unavailable ({observation}): "
                            f"{metadata.get('observation_error')}"
                        )
                    _verify_raw(raw_path, entry)
                    name = f"{day}_{source_kind}.jsonl"
                    staged = stage / name
                    normalized = normalize_file(
                        raw_path,
                        kind=SOURCE_KIND_TO_EVENT[source_kind],
                        dataset=DATASET,
                        publisher_id=int(entry["publisher_id"]),
                        instrument_id=INSTRUMENT_ID,
                        raw_symbol=RAW_SYMBOL,
                        definition_date=str(entry["definition_date"]),
                        session_day=day,
                        output=staged,
                        skip_nonmatching=source_kind == "l1_trades",
                    )
                    if int(normalized["record_count"]) != int(entry["record_count"]):
                        raise G16HistoricalReplayError(f"{day}:{source_kind}: normalized count changed")
                    if abs(float(normalized["event_start_s"]) - float(entry["event_start_s"])) > 1e-9:
                        raise G16HistoricalReplayError(f"{day}:{source_kind}: normalized start changed")
                    if abs(float(normalized["event_end_s"]) - float(entry["event_end_s"])) > 1e-9:
                        raise G16HistoricalReplayError(f"{day}:{source_kind}: normalized end changed")
                    sources.append(
                        {
                            "day": day,
                            "source_kind": source_kind,
                            "event_type": SOURCE_KIND_TO_EVENT[source_kind],
                            "path": str(output_dir / name),
                            "record_count": normalized["record_count"],
                            "event_start_s": normalized["event_start_s"],
                            "event_end_s": normalized["event_end_s"],
                            "size_bytes": normalized["size_bytes"],
                            "sha256": normalized["sha256"],
                            "raw_location": entry["location"],
                            "raw_size_bytes": entry["size_bytes"],
                            "raw_sha256": entry["sha256"],
                            "manifest_entry_fingerprint": _sha(entry),
                        }
                    )
        sources.sort(
            key=lambda row: (
                str(row.get("day") or ""),
                SOURCE_ORDER.get(str(row.get("source_kind") or ""), 99),
                str(row.get("path") or ""),
            )
        )
        index = {
            "schema": PREPARED_SCHEMA,
            "market": "NG",
            "group": 16,
            "status": "READY",
            "authority": "HISTORICAL_REPLAY_INPUT_ONLY",
            "manifest_fingerprint": manifest["fingerprint"],
            "manifest_report": report,
            "output_dir": str(output_dir),
            "source_count": len(sources),
            "sources": sources,
            "actual_outcomes_used": False,
            "paid_live_data_assumed": False,
            "may_change_g16_blind_prior": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
        }
        index["prepared_corpus_fingerprint"] = _sha(index)
        os.replace(stage, output_dir)
        stage = None
        validate_prepared_index(index)
        return index
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def validate_prepared_index(index: Mapping[str, Any], *, verify_files: bool = True) -> None:
    candidate = copy.deepcopy(dict(index))
    observed = candidate.pop("prepared_corpus_fingerprint", None)
    if candidate.get("schema") != PREPARED_SCHEMA or candidate.get("status") != "READY":
        raise G16HistoricalReplayError("G16 prepared index is not READY")
    if observed != _sha(candidate):
        raise G16HistoricalReplayError("G16 prepared index fingerprint mismatch")
    if candidate.get("group") != 16 or int(candidate.get("source_count") or 0) != 23:
        raise G16HistoricalReplayError("G16 prepared index must contain 23 sources")
    for field in (
        "actual_outcomes_used", "paid_live_data_assumed", "may_change_g16_blind_prior",
        "may_update_ng_brain", "execution_authority",
    ):
        if candidate.get(field) is not False:
            raise G16HistoricalReplayError(f"prepared index must keep {field}=false")
    sources = candidate.get("sources")
    if not isinstance(sources, list):
        raise G16HistoricalReplayError("prepared sources must be a list")
    keys = [(str(row.get("day") or ""), str(row.get("source_kind") or "")) for row in sources]
    expected = [(CANONICAL_DATES[0], "definition")] + [
        (day, kind) for day in CANONICAL_DATES for kind in SOURCE_KINDS
    ]
    if sorted(keys) != sorted(expected):
        raise G16HistoricalReplayError("prepared source lane set is not canonical")
    if verify_files:
        for source in sources:
            path = Path(source["path"])
            if not path.is_file():
                raise G16HistoricalReplayError(f"prepared source missing: {path}")
            if path.stat().st_size != int(source["size_bytes"]) or _sha256(path) != source["sha256"]:
                raise G16HistoricalReplayError(f"prepared source changed: {path}")


def _manifest_identity_by_day(manifest: Mapping[str, Any]) -> dict[str, tuple[Any, ...]]:
    result = {}
    for entry in manifest.get("entries") or []:
        if entry.get("source_kind") != "l1_trades":
            continue
        result[str(entry["day"])] = (
            str(entry["dataset"]),
            entry["publisher_id"],
            int(entry["instrument_id"]),
            str(entry["raw_symbol"]),
            str(entry["definition_date"]),
        )
    return result


def _replay_events(
    events: Iterable[dict[str, Any]],
    *,
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
) -> dict[str, Any]:
    manifest_report = validate_manifest(manifest)
    expected_identity = _manifest_identity_by_day(manifest)
    prior_before = copy.deepcopy(blind_prior)
    prior_hash = _sha(prior_before)
    operators: dict[tuple[Any, ...], NGLiveOperator] = {}
    stream_states: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    stream_sequences: dict[tuple[Any, ...], int] = {}
    continuity = SourceContinuity()
    definition_seen: set[tuple[Any, ...]] = set()
    processed = {"trade": 0, "mbo": 0, "definition": 0}
    complete_boundaries = 0
    last_key = None

    for raw_event in events:
        event = validate_normalized_event(copy.deepcopy(raw_event))
        key = _event_key(event)
        if last_key is not None and key < last_key:
            raise G16HistoricalReplayError("merged G16 replay moved backward")
        last_key = key
        continuity.observe(event)
        identity = _identity(event)
        day = str(event.get("session_day") or "")
        if day not in EXPECTED:
            raise G16HistoricalReplayError(f"{day!r}: event is outside canonical G16")
        if (identity[2], identity[3]) != (INSTRUMENT_ID, RAW_SYMBOL):
            raise G16HistoricalReplayError(f"{day}: wrong G16 contract identity")
        if identity != expected_identity.get(day):
            raise G16HistoricalReplayError(f"{day}: event identity differs from manifest")
        event_type = str(event["event_type"])
        processed[event_type] += 1
        if event_type == "definition":
            definition_seen.add(identity)
            continue
        operator = operators.setdefault(identity, NGLiveOperator())
        stream_states.setdefault(identity, [])
        if event_type == "trade":
            operator.on_trade(
                float(event["ts_event_s"]), float(event["price"]), float(event["size"]), event["side"]
            )
            continue
        operator.on_mbo(
            float(event["ts_event_s"]), event["action"], event["side"], float(event["size"]),
            int(event["order_id"]), None if event.get("price") is None else float(event["price"]),
            int(event["flags"]),
        )
        if not (int(event["flags"]) & int(F_LAST)):
            continue
        complete_boundaries += 1
        stream_sequences[identity] = stream_sequences.get(identity, 0) + 1
        quality = continuity.quality(identity)
        quality["definition_verified_by_stream"] = identity in definition_seen
        quality["definition_verified_by_manifest"] = True
        snapshot = operator.snapshot(float(event["ts_event_s"]))
        if day in set(manifest_report.get("queue_stand_down_days") or []):
            data_quality = dict(snapshot.get("data_quality") or {})
            mapping_flags = list(data_quality.get("mapping_flags") or [])
            if "inventory_queue_stand_down" not in mapping_flags:
                mapping_flags.append("inventory_queue_stand_down")
            data_quality["mapping_flags"] = mapping_flags
            snapshot["data_quality"] = data_quality
        state = build_feature_state(
            blind_prior=prior_before,
            operator_snapshot=snapshot,
            instrument_identity={
                "dataset": identity[0],
                "publisher_id": identity[1],
                "instrument_id": identity[2],
                "raw_symbol": identity[3],
                "definition_date": identity[4],
                "continuous_symbol": "NG.v.0",
                "roll_rule": "single_exact_contract_no_roll",
            },
            decision_cutoff_s=float(event["ts_event_s"]),
            horizon="close",
            source_mode="historical_replay",
            sequence=stream_sequences[identity],
            collector_quality=quality,
        )
        state["session_day"] = day
        state["completed_mbo_event_boundary"] = True
        stream_states[identity].append(state)

    for states in stream_states.values():
        validate_chronological(states)
    if blind_prior != prior_before or _sha(blind_prior) != prior_hash:
        raise G16HistoricalReplayError("G16 blind prior was mutated")
    all_states = [state for states in stream_states.values() for state in states]
    days_with_states = sorted({str(state.get("session_day") or "") for state in all_states})
    if days_with_states != sorted(CANONICAL_DATES):
        raise G16HistoricalReplayError(
            f"G16 replay missing completed session states: {sorted(set(CANONICAL_DATES)-set(days_with_states))}"
        )
    stand_down_days = sorted(
        {
            str(state.get("session_day") or "")
            for state in all_states
            if list((state.get("availability") or {}).get("stand_down_reasons") or [])
        }
    )
    streams = [
        {
            "instrument": {
                "dataset": identity[0],
                "publisher_id": identity[1],
                "instrument_id": identity[2],
                "raw_symbol": identity[3],
                "definition_date": identity[4],
            },
            "n_states": len(stream_states[identity]),
            "states": stream_states[identity],
        }
        for identity in sorted(stream_states, key=lambda row: (row[2], row[3], row[4]))
    ]
    return {
        "schema": REPLAY_SCHEMA,
        "market": "NG",
        "group": 16,
        "status": "READY_WITH_STAND_DOWNS" if stand_down_days else "READY",
        "authority": "HISTORICAL_REFINE_REPLAY_ONLY",
        "execution_authority": False,
        "blind_prior_fingerprint": prior_hash,
        "manifest_fingerprint": manifest["fingerprint"],
        "manifest_report": manifest_report,
        "processed_records": processed,
        "completed_mbo_event_boundaries": complete_boundaries,
        "sequence_gaps": continuity.sequence_gaps,
        "duplicate_records": continuity.duplicates,
        "queue_stand_down_days": manifest_report["queue_stand_down_days"],
        "stand_down_days": stand_down_days,
        "streams": streams,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_change_g16_blind_prior": False,
        "may_update_ng_brain": False,
        "note": "States emit only on F_LAST through NGLiveOperator and ng_rt_feature_state.",
    }


def replay_prepared(
    prepared_index: dict[str, Any],
    manifest: dict[str, Any],
    blind_prior: dict[str, Any],
) -> dict[str, Any]:
    validate_prepared_index(prepared_index)
    validate_manifest(manifest)
    if prepared_index.get("manifest_fingerprint") != manifest.get("fingerprint"):
        raise G16HistoricalReplayError("prepared index references a different G16 manifest")
    sources = sorted(
        prepared_index["sources"],
        key=lambda row: (
            str(row.get("day") or ""),
            SOURCE_ORDER.get(str(row.get("source_kind") or ""), 99),
            str(row.get("path") or ""),
        ),
    )
    iterables = [read_jsonl(Path(source["path"])) for source in sources]
    result = _replay_events(
        merge_sorted_sources(iterables),
        manifest=manifest,
        blind_prior=blind_prior,
    )
    result["prepared_corpus_fingerprint"] = prepared_index["prepared_corpus_fingerprint"]
    result["source_count"] = prepared_index["source_count"]
    result["fingerprint"] = _sha(result)
    validate_replay_output(result)
    return result


def validate_replay_output(output: Mapping[str, Any]) -> None:
    candidate = copy.deepcopy(dict(output))
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != REPLAY_SCHEMA or candidate.get("group") != 16:
        raise G16HistoricalReplayError("unexpected G16 replay output")
    if observed != _sha(candidate):
        raise G16HistoricalReplayError("G16 replay output fingerprint mismatch")
    if candidate.get("status") not in {"READY", "READY_WITH_STAND_DOWNS"}:
        raise G16HistoricalReplayError("G16 replay output is not ready")
    for field in (
        "actual_outcomes_used", "paid_live_data_assumed", "may_change_g16_blind_prior",
        "may_update_ng_brain", "execution_authority",
    ):
        if candidate.get(field) is not False:
            raise G16HistoricalReplayError(f"replay output must keep {field}=false")
    if candidate.get("duplicate_records"):
        raise G16HistoricalReplayError("duplicate records are not publication-ready")
    queue_days = set(candidate.get("queue_stand_down_days") or [])
    visible_days = set(candidate.get("stand_down_days") or [])
    if not queue_days.issubset(visible_days):
        raise G16HistoricalReplayError("basis-level queue stand-downs are not visible in replay states")
    states = [
        state
        for stream in candidate.get("streams") or []
        for state in stream.get("states") or []
    ]
    if sorted({str(state.get("session_day") or "") for state in states}) != sorted(CANONICAL_DATES):
        raise G16HistoricalReplayError("replay output lacks canonical G16 state coverage")
    for state in states:
        if state.get("completed_mbo_event_boundary") is not True:
            raise G16HistoricalReplayError("G16 state was not emitted on a completed MBO boundary")
        identity = state.get("instrument_identity") or state.get("instrument") or {}
        if identity and (
            int(identity.get("instrument_id") or 0) != INSTRUMENT_ID
            or identity.get("raw_symbol") != RAW_SYMBOL
        ):
            raise G16HistoricalReplayError("G16 state identity changed")


def _fixture_inventory(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    definition_start = 1_700_000_000.0
    definition_end = 1_900_000_000.0
    for index, day in enumerate(CANONICAL_DATES):
        base = 1_774_000_000.0 + index * 100_000.0
        trade_path = root / f"{day}_trades.jsonl"
        mbo_path = root / f"{day}_mbo.jsonl"
        trade_rows = []
        for seq, offset in enumerate((1, 2, 3, 4, 5, 20), 1):
            trade_rows.append(
                {"ts_event_s": base + offset, "price": 3.0 + seq * 0.001, "size": 1, "side": "B",
                 "source_sequence": seq}
            )
        mbo_rows = [
            {"ts_event_s": base + 20, "action": "A", "side": "B", "size": 10,
             "order_id": index + 1, "price": 3.0, "flags": int(F_LAST), "source_sequence": 1}
        ]
        trade_path.write_text("\n".join(_canonical(row) for row in trade_rows) + "\n", encoding="utf-8")
        mbo_path.write_text("\n".join(_canonical(row) for row in mbo_rows) + "\n", encoding="utf-8")
        rows.append(
            {
                "date": day,
                "status": "PRESENT",
                "dataset": DATASET,
                "publisher_id": 1,
                "contract": RAW_SYMBOL,
                "expected_instrument_id": INSTRUMENT_ID,
                "instrument_id": INSTRUMENT_ID,
                "raw_symbol": RAW_SYMBOL,
                "definition_start_s": definition_start,
                "definition_end_s": definition_end,
                "mbo_definition_start_s": definition_start,
                "mbo_definition_end_s": definition_end,
                "mbo_present": True,
                "mbo_bytes": mbo_path.stat().st_size,
                "n_mbo": 1,
                "n_trades": 6,
                "mbo_first_event_s": base + 20,
                "mbo_last_event_s": base + 20,
                "first_event_utc": base + 20,
                "last_event_utc": base + 20,
                "mbo_basis_correct": True,
                "chronological_ok": True,
                "flow_usable": True,
                "queue_usable": True,
                "l1_present": True,
                "l1_readable": True,
                "l1_bytes": trade_path.stat().st_size,
                "l1_n_rows": 6,
                "l1_n_trades": 6,
                "l1_instrument_id": [INSTRUMENT_ID],
                "l1_raw_symbol": RAW_SYMBOL,
                "l1_definition_start_s": definition_start,
                "l1_definition_end_s": definition_end,
                "l1_first_event_s": base + 1,
                "l1_last_event_s": base + 20,
                "l1_basis_correct": True,
                "_fixture_paths": {
                    "l1_trades": str(trade_path),
                    "mbo": str(mbo_path),
                },
            }
        )
    definition = {
        "dataset": DATASET,
        "publisher_id": 1,
        "instrument_id": INSTRUMENT_ID,
        "raw_symbol": RAW_SYMBOL,
        "definition_date": "2026-03-20",
        "definition_start_s": definition_start,
        "definition_end_s": definition_end,
        "observed_at": "2026-07-22T00:00:00Z",
        "source": "fixture",
    }
    return rows, definition


def _fixture_catalog(inventory: list[dict[str, Any]], definition: dict[str, Any]) -> dict[str, Any]:
    catalog = build_catalog_template(inventory)
    catalog["status"] = "PRESENT"
    catalog["definition"] = definition
    rows = _inventory_rows(inventory)
    for source in catalog["sources"]:
        day = source["day"]
        kind = source["source_kind"]
        path = Path(rows[day]["_fixture_paths"][kind])
        start, end = _inventory_range(rows[day], kind)
        source.update(
            status="PRESENT",
            location=str(path),
            dataset=DATASET,
            publisher_id=1,
            instrument_id=INSTRUMENT_ID,
            raw_symbol=RAW_SYMBOL,
            definition_date=definition["definition_date"],
            definition_start_s=definition["definition_start_s"],
            definition_end_s=definition["definition_end_s"],
            event_start_s=start,
            event_end_s=end,
            record_count=_expected_count(rows[day], kind),
            size_bytes=path.stat().st_size,
            sha256=_sha256(path),
            inventory_observed_at="2026-07-22T00:00:00Z",
        )
    catalog.pop("fingerprint", None)
    catalog["fingerprint"] = _sha(catalog)
    return catalog


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        inventory, definition = _fixture_inventory(root)
        catalog = _fixture_catalog(inventory, definition)
        manifest = build_manifest(inventory, catalog)
        prepared = prepare_corpus(manifest, root / "prepared")
        prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        result = replay_prepared(prepared, manifest, prior)
        assert result["processed_records"]["trade"] == len(CANONICAL_DATES) * 6
        assert result["completed_mbo_event_boundaries"] == len(CANONICAL_DATES)
        assert prior == {"up": 0.4, "flat": 0.2, "down": 0.4}
    print("[ng_g16_historical_replay] selftest PASS")
    return 0


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and replay exact-basis G16 historical L1 + MBO")
    parser.add_argument("--selftest", action="store_true")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init-catalog")
    init.add_argument("--inventory", type=Path, required=True)
    init.add_argument("--out", type=Path, required=True)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--inventory", type=Path, required=True)
    prepare.add_argument("--catalog", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--manifest-out", type=Path, required=True)
    prepare.add_argument("--index-out", type=Path, required=True)

    replay = sub.add_parser("replay")
    replay.add_argument("--manifest", type=Path, required=True)
    replay.add_argument("--prepared-index", type=Path, required=True)
    replay.add_argument("--blind-prior", type=Path, required=True)
    replay.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.command == "init-catalog":
        _atomic_json(args.out, build_catalog_template(_load(args.inventory)))
        return 0
    if args.command == "prepare":
        inventory = _load(args.inventory)
        catalog = _load(args.catalog)
        manifest = build_manifest(inventory, catalog)
        prepared = prepare_corpus(manifest, args.output_dir)
        _atomic_json(args.manifest_out, manifest)
        _atomic_json(args.index_out, prepared)
        return 0
    if args.command == "replay":
        result = replay_prepared(
            _load(args.prepared_index),
            _load(args.manifest),
            _load(args.blind_prior),
        )
        _atomic_json(args.out, result)
        return 0
    parser.error("choose init-catalog, prepare, replay, or --selftest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
