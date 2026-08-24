#!/usr/bin/env python3
"""Fail-closed completion gate for the exact Sep-Nov 2021 bounded Step-1 run.

This gate validates only the three authorized native source segments in
[2021-09-01, 2021-12-01). It never lists S3, replays raw MBO, requests a
52-week source population, or launches downstream V4/Frankie work.

The frozen 52-week value is checked only as the unchanged sufficiency threshold
for history-dependent OOT statistics. With this three-month population those
statistics must remain unscored/insufficient while all Step-1 cases are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


RESEARCH_DIR = Path(__file__).resolve().parents[1]
if str(RESEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(RESEARCH_DIR))

import ng_exhaustion_mbo_5y_step1_census_20260822 as census
import ng_exhaustion_mbo_3mo_step1_finalize_20260823 as bounded


class CompletionGateError(ValueError):
    pass


EXPECTED_OUTPUTS = (
    ("event_outputs", "legacy", "LEGACY_CONTROL_EVENTS.jsonl.gz"),
    ("event_outputs", "native", "V4_NATIVE_FULL_EVENTS.jsonl.gz"),
    ("lineage_input_outputs", "legacy", "LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz"),
    ("lineage_input_outputs", "native", "V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz"),
    ("population_outputs", "legacy", "LEGACY_CONTROL_POPULATION.jsonl.gz"),
    ("population_outputs", "native", "V4_NATIVE_FULL_POPULATION.jsonl.gz"),
    ("crosswalk_index_outputs", "legacy", "LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz"),
    ("crosswalk_index_outputs", "native", "V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz"),
    (None, "crosswalk_output", "DUAL_CENSUS_CROSSWALK.jsonl.gz"),
    (None, "retained_overlap_mismatches", "LEGACY_CONTROL_OVERLAP_MISMATCHES.jsonl.gz"),
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CompletionGateError(f"{label} must be a mapping")
    return value


def _require_false(body: Mapping[str, Any], *fields: str) -> None:
    for field in fields:
        if body.get(field) is not False:
            raise CompletionGateError(f"{field} must be explicitly false")


def _validate_receipt_self_hash(receipt: Mapping[str, Any]) -> None:
    claimed = receipt.get("receipt_sha256")
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    if claimed != census.sha256_json(body):
        raise CompletionGateError("bounded Step-1 receipt canonical hash drift")


def validate_receipt_shape(
    receipt: Mapping[str, Any],
    *,
    bounded_manifest: Mapping[str, Any],
    parent_manifest: Mapping[str, Any],
    parent_manifest_file_sha256: str,
    expected_engine_hashes: Mapping[str, str],
) -> None:
    """Validate the bounded scientific/completion claims without reading raw MBO."""
    _validate_receipt_self_hash(receipt)

    if receipt.get("schema") != bounded.SCHEMA:
        raise CompletionGateError("bounded Step-1 receipt schema drift")
    if receipt.get("status") != bounded.STATUS:
        raise CompletionGateError("bounded Step-1 receipt is not complete")
    if receipt.get("source_window") != {
        "start": bounded.WINDOW_START,
        "end_exclusive": bounded.WINDOW_END_EXCLUSIVE,
        "interval_semantics": "HALF_OPEN_START_INCLUSIVE_END_EXCLUSIVE",
    }:
        raise CompletionGateError("bounded Step-1 source window drift")
    if receipt.get("source_change_policy") != bounded.SOURCE_CHANGE_POLICY:
        raise CompletionGateError("bounded Step-1 source-change policy drift")
    if tuple(receipt.get("exact_segments", ())) != bounded.SEGMENTS:
        raise CompletionGateError("bounded Step-1 segment set drift")
    if receipt.get("child_receipt_count") != len(bounded.SEGMENTS):
        raise CompletionGateError("bounded Step-1 child cardinality drift")

    if receipt.get("source_manifest_file") != "STEP1_3MO_BOUNDED_SOURCE_MANIFEST.json":
        raise CompletionGateError("bounded source-manifest filename drift")
    if receipt.get("source_manifest_sha256") != bounded_manifest.get("manifest_sha256"):
        raise CompletionGateError("bounded source-manifest identity drift")
    if receipt.get("parent_source_manifest_sha256") != parent_manifest.get("manifest_sha256"):
        raise CompletionGateError("parent canonical-manifest identity drift")
    if receipt.get("child_source_manifest_sha256") != parent_manifest.get("manifest_sha256"):
        raise CompletionGateError("child parent-manifest identity drift")
    if receipt.get("parent_source_manifest_file_sha256") != parent_manifest_file_sha256:
        raise CompletionGateError("parent canonical-manifest file hash drift")
    if receipt.get("source_object_count") != bounded_manifest.get("canonical_object_count"):
        raise CompletionGateError("bounded source object-count drift")
    if receipt.get("source_total_bytes") != bounded_manifest.get("canonical_total_bytes"):
        raise CompletionGateError("bounded source byte-count drift")
    if receipt.get("replayed_source_object_count") != bounded_manifest.get("canonical_object_count"):
        raise CompletionGateError("verified child object-count drift")
    if receipt.get("replayed_source_total_bytes") != bounded_manifest.get("canonical_total_bytes"):
        raise CompletionGateError("verified child byte-count drift")

    if receipt.get("engine_hashes") != expected_engine_hashes:
        raise CompletionGateError("bounded Step-1 engine hash drift")
    if receipt.get("ruleset_sha256") != census.ruleset_sha256():
        raise CompletionGateError("bounded Step-1 ruleset drift")
    if receipt.get("adapter_revision") != census.ADAPTER_REVISION:
        raise CompletionGateError("bounded Step-1 adapter revision drift")
    if receipt.get("native_taxonomy") != census.NATIVE_TAXONOMY:
        raise CompletionGateError("bounded Step-1 taxonomy drift")
    if receipt.get("retention_policy") != census.RULESET:
        raise CompletionGateError("bounded Step-1 retention policy drift")
    if receipt.get("weeks_filter") is not None:
        raise CompletionGateError("bounded Step-1 may not apply a secondary week filter")

    identity = _mapping(receipt.get("producer_science_identity"), "producer_science_identity")
    if identity.get("engine_hashes") != expected_engine_hashes:
        raise CompletionGateError("producer engine identity drift")
    if identity.get("ruleset_sha256") != census.ruleset_sha256():
        raise CompletionGateError("producer ruleset identity drift")
    if identity.get("adapter_revision") != census.ADAPTER_REVISION:
        raise CompletionGateError("producer adapter identity drift")
    if identity.get("native_taxonomy") != census.NATIVE_TAXONOMY:
        raise CompletionGateError("producer taxonomy identity drift")
    _require_false(
        identity,
        "raw_mbo_resolution_changed",
        "v4_reconstruction_changed",
        "event_detection_changed",
        "features_changed",
        "state_changed",
        "chain_case_retention_changed",
        "provenance_rules_changed",
        "integrity_rules_changed",
        "causal_rules_changed",
    )

    reuse = _mapping(receipt.get("child_output_reuse"), "child_output_reuse")
    if reuse.get("reused_existing_child_outputs") is not True:
        raise CompletionGateError("bounded finalizer did not reuse verified child outputs")
    if reuse.get("raw_mbo_replayed_by_bounded_finalizer") is not False:
        raise CompletionGateError("bounded finalizer unexpectedly replayed raw MBO")
    if reuse.get("reuse_policy") != "ONLY_HASH_VERIFIED_CHILDREN_WITH_FROZEN_ENGINE_AND_EXACT_PARENT_SOURCE_SCOPE":
        raise CompletionGateError("bounded child reuse policy drift")
    if reuse.get("source_duration_only_population_change") is not True:
        raise CompletionGateError("bounded run claims a scientific change beyond source duration")

    weeks = receipt.get("weeks")
    if not isinstance(weeks, list):
        raise CompletionGateError("bounded observed-week list is absent")
    history = _mapping(receipt.get("history_sufficiency"), "history_sufficiency")
    if census.INITIAL_TRAIN_WEEKS != 52:
        raise CompletionGateError("frozen initial-training statistic definition drift")
    if history.get("status") != "INSUFFICIENT_HISTORY_FOR_52_WEEK_OOT_FOLDS":
        raise CompletionGateError("three-month history must remain insufficient/unscored")
    if history.get("observed_week_count") != len(weeks):
        raise CompletionGateError("observed-week accounting drift")
    if not 0 < len(weeks) < census.INITIAL_TRAIN_WEEKS:
        raise CompletionGateError("bounded run does not represent sub-52-week source history")
    if history.get("minimum_initial_train_weeks") != census.INITIAL_TRAIN_WEEKS:
        raise CompletionGateError("history threshold definition was changed")
    if history.get("test_block_weeks") != census.TEST_BLOCK_WEEKS:
        raise CompletionGateError("test-block definition was changed")
    if history.get("minimum_weeks_for_first_test_observation") != census.INITIAL_TRAIN_WEEKS + 1:
        raise CompletionGateError("first-test observation threshold drift")
    if history.get("legacy_fold_count") != 0 or history.get("native_fold_count") != 0:
        raise CompletionGateError("three-month Step-1 must not manufacture OOT folds")
    if history.get("sufficient_for_any_out_of_time_fold") is not False:
        raise CompletionGateError("three-month history was incorrectly promoted to sufficient")
    if history.get("statistic_definition_changed") is not False:
        raise CompletionGateError("history-dependent statistic definition was changed")
    if history.get("training_window_shortened") is not False:
        raise CompletionGateError("frozen training threshold was shortened")
    if history.get("handling") != "RETAIN_ALL_CASES_UNSCORED_WITH_EXISTING_UNRESOLVED_REASONS":
        raise CompletionGateError("history-insufficient case-retention semantics drift")
    if history.get("affected_statistic_family") != "FROZEN_D1_D5_OUT_OF_TIME_PAIRED_DEPTH":
        raise CompletionGateError("history-dependent statistic family drift")

    overlap = _mapping(receipt.get("legacy_overlap_equivalence"), "legacy_overlap_equivalence")
    if overlap.get("status") != "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED":
        raise CompletionGateError("exact accepted one-day canary posture is required")
    if overlap.get("retained_mismatch_count") != 1:
        raise CompletionGateError("accepted canary retained mismatch was not preserved")
    if overlap.get("lineage_equivalence_asserted") is not False:
        raise CompletionGateError("bounded completion overclaims lineage equivalence")
    if overlap.get("multiweek_equivalence_asserted") is not False:
        raise CompletionGateError("bounded completion overclaims multiweek equivalence")
    if overlap.get("historical_three_week_gate_run_by_finalizer") is not False:
        raise CompletionGateError("bounded finalizer unexpectedly ran a historical multiweek gate")

    _require_false(
        receipt,
        "release_or_virgin_holdout_consumed",
        "predictive_or_trading_experiment_run",
        "result_bearing_launch_authorized",
        "permanent_frankie_mutated",
        "frankie_launched",
        "frozen_detector_mutated",
    )


def _validate_declared_outputs(receipt: Mapping[str, Any], out_dir: Path) -> dict[str, str]:
    verified: dict[str, str] = {}
    resolved_root = out_dir.resolve()
    for group, key, expected_name in EXPECTED_OUTPUTS:
        metadata = receipt.get(key) if group is None else _mapping(receipt.get(group), group).get(key)
        metadata = _mapping(metadata, expected_name)
        declared_name = Path(str(metadata.get("path") or "")).name
        if declared_name != expected_name:
            raise CompletionGateError(f"final output path drift: {expected_name}")
        actual = (out_dir / expected_name).resolve()
        if actual.parent != resolved_root:
            raise CompletionGateError(f"final output escaped bounded output directory: {expected_name}")
        if not actual.is_file():
            raise CompletionGateError(f"final output is missing: {expected_name}")
        digest = _sha256_file(actual)
        if metadata.get("gzip_sha256") != digest:
            raise CompletionGateError(f"final output hash drift: {expected_name}")
        rows = metadata.get("rows")
        if type(rows) is not int or rows < 0:
            raise CompletionGateError(f"final output row-count metadata malformed: {expected_name}")
        verified[expected_name] = digest
    return verified


def validate_completion(
    *,
    parent_manifest_path: Path,
    segment_dir: Path,
    out_dir: Path,
    accepted_one_day_launch_receipt: Path,
) -> dict[str, Any]:
    """Recertify the three-month completion from existing artifacts only."""
    receipt_path = out_dir / "STEP1_DUAL_CENSUS_RECEIPT.json"
    bounded_manifest_path = out_dir / "STEP1_3MO_BOUNDED_SOURCE_MANIFEST.json"
    if not receipt_path.is_file():
        raise CompletionGateError("bounded Step-1 receipt is missing")
    if not bounded_manifest_path.is_file():
        raise CompletionGateError("bounded source-manifest view is missing")

    parent_manifest = census.load_manifest(parent_manifest_path)
    bounded_manifest = json.loads(bounded_manifest_path.read_text(encoding="utf-8"))
    bounded.validate_bounded_manifest(bounded_manifest)
    rebuilt = bounded.build_bounded_manifest(
        parent_manifest,
        parent_manifest_path=parent_manifest_path,
    )
    if bounded_manifest != rebuilt:
        raise CompletionGateError("bounded source view is not the exact parent-manifest subset")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected_engine_hashes = census.material_hashes()
    validate_receipt_shape(
        receipt,
        bounded_manifest=bounded_manifest,
        parent_manifest=parent_manifest,
        parent_manifest_file_sha256=_sha256_file(parent_manifest_path),
        expected_engine_hashes=expected_engine_hashes,
    )

    expected_source_scopes = {
        segment: census._segment_source_scope(parent_manifest, segment, None)
        for segment in bounded.SEGMENTS
    }
    _, child_receipt_hashes = census._verified_child_outputs(
        parent_manifest,
        segment_dir,
        list(bounded.SEGMENTS),
        expected_engine_hashes=expected_engine_hashes,
        expected_source_scopes=expected_source_scopes,
    )
    if receipt.get("child_receipt_hashes") != child_receipt_hashes:
        raise CompletionGateError("bounded receipt is not bound to the verified child receipts")
    if receipt.get("replay_source_scopes") != [
        expected_source_scopes[segment] for segment in bounded.SEGMENTS
    ]:
        raise CompletionGateError("bounded receipt child source-scope accounting drift")

    expected_overlap, mismatches = census.accepted_one_day_canary_overlap(
        accepted_one_day_launch_receipt,
        source_manifest_sha256=parent_manifest["manifest_sha256"],
    )
    if receipt.get("legacy_overlap_equivalence") != expected_overlap:
        raise CompletionGateError("bounded receipt one-day canary binding drift")
    if receipt.get("accepted_launch_receipt_file_sha256") != _sha256_file(
        accepted_one_day_launch_receipt
    ):
        raise CompletionGateError("bounded receipt accepted-launch file hash drift")

    mismatch_meta = _mapping(
        receipt.get("retained_overlap_mismatches"), "retained_overlap_mismatches"
    )
    if mismatch_meta.get("rows") != len(mismatches) or len(mismatches) != 1:
        raise CompletionGateError("retained canary mismatch row was not preserved exactly")

    output_hashes = _validate_declared_outputs(receipt, out_dir)
    return {
        "status": "STEP1_3MO_COMPLETION_GATE_PASS",
        "source_window": receipt["source_window"],
        "exact_segments": list(bounded.SEGMENTS),
        "source_object_count": receipt["source_object_count"],
        "child_receipt_count": receipt["child_receipt_count"],
        "observed_week_count": receipt["history_sufficiency"]["observed_week_count"],
        "history_status": receipt["history_sufficiency"]["status"],
        "oot_fold_count": 0,
        "history_threshold_definition_weeks": census.INITIAL_TRAIN_WEEKS,
        "source_history_extended_to_threshold": False,
        "raw_mbo_replayed_by_completion_gate": False,
        "s3_relisted_by_completion_gate": False,
        "lineage_equivalence_asserted": False,
        "multiweek_equivalence_asserted": False,
        "retained_mismatch_count": 1,
        "frankie_launched": False,
        "predictive_or_trading_experiment_run": False,
        "verified_output_hashes": output_hashes,
    }


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
    result = validate_completion(
        parent_manifest_path=Path(args.parent_manifest),
        segment_dir=Path(args.segment_dir),
        out_dir=Path(args.out_dir),
        accepted_one_day_launch_receipt=Path(args.accepted_one_day_launch_receipt),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
