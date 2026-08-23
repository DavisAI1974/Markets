import gzip
import hashlib
import json
from pathlib import Path

import pytest

from research.kalshi.ng_exhaustion_step1_to_v4_registry import RegistryError, build_registry


H = "a" * 64
CANDIDATE = "0d318335825b4a0e19a5a2881522f3da0374788e"
ADAPTER = "NG_EXHAUSTION_MBO_V4_STATE_ADAPTER_V2_20260823"
RETENTION = "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL"
ENGINE = {"engine.py": H}


def canonical_hash(body):
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def population_row(view, event_id, chain_id):
    return {
        "schema": "NG_EXHAUSTION_STEP1_POPULATION_CASE_V1_20260822",
        "census_view": view,
        "chain_id": chain_id,
        "chain_origin_event_id": event_id,
        "week_sunday": "20220102",
        "realized_structural_depth": 0,
        "legacy_d_label": "D0" if view == "LEGACY_CONTROL" else None,
        "unresolved": False,
        "short_long_state": "UNDECLARED_STRUCTURAL_CENSUS_ONLY",
        "source_provenance": {"source_dbn_key": "exact.dbn.zst", "source_dbn_sha256": H},
        "adapter_revision": ADAPTER,
        "engine_hashes": ENGINE,
        "ruleset_sha256": H,
        "retention_policy": RETENTION,
    }


def promoted_launch(result_prefix="s3://bucket/exact/full/"):
    return {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_LAUNCH_RECEIPT_V1_20260822",
        "candidate_commit": CANDIDATE,
        "full_census_launched": True,
        "result_prefix": result_prefix,
        "candidate_lock": {
            "source_manifest_sha256": H,
            "ruleset_sha256": H,
            "engine_hashes": ENGINE,
        },
        "launch_method": "USER_AUTHORIZED_ONE_DAY_CANARY_PROMOTION_V1_20260823",
        "canary_evidence": {
            "schema": "NG_EXHAUSTION_MBO_LEGACY_GROUP_AUDIT_V2_20260823",
            "artifact_id": 9490488236,
            "artifact_json_sha256": "a71b3ead28088eb1f19e919f978fca07b0e44ec6e8b91879bacb6e84e11148f0",
            "github_run_id": 32628933260,
            "date": "20250713",
            "implementation_commit": "6904bdda457f108e98508d43c9f6f53a5aaee1b8",
            "mbo_dbn_sha256": "8eb969be27fe31f2a13d3fe2b2231fee8d74f3e3c7f69a0facb9ea5a8b4eb542",
            "mbp10_gzip_sha256": "0ab2668241466143e2a05a52003d85f71ac813df8670b5de9ff4faaf93108317",
            "mbp10_row_count": 20361,
            "projected_legacy_row_count": 20360,
            "mbp10_only_detector_input_row_count": 1,
            "projection_only_detector_input_row_count": 0,
            "retained_interpretation": "ONE_MBP10_ONLY_DUPLICATE_AND_ZERO_PROJECTION_ONLY_DETECTOR_INPUT_ROWS",
            "lineage_equivalence_asserted": False,
            "multiweek_equivalence_asserted": False,
            "user_authorized_as_launch_canary": True,
            "source_prefix_wide_enumeration_used": False,
            "release_or_virgin_holdout_consumed": False,
            "predictive_or_trading_experiment_run": False,
        },
        "legacy_overlap_equivalence": {
            "status": "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED",
            "retained_mismatch_count": 1,
            "lineage_equivalence_asserted": False,
            "multiweek_equivalence_asserted": False,
        },
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "permanent_frankie_mutated": False,
    }


def fixture(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    launch_path = tmp_path / "LAUNCH_RECEIPT.json"
    launch_path.write_text(json.dumps(promoted_launch()), encoding="utf-8")
    legacy = tmp_path / "LEGACY_CONTROL_POPULATION.jsonl.gz"
    native = tmp_path / "V4_NATIVE_FULL_POPULATION.jsonl.gz"
    crosswalk = tmp_path / "DUAL_CENSUS_CROSSWALK.jsonl.gz"
    legacy_hash = write_jsonl(legacy, [population_row("LEGACY_CONTROL", "L1", "legacy-chain")])
    native_hash = write_jsonl(native, [population_row("V4_NATIVE_FULL", "N1", "native-chain")])
    crosswalk_hash = write_jsonl(crosswalk, [{
        "status": "MATCH", "legacy_event_id": "L1", "native_event_id": "N1",
        "legacy_depth": 0, "native_depth": 0, "depth_agreement": True,
        "primary_one_to_one_match": True, "reset_agreement": True,
    }])
    receipt = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_RECONCILIATION_V1_20260822",
        "status": "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE",
        "revision": "NG_EXHAUSTION_MBO_5Y_STEP1_DUAL_CENSUS_V1_20260822",
        "source_manifest_sha256": H,
        "ruleset_sha256": H,
        "engine_hashes": ENGINE,
        "adapter_revision": ADAPTER,
        "native_taxonomy": "NG_EXHAUSTION_V4_NATIVE_STRUCTURE_TAXONOMY_V1_20260822",
        "retention_policy": RETENTION,
        "weeks_filter": None,
        "preflight_child_recovery": None,
        "population_outputs": {
            "legacy": {"path": str(legacy), "rows": 1, "gzip_sha256": legacy_hash},
            "native": {"path": str(native), "rows": 1, "gzip_sha256": native_hash},
        },
        "legacy_population_summary": {
            "view": "LEGACY_CONTROL", "event_count": 1,
            "population_count": 1, "case_retention_exact": True,
        },
        "native_population_summary": {
            "view": "V4_NATIVE_FULL", "event_count": 1,
            "population_count": 1, "case_retention_exact": True,
        },
        "crosswalk_output": {"path": str(crosswalk), "rows": 1, "gzip_sha256": crosswalk_hash},
        "crosswalk_summary": {
            "schema": "NG_EXHAUSTION_STEP1_DUAL_CENSUS_CROSSWALK_V1_20260822",
            "match_edges": 1, "split_edges": 0, "merge_edges": 0,
            "complex_split_merge_edges": 0, "legacy_control_only": 0,
            "v4_native_full_only": 0,
            "primary_matches": 1,
            "depth_agreements": 1, "depth_disagreements": 0,
            "reset_agreements": 1, "reset_disagreements": 0,
            "splits_merges_policy": "NO_CASE_DROPPED_OR_FORCED_INTO_LEGACY_LABEL",
            "retention_policy": RETENTION,
        },
        "release_or_virgin_holdout_consumed": False,
        "predictive_or_trading_experiment_run": False,
        "permanent_frankie_mutated": False,
        "frozen_detector_mutated": False,
    }
    receipt["receipt_sha256"] = canonical_hash(receipt)
    receipt_path = tmp_path / "STEP1_DUAL_CENSUS_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return launch_path, receipt_path, legacy, native, crosswalk


def rebuild_receipt(receipt_path, receipt):
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = canonical_hash(receipt)
    receipt_path.write_text(json.dumps(receipt))


def build(paths, candidate=CANDIDATE):
    launch, receipt, legacy, native, crosswalk = paths
    return build_registry(
        launch, receipt, legacy, native, crosswalk,
        candidate_commit=candidate,
        result_prefix="s3://bucket/exact/full/results/",
    )


def test_builds_frozen_non_result_bearing_registry(tmp_path):
    registry = build(fixture(tmp_path))
    assert registry["status"] == "STEP1_TO_V4_FROZEN_REGISTRY_READY"
    assert registry["eligible_crosswalk_edge_count"] == 1
    assert registry["inventory_by_d_year"] == {"D0": {"2022": 1}}
    assert registry["launch_canary_mode"] == "USER_AUTHORIZED_ONE_DAY_CANARY"
    assert registry["result_bearing_launch_authorized"] is False
    assert len(registry["registry_sha256"]) == 64


def test_population_hash_drift_fails_closed(tmp_path):
    paths = fixture(tmp_path)
    with gzip.open(paths[3], "at", encoding="utf-8") as handle:
        handle.write("{}\n")
    with pytest.raises(RegistryError, match="hash"):
        build(paths)


def test_unsafe_step1_receipt_fails_closed(tmp_path):
    paths = fixture(tmp_path)
    receipt = json.loads(paths[1].read_text())
    receipt["release_or_virgin_holdout_consumed"] = True
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="holdout"):
        build(paths)


def test_unknown_crosswalk_status_fails_closed(tmp_path):
    paths = fixture(tmp_path)
    crosswalk_hash = write_jsonl(paths[4], [{
        "status": "UNKNOWN", "legacy_event_id": "L1", "native_event_id": "N1",
    }])
    receipt = json.loads(paths[1].read_text())
    receipt["crosswalk_output"]["gzip_sha256"] = crosswalk_hash
    receipt["crosswalk_summary"]["match_edges"] = 0
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="status"):
        build(paths)


def test_every_population_case_must_be_covered_by_crosswalk(tmp_path):
    paths = fixture(tmp_path)
    legacy_hash = write_jsonl(paths[2], [
        population_row("LEGACY_CONTROL", "L1", "legacy-chain"),
        population_row("LEGACY_CONTROL", "L2", "legacy-chain-2"),
    ])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["legacy"].update(rows=2, gzip_sha256=legacy_hash)
    receipt["legacy_population_summary"]["event_count"] = 2
    receipt["legacy_population_summary"]["population_count"] = 2
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="coverage"):
        build(paths)


def test_builder_binds_candidate_to_authoritative_launch_receipt(tmp_path):
    paths = fixture(tmp_path)
    launch = json.loads(paths[0].read_text())
    launch["candidate_commit"] = "f" * 40
    paths[0].write_text(json.dumps(launch))
    with pytest.raises(RegistryError, match="candidate"):
        build(paths, candidate="f" * 40)


def test_builder_requires_the_exact_promoted_canary_not_strict_preflight(tmp_path):
    paths = fixture(tmp_path)
    launch = json.loads(paths[0].read_text())
    launch.pop("launch_method")
    launch.pop("canary_evidence")
    launch.pop("legacy_overlap_equivalence")
    launch["preflight"] = {
        "status": "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE",
        "source_manifest_sha256": H,
        "legacy_overlap_equivalence": {"status": "PASS"},
    }
    paths[0].write_text(json.dumps(launch))
    with pytest.raises(RegistryError, match="promoted"):
        build(paths)


def test_nested_schema_and_row_provenance_drift_fail_closed(tmp_path):
    paths = fixture(tmp_path)
    receipt = json.loads(paths[1].read_text())
    receipt["crosswalk_summary"].pop("schema")
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="crosswalk schema"):
        build(paths)

    paths = fixture(tmp_path / "row-drift")
    native = population_row("V4_NATIVE_FULL", "N1", "native-chain")
    native["engine_hashes"] = {"engine.py": "b" * 64}
    native_hash = write_jsonl(paths[3], [native])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["native"]["gzip_sha256"] = native_hash
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="engine"):
        build(paths)


def test_unresolved_flag_and_crosswalk_semantics_are_explicit(tmp_path):
    paths = fixture(tmp_path)
    native = population_row("V4_NATIVE_FULL", "N1", "native-chain")
    native.pop("unresolved")
    native["source_provenance"] = {}
    native_hash = write_jsonl(paths[3], [native])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["native"]["gzip_sha256"] = native_hash
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="unresolved"):
        build(paths)

    paths = fixture(tmp_path / "week-drift")
    native = population_row("V4_NATIVE_FULL", "N1", "native-chain")
    native["week_sunday"] = "20230101"
    native_hash = write_jsonl(paths[3], [native])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["native"]["gzip_sha256"] = native_hash
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="week"):
        build(paths)

    paths = fixture(tmp_path / "depth-agreement-drift")
    crosswalk_hash = write_jsonl(paths[4], [{
        "status": "MATCH", "legacy_event_id": "L1", "native_event_id": "N1",
        "legacy_depth": 0, "native_depth": 0, "depth_agreement": False,
        "primary_one_to_one_match": True, "reset_agreement": True,
    }])
    receipt = json.loads(paths[1].read_text())
    receipt["crosswalk_output"]["gzip_sha256"] = crosswalk_hash
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="depth_agreement"):
        build(paths)


def test_population_event_and_case_counts_must_match(tmp_path):
    paths = fixture(tmp_path)
    receipt = json.loads(paths[1].read_text())
    receipt["native_population_summary"]["event_count"] = 2
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="event/case"):
        build(paths)


def test_crosswalk_relationships_are_recomputed_from_graph_degrees(tmp_path):
    paths = fixture(tmp_path)
    native_hash = write_jsonl(paths[3], [
        population_row("V4_NATIVE_FULL", "N1", "native-chain"),
        population_row("V4_NATIVE_FULL", "N2", "native-chain-2"),
    ])
    crosswalk_hash = write_jsonl(paths[4], [
        {
            "status": "MATCH", "legacy_event_id": "L1", "native_event_id": "N1",
            "legacy_depth": 0, "native_depth": 0, "depth_agreement": True,
            "primary_one_to_one_match": True, "reset_agreement": True,
        },
        {
            "status": "MATCH", "legacy_event_id": "L1", "native_event_id": "N2",
            "legacy_depth": 0, "native_depth": 0, "depth_agreement": True,
            "primary_one_to_one_match": False, "reset_agreement": True,
        },
    ])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["native"].update(rows=2, gzip_sha256=native_hash)
    receipt["native_population_summary"].update(event_count=2, population_count=2)
    receipt["crosswalk_output"].update(rows=2, gzip_sha256=crosswalk_hash)
    receipt["crosswalk_summary"].update(
        match_edges=2,
        primary_matches=1,
        depth_agreements=2,
        reset_agreements=2,
    )
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="relationship"):
        build(paths)


def test_boolean_depth_and_non_sunday_week_are_rejected(tmp_path):
    paths = fixture(tmp_path)
    legacy = population_row("LEGACY_CONTROL", "L1", "legacy-chain")
    native = population_row("V4_NATIVE_FULL", "N1", "native-chain")
    legacy.update(realized_structural_depth=True, legacy_d_label="DTrue")
    native["realized_structural_depth"] = True
    legacy_hash = write_jsonl(paths[2], [legacy])
    native_hash = write_jsonl(paths[3], [native])
    crosswalk_hash = write_jsonl(paths[4], [{
        "status": "MATCH", "legacy_event_id": "L1", "native_event_id": "N1",
        "legacy_depth": True, "native_depth": True, "depth_agreement": True,
        "primary_one_to_one_match": True, "reset_agreement": True,
    }])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["legacy"]["gzip_sha256"] = legacy_hash
    receipt["population_outputs"]["native"]["gzip_sha256"] = native_hash
    receipt["crosswalk_output"]["gzip_sha256"] = crosswalk_hash
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="depth"):
        build(paths)

    paths = fixture(tmp_path / "monday")
    legacy = population_row("LEGACY_CONTROL", "L1", "legacy-chain")
    native = population_row("V4_NATIVE_FULL", "N1", "native-chain")
    legacy["week_sunday"] = native["week_sunday"] = "20220103"
    legacy_hash = write_jsonl(paths[2], [legacy])
    native_hash = write_jsonl(paths[3], [native])
    receipt = json.loads(paths[1].read_text())
    receipt["population_outputs"]["legacy"]["gzip_sha256"] = legacy_hash
    receipt["population_outputs"]["native"]["gzip_sha256"] = native_hash
    rebuild_receipt(paths[1], receipt)
    with pytest.raises(RegistryError, match="Sunday"):
        build(paths)
