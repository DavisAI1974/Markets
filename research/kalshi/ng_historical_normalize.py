#!/usr/bin/env python3
"""Normalize historical Databento NG records for causal replay.

The replay layer consumes one deliberately small transport contract regardless of
whether the source is DBN, decoded JSONL, or a test fixture. Raw files are never
modified. Identity must be explicit: dataset, publisher, instrument, raw symbol,
definition date, and session day are carried on every normalized event.

DBN support is optional at import time. JSONL normalization and inventory remain
usable in credential-free CI environments where the ``databento`` package is not
installed. Large DBN files are streamed when the installed DBNStore supports
iteration; an ndarray fallback is used only for older clients.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

SCHEMA = "ng_normalized_event.v1"
PRICE_SCALE = 1_000_000_000.0
UNDEF_PRICE = 9_000_000_000_000_000_000
EVENT_TYPES = {"definition", "trade", "mbo"}
ACTION_MAP = {
    "ADD": "A", "A": "A",
    "MODIFY": "M", "M": "M",
    "CANCEL": "C", "C": "C",
    "CLEAR": "R", "RESET": "R", "R": "R",
    "TRADE": "T", "T": "T",
    "FILL": "F", "F": "F",
    "NONE": "N", "N": "N",
}
SIDE_MAP = {
    "BUY": "B", "BID": "B", "B": "B",
    "SELL": "A", "ASK": "A", "A": "A",
    "NONE": "N", "N": "N",
}


class NormalizeError(ValueError):
    """Raised when a raw record cannot safely enter causal replay."""


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


def _enum_text(value: Any) -> str:
    value = getattr(value, "name", value)
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    if isinstance(value, int) and 0 <= value <= 255:
        character = chr(value)
        if character.isprintable():
            value = character
    return str(value or "").strip().upper()


def event_seconds(value: Any) -> float:
    """Convert ISO/datetime or s/ms/us/ns numeric timestamps to Unix seconds."""
    value = getattr(value, "value", value)
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.timestamp()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise NormalizeError("empty timestamp")
        try:
            value = float(text)
        except ValueError:
            try:
                parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError as error:
                raise NormalizeError(f"invalid timestamp: {text!r}") from error
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.timestamp()
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise NormalizeError(f"invalid timestamp: {value!r}") from error
    if not math.isfinite(numeric) or numeric < 0:
        raise NormalizeError(f"invalid timestamp: {value!r}")
    magnitude = abs(numeric)
    if magnitude >= 1e17:
        numeric /= 1e9
    elif magnitude >= 1e14:
        numeric /= 1e6
    elif magnitude >= 1e11:
        numeric /= 1e3
    return numeric


def decimal_price(value: Any) -> float | None:
    """Convert Databento fixed-point prices while preserving decoded decimal prices."""
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise NormalizeError(f"invalid price: {value!r}") from error
    if not math.isfinite(numeric) or abs(numeric) >= UNDEF_PRICE:
        return None
    if abs(numeric) >= 10_000_000:
        numeric /= PRICE_SCALE
    return numeric


def _integer(value: Any, name: str, *, default: int | None = None) -> int:
    if value in (None, ""):
        if default is not None:
            return default
        raise NormalizeError(f"missing {name}")
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise NormalizeError(f"invalid {name}: {value!r}") from error


def _identity_value(
    record: Any,
    name: str,
    explicit: Any,
    *,
    aliases: tuple[str, ...] = (),
    coerce: Any = str,
) -> Any:
    """Use explicit manifest identity and reject contradictory decoded metadata.

    Generic transport labels such as ``symbol=NG`` are not allowed to override an
    explicit raw contract identity such as ``NGJ26``.
    """
    decoded = _value(record, name, *aliases, default=None)
    if explicit not in (None, ""):
        expected = coerce(explicit)
        if decoded not in (None, "") and coerce(decoded) != expected:
            raise NormalizeError(f"{name} mismatch: decoded {decoded!r} != explicit {explicit!r}")
        return expected
    if decoded in (None, ""):
        return None
    return coerce(decoded)


def classify_record(record: Any, forced: str | None = None) -> str:
    if forced:
        event_type = forced.lower()
    else:
        explicit = _value(record, "event_type", "schema_name", default="")
        event_type = str(explicit or "").lower()
        if event_type not in EVENT_TYPES:
            name = type(record).__name__.lower()
            if "definition" in name or "instrumentdef" in name:
                event_type = "definition"
            elif "mbo" in name or _value(record, "order_id", default=None) is not None:
                event_type = "mbo"
            elif "trade" in name:
                event_type = "trade"
    if event_type not in EVENT_TYPES:
        raise NormalizeError(
            "record type is ambiguous; pass --kind definition, trade, or mbo rather than guessing from rtype"
        )
    return event_type


def record_matches_kind(record: Any, kind: str) -> bool:
    """Return whether a mixed decoded row belongs in the requested replay lane.

    Dedicated trades-schema rows often omit ``action`` and therefore match the
    trade lane. Mixed MBP/MBO rows match the trade lane only for action T.
    """
    if kind == "definition":
        return True
    action_raw = _value(record, "action", default=None)
    if kind == "trade":
        if action_raw in (None, ""):
            return True
        return ACTION_MAP.get(_enum_text(action_raw)) == "T"
    if kind == "mbo":
        return action_raw not in (None, "") or _value(record, "order_id", default=None) is not None
    return False


def normalize_record(
    record: Any,
    *,
    event_type: str | None = None,
    dataset: str | None = None,
    publisher_id: int | None = None,
    instrument_id: int | None = None,
    raw_symbol: str | None = None,
    definition_date: str | None = None,
    session_day: str | None = None,
    source_id: str | None = None,
    ingest_sequence: int = 0,
) -> dict[str, Any]:
    """Normalize one decoded record without mutating the input."""
    kind = classify_record(record, event_type)
    timestamp = event_seconds(_value(record, "ts_event_s", "ts_event", "timestamp", "ts", "ts_recv"))

    dataset_value = _identity_value(record, "dataset", dataset, coerce=str)
    publisher_value = _identity_value(record, "publisher_id", publisher_id, coerce=int)
    instrument_value = _identity_value(record, "instrument_id", instrument_id, coerce=int)
    # Only raw_symbol is authoritative decoded contract identity. A generic
    # legacy ``symbol`` field may be used only when no explicit raw symbol exists.
    raw_aliases = ("symbol",) if raw_symbol in (None, "") else ()
    raw_symbol_value = _identity_value(record, "raw_symbol", raw_symbol, aliases=raw_aliases, coerce=str)
    definition_value = _identity_value(record, "definition_date", definition_date, coerce=str)
    session_value = _identity_value(record, "session_day", session_day, coerce=str)

    identity = {
        "dataset": dataset_value or "",
        "publisher_id": publisher_value,
        "instrument_id": instrument_value,
        "raw_symbol": raw_symbol_value or "",
        "definition_date": definition_value or "",
        "session_day": session_value or "",
    }
    missing = [
        key for key in ("dataset", "publisher_id", "instrument_id", "raw_symbol", "definition_date", "session_day")
        if identity[key] in (None, "", 0)
    ]
    if missing:
        raise NormalizeError("missing identity: " + ", ".join(missing))

    normalized: dict[str, Any] = {
        **identity,
        "schema": SCHEMA,
        "event_type": kind,
        "ts_event_s": timestamp,
        "source_sequence": _integer(
            _value(record, "source_sequence", "sequence", "sequence_number", default=ingest_sequence),
            "source_sequence",
            default=ingest_sequence,
        ),
        "ingest_sequence": int(ingest_sequence),
        "source_id": str(source_id or _value(record, "source_id", default="") or ""),
    }

    if kind == "definition":
        return normalized

    if kind == "trade":
        side_text = _enum_text(_value(record, "side"))
        side = SIDE_MAP.get(side_text)
        if side not in {"B", "A"}:
            raise NormalizeError(f"unmapped trade side: {side_text!r}")
        price = decimal_price(_value(record, "price", "px"))
        if price is None:
            raise NormalizeError("trade price is undefined")
        try:
            size = float(_value(record, "size", "quantity", "qty"))
        except (TypeError, ValueError, OverflowError) as error:
            raise NormalizeError("trade size is invalid") from error
        if not math.isfinite(size) or size <= 0:
            raise NormalizeError("trade size must be positive")
        normalized.update(price=price, size=size, side=side)
        return normalized

    action_text = _enum_text(_value(record, "action"))
    action = ACTION_MAP.get(action_text)
    if action is None:
        raise NormalizeError(f"unmapped MBO action: {action_text!r}")
    side_text = _enum_text(_value(record, "side", default="N"))
    side = SIDE_MAP.get(side_text)
    if side is None:
        raise NormalizeError(f"unmapped MBO side: {side_text!r}")
    price = decimal_price(_value(record, "price", "px"))
    if action in {"A", "M"} and price is None:
        raise NormalizeError(f"MBO {action} requires a price")
    try:
        size = float(_value(record, "size", "quantity", "qty", default=0) or 0)
    except (TypeError, ValueError, OverflowError) as error:
        raise NormalizeError("MBO size is invalid") from error
    if not math.isfinite(size) or size < 0:
        raise NormalizeError("MBO size cannot be negative")
    normalized.update(
        action=action,
        side=side,
        size=size,
        order_id=_integer(_value(record, "order_id", default=0), "order_id", default=0),
        price=price,
        flags=_integer(_value(record, "flags", default=0), "flags", default=0),
    )
    return normalized


def _record_to_mapping(record: Any) -> Any:
    dtype = getattr(record, "dtype", None)
    names = getattr(dtype, "names", None)
    if names:
        return {name: record[name].item() if hasattr(record[name], "item") else record[name] for name in names}
    return record


def iter_dbn(path: Path) -> Iterator[Any]:
    try:
        import databento as db  # type: ignore
    except ImportError as error:
        raise NormalizeError("DBN input requires the optional databento package") from error
    store = db.DBNStore.from_file(str(path))
    # Prefer streaming. Materializing a multi-gigabyte MBO store to ndarray can
    # exceed memory and invalidates the historical-first bounded-memory design.
    try:
        iterator = iter(store)
    except TypeError:
        iterator = None
    if iterator is not None:
        for record in iterator:
            yield _record_to_mapping(record)
        return
    if hasattr(store, "to_ndarray"):
        for record in store.to_ndarray():
            yield _record_to_mapping(record)
        return
    raise NormalizeError("installed databento DBNStore has no supported streaming/array interface")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise NormalizeError(f"{path}:{line_number}: {error}") from error
            if not isinstance(row, dict):
                raise NormalizeError(f"{path}:{line_number}: expected JSON object")
            yield row


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_file(
    path: Path,
    *,
    kind: str,
    dataset: str,
    publisher_id: int,
    raw_symbol: str,
    instrument_id: int,
    definition_date: str,
    session_day: str,
    output: Path,
    skip_nonmatching: bool = False,
) -> dict[str, Any]:
    if not path.exists():
        raise NormalizeError(f"input does not exist: {path}")
    is_dbn = path.suffix.lower() in {".dbn", ".zst"} or path.name.lower().endswith(".dbn.zst")
    rows: Iterable[Any] = iter_dbn(path) if is_dbn else iter_jsonl(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    input_count = 0
    normalized_count = 0
    skipped = 0
    first: float | None = None
    last: float | None = None
    previous: tuple[float, int, int] | None = None
    try:
        with temp.open("w", encoding="utf-8") as handle:
            for input_count, raw in enumerate(rows, 1):
                if not record_matches_kind(raw, kind):
                    if skip_nonmatching:
                        skipped += 1
                        continue
                    raise NormalizeError(f"record {input_count} does not match requested kind {kind}")
                event = normalize_record(
                    raw,
                    event_type=kind,
                    dataset=dataset,
                    publisher_id=publisher_id,
                    instrument_id=instrument_id,
                    raw_symbol=raw_symbol,
                    definition_date=definition_date,
                    session_day=session_day,
                    source_id=str(path),
                    ingest_sequence=input_count,
                )
                key = (
                    float(event["ts_event_s"]),
                    int(event["source_sequence"]),
                    int(event["ingest_sequence"]),
                )
                if previous is not None and key < previous:
                    raise NormalizeError(f"source moved backwards at input record {input_count}")
                previous = key
                normalized_count += 1
                first = float(event["ts_event_s"]) if first is None else first
                last = float(event["ts_event_s"])
                handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if normalized_count == 0:
            raise NormalizeError("input contained zero matching records")
        os.replace(temp, output)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return {
        "schema": "ng_normalization_report.v1",
        "input": str(path),
        "output": str(output),
        "event_type": kind,
        "input_record_count": input_count,
        "record_count": normalized_count,
        "skipped_nonmatching": skipped,
        "event_start_s": first,
        "event_end_s": last,
        "size_bytes": output.stat().st_size,
        "sha256": _sha256(output),
        "identity": {
            "dataset": dataset,
            "publisher_id": publisher_id,
            "instrument_id": instrument_id,
            "raw_symbol": raw_symbol,
            "definition_date": definition_date,
            "session_day": session_day,
        },
        "raw_input_untouched": True,
        "execution_authority": False,
    }


def selftest() -> int:
    base = {
        "dataset": "GLBX.MDP3", "publisher_id": 1, "instrument_id": 1008,
        "raw_symbol": "NGJ26", "definition_date": "2026-03-01", "session_day": "20260316",
    }
    trade = normalize_record(
        {**base, "event_type": "trade", "ts_event": 1_700_000_000_000_000_000,
         "price": 3_123_000_000, "size": 2, "side": "B", "sequence": 7},
        ingest_sequence=1,
    )
    assert trade["ts_event_s"] == 1_700_000_000.0
    assert trade["price"] == 3.123 and trade["side"] == "B"
    legacy = normalize_record(
        {"symbol": "NG", "ts": 1.0, "price": 3.0, "size": 1, "side": "A",
         "instrument_id": 1008},
        event_type="trade", dataset="GLBX.MDP3", publisher_id=1, instrument_id=1008,
        raw_symbol="NGJ26", definition_date="2026-03-01", session_day="20260316",
    )
    assert legacy["raw_symbol"] == "NGJ26"
    mbo = normalize_record(
        {**base, "event_type": "mbo", "ts_event_s": 1.0, "action": "Cancel", "side": "Bid",
         "size": 1, "order_id": 4, "flags": 128, "price": 3.0},
        ingest_sequence=2,
    )
    assert mbo["action"] == "C" and mbo["side"] == "B"
    assert record_matches_kind({"action": "A"}, "trade") is False
    assert record_matches_kind({"action": "T"}, "trade") is True
    print("[ng_historical_normalize] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize historical NG DBN/JSONL for deterministic replay")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--kind", choices=sorted(EVENT_TYPES))
    parser.add_argument("--dataset", default="GLBX.MDP3")
    parser.add_argument("--publisher-id", type=int)
    parser.add_argument("--instrument-id", type=int)
    parser.add_argument("--raw-symbol")
    parser.add_argument("--definition-date")
    parser.add_argument("--session-day")
    parser.add_argument("--skip-nonmatching", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = {
        "input": args.input, "output": args.output, "kind": args.kind,
        "publisher_id": args.publisher_id, "instrument_id": args.instrument_id,
        "raw_symbol": args.raw_symbol, "definition_date": args.definition_date,
        "session_day": args.session_day,
    }
    missing = [name for name, value in required.items() if value in (None, "")]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))
    report = normalize_file(
        args.input, kind=args.kind, dataset=args.dataset, publisher_id=args.publisher_id,
        raw_symbol=args.raw_symbol, instrument_id=args.instrument_id,
        definition_date=args.definition_date, session_day=args.session_day, output=args.output,
        skip_nonmatching=args.skip_nonmatching,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
