#!/usr/bin/env python3
"""Inspect materialized NG historical objects and build the canonical corpus catalog.

This module is the operational bridge between real local/AWS object inspection and
``ng_corpus_coverage_audit.py``. It never infers contract identity from filenames,
S3 keys, directory names, or continuous symbols. Every PRESENT object is bound to
an observed, fingerprinted definition record and its bytes are hashed before and
after a streaming record inspection.

The output remains metadata-only and outcome-blind. It cannot alter blind
forecasts, posterior state, ``knowledge/ng_brain.json``, or execution authority.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_historical_normalize as normalize

PLAN_SCHEMA = "ng_corpus_inspection_plan.v1"
DEFINITION_SCHEMA = "ng_definition_observation.v1"
RECEIPT_SCHEMA = "ng_corpus_inspection_receipt.v1"
DATASET = coverage.DATASET
CORPUS_IDS = tuple(coverage.EXPECTED_WINDOWS)
LANE_TO_KIND = {"l1_trades": "trade", "mbo": "mbo"}


class CorpusInspectionError(ValueError):
    """Raised when inspection metadata is malformed, contradictory, or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise CorpusInspectionError(f"{label} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusInspectionError(f"{label} must be finite") from error
    if not math.isfinite(number):
        raise CorpusInspectionError(f"{label} must be finite")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise CorpusInspectionError(f"{label} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusInspectionError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise CorpusInspectionError(f"{label} must be a positive integer")
    return number


def _verify_fingerprint(
    value: Mapping[str, Any], field: str, *, label: str
) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise CorpusInspectionError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _authority_contract(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "may_update_ng_brain",
        "may_change_blind_forecast",
        "may_change_posterior",
        "execution_authority",
    ):
        if value.get(field) is not False:
            raise CorpusInspectionError(f"{label}: {field} must remain false")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise CorpusInspectionError(
            f"{label}: cme_event_contracts_mode must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise CorpusInspectionError(
            f"{label}: brokerage_contract must be tastytrade_not_ibkr"
        )
    if value.get("options_lane_started") is not False:
        raise CorpusInspectionError(f"{label}: options lane must remain unstarted")


def _base_authority() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def definition_observation(
    *,
    dataset: str,
    publisher_id: int,
    instrument_id: int,
    raw_symbol: str,
    definition_date: str,
    definition_start_s: float,
    definition_end_s: float,
    observed_from: str,
    observed_at: str,
    source_sha256: str,
    source_size_bytes: int,
) -> dict[str, Any]:
    """Create one fingerprinted observed-definition record."""
    value = {
        "schema": DEFINITION_SCHEMA,
        "dataset": str(dataset),
        "publisher_id": int(publisher_id),
        "instrument_id": int(instrument_id),
        "raw_symbol": str(raw_symbol),
        "definition_date": str(definition_date),
        "definition_start_s": float(definition_start_s),
        "definition_end_s": float(definition_end_s),
        "observed_from": str(observed_from),
        "observed_at": str(observed_at),
        "source_sha256": str(source_sha256).lower(),
        "source_size_bytes": int(source_size_bytes),
        "identity_inferred_from_filename": False,
        **_base_authority(),
    }
    value["definition_fingerprint"] = _fp(value)
    validate_definition(value)
    return value


def validate_definition(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify_fingerprint(
        value, "definition_fingerprint", label="definition observation"
    )
    if checked.get("schema") != DEFINITION_SCHEMA:
        raise CorpusInspectionError("definition observation schema mismatch")
    _authority_contract(checked, label="definition observation")
    if checked.get("dataset") != DATASET:
        raise CorpusInspectionError(f"definition dataset must be {DATASET}")
    _positive_int(checked.get("publisher_id"), label="definition publisher_id")
    _positive_int(checked.get("instrument_id"), label="definition instrument_id")
    raw_symbol = str(checked.get("raw_symbol") or "")
    if not raw_symbol.startswith("NG") or len(raw_symbol) < 5:
        raise CorpusInspectionError("definition raw_symbol must be an exact NG contract")
    start = _finite(checked.get("definition_start_s"), label="definition_start_s")
    end = _finite(checked.get("definition_end_s"), label="definition_end_s")
    if end < start:
        raise CorpusInspectionError("definition period is backwards")
    if not str(checked.get("definition_date") or ""):
        raise CorpusInspectionError("definition_date is required")
    if not str(checked.get("observed_from") or ""):
        raise CorpusInspectionError("definition observed_from is required")
    if not str(checked.get("observed_at") or ""):
        raise CorpusInspectionError("definition observed_at is required")
    source_sha = str(checked.get("source_sha256") or "")
    if len(source_sha) != 64 or any(
        character not in "0123456789abcdef"
        for character in source_sha.lower()
    ):
        raise CorpusInspectionError(
            "definition source_sha256 must be 64 hex characters"
        )
    _positive_int(
        checked.get("source_size_bytes"), label="definition source_size_bytes"
    )
    if checked.get("identity_inferred_from_filename") is not False:
        raise CorpusInspectionError(
            "definition identity may not be inferred from filename"
        )
    return checked


def plan_template(*, allowed_roots: Sequence[str] = ()) -> dict[str, Any]:
    """Return a fail-closed plan template with no asserted object presence."""
    corpora = []
    for corpus_id, expected in coverage.EXPECTED_WINDOWS.items():
        corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": expected["lane"],
                "declared_window": {
                    "start": expected["start"],
                    "end_exclusive": expected["end_exclusive"],
                },
                "publisher_id": None,
                "expected_days": [],
                "expected_object_count": None,
                "inventory_scope_verified": False,
                "inventory_complete_asserted": False,
                "inventory_observed_at": None,
                "sources": [],
            }
        )
    value = {
        "schema": PLAN_SCHEMA,
        "market": "NG",
        "dataset": DATASET,
        "allowed_roots": [
            str(Path(root).expanduser()) for root in allowed_roots
        ],
        "corpora": corpora,
        "identity_may_be_inferred_from_filename": False,
        "remote_presence_inferred": False,
        **_base_authority(),
    }
    value["plan_fingerprint"] = _fp(value)
    return value


def _validate_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify_fingerprint(
        value, "plan_fingerprint", label="inspection plan"
    )
    if checked.get("schema") != PLAN_SCHEMA:
        raise CorpusInspectionError("inspection plan schema mismatch")
    if checked.get("market") != "NG" or checked.get("dataset") != DATASET:
        raise CorpusInspectionError("inspection plan market/dataset mismatch")
    _authority_contract(checked, label="inspection plan")
    if checked.get("identity_may_be_inferred_from_filename") is not False:
        raise CorpusInspectionError(
            "inspection plan may not infer identity from filenames"
        )
    if checked.get("remote_presence_inferred") is not False:
        raise CorpusInspectionError(
            "inspection plan may not infer remote presence"
        )

    roots = [
        Path(str(root)).expanduser().resolve()
        for root in checked.get("allowed_roots") or []
    ]
    if not roots:
        raise CorpusInspectionError(
            "inspection plan requires at least one allowed_root"
        )

    corpora = list(checked.get("corpora") or [])
    seen_corpora: set[str] = set()
    seen_sources: set[str] = set()
    if len(corpora) != len(CORPUS_IDS):
        raise CorpusInspectionError(
            "inspection plan must contain both canonical corpora"
        )
    for corpus in corpora:
        if not isinstance(corpus, Mapping):
            raise CorpusInspectionError(
                "inspection plan contains non-object corpus"
            )
        corpus_id = str(corpus.get("corpus_id") or "")
        if (
            corpus_id not in coverage.EXPECTED_WINDOWS
            or corpus_id in seen_corpora
        ):
            raise CorpusInspectionError(
                f"unexpected or duplicate corpus_id {corpus_id!r}"
            )
        seen_corpora.add(corpus_id)
        expected = coverage.EXPECTED_WINDOWS[corpus_id]
        if corpus.get("lane") != expected["lane"]:
            raise CorpusInspectionError(f"{corpus_id}: lane mismatch")
        if dict(corpus.get("declared_window") or {}) != {
            "start": expected["start"],
            "end_exclusive": expected["end_exclusive"],
        }:
            raise CorpusInspectionError(
                f"{corpus_id}: declared window mismatch"
            )
        expected_days = [
            str(day).replace("-", "")
            for day in corpus.get("expected_days") or []
        ]
        if len(expected_days) != len(set(expected_days)):
            raise CorpusInspectionError(
                f"{corpus_id}: duplicate expected_days"
            )
        count = corpus.get("expected_object_count")
        if count is not None:
            _positive_int(
                count, label=f"{corpus_id} expected_object_count"
            )
        if corpus.get("inventory_complete_asserted") is True:
            if not corpus.get("inventory_scope_verified"):
                raise CorpusInspectionError(
                    f"{corpus_id}: complete inventory requires verified scope"
                )
            if not expected_days or count is None:
                raise CorpusInspectionError(
                    f"{corpus_id}: complete inventory requires expected days "
                    "and object count"
                )
        for source in corpus.get("sources") or []:
            if not isinstance(source, Mapping):
                raise CorpusInspectionError(
                    f"{corpus_id}: source is not an object"
                )
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in seen_sources:
                raise CorpusInspectionError(
                    f"duplicate or missing source_id {source_id!r}"
                )
            seen_sources.add(source_id)
            day = str(source.get("day") or "").replace("-", "")
            if len(day) != 8 or not day.isdigit():
                raise CorpusInspectionError(f"{source_id}: invalid day")
            if source.get("lane", expected["lane"]) != expected["lane"]:
                raise CorpusInspectionError(f"{source_id}: lane mismatch")
            materialized = source.get("materialized_path")
            if materialized not in (None, ""):
                resolved = Path(str(materialized)).expanduser().resolve()
                if not any(
                    resolved == root or root in resolved.parents
                    for root in roots
                ):
                    raise CorpusInspectionError(
                        f"{source_id}: materialized path escapes allowed_roots"
                    )
            definition = source.get("definition")
            if definition not in (None, ""):
                if not isinstance(definition, Mapping):
                    raise CorpusInspectionError(
                        f"{source_id}: definition must be an object"
                    )
                validate_definition(definition)
    if seen_corpora != set(CORPUS_IDS):
        raise CorpusInspectionError(
            "inspection plan missing canonical corpus"
        )
    return checked


def _iter_raw(path: Path) -> Iterable[Any]:
    lower = path.name.lower()
    if (
        lower.endswith(".dbn")
        or lower.endswith(".dbn.zst")
        or lower.endswith(".zst")
    ):
        return normalize.iter_dbn(path)
    return normalize.iter_jsonl(path)


def _minimal_entry(
    source: Mapping[str, Any], lane: str, status: str, error: str
) -> dict[str, Any]:
    row = {
        "source_id": str(source.get("source_id") or ""),
        "location": str(
            source.get("location")
            or source.get("materialized_path")
            or ""
        ),
        "day": str(source.get("day") or "").replace("-", ""),
        "lane": lane,
        "status": status,
        "observation_error": error,
        "identity_inferred_from_filename": False,
    }
    row["inspection_fingerprint"] = _fp(row)
    return row


def inspect_source(
    source: Mapping[str, Any], *, lane: str
) -> dict[str, Any]:
    """Inspect one materialized object without mutating it or inferring identity."""
    source_copy = copy.deepcopy(dict(source))
    materialized = source_copy.get("materialized_path")
    if materialized in (None, ""):
        return _minimal_entry(
            source_copy,
            lane,
            "UNKNOWN",
            "object has not been materialized for inspection",
        )
    path = Path(str(materialized)).expanduser().resolve()
    if not path.exists():
        return _minimal_entry(
            source_copy,
            lane,
            "MISSING",
            f"missing materialized object: {path}",
        )
    if not path.is_file():
        return _minimal_entry(
            source_copy,
            lane,
            "CORRUPT",
            f"materialized path is not a file: {path}",
        )
    try:
        definition_raw = source_copy.get("definition")
        if not isinstance(definition_raw, Mapping):
            raise CorpusInspectionError("observed definition is required")
        definition = validate_definition(definition_raw)
        expected_kind = LANE_TO_KIND[lane]
        before_size = path.stat().st_size
        before_sha = _sha256(path)
        record_count = 0
        input_count = 0
        skipped = 0
        first: float | None = None
        last: float | None = None
        previous: tuple[float, int, int] | None = None
        skip_nonmatching = source_copy.get("skip_nonmatching") is True
        for input_count, raw in enumerate(_iter_raw(path), 1):
            if not normalize.record_matches_kind(raw, expected_kind):
                if skip_nonmatching:
                    skipped += 1
                    continue
                raise CorpusInspectionError(
                    f"record {input_count} does not match lane {lane}"
                )
            event = normalize.normalize_record(
                raw,
                event_type=expected_kind,
                dataset=definition["dataset"],
                publisher_id=int(definition["publisher_id"]),
                instrument_id=int(definition["instrument_id"]),
                raw_symbol=str(definition["raw_symbol"]),
                definition_date=str(definition["definition_date"]),
                session_day=str(source_copy.get("day") or "").replace(
                    "-", ""
                ),
                source_id=str(source_copy.get("source_id") or ""),
                ingest_sequence=input_count,
            )
            timestamp = float(event["ts_event_s"])
            if (
                timestamp < float(definition["definition_start_s"])
                or timestamp > float(definition["definition_end_s"])
            ):
                raise CorpusInspectionError(
                    f"record {input_count} falls outside observed definition period"
                )
            key = (
                timestamp,
                int(event.get("source_sequence", 0)),
                int(event.get("ingest_sequence", input_count)),
            )
            if previous is not None and key < previous:
                raise CorpusInspectionError(
                    f"source moved backwards at input record {input_count}"
                )
            previous = key
            record_count += 1
            first = timestamp if first is None else first
            last = timestamp
        if record_count == 0:
            raise CorpusInspectionError(
                "object contained zero matching records"
            )
        after_size = path.stat().st_size
        after_sha = _sha256(path)
        if (before_size, before_sha) != (after_size, after_sha):
            raise CorpusInspectionError(
                "object changed during inspection"
            )
        row = {
            "source_id": str(source_copy.get("source_id") or ""),
            "location": str(source_copy.get("location") or path),
            "materialized_path": str(path),
            "day": str(source_copy.get("day") or "").replace("-", ""),
            "lane": lane,
            "status": "PRESENT",
            "dataset": definition["dataset"],
            "publisher_id": int(definition["publisher_id"]),
            "instrument_id": int(definition["instrument_id"]),
            "raw_symbol": str(definition["raw_symbol"]),
            "definition_date": str(definition["definition_date"]),
            "definition_start_s": float(
                definition["definition_start_s"]
            ),
            "definition_end_s": float(definition["definition_end_s"]),
            "event_start_s": first,
            "event_end_s": last,
            "record_count": record_count,
            "input_record_count": input_count,
            "skipped_nonmatching": skipped,
            "size_bytes": before_size,
            "sha256": before_sha,
            "inventory_observed_at": str(
                source_copy.get("inventory_observed_at")
                or definition.get("observed_at")
                or ""
            ),
            "definition_fingerprint": definition[
                "definition_fingerprint"
            ],
            "definition_source_location": definition["observed_from"],
            "raw_input_untouched": True,
            "identity_inferred_from_filename": False,
        }
        row["inspection_fingerprint"] = _fp(row)
        return row
    except Exception as error:
        return _minimal_entry(
            source_copy, lane, "CORRUPT", str(error)
        )


def build_catalog(
    plan: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Inspect all planned objects and return catalog, audit, and receipt."""
    checked = _validate_plan(plan)
    catalog_corpora: list[dict[str, Any]] = []
    source_statuses: dict[str, str] = {}
    source_fingerprints: dict[str, str] = {}
    for corpus in checked["corpora"]:
        corpus_id = str(corpus["corpus_id"])
        lane = str(corpus["lane"])
        rows = [
            inspect_source(source, lane=lane)
            for source in corpus.get("sources") or []
        ]
        for row in rows:
            source_statuses[str(row["source_id"])] = str(row["status"])
            source_fingerprints[str(row["source_id"])] = str(
                row["inspection_fingerprint"]
            )
        expected_days = [
            str(day).replace("-", "")
            for day in corpus.get("expected_days") or []
        ]
        present_days = {
            row["day"] for row in rows if row["status"] == "PRESENT"
        }
        all_inspected = all(
            row["status"] != "UNKNOWN" for row in rows
        )
        all_present = bool(rows) and all(
            row["status"] == "PRESENT" for row in rows
        )
        expected_count = corpus.get("expected_object_count")
        counts_match = (
            expected_count is not None
            and int(expected_count) == len(rows)
        )
        days_match = bool(expected_days) and set(expected_days).issubset(
            present_days
        )
        remote_verified = bool(
            corpus.get("inventory_scope_verified") and all_inspected
        )
        inventory_complete = bool(
            corpus.get("inventory_complete_asserted")
            and remote_verified
            and all_present
            and counts_match
            and days_match
        )
        publishers = {
            int(row["publisher_id"])
            for row in rows
            if row["status"] == "PRESENT"
        }
        publisher_id = (
            int(corpus["publisher_id"])
            if corpus.get("publisher_id") not in (None, "")
            else (
                next(iter(publishers))
                if len(publishers) == 1
                else None
            )
        )
        catalog_corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "declared_window": copy.deepcopy(
                    dict(corpus["declared_window"])
                ),
                "publisher_id": publisher_id,
                "remote_inventory_verified": remote_verified,
                "inventory_complete": inventory_complete,
                "expected_object_count": expected_count,
                "observed_object_count": len(rows),
                "expected_days": expected_days,
                "inventory_observed_at": corpus.get(
                    "inventory_observed_at"
                ),
                "entries": rows,
                "note": (
                    "Built only from materialized, byte-hashed object inspection; "
                    "filenames and S3 keys were not used as identity evidence."
                ),
            }
        )
    catalog = {
        "schema": coverage.CATALOG_SCHEMA,
        "market": "NG",
        "dataset": DATASET,
        "corpora": catalog_corpora,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "may_update_ng_brain": False,
        "may_change_blind_forecast": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
    }
    catalog["catalog_fingerprint"] = coverage._fp(catalog)
    audit = coverage.build_audit(catalog)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "INSPECTION_COMPLETE",
        "plan_fingerprint": checked["plan_fingerprint"],
        "catalog_fingerprint": catalog["catalog_fingerprint"],
        "audit_fingerprint": audit["fingerprint"],
        "source_statuses": source_statuses,
        "source_inspection_fingerprints": source_fingerprints,
        "present_count": sum(
            status == "PRESENT" for status in source_statuses.values()
        ),
        "missing_count": sum(
            status == "MISSING" for status in source_statuses.values()
        ),
        "corrupt_count": sum(
            status == "CORRUPT" for status in source_statuses.values()
        ),
        "unknown_count": sum(
            status == "UNKNOWN" for status in source_statuses.values()
        ),
        "identity_inferred_from_filename": False,
        "remote_presence_inferred": False,
        "catalog": catalog,
        "audit": audit,
        **_base_authority(),
    }
    receipt["receipt_fingerprint"] = _fp(receipt)
    validate_receipt(receipt)
    return catalog, audit, receipt


def validate_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify_fingerprint(
        value, "receipt_fingerprint", label="inspection receipt"
    )
    if checked.get("schema") != RECEIPT_SCHEMA:
        raise CorpusInspectionError("inspection receipt schema mismatch")
    if checked.get("status") != "INSPECTION_COMPLETE":
        raise CorpusInspectionError("inspection receipt status mismatch")
    _authority_contract(checked, label="inspection receipt")
    if checked.get("identity_inferred_from_filename") is not False:
        raise CorpusInspectionError(
            "receipt may not infer identity from filename"
        )
    if checked.get("remote_presence_inferred") is not False:
        raise CorpusInspectionError(
            "receipt may not infer remote presence"
        )
    catalog = copy.deepcopy(dict(checked.get("catalog") or {}))
    if catalog.get("catalog_fingerprint") != checked.get(
        "catalog_fingerprint"
    ):
        raise CorpusInspectionError(
            "receipt catalog fingerprint mismatch"
        )
    rebuilt_audit = coverage.build_audit(catalog)
    audit = copy.deepcopy(dict(checked.get("audit") or {}))
    coverage.validate_audit(audit)
    if audit.get("fingerprint") != checked.get("audit_fingerprint"):
        raise CorpusInspectionError("receipt audit fingerprint mismatch")
    if _canonical(rebuilt_audit) != _canonical(audit):
        raise CorpusInspectionError(
            "receipt audit does not match rebuilt catalog audit"
        )
    entries = [
        row
        for corpus in catalog.get("corpora") or []
        for row in corpus.get("entries") or []
    ]
    statuses = {
        str(row.get("source_id")): str(row.get("status"))
        for row in entries
    }
    if statuses != dict(checked.get("source_statuses") or {}):
        raise CorpusInspectionError(
            "receipt source statuses mismatch"
        )
    fingerprints = {
        str(row.get("source_id")): str(
            row.get("inspection_fingerprint")
        )
        for row in entries
    }
    if fingerprints != dict(
        checked.get("source_inspection_fingerprints") or {}
    ):
        raise CorpusInspectionError(
            "receipt source fingerprints mismatch"
        )
    for row in entries:
        payload = copy.deepcopy(dict(row))
        observed = payload.pop("inspection_fingerprint", None)
        if observed != _fp(payload):
            raise CorpusInspectionError(
                "inspection entry fingerprint mismatch: "
                f"{row.get('source_id')}"
            )
    counts = {
        "present_count": sum(
            status == "PRESENT" for status in statuses.values()
        ),
        "missing_count": sum(
            status == "MISSING" for status in statuses.values()
        ),
        "corrupt_count": sum(
            status == "CORRUPT" for status in statuses.values()
        ),
        "unknown_count": sum(
            status == "UNKNOWN" for status in statuses.values()
        ),
    }
    for field, expected in counts.items():
        if checked.get(field) != expected:
            raise CorpusInspectionError(f"receipt {field} mismatch")
    return checked


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise CorpusInspectionError(f"{path}: expected JSON object")
    return value


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data = root / "trade.jsonl"
        definition = definition_observation(
            dataset=DATASET,
            publisher_id=1,
            instrument_id=996,
            raw_symbol="NGK26",
            definition_date="2026-03-01",
            definition_start_s=1.0,
            definition_end_s=100.0,
            observed_from="s3://observed/definition.dbn",
            observed_at="2026-07-22T00:00:00Z",
            source_sha256="a" * 64,
            source_size_bytes=10,
        )
        rows = [
            {
                "event_type": "trade",
                "ts_event_s": 10.0,
                "source_sequence": 1,
                "price": 3.0,
                "size": 1,
                "side": "B",
            },
            {
                "event_type": "trade",
                "ts_event_s": 20.0,
                "source_sequence": 2,
                "price": 3.1,
                "size": 2,
                "side": "A",
            },
        ]
        data.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        plan = plan_template(allowed_roots=[str(root)])
        plan["corpora"][0]["sources"].append(
            {
                "source_id": "selftest-trades",
                "location": "s3://observed/trade.dbn",
                "materialized_path": str(data),
                "day": "20260330",
                "lane": "l1_trades",
                "definition": definition,
                "inventory_observed_at": "2026-07-22T00:00:00Z",
            }
        )
        plan.pop("plan_fingerprint")
        plan["plan_fingerprint"] = _fp(plan)
        catalog, audit, receipt = build_catalog(plan)
        assert catalog["corpora"][0]["entries"][0]["status"] == "PRESENT"
        assert audit["actual_outcomes_used"] is False
        validate_receipt(receipt)
    print("[ng_corpus_inspection] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect materialized NG historical objects and build the canonical "
            "corpus catalog"
        )
    )
    sub = parser.add_subparsers(dest="command", required=False)
    init = sub.add_parser(
        "init-plan", help="write a fail-closed inspection plan template"
    )
    init.add_argument("--allowed-root", action="append", default=[])
    init.add_argument("--out", type=Path, required=True)

    inspect = sub.add_parser(
        "inspect",
        help="inspect all plan sources and write catalog/audit/receipt",
    )
    inspect.add_argument("--plan", type=Path, required=True)
    inspect.add_argument("--catalog-out", type=Path, required=True)
    inspect.add_argument("--audit-out", type=Path, required=True)
    inspect.add_argument("--receipt-out", type=Path, required=True)

    validate = sub.add_parser(
        "validate", help="validate a completed inspection receipt"
    )
    validate.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if args.command == "init-plan":
        _write_json(
            args.out,
            plan_template(allowed_roots=args.allowed_root),
        )
        return 0
    if args.command == "inspect":
        catalog, audit, receipt = build_catalog(_load_json(args.plan))
        _write_json(args.catalog_out, catalog)
        _write_json(args.audit_out, audit)
        _write_json(args.receipt_out, receipt)
        print(
            json.dumps(
                {
                    "catalog": str(args.catalog_out),
                    "audit": str(args.audit_out),
                    "receipt": str(args.receipt_out),
                    "audit_status": audit["status"],
                    "present": receipt["present_count"],
                    "missing": receipt["missing_count"],
                    "corrupt": receipt["corrupt_count"],
                    "unknown": receipt["unknown_count"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "validate":
        validate_receipt(_load_json(args.receipt))
        print("[ng_corpus_inspection] receipt VALID")
        return 0
    parser.error("select a command or --selftest")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
