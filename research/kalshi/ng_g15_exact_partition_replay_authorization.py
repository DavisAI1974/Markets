#!/usr/bin/env python3
"""Bind exact G15 replay bytes to the verified broad-corpus source partition.

The broad partition gate proves that each shared-day lane owns a unique,
non-overlapping set of inspected bytes.  The replay completion gate proves that
the prepared replay ran causally, but historically those two proofs were only
ordered in readiness.  This authorization joins them explicitly by matching
every G15 replay-manifest lane to exactly one source in the verified partition.

No outcomes are read.  The artifact cannot alter blind forecasts, posterior
state, ng_brain.json, execution authority, CME SHADOW mode, or the options lane.
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
import ng_g15_exact_replay_completion as replay_completion
import ng_g15_replay_manifest_bridge as replay_bridge
from ng_historical_manifest import G15_DATES, SOURCE_KINDS

SCHEMA = "ng_g15_exact_partition_replay_authorization.v1"
READY = "EXACT_G15_PARTITION_REPLAY_AUTHORIZED"
READY_WITH_STAND_DOWNS = "EXACT_G15_PARTITION_REPLAY_AUTHORIZED_WITH_STAND_DOWNS"


class ExactPartitionReplayAuthorizationError(ValueError):
    """Raised when replay provenance is not the exact verified partition."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fp(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExactPartitionReplayAuthorizationError(
            f"cannot read JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ExactPartitionReplayAuthorizationError(
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
        raise ExactPartitionReplayAuthorizationError(f"{label} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ExactPartitionReplayAuthorizationError(
            f"{label} must be finite"
        ) from error
    if not math.isfinite(number):
        raise ExactPartitionReplayAuthorizationError(f"{label} must be finite")
    return number


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
            raise ExactPartitionReplayAuthorizationError(
                f"{label}: {field} must remain false"
            )
    if value.get("one_signal_authority_preserved") is not True:
        raise ExactPartitionReplayAuthorizationError(
            f"{label}: one signal authority must be preserved"
        )
    if value.get("blind_forecasts_immutable") is not True:
        raise ExactPartitionReplayAuthorizationError(
            f"{label}: blind forecasts must remain immutable"
        )
    if value.get("cme_event_contracts_mode") != "SHADOW":
        raise ExactPartitionReplayAuthorizationError(
            f"{label}: CME event contracts must remain SHADOW"
        )
    if value.get("brokerage_contract") != "tastytrade_not_ibkr":
        raise ExactPartitionReplayAuthorizationError(
            f"{label}: brokerage must remain tastytrade, not IBKR"
        )


def _manifest_identity(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "dataset": entry.get("dataset"),
        "publisher_id": entry.get("publisher_id"),
        "instrument_id": entry.get("instrument_id"),
        "raw_symbol": entry.get("raw_symbol"),
        "definition_date": entry.get("definition_date"),
        "definition_start_s": entry.get("definition_start_s"),
        "definition_end_s": entry.get("definition_end_s"),
    }


def _same_number(left: Any, right: Any, *, label: str) -> bool:
    return abs(_finite(left, label=f"{label}.left") - _finite(right, label=f"{label}.right")) <= 1e-6


def _source_matches(entry: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    if str(entry.get("location") or "") != str(source.get("location") or ""):
        return False
    if str(entry.get("sha256") or "").lower() != str(source.get("sha256") or "").lower():
        return False
    for field in ("size_bytes", "record_count"):
        if int(entry.get(field) or 0) != int(source.get(field) or 0):
            return False
    return _same_number(
        entry.get("event_start_s"), source.get("event_start_s"), label="event_start_s"
    ) and _same_number(
        entry.get("event_end_s"), source.get("event_end_s"), label="event_end_s"
    )


def _build_unchecked(
    exact_partition_gate: Mapping[str, Any],
    exact_replay_completion: Mapping[str, Any],
    bridge: Mapping[str, Any],
) -> dict[str, Any]:
    partition_value = copy.deepcopy(dict(exact_partition_gate))
    completion_value = copy.deepcopy(dict(exact_replay_completion))
    bridge_value = copy.deepcopy(dict(bridge))

    partition_gate.validate_gate(partition_value)
    replay_bridge.validate_bridge_output(bridge_value)
    replay_completion.validate_completion(completion_value, bridge=bridge_value)

    if partition_value.get("status") != partition_gate.READY_STATUS:
        raise ExactPartitionReplayAuthorizationError(
            "broad exact source partition is not verified"
        )
    if completion_value.get("status") not in {
        replay_completion.READY,
        replay_completion.READY_WITH_STAND_DOWNS,
    }:
        raise ExactPartitionReplayAuthorizationError("exact G15 replay is not complete")
    if completion_value.get("bridge_fingerprint") != bridge_value.get("fingerprint"):
        raise ExactPartitionReplayAuthorizationError(
            "replay completion references a different manifest bridge"
        )

    manifest = copy.deepcopy(dict(bridge_value.get("manifest") or {}))
    manifest_entries = list(manifest.get("entries") or [])
    expected_keys = {(day, kind) for day in G15_DATES for kind in SOURCE_KINDS}
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in manifest_entries:
        entry = copy.deepcopy(dict(raw))
        key = (str(entry.get("day") or ""), str(entry.get("source_kind") or ""))
        if key in entries:
            raise ExactPartitionReplayAuthorizationError(
                f"duplicate replay manifest lane: {key[0]}:{key[1]}"
            )
        entries[key] = entry
    if set(entries) != expected_keys:
        missing = sorted(expected_keys - set(entries))
        extra = sorted(set(entries) - expected_keys)
        raise ExactPartitionReplayAuthorizationError(
            f"replay manifest lane mismatch; missing={missing} extra={extra}"
        )

    partition_days = {
        str(row.get("day") or ""): copy.deepcopy(dict(row))
        for row in partition_value.get("day_reports") or []
    }
    completion_days = {
        str(row.get("date") or ""): copy.deepcopy(dict(row))
        for row in completion_value.get("days") or []
    }
    if [str(row.get("date") or "") for row in completion_value.get("days") or []] != list(G15_DATES):
        raise ExactPartitionReplayAuthorizationError(
            "replay completion lost canonical G15 day order"
        )

    day_bindings: list[dict[str, Any]] = []
    bound_source_ids: set[str] = set()
    for day in G15_DATES:
        report = partition_days.get(day)
        if report is None or report.get("status") != "READY":
            raise ExactPartitionReplayAuthorizationError(
                f"{day}: exact source partition is not ready"
            )
        identity = copy.deepcopy(dict(report.get("selected_identity") or {}))
        lane_bindings: dict[str, Any] = {}
        for source_kind in SOURCE_KINDS:
            lane_key = "l1_partition" if source_kind == "l1_trades" else "mbo_partition"
            lane = copy.deepcopy(dict(report.get(lane_key) or {}))
            if lane.get("status") != "READY":
                raise ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: source partition is not ready"
                )
            entry = entries[(day, source_kind)]
            if _canonical(_manifest_identity(entry)) != _canonical(identity):
                raise ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: replay identity differs from exact partition"
                )
            matches = [
                copy.deepcopy(dict(source))
                for source in lane.get("ordered_sources") or []
                if _source_matches(entry, source)
            ]
            if len(matches) != 1:
                raise ExactPartitionReplayAuthorizationError(
                    f"{day}:{source_kind}: replay source must match exactly one partition source"
                )
            source = matches[0]
            source_id = str(source.get("source_id") or "")
            if not source_id or source_id in bound_source_ids:
                raise ExactPartitionReplayAuthorizationError(
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
        completion_day = completion_days.get(day) or {}
        reasons = copy.deepcopy(dict(completion_day.get("stand_down_reasons") or {}))
        day_bindings.append(
            {
                "day": day,
                "selected_identity": identity,
                "l1_trades": lane_bindings["l1_trades"],
                "mbo": lane_bindings["mbo"],
                "completed_states": int(completion_day.get("completed_states") or 0),
                "first_replay_event_s": completion_day.get("first_event_s"),
                "last_replay_event_s": completion_day.get("last_event_s"),
                "stand_down_reasons": reasons,
            }
        )

    if len(bound_source_ids) != len(expected_keys):
        raise ExactPartitionReplayAuthorizationError(
            "not all 24 canonical G15 replay lanes were uniquely bound"
        )
    stand_down_days = [
        row["day"] for row in day_bindings if row["stand_down_reasons"]
    ]
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "status": READY_WITH_STAND_DOWNS if stand_down_days else READY,
        "market": "NG",
        "group": 15,
        "exact_partition_gate_fingerprint": partition_value.get("fingerprint"),
        "exact_overlap_gate_fingerprint": partition_value.get(
            "exact_overlap_gate_fingerprint"
        ),
        "bridge_fingerprint": bridge_value.get("fingerprint"),
        "manifest_fingerprint": completion_value.get("manifest_fingerprint"),
        "exact_replay_completion_fingerprint": completion_value.get(
            "completion_fingerprint"
        ),
        "replay_fingerprint": completion_value.get("replay_fingerprint"),
        "prepared_corpus_fingerprint": completion_value.get(
            "prepared_corpus_fingerprint"
        ),
        "source_exact_partition_gate": partition_value,
        "source_exact_replay_completion": completion_value,
        "source_bridge": bridge_value,
        "day_bindings": day_bindings,
        "bound_replay_source_ids": sorted(bound_source_ids),
        "bound_replay_source_count": len(bound_source_ids),
        "all_g15_replay_sources_bound_to_exact_partition": True,
        "stand_down_days": stand_down_days,
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
        "next_permitted_stage": "AUTHORIZE_EXACT_G15_REPLAY_WINDOWS",
    }
    output["fingerprint"] = _fp(output)
    return output


def build_authorization(
    exact_partition_gate: Mapping[str, Any],
    exact_replay_completion: Mapping[str, Any],
    bridge: Mapping[str, Any],
) -> dict[str, Any]:
    result = _build_unchecked(
        exact_partition_gate, exact_replay_completion, bridge
    )
    validate_authorization(result)
    return result


def validate_authorization(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = copy.deepcopy(dict(value))
    observed = checked.pop("fingerprint", None)
    if checked.get("schema") != SCHEMA or observed != _fp(checked):
        raise ExactPartitionReplayAuthorizationError(
            "partition-replay authorization schema or fingerprint mismatch"
        )
    checked["fingerprint"] = observed
    _authority(checked, label="partition-replay authorization")
    expected = _build_unchecked(
        checked.get("source_exact_partition_gate") or {},
        checked.get("source_exact_replay_completion") or {},
        checked.get("source_bridge") or {},
    )
    if _canonical(expected) != _canonical(checked):
        raise ExactPartitionReplayAuthorizationError(
            "partition-replay authorization differs from deterministic reconstruction"
        )
    if checked.get("status") not in {READY, READY_WITH_STAND_DOWNS}:
        raise ExactPartitionReplayAuthorizationError(
            "partition-replay authorization is not ready"
        )
    if checked.get("all_g15_replay_sources_bound_to_exact_partition") is not True:
        raise ExactPartitionReplayAuthorizationError(
            "not every G15 replay source is bound to the exact partition"
        )
    if checked.get("bound_replay_source_count") != 24:
        raise ExactPartitionReplayAuthorizationError(
            "exactly 24 G15 replay lanes must be bound"
        )
    if [row.get("day") for row in checked.get("day_bindings") or []] != list(G15_DATES):
        raise ExactPartitionReplayAuthorizationError(
            "partition-replay authorization lost canonical G15 order"
        )
    return copy.deepcopy(dict(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exact-partition-gate", type=Path)
    parser.add_argument("--exact-replay-completion", type=Path)
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    required = (
        args.exact_partition_gate,
        args.exact_replay_completion,
        args.bridge,
        args.out,
    )
    if any(value is None for value in required):
        parser.error(
            "--exact-partition-gate, --exact-replay-completion, --bridge, and --out are required"
        )
    result = build_authorization(
        _load(args.exact_partition_gate),
        _load(args.exact_replay_completion),
        _load(args.bridge),
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
