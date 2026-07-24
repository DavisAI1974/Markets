#!/usr/bin/env python3
"""Verify exact L1/dense-trades and MBO alignment across the full shared corpus window.

The broad-scope gate proves that the one-year L1/dense-trades inventory and the
spring/summer MBO inventory are present and byte inspected. It does not prove that
every day shared by the two corpora can be joined on the exact dataset, publisher,
instrument, raw symbol, observed definition period, and event time. This gate is the
fail-closed bridge between broad-scope verification and exact G15 replay.

Every expected MBO day must also exist in the L1 corpus. All inspected sources for a
shared day must resolve to one exact identity partition, every source must participate
in at least one positive-duration cross-lane event-time overlap, and an identity may
not disappear and later reappear after a contract transition. Ambiguity, extra
wrong-basis objects, missing event overlap, or a reversion produces an explicit
stand-down instead of a guessed pairing.

The gate is historical-first and outcome-blind. It cannot change a blind forecast or
posterior, update ``knowledge/ng_brain.json``, grant execution authority, make CME
event contracts live, substitute IBKR for tastytrade, or start the options lane.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import ng_broad_corpus_scope_gate as broad
import ng_corpus_coverage_audit as coverage

SCHEMA = "ng_broad_corpus_exact_overlap_gate.v1"
READY_STATUS = "BROAD_CORPUS_EXACT_OVERLAP_VERIFIED"
BLOCKED_STATUS = "BROAD_CORPUS_EXACT_OVERLAP_BLOCKED"
EXACT_NG_SYMBOL = re.compile(r"NG[A-Z][0-9]{2}")


class BroadCorpusExactOverlapError(ValueError):
    """Raised when broad-corpus overlap evidence is malformed or tampered."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BroadCorpusExactOverlapError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise BroadCorpusExactOverlapError(f"JSON artifact must be an object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise BroadCorpusExactOverlapError(f"{label}: {field} must remain false")
    if value.get("one_signal_authority_preserved") is not True:
        raise BroadCorpusExactOverlapError(f"{label}: one signal authority must be preserved")
    if value.get("blind_forecasts_immutable") is not True:
        raise BroadCorpusExactOverlapError(f"{label}: blind forecasts must remain immutable")
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise BroadCorpusExactOverlapError(f"{label}: CME event contracts must remain SHADOW")
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise BroadCorpusExactOverlapError(f"{label}: brokerage must remain tastytrade, not IBKR")


def _day(value: Any, *, label: str) -> str:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise BroadCorpusExactOverlapError(f"{label}: invalid day {value!r}")
    try:
        datetime.strptime(text, "%Y%m%d")
    except ValueError as error:
        raise BroadCorpusExactOverlapError(f"{label}: invalid day {value!r}") from error
    return text


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise BroadCorpusExactOverlapError(f"{label}: value must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BroadCorpusExactOverlapError(f"{label}: value must be finite") from error
    if not math.isfinite(number):
        raise BroadCorpusExactOverlapError(f"{label}: value must be finite")
    return number


def _positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool):
        raise BroadCorpusExactOverlapError(f"{label}: value must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise BroadCorpusExactOverlapError(f"{label}: value must be a positive integer") from error
    if number <= 0:
        raise BroadCorpusExactOverlapError(f"{label}: value must be a positive integer")
    return number


def _identity(row: Mapping[str, Any], *, label: str) -> tuple[Any, ...]:
    if row.get("status") != "PRESENT":
        raise BroadCorpusExactOverlapError(f"{label}: overlap sources must be PRESENT")
    dataset = str(row.get("dataset") or "")
    if dataset != coverage.DATASET:
        raise BroadCorpusExactOverlapError(f"{label}: dataset must be {coverage.DATASET}")
    publisher_id = _positive_int(row.get("publisher_id"), label=f"{label}:publisher_id")
    instrument_id = _positive_int(row.get("instrument_id"), label=f"{label}:instrument_id")
    raw_symbol = str(row.get("raw_symbol") or "")
    if not EXACT_NG_SYMBOL.fullmatch(raw_symbol):
        raise BroadCorpusExactOverlapError(f"{label}: raw symbol must be an exact NG contract")
    definition_date = str(row.get("definition_date") or "")
    if not definition_date:
        raise BroadCorpusExactOverlapError(f"{label}: definition_date is required")
    definition_start = _finite(row.get("definition_start_s"), label=f"{label}:definition_start_s")
    definition_end = _finite(row.get("definition_end_s"), label=f"{label}:definition_end_s")
    if definition_end < definition_start:
        raise BroadCorpusExactOverlapError(f"{label}: definition period is backwards")
    return (
        dataset,
        publisher_id,
        instrument_id,
        raw_symbol,
        definition_date,
        definition_start,
        definition_end,
    )


def _event_range(row: Mapping[str, Any], *, day: str, label: str) -> tuple[float, float]:
    start = _finite(row.get("event_start_s"), label=f"{label}:event_start_s")
    end = _finite(row.get("event_end_s"), label=f"{label}:event_end_s")
    if end < start:
        raise BroadCorpusExactOverlapError(f"{label}: event range is backwards")
    observed_start_day = datetime.fromtimestamp(start, tz=timezone.utc).strftime("%Y%m%d")
    observed_end_day = datetime.fromtimestamp(end, tz=timezone.utc).strftime("%Y%m%d")
    if observed_start_day != day or observed_end_day != day:
        raise BroadCorpusExactOverlapError(
            f"{label}: event range {observed_start_day}-{observed_end_day} does not stay inside UTC day {day}"
        )
    return start, end


def _identity_object(key: Sequence[Any]) -> dict[str, Any]:
    return {
        "dataset": key[0],
        "publisher_id": key[1],
        "instrument_id": key[2],
        "raw_symbol": key[3],
        "definition_date": key[4],
        "definition_start_s": key[5],
        "definition_end_s": key[6],
    }


def _merge_intervals(intervals: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _day_report(day: str, l1_rows: Sequence[Mapping[str, Any]], mbo_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    if not l1_rows:
        blockers.append("MISSING_L1_DENSE_TRADES_DAY")
    if not mbo_rows:
        blockers.append("MISSING_MBO_DAY")

    l1: list[tuple[Mapping[str, Any], tuple[Any, ...], tuple[float, float]]] = []
    mbo: list[tuple[Mapping[str, Any], tuple[Any, ...], tuple[float, float]]] = []
    for lane, rows, destination in (("l1_trades", l1_rows, l1), ("mbo", mbo_rows, mbo)):
        seen_source_ids: set[str] = set()
        for index, row in enumerate(rows):
            source_id = str(row.get("source_id") or "")
            label = f"{day}:{lane}:{source_id or index}"
            if not source_id or source_id in seen_source_ids:
                blockers.append(f"{lane.upper()}_DUPLICATE_OR_MISSING_SOURCE_ID")
            seen_source_ids.add(source_id)
            if str(row.get("lane") or lane) != lane:
                blockers.append(f"{lane.upper()}_LANE_MISMATCH")
            try:
                identity = _identity(row, label=label)
                event_range = _event_range(row, day=day, label=label)
            except BroadCorpusExactOverlapError as error:
                blockers.append(str(error))
                continue
            destination.append((row, identity, event_range))

    compatible: list[dict[str, Any]] = []
    for l1_row, l1_identity, (l1_start, l1_end) in l1:
        for mbo_row, mbo_identity, (mbo_start, mbo_end) in mbo:
            if l1_identity != mbo_identity:
                continue
            overlap_start = max(l1_start, mbo_start)
            overlap_end = min(l1_end, mbo_end)
            if overlap_end <= overlap_start:
                continue
            compatible.append(
                {
                    "identity_key": l1_identity,
                    "l1_source_id": str(l1_row.get("source_id")),
                    "mbo_source_id": str(mbo_row.get("source_id")),
                    "overlap_start_s": overlap_start,
                    "overlap_end_s": overlap_end,
                    "overlap_duration_s": overlap_end - overlap_start,
                }
            )

    compatible_identities = {tuple(row["identity_key"]) for row in compatible}
    selected_identity: tuple[Any, ...] | None = None
    if not compatible and l1_rows and mbo_rows:
        blockers.append("NO_EXACT_IDENTITY_EVENT_TIME_OVERLAP")
    elif len(compatible_identities) > 1:
        blockers.append("AMBIGUOUS_EXACT_IDENTITY_PARTITIONS")
    elif compatible_identities:
        selected_identity = next(iter(compatible_identities))

    if selected_identity is not None:
        wrong_l1 = sorted(
            str(row.get("source_id")) for row, identity, _ in l1 if identity != selected_identity
        )
        wrong_mbo = sorted(
            str(row.get("source_id")) for row, identity, _ in mbo if identity != selected_identity
        )
        if wrong_l1:
            blockers.append("EXTRA_L1_WRONG_BASIS_SOURCE")
        if wrong_mbo:
            blockers.append("EXTRA_MBO_WRONG_BASIS_SOURCE")

        selected_pairs = [row for row in compatible if tuple(row["identity_key"]) == selected_identity]
        used_l1 = {str(row["l1_source_id"]) for row in selected_pairs}
        used_mbo = {str(row["mbo_source_id"]) for row in selected_pairs}
        selected_l1 = {str(row.get("source_id")) for row, identity, _ in l1 if identity == selected_identity}
        selected_mbo = {str(row.get("source_id")) for row, identity, _ in mbo if identity == selected_identity}
        if selected_l1 - used_l1:
            blockers.append("L1_SOURCE_WITHOUT_MBO_EVENT_OVERLAP")
        if selected_mbo - used_mbo:
            blockers.append("MBO_SOURCE_WITHOUT_L1_EVENT_OVERLAP")
    else:
        selected_pairs = []
        wrong_l1 = []
        wrong_mbo = []
        used_l1 = set()
        used_mbo = set()

    intervals = _merge_intervals(
        [(float(row["overlap_start_s"]), float(row["overlap_end_s"])) for row in selected_pairs]
    )
    pair_rows = [
        {key: value for key, value in row.items() if key != "identity_key"}
        for row in sorted(
            selected_pairs,
            key=lambda value: (
                value["overlap_start_s"],
                value["overlap_end_s"],
                value["l1_source_id"],
                value["mbo_source_id"],
            ),
        )
    ]
    blockers = sorted(set(blockers))
    return {
        "day": day,
        "status": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "l1_source_ids": sorted(str(row.get("source_id")) for row in l1_rows),
        "mbo_source_ids": sorted(str(row.get("source_id")) for row in mbo_rows),
        "selected_identity": None if selected_identity is None else _identity_object(selected_identity),
        "compatible_pairs": pair_rows,
        "compatible_pair_count": len(pair_rows),
        "participating_l1_source_ids": sorted(used_l1),
        "participating_mbo_source_ids": sorted(used_mbo),
        "wrong_basis_l1_source_ids": wrong_l1,
        "wrong_basis_mbo_source_ids": wrong_mbo,
        "merged_overlap_intervals": [
            {"start_s": start, "end_s": end, "duration_s": end - start}
            for start, end in intervals
        ],
        "total_merged_overlap_s": sum(end - start for start, end in intervals),
        "event_time_positive_overlap_required": True,
        "event_time_confined_to_declared_utc_day": True,
    }


def _identity_runs(day_reports: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    runs: list[dict[str, Any]] = []
    blockers: list[str] = []
    seen: set[str] = set()
    for report in day_reports:
        if report.get("status") != "READY":
            continue
        identity = dict(report.get("selected_identity") or {})
        identity_fingerprint = _fp(identity)
        day = str(report.get("day"))
        if runs and runs[-1]["identity_fingerprint"] == identity_fingerprint:
            runs[-1]["last_day"] = day
            runs[-1]["day_count"] += 1
            runs[-1]["days"].append(day)
            continue
        if identity_fingerprint in seen:
            blockers.append("IDENTITY_REAPPEARED_AFTER_CONTRACT_TRANSITION")
        seen.add(identity_fingerprint)
        runs.append(
            {
                "identity_fingerprint": identity_fingerprint,
                "identity": identity,
                "first_day": day,
                "last_day": day,
                "day_count": 1,
                "days": [day],
            }
        )

    by_symbol: dict[str, set[str]] = {}
    for run in runs:
        symbol = str(run["identity"].get("raw_symbol") or "")
        by_symbol.setdefault(symbol, set()).add(str(run["identity_fingerprint"]))
    if any(len(values) != 1 for values in by_symbol.values()):
        blockers.append("RAW_SYMBOL_HAS_CONFLICTING_DEFINITION_IDENTITY")
    return runs, sorted(set(blockers))


def _build_unchecked(broad_gate: Mapping[str, Any]) -> dict[str, Any]:
    checked_gate = copy.deepcopy(dict(broad_gate))
    broad.validate_gate(checked_gate)
    _authority(checked_gate, label="broad-scope gate")

    receipt = copy.deepcopy(dict(checked_gate.get("source_inspection_receipt") or {}))
    catalog = copy.deepcopy(dict(receipt.get("catalog") or {}))
    corpora = {str(row.get("corpus_id") or ""): row for row in catalog.get("corpora") or []}
    if set(corpora) != {coverage.L1_CORPUS_ID, coverage.MBO_CORPUS_ID}:
        raise BroadCorpusExactOverlapError("broad gate must embed both canonical corpora")

    l1_corpus = corpora[coverage.L1_CORPUS_ID]
    mbo_corpus = corpora[coverage.MBO_CORPUS_ID]
    l1_expected = sorted({_day(value, label="l1_expected_day") for value in l1_corpus.get("expected_days") or []})
    mbo_expected = sorted({_day(value, label="mbo_expected_day") for value in mbo_corpus.get("expected_days") or []})
    l1_expected_set = set(l1_expected)
    blockers: list[str] = []
    if checked_gate.get("status") != broad.READY_STATUS:
        blockers.append("BROAD_CORPUS_SCOPE_NOT_VERIFIED")
    missing_l1_days = sorted(set(mbo_expected) - l1_expected_set)
    if missing_l1_days:
        blockers.append("MBO_EXPECTED_DAYS_MISSING_FROM_L1_EXPECTED_DAYS")

    def rows_by_day(corpus: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        for row in corpus.get("entries") or []:
            day = _day(row.get("day"), label=f"{corpus.get('corpus_id')}:entry_day")
            result.setdefault(day, []).append(copy.deepcopy(dict(row)))
        return result

    l1_by_day = rows_by_day(l1_corpus)
    mbo_by_day = rows_by_day(mbo_corpus)
    day_reports = [_day_report(day, l1_by_day.get(day, []), mbo_by_day.get(day, [])) for day in mbo_expected]
    ready_days = [row["day"] for row in day_reports if row["status"] == "READY"]
    blocked_days = [row["day"] for row in day_reports if row["status"] == "BLOCKED"]
    for row in day_reports:
        blockers.extend(f"{row['day']}:{reason}" for reason in row.get("blockers") or [])

    runs, run_blockers = _identity_runs(day_reports)
    blockers.extend(run_blockers)
    publishers = sorted(
        {
            int(dict(row.get("selected_identity") or {}).get("publisher_id"))
            for row in day_reports
            if row.get("status") == "READY"
        }
    )
    if len(publishers) != 1 and ready_days:
        blockers.append("OVERLAP_WINDOW_PUBLISHER_NOT_UNIQUE")
    if len(ready_days) != len(mbo_expected):
        blockers.append("NOT_ALL_SHARED_WINDOW_DAYS_EXACTLY_ALIGNED")

    target_days = set(coverage.G15_DATES + coverage.G16_DATES)
    missing_target_days = sorted(target_days - set(ready_days))
    if missing_target_days:
        blockers.append("G15_G16_TARGET_DAY_NOT_ALIGNED_IN_BROAD_WINDOW")

    blockers = sorted(set(blockers))
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_STATUS if not blockers else BLOCKED_STATUS,
        "market": "NG",
        "dataset": coverage.DATASET,
        "broad_scope_gate_fingerprint": checked_gate.get("fingerprint"),
        "inspection_receipt_fingerprint": checked_gate.get("inspection_receipt_fingerprint"),
        "catalog_fingerprint": checked_gate.get("catalog_fingerprint"),
        "coverage_audit_fingerprint": checked_gate.get("coverage_audit_fingerprint"),
        "source_broad_scope_gate": checked_gate,
        "overlap_window": copy.deepcopy(dict(mbo_corpus.get("declared_window") or {})),
        "alignment_basis": [
            "dataset",
            "publisher_id",
            "instrument_id",
            "raw_symbol",
            "definition_date",
            "definition_start_s",
            "definition_end_s",
            "positive_event_time_overlap",
        ],
        "expected_overlap_days": mbo_expected,
        "expected_overlap_day_count": len(mbo_expected),
        "ready_days": ready_days,
        "blocked_days": blocked_days,
        "missing_l1_expected_days": missing_l1_days,
        "day_reports": day_reports,
        "identity_runs": runs,
        "contract_transition_count": max(0, len(runs) - 1),
        "aligned_publisher_ids": publishers,
        "all_shared_days_exactly_aligned": not blockers and len(ready_days) == len(mbo_expected),
        "g15_g16_days_included": not missing_target_days,
        "identity_reversion_forbidden": True,
        "ambiguous_pair_selection_forbidden": True,
        "extra_wrong_basis_sources_forbidden": True,
        "blockers": blockers,
        "remote_presence_inferred": False,
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
        "next_permitted_stage": (
            "CONFIGURE_EXACT_G15_REPLAY"
            if not blockers
            else "REPAIR_BROAD_CORPUS_EXACT_OVERLAP_ALIGNMENT"
        ),
    }
    output["fingerprint"] = _fp(output)
    return output


def build_gate(broad_scope_gate: Mapping[str, Any]) -> dict[str, Any]:
    result = _build_unchecked(broad_scope_gate)
    validate_gate(result)
    return result


def validate_gate(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise BroadCorpusExactOverlapError("exact-overlap gate schema or fingerprint mismatch")
    checked["fingerprint"] = observed
    _authority(checked, label="exact-overlap gate")
    source = copy.deepcopy(dict(checked.get("source_broad_scope_gate") or {}))
    expected = _build_unchecked(source)
    if _canonical(expected) != _canonical(checked):
        raise BroadCorpusExactOverlapError("exact-overlap gate differs from deterministic reconstruction")
    if checked.get("status") == READY_STATUS:
        if checked.get("blockers") != []:
            raise BroadCorpusExactOverlapError("ready exact-overlap gate may not contain blockers")
        if checked.get("all_shared_days_exactly_aligned") is not True:
            raise BroadCorpusExactOverlapError("shared broad-corpus days are not exactly aligned")
        if checked.get("g15_g16_days_included") is not True:
            raise BroadCorpusExactOverlapError("G15/G16 target days are not included")
        if checked.get("ready_days") != checked.get("expected_overlap_days"):
            raise BroadCorpusExactOverlapError("ready days must equal the complete overlap-day set")
    return copy.deepcopy(dict(value))


def _fixture_entry(*, lane: str, day: str, symbol: str, instrument_id: int) -> dict[str, Any]:
    start_dt = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc)
    start = start_dt.timestamp() + (60 if lane == "l1_trades" else 120)
    end = start_dt.timestamp() + (3600 if lane == "l1_trades" else 3540)
    definition_anchor = datetime(2026, 3, 1 if symbol == "NGJ26" else 20, tzinfo=timezone.utc)
    return {
        "day": day,
        "lane": lane,
        "source_id": f"{lane}:{day}:{symbol}",
        "status": "PRESENT",
        "location": f"/fixture/{lane}/{day}-{symbol}.jsonl",
        "dataset": coverage.DATASET,
        "publisher_id": 1,
        "instrument_id": instrument_id,
        "raw_symbol": symbol,
        "definition_date": definition_anchor.date().isoformat(),
        "definition_start_s": definition_anchor.timestamp(),
        "definition_end_s": datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp(),
        "event_start_s": start,
        "event_end_s": end,
        "record_count": 10,
        "size_bytes": 100,
        "sha256": "a" * 64,
        "inventory_observed_at": "2026-07-24T00:00:00Z",
    }


def selftest() -> int:
    original = broad.validate_gate
    try:
        broad.validate_gate = lambda value: value  # type: ignore[assignment]
        days = list(coverage.G15_DATES + coverage.G16_DATES)
        corpora = []
        for corpus_id, lane in ((coverage.L1_CORPUS_ID, "l1_trades"), (coverage.MBO_CORPUS_ID, "mbo")):
            entries = []
            for day in days:
                expected = coverage.G15_CONTRACT_MAP.get(day) or coverage.G16_CONTRACT_MAP[day]
                entries.append(
                    _fixture_entry(
                        lane=lane,
                        day=day,
                        symbol=expected["raw_symbol"],
                        instrument_id=expected["instrument_id"],
                    )
                )
            corpora.append(
                {
                    "corpus_id": corpus_id,
                    "lane": lane,
                    "declared_window": copy.deepcopy(coverage.EXPECTED_WINDOWS[corpus_id]),
                    "expected_days": days,
                    "entries": entries,
                }
            )
        gate = {
            "status": broad.READY_STATUS,
            "fingerprint": "fixture-broad",
            "inspection_receipt_fingerprint": "fixture-receipt",
            "catalog_fingerprint": "fixture-catalog",
            "coverage_audit_fingerprint": "fixture-audit",
            "source_inspection_receipt": {"catalog": {"corpora": corpora}},
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
        result = build_gate(gate)
        assert result["status"] == READY_STATUS, result["blockers"]
        assert result["ready_days"] == days
        assert result["g15_g16_days_included"] is True
    finally:
        broad.validate_gate = original
    print("[ng_broad_corpus_exact_overlap_gate] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--broad-scope-gate", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.broad_scope_gate is None or args.out is None:
        parser.error("--broad-scope-gate and --out are required")
    result = build_gate(_load(args.broad_scope_gate))
    _write(args.out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
