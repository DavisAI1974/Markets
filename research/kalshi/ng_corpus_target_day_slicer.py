#!/usr/bin/env python3
"""Slice cumulative NG corpus objects into exact event-time target-day sources.

Some historical MBO objects are cumulative or span more than one UTC day. The corpus
binding review correctly refuses to assign such an object to one day, but the exact
G15/G16 replay chain still needs one immutable source per target day and lane. This
module closes that seam without using filenames, S3 keys, or continuous symbols.

The slicer accepts only provenance-locked, uniquely defined quarantine objects. It
streams each source, normalizes matching records through the existing replay contract,
and writes deterministic per-UTC-day JSONL shards for the Friday G15 anchor plus every
canonical G15 and G16 day. Multiple source objects for the same exact day/lane are
accepted only when their normalized shard bytes are identical. Conflicting candidates
stand down visibly; no source is selected by file name, modification time, or record
count alone.

The output includes an ``ng_corpus_inspection_plan.v1`` that can feed the existing
byte-level inspector and coverage audit. Broad one-year/spring-summer completeness is
never inferred from target slicing. Outcomes remain unavailable, blind forecasts and
posterior state remain immutable, ``knowledge/ng_brain.json`` cannot be updated, CME
event contracts remain SHADOW, tastytrade remains the brokerage contract, and the
options lane remains unstarted.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import ng_corpus_coverage_audit as coverage
import ng_corpus_definition_probe_gate as definition_gate
import ng_corpus_identity_probe as identity_probe
import ng_corpus_inspection as inspection
import ng_corpus_materialization as materialization
import ng_definition_observation as definition_observation
import ng_historical_normalize as normalize
from ng_corpus_quarantine_storage import (
    CorpusQuarantineError,
    _authority,
    _fp,
    _sha256,
    _validate_authority,
    validate_quarantine,
)

SCHEMA = "ng_corpus_target_day_slice_bundle.v1"
ANCHOR_DAY = "20260313"
ANCHOR_IDENTITY = {"raw_symbol": "NGJ26", "instrument_id": 1008}
LANE_TO_KIND = {"l1_trades": "trade", "mbo": "mbo"}
READY_LANE_STATUSES = {"UNIQUE_SLICE_READY", "IDENTICAL_DUPLICATE_SLICES_READY"}


class TargetDaySliceError(ValueError):
    """Raised when exact target-day slicing or provenance validation fails."""


def _verify(value: Mapping[str, Any], field: str, *, label: str) -> dict[str, Any]:
    payload = copy.deepcopy(dict(value))
    observed = payload.pop(field, None)
    if not isinstance(observed, str) or observed != _fp(payload):
        raise TargetDaySliceError(f"{label}: {field} mismatch")
    return copy.deepcopy(dict(value))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def _canonical_event(event: Mapping[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _utc_day(timestamp: float) -> str:
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).strftime("%Y%m%d")


def _target_identity(day: str) -> dict[str, Any] | None:
    if day == ANCHOR_DAY:
        return copy.deepcopy(ANCHOR_IDENTITY)
    if day in coverage.G15_CONTRACT_MAP:
        return copy.deepcopy(coverage.G15_CONTRACT_MAP[day])
    if day in coverage.G16_CONTRACT_MAP:
        return copy.deepcopy(coverage.G16_CONTRACT_MAP[day])
    return None


def _target_days() -> tuple[str, ...]:
    return (ANCHOR_DAY, *coverage.G15_DATES, *coverage.G16_DATES)


def _target_label(day: str) -> str:
    if day == ANCHOR_DAY:
        return "G15_ANCHOR"
    if day in coverage.G15_CONTRACT_MAP:
        return "G15"
    if day in coverage.G16_CONTRACT_MAP:
        return "G16"
    raise TargetDaySliceError(f"unexpected target day {day}")


def _corpus_id(lane: str) -> str:
    if lane == "l1_trades":
        return coverage.L1_CORPUS_ID
    if lane == "mbo":
        return coverage.MBO_CORPUS_ID
    raise TargetDaySliceError(f"unsupported lane {lane!r}")


def _is_dbn(path: Path) -> bool:
    lower = path.name.lower()
    return lower.endswith(".dbn") or lower.endswith(".dbn.zst") or lower.endswith(".zst")


def _iter_raw(path: Path) -> Iterable[Any]:
    return normalize.iter_dbn(path) if _is_dbn(path) else normalize.iter_jsonl(path)


def _validate_chain(
    *,
    gate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
    verify_definition_files: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    snap = materialization.validate_snapshot(snapshot)
    quarantined = validate_quarantine(quarantine, snapshot=snap, verify_files=True)
    catalog = definition_observation.validate_catalog(
        definition_catalog, verify_files=verify_definition_files
    )
    probed = identity_probe.validate_probe(
        probe,
        snapshot=snap,
        quarantine=quarantined,
        proposed_bindings=proposed_bindings,
    )
    bindings = materialization.validate_bindings(
        proposed_bindings, snapshot=snap, require_approved=False
    )
    locked = definition_gate.validate_gate(
        gate,
        snapshot=snap,
        quarantine=quarantined,
        definition_catalog=catalog,
        probe=probed,
        proposed_bindings=bindings,
        verify_definition_files=verify_definition_files,
    )
    return locked, snap, quarantined, catalog, probed, bindings


def _candidate_source_id(*, lane: str, day: str, definition: Mapping[str, Any]) -> str:
    return (
        f"target-slice:{lane}:{day}:{definition['dataset']}:{definition['publisher_id']}:"
        f"{definition['instrument_id']}:{definition['raw_symbol']}:"
        f"{str(definition['definition_fingerprint'])[:16]}"
    )


def _slice_one_object(
    *,
    evidence: Mapping[str, Any],
    quarantine_row: Mapping[str, Any],
    proposed_binding: Mapping[str, Any],
    stage: Path,
) -> list[dict[str, Any]]:
    if evidence.get("status") != "UNIQUE_DEFINITION_MATCH":
        return []
    lane = str(evidence.get("proposed_lane") or "")
    if lane not in LANE_TO_KIND:
        return []
    definition_raw = evidence.get("unique_definition")
    if not isinstance(definition_raw, Mapping):
        raise TargetDaySliceError("unique definition evidence is missing")
    definition = inspection.validate_definition(definition_raw)
    path = Path(str(quarantine_row.get("quarantine_path") or "")).expanduser().resolve()
    before_size = path.stat().st_size
    before_sha = _sha256(path)
    if before_size != int(quarantine_row["size_bytes"]) or before_sha != quarantine_row["sha256"]:
        raise TargetDaySliceError(f"quarantine bytes changed before slicing: {path}")

    handles: dict[str, Any] = {}
    temporary_paths: dict[str, Path] = {}
    final_paths: dict[str, Path] = {}
    counts: dict[str, int] = {}
    starts: dict[str, float] = {}
    ends: dict[str, float] = {}
    previous: tuple[float, int, int] | None = None
    input_count = 0
    skipped_nonmatching = 0
    skipped_nontarget = 0
    try:
        for input_count, raw in enumerate(_iter_raw(path), 1):
            if not normalize.record_matches_kind(raw, LANE_TO_KIND[lane]):
                if lane == "l1_trades" or proposed_binding.get("skip_nonmatching") is True:
                    skipped_nonmatching += 1
                    continue
                raise TargetDaySliceError(
                    f"{path}: record {input_count} does not match lane {lane}"
                )
            timestamp = normalize.event_seconds(
                normalize._value(raw, "ts_event_s", "ts_event", "timestamp", "ts", "ts_recv")
            )
            source_sequence_raw = normalize._value(
                raw,
                "source_sequence",
                "sequence",
                "sequence_number",
                default=input_count,
            )
            try:
                source_sequence = int(source_sequence_raw)
            except (TypeError, ValueError, OverflowError):
                source_sequence = input_count
            key = (float(timestamp), source_sequence, input_count)
            if previous is not None and key < previous:
                raise TargetDaySliceError(
                    f"source moved backwards at record {input_count}: {path}"
                )
            previous = key
            if timestamp < float(definition["definition_start_s"]) or timestamp > float(
                definition["definition_end_s"]
            ):
                raise TargetDaySliceError(
                    f"record {input_count} falls outside observed definition period"
                )
            day = _utc_day(timestamp)
            expected = _target_identity(day)
            if expected is None:
                skipped_nontarget += 1
                continue
            if (
                definition["raw_symbol"] != expected["raw_symbol"]
                or int(definition["instrument_id"]) != int(expected["instrument_id"])
            ):
                skipped_nontarget += 1
                continue
            shard_sequence = counts.get(day, 0) + 1
            event = normalize.normalize_record(
                raw,
                event_type=LANE_TO_KIND[lane],
                dataset=str(definition["dataset"]),
                publisher_id=int(definition["publisher_id"]),
                instrument_id=int(definition["instrument_id"]),
                raw_symbol=str(definition["raw_symbol"]),
                definition_date=str(definition["definition_date"]),
                session_day=day,
                source_id=_candidate_source_id(lane=lane, day=day, definition=definition),
                ingest_sequence=shard_sequence,
            )
            if day not in handles:
                name = f"{str(evidence['object_id'])[:20]}_{lane}_{day}.jsonl"
                final_path = stage / name
                temp_path = stage / (name + ".partial")
                handles[day] = temp_path.open("w", encoding="utf-8")
                temporary_paths[day] = temp_path
                final_paths[day] = final_path
            handles[day].write(_canonical_event(event) + "\n")
            counts[day] = shard_sequence
            starts.setdefault(day, float(timestamp))
            ends[day] = float(timestamp)
        for handle in handles.values():
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
        handles.clear()
        candidates: list[dict[str, Any]] = []
        for day in sorted(counts):
            os.replace(temporary_paths[day], final_paths[day])
            row = {
                "candidate_id": _fp(
                    {
                        "object_id": evidence["object_id"],
                        "lane": lane,
                        "day": day,
                        "definition_fingerprint": definition["definition_fingerprint"],
                    }
                ),
                "object_id": evidence["object_id"],
                "source_location": evidence["location"],
                "quarantine_object_fingerprint": quarantine_row[
                    "quarantine_object_fingerprint"
                ],
                "probe_object_fingerprint": evidence["probe_object_fingerprint"],
                "probe_evidence_fingerprint": evidence["evidence_fingerprint"],
                "proposed_binding_fingerprint": proposed_binding["binding_fingerprint"],
                "corpus_id": _corpus_id(lane),
                "target": _target_label(day),
                "day": day,
                "lane": lane,
                "definition": copy.deepcopy(definition),
                "definition_fingerprint": definition["definition_fingerprint"],
                "materialized_path": str(final_paths[day]),
                "record_count": counts[day],
                "event_start_s": starts[day],
                "event_end_s": ends[day],
                "size_bytes": final_paths[day].stat().st_size,
                "sha256": _sha256(final_paths[day]),
                "normalized_source_id": _candidate_source_id(
                    lane=lane, day=day, definition=definition
                ),
                "input_record_count": input_count,
                "skipped_nonmatching": skipped_nonmatching,
                "skipped_nontarget": skipped_nontarget,
                "derived_from_cumulative_or_multiday_object": len(counts) > 1,
                "source_bytes_unchanged": True,
                "identity_inferred_from_object_name": False,
                "session_day_inferred_from_object_name": False,
            }
            row["candidate_fingerprint"] = _fp(row)
            candidates.append(row)
        after_size = path.stat().st_size
        after_sha = _sha256(path)
        if (before_size, before_sha) != (after_size, after_sha):
            raise TargetDaySliceError(f"source changed during slicing: {path}")
        return candidates
    except Exception:
        for handle in handles.values():
            try:
                handle.close()
            except Exception:
                pass
        for temp_path in temporary_paths.values():
            temp_path.unlink(missing_ok=True)
        for final_path in final_paths.values():
            final_path.unlink(missing_ok=True)
        raise


def _selection_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for candidate in candidates:
        key = (candidate["day"], candidate["lane"])
        by_key.setdefault(key, []).append(candidate)
    rows: list[dict[str, Any]] = []
    for day in _target_days():
        expected = _target_identity(day)
        assert expected is not None
        for lane in coverage.LANES:
            options = sorted(by_key.get((day, lane), []), key=lambda row: row["candidate_id"])
            if not options:
                status = "MISSING"
                selected = None
            elif len(options) == 1:
                status = "UNIQUE_SLICE_READY"
                selected = options[0]
            else:
                signatures = {
                    (
                        row["sha256"],
                        int(row["record_count"]),
                        float(row["event_start_s"]),
                        float(row["event_end_s"]),
                        row["definition_fingerprint"],
                    )
                    for row in options
                }
                if len(signatures) == 1:
                    status = "IDENTICAL_DUPLICATE_SLICES_READY"
                    selected = options[0]
                else:
                    status = "CONFLICTING_SLICE_CANDIDATES"
                    selected = None
            row = {
                "target": _target_label(day),
                "day": day,
                "lane": lane,
                "expected_dataset": coverage.DATASET,
                "expected_raw_symbol": expected["raw_symbol"],
                "expected_instrument_id": expected["instrument_id"],
                "status": status,
                "candidate_fingerprints": [row["candidate_fingerprint"] for row in options],
                "candidate_ids": [row["candidate_id"] for row in options],
                "selected_candidate_fingerprint": (
                    selected["candidate_fingerprint"] if selected is not None else None
                ),
                "selected_candidate_id": selected["candidate_id"] if selected is not None else None,
                "automatic_selection_basis": (
                    "ONLY_EXACT_CANDIDATE"
                    if status == "UNIQUE_SLICE_READY"
                    else "BYTE_IDENTICAL_EXACT_CANDIDATES_LEXICAL_TIE_BREAK"
                    if status == "IDENTICAL_DUPLICATE_SLICES_READY"
                    else None
                ),
            }
            row["selection_fingerprint"] = _fp(row)
            rows.append(row)
    return rows


def _pair_rows(
    selections: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    selected_by_fp = {row["candidate_fingerprint"]: row for row in candidates}
    by_key = {(row["day"], row["lane"]): row for row in selections}
    result: list[dict[str, Any]] = []
    for day in _target_days():
        l1 = by_key[(day, "l1_trades")]
        mbo = by_key[(day, "mbo")]
        blockers: list[str] = []
        overlap = None
        if l1["status"] not in READY_LANE_STATUSES:
            blockers.append(f"L1_{l1['status']}")
        if mbo["status"] not in READY_LANE_STATUSES:
            blockers.append(f"MBO_{mbo['status']}")
        if not blockers:
            l1_candidate = selected_by_fp[l1["selected_candidate_fingerprint"]]
            mbo_candidate = selected_by_fp[mbo["selected_candidate_fingerprint"]]
            if l1_candidate["definition_fingerprint"] != mbo_candidate["definition_fingerprint"]:
                blockers.append("DEFINITION_MISMATCH")
            start = max(
                float(l1_candidate["event_start_s"]), float(mbo_candidate["event_start_s"])
            )
            end = min(
                float(l1_candidate["event_end_s"]), float(mbo_candidate["event_end_s"])
            )
            if end < start:
                blockers.append("EVENT_TIME_NONOVERLAP")
            else:
                overlap = {"event_start_s": start, "event_end_s": end}
        row = {
            "target": _target_label(day),
            "day": day,
            "status": "MATCHED_L1_MBO_READY" if not blockers else "BLOCKED",
            "blockers": blockers,
            "event_time_overlap": overlap,
            "l1_selection_fingerprint": l1["selection_fingerprint"],
            "mbo_selection_fingerprint": mbo["selection_fingerprint"],
        }
        row["pair_fingerprint"] = _fp(row)
        result.append(row)
    return result


def _status(pair_rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    groups = []
    for target in ("G15_ANCHOR", "G15", "G16"):
        rows = [row for row in pair_rows if row["target"] == target]
        ready = bool(rows) and all(row["status"] == "MATCHED_L1_MBO_READY" for row in rows)
        groups.append(
            {
                "target": target,
                "status": "MATCHED_L1_MBO_READY" if ready else "BLOCKED",
                "days": [row["day"] for row in rows],
                "blocked_days": [row["day"] for row in rows if row["status"] != "MATCHED_L1_MBO_READY"],
            }
        )
    by_target = {row["target"]: row["status"] for row in groups}
    if all(value == "MATCHED_L1_MBO_READY" for value in by_target.values()):
        status = "ANCHOR_G15_G16_TARGET_SLICES_READY"
    elif by_target.get("G15_ANCHOR") == by_target.get("G15") == "MATCHED_L1_MBO_READY":
        status = "ANCHOR_G15_TARGET_SLICES_READY_G16_BLOCKED"
    else:
        status = "BLOCKED"
    return status, groups


def _build_inspection_plan(
    *,
    selections: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    output_root: Path,
    snapshot: Mapping[str, Any],
    bundle_fingerprint: str | None = None,
) -> dict[str, Any]:
    selected_by_fp = {row["candidate_fingerprint"]: row for row in candidates}
    plan = inspection.plan_template(allowed_roots=[str(output_root)])
    corpora = {row["corpus_id"]: row for row in plan["corpora"]}
    for selection in selections:
        fingerprint = selection.get("selected_candidate_fingerprint")
        if not fingerprint:
            continue
        candidate = selected_by_fp[fingerprint]
        corpus = corpora[candidate["corpus_id"]]
        corpus["sources"].append(
            {
                "source_id": candidate["normalized_source_id"],
                "location": candidate["source_location"],
                "materialized_path": candidate["materialized_path"],
                "day": candidate["day"],
                "lane": candidate["lane"],
                "definition": copy.deepcopy(candidate["definition"]),
                "inventory_observed_at": snapshot["observed_at"],
                "skip_nonmatching": False,
                "target_slice_candidate_fingerprint": candidate["candidate_fingerprint"],
                "target_slice_bundle_fingerprint": bundle_fingerprint,
                "identity_inferred_from_filename": False,
            }
        )
    for corpus in corpora.values():
        corpus["sources"].sort(key=lambda row: (row["day"], row["source_id"]))
        corpus["expected_days"] = sorted({row["day"] for row in corpus["sources"]})
        corpus["expected_object_count"] = len(corpus["sources"]) or None
        corpus["inventory_scope_verified"] = False
        corpus["inventory_complete_asserted"] = False
        corpus["inventory_observed_at"] = snapshot["observed_at"]
        publishers = {int(row["definition"]["publisher_id"]) for row in corpus["sources"]}
        corpus["publisher_id"] = next(iter(publishers)) if len(publishers) == 1 else None
    plan.pop("plan_fingerprint", None)
    plan["target_day_slices_only"] = True
    plan["broad_corpus_completeness_asserted"] = False
    plan["plan_fingerprint"] = inspection._fp(plan)
    inspection._validate_plan(plan)
    return plan


def build_target_day_slices(
    *,
    gate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
    output_root: Path,
    confirm_slice: bool,
    verify_definition_files: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create deterministic exact target-day shards and an inspection plan."""
    if confirm_slice is not True:
        raise TargetDaySliceError("target-day slicing requires explicit confirmation")
    locked, snap, quarantined, catalog, probed, bindings = _validate_chain(
        gate=gate,
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=definition_catalog,
        probe=probe,
        proposed_bindings=proposed_bindings,
        verify_definition_files=verify_definition_files,
    )
    root = output_root.expanduser().resolve()
    if root.exists():
        raise TargetDaySliceError(f"refusing to overwrite target-day slice directory {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="ng_target_slice_", dir=str(root.parent)))
    quarantine_by_id = {str(row["object_id"]): row for row in quarantined["objects"]}
    binding_by_id = {str(row["object_id"]): row for row in bindings["bindings"]}
    candidates: list[dict[str, Any]] = []
    skipped_objects: list[dict[str, Any]] = []
    try:
        for evidence in sorted(probed["objects"], key=lambda row: str(row["object_id"])):
            object_id = str(evidence["object_id"])
            if evidence.get("status") != "UNIQUE_DEFINITION_MATCH" or evidence.get(
                "proposed_lane"
            ) not in LANE_TO_KIND:
                skipped_objects.append(
                    {
                        "object_id": object_id,
                        "probe_status": evidence.get("status"),
                        "reason": "EXACT_UNIQUE_IDENTITY_AND_LANE_REQUIRED",
                        "probe_object_fingerprint": evidence["probe_object_fingerprint"],
                    }
                )
                continue
            candidates.extend(
                _slice_one_object(
                    evidence=evidence,
                    quarantine_row=quarantine_by_id[object_id],
                    proposed_binding=binding_by_id[object_id],
                    stage=stage,
                )
            )
        os.replace(stage, root)
        for candidate in candidates:
            candidate["materialized_path"] = str(root / Path(candidate["materialized_path"]).name)
            candidate.pop("candidate_fingerprint", None)
            candidate["candidate_fingerprint"] = _fp(candidate)
        selections = _selection_rows(candidates)
        pairs = _pair_rows(selections, candidates)
        status, groups = _status(pairs)
        provisional = {
            "schema": SCHEMA,
            "status": status,
            "snapshot_fingerprint": snap["snapshot_fingerprint"],
            "quarantine_fingerprint": quarantined["quarantine_fingerprint"],
            "definition_catalog_fingerprint": catalog["catalog_fingerprint"],
            "definition_probe_gate_fingerprint": locked["gate_fingerprint"],
            "probe_fingerprint": probed["probe_fingerprint"],
            "proposed_binding_manifest_fingerprint": bindings[
                "binding_manifest_fingerprint"
            ],
            "output_root": str(root),
            "target_days": list(_target_days()),
            "candidate_count": len(candidates),
            "candidates": sorted(
                candidates, key=lambda row: (row["day"], row["lane"], row["candidate_id"])
            ),
            "selections": selections,
            "pairs": pairs,
            "groups": groups,
            "skipped_objects": sorted(skipped_objects, key=lambda row: row["object_id"]),
            "selection_may_use_record_count_or_filename_alone": False,
            "conflicting_candidates_stand_down": True,
            "broad_corpus_completeness_asserted": False,
            "source_bytes_untouched": True,
            "random_shuffle_used": False,
            **_authority(),
        }
        provisional["slice_bundle_fingerprint"] = _fp(provisional)
        plan = _build_inspection_plan(
            selections=selections,
            candidates=candidates,
            output_root=root,
            snapshot=snap,
            bundle_fingerprint=provisional["slice_bundle_fingerprint"],
        )
        provisional["inspection_plan_fingerprint"] = plan["plan_fingerprint"]
        provisional["inspection_plan"] = plan
        provisional.pop("slice_bundle_fingerprint")
        provisional["slice_bundle_fingerprint"] = _fp(provisional)
        # Refresh the informational bundle link in plan after the final bundle shape.
        for corpus in plan["corpora"]:
            for source in corpus["sources"]:
                source["target_slice_bundle_fingerprint"] = provisional[
                    "slice_bundle_fingerprint"
                ]
        plan.pop("plan_fingerprint")
        plan["plan_fingerprint"] = inspection._fp(plan)
        provisional["inspection_plan_fingerprint"] = plan["plan_fingerprint"]
        provisional["inspection_plan"] = plan
        provisional.pop("slice_bundle_fingerprint")
        provisional["slice_bundle_fingerprint"] = _fp(provisional)
        # Keep the plan link informational and stable without a recursive fingerprint loop.
        for corpus in plan["corpora"]:
            for source in corpus["sources"]:
                source["target_slice_bundle_fingerprint"] = None
        plan.pop("plan_fingerprint")
        plan["plan_fingerprint"] = inspection._fp(plan)
        provisional["inspection_plan_fingerprint"] = plan["plan_fingerprint"]
        provisional["inspection_plan"] = plan
        provisional.pop("slice_bundle_fingerprint")
        provisional["slice_bundle_fingerprint"] = _fp(provisional)
        validate_slice_bundle(
            provisional,
            gate=locked,
            snapshot=snap,
            quarantine=quarantined,
            definition_catalog=catalog,
            probe=probed,
            proposed_bindings=bindings,
            verify_files=True,
            verify_definition_files=verify_definition_files,
        )
        return provisional, plan
    except Exception:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        raise


def validate_slice_bundle(
    value: Mapping[str, Any],
    *,
    gate: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    quarantine: Mapping[str, Any],
    definition_catalog: Mapping[str, Any],
    probe: Mapping[str, Any],
    proposed_bindings: Mapping[str, Any],
    verify_files: bool,
    verify_definition_files: bool = True,
) -> dict[str, Any]:
    checked = _verify(value, "slice_bundle_fingerprint", label="target-day slice bundle")
    if checked.get("schema") != SCHEMA:
        raise TargetDaySliceError("target-day slice bundle schema mismatch")
    _validate_authority(checked, label="target-day slice bundle")
    if checked.get("selection_may_use_record_count_or_filename_alone") is not False:
        raise TargetDaySliceError("target-day selection used an unsafe heuristic")
    if checked.get("conflicting_candidates_stand_down") is not True:
        raise TargetDaySliceError("conflicting target-day candidates must stand down")
    if checked.get("broad_corpus_completeness_asserted") is not False:
        raise TargetDaySliceError("target slicing may not assert broad corpus completeness")
    if checked.get("source_bytes_untouched") is not True:
        raise TargetDaySliceError("source bytes must remain untouched")
    if checked.get("random_shuffle_used") is not False:
        raise TargetDaySliceError("time-series records may not be randomly shuffled")

    locked, snap, quarantined, catalog, probed, bindings = _validate_chain(
        gate=gate,
        snapshot=snapshot,
        quarantine=quarantine,
        definition_catalog=definition_catalog,
        probe=probe,
        proposed_bindings=proposed_bindings,
        verify_definition_files=verify_definition_files,
    )
    links = {
        "snapshot_fingerprint": snap["snapshot_fingerprint"],
        "quarantine_fingerprint": quarantined["quarantine_fingerprint"],
        "definition_catalog_fingerprint": catalog["catalog_fingerprint"],
        "definition_probe_gate_fingerprint": locked["gate_fingerprint"],
        "probe_fingerprint": probed["probe_fingerprint"],
        "proposed_binding_manifest_fingerprint": bindings[
            "binding_manifest_fingerprint"
        ],
    }
    for field, expected in links.items():
        if checked.get(field) != expected:
            raise TargetDaySliceError(f"target-day slice {field} mismatch")
    if checked.get("target_days") != list(_target_days()):
        raise TargetDaySliceError("target-day list mismatch")

    candidates = list(checked.get("candidates") or [])
    if checked.get("candidate_count") != len(candidates):
        raise TargetDaySliceError("target-day candidate count mismatch")
    seen_candidates: set[str] = set()
    for raw in candidates:
        row = copy.deepcopy(dict(raw))
        observed = row.pop("candidate_fingerprint", None)
        if observed != _fp(row):
            raise TargetDaySliceError("target-day candidate fingerprint mismatch")
        candidate_id = str(raw.get("candidate_id") or "")
        if not candidate_id or candidate_id in seen_candidates:
            raise TargetDaySliceError("missing or duplicate target-day candidate_id")
        seen_candidates.add(candidate_id)
        day = str(raw.get("day") or "")
        lane = str(raw.get("lane") or "")
        expected = _target_identity(day)
        if expected is None or lane not in coverage.LANES:
            raise TargetDaySliceError("candidate is outside canonical targets")
        definition = inspection.validate_definition(raw["definition"])
        if raw.get("definition_fingerprint") != definition["definition_fingerprint"]:
            raise TargetDaySliceError("candidate definition fingerprint mismatch")
        if (
            definition["dataset"] != coverage.DATASET
            or definition["raw_symbol"] != expected["raw_symbol"]
            or int(definition["instrument_id"]) != int(expected["instrument_id"])
        ):
            raise TargetDaySliceError("candidate exact contract identity mismatch")
        if _utc_day(float(raw["event_start_s"])) != day or _utc_day(
            float(raw["event_end_s"])
        ) != day:
            raise TargetDaySliceError("candidate event range is not confined to its UTC day")
        if int(raw.get("record_count") or 0) <= 0 or int(raw.get("size_bytes") or 0) <= 0:
            raise TargetDaySliceError("candidate must contain positive records and bytes")
        if verify_files:
            path = Path(str(raw.get("materialized_path") or "")).expanduser().resolve()
            root = Path(str(checked.get("output_root") or "")).expanduser().resolve()
            if not path.is_file() or not (path == root or root in path.parents):
                raise TargetDaySliceError(f"candidate file is missing or escapes output_root: {path}")
            if path.stat().st_size != int(raw["size_bytes"]) or _sha256(path) != raw["sha256"]:
                raise TargetDaySliceError(f"candidate file verification failed: {path}")

    expected_selections = _selection_rows(candidates)
    if checked.get("selections") != expected_selections:
        raise TargetDaySliceError("target-day selections were not reproduced")
    expected_pairs = _pair_rows(expected_selections, candidates)
    if checked.get("pairs") != expected_pairs:
        raise TargetDaySliceError("target-day pair alignment was not reproduced")
    expected_status, expected_groups = _status(expected_pairs)
    if checked.get("status") != expected_status or checked.get("groups") != expected_groups:
        raise TargetDaySliceError("target-day status was not reproduced")

    plan = copy.deepcopy(dict(checked.get("inspection_plan") or {}))
    inspection._validate_plan(plan)
    if checked.get("inspection_plan_fingerprint") != plan.get("plan_fingerprint"):
        raise TargetDaySliceError("target-day inspection plan fingerprint mismatch")
    expected_plan = _build_inspection_plan(
        selections=expected_selections,
        candidates=candidates,
        output_root=Path(str(checked["output_root"])),
        snapshot=snap,
        bundle_fingerprint=None,
    )
    if plan != expected_plan:
        raise TargetDaySliceError("target-day inspection plan was not reproduced")
    return copy.deepcopy(dict(value))


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TargetDaySliceError(f"{path}: expected JSON object")
    return value


def selftest() -> int:
    # The full provenance chain is covered by unit tests. Keep this test dependency-free.
    assert ANCHOR_DAY not in coverage.G15_DATES
    assert _target_identity("20260315") == {"raw_symbol": "NGJ26", "instrument_id": 1008}
    assert _target_identity("20260410") == {"raw_symbol": "NGK26", "instrument_id": 996}
    assert len(_target_days()) == 24
    print("[ng_corpus_target_day_slicer] selftest PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Slice exact NG quarantine objects into deterministic target-day sources"
    )
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--quarantine", type=Path)
    parser.add_argument("--definition-catalog", type=Path)
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--proposed-bindings", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--bundle-out", type=Path)
    parser.add_argument("--plan-out", type=Path)
    parser.add_argument("--confirm-slice", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    required = (
        "gate",
        "snapshot",
        "quarantine",
        "definition_catalog",
        "probe",
        "proposed_bindings",
        "output_root",
        "bundle_out",
        "plan_out",
    )
    missing = [name for name in required if getattr(args, name) is None]
    if missing:
        parser.error("missing required arguments: " + ", ".join(missing))
    bundle, plan = build_target_day_slices(
        gate=_load_json(args.gate),
        snapshot=_load_json(args.snapshot),
        quarantine=_load_json(args.quarantine),
        definition_catalog=_load_json(args.definition_catalog),
        probe=_load_json(args.probe),
        proposed_bindings=_load_json(args.proposed_bindings),
        output_root=args.output_root,
        confirm_slice=args.confirm_slice,
    )
    _write_json(args.bundle_out, bundle)
    _write_json(args.plan_out, plan)
    print(
        json.dumps(
            {
                "status": bundle["status"],
                "candidate_count": bundle["candidate_count"],
                "blocked_groups": [
                    row for row in bundle["groups"] if row["status"] != "MATCHED_L1_MBO_READY"
                ],
                "bundle": str(args.bundle_out),
                "inspection_plan": str(args.plan_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
