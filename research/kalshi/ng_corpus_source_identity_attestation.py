#!/usr/bin/env python3
"""Attest source-native corpus identity before broad replay inspection.

The historical inspection plan carries explicit dataset, publisher, instrument, raw
symbol, and definition-period observations. This gate independently checks that the
materialized source bytes themselves support those identities:

* DBN files: dataset/schema metadata, symbology mappings, record-header publisher and
  instrument IDs, definition-period event bounds, and chronological event order.
* Decoded JSONL files: every matching row must carry the exact identity explicitly;
  injected manifest identity is not accepted as native evidence.

The gate is historical-only and outcome-blind. It never mutates blind forecasts,
posterior state, ``knowledge/ng_brain.json``, execution authority, CME SHADOW mode,
brokerage configuration, or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import ng_corpus_inspection as inspection
import ng_corpus_s3_materializer_provenance_gate as materializer_provenance
import ng_historical_normalize as normalize

SCHEMA = "ng_corpus_source_identity_attestation.v1"
READY_STATUS = "CORPUS_SOURCE_NATIVE_IDENTITY_ATTESTED"
BLOCKED_STATUS = "CORPUS_SOURCE_NATIVE_IDENTITY_BLOCKED"
DBN_SUFFIXES = (".dbn", ".dbn.zst", ".zst")
EXPECTED_SCHEMA = {"l1_trades": "trades", "mbo": "mbo"}


class CorpusSourceIdentityError(ValueError):
    """Raised when source-native identity evidence is malformed or contradictory."""


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


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CorpusSourceIdentityError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise CorpusSourceIdentityError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority_fields() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _authority(
    value: Mapping[str, Any], *, label: str, require_all: bool = True
) -> None:
    for field, expected in _authority_fields().items():
        if not require_all and field not in value:
            continue
        if value.get(field) != expected:
            raise CorpusSourceIdentityError(
                f"{label}: {field} must remain {expected!r}"
            )


def _value(value: Any, *names: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return default
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    for method in ("model_dump", "dict"):
        callable_value = getattr(value, method, None)
        if callable(callable_value):
            try:
                return _plain(callable_value())
            except TypeError:
                pass
    return value


def _enum_text(value: Any) -> str:
    for attribute in ("value", "name"):
        candidate = getattr(value, attribute, None)
        if candidate not in (None, ""):
            value = candidate
            break
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    return str(value or "").strip().lower().replace("_", "-")


def _date_text(value: Any) -> str:
    if isinstance(value, dt.datetime):
        value = value.date()
    if isinstance(value, dt.date):
        return value.strftime("%Y%m%d")
    text = str(value or "").strip().replace("-", "")
    return text[:8] if len(text) >= 8 else text


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _load_dbn_store(path: Path) -> Any:
    try:
        import databento as db  # type: ignore
    except ImportError as error:
        raise CorpusSourceIdentityError(
            "DBN source identity attestation requires the optional databento package"
        ) from error
    return db.DBNStore.from_file(str(path))


def _metadata(store: Any) -> Any:
    metadata = getattr(store, "metadata", None)
    return metadata if metadata is not None else store


def _schema_matches(observed: Any, lane: str) -> bool:
    text = _enum_text(observed)
    expected = EXPECTED_SCHEMA[lane]
    aliases = {
        "trades": {"trades", "trade"},
        "mbo": {"mbo", "market-by-order"},
    }
    return text in aliases[expected]


def _mapping_interval_contains(segment: Any, session_day: str) -> bool:
    start = _date_text(_value(segment, "start_date", "start", default=""))
    end = _date_text(_value(segment, "end_date", "end", default=""))
    if not start or not end:
        return False
    return start <= session_day < end


def _symbology_supports(
    symbology: Any,
    *,
    raw_symbol: str,
    instrument_id: int,
    session_day: str,
) -> tuple[bool, dict[str, Any]]:
    plain = _plain(symbology)
    if not isinstance(plain, Mapping):
        return False, {"reason": "symbology is unavailable or not mapping-like"}

    stype_in = _enum_text(plain.get("stype_in"))
    stype_out = _enum_text(plain.get("stype_out"))
    mappings = plain.get("mappings")
    if not isinstance(mappings, Mapping):
        return False, {
            "stype_in": stype_in,
            "stype_out": stype_out,
            "reason": "symbology mappings missing",
        }

    target_id = str(instrument_id)
    candidates: list[dict[str, Any]] = []
    for key, segments in mappings.items():
        if not isinstance(segments, (list, tuple)):
            continue
        for segment in segments:
            output = str(_value(segment, "symbol", "stype_out_symbol", default="") or "")
            interval_ok = _mapping_interval_contains(segment, session_day)
            key_text = str(key)
            direct = (
                stype_in in {"raw-symbol", "raw_symbol", "raw"}
                and stype_out in {"instrument-id", "instrument_id"}
                and key_text == raw_symbol
                and output == target_id
            )
            reverse = (
                stype_in in {"instrument-id", "instrument_id"}
                and stype_out in {"raw-symbol", "raw_symbol", "raw"}
                and key_text == target_id
                and output == raw_symbol
            )
            unlabeled = (
                not stype_in
                and not stype_out
                and (
                    (key_text == raw_symbol and output == target_id)
                    or (key_text == target_id and output == raw_symbol)
                )
            )
            if direct or reverse or unlabeled:
                candidates.append(
                    {
                        "mapping_key": key_text,
                        "mapping_symbol": output,
                        "start_date": _date_text(
                            _value(segment, "start_date", "start", default="")
                        ),
                        "end_date": _date_text(
                            _value(segment, "end_date", "end", default="")
                        ),
                        "session_day_in_interval": interval_ok,
                    }
                )
    usable = [row for row in candidates if row["session_day_in_interval"]]
    return bool(usable), {
        "stype_in": stype_in,
        "stype_out": stype_out,
        "matching_intervals": usable,
        "candidate_intervals": candidates,
    }


def _record_identity_scan(
    records: Iterable[Any],
    *,
    lane: str,
    definition: Mapping[str, Any],
    source_id: str,
    require_explicit_text_identity: bool,
) -> tuple[dict[str, Any], list[str]]:
    expected_kind = inspection.LANE_TO_KIND[lane]
    blockers: list[str] = []
    count = 0
    first: float | None = None
    last: float | None = None
    previous: tuple[float, int, int] | None = None
    observed_publishers: set[int] = set()
    observed_instruments: set[int] = set()
    observed_datasets: set[str] = set()
    observed_symbols: set[str] = set()
    observed_definition_dates: set[str] = set()

    for input_index, raw in enumerate(records, 1):
        if not normalize.record_matches_kind(raw, expected_kind):
            continue
        count += 1
        timestamp = normalize.event_seconds(
            _value(raw, "ts_event_s", "ts_event", "timestamp", "ts", "ts_recv")
        )
        source_sequence = _integer(
            _value(raw, "source_sequence", "sequence", "sequence_number", default=input_index)
        )
        key = (timestamp, source_sequence or input_index, input_index)
        if previous is not None and key < previous:
            blockers.append("RECORD_EVENT_TIME_MOVED_BACKWARDS")
        previous = key
        first = timestamp if first is None else first
        last = timestamp

        publisher = _integer(_value(raw, "publisher_id"))
        instrument = _integer(_value(raw, "instrument_id"))
        if publisher is None:
            blockers.append("RECORD_PUBLISHER_ID_MISSING")
        else:
            observed_publishers.add(publisher)
            if publisher != int(definition["publisher_id"]):
                blockers.append("RECORD_PUBLISHER_ID_MISMATCH")
        if instrument is None:
            blockers.append("RECORD_INSTRUMENT_ID_MISSING")
        else:
            observed_instruments.add(instrument)
            if instrument != int(definition["instrument_id"]):
                blockers.append("RECORD_INSTRUMENT_ID_MISMATCH")

        if require_explicit_text_identity:
            dataset = str(_value(raw, "dataset", default="") or "")
            raw_symbol = str(_value(raw, "raw_symbol", default="") or "")
            definition_date = str(_value(raw, "definition_date", default="") or "")
            if not dataset:
                blockers.append("JSONL_DATASET_MISSING")
            else:
                observed_datasets.add(dataset)
                if dataset != str(definition["dataset"]):
                    blockers.append("JSONL_DATASET_MISMATCH")
            if not raw_symbol:
                blockers.append("JSONL_RAW_SYMBOL_MISSING")
            else:
                observed_symbols.add(raw_symbol)
                if raw_symbol != str(definition["raw_symbol"]):
                    blockers.append("JSONL_RAW_SYMBOL_MISMATCH")
            if not definition_date:
                blockers.append("JSONL_DEFINITION_DATE_MISSING")
            else:
                observed_definition_dates.add(definition_date)
                if definition_date != str(definition["definition_date"]):
                    blockers.append("JSONL_DEFINITION_DATE_MISMATCH")

        if timestamp < float(definition["definition_start_s"]) or timestamp > float(
            definition["definition_end_s"]
        ):
            blockers.append("RECORD_EVENT_OUTSIDE_DEFINITION_PERIOD")

    if count == 0:
        blockers.append("NO_MATCHING_RECORDS")
    summary = {
        "source_id": source_id,
        "matching_record_count": count,
        "event_start_s": first,
        "event_end_s": last,
        "publisher_ids": sorted(observed_publishers),
        "instrument_ids": sorted(observed_instruments),
        "datasets": sorted(observed_datasets),
        "raw_symbols": sorted(observed_symbols),
        "definition_dates": sorted(observed_definition_dates),
        "chronological_order_attested": "RECORD_EVENT_TIME_MOVED_BACKWARDS" not in blockers,
        "definition_period_attested": "RECORD_EVENT_OUTSIDE_DEFINITION_PERIOD" not in blockers,
    }
    return summary, sorted(set(blockers))


def _materialization_map(provenance: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    exact = provenance.get("exact_materializer_receipt")
    if not isinstance(exact, Mapping):
        raise CorpusSourceIdentityError(
            "materializer provenance lacks embedded exact materializer receipt"
        )
    rows = exact.get("source_materializations")
    if not isinstance(rows, list):
        raise CorpusSourceIdentityError(
            "exact materializer receipt lacks source materializations"
        )
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise CorpusSourceIdentityError("source materialization row is not an object")
        source_id = str(row.get("source_id") or "")
        if not source_id or source_id in result:
            raise CorpusSourceIdentityError(
                f"duplicate or missing materialized source_id {source_id!r}"
            )
        result[source_id] = row
    return result


def inspect_source_identity(
    source: Mapping[str, Any],
    *,
    lane: str,
    materialization: Mapping[str, Any],
    store_loader: Callable[[Path], Any] = _load_dbn_store,
) -> dict[str, Any]:
    source_id = str(source.get("source_id") or "")
    definition_raw = source.get("definition")
    blockers: list[str] = []
    metadata_evidence: dict[str, Any] = {}
    symbology_evidence: dict[str, Any] = {}
    record_evidence: dict[str, Any] = {}
    path = Path(str(source.get("materialized_path") or "")).expanduser().resolve()

    try:
        if not isinstance(definition_raw, Mapping):
            raise CorpusSourceIdentityError("observed definition is required")
        definition = inspection.validate_definition(definition_raw)
        if not path.is_file():
            blockers.append("SOURCE_FILE_MISSING")
            raise CorpusSourceIdentityError("materialized source file is missing")

        expected_path = Path(
            str(materialization.get("materialized_path") or "")
        ).expanduser().resolve()
        if expected_path != path:
            blockers.append("MATERIALIZED_PATH_MISMATCH")
        before_size = path.stat().st_size
        before_sha = _sha256(path)
        if before_size != int(materialization.get("expected_size_bytes") or 0):
            blockers.append("MATERIALIZED_SIZE_MISMATCH")
        if before_sha != str(materialization.get("expected_sha256") or ""):
            blockers.append("MATERIALIZED_SHA256_MISMATCH")
        if before_size != int(definition["source_size_bytes"]):
            blockers.append("DEFINITION_SOURCE_SIZE_MISMATCH")
        if before_sha != str(definition["source_sha256"]):
            blockers.append("DEFINITION_SOURCE_SHA256_MISMATCH")

        lower = path.name.lower()
        if lower.endswith(DBN_SUFFIXES):
            store = store_loader(path)
            metadata = _metadata(store)
            dataset = str(_value(metadata, "dataset", default="") or "")
            schema = _value(metadata, "schema", default="")
            metadata_evidence = {
                "dataset": dataset,
                "schema": _enum_text(schema),
                "start": str(_value(metadata, "start", "start_date", default="") or ""),
                "end": str(_value(metadata, "end", "end_date", default="") or ""),
            }
            if dataset != str(definition["dataset"]):
                blockers.append("DBN_METADATA_DATASET_MISMATCH")
            if not _schema_matches(schema, lane):
                blockers.append("DBN_METADATA_SCHEMA_MISMATCH")
            supported, symbology_evidence = _symbology_supports(
                getattr(store, "symbology", None),
                raw_symbol=str(definition["raw_symbol"]),
                instrument_id=int(definition["instrument_id"]),
                session_day=str(source.get("day") or "").replace("-", ""),
            )
            if not supported:
                blockers.append("DBN_SYMBOLOGY_MAPPING_MISSING")
            record_evidence, record_blockers = _record_identity_scan(
                iter(store),
                lane=lane,
                definition=definition,
                source_id=source_id,
                require_explicit_text_identity=False,
            )
        else:
            metadata_evidence = {
                "dataset": str(definition["dataset"]),
                "schema": EXPECTED_SCHEMA[lane],
                "source_encoding": "decoded-jsonl",
            }
            symbology_evidence = {
                "raw_symbol": str(definition["raw_symbol"]),
                "instrument_id": int(definition["instrument_id"]),
                "identity_required_on_every_matching_row": True,
            }
            record_evidence, record_blockers = _record_identity_scan(
                normalize.iter_jsonl(path),
                lane=lane,
                definition=definition,
                source_id=source_id,
                require_explicit_text_identity=True,
            )
        blockers.extend(record_blockers)

        after_size = path.stat().st_size
        after_sha = _sha256(path)
        if (before_size, before_sha) != (after_size, after_sha):
            blockers.append("SOURCE_BYTES_CHANGED_DURING_IDENTITY_ATTESTATION")
    except Exception as error:
        if not blockers:
            blockers.append(f"IDENTITY_INSPECTION_FAILED:{type(error).__name__}")
        metadata_evidence.setdefault("error", str(error))

    blockers = sorted(set(blockers))
    row = {
        "source_id": source_id,
        "corpus_id": str(materialization.get("corpus_id") or ""),
        "lane": lane,
        "day": str(source.get("day") or "").replace("-", ""),
        "materialized_path": str(path),
        "definition_fingerprint": (
            str(definition_raw.get("definition_fingerprint") or "")
            if isinstance(definition_raw, Mapping)
            else ""
        ),
        "metadata_evidence": metadata_evidence,
        "metadata_evidence_fingerprint": _fp(metadata_evidence),
        "symbology_evidence": symbology_evidence,
        "symbology_evidence_fingerprint": _fp(symbology_evidence),
        "record_identity_evidence": record_evidence,
        "record_identity_evidence_fingerprint": _fp(record_evidence),
        "source_native_identity_attested": not blockers,
        "blockers": blockers,
        "identity_inferred_from_filename_or_s3_key": False,
    }
    row["identity_evidence_fingerprint"] = _fp(row)
    return row


def build_attestation(
    provenance_receipt: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    provenance_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = materializer_provenance.validate_gate,
    plan_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = inspection._validate_plan,
    store_loader: Callable[[Path], Any] = _load_dbn_store,
) -> dict[str, Any]:
    try:
        provenance = copy.deepcopy(dict(provenance_validator(provenance_receipt)))
    except Exception as error:
        raise CorpusSourceIdentityError(
            f"materializer provenance receipt is invalid: {error}"
        ) from error
    try:
        checked_plan = copy.deepcopy(dict(plan_validator(plan)))
    except Exception as error:
        raise CorpusSourceIdentityError(f"inspection plan is invalid: {error}") from error

    _authority(provenance, label="materializer provenance receipt")
    _authority(checked_plan, label="inspection plan", require_all=False)
    blockers: list[str] = []
    if provenance.get("status") != materializer_provenance.READY_STATUS:
        blockers.append("MATERIALIZER_PROVENANCE_NOT_READY")
    if list(provenance.get("blockers") or []):
        blockers.append("MATERIALIZER_PROVENANCE_HAS_BLOCKERS")
    if provenance.get("plan_fingerprint") != checked_plan.get("plan_fingerprint"):
        blockers.append("MATERIALIZER_PROVENANCE_PLAN_MISMATCH")

    materialized = _materialization_map(provenance)
    planned_sources: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for corpus in checked_plan.get("corpora") or []:
        lane = str(corpus.get("lane") or "")
        for source in corpus.get("sources") or []:
            source_id = str(source.get("source_id") or "")
            if source_id in planned_sources:
                raise CorpusSourceIdentityError(f"duplicate planned source {source_id}")
            planned_sources[source_id] = (lane, source)

    if set(planned_sources) != set(materialized):
        blockers.append("PLANNED_AND_MATERIALIZED_SOURCE_SET_MISMATCH")

    evidence: list[dict[str, Any]] = []
    for source_id in sorted(planned_sources):
        lane, source = planned_sources[source_id]
        row_materialization = materialized.get(source_id)
        if row_materialization is None:
            missing = {
                "source_id": source_id,
                "source_native_identity_attested": False,
                "blockers": ["MATERIALIZATION_EVIDENCE_MISSING"],
                "identity_inferred_from_filename_or_s3_key": False,
            }
            missing["identity_evidence_fingerprint"] = _fp(missing)
            evidence.append(missing)
            blockers.append(f"{source_id}:MATERIALIZATION_EVIDENCE_MISSING")
            continue
        row = inspect_source_identity(
            source,
            lane=lane,
            materialization=row_materialization,
            store_loader=store_loader,
        )
        evidence.append(row)
        blockers.extend(f"{source_id}:{item}" for item in row["blockers"])

    blockers = sorted(set(blockers))
    status = READY_STATUS if not blockers else BLOCKED_STATUS
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "materializer_provenance_receipt": provenance,
        "materializer_provenance_fingerprint": provenance.get("fingerprint"),
        "plan": checked_plan,
        "plan_fingerprint": checked_plan.get("plan_fingerprint"),
        "source_materializations_fingerprint": provenance.get(
            "source_materializations_fingerprint"
        ),
        "source_identity_evidence": evidence,
        "source_identity_evidence_fingerprint": _fp(evidence),
        "source_count": len(evidence),
        "all_source_native_identities_attested": status == READY_STATUS,
        "dataset_publisher_instrument_symbol_and_period_bound_to_source_bytes": (
            status == READY_STATUS
        ),
        "identity_inferred_from_filename_or_s3_key": False,
        "blockers": blockers,
        "next_action": (
            "RUN_BYTE_LEVEL_CORPUS_INSPECTION"
            if status == READY_STATUS
            else "REPAIR_SOURCE_NATIVE_IDENTITY_BLOCKERS_AND_STAND_DOWN"
        ),
        **_authority_fields(),
    }
    receipt["fingerprint"] = _fp(receipt)
    return receipt


def validate_attestation(
    value: Mapping[str, Any],
    *,
    provenance_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = materializer_provenance.validate_gate,
    plan_validator: Callable[[Mapping[str, Any]], Mapping[str, Any]] = inspection._validate_plan,
    store_loader: Callable[[Path], Any] = _load_dbn_store,
) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise CorpusSourceIdentityError(
            "source identity attestation schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="source identity attestation")
    provenance = checked.get("materializer_provenance_receipt")
    plan = checked.get("plan")
    if not isinstance(provenance, Mapping) or not isinstance(plan, Mapping):
        raise CorpusSourceIdentityError(
            "source identity attestation lacks embedded provenance or plan"
        )
    expected = build_attestation(
        provenance,
        plan,
        provenance_validator=provenance_validator,
        plan_validator=plan_validator,
        store_loader=store_loader,
    )
    if checked != expected:
        raise CorpusSourceIdentityError(
            "source identity attestation does not reconstruct deterministically"
        )
    return copy.deepcopy(dict(value))


def build_from_paths(*, provenance_path: Path, plan_path: Path, out: Path) -> dict[str, Any]:
    receipt = build_attestation(_load(provenance_path), _load(plan_path))
    _write(out, receipt)
    validate_attestation(receipt)
    return receipt


def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        allowed = root / "data"
        allowed.mkdir()
        corpora: list[dict[str, Any]] = []
        materializations: list[dict[str, Any]] = []
        for source_id, lane, corpus_id, day in (
            ("l1", "l1_trades", inspection.coverage.L1_CORPUS_ID, "20260313"),
            ("mbo", "mbo", inspection.coverage.MBO_CORPUS_ID, "20260313"),
        ):
            path = allowed / f"{source_id}.jsonl"
            row = {
                "event_type": "trade" if lane == "l1_trades" else "mbo",
                "dataset": inspection.DATASET,
                "publisher_id": 1,
                "instrument_id": 1008,
                "raw_symbol": "NGJ26",
                "definition_date": "20260313",
                "ts_event_s": 1.0,
                "source_sequence": 1,
                "side": "B",
                "price": 3.0,
                "size": 1,
                "action": "A" if lane == "mbo" else None,
                "order_id": 9,
            }
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            digest = _sha256(path)
            definition = inspection.definition_observation(
                dataset=inspection.DATASET,
                publisher_id=1,
                instrument_id=1008,
                raw_symbol="NGJ26",
                definition_date="20260313",
                definition_start_s=0.0,
                definition_end_s=2.0,
                observed_from=f"selftest:{source_id}",
                observed_at="2026-07-25T00:00:00Z",
                source_sha256=digest,
                source_size_bytes=path.stat().st_size,
            )
            expected = inspection.coverage.EXPECTED_WINDOWS[corpus_id]
            corpora.append(
                {
                    "corpus_id": corpus_id,
                    "lane": lane,
                    "declared_window": {
                        "start": expected["start"],
                        "end_exclusive": expected["end_exclusive"],
                    },
                    "publisher_id": 1,
                    "expected_days": [day],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "inventory_observed_at": "2026-07-25T00:00:00Z",
                    "sources": [
                        {
                            "source_id": source_id,
                            "day": day,
                            "lane": lane,
                            "materialized_path": str(path),
                            "location": f"s3://selftest/{source_id}",
                            "definition": definition,
                        }
                    ],
                }
            )
            materializations.append(
                {
                    "corpus_id": corpus_id,
                    "source_id": source_id,
                    "materialized_path": str(path),
                    "expected_size_bytes": path.stat().st_size,
                    "expected_sha256": digest,
                }
            )
        plan = {
            "schema": inspection.PLAN_SCHEMA,
            "market": "NG",
            "dataset": inspection.DATASET,
            "allowed_roots": [str(allowed)],
            "corpora": corpora,
            "identity_may_be_inferred_from_filename": False,
            "remote_presence_inferred": False,
            **inspection._base_authority(),
        }
        plan["plan_fingerprint"] = inspection._fp(plan)
        provenance = {
            "schema": materializer_provenance.SCHEMA,
            "status": materializer_provenance.READY_STATUS,
            "fingerprint": "p" * 64,
            "plan_fingerprint": plan["plan_fingerprint"],
            "source_materializations_fingerprint": _fp(materializations),
            "exact_materializer_receipt": {
                "source_materializations": materializations,
            },
            "blockers": [],
            **_authority_fields(),
        }
        result = build_attestation(
            provenance,
            plan,
            provenance_validator=lambda item: item,
        )
        assert result["status"] == READY_STATUS, result["blockers"]
        validate_attestation(
            result,
            provenance_validator=lambda item: item,
        )
    print("[ng_corpus_source_identity_attestation] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--provenance", type=Path, required=True)
    build.add_argument("--plan", type=Path, required=True)
    build.add_argument("--out", type=Path, required=True)
    subparsers.add_parser("selftest")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return _selftest()
    receipt = build_from_paths(
        provenance_path=args.provenance,
        plan_path=args.plan,
        out=args.out,
    )
    print(
        json.dumps(
            {"out": str(args.out), "status": receipt["status"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
