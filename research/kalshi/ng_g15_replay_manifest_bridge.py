#!/usr/bin/env python3
"""Bridge the promoted exact-basis G15 inventory into the canonical replay manifest.

The live G15 corpus audit and the deterministic replay stack intentionally use two
separate contracts:

* ``ng_g15_corpus_basis_gate.v1`` proves that each session has the correct
  NGJ26/NGK26 L1 and MBO basis; and
* ``ng_historical_manifest.v1`` names the exact observed source objects that may
  be materialized, normalized, and replayed.

This bridge joins those contracts without inventing remote presence. A source
catalog must contain exact object provenance (location, size, SHA-256, identity,
definition period, and event-time coverage) for all 24 replay lanes. The bridge
refuses wrong-basis or incomplete inventory, verifies the catalog against every
basis row, and emits a canonical manifest only when the downstream manifest
validator reports ``READY``.

The Friday 2026-03-13 anchor remains an input to the basis gate but is deliberately
excluded from the 12-session replay manifest. It is handled separately by
``ng_g15_anchor.py``. No outcomes are read; no blind forecast, posterior, brain,
or execution authority can be changed here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ng_g15_corpus_basis_gate import EXPECTED, evaluate_manifest, validate_report
from ng_historical_manifest import (
    DATASET,
    G15_CONTRACT_MAP,
    G15_DATES,
    SCHEMA as MANIFEST_SCHEMA,
    SOURCE_KINDS,
    validate_manifest,
)

CATALOG_SCHEMA = "ng_g15_replay_source_catalog.v1"
BRIDGE_SCHEMA = "ng_g15_replay_manifest_bridge.v1"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReplayManifestBridgeError(ValueError):
    """Raised when exact-basis inventory cannot be joined to observed sources."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ReplayManifestBridgeError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(number):
        raise ReplayManifestBridgeError(f"invalid {name}: {value!r}")
    return number


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ReplayManifestBridgeError(f"invalid {name}: {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ReplayManifestBridgeError(f"invalid {name}: {value!r}") from error
    if number <= 0:
        raise ReplayManifestBridgeError(f"{name} must be positive")
    return number


def _parse_time(value: Any, name: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _finite(value, name)
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ReplayManifestBridgeError(f"{name} is required")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError as error:
        raise ReplayManifestBridgeError(f"invalid {name}: {value!r}") from error


def _inventory_rows(inventory: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not isinstance(inventory, list):
        raise ReplayManifestBridgeError("G15 basis inventory must be a list")
    result: dict[str, dict[str, Any]] = {}
    for raw in inventory:
        if not isinstance(raw, dict):
            raise ReplayManifestBridgeError("G15 basis inventory contains a non-object row")
        day = str(raw.get("date") or "").replace("-", "")
        if day not in EXPECTED:
            raise ReplayManifestBridgeError(f"unexpected G15 basis date: {day!r}")
        if day in result:
            raise ReplayManifestBridgeError(f"duplicate G15 basis date: {day}")
        result[day] = copy.deepcopy(raw)
    missing = sorted(set(EXPECTED) - set(result))
    if missing:
        raise ReplayManifestBridgeError("basis inventory is missing dates: " + ", ".join(missing))
    return result


def _validate_definition(symbol: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    expected_id = 1008 if symbol == "NGJ26" else 996
    candidate = dict(raw)
    if candidate.get("dataset") != DATASET:
        raise ReplayManifestBridgeError(f"{symbol} definition dataset must be {DATASET}")
    if str(candidate.get("raw_symbol") or "") != symbol:
        raise ReplayManifestBridgeError(f"{symbol} definition raw_symbol mismatch")
    publisher_id = _positive_int(candidate.get("publisher_id"), f"{symbol}.publisher_id")
    if _positive_int(candidate.get("instrument_id"), f"{symbol}.instrument_id") != expected_id:
        raise ReplayManifestBridgeError(f"{symbol} definition instrument_id mismatch")
    definition_date = str(candidate.get("definition_date") or "")
    if not definition_date:
        raise ReplayManifestBridgeError(f"{symbol} definition_date is required")
    start = _finite(candidate.get("definition_start_s"), f"{symbol}.definition_start_s")
    end = _finite(candidate.get("definition_end_s"), f"{symbol}.definition_end_s")
    if end < start:
        raise ReplayManifestBridgeError(f"{symbol} definition validity moves backward")
    observed_at = str(candidate.get("observed_at") or "")
    if not observed_at:
        raise ReplayManifestBridgeError(f"{symbol} observed_at is required")
    return {
        "dataset": DATASET,
        "publisher_id": publisher_id,
        "instrument_id": expected_id,
        "raw_symbol": symbol,
        "definition_date": definition_date,
        "definition_start_s": start,
        "definition_end_s": end,
        "observed_at": observed_at,
        "source": candidate.get("source"),
        "source_fingerprint": _sha(candidate),
    }


def build_catalog_template(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    """Return an UNKNOWN source template; it never asserts an object exists."""
    rows = _inventory_rows(inventory)
    basis_report = evaluate_manifest(copy.deepcopy(inventory))
    validate_report(basis_report)
    sources = []
    for day in G15_DATES:
        expected = G15_CONTRACT_MAP[day]
        basis_row = rows[day]
        for source_kind in SOURCE_KINDS:
            sources.append(
                {
                    "day": day,
                    "source_kind": source_kind,
                    "status": "UNKNOWN",
                    "location": None,
                    "dataset": DATASET,
                    "publisher_id": basis_row.get("publisher_id"),
                    "instrument_id": expected["instrument_id"],
                    "raw_symbol": expected["raw_symbol"],
                    "definition_date": None,
                    "definition_start_s": None,
                    "definition_end_s": None,
                    "event_start_s": None,
                    "event_end_s": None,
                    "record_count": None,
                    "size_bytes": None,
                    "sha256": None,
                    "inventory_observed_at": None,
                    "basis_row_fingerprint": _sha(basis_row),
                }
            )
    catalog = {
        "schema": CATALOG_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": "UNKNOWN",
        "basis_inventory_fingerprint": _sha(inventory),
        "basis_report_fingerprint": basis_report["fingerprint"],
        "definitions": {"NGJ26": None, "NGK26": None},
        "sources": sources,
        "actual_outcomes_used": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "note": "UNKNOWN is intentional until exact objects and definitions are observed.",
    }
    catalog["fingerprint"] = _sha(catalog)
    return catalog


def _validate_catalog_envelope(
    catalog: dict[str, Any],
    *,
    inventory: list[dict[str, Any]],
    basis_report: dict[str, Any],
) -> dict[str, Any]:
    candidate = copy.deepcopy(catalog)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != CATALOG_SCHEMA:
        raise ReplayManifestBridgeError("unexpected G15 replay source-catalog schema")
    if observed != _sha(candidate):
        raise ReplayManifestBridgeError("G15 replay source-catalog fingerprint mismatch")
    if candidate.get("group") != 15 or candidate.get("market") != "NG":
        raise ReplayManifestBridgeError("source catalog must describe G15 NG")
    if candidate.get("basis_inventory_fingerprint") != _sha(inventory):
        raise ReplayManifestBridgeError("source catalog references a different basis inventory")
    if candidate.get("basis_report_fingerprint") != basis_report.get("fingerprint"):
        raise ReplayManifestBridgeError("source catalog references a different basis report")
    for name in (
        "actual_outcomes_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
    ):
        if candidate.get(name) is not False:
            raise ReplayManifestBridgeError(f"source catalog must keep {name}=false")
    return candidate


def _catalog_sources(catalog: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    sources = catalog.get("sources")
    if not isinstance(sources, list):
        raise ReplayManifestBridgeError("source catalog sources must be a list")
    for raw in sources:
        if not isinstance(raw, dict):
            raise ReplayManifestBridgeError("source catalog contains a non-object source")
        key = (str(raw.get("day") or ""), str(raw.get("source_kind") or ""))
        if key in result:
            raise ReplayManifestBridgeError(f"duplicate source catalog lane: {key[0]}:{key[1]}")
        result[key] = copy.deepcopy(raw)
    expected = {(day, kind) for day in G15_DATES for kind in SOURCE_KINDS}
    missing = sorted(expected - set(result))
    extra = sorted(set(result) - expected)
    if missing or extra:
        raise ReplayManifestBridgeError(f"source catalog lane mismatch; missing={missing} extra={extra}")
    return result


def _expected_inventory_count(row: Mapping[str, Any], source_kind: str) -> int:
    field = "l1_n_trades" if source_kind == "l1_trades" else "n_mbo"
    return _positive_int(row.get(field), field)


def _inventory_event_range(row: Mapping[str, Any], source_kind: str) -> tuple[float | None, float | None]:
    prefix = "l1" if source_kind == "l1_trades" else "mbo"
    explicit_start = row.get(f"{prefix}_first_event_s") or row.get(f"{prefix}_first_event_utc")
    explicit_end = row.get(f"{prefix}_last_event_s") or row.get(f"{prefix}_last_event_utc")
    if explicit_start not in (None, "") and explicit_end not in (None, ""):
        return _parse_time(explicit_start, f"{prefix}_first_event"), _parse_time(explicit_end, f"{prefix}_last_event")
    if source_kind == "mbo":
        return (
            _parse_time(row.get("first_event_utc"), "first_event_utc"),
            _parse_time(row.get("last_event_utc"), "last_event_utc"),
        )
    return None, None


def _validate_source(
    source: dict[str, Any],
    *,
    day: str,
    source_kind: str,
    basis_row: Mapping[str, Any],
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    expected = G15_CONTRACT_MAP[day]
    prefix = f"{day}:{source_kind}"
    if str(source.get("status") or "").upper() != "PRESENT":
        raise ReplayManifestBridgeError(f"{prefix}: source is not observed PRESENT")
    if source.get("basis_row_fingerprint") != _sha(basis_row):
        raise ReplayManifestBridgeError(f"{prefix}: basis-row fingerprint mismatch")
    if source.get("dataset") != DATASET:
        raise ReplayManifestBridgeError(f"{prefix}: dataset must be {DATASET}")
    if _positive_int(source.get("publisher_id"), f"{prefix}.publisher_id") != int(basis_row["publisher_id"]):
        raise ReplayManifestBridgeError(f"{prefix}: publisher differs from basis inventory")
    if _positive_int(source.get("instrument_id"), f"{prefix}.instrument_id") != expected["instrument_id"]:
        raise ReplayManifestBridgeError(f"{prefix}: wrong instrument_id")
    if str(source.get("raw_symbol") or "") != expected["raw_symbol"]:
        raise ReplayManifestBridgeError(f"{prefix}: wrong raw_symbol")
    if str(source.get("definition_date") or "") != definition["definition_date"]:
        raise ReplayManifestBridgeError(f"{prefix}: definition_date mismatch")
    definition_start = _finite(source.get("definition_start_s"), f"{prefix}.definition_start_s")
    definition_end = _finite(source.get("definition_end_s"), f"{prefix}.definition_end_s")
    if definition_start != float(definition["definition_start_s"]) or definition_end != float(definition["definition_end_s"]):
        raise ReplayManifestBridgeError(f"{prefix}: definition period differs from observed definition")
    event_start = _finite(source.get("event_start_s"), f"{prefix}.event_start_s")
    event_end = _finite(source.get("event_end_s"), f"{prefix}.event_end_s")
    if event_end < event_start:
        raise ReplayManifestBridgeError(f"{prefix}: event range moves backward")
    if event_start < definition_start or event_end > definition_end:
        raise ReplayManifestBridgeError(f"{prefix}: event range falls outside definition period")
    expected_count = _expected_inventory_count(basis_row, source_kind)
    record_count = _positive_int(source.get("record_count"), f"{prefix}.record_count")
    if record_count != expected_count:
        raise ReplayManifestBridgeError(
            f"{prefix}: record_count {record_count} != basis inventory {expected_count}"
        )
    size_bytes = _positive_int(source.get("size_bytes"), f"{prefix}.size_bytes")
    sha256 = str(source.get("sha256") or "").lower()
    if not _SHA256_RE.fullmatch(sha256):
        raise ReplayManifestBridgeError(f"{prefix}: sha256 must be a lowercase 64-character digest")
    location = str(source.get("location") or "")
    if not location:
        raise ReplayManifestBridgeError(f"{prefix}: observed location is required")
    observed_at = str(source.get("inventory_observed_at") or "")
    if not observed_at:
        raise ReplayManifestBridgeError(f"{prefix}: inventory_observed_at is required")
    inventory_start, inventory_end = _inventory_event_range(basis_row, source_kind)
    if inventory_start is not None and abs(event_start - inventory_start) > 1e-6:
        raise ReplayManifestBridgeError(f"{prefix}: event_start differs from basis inventory")
    if inventory_end is not None and abs(event_end - inventory_end) > 1e-6:
        raise ReplayManifestBridgeError(f"{prefix}: event_end differs from basis inventory")
    return {
        "day": day,
        "source_kind": source_kind,
        "status": "PRESENT",
        "location": location,
        "dataset": DATASET,
        "publisher_id": int(source["publisher_id"]),
        "instrument_id": expected["instrument_id"],
        "raw_symbol": expected["raw_symbol"],
        "definition_date": definition["definition_date"],
        "definition_start_s": definition_start,
        "definition_end_s": definition_end,
        "event_start_s": event_start,
        "event_end_s": event_end,
        "record_count": record_count,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "inventory_observed_at": observed_at,
        "basis_row_fingerprint": _sha(basis_row),
        "catalog_source_fingerprint": _sha(source),
    }


def build_replay_manifest(
    inventory: list[dict[str, Any]],
    source_catalog: dict[str, Any],
) -> dict[str, Any]:
    """Build a canonical READY replay manifest from exact-basis observed inputs."""
    inventory_before = copy.deepcopy(inventory)
    catalog_before = copy.deepcopy(source_catalog)
    basis_report = evaluate_manifest(copy.deepcopy(inventory))
    validate_report(basis_report)
    if basis_report.get("status") != "MATCHED_L1_MBO_READY":
        raise ReplayManifestBridgeError(
            f"exact replay manifest requires MATCHED_L1_MBO_READY; got {basis_report.get('status')}"
        )
    basis_rows = _inventory_rows(inventory)
    catalog = _validate_catalog_envelope(
        source_catalog,
        inventory=inventory,
        basis_report=basis_report,
    )
    definitions_raw = catalog.get("definitions")
    if not isinstance(definitions_raw, dict):
        raise ReplayManifestBridgeError("source catalog definitions must be an object")
    definitions = {
        symbol: _validate_definition(symbol, definitions_raw.get(symbol) or {})
        for symbol in ("NGJ26", "NGK26")
    }
    sources = _catalog_sources(catalog)
    entries = []
    for day in G15_DATES:
        symbol = G15_CONTRACT_MAP[day]["raw_symbol"]
        day_entries = []
        for source_kind in SOURCE_KINDS:
            entry = _validate_source(
                sources[(day, source_kind)],
                day=day,
                source_kind=source_kind,
                basis_row=basis_rows[day],
                definition=definitions[symbol],
            )
            entries.append(entry)
            day_entries.append(entry)
        overlap_start = max(float(row["event_start_s"]) for row in day_entries)
        overlap_end = min(float(row["event_end_s"]) for row in day_entries)
        if overlap_end < overlap_start:
            raise ReplayManifestBridgeError(f"{day}: observed L1 and MBO event ranges do not overlap")

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "market": "NG",
        "group": 15,
        "coverage": {"start": G15_DATES[0], "end": G15_DATES[-1]},
        "authority": "HISTORICAL_INPUT_METADATA_ONLY",
        "execution_authority": False,
        "remote_inventory_verified": True,
        "basis_status": basis_report["status"],
        "basis_inventory_fingerprint": _sha(inventory),
        "basis_report_fingerprint": basis_report["fingerprint"],
        "source_catalog_fingerprint": source_catalog["fingerprint"],
        "definitions": definitions,
        "corpus_expectations": {
            "l1_trades": {
                "expected_window": {"start": "2025-07-01", "end_exclusive": "2026-07-01"},
                "known_logical_store": "exact-contract observed catalog",
                "known_format": "raw observed object normalized to trade-only replay events",
                "inventory_status": "VERIFIED",
            },
            "mbo": {
                "expected_window": {"start": "2026-03-01", "end_exclusive": "2026-07-01"},
                "known_logical_store": "specific-leg observed catalog",
                "known_format": "DBN or causally normalized JSONL",
                "inventory_status": "VERIFIED",
            },
        },
        "entries": entries,
        "actual_outcomes_used": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "note": (
            "Built only after the separate exact-basis gate reported MATCHED_L1_MBO_READY. "
            "The 2026-03-13 anchor is intentionally outside replay entries."
        ),
    }
    report = validate_manifest(manifest)
    if report.get("status") != "READY" or report.get("can_replay_all_g15") is not True:
        raise ReplayManifestBridgeError(f"canonical historical manifest is not READY: {report}")
    bridge = {
        "schema": BRIDGE_SCHEMA,
        "group": 15,
        "status": "READY",
        "manifest": manifest,
        "manifest_report": report,
        "basis_inventory_fingerprint": _sha(inventory),
        "basis_report_fingerprint": basis_report["fingerprint"],
        "source_catalog_fingerprint": source_catalog["fingerprint"],
        "anchor_date_excluded_from_replay": "20260313",
        "actual_outcomes_used": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
    }
    bridge["fingerprint"] = _sha(bridge)
    if inventory != inventory_before or source_catalog != catalog_before:
        raise ReplayManifestBridgeError("bridge mutated its source artifacts")
    return bridge


def validate_bridge_output(
    bridge: dict[str, Any],
    *,
    inventory: list[dict[str, Any]] | None = None,
    source_catalog: dict[str, Any] | None = None,
) -> None:
    candidate = copy.deepcopy(bridge)
    observed = candidate.pop("fingerprint", None)
    if candidate.get("schema") != BRIDGE_SCHEMA or candidate.get("status") != "READY":
        raise ReplayManifestBridgeError("unexpected or non-ready bridge artifact")
    if observed != _sha(candidate):
        raise ReplayManifestBridgeError("bridge artifact fingerprint mismatch")
    for name in (
        "actual_outcomes_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
    ):
        if candidate.get(name) is not False:
            raise ReplayManifestBridgeError(f"bridge artifact must keep {name}=false")
    manifest = candidate.get("manifest")
    if not isinstance(manifest, dict):
        raise ReplayManifestBridgeError("bridge artifact is missing canonical manifest")
    report = validate_manifest(manifest)
    if report.get("status") != "READY" or report.get("can_replay_all_g15") is not True:
        raise ReplayManifestBridgeError("bridge canonical manifest is no longer READY")
    if report != candidate.get("manifest_report"):
        raise ReplayManifestBridgeError("bridge manifest report changed")
    if inventory is not None and candidate.get("basis_inventory_fingerprint") != _sha(inventory):
        raise ReplayManifestBridgeError("bridge references a different basis inventory")
    if source_catalog is not None and candidate.get("source_catalog_fingerprint") != source_catalog.get("fingerprint"):
        raise ReplayManifestBridgeError("bridge references a different source catalog")


def _fixture_inventory(*, wrong_pre_roll: bool = False) -> list[dict[str, Any]]:
    rows = []
    for day, expected in EXPECTED.items():
        l1_id = 996 if wrong_pre_roll and day <= "20260319" else expected["instrument_id"]
        start = datetime.fromisoformat(f"{day[:4]}-{day[4:6]}-{day[6:]}T00:00:00+00:00").timestamp()
        end = start + 3600
        rows.append(
            {
                "date": day,
                "contract": expected["contract"],
                "expected_instrument_id": expected["instrument_id"],
                "mbo_present": True,
                "mbo_bytes": 1000,
                "l1_present": True,
                "l1_bytes": 500,
                "l1_readable": True,
                "l1_instrument_id": [l1_id],
                "l1_n_rows": 20,
                "l1_n_trades": 10,
                "l1_basis_correct": l1_id == expected["instrument_id"],
                "dataset": DATASET,
                "publisher_id": 1,
                "instrument_id": expected["instrument_id"],
                "raw_symbol": expected["contract"],
                "mbo_basis_correct": True,
                "n_mbo": 30,
                "n_trades": 10,
                "first_event_utc": start,
                "last_event_utc": end,
                "mbo_first_event_s": start,
                "mbo_last_event_s": end,
                "l1_first_event_s": start + 1,
                "l1_last_event_s": end - 1,
                "chronological_ok": True,
                "flow_usable": True,
                "queue_usable": True,
            }
        )
    return rows


def _fixture_catalog(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _inventory_rows(inventory)
    basis = evaluate_manifest(copy.deepcopy(inventory))
    definitions = {
        "NGJ26": {
            "dataset": DATASET,
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
            "definition_start_s": 0.0,
            "definition_end_s": 2_000_000_000.0,
            "observed_at": "2026-07-22T00:00:00Z",
            "source": "fixture",
        },
        "NGK26": {
            "dataset": DATASET,
            "publisher_id": 1,
            "instrument_id": 996,
            "raw_symbol": "NGK26",
            "definition_date": "2026-03-20",
            "definition_start_s": 0.0,
            "definition_end_s": 2_000_000_000.0,
            "observed_at": "2026-07-22T00:00:00Z",
            "source": "fixture",
        },
    }
    sources = []
    for day in G15_DATES:
        row = rows[day]
        symbol = G15_CONTRACT_MAP[day]["raw_symbol"]
        definition = definitions[symbol]
        for source_kind in SOURCE_KINDS:
            start, end = _inventory_event_range(row, source_kind)
            count = _expected_inventory_count(row, source_kind)
            sources.append(
                {
                    "day": day,
                    "source_kind": source_kind,
                    "status": "PRESENT",
                    "location": f"file:///fixture/{day}_{source_kind}.dbn",
                    "dataset": DATASET,
                    "publisher_id": 1,
                    "instrument_id": G15_CONTRACT_MAP[day]["instrument_id"],
                    "raw_symbol": symbol,
                    "definition_date": definition["definition_date"],
                    "definition_start_s": definition["definition_start_s"],
                    "definition_end_s": definition["definition_end_s"],
                    "event_start_s": start,
                    "event_end_s": end,
                    "record_count": count,
                    "size_bytes": 1000 + count,
                    "sha256": hashlib.sha256(f"{day}:{source_kind}".encode()).hexdigest(),
                    "inventory_observed_at": "2026-07-22T00:00:00Z",
                    "basis_row_fingerprint": _sha(row),
                }
            )
    catalog = {
        "schema": CATALOG_SCHEMA,
        "market": "NG",
        "group": 15,
        "status": "READY",
        "basis_inventory_fingerprint": _sha(inventory),
        "basis_report_fingerprint": basis["fingerprint"],
        "definitions": definitions,
        "sources": sources,
        "actual_outcomes_used": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "note": "fixture",
    }
    catalog["fingerprint"] = _sha(catalog)
    return catalog


def selftest() -> int:
    inventory = _fixture_inventory()
    catalog = _fixture_catalog(inventory)
    bridge = build_replay_manifest(inventory, catalog)
    validate_bridge_output(bridge, inventory=inventory, source_catalog=catalog)
    assert bridge["manifest_report"]["status"] == "READY"
    assert len(bridge["manifest"]["entries"]) == 24
    assert all(row["day"] != "20260313" for row in bridge["manifest"]["entries"])
    print("[ng_g15_replay_manifest_bridge] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge exact G15 basis inventory into replay manifest")
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--source-catalog", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--init-catalog", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.inventory:
        parser.error("--inventory is required")
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    if args.init_catalog:
        if not args.out:
            parser.error("--out is required with --init-catalog")
        catalog = build_catalog_template(inventory)
        _atomic_json(args.out, catalog)
        print(json.dumps({"status": catalog["status"], "out": str(args.out)}, indent=2))
        return 0
    if not args.source_catalog or not args.out:
        parser.error("--source-catalog and --out are required")
    catalog = json.loads(args.source_catalog.read_text(encoding="utf-8"))
    bridge = build_replay_manifest(inventory, catalog)
    validate_bridge_output(bridge, inventory=inventory, source_catalog=catalog)
    _atomic_json(args.out, bridge)
    print(
        json.dumps(
            {
                "status": bridge["status"],
                "manifest_status": bridge["manifest_report"]["status"],
                "entry_count": len(bridge["manifest"]["entries"]),
                "fingerprint": bridge["fingerprint"],
                "out": str(args.out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
