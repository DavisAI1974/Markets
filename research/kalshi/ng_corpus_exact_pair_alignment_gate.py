#!/usr/bin/env python3
"""Authorize exact G15/G16 L1+MBO pairs after manual corpus review.

The manual binding review proves object identity and evidence-based UTC day ownership.
This gate is the stricter pair authority: for each G15/G16 session it requires exactly
one L1 source and one MBO source with the same dataset, publisher, instrument, raw
symbol, exact definition period, and overlapping event time. Identity-level readiness
alone is not enough.

The artifact is metadata-only, outcome-blind, SHADOW-only, and cannot mutate forecasts,
posterior state, ``knowledge/ng_brain.json``, execution state, or the options lane.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_binding_review_gate as review
import ng_corpus_coverage_audit as coverage
import ng_corpus_materialization as materialization
from ng_corpus_quarantine_storage import (
    CorpusQuarantineError,
    _authority,
    _fp,
    _validate_authority,
)

SCHEMA = "ng_corpus_exact_pair_alignment_gate.v1"


def _verify(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise CorpusQuarantineError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _validated_probe(value: Mapping[str, Any]) -> dict[str, Any]:
    checked = _verify(value, "probe_fingerprint", label="identity probe")
    if checked.get("schema") != "ng_corpus_identity_probe.v1":
        raise CorpusQuarantineError("identity probe schema mismatch")
    if checked.get("status") != "REVIEW_REQUIRED":
        raise CorpusQuarantineError("identity probe status mismatch")
    _validate_authority(checked, label="identity probe")
    rows = list(checked.get("objects") or [])
    if checked.get("probed_object_count") != len(rows):
        raise CorpusQuarantineError("identity probe object count mismatch")
    seen: set[str] = set()
    for raw in rows:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("probe_object_fingerprint", None)
        if observed != _fp(row):
            raise CorpusQuarantineError("identity probe object fingerprint mismatch")
        object_id = str(raw.get("object_id") or "")
        if not object_id or object_id in seen:
            raise CorpusQuarantineError("identity probe has missing or duplicate object_id")
        seen.add(object_id)
        evidence = {
            key: raw[key]
            for key in (
                "status",
                "record_count",
                "event_start_s",
                "event_end_s",
                "datasets",
                "publisher_ids",
                "instrument_ids",
                "decoded_raw_symbols",
                "source_schemas",
                "transport_metadata",
                "event_types",
                "proposed_lane",
                "matching_definition_fingerprints",
                "unique_definition",
                "identity_inferred_from_object_name",
            )
        }
        if raw.get("evidence_fingerprint") != _fp(evidence):
            raise CorpusQuarantineError("identity probe evidence fingerprint mismatch")
    return checked


def _pair_rows(
    *, reviewed_bindings: Mapping[str, Any], probe: Mapping[str, Any]
) -> list[dict[str, Any]]:
    evidence_by_id = {str(row["object_id"]): row for row in probe["objects"]}
    approved = [row for row in reviewed_bindings["bindings"] if row["review_status"] == "APPROVED"]
    rows = []
    for group, (days, contract_map) in coverage.TARGETS.items():
        for day in days:
            expected = contract_map[day]
            lane_results: dict[str, Any] = {}
            selected: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
            for lane in coverage.LANES:
                same_day = [
                    binding
                    for binding in approved
                    if str(binding.get("day") or "").replace("-", "") == day
                    and binding.get("lane") == lane
                ]
                exact = []
                for binding in same_day:
                    definition = binding.get("definition") or {}
                    if (
                        definition.get("dataset") == coverage.DATASET
                        and definition.get("raw_symbol") == expected["raw_symbol"]
                        and int(definition.get("instrument_id") or -1) == int(expected["instrument_id"])
                    ):
                        object_id = str(binding.get("object_id") or "")
                        evidence = evidence_by_id.get(object_id)
                        if evidence is None:
                            raise CorpusQuarantineError("approved binding is missing probe evidence")
                        if binding.get("probe_evidence_fingerprint") != evidence.get("evidence_fingerprint"):
                            raise CorpusQuarantineError("approved binding probe provenance mismatch")
                        exact.append((binding, evidence))
                if len(exact) == 1:
                    lane_status = "READY"
                    selected[lane] = exact[0]
                elif len(exact) > 1:
                    lane_status = "DUPLICATE_EXACT_BASIS"
                elif same_day:
                    lane_status = "WRONG_BASIS"
                else:
                    lane_status = "MISSING"
                lane_results[lane] = {
                    "status": lane_status,
                    "exact_source_ids": sorted(str(pair[0]["source_id"]) for pair in exact),
                    "approved_source_ids": sorted(str(binding["source_id"]) for binding in same_day),
                }

            blockers: list[str] = []
            overlap = None
            publisher_id = None
            definition_period = None
            if set(selected) == set(coverage.LANES):
                l1_binding, l1_evidence = selected["l1_trades"]
                mbo_binding, mbo_evidence = selected["mbo"]
                l1_definition = l1_binding["definition"]
                mbo_definition = mbo_binding["definition"]
                l1_publisher = int(l1_definition["publisher_id"])
                mbo_publisher = int(mbo_definition["publisher_id"])
                if l1_publisher != mbo_publisher:
                    blockers.append("PUBLISHER_MISMATCH")
                else:
                    publisher_id = l1_publisher
                l1_period = (
                    float(l1_definition["definition_start_s"]),
                    float(l1_definition["definition_end_s"]),
                )
                mbo_period = (
                    float(mbo_definition["definition_start_s"]),
                    float(mbo_definition["definition_end_s"]),
                )
                if l1_period != mbo_period:
                    blockers.append("DEFINITION_PERIOD_MISMATCH")
                else:
                    definition_period = {
                        "definition_start_s": l1_period[0],
                        "definition_end_s": l1_period[1],
                    }
                event_start = max(
                    float(l1_evidence["event_start_s"]), float(mbo_evidence["event_start_s"])
                )
                event_end = min(
                    float(l1_evidence["event_end_s"]), float(mbo_evidence["event_end_s"])
                )
                if event_end < event_start:
                    blockers.append("EVENT_TIME_NONOVERLAP")
                else:
                    overlap = {"event_start_s": event_start, "event_end_s": event_end}
            ready = (
                all(lane_results[lane]["status"] == "READY" for lane in coverage.LANES)
                and not blockers
            )
            rows.append(
                {
                    "group": group,
                    "day": day,
                    "expected_dataset": coverage.DATASET,
                    "expected_raw_symbol": expected["raw_symbol"],
                    "expected_instrument_id": expected["instrument_id"],
                    "lanes": lane_results,
                    "publisher_id": publisher_id,
                    "definition_period": definition_period,
                    "event_time_overlap": overlap,
                    "pair_blockers": blockers,
                    "status": "MATCHED_L1_MBO_READY" if ready else "BLOCKED",
                }
            )
    return rows


def build_alignment_gate(
    *,
    review_gate: Mapping[str, Any],
    reviewed_bindings: Mapping[str, Any],
    probe: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    checked_review = _verify(review_gate, "review_gate_fingerprint", label="binding review gate")
    if checked_review.get("schema") != review.GATE_SCHEMA:
        raise CorpusQuarantineError("binding review gate schema mismatch")
    _validate_authority(checked_review, label="binding review gate")
    snap = materialization.validate_snapshot(snapshot)
    bindings = materialization.validate_bindings(
        reviewed_bindings, snapshot=snap, require_approved=True
    )
    if checked_review.get("reviewed_binding_manifest_fingerprint") != bindings.get(
        "binding_manifest_fingerprint"
    ):
        raise CorpusQuarantineError("binding review gate manifest mismatch")
    probed = _validated_probe(probe)
    rows = _pair_rows(reviewed_bindings=bindings, probe=probed)
    groups = []
    for group in (15, 16):
        group_rows = [row for row in rows if row["group"] == group]
        groups.append(
            {
                "group": group,
                "status": (
                    "MATCHED_L1_MBO_READY"
                    if group_rows and all(row["status"] == "MATCHED_L1_MBO_READY" for row in group_rows)
                    else "BLOCKED"
                ),
                "days": group_rows,
            }
        )
    status = (
        "G15_G16_EXACT_PAIR_ALIGNMENT_READY"
        if all(group["status"] == "MATCHED_L1_MBO_READY" for group in groups)
        else "BLOCKED"
    )
    value = {
        "schema": SCHEMA,
        "status": status,
        "review_gate_fingerprint": checked_review["review_gate_fingerprint"],
        "reviewed_binding_manifest_fingerprint": bindings["binding_manifest_fingerprint"],
        "probe_fingerprint": probed["probe_fingerprint"],
        "groups": groups,
        "identity_level_readiness_is_not_pair_readiness": True,
        "exact_pair_requires_dataset_publisher_instrument_symbol_definition_period_and_event_overlap": True,
        "random_shuffle_used": False,
        **_authority(),
    }
    value["alignment_gate_fingerprint"] = _fp(value)
    validate_alignment_gate(
        value,
        review_gate=checked_review,
        reviewed_bindings=bindings,
        probe=probed,
        snapshot=snap,
    )
    return value


def validate_alignment_gate(
    value: Mapping[str, Any],
    *,
    review_gate: Mapping[str, Any],
    reviewed_bindings: Mapping[str, Any],
    probe: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    checked = _verify(value, "alignment_gate_fingerprint", label="exact pair alignment gate")
    if checked.get("schema") != SCHEMA:
        raise CorpusQuarantineError("exact pair alignment gate schema mismatch")
    _validate_authority(checked, label="exact pair alignment gate")
    if checked.get("random_shuffle_used") is not False:
        raise CorpusQuarantineError("exact pair alignment may not random-shuffle")
    if checked.get("identity_level_readiness_is_not_pair_readiness") is not True:
        raise CorpusQuarantineError("exact pair alignment weakened the readiness rule")
    if checked.get(
        "exact_pair_requires_dataset_publisher_instrument_symbol_definition_period_and_event_overlap"
    ) is not True:
        raise CorpusQuarantineError("exact pair alignment omitted required identity dimensions")
    reviewed = _verify(review_gate, "review_gate_fingerprint", label="binding review gate")
    snap = materialization.validate_snapshot(snapshot)
    bindings = materialization.validate_bindings(
        reviewed_bindings, snapshot=snap, require_approved=True
    )
    probed = _validated_probe(probe)
    expected_links = {
        "review_gate_fingerprint": reviewed["review_gate_fingerprint"],
        "reviewed_binding_manifest_fingerprint": bindings["binding_manifest_fingerprint"],
        "probe_fingerprint": probed["probe_fingerprint"],
    }
    for field, expected in expected_links.items():
        if checked.get(field) != expected:
            raise CorpusQuarantineError(f"exact pair alignment {field} mismatch")
    rows = _pair_rows(reviewed_bindings=bindings, probe=probed)
    groups = []
    for group in (15, 16):
        group_rows = [row for row in rows if row["group"] == group]
        groups.append(
            {
                "group": group,
                "status": (
                    "MATCHED_L1_MBO_READY"
                    if group_rows and all(row["status"] == "MATCHED_L1_MBO_READY" for row in group_rows)
                    else "BLOCKED"
                ),
                "days": group_rows,
            }
        )
    if checked.get("groups") != groups:
        raise CorpusQuarantineError("exact pair alignment groups were not reproduced")
    expected_status = (
        "G15_G16_EXACT_PAIR_ALIGNMENT_READY"
        if all(group["status"] == "MATCHED_L1_MBO_READY" for group in groups)
        else "BLOCKED"
    )
    if checked.get("status") != expected_status:
        raise CorpusQuarantineError("exact pair alignment status mismatch")
    return checked


def _load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _selftest() -> None:
    assert coverage.G15_CONTRACT_MAP["20260315"] == {
        "raw_symbol": "NGJ26",
        "instrument_id": 1008,
    }
    assert coverage.G16_CONTRACT_MAP["20260410"] == {
        "raw_symbol": "NGK26",
        "instrument_id": 996,
    }
    assert _authority()["options_lane_started"] is False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--review-gate", type=Path)
    parser.add_argument("--reviewed-bindings", type=Path)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print("ng_corpus_exact_pair_alignment_gate selftest: PASS")
        return
    if any(path is None for path in (args.review_gate, args.reviewed_bindings, args.probe, args.snapshot, args.out)):
        parser.error("review gate, reviewed bindings, probe, snapshot, and out are required")
    value = build_alignment_gate(
        review_gate=_load(args.review_gate),
        reviewed_bindings=_load(args.reviewed_bindings),
        probe=_load(args.probe),
        snapshot=_load(args.snapshot),
    )
    _write(args.out, value)


if __name__ == "__main__":
    main()
