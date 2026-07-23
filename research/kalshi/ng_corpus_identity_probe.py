#!/usr/bin/env python3
"""Decode quarantined NG records and build REVIEW_REQUIRED exact-identity proposals."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import ng_corpus_coverage_audit as coverage
import ng_corpus_inspection as inspection
import ng_corpus_materialization as materialization
import ng_historical_normalize as normalize
from ng_corpus_quarantine_storage import (
    CorpusQuarantineError,
    _authority,
    _fp,
    _sha256,
    _validate_authority,
    _verify,
    validate_quarantine,
)

PROBE_SCHEMA = "ng_corpus_identity_probe.v1"
PROBE_STATUSES = {
    "UNIQUE_DEFINITION_MATCH",
    "NO_DEFINITION_MATCH",
    "AMBIGUOUS_DEFINITION_MATCH",
    "MULTI_INSTRUMENT_SOURCE",
    "PUBLISHER_UNOBSERVED",
    "DATASET_UNOBSERVED",
    "LANE_UNOBSERVED",
}


def _value(record: Any, *names: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        for name in names:
            if name in record:
                return record[name]
        return default
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def _text(value: Any) -> str:
    value = getattr(value, "name", value)
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    return str(value or "").strip()


def _int_or_none(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _is_dbn(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".dbn") or name.endswith(".dbn.zst") or path.suffix.lower() == ".zst"


def _transport_metadata(path: Path) -> dict[str, str]:
    """Read DBN header metadata without treating the object path as identity."""
    if not _is_dbn(path):
        return {"dataset": "", "source_schema": ""}
    try:
        import databento as db  # type: ignore
    except ImportError:
        return {"dataset": "", "source_schema": ""}
    store = db.DBNStore.from_file(str(path))
    metadata = getattr(store, "metadata", None)
    return {
        "dataset": _text(getattr(metadata, "dataset", "")),
        "source_schema": _text(getattr(metadata, "schema", "")),
    }


def _iter_records(path: Path) -> Iterable[Any]:
    return normalize.iter_dbn(path) if _is_dbn(path) else normalize.iter_jsonl(path)


def _lane_from_evidence(source_schemas: set[str], event_types: set[str]) -> str | None:
    normalized = {value.upper().replace("_", "-") for value in source_schemas if value}
    if any(value == "MBO" or value.endswith(".MBO") for value in normalized):
        return "mbo"
    if any(value in {"TRADES", "MBP-1", "MBP1", "TBBO"} for value in normalized):
        return "l1_trades"
    lowered = {value.lower() for value in event_types if value}
    if lowered == {"trade"}:
        return "l1_trades"
    if lowered == {"mbo"} or "mbo" in lowered:
        return "mbo"
    return None


def _probe_path(path: Path, definitions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    transport = _transport_metadata(path)
    datasets: set[str] = {transport["dataset"]} if transport["dataset"] else set()
    publishers: set[int] = set()
    instruments: set[int] = set()
    raw_symbols: set[str] = set()
    source_schemas: set[str] = (
        {transport["source_schema"]} if transport["source_schema"] else set()
    )
    event_types: set[str] = set()
    event_start: float | None = None
    event_end: float | None = None
    previous: tuple[float, int, int] | None = None
    record_count = 0
    for record_count, raw in enumerate(_iter_records(path), 1):
        timestamp_raw = _value(raw, "ts_event_s", "ts_event", "timestamp", "ts", "ts_recv")
        timestamp = normalize.event_seconds(timestamp_raw)
        sequence = _int_or_none(
            _value(raw, "source_sequence", "sequence", "sequence_number", default=record_count)
        )
        sequence = record_count if sequence is None else sequence
        key = (timestamp, sequence, record_count)
        if previous is not None and key < previous:
            raise CorpusQuarantineError(f"source moved backwards at record {record_count}: {path}")
        previous = key
        event_start = timestamp if event_start is None else min(event_start, timestamp)
        event_end = timestamp if event_end is None else max(event_end, timestamp)
        dataset = _text(_value(raw, "dataset", default=""))
        if dataset:
            datasets.add(dataset)
        publisher = _int_or_none(_value(raw, "publisher_id", default=None))
        if publisher is not None:
            publishers.add(publisher)
        instrument = _int_or_none(_value(raw, "instrument_id", default=None))
        if instrument is not None:
            instruments.add(instrument)
        raw_symbol = _text(_value(raw, "raw_symbol", default=""))
        if raw_symbol:
            raw_symbols.add(raw_symbol)
        source_schema = _text(
            _value(raw, "source_schema", "schema_name", "databento_schema", default="")
        )
        if source_schema:
            source_schemas.add(source_schema)
        event_type = _text(_value(raw, "event_type", default=""))
        if event_type:
            event_types.add(event_type)
    if record_count == 0 or event_start is None or event_end is None:
        raise CorpusQuarantineError(f"source contained zero records: {path}")
    lane = _lane_from_evidence(source_schemas, event_types)
    matching: list[dict[str, Any]] = []
    if len(datasets) == len(publishers) == len(instruments) == 1:
        dataset = next(iter(datasets))
        publisher = next(iter(publishers))
        instrument = next(iter(instruments))
        for definition in definitions:
            checked = inspection.validate_definition(definition)
            if checked["dataset"] != dataset:
                continue
            if int(checked["publisher_id"]) != publisher:
                continue
            if int(checked["instrument_id"]) != instrument:
                continue
            if raw_symbols and raw_symbols != {str(checked["raw_symbol"])}:
                continue
            if event_start < float(checked["definition_start_s"]):
                continue
            if event_end > float(checked["definition_end_s"]):
                continue
            matching.append(checked)
    deduped = {row["definition_fingerprint"]: row for row in matching}
    matches = [deduped[key] for key in sorted(deduped)]
    if len(instruments) != 1:
        status = "MULTI_INSTRUMENT_SOURCE"
    elif not publishers:
        status = "PUBLISHER_UNOBSERVED"
    elif not datasets:
        status = "DATASET_UNOBSERVED"
    elif lane is None:
        status = "LANE_UNOBSERVED"
    elif len(matches) == 1:
        status = "UNIQUE_DEFINITION_MATCH"
    elif len(matches) > 1:
        status = "AMBIGUOUS_DEFINITION_MATCH"
    else:
        status = "NO_DEFINITION_MATCH"
    value = {
        "status": status,
        "record_count": record_count,
        "event_start_s": event_start,
        "event_end_s": event_end,
        "datasets": sorted(datasets),
        "publisher_ids": sorted(publishers),
        "instrument_ids": sorted(instruments),
        "decoded_raw_symbols": sorted(raw_symbols),
        "source_schemas": sorted(source_schemas),
        "transport_metadata": transport,
        "event_types": sorted(event_types),
        "proposed_lane": lane,
        "matching_definition_fingerprints": [row["definition_fingerprint"] for row in matches],
        "unique_definition": matches[0] if len(matches) == 1 else None,
        "identity_inferred_from_object_name": False,
    }
    value["evidence_fingerprint"] = _fp(value)
    return value


def _load_definitions(value: Any) -> list[dict[str, Any]]:
    rows = value.get("definitions") if isinstance(value, Mapping) else value
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise CorpusQuarantineError("definitions must be a list or an object containing definitions")
    checked = [inspection.validate_definition(row) for row in rows]
    fingerprints = [row["definition_fingerprint"] for row in checked]
    if len(fingerprints) != len(set(fingerprints)):
        raise CorpusQuarantineError("definitions contain duplicate fingerprints")
    return checked


def probe_quarantine(
    *,
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definitions: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Probe quarantined bytes and return an explicit REVIEW_REQUIRED binding proposal."""
    snap = materialization.validate_snapshot(snapshot)
    quarantined = validate_quarantine(quarantine, snapshot=snap, verify_files=True)
    observed_definitions = _load_definitions(definitions)
    proposal = materialization.binding_template(snap)
    by_binding = {row["object_id"]: row for row in proposal["bindings"]}
    evidence_rows: list[dict[str, Any]] = []
    for object_receipt in quarantined["objects"]:
        object_id = object_receipt["object_id"]
        path = Path(object_receipt["quarantine_path"]).expanduser().resolve()
        before_sha = _sha256(path)
        evidence = _probe_path(path, observed_definitions)
        after_sha = _sha256(path)
        if before_sha != object_receipt["sha256"] or after_sha != before_sha:
            raise CorpusQuarantineError(f"quarantine source changed during probe: {path}")
        row = {
            "object_id": object_id,
            "location": object_receipt["location"],
            "quarantine_object_fingerprint": object_receipt["quarantine_object_fingerprint"],
            "source_sha256_before": before_sha,
            "source_sha256_after": after_sha,
            **evidence,
        }
        row["probe_object_fingerprint"] = _fp(row)
        evidence_rows.append(row)
        binding = by_binding[object_id]
        lane = evidence.get("proposed_lane")
        corpus_id = (
            coverage.L1_CORPUS_ID
            if lane == "l1_trades"
            else coverage.MBO_CORPUS_ID
            if lane == "mbo"
            else None
        )
        binding.update(
            review_status="REVIEW_REQUIRED",
            source_id=f"probe:{object_id}",
            corpus_id=corpus_id,
            lane=lane,
            day=None,
            definition=evidence.get("unique_definition"),
            skip_nonmatching=bool(lane == "l1_trades" and "TRADES" not in {s.upper() for s in evidence["source_schemas"]}),
            probe_status=evidence["status"],
            probe_evidence_fingerprint=evidence["evidence_fingerprint"],
            identity_inferred_from_object_name=False,
        )
        binding.pop("binding_fingerprint", None)
        binding["binding_fingerprint"] = _fp(binding)
    proposal.pop("binding_manifest_fingerprint", None)
    proposal["binding_manifest_fingerprint"] = _fp(proposal)
    materialization.validate_bindings(proposal, snapshot=snap, require_approved=False)
    evidence_rows.sort(key=lambda row: row["object_id"])
    value = {
        "schema": PROBE_SCHEMA,
        "status": "REVIEW_REQUIRED",
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "quarantine_fingerprint": quarantined["quarantine_fingerprint"],
        "definition_fingerprints": sorted(
            row["definition_fingerprint"] for row in observed_definitions
        ),
        "probed_object_count": len(evidence_rows),
        "objects": evidence_rows,
        "proposed_binding_manifest_fingerprint": proposal["binding_manifest_fingerprint"],
        "automatic_approval_permitted": False,
        "session_day_inferred_from_object_name": False,
        **_authority(),
    }
    value["probe_fingerprint"] = _fp(value)
    validate_probe(
        value,
        snapshot=snap,
        quarantine=quarantined,
        proposed_bindings=proposal,
    )
    return value, proposal


def validate_probe(
    value: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    checked = _verify(value, "probe_fingerprint", label="identity probe")
    if checked.get("schema") != PROBE_SCHEMA or checked.get("status") != "REVIEW_REQUIRED":
        raise CorpusQuarantineError("identity probe schema/status mismatch")
    _validate_authority(checked, label="identity probe")
    if checked.get("automatic_approval_permitted") is not False:
        raise CorpusQuarantineError("identity probe may not approve objects")
    if checked.get("session_day_inferred_from_object_name") is not False:
        raise CorpusQuarantineError("identity probe may not infer session day from object name")
    snap = materialization.validate_snapshot(snapshot)
    quarantined = validate_quarantine(quarantine, snapshot=snap, verify_files=True)
    proposal = materialization.validate_bindings(
        proposed_bindings, snapshot=snap, require_approved=False
    )
    if checked.get("snapshot_fingerprint") != snap["snapshot_fingerprint"]:
        raise CorpusQuarantineError("identity probe snapshot mismatch")
    if checked.get("quarantine_fingerprint") != quarantined["quarantine_fingerprint"]:
        raise CorpusQuarantineError("identity probe quarantine mismatch")
    if checked.get("proposed_binding_manifest_fingerprint") != proposal["binding_manifest_fingerprint"]:
        raise CorpusQuarantineError("identity probe proposed binding mismatch")
    rows = list(checked.get("objects") or [])
    if checked.get("probed_object_count") != len(rows):
        raise CorpusQuarantineError("identity probe object count mismatch")
    quarantine_by_id = {row["object_id"]: row for row in quarantined["objects"]}
    seen: set[str] = set()
    for raw in rows:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("probe_object_fingerprint", None)
        if observed != _fp(row):
            raise CorpusQuarantineError("identity probe object fingerprint mismatch")
        object_id = str(raw.get("object_id") or "")
        if object_id not in quarantine_by_id or object_id in seen:
            raise CorpusQuarantineError("identity probe unknown or duplicate object")
        seen.add(object_id)
        if raw.get("status") not in PROBE_STATUSES:
            raise CorpusQuarantineError("identity probe status is invalid")
        if raw.get("identity_inferred_from_object_name") is not False:
            raise CorpusQuarantineError("identity probe inferred identity from object name")
        if raw.get("source_sha256_before") != quarantine_by_id[object_id]["sha256"]:
            raise CorpusQuarantineError("identity probe source hash mismatch")
        if raw.get("source_sha256_after") != raw.get("source_sha256_before"):
            raise CorpusQuarantineError("identity probe source changed")
        evidence = copy.deepcopy(dict(raw))
        evidence.pop("probe_object_fingerprint", None)
        for field in (
            "object_id",
            "location",
            "quarantine_object_fingerprint",
            "source_sha256_before",
            "source_sha256_after",
        ):
            evidence.pop(field, None)
        observed_evidence = evidence.pop("evidence_fingerprint", None)
        if observed_evidence != _fp(evidence):
            raise CorpusQuarantineError("identity probe evidence fingerprint mismatch")
    binding_by_id = {row["object_id"]: row for row in proposal["bindings"]}
    for object_id in seen:
        binding = binding_by_id[object_id]
        if binding.get("review_status") != "REVIEW_REQUIRED":
            raise CorpusQuarantineError("identity probe proposal must remain REVIEW_REQUIRED")
    return checked
