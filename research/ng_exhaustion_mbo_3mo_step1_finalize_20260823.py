#!/usr/bin/env python3
"""Finalize the exact Sep-Nov 2021 Step-1 population from verified full-MBO children.

This module never replays raw MBO. It reuses only the three exact monthly child
outputs produced by the frozen five-year Step-1 scientific engine, verifies their
parent-manifest, source-scope, ruleset, engine, receipt, and seconds hashes, then
runs the unchanged Step-1 event/lineage/crosswalk finalization over the bounded
source population.

The only scientific population change is the authorized source duration:
[2021-09-01, 2021-12-01). Statistics that require the frozen 52-week training
history remain definitionally unchanged and are retained as insufficient/unscored.
"""
from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

import ng_exhaustion_mbo_5y_step1_census_20260822 as base


SCHEMA = "NG_EXHAUSTION_MBO_3MO_STEP1_RECONCILIATION_V1_20260823"
MANIFEST_SCHEMA = "NG_EXHAUSTION_MBO_3MO_BOUNDED_MANIFEST_VIEW_V1_20260823"
STATUS = "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE_BOUNDED_3MO"
WINDOW_START = "2021-09-01"
WINDOW_END_EXCLUSIVE = "2021-12-01"
SEGMENTS = (
    "20210901_20211001",
    "20211001_20211101",
    "20211101_20211201",
)
SOURCE_CHANGE_POLICY = "SOURCE_DURATION_ONLY_5Y_TO_BOUNDED_3MO"
DERIVATION_POLICY = "EXACT_NATIVE_SEGMENT_SUBSET_OF_FROZEN_5Y_MANIFEST_NO_RELIST"


def _load_parent_manifest(path: str | Path) -> dict[str, Any]:
    return base.load_manifest(path)


def build_bounded_manifest(
    parent_manifest: dict[str, Any],
    *,
    parent_manifest_path: str | Path,
) -> dict[str, Any]:
    """Create an exact-object bounded view without relisting or changing objects."""
    parent_objects = parent_manifest.get("canonical_dbn_objects")
    if not isinstance(parent_objects, list) or not parent_objects:
        raise base.CensusError("parent canonical object inventory is absent")
    selected = [row for row in parent_objects if row.get("segment") in SEGMENTS]
    observed_segments = sorted({str(row.get("segment")) for row in selected})
    if observed_segments != list(SEGMENTS):
        raise base.CensusError(
            f"bounded manifest exact segment set drift: {observed_segments}"
        )
    if any(row.get("segment") not in SEGMENTS for row in selected):
        raise base.CensusError("bounded manifest contains an out-of-window segment")
    object_count = len(selected)
    total_bytes = sum(int(row["bytes"]) for row in selected)
    if object_count <= 0 or total_bytes <= 0:
        raise base.CensusError("bounded manifest selected object accounting is empty")

    segment_inventory = {}
    for segment in SEGMENTS:
        rows = [row for row in selected if row.get("segment") == segment]
        if not rows:
            raise base.CensusError(f"bounded manifest segment has no objects: {segment}")
        segment_inventory[segment] = {
            "object_count": len(rows),
            "total_bytes": sum(int(row["bytes"]) for row in rows),
            "object_keys": [str(row["key"]) for row in rows],
            "object_sha256": [str(row["sha256"]) for row in rows],
        }

    body = {
        "schema": MANIFEST_SCHEMA,
        "status": "BOUNDED_SOURCE_VIEW_FROZEN_FROM_PARENT_CANONICAL_MANIFEST",
        "approved_range": {
            "start": WINDOW_START,
            "end_exclusive": WINDOW_END_EXCLUSIVE,
        },
        "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
        "source_change_policy": SOURCE_CHANGE_POLICY,
        "derivation_policy": DERIVATION_POLICY,
        "exact_segments": list(SEGMENTS),
        "deterministic_native_segment_count": len(SEGMENTS),
        "canonical_object_count": object_count,
        "canonical_total_bytes": total_bytes,
        "canonical_dbn_objects": selected,
        "segment_inventory": segment_inventory,
        "parent_source_manifest_sha256": parent_manifest["manifest_sha256"],
        "parent_manifest_file_sha256": base.sha256_file(Path(parent_manifest_path)),
        "parent_manifest_status": parent_manifest.get("status"),
        "parent_prefix_wide_enumeration_used": parent_manifest.get(
            "prefix_wide_enumeration_used"
        ),
        "source_prefix_wide_enumeration_used": False,
        "object_selection_relisted_from_s3": False,
        "object_content_or_metadata_mutated": False,
    }
    if body["parent_prefix_wide_enumeration_used"] is not False:
        raise base.CensusError("parent manifest prefix-enumeration safety drift")
    return {**body, "manifest_sha256": base.sha256_json(body)}


def validate_bounded_manifest(manifest: dict[str, Any]) -> None:
    claimed = manifest.get("manifest_sha256")
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    if claimed != base.sha256_json(body):
        raise base.CensusError("bounded manifest hash drift")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise base.CensusError("bounded manifest schema drift")
    if manifest.get("status") != "BOUNDED_SOURCE_VIEW_FROZEN_FROM_PARENT_CANONICAL_MANIFEST":
        raise base.CensusError("bounded manifest status drift")
    if manifest.get("approved_range") != {
        "start": WINDOW_START,
        "end_exclusive": WINDOW_END_EXCLUSIVE,
    }:
        raise base.CensusError("bounded manifest source window drift")
    if tuple(manifest.get("exact_segments", ())) != SEGMENTS:
        raise base.CensusError("bounded manifest segment set drift")
    if manifest.get("deterministic_native_segment_count") != len(SEGMENTS):
        raise base.CensusError("bounded manifest segment cardinality drift")
    if manifest.get("source_change_policy") != SOURCE_CHANGE_POLICY:
        raise base.CensusError("bounded manifest source-change policy drift")
    if manifest.get("derivation_policy") != DERIVATION_POLICY:
        raise base.CensusError("bounded manifest derivation policy drift")
    if manifest.get("source_prefix_wide_enumeration_used") is not False:
        raise base.CensusError("bounded manifest prefix-enumeration safety drift")
    if manifest.get("object_selection_relisted_from_s3") is not False:
        raise base.CensusError("bounded manifest unexpectedly relisted S3")
    if manifest.get("object_content_or_metadata_mutated") is not False:
        raise base.CensusError("bounded manifest object mutation claim drift")


def _write_bounded_manifest(
    parent_manifest: dict[str, Any],
    parent_manifest_path: str | Path,
    output_path: Path,
) -> dict[str, Any]:
    bounded = build_bounded_manifest(
        parent_manifest,
        parent_manifest_path=parent_manifest_path,
    )
    validate_bounded_manifest(bounded)
    base.atomic_json(output_path, bounded)
    return bounded


def finalize_bounded_three_months(
    parent_manifest_path: str | Path,
    segment_dir: str | Path,
    out_dir: str | Path,
    accepted_one_day_launch_receipt: str | Path,
) -> dict[str, Any]:
    parent_manifest_path = Path(parent_manifest_path)
    launch_receipt_path = Path(accepted_one_day_launch_receipt)
    segment_dir = Path(segment_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    parent_manifest = _load_parent_manifest(parent_manifest_path)
    bounded_manifest = _write_bounded_manifest(
        parent_manifest,
        parent_manifest_path,
        out / "STEP1_3MO_BOUNDED_SOURCE_MANIFEST.json",
    )
    hashes = base.material_hashes()
    expected_source_scopes = {
        segment: base._segment_source_scope(parent_manifest, segment, None)
        for segment in SEGMENTS
    }
    seconds_paths, child_receipt_hashes = base._verified_child_outputs(
        parent_manifest,
        segment_dir,
        list(SEGMENTS),
        expected_engine_hashes=hashes,
        expected_source_scopes=expected_source_scopes,
    )
    child_receipts = [
        json.loads((segment_dir / f"{segment}.receipt.json").read_text())
        for segment in SEGMENTS
    ]
    child_source_scopes = [row["source_scope"] for row in child_receipts]
    replayed_object_count = sum(
        int(scope["selected_object_count"]) for scope in child_source_scopes
    )
    replayed_total_bytes = sum(
        int(scope["selected_total_bytes"]) for scope in child_source_scopes
    )
    if replayed_object_count != bounded_manifest["canonical_object_count"]:
        raise base.CensusError("bounded child object count does not match source view")
    if replayed_total_bytes != bounded_manifest["canonical_total_bytes"]:
        raise base.CensusError("bounded child byte count does not match source view")

    overlap, mismatches = base.accepted_one_day_canary_overlap(
        launch_receipt_path,
        source_manifest_sha256=parent_manifest["manifest_sha256"],
    )
    if overlap.get("lineage_equivalence_asserted") is not False:
        raise base.CensusError("bounded finalizer may not assert lineage equivalence")
    if overlap.get("multiweek_equivalence_asserted") is not False:
        raise base.CensusError("bounded finalizer may not assert multiweek equivalence")

    pre_classifier = base.frozen_detector.FrozenPreFamilyClassifier.load(
        "research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json"
    )
    a_classifier = base.frozen_detector.FrozenAClassifier.load(
        "research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json"
    )
    event_writers = {
        "legacy": base.DeterministicGzipJsonlWriter(
            out / "LEGACY_CONTROL_EVENTS.jsonl.gz"
        ),
        "native": base.DeterministicGzipJsonlWriter(
            out / "V4_NATIVE_FULL_EVENTS.jsonl.gz"
        ),
    }
    lineage_writers = {
        "legacy": base.DeterministicGzipJsonlWriter(
            out / "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz"
        ),
        "native": base.DeterministicGzipJsonlWriter(
            out / "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz"
        ),
    }
    weeks: list[str] = []
    population_seconds = 0
    boundary_audit: dict[str, Any] = {}
    try:
        for week, rows in base._iter_seconds_weeks(
            seconds_paths,
            None,
            list(SEGMENTS),
            boundary_audit,
        ):
            weeks.append(week)
            population_seconds += len(rows)
            legacy_events = base.detect_events_for_week(
                rows, "LEGACY_CONTROL", pre_classifier, a_classifier
            )
            native_events = base.detect_events_for_week(
                rows, "V4_NATIVE_FULL", pre_classifier, a_classifier
            )
            for event in legacy_events:
                event_writers["legacy"].write(event)
                lineage_writers["legacy"].write(base.compact_lineage_input(event))
            for event in native_events:
                event_writers["native"].write(event)
                lineage_writers["native"].write(base.compact_lineage_input(event))
        event_outputs = {key: writer.close() for key, writer in event_writers.items()}
        lineage_inputs = {
            key: writer.close() for key, writer in lineage_writers.items()
        }
    except Exception:
        for writer in [*event_writers.values(), *lineage_writers.values()]:
            writer.abort()
        raise

    base.atomic_json(out / "LEGACY_CONTROL_OVERLAP_EQUIVALENCE.json", overlap)
    mismatch_output = base.deterministic_gzip_jsonl(
        out / "LEGACY_CONTROL_OVERLAP_MISMATCHES.jsonl.gz",
        mismatches,
    )
    if overlap.get("status") != "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED":
        raise base.CensusError("exact accepted one-day canary is required")

    legacy_population, legacy_summary, legacy_index = base.lineage_population(
        out / "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz",
        "LEGACY_CONTROL",
        hashes,
        out / "LEGACY_CONTROL_POPULATION.jsonl.gz",
        out / "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz",
    )
    gc.collect()
    native_population, native_summary, native_index = base.lineage_population(
        out / "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz",
        "V4_NATIVE_FULL",
        hashes,
        out / "V4_NATIVE_FULL_POPULATION.jsonl.gz",
        out / "V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz",
    )
    gc.collect()
    crosswalk_output, crosswalk_summary = base.build_crosswalk(
        out / "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz",
        out / "V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz",
        out / "DUAL_CENSUS_CROSSWALK.jsonl.gz",
    )

    history_sufficiency = {
        "schema": "NG_EXHAUSTION_STEP1_HISTORY_SUFFICIENCY_V1_20260823",
        "status": "INSUFFICIENT_HISTORY_FOR_52_WEEK_OOT_FOLDS",
        "observed_week_count": len(weeks),
        "minimum_initial_train_weeks": base.INITIAL_TRAIN_WEEKS,
        "test_block_weeks": base.TEST_BLOCK_WEEKS,
        "minimum_weeks_for_first_test_observation": base.INITIAL_TRAIN_WEEKS + 1,
        "legacy_fold_count": len(legacy_summary.get("folds", [])),
        "native_fold_count": len(native_summary.get("folds", [])),
        "sufficient_for_any_out_of_time_fold": len(weeks) > base.INITIAL_TRAIN_WEEKS,
        "statistic_definition_changed": False,
        "training_window_shortened": False,
        "handling": "RETAIN_ALL_CASES_UNSCORED_WITH_EXISTING_UNRESOLVED_REASONS",
        "affected_statistic_family": "FROZEN_D1_D5_OUT_OF_TIME_PAIRED_DEPTH",
    }
    if history_sufficiency["sufficient_for_any_out_of_time_fold"]:
        raise base.CensusError(
            "three-month source unexpectedly satisfies the frozen 52-week OOT prerequisite"
        )
    if history_sufficiency["legacy_fold_count"] or history_sufficiency["native_fold_count"]:
        raise base.CensusError("bounded population unexpectedly produced an OOT fold")

    summary = {
        "schema": SCHEMA,
        "status": STATUS,
        "revision": base.REVISION,
        "source_window": {
            "start": WINDOW_START,
            "end_exclusive": WINDOW_END_EXCLUSIVE,
            "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
        },
        "source_change_policy": SOURCE_CHANGE_POLICY,
        "source_manifest_sha256": bounded_manifest["manifest_sha256"],
        "source_manifest_file": "STEP1_3MO_BOUNDED_SOURCE_MANIFEST.json",
        "parent_source_manifest_sha256": parent_manifest["manifest_sha256"],
        "parent_source_manifest_file_sha256": base.sha256_file(parent_manifest_path),
        "child_source_manifest_sha256": parent_manifest["manifest_sha256"],
        "source_object_count": bounded_manifest["canonical_object_count"],
        "source_total_bytes": bounded_manifest["canonical_total_bytes"],
        "exact_segments": list(SEGMENTS),
        "child_receipt_count": len(child_receipt_hashes),
        "child_receipt_hashes": child_receipt_hashes,
        "replay_source_scopes": child_source_scopes,
        "replayed_source_object_count": replayed_object_count,
        "replayed_source_total_bytes": replayed_total_bytes,
        "segment_boundary_reconciliation": boundary_audit,
        "population_seconds": population_seconds,
        "weeks": weeks,
        "weeks_filter": None,
        "history_sufficiency": history_sufficiency,
        "legacy_overlap_equivalence": overlap,
        "retained_overlap_mismatches": mismatch_output,
        "event_outputs": event_outputs,
        "lineage_input_outputs": lineage_inputs,
        "population_outputs": {
            "legacy": legacy_population,
            "native": native_population,
        },
        "crosswalk_index_outputs": {
            "legacy": legacy_index,
            "native": native_index,
        },
        "legacy_population_summary": legacy_summary,
        "native_population_summary": native_summary,
        "crosswalk_output": crosswalk_output,
        "crosswalk_summary": crosswalk_summary,
        "engine_hashes": hashes,
        "ruleset_sha256": base.ruleset_sha256(),
        "adapter_revision": base.ADAPTER_REVISION,
        "native_taxonomy": base.NATIVE_TAXONOMY,
        "retention_policy": base.RULESET,
        "producer_science_identity": {
            "engine_hashes": hashes,
            "ruleset_sha256": base.ruleset_sha256(),
            "adapter_revision": base.ADAPTER_REVISION,
            "native_taxonomy": base.NATIVE_TAXONOMY,
            "raw_mbo_resolution_changed": False,
            "v4_reconstruction_changed": False,
            "event_detection_changed": False,
            "features_changed": False,
            "state_changed": False,
            "chain_case_retention_changed": False,
            "provenance_rules_changed": False,
            "integrity_rules_changed": False,
            "causal_rules_changed": False,
        },
        "child_output_reuse": {
            "reused_existing_child_outputs": True,
            "raw_mbo_replayed_by_bounded_finalizer": False,
            "reuse_policy": "ONLY_HASH_VERIFIED_CHILDREN_WITH_FROZEN_ENGINE_AND_EXACT_PARENT_SOURCE_SCOPE",
            "source_duration_only_population_change": True,
        },
        "accepted_launch_receipt_file_sha256": base.sha256_file(launch_receipt_path),
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "result_bearing_launch_authorized": False,
        "permanent_frankie_mutated": False,
        "frankie_launched": False,
        "frozen_detector_mutated": False,
    }
    summary["receipt_sha256"] = base.sha256_json(summary)
    base.atomic_json(out / "STEP1_DUAL_CENSUS_RECEIPT.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--parent-manifest",
        default="research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json",
    )
    parser.add_argument("--segment-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--accepted-one-day-launch-receipt",
        default="research/kalshi/NG_EXHAUSTION_MBO_5Y_STEP1_LAUNCH_20260822.json",
    )
    args = parser.parse_args()
    receipt = finalize_bounded_three_months(
        args.parent_manifest,
        args.segment_dir,
        args.out_dir,
        args.accepted_one_day_launch_receipt,
    )
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "source_window": receipt["source_window"],
                "exact_segments": receipt["exact_segments"],
                "child_receipt_count": receipt["child_receipt_count"],
                "observed_week_count": receipt["history_sufficiency"][
                    "observed_week_count"
                ],
                "history_status": receipt["history_sufficiency"]["status"],
                "raw_mbo_replayed_by_bounded_finalizer": False,
                "frankie_launched": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
