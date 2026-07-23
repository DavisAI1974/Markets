#!/usr/bin/env python3
"""Review decoded NG corpus identities and lock evidence-based day assignments.

This is the manual-review seam between the provenance-locked quarantine probe and
canonical materialization. It never infers a session day from an object name. An
approved object must have one uniquely observed contract definition and its entire
event-time range must lie in one UTC calendar day; multi-day objects stand down and
must be split before approval.

The output is a reviewed ``ng_corpus_object_binding.v1`` manifest plus a fingerprinted
coverage report for the exact G15/G16 L1+MBO targets. Broad-corpus completeness and
exact-target readiness remain separate claims. The gate cannot read outcomes, change
a blind forecast or posterior, update ``knowledge/ng_brain.json``, authorize trading,
or start the options lane.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import ng_corpus_coverage_audit as coverage
import ng_corpus_definition_probe_gate as definition_gate
import ng_corpus_identity_probe as identity_probe
import ng_corpus_inspection as inspection
import ng_corpus_materialization as materialization
from ng_corpus_quarantine_storage import (
    CorpusQuarantineError,
    _authority,
    _fp,
    _validate_authority,
)

DECISION_SCHEMA = "ng_corpus_binding_review_decision.v1"
GATE_SCHEMA = "ng_corpus_binding_review_gate.v1"
DECISIONS = {"REVIEW_REQUIRED", "APPROVED", "REJECTED"}


def _verify(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise CorpusQuarantineError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _utc_days_for_range(start_s: Any, end_s: Any) -> list[str]:
    try:
        start = float(start_s)
        end = float(end_s)
    except (TypeError, ValueError, OverflowError) as error:
        raise CorpusQuarantineError("probe event range must be finite timestamps") from error
    if end < start:
        raise CorpusQuarantineError("probe event range moved backwards")
    start_day = datetime.fromtimestamp(start, tz=timezone.utc).date()
    end_day = datetime.fromtimestamp(end, tz=timezone.utc).date()
    days: list[str] = []
    day = start_day
    while day <= end_day:
        days.append(day.strftime("%Y%m%d"))
        day += timedelta(days=1)
        if len(days) > 370:
            raise CorpusQuarantineError("probe event range is implausibly wide")
    return days


def _canonical_source_id(lane: str, day: str, object_id: str) -> str:
    return f"review:{lane}:{day}:{object_id[:16]}"


def review_template(
    *,
    gate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Create an explicit-review template with event-time-derived day evidence."""
    locked = definition_gate.validate_gate(
        gate,
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=definition_catalog,
        probe=probe,
        proposed_bindings=proposed_bindings,
        verify_definition_files=True,
    )
    snap = materialization.validate_snapshot(snapshot)
    probed = identity_probe.validate_probe(
        probe,
        snapshot=snap,
        quarantine=quarantine,
        proposed_bindings=proposed_bindings,
    )
    proposal = materialization.validate_bindings(
        proposed_bindings, snapshot=snap, require_approved=False
    )
    proposal_by_id = {str(row["object_id"]): row for row in proposal["bindings"]}
    decisions = []
    for evidence in probed["objects"]:
        object_id = str(evidence["object_id"])
        binding = proposal_by_id[object_id]
        days = _utc_days_for_range(evidence["event_start_s"], evidence["event_end_s"])
        row = {
            "object_id": object_id,
            "location": evidence["location"],
            "decision": "REVIEW_REQUIRED",
            "assigned_day": days[0] if len(days) == 1 else None,
            "event_time_utc_days": days,
            "split_required": len(days) != 1,
            "source_id": (
                _canonical_source_id(str(binding.get("lane") or "unknown"), days[0], object_id)
                if len(days) == 1 and binding.get("lane")
                else None
            ),
            "corpus_id": binding.get("corpus_id"),
            "lane": binding.get("lane"),
            "probe_status": evidence["status"],
            "probe_evidence_fingerprint": evidence["evidence_fingerprint"],
            "unique_definition_fingerprint": (
                evidence["unique_definition"]["definition_fingerprint"]
                if isinstance(evidence.get("unique_definition"), Mapping)
                else None
            ),
            "review_note": "",
        }
        row["decision_fingerprint"] = _fp(row)
        decisions.append(row)
    decisions.sort(key=lambda row: row["object_id"])
    value = {
        "schema": DECISION_SCHEMA,
        "status": "REVIEW_REQUIRED",
        "definition_probe_gate_fingerprint": locked["gate_fingerprint"],
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "probe_fingerprint": probed["probe_fingerprint"],
        "proposed_binding_manifest_fingerprint": proposal["binding_manifest_fingerprint"],
        "reviewed_by": None,
        "reviewed_at": None,
        "review_basis": "DECODED_EVENT_TIME_AND_OBSERVED_DEFINITION",
        "corpora": copy.deepcopy(proposal["corpora"]),
        "decisions": decisions,
        "all_objects_require_explicit_review": True,
        "session_day_inferred_from_object_name": False,
        **_authority(),
    }
    value["review_decision_fingerprint"] = _fp(value)
    validate_review_decisions(
        value,
        gate=locked,
        probe=probed,
        proposed_bindings=proposal,
        require_complete=False,
    )
    return value


def validate_review_decisions(
    value: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
    require_complete: bool,
) -> dict[str, Any]:
    checked = _verify(value, "review_decision_fingerprint", label="binding review decisions")
    if checked.get("schema") != DECISION_SCHEMA:
        raise CorpusQuarantineError("binding review decision schema mismatch")
    _validate_authority(checked, label="binding review decisions")
    if checked.get("all_objects_require_explicit_review") is not True:
        raise CorpusQuarantineError("binding review must require explicit review for every object")
    if checked.get("session_day_inferred_from_object_name") is not False:
        raise CorpusQuarantineError("binding review inferred a day from an object name")
    if checked.get("review_basis") != "DECODED_EVENT_TIME_AND_OBSERVED_DEFINITION":
        raise CorpusQuarantineError("binding review basis mismatch")
    if checked.get("definition_probe_gate_fingerprint") != gate.get("gate_fingerprint"):
        raise CorpusQuarantineError("binding review gate provenance mismatch")
    if checked.get("probe_fingerprint") != probe.get("probe_fingerprint"):
        raise CorpusQuarantineError("binding review probe provenance mismatch")
    if checked.get("proposed_binding_manifest_fingerprint") != proposed_bindings.get(
        "binding_manifest_fingerprint"
    ):
        raise CorpusQuarantineError("binding review proposal provenance mismatch")

    evidence_by_id = {str(row["object_id"]): row for row in probe["objects"]}
    proposal_by_id = {str(row["object_id"]): row for row in proposed_bindings["bindings"]}
    rows = list(checked.get("decisions") or [])
    if {str(row.get("object_id") or "") for row in rows} != set(evidence_by_id):
        raise CorpusQuarantineError("binding review decisions do not cover probed objects exactly")
    seen: set[str] = set()
    complete = True
    for raw in rows:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("decision_fingerprint", None)
        if observed != _fp(row):
            raise CorpusQuarantineError("binding review object fingerprint mismatch")
        object_id = str(raw.get("object_id") or "")
        if object_id in seen:
            raise CorpusQuarantineError("binding review contains duplicate object decisions")
        seen.add(object_id)
        evidence = evidence_by_id[object_id]
        proposal = proposal_by_id[object_id]
        if raw.get("location") != evidence.get("location"):
            raise CorpusQuarantineError("binding review object location mismatch")
        if raw.get("probe_status") != evidence.get("status"):
            raise CorpusQuarantineError("binding review probe status mismatch")
        if raw.get("probe_evidence_fingerprint") != evidence.get("evidence_fingerprint"):
            raise CorpusQuarantineError("binding review evidence fingerprint mismatch")
        days = _utc_days_for_range(evidence["event_start_s"], evidence["event_end_s"])
        if raw.get("event_time_utc_days") != days:
            raise CorpusQuarantineError("binding review UTC day evidence mismatch")
        split_required = len(days) != 1
        if raw.get("split_required") is not split_required:
            raise CorpusQuarantineError("binding review split-required flag mismatch")
        if raw.get("corpus_id") != proposal.get("corpus_id") or raw.get("lane") != proposal.get("lane"):
            raise CorpusQuarantineError("binding review lane/corpus differs from probe proposal")
        unique = evidence.get("unique_definition")
        unique_fp = unique.get("definition_fingerprint") if isinstance(unique, Mapping) else None
        if raw.get("unique_definition_fingerprint") != unique_fp:
            raise CorpusQuarantineError("binding review unique-definition provenance mismatch")
        decision = str(raw.get("decision") or "")
        if decision not in DECISIONS:
            raise CorpusQuarantineError(f"invalid binding review decision {decision!r}")
        if decision == "REVIEW_REQUIRED":
            complete = False
            continue
        if decision == "REJECTED":
            if raw.get("assigned_day") not in (None, "") or raw.get("source_id") not in (None, ""):
                raise CorpusQuarantineError("rejected object may not retain a day or source_id")
            continue
        if evidence.get("status") != "UNIQUE_DEFINITION_MATCH" or not isinstance(unique, Mapping):
            raise CorpusQuarantineError("only a unique observed definition may be approved")
        if split_required:
            raise CorpusQuarantineError("multi-day source must be split before approval")
        assigned_day = str(raw.get("assigned_day") or "").replace("-", "")
        if assigned_day != days[0]:
            raise CorpusQuarantineError("approved day must equal the decoded event-time UTC day")
        lane = str(raw.get("lane") or "")
        expected_source_id = _canonical_source_id(lane, assigned_day, object_id)
        if raw.get("source_id") != expected_source_id:
            raise CorpusQuarantineError("approved source_id is not canonical")
        expected = coverage.EXPECTED_WINDOWS.get(str(raw.get("corpus_id") or ""))
        if expected is None or not materialization._day_in_window(
            assigned_day, start=expected["start"], end_exclusive=expected["end_exclusive"]
        ):
            raise CorpusQuarantineError("approved event-time day lies outside corpus window")
        inspection.validate_definition(unique)
    if require_complete:
        if not complete:
            raise CorpusQuarantineError("binding review is incomplete")
        if not str(checked.get("reviewed_by") or "").strip() or not str(
            checked.get("reviewed_at") or ""
        ).strip():
            raise CorpusQuarantineError("completed binding review requires reviewer and timestamp")
        if checked.get("status") != "REVIEW_COMPLETE":
            raise CorpusQuarantineError("completed binding review status mismatch")
    elif checked.get("status") not in {"REVIEW_REQUIRED", "REVIEW_COMPLETE"}:
        raise CorpusQuarantineError("binding review status mismatch")
    return checked


def _target_coverage(reviewed_bindings: Mapping[str, Any]) -> dict[str, Any]:
    approved = [row for row in reviewed_bindings["bindings"] if row["review_status"] == "APPROVED"]
    groups = []
    for group, (days, contract_map) in coverage.TARGETS.items():
        day_rows = []
        group_ready = True
        for day in days:
            expected_identity = contract_map[day]
            lanes: dict[str, Any] = {}
            for lane in coverage.LANES:
                same_day = [
                    row
                    for row in approved
                    if str(row.get("day") or "").replace("-", "") == day
                    and row.get("lane") == lane
                ]
                exact = [
                    row
                    for row in same_day
                    if row["definition"]["dataset"] == coverage.DATASET
                    and row["definition"]["raw_symbol"] == expected_identity["raw_symbol"]
                    and int(row["definition"]["instrument_id"]) == int(expected_identity["instrument_id"])
                ]
                if len(exact) == 1:
                    status = "READY"
                elif len(exact) > 1:
                    status = "DUPLICATE_EXACT_BASIS"
                    group_ready = False
                elif same_day:
                    status = "WRONG_BASIS"
                    group_ready = False
                else:
                    status = "MISSING"
                    group_ready = False
                lanes[lane] = {
                    "status": status,
                    "exact_source_ids": sorted(str(row["source_id"]) for row in exact),
                    "approved_source_ids": sorted(str(row["source_id"]) for row in same_day),
                }
            day_rows.append(
                {
                    "day": day,
                    "expected_raw_symbol": expected_identity["raw_symbol"],
                    "expected_instrument_id": expected_identity["instrument_id"],
                    "lanes": lanes,
                    "status": (
                        "MATCHED_L1_MBO_READY"
                        if all(lanes[lane]["status"] == "READY" for lane in coverage.LANES)
                        else "BLOCKED"
                    ),
                }
            )
        groups.append(
            {
                "group": group,
                "status": "MATCHED_L1_MBO_READY" if group_ready else "BLOCKED",
                "days": day_rows,
            }
        )
    return {"groups": groups}


def _broad_coverage(reviewed_bindings: Mapping[str, Any], snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    approved = [row for row in reviewed_bindings["bindings"] if row["review_status"] == "APPROVED"]
    results = []
    for control in reviewed_bindings["corpora"]:
        corpus_id = str(control["corpus_id"])
        rows = [row for row in approved if row.get("corpus_id") == corpus_id]
        approved_days = sorted({str(row["day"]).replace("-", "") for row in rows})
        expected_days = sorted(str(day).replace("-", "") for day in control.get("expected_days") or [])
        asserted = control.get("inventory_complete_asserted") is True
        if asserted:
            if not materialization.checked_snapshot_scope(snapshot, control):
                raise CorpusQuarantineError("broad corpus completeness lacks verified snapshot scope")
            if approved_days != expected_days:
                raise CorpusQuarantineError("broad corpus approved days differ from expected days")
            if int(control.get("expected_object_count") or 0) != len(rows):
                raise CorpusQuarantineError("broad corpus approved count differs from expected count")
            status = "VERIFIED_COMPLETE"
        else:
            status = "UNVERIFIED"
        results.append(
            {
                "corpus_id": corpus_id,
                "status": status,
                "approved_object_count": len(rows),
                "approved_days": approved_days,
                "expected_days": expected_days,
            }
        )
    return results


def complete_review(
    *,
    decisions: Mapping[str, Any],
    gate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Lock explicit decisions and emit the canonical reviewed binding manifest."""
    locked_gate = definition_gate.validate_gate(
        gate,
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=definition_catalog,
        probe=probe,
        proposed_bindings=proposed_bindings,
        verify_definition_files=True,
    )
    snap = materialization.validate_snapshot(snapshot)
    probed = identity_probe.validate_probe(
        probe,
        snapshot=snap,
        quarantine=quarantine,
        proposed_bindings=proposed_bindings,
    )
    proposal = materialization.validate_bindings(
        proposed_bindings, snapshot=snap, require_approved=False
    )
    reviewed_decisions = validate_review_decisions(
        decisions,
        gate=locked_gate,
        probe=probed,
        proposed_bindings=proposal,
        require_complete=True,
    )
    decision_by_id = {str(row["object_id"]): row for row in reviewed_decisions["decisions"]}
    evidence_by_id = {str(row["object_id"]): row for row in probed["objects"]}
    reviewed = copy.deepcopy(proposal)
    reviewed["corpora"] = copy.deepcopy(reviewed_decisions["corpora"])
    reviewed["review_decision_fingerprint"] = reviewed_decisions["review_decision_fingerprint"]
    reviewed["definition_probe_gate_fingerprint"] = locked_gate["gate_fingerprint"]
    for binding in reviewed["bindings"]:
        decision = decision_by_id[str(binding["object_id"])]
        evidence = evidence_by_id[str(binding["object_id"])]
        if decision["decision"] == "APPROVED":
            binding.update(
                review_status="APPROVED",
                source_id=decision["source_id"],
                day=decision["assigned_day"],
                definition=copy.deepcopy(evidence["unique_definition"]),
            )
        else:
            binding.update(
                review_status="REJECTED",
                source_id=None,
                day=None,
                definition=None,
            )
        binding["reviewed_by"] = reviewed_decisions["reviewed_by"]
        binding["reviewed_at"] = reviewed_decisions["reviewed_at"]
        binding["event_time_utc_days"] = list(decision["event_time_utc_days"])
        binding["review_decision_fingerprint"] = decision["decision_fingerprint"]
        binding.pop("binding_fingerprint", None)
        binding["binding_fingerprint"] = _fp(binding)
    reviewed.pop("binding_manifest_fingerprint", None)
    reviewed["binding_manifest_fingerprint"] = _fp(reviewed)
    materialization.validate_bindings(reviewed, snapshot=snap, require_approved=True)

    target = _target_coverage(reviewed)
    broad = _broad_coverage(reviewed, snap)
    target_ready = all(group["status"] == "MATCHED_L1_MBO_READY" for group in target["groups"])
    broad_ready = all(row["status"] == "VERIFIED_COMPLETE" for row in broad)
    if target_ready and broad_ready:
        status = "REVIEW_COMPLETE_FULL_CORPUS_AND_EXACT_TARGETS_READY"
    elif target_ready:
        status = "REVIEW_COMPLETE_EXACT_TARGETS_READY_BROAD_UNVERIFIED"
    else:
        status = "REVIEW_COMPLETE_TARGETS_BLOCKED"
    artifact = {
        "schema": GATE_SCHEMA,
        "status": status,
        "definition_probe_gate_fingerprint": locked_gate["gate_fingerprint"],
        "review_decision_fingerprint": reviewed_decisions["review_decision_fingerprint"],
        "reviewed_binding_manifest_fingerprint": reviewed["binding_manifest_fingerprint"],
        "reviewed_by": reviewed_decisions["reviewed_by"],
        "reviewed_at": reviewed_decisions["reviewed_at"],
        "approved_object_count": sum(
            1 for row in reviewed["bindings"] if row["review_status"] == "APPROVED"
        ),
        "rejected_object_count": sum(
            1 for row in reviewed["bindings"] if row["review_status"] == "REJECTED"
        ),
        "broad_corpora": broad,
        "exact_targets": target["groups"],
        "materialization_permitted_for_approved_objects": True,
        "automatic_approval_permitted": False,
        "multi_day_objects_require_split": True,
        "session_day_inferred_from_object_name": False,
        **_authority(),
    }
    artifact["review_gate_fingerprint"] = _fp(artifact)
    validate_completed_review(
        artifact,
        decisions=reviewed_decisions,
        reviewed_bindings=reviewed,
        gate=locked_gate,
        snapshot=snap,
    )
    return artifact, reviewed


def validate_completed_review(
    value: Mapping[str, Any],
    *,
    decisions: Mapping[str, Any],
    reviewed_bindings: Mapping[str, Any],
    gate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    checked = _verify(value, "review_gate_fingerprint", label="binding review gate")
    if checked.get("schema") != GATE_SCHEMA:
        raise CorpusQuarantineError("binding review gate schema mismatch")
    _validate_authority(checked, label="binding review gate")
    if checked.get("automatic_approval_permitted") is not False:
        raise CorpusQuarantineError("binding review gate may not auto-approve")
    if checked.get("multi_day_objects_require_split") is not True:
        raise CorpusQuarantineError("binding review gate must split multi-day sources")
    if checked.get("session_day_inferred_from_object_name") is not False:
        raise CorpusQuarantineError("binding review gate inferred a day from an object name")
    reviewed_decisions = _verify(
        decisions, "review_decision_fingerprint", label="binding review decisions"
    )
    if reviewed_decisions.get("schema") != DECISION_SCHEMA:
        raise CorpusQuarantineError("binding review decision schema mismatch")
    _validate_authority(reviewed_decisions, label="binding review decisions")
    if reviewed_decisions.get("status") != "REVIEW_COMPLETE":
        raise CorpusQuarantineError("binding review decisions are not complete")
    if not str(reviewed_decisions.get("reviewed_by") or "").strip() or not str(
        reviewed_decisions.get("reviewed_at") or ""
    ).strip():
        raise CorpusQuarantineError("binding review decisions omit reviewer provenance")
    snap = materialization.validate_snapshot(snapshot)
    reviewed = materialization.validate_bindings(
        reviewed_bindings, snapshot=snap, require_approved=True
    )
    if checked.get("definition_probe_gate_fingerprint") != gate.get("gate_fingerprint"):
        raise CorpusQuarantineError("binding review gate upstream mismatch")
    if checked.get("review_decision_fingerprint") != reviewed_decisions.get(
        "review_decision_fingerprint"
    ):
        raise CorpusQuarantineError("binding review gate decision mismatch")
    if checked.get("reviewed_binding_manifest_fingerprint") != reviewed.get(
        "binding_manifest_fingerprint"
    ):
        raise CorpusQuarantineError("binding review gate manifest mismatch")
    target = _target_coverage(reviewed)["groups"]
    broad = _broad_coverage(reviewed, snap)
    if checked.get("exact_targets") != target or checked.get("broad_corpora") != broad:
        raise CorpusQuarantineError("binding review gate coverage was not reproduced")
    approved = sum(1 for row in reviewed["bindings"] if row["review_status"] == "APPROVED")
    rejected = sum(1 for row in reviewed["bindings"] if row["review_status"] == "REJECTED")
    if checked.get("approved_object_count") != approved or checked.get("rejected_object_count") != rejected:
        raise CorpusQuarantineError("binding review gate decision counts mismatch")
    target_ready = all(group["status"] == "MATCHED_L1_MBO_READY" for group in target)
    broad_ready = all(row["status"] == "VERIFIED_COMPLETE" for row in broad)
    expected_status = (
        "REVIEW_COMPLETE_FULL_CORPUS_AND_EXACT_TARGETS_READY"
        if target_ready and broad_ready
        else "REVIEW_COMPLETE_EXACT_TARGETS_READY_BROAD_UNVERIFIED"
        if target_ready
        else "REVIEW_COMPLETE_TARGETS_BLOCKED"
    )
    if checked.get("status") != expected_status:
        raise CorpusQuarantineError("binding review gate status mismatch")
    if checked.get("materialization_permitted_for_approved_objects") is not True:
        raise CorpusQuarantineError("binding review gate materialization flag mismatch")
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
    start = datetime(2026, 3, 15, 0, 1, tzinfo=timezone.utc).timestamp()
    end = datetime(2026, 3, 15, 23, 59, tzinfo=timezone.utc).timestamp()
    assert _utc_days_for_range(start, end) == ["20260315"]
    assert _canonical_source_id("mbo", "20260315", "a" * 64) == "review:mbo:20260315:aaaaaaaaaaaaaaaa"
    cross = datetime(2026, 3, 16, 0, 1, tzinfo=timezone.utc).timestamp()
    assert _utc_days_for_range(start, cross) == ["20260315", "20260316"]
    assert _authority()["options_lane_started"] is False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--definition-catalog", type=Path)
    parser.add_argument("--definition-probe-gate", type=Path)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--proposed-bindings", type=Path)
    parser.add_argument("--review-decisions", type=Path)
    parser.add_argument("--template-out", type=Path)
    parser.add_argument("--gate-out", type=Path)
    parser.add_argument("--bindings-out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        print("ng_corpus_binding_review_gate selftest: PASS")
        return
    required = (
        args.snapshot,
        args.quarantine,
        args.definition_catalog,
        args.definition_probe_gate,
        args.probe,
        args.proposed_bindings,
    )
    if any(path is None for path in required):
        parser.error("snapshot, quarantine, definition catalog, probe gate, probe, and proposed bindings are required")
    common = {
        "snapshot": _load(args.snapshot),
        "quarantine": _load(args.quarantine),
        "definition_catalog": _load(args.definition_catalog),
        "gate": _load(args.definition_probe_gate),
        "probe": _load(args.probe),
        "proposed_bindings": _load(args.proposed_bindings),
    }
    if args.review_decisions is None:
        if args.template_out is None:
            parser.error("--template-out is required when creating a review template")
        _write(args.template_out, review_template(**common))
        return
    if args.gate_out is None or args.bindings_out is None:
        parser.error("--gate-out and --bindings-out are required when completing review")
    artifact, bindings = complete_review(decisions=_load(args.review_decisions), **common)
    _write(args.gate_out, artifact)
    _write(args.bindings_out, bindings)


if __name__ == "__main__":
    main()
