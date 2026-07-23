"""Low-level exact NG definition-source inspection helpers."""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import ng_corpus_inspection as inspection
import ng_historical_normalize as normalize

SOURCE_SCHEMA = "ng_definition_source_receipt.v1"
EXACT_NG_RE = re.compile(r"^NG[A-Z][0-9]{2}$")
START_FIELDS = ("definition_start_s", "activation", "activation_ns", "activation_ts", "activation_time", "valid_from", "valid_from_s", "start_ts", "start_time")
END_FIELDS = ("definition_end_s", "expiration", "expiration_ns", "expiration_ts", "expiration_time", "valid_to", "valid_to_s", "end_ts", "end_time")


class DefinitionObservationError(ValueError):
    """Definition evidence is missing, contradictory, or tampered."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def fp(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def value(record: Any, *names: str, default: Any = None) -> Any:
    if isinstance(record, Mapping):
        for name in names:
            if name in record:
                return record[name]
        return default
    for name in names:
        if hasattr(record, name):
            return getattr(record, name)
    return default


def text(item: Any) -> str:
    item = getattr(item, "name", item)
    if isinstance(item, bytes):
        item = item.decode("ascii", errors="replace")
    return str(item or "").strip().rstrip("\x00").strip()


def positive_int(item: Any, label: str) -> int:
    if isinstance(item, bool):
        raise DefinitionObservationError(f"{label} must be a positive integer")
    try:
        number = int(item)
    except (TypeError, ValueError, OverflowError) as error:
        raise DefinitionObservationError(f"{label} must be a positive integer") from error
    if number <= 0:
        raise DefinitionObservationError(f"{label} must be a positive integer")
    return number


def timestamp(item: Any, label: str) -> float:
    try:
        number = float(normalize.event_seconds(item))
    except Exception as error:
        raise DefinitionObservationError(f"{label} is not a valid timestamp") from error
    if not math.isfinite(number) or number < 0:
        raise DefinitionObservationError(f"{label} is not a valid timestamp")
    return number


def first_present(record: Any, fields: Sequence[str]) -> Any:
    for field in fields:
        item = value(record, field, default=None)
        if item not in (None, ""):
            return item
    return None


def is_dbn(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(".dbn") or name.endswith(".dbn.zst") or path.suffix.lower() == ".zst"


def iter_records(path: Path) -> Iterable[Any]:
    return normalize.iter_dbn(path) if is_dbn(path) else normalize.iter_jsonl(path)


def transport_metadata(path: Path) -> dict[str, str]:
    if not is_dbn(path):
        return {"dataset": "", "source_schema": ""}
    try:
        import databento as db  # type: ignore
    except ImportError:
        return {"dataset": "", "source_schema": ""}
    metadata = getattr(db.DBNStore.from_file(str(path)), "metadata", None)
    return {"dataset": text(getattr(metadata, "dataset", "")), "source_schema": text(getattr(metadata, "schema", ""))}


def authority() -> dict[str, Any]:
    return {
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "identity_inferred_from_filename": False,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def validate_authority(item: Mapping[str, Any], label: str) -> None:
    false_fields = ("actual_outcomes_used", "paid_live_data_assumed", "identity_inferred_from_filename", "may_change_blind_forecast", "may_change_posterior", "may_update_ng_brain", "execution_authority", "options_lane_started")
    for field in false_fields:
        if item.get(field) is not False:
            raise DefinitionObservationError(f"{label}: {field} must remain false")
    if item.get("cme_event_contracts_mode") != "SHADOW":
        raise DefinitionObservationError(f"{label}: CME event contracts must remain SHADOW")
    if item.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise DefinitionObservationError(f"{label}: brokerage contract must be tastytrade_not_ibkr")


def verify(item: Mapping[str, Any], field: str, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(item)); observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != fp(payload):
        raise DefinitionObservationError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(item))


def validate_observed_at(item: str) -> str:
    item = str(item or "").strip()
    if not item:
        raise DefinitionObservationError("observed_at is required")
    try:
        parsed = dt.datetime.fromisoformat(item.replace("Z", "+00:00"))
    except ValueError as error:
        raise DefinitionObservationError("observed_at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise DefinitionObservationError("observed_at must include a timezone")
    return item


def definition_date(record: Any, event_s: float) -> str:
    explicit = text(value(record, "definition_date", default=""))
    if not explicit:
        return dt.datetime.fromtimestamp(event_s, tz=dt.timezone.utc).strftime("%Y%m%d")
    compact = explicit.replace("-", "")
    if len(compact) != 8 or not compact.isdigit():
        raise DefinitionObservationError("definition_date must be YYYYMMDD or YYYY-MM-DD")
    return compact


def extract_candidate(record: Any, *, transport: Mapping[str, str], path: Path, observed_at: str, source_sha: str, source_size: int) -> dict[str, Any] | None:
    symbol = text(value(record, "raw_symbol", default="")).upper()
    if not EXACT_NG_RE.fullmatch(symbol):
        return None
    event_type = text(value(record, "event_type", default="")).lower()
    source_schema = text(value(record, "source_schema", "schema_name", "databento_schema", default="")) or text(transport.get("source_schema", ""))
    schema_key = source_schema.lower().replace("_", "-")
    if event_type and event_type != "definition":
        raise DefinitionObservationError(f"exact contract {symbol} record is not definition evidence: {event_type!r}")
    if source_schema and "definition" not in schema_key and "instrument-def" not in schema_key:
        raise DefinitionObservationError(f"exact contract {symbol} source schema is not definition: {source_schema!r}")
    if not event_type and not source_schema:
        raise DefinitionObservationError(f"exact contract {symbol} lacks definition event/schema evidence")
    row_dataset, header_dataset = text(value(record, "dataset", default="")), text(transport.get("dataset", ""))
    if row_dataset and header_dataset and row_dataset != header_dataset:
        raise DefinitionObservationError(f"dataset mismatch in {path}: row {row_dataset!r} != header {header_dataset!r}")
    dataset = row_dataset or header_dataset
    if not dataset:
        raise DefinitionObservationError(f"dataset is unobserved for exact contract {symbol}")
    if dataset != inspection.DATASET:
        raise DefinitionObservationError(f"exact contract {symbol} dataset {dataset!r} != {inspection.DATASET!r}")
    publisher = positive_int(value(record, "publisher_id", default=None), f"{symbol} publisher_id")
    instrument = positive_int(value(record, "instrument_id", default=None), f"{symbol} instrument_id")
    event_s = timestamp(first_present(record, ("ts_event_s", "ts_event", "timestamp", "ts", "ts_recv")), f"{symbol} definition event time")
    start_raw, end_raw = first_present(record, START_FIELDS), first_present(record, END_FIELDS)
    if start_raw in (None, "") or end_raw in (None, ""):
        raise DefinitionObservationError(f"exact contract {symbol} is missing activation/expiration definition bounds")
    start_s, end_s = timestamp(start_raw, f"{symbol} definition start"), timestamp(end_raw, f"{symbol} definition end")
    if end_s < start_s:
        raise DefinitionObservationError(f"exact contract {symbol} definition period is backwards")
    observed = inspection.definition_observation(dataset=dataset, publisher_id=publisher, instrument_id=instrument, raw_symbol=symbol, definition_date=definition_date(record, event_s), definition_start_s=start_s, definition_end_s=end_s, observed_from=str(path), observed_at=observed_at, source_sha256=source_sha, source_size_bytes=source_size)
    return {"definition": observed, "definition_event_s": event_s, "source_schema": source_schema}


def identity_key(definition: Mapping[str, Any]) -> tuple[Any, ...]:
    return (definition["dataset"], int(definition["publisher_id"]), int(definition["instrument_id"]), definition["raw_symbol"], float(definition["definition_start_s"]), float(definition["definition_end_s"]))
