#!/usr/bin/env python3
"""Attest exact identity and definition-time bounds in prepared G15 replay events.

The broad corpus, exact-pair catalog, and source-native identity gates prove which raw
objects may be used. This gate verifies the normalized files that will actually enter
``ng_historical_replay``. Every row must preserve dataset, publisher, instrument, raw
symbol, definition date, session day, lane type, chronological event time, and the
manifest definition/event period. Definitions must be present before trade/MBO replay.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from ng_g15_replay_manifest_bridge import validate_bridge_output
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, SOURCE_KINDS
from ng_historical_prepare import validate_prepared_index
from ng_historical_replay import validate_normalized_event

SCHEMA = "ng_g15_prepared_normalized_identity_guard.v1"
READY = "G15_PREPARED_NORMALIZED_IDENTITY_AND_TIME_ATTESTED"
BLOCKED = "G15_PREPARED_NORMALIZED_IDENTITY_AND_TIME_BLOCKED"
EXPECTED_SOURCE_COUNT = len(G15_DATES) * len(SOURCE_KINDS) + 2
LANE_EVENT_TYPE = {"l1_trades": "trade", "mbo": "mbo"}


class PreparedNormalizedIdentityGuardError(ValueError):
    """Raised when a guard artifact is malformed or cannot be reconstructed."""


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


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise PreparedNormalizedIdentityGuardError(f"invalid {name}: {value!r}") from error
    if not math.isfinite(result):
        raise PreparedNormalizedIdentityGuardError(f"invalid {name}: {value!r}")
    return result


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise PreparedNormalizedIdentityGuardError(f"invalid {name}: {value!r}")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise PreparedNormalizedIdentityGuardError(f"invalid {name}: {value!r}") from error
    if result <= 0:
        raise PreparedNormalizedIdentityGuardError(f"{name} must be positive")
    return result


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise PreparedNormalizedIdentityGuardError(
                    f"{path}:{line_number}: invalid JSON: {error}"
                ) from error
            if not isinstance(row, dict):
                raise PreparedNormalizedIdentityGuardError(
                    f"{path}:{line_number}: normalized row must be an object"
                )
            yield row


def _identity(value: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(value.get("dataset") or ""),
        value.get("publisher_id"),
        int(value.get("instrument_id") or 0),
        str(value.get("raw_symbol") or ""),
        str(value.get("definition_date") or ""),
    )


def _manifest_entries(manifest: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in manifest.get("entries") or []:
        row = copy.deepcopy(dict(raw))
        key = (str(row.get("day") or ""), str(row.get("source_kind") or ""))
        if key in rows:
            raise PreparedNormalizedIdentityGuardError(f"duplicate manifest lane: {key}")
        rows[key] = row
    expected = {(day, lane) for day in G15_DATES for lane in SOURCE_KINDS}
    if set(rows) != expected:
        raise PreparedNormalizedIdentityGuardError(
            f"manifest lane set mismatch; missing={sorted(expected - set(rows))} "
            f"extra={sorted(set(rows) - expected)}"
        )
    return rows


def _definition_rows(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    definitions = dict(manifest.get("definitions") or {})
    result: dict[str, dict[str, Any]] = {}
    for symbol in ("NGJ26", "NGK26"):
        definition = copy.deepcopy(dict(definitions.get(symbol) or {}))
        required = (
            "dataset",
            "publisher_id",
            "instrument_id",
            "raw_symbol",
            "definition_date",
            "definition_start_s",
            "definition_end_s",
        )
        missing = [name for name in required if definition.get(name) in (None, "")]
        if missing:
            raise PreparedNormalizedIdentityGuardError(
                f"{symbol} definition missing: {', '.join(missing)}"
            )
        _positive_int(definition["publisher_id"], f"{symbol}.publisher_id")
        result[symbol] = definition
    return result


def _source_key(source: Mapping[str, Any]) -> tuple[str, str]:
    return str(source.get("day") or ""), str(source.get("source_kind") or "")


def _scan_source(
    source: Mapping[str, Any],
    *,
    expected_identity: tuple[Any, ...],
    expected_day: str,
    expected_event_type: str,
    definition_start_s: float,
    definition_end_s: float,
    event_start_s: float,
    event_end_s: float,
) -> tuple[dict[str, Any], list[str]]:
    path = Path(str(source.get("path") or ""))
    blockers: list[str] = []
    if not path.is_file():
        return {"path": str(path), "record_count": 0}, ["PREPARED_SOURCE_FILE_MISSING"]
    actual_size = path.stat().st_size
    actual_sha = _sha256(path)
    if actual_size != int(source.get("size_bytes") or -1):
        blockers.append("PREPARED_SOURCE_SIZE_MISMATCH")
    if actual_sha != str(source.get("sha256") or ""):
        blockers.append("PREPARED_SOURCE_SHA256_MISMATCH")

    count = 0
    first_event: float | None = None
    last_event: float | None = None
    prior_key: tuple[float, int, int] | None = None
    row_fingerprints: list[str] = []
    for line_number, raw in enumerate(_iter_jsonl(path), 1):
        count += 1
        try:
            row = validate_normalized_event(copy.deepcopy(raw))
        except Exception as error:
            blockers.append(f"NORMALIZED_EVENT_INVALID:{line_number}:{error}")
            continue
        if row.get("event_type") != expected_event_type:
            blockers.append(f"NORMALIZED_EVENT_TYPE_MISMATCH:{line_number}")
        if _identity(row) != expected_identity:
            blockers.append(f"NORMALIZED_IDENTITY_MISMATCH:{line_number}")
        try:
            _positive_int(row.get("publisher_id"), f"row {line_number} publisher_id")
        except PreparedNormalizedIdentityGuardError:
            blockers.append(f"NORMALIZED_PUBLISHER_MISSING:{line_number}")
        if str(row.get("session_day") or "") != expected_day:
            blockers.append(f"NORMALIZED_SESSION_DAY_MISMATCH:{line_number}")
        event_time = _finite(row.get("ts_event_s"), f"row {line_number} ts_event_s")
        if event_time < definition_start_s or event_time > definition_end_s:
            blockers.append(f"EVENT_OUTSIDE_DEFINITION_PERIOD:{line_number}")
        if event_time < event_start_s or event_time > event_end_s:
            blockers.append(f"EVENT_OUTSIDE_SELECTED_LANE_COVERAGE:{line_number}")
        key = (
            event_time,
            int(row.get("source_sequence") or 0),
            int(row.get("ingest_sequence") or 0),
        )
        if prior_key is not None and key < prior_key:
            blockers.append(f"NORMALIZED_SOURCE_NOT_CHRONOLOGICAL:{line_number}")
        prior_key = key
        first_event = event_time if first_event is None else first_event
        last_event = event_time
        row_fingerprints.append(_fingerprint(row))

    if count != int(source.get("record_count") or -1):
        blockers.append("NORMALIZED_RECORD_COUNT_MISMATCH")
    if count <= 0:
        blockers.append("NORMALIZED_SOURCE_EMPTY")
    return (
        {
            "path": str(path),
            "size_bytes": actual_size,
            "sha256": actual_sha,
            "record_count": count,
            "first_event_s": first_event,
            "last_event_s": last_event,
            "row_fingerprints_fingerprint": _fingerprint(row_fingerprints),
        },
        blockers,
    )


def build_guard(
    bridge: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    *,
    verify_files: bool = True,
) -> dict[str, Any]:
    originals = copy.deepcopy((bridge, prepared_index))
    validate_bridge_output(copy.deepcopy(dict(bridge)))
    validate_prepared_index(copy.deepcopy(dict(prepared_index)), verify_files=verify_files)
    manifest = copy.deepcopy(dict(bridge.get("manifest") or {}))
    entries = _manifest_entries(manifest)
    definitions = _definition_rows(manifest)
    sources = [copy.deepcopy(dict(row)) for row in prepared_index.get("sources") or []]
    blockers: list[str] = []
    evidence: list[dict[str, Any]] = []

    if int(prepared_index.get("source_count") or 0) != EXPECTED_SOURCE_COUNT:
        blockers.append("PREPARED_SOURCE_COUNT_MISMATCH")
    if len(sources) != EXPECTED_SOURCE_COUNT:
        blockers.append("PREPARED_SOURCE_LIST_COUNT_MISMATCH")

    definition_sources = [row for row in sources if row.get("source_kind") == "definition"]
    lane_sources = [row for row in sources if row.get("source_kind") in SOURCE_KINDS]
    if len(definition_sources) != 2:
        blockers.append("PREPARED_DEFINITION_SOURCE_COUNT_MISMATCH")
    expected_lane_keys = {(day, lane) for day in G15_DATES for lane in SOURCE_KINDS}
    observed_lane_keys = [_source_key(row) for row in lane_sources]
    if set(observed_lane_keys) != expected_lane_keys or len(observed_lane_keys) != len(set(observed_lane_keys)):
        blockers.append("PREPARED_LANE_SET_MISMATCH")

    seen_definition_identities: set[tuple[Any, ...]] = set()
    for source in definition_sources:
        path = Path(str(source.get("path") or ""))
        rows = list(_iter_jsonl(path)) if verify_files and path.is_file() else []
        local_blockers: list[str] = []
        if verify_files and len(rows) != 1:
            local_blockers.append("DEFINITION_SOURCE_MUST_HAVE_ONE_ROW")
        if rows:
            row = rows[0]
            symbol = str(row.get("raw_symbol") or "")
            definition = definitions.get(symbol)
            if definition is None:
                local_blockers.append("UNEXPECTED_DEFINITION_SYMBOL")
            else:
                expected = _identity(definition)
                if _identity(row) != expected:
                    local_blockers.append("DEFINITION_IDENTITY_MISMATCH")
                if row.get("event_type") != "definition":
                    local_blockers.append("DEFINITION_EVENT_TYPE_MISMATCH")
                event_time = _finite(row.get("ts_event_s"), "definition ts_event_s")
                if abs(event_time - _finite(definition["definition_start_s"], "definition_start_s")) > 1e-9:
                    local_blockers.append("DEFINITION_TIMESTAMP_MISMATCH")
                seen_definition_identities.add(expected)
        evidence.append(
            {
                "day": source.get("day"),
                "source_kind": "definition",
                "path": str(path),
                "blockers": sorted(set(local_blockers)),
            }
        )
        blockers.extend(local_blockers)

    for source in sorted(lane_sources, key=_source_key):
        day, lane = _source_key(source)
        entry = entries.get((day, lane))
        local_blockers: list[str] = []
        scan: dict[str, Any] = {"path": str(source.get("path") or ""), "record_count": 0}
        if entry is None:
            local_blockers.append("PREPARED_LANE_NOT_IN_MANIFEST")
        else:
            expected = _identity(entry)
            if expected not in seen_definition_identities and verify_files:
                local_blockers.append("DEFINITION_NOT_PREPARED_BEFORE_LANE")
            if verify_files:
                scan, scan_blockers = _scan_source(
                    source,
                    expected_identity=expected,
                    expected_day=day,
                    expected_event_type=LANE_EVENT_TYPE[lane],
                    definition_start_s=_finite(entry["definition_start_s"], "definition_start_s"),
                    definition_end_s=_finite(entry["definition_end_s"], "definition_end_s"),
                    event_start_s=_finite(entry["event_start_s"], "event_start_s"),
                    event_end_s=_finite(entry["event_end_s"], "event_end_s"),
                )
                local_blockers.extend(scan_blockers)
        evidence.append(
            {
                "day": day,
                "source_kind": lane,
                **scan,
                "blockers": sorted(set(local_blockers)),
            }
        )
        blockers.extend(local_blockers)

    unique_blockers = sorted(set(blockers))
    result = {
        "schema": SCHEMA,
        "status": READY if not unique_blockers else BLOCKED,
        "market": "NG",
        "group": 15,
        "authority": "PREPARED_NORMALIZED_REPLAY_INPUT_AUDIT_ONLY",
        "execution_authority": False,
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "bridge": copy.deepcopy(dict(bridge)),
        "prepared_index": copy.deepcopy(dict(prepared_index)),
        "bridge_fingerprint": bridge.get("fingerprint"),
        "manifest_fingerprint": _fingerprint(manifest),
        "prepared_corpus_fingerprint": prepared_index.get("prepared_corpus_fingerprint"),
        "expected_source_count": EXPECTED_SOURCE_COUNT,
        "source_count": len(sources),
        "all_publishers_explicit_and_positive": not any(
            "PUBLISHER" in blocker for blocker in unique_blockers
        ),
        "all_rows_match_exact_manifest_identity": not any(
            "IDENTITY" in blocker or "SESSION_DAY" in blocker for blocker in unique_blockers
        ),
        "all_events_within_definition_and_lane_periods": not any(
            "OUTSIDE" in blocker or "TIMESTAMP" in blocker for blocker in unique_blockers
        ),
        "all_sources_chronological": not any(
            "NOT_CHRONOLOGICAL" in blocker for blocker in unique_blockers
        ),
        "definitions_precede_trade_and_mbo_replay": not any(
            "DEFINITION_NOT_PREPARED" in blocker for blocker in unique_blockers
        ),
        "source_evidence": evidence,
        "source_evidence_fingerprint": _fingerprint(evidence),
        "blockers": unique_blockers,
        "next_action": (
            "RUN_EXACT_G15_CAUSAL_REPLAY"
            if not unique_blockers
            else "REPAIR_PREPARED_NORMALIZED_IDENTITY_OR_TIME_BLOCKERS_AND_STAND_DOWN"
        ),
    }
    result["fingerprint"] = _fingerprint(result)
    if (bridge, prepared_index) != originals:
        raise PreparedNormalizedIdentityGuardError("guard mutated an input artifact")
    validate_guard(result, verify_files=verify_files)
    return result


def validate_guard(guard: Mapping[str, Any], *, verify_files: bool = True) -> None:
    value = copy.deepcopy(dict(guard))
    observed = value.pop("fingerprint", None)
    if value.get("schema") != SCHEMA or observed != _fingerprint(value):
        raise PreparedNormalizedIdentityGuardError("guard schema or fingerprint mismatch")
    if value.get("status") not in {READY, BLOCKED}:
        raise PreparedNormalizedIdentityGuardError("guard status is invalid")
    for field in (
        "execution_authority",
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise PreparedNormalizedIdentityGuardError(f"guard must keep {field}=false")
    if value.get("one_signal_authority_preserved") is not True:
        raise PreparedNormalizedIdentityGuardError("single signal authority must remain preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise PreparedNormalizedIdentityGuardError("blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise PreparedNormalizedIdentityGuardError("CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise PreparedNormalizedIdentityGuardError("brokerage must remain tastytrade, not IBKR")
    if value.get("source_evidence_fingerprint") != _fingerprint(value.get("source_evidence") or []):
        raise PreparedNormalizedIdentityGuardError("source evidence fingerprint mismatch")
    if verify_files:
        rebuilt = build_guard(value["bridge"], value["prepared_index"], verify_files=True)
        if rebuilt != dict(guard):
            raise PreparedNormalizedIdentityGuardError("guard is not the deterministic rebuild")


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "source.jsonl"
        identity = {
            "schema": "ng_normalized_event.v1",
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
            "session_day": "20260316",
            "event_type": "trade",
            "ts_event_s": 10.0,
            "source_sequence": 1,
            "ingest_sequence": 1,
            "price": 3.0,
            "size": 1,
            "side": "B",
        }
        path.write_text(_canonical(identity) + "\n", encoding="utf-8")
        source = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "record_count": 1,
        }
        evidence, blockers = _scan_source(
            source,
            expected_identity=("GLBX.MDP3", 1, 1008, "NGJ26", "2026-03-01"),
            expected_day="20260316",
            expected_event_type="trade",
            definition_start_s=0.0,
            definition_end_s=20.0,
            event_start_s=1.0,
            event_end_s=20.0,
        )
        assert evidence["record_count"] == 1 and blockers == []
    print("[ng_g15_prepared_normalized_identity_guard] selftest PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", nargs="?")
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--prepared-index", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.bridge or not args.prepared_index or not args.out:
        parser.error("--bridge, --prepared-index, and --out are required")
    result = build_guard(
        json.loads(args.bridge.read_text(encoding="utf-8")),
        json.loads(args.prepared_index.read_text(encoding="utf-8")),
    )
    _atomic_json(args.out, result)
    print(json.dumps({"out": str(args.out), "status": result["status"]}, sort_keys=True))
    return 0 if result["status"] == READY else 2


if __name__ == "__main__":
    raise SystemExit(main())
