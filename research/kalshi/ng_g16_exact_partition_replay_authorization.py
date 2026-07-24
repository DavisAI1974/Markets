#!/usr/bin/env python3
"""Bind exact G16 replay bytes and state windows to the verified broad partition.

The prepared G16 replay gate verifies normalized-file hashes and raw-manifest
lineage, while the broad partition gate verifies unique source ownership across
the one-year L1/dense-trades and spring/summer MBO corpora.  This authorization
joins those proofs before any G16 causal posterior is allowed:

* every one of the 22 NGK26 replay lanes must match exactly one verified
  partition source by location, SHA-256, size, record count, event range, and
  exact dataset/publisher/instrument/raw-symbol/definition identity;
* no partition source may be reused by another day or lane;
* every emitted G16 feature-state cutoff must remain inside the exact common
  L1/MBO event-time window for its canonical session.

No outcomes are read.  Blind forecasts and the posterior remain immutable,
random shuffling is forbidden, CME event contracts remain SHADOW, tastytrade
remains the brokerage contract, and the options lane remains unstarted.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import ng_broad_corpus_exact_partition_gate as partition_gate
import ng_g16_historical_replay as replay_module
import ng_g16_prepared_replay_gate as prepared_gate
from ng_g16_historical_replay import CANONICAL_DATES, SOURCE_KINDS

SCHEMA = "ng_g16_exact_partition_replay_authorization.v1"
READY = "EXACT_G16_PARTITION_REPLAY_WINDOWS_AUTHORIZED"
READY_WITH_STAND_DOWNS = "EXACT_G16_PARTITION_REPLAY_WINDOWS_AUTHORIZED_WITH_STAND_DOWNS"
EXPECTED_REPLAY_SOURCE_COUNT = len(CANONICAL_DATES) * len(SOURCE_KINDS)


class G16ExactPartitionReplayAuthorizationError(ValueError):
    """Raised when G16 replay bytes or state windows are not exactly authorized."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G16ExactPartitionReplayAuthorizationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise G16ExactPartitionReplayAuthorizationError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _finite(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise G16ExactPartitionReplayAuthorizationError(f"{label} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise G16ExactPartitionReplayAuthorizationError(
            f"{label} must be finite"
        ) from error
    if not math.isfinite(number):
        raise G16ExactPartitionReplayAuthorizationError(f"{label} must be finite")
    return number


def _same_number(left: Any, right: Any, *, label: str) -> bool:
    return abs(
        _finite(left, label=f"{label}.left")
        - _finite(right, label=f"{label}.right")
    ) <= 1e-6


def _authority(value: Mapping[str, Any], *, label: str) -> None:
    for field in (
        "actual_g16_outcomes_used",
        "paid_live_data_assumed",
        "random_shuffle_used",
        "may_change_g16_blind_prior",
        "may_change_g16_blind_forecast",
        "may_change_posterior",
        "may_update_ng_brain",
        "execution_authority",
        "options_lane_started",
    ):
        if value.get(field) is not False:
            raise G16ExactPartitionReplayAuthorizationError(
                f"{label}: {field} must remain false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise G16ExactPartitionReplayAuthorizationError(
            f"{label}: one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise G16ExactPartitionReplayAuthorizationError(
            f"{label}: blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise G16ExactPartitionReplayAuthorizationError(
            f"{label}: CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise G16ExactPartitionReplayAuthorizationError(
            f"{label}: brokerage must remain tastytrade, not IBKR"
        )


def _identity(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset": entry.get("dataset"),
        "publisher_id": entry.get("publisher_id"),
        "instrument_id": entry.get("instrument_id"),
        "raw_symbol": entry.get("raw_symbol"),
        "definition_date": entry.get("definition_date"),
        "definition_start_s": entry.get("definition_start_s"),
        "definition_end_s": entry.get("definition_end_s"),
    }


def _source_matches(entry: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    if str(entry.get("location") or "") != str(source.get("location") or ""):
        return False
    if str(entry.get("sha256") or "").lower() != str(
        source.get("sha256") or ""
    ).lower():
        return False
    for field in ("size_bytes", "record_count"):
        if int(entry.get(field) or 0) != int(source.get(field) or 0):
            return False
    return _same_number(
        entry.get("event_start_s"),
        source.get("event_start_s"),
        label="event_start_s",
    ) and _same_number(
        entry.get("event_end_s"),
        source.get("event_end_s"),
        label="event_end_s",
    )


def _states_by_day(replay: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {day: [] for day in CANONICAL_DATES}
    for stream in replay.get("streams") or []:
        for raw in stream.get("states") or []:
            state = copy.deepcopy(dict(raw))
            day = str(state.get("session_day") or "")
            if day not in result:
                raise G16ExactPartitionReplayAuthorizationError(
                    f"replay state is outside canonical G16: {day!r}"
                )
            result[day].append(state)
    for day, states in result.items():
        states.sort(
            key=lambda state: (
                _finite(state.get("decision_cutoff_s"), label=f"{day}.decision_cutoff_s"),
                int(state.get("sequence") or 0),
            )
        )
        if not states:
            raise G16ExactPartitionReplayAuthorizationError(
                f"{day}: replay emitted no completed feature states"
            )
    return result


def _build_unchecked(
    exact_partition_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    prepared_replay_gate: Mapping[str, Any],
) -> dict[str, Any]:
    partition_value = copy.deepcopy(dict(exact_partition_gate))
    prepared_value = copy.deepcopy(dict(prepared_index))
    manifest_value = copy.deepcopy(dict(manifest))
    replay_value = copy.deepcopy(dict(replay))
    blind_value = copy.deepcopy(dict(blind_prior))
    prepared_gate_value = copy.deepcopy(dict(prepared_replay_gate))

    partition_gate.validate_gate(partition_value)
    replay_module.validate_prepared_index(prepared_value, verify_files=True)
    replay_module.validate_manifest(manifest_value)
    replay_module.validate_replay_output(replay_value)
    prepared_gate.validate_gate_artifact(
        prepared_gate_value,
        prepared_index=prepared_value,
        manifest=manifest_value,
        replay=replay_value,
        blind_prior=blind_value,
    )

    if partition_value.get("status") != partition_gate.READY_STATUS:
        raise G16ExactPartitionReplayAuthorizationError(
            "broad exact source partition is not verified"
        )
    if prepared_gate_value.get("status") not in {
        prepared_gate.STATUS_READY,
        prepared_gate.STATUS_STAND_DOWNS,
    }:
        raise G16ExactPartitionReplayAuthorizationError(
            "prepared G16 replay gate is not ready"
        )
    if prepared_gate_value.get("manifest_fingerprint") != manifest_value.get(
        "fingerprint"
    ):
        raise G16ExactPartitionReplayAuthorizationError(
            "prepared replay gate references a different manifest"
        )
    if prepared_gate_value.get("prepared_corpus_fingerprint") != prepared_value.get(
        "prepared_corpus_fingerprint"
    ):
        raise G16ExactPartitionReplayAuthorizationError(
            "prepared replay gate references a different prepared corpus"
        )
    if prepared_gate_value.get("replay_fingerprint") != replay_value.get("fingerprint"):
        raise G16ExactPartitionReplayAuthorizationError(
            "prepared replay gate references a different replay"
        )

    expected_keys = {
        (day, source_kind)
        for day in CANONICAL_DATES
        for source_kind in SOURCE_KINDS
    }
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in manifest_value.get("entries") or []:
        entry = copy.deepcopy(dict(raw))
        key = (str(entry.get("day") or ""), str(entry.get("source_kind") or ""))
        if key in entries:
            raise G16ExactPartitionReplayAuthorizationError(
                f"duplicate G16 manifest lane: {key[0]}:{key[1]}"
            )
        entries[key] = entry
    if set(entries) != expected_keys:
        raise G16ExactPartitionReplayAuthorizationError(
            "G16 manifest does not contain the canonical 22 replay lanes"
        )

    partition_days = {
        str(row.get("day") or ""): copy.deepcopy(dict(row))
        for row in partition_value.get("day_reports") or []
    }
    states_by_day = _states_by_day(replay_value)
    bound_source_ids: set[str] = set()
    day_bindings: list[dict[str, Any]] = []

    for day in CANONICAL_DATES:
        report = partition_days.get(day)
        if report is None or report.get("status") != "READY":
            raise G16ExactPartitionReplayAuthorizationError(
                f"{day}: exact source partition is not ready"
            )
        selected_identity = copy.deepcopy(dict(report.get("selected_identity") or {}))
        lane_bindings: dict[str, dict[str, Any]] = {}
        for source_kind in SOURCE_KINDS:
            lane_key = "l1_partition" if source_kind == "l1_trades" else "mbo_partition"
            lane = copy.deepcopy(dict(report.get(lane_key) or {}))
            if lane.get("status") != "READY":
                raise G16ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: exact source partition is not ready"
                )
            entry = entries[(day, source_kind)]
            if _canonical(_identity(entry)) != _canonical(selected_identity):
                raise G16ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: manifest identity differs from exact partition"
                )
            matches = [
                copy.deepcopy(dict(source))
                for source in lane.get("ordered_sources") or []
                if _source_matches(entry, source)
            ]
            if len(matches) != 1:
                raise G16ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: manifest source must match exactly one partition source"
                )
            source = matches[0]
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in bound_source_ids:
                raise G16ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: partition source is missing or reused"
                )
            bound_source_ids.add(source_id)
            lane_bindings[source_kind] = {
                "source_id": source_id,
                "location": source["location"],
                "sha256": source["sha256"],
                "size_bytes": int(source["size_bytes"]),
                "record_count": int(source["record_count"]),
                "event_start_s": float(source["event_start_s"]),
                "event_end_s": float(source["event_end_s"]),
                "source_partition_fingerprint": lane.get(
                    "source_partition_fingerprint"
                ),
                "manifest_entry_fingerprint": _fp(entry),
            }

        common_start = max(
            lane_bindings["l1_trades"]["event_start_s"],
            lane_bindings["mbo"]["event_start_s"],
        )
        common_end = min(
            lane_bindings["l1_trades"]["event_end_s"],
            lane_bindings["mbo"]["event_end_s"],
        )
        if common_end < common_start:
            raise G16ExactPartitionReplayAuthorizationError(
                f"{day}: exact L1/MBO event windows do not overlap"
            )

        states = states_by_day[day]
        state_times = [
            _finite(
                state.get("decision_cutoff_s"),
                label=f"{day}.state[{index}].decision_cutoff_s",
            )
            for index, state in enumerate(states)
        ]
        first_state = min(state_times)
        last_state = max(state_times)
        if first_state < common_start - 1e-6 or last_state > common_end + 1e-6:
            raise G16ExactPartitionReplayAuthorizationError(
                f"{day}: replay state span escapes the exact common L1/MBO window"
            )
        stand_down_reasons = sorted(
            {
                str(reason)
                for state in states
                for reason in (
                    (state.get("availability") or {}).get("stand_down_reasons")
                    or []
                )
            }
        )
        day_bindings.append(
            {
                "day": day,
                "selected_identity": selected_identity,
                "l1_trades": lane_bindings["l1_trades"],
                "mbo": lane_bindings["mbo"],
                "common_event_start_s": common_start,
                "common_event_end_s": common_end,
                "state_count": len(states),
                "first_state_cutoff_s": first_state,
                "last_state_cutoff_s": last_state,
                "all_state_cutoffs_inside_common_window": True,
                "stand_down_reasons": stand_down_reasons,
            }
        )

    if len(bound_source_ids) != EXPECTED_REPLAY_SOURCE_COUNT:
        raise G16ExactPartitionReplayAuthorizationError(
            "not all 22 canonical G16 replay lanes were uniquely bound"
        )

    replay_stand_downs = sorted(
        str(day) for day in replay_value.get("stand_down_days") or []
    )
    derived_stand_downs = [
        row["day"] for row in day_bindings if row["stand_down_reasons"]
    ]
    stand_down_days = sorted(set(replay_stand_downs) | set(derived_stand_downs))
    source_binding = {
        "exact_partition_gate_fingerprint": partition_value.get("fingerprint"),
        "manifest_fingerprint": manifest_value.get("fingerprint"),
        "prepared_corpus_fingerprint": prepared_value.get(
            "prepared_corpus_fingerprint"
        ),
        "bound_replay_source_ids": sorted(bound_source_ids),
        "day_lane_fingerprints": [
            {
                "day": row["day"],
                "l1": row["l1_trades"]["manifest_entry_fingerprint"],
                "mbo": row["mbo"]["manifest_entry_fingerprint"],
            }
            for row in day_bindings
        ],
    }
    window_contract = {
        "replay_fingerprint": replay_value.get("fingerprint"),
        "days": [
            {
                "day": row["day"],
                "common_event_start_s": row["common_event_start_s"],
                "common_event_end_s": row["common_event_end_s"],
                "state_count": row["state_count"],
                "first_state_cutoff_s": row["first_state_cutoff_s"],
                "last_state_cutoff_s": row["last_state_cutoff_s"],
            }
            for row in day_bindings
        ],
    }

    output: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "market": "NG",
        "group": 16,
        "exact_partition_gate_fingerprint": partition_value.get("fingerprint"),
        "prepared_replay_gate_fingerprint": prepared_gate_value.get("fingerprint"),
        "manifest_fingerprint": manifest_value.get("fingerprint"),
        "prepared_corpus_fingerprint": prepared_value.get(
            "prepared_corpus_fingerprint"
        ),
        "replay_fingerprint": replay_value.get("fingerprint"),
        "blind_prior_fingerprint": prepared_gate_value.get(
            "blind_prior_fingerprint"
        ),
        "source_binding_fingerprint": _fp(source_binding),
        "window_contract_fingerprint": _fp(window_contract),
        "source_exact_partition_gate": partition_value,
        "source_prepared_index": prepared_value,
        "source_manifest": manifest_value,
        "source_replay": replay_value,
        "source_blind_prior": blind_value,
        "source_prepared_replay_gate": prepared_gate_value,
        "day_bindings": day_bindings,
        "bound_replay_source_ids": sorted(bound_source_ids),
        "bound_replay_source_count": len(bound_source_ids),
        "all_g16_replay_sources_bound_to_exact_partition": True,
        "all_g16_state_spans_inside_exact_common_windows": True,
        "stand_down_days": stand_down_days,
        "actual_g16_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_g16_blind_prior": False,
        "may_change_g16_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
        "next_permitted_stage": "G16_PRE_CUTOFF_EXACT_CAUSAL_PIPELINE",
    }
    output["fingerprint"] = _fp(output)
    return output


def build_authorization(
    exact_partition_gate: Mapping[str, Any],
    prepared_index: Mapping[str, Any],
    manifest: Mapping[str, Any],
    replay: Mapping[str, Any],
    blind_prior: Mapping[str, Any],
    prepared_replay_gate: Mapping[str, Any],
) -> dict[str, Any]:
    result = _build_unchecked(
        exact_partition_gate,
        prepared_index,
        manifest,
        replay,
        blind_prior,
        prepared_replay_gate,
    )
    validate_authorization(result)
    return result


def validate_authorization(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise G16ExactPartitionReplayAuthorizationError(
            "G16 partition/replay authorization schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="G16 partition/replay authorization")
    expected = _build_unchecked(
        checked.get("source_exact_partition_gate") or {},
        checked.get("source_prepared_index") or {},
        checked.get("source_manifest") or {},
        checked.get("source_replay") or {},
        checked.get("source_blind_prior") or {},
        checked.get("source_prepared_replay_gate") or {},
    )
    if _canonical(expected) != _canonical(checked):
        raise G16ExactPartitionReplayAuthorizationError(
            "G16 partition/replay authorization differs from deterministic reconstruction"
        )
    if checked.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise G16ExactPartitionReplayAuthorizationError(
            "G16 partition/replay authorization is not ready"
        )
    if checked.get("bound_replay_source_count") != EXPECTED_REPLAY_SOURCE_COUNT:
        raise G16ExactPartitionReplayAuthorizationError(
            "exactly 22 G16 replay lanes must be bound"
        )
    if checked.get("all_g16_replay_sources_bound_to_exact_partition") is not True:
        raise G16ExactPartitionReplayAuthorizationError(
            "not every G16 replay source is bound to the exact partition"
        )
    if (
        checked.get("all_g16_state_spans_inside_exact_common_windows")
        is not True
    ):
        raise G16ExactPartitionReplayAuthorizationError(
            "not every G16 replay state span is inside the exact common window"
        )
    if [row.get("day") for row in checked.get("day_bindings") or []] != list(
        CANONICAL_DATES
    ):
        raise G16ExactPartitionReplayAuthorizationError(
            "G16 partition/replay authorization lost canonical day order"
        )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-partition-gate", type=Path)
    parser.add_argument("--prepared-index", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--blind-prior", type=Path)
    parser.add_argument("--prepared-replay-gate", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    required = (
        args.exact_partition_gate,
        args.prepared_index,
        args.manifest,
        args.replay,
        args.blind_prior,
        args.prepared_replay_gate,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "--exact-partition-gate, --prepared-index, --manifest, --replay, "
            "--blind-prior, --prepared-replay-gate, and --out are required"
        )
    result = build_authorization(
        _load(args.exact_partition_gate),
        _load(args.prepared_index),
        _load(args.manifest),
        _load(args.replay),
        _load(args.blind_prior),
        _load(args.prepared_replay_gate),
    )
    _write(args.out, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "days": len(result["day_bindings"]),
                "bound_replay_sources": result["bound_replay_source_count"],
                "stand_down_days": result["stand_down_days"],
                "fingerprint": result["fingerprint"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
