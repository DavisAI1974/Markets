import hashlib
import json

import pytest

from research.kalshi.ng_exhaustion_step1_completion_gate import (
    CompletionGateError,
    classify_recovery_state,
    declared_final_output_hashes,
    validate_finalization_provenance,
    validate_final_receipt_heartbeat,
    validate_launch_canary,
    validate_runtime_state,
)


CANDIDATE = "0d318335825b4a0e19a5a2881522f3da0374788e"
SOURCE = "5739bce85d9bfbbe6c59d000bc411b424d7752b98a309725161d44e6d1d3dc2e"


def promoted_launch():
    return {
        "launch_method": "USER_AUTHORIZED_ONE_DAY_CANARY_PROMOTION_V1_20260823",
        "candidate_commit": CANDIDATE,
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
    }


def finalizer_lock():
    lock = {
        "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZER_LOCK_V1_20260823",
        "parent_candidate_commit": CANDIDATE,
        "recovery_scope": "FULL_65_CHILDREN_REUSED_NO_RAW_MBO_REPLAY",
        "finalizer_engine_hashes": {"research/runner.py": "2" * 64},
    }
    lock["finalizer_lock_sha256"] = hashlib.sha256(
        json.dumps(lock, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    return lock


def recovered_final_receipt(lock):
    producer = {"research/runner.py": "1" * 64}
    finalizer = {"research/runner.py": "2" * 64}
    children = {
        f"segment-{i:02d}": {
            "receipt_sha256": f"{i + 1:064x}",
            "seconds_gzip_sha256": f"{i + 101:064x}",
            "seconds_rows": i + 1,
        }
        for i in range(65)
    }
    return {
        "source_manifest_sha256": SOURCE,
        "ruleset_sha256": "6" * 64,
        "engine_hashes": finalizer,
        "child_receipt_count": 65,
        "child_receipt_hashes": [row["receipt_sha256"] for row in children.values()],
        "preflight_child_recovery": None,
        "finalization_recovery": {
            "schema": "NG_EXHAUSTION_MBO_5Y_STEP1_FINALIZATION_RECOVERY_V1_20260823",
            "contract_sha256": "7" * 64,
            "parent_candidate_commit": CANDIDATE,
            "source_manifest_sha256": SOURCE,
            "ruleset_sha256": "6" * 64,
            "recovery_scope": "FULL_65_CHILDREN_REUSED_NO_RAW_MBO_REPLAY",
            "raw_mbo_replayed": False,
            "producer_engine_hashes": producer,
            "finalizer_engine_hashes": finalizer,
            "accepted_launch_receipt_file_sha256": "3" * 64,
            "finalizer_lock_sha256": lock["finalizer_lock_sha256"],
            "children": children,
        },
        "legacy_overlap_equivalence": {
            "status": "USER_AUTHORIZED_ONE_DAY_CANARY_ACCEPTED",
            "retained_mismatch_count": 1,
            "lineage_equivalence_asserted": False,
            "multiweek_equivalence_asserted": False,
            "accepted_launch_receipt_file_sha256": "3" * 64,
            "candidate_commit": CANDIDATE,
            "canary_evidence": promoted_launch()["canary_evidence"],
        },
    }


def test_promoted_one_day_canary_is_valid_launch_evidence():
    mode = validate_launch_canary(promoted_launch(), {"source_manifest_sha256": SOURCE})
    assert mode == "USER_AUTHORIZED_ONE_DAY_CANARY"


def test_promoted_canary_identity_drift_fails_closed():
    launch = promoted_launch()
    launch["canary_evidence"]["artifact_id"] = 1
    with pytest.raises(CompletionGateError, match="canary identity"):
        validate_launch_canary(launch, {"source_manifest_sha256": SOURCE})


def test_promoted_canary_implementation_drift_fails_closed():
    launch = promoted_launch()
    launch["canary_evidence"]["implementation_commit"] = "0" * 40
    with pytest.raises(CompletionGateError, match="canary identity"):
        validate_launch_canary(launch, {"source_manifest_sha256": SOURCE})


def test_promoted_canary_is_bound_to_the_exact_launched_candidate():
    launch = promoted_launch()
    launch["candidate_commit"] = "f" * 40
    with pytest.raises(CompletionGateError, match="candidate"):
        validate_launch_canary(launch, {"source_manifest_sha256": SOURCE})


def test_original_strict_preflight_remains_supported():
    launch = {
        "preflight": {
            "status": "STEP1_DUAL_STRUCTURAL_CENSUS_COMPLETE",
            "source_manifest_sha256": SOURCE,
            "legacy_overlap_equivalence": {"status": "PASS"},
        }
    }
    assert validate_launch_canary(launch, {"source_manifest_sha256": SOURCE}) == "STRICT_PREFLIGHT"


def test_running_verification_requires_live_loaded_unit():
    mode = validate_runtime_state(
        final_available=False,
        require_complete_outputs=False,
        heartbeat_phase="SEGMENT_COMPLETE",
        active_state="active",
        load_state="loaded",
        sub_state="running",
        main_pid=123,
        pid_alive=True,
    )
    assert mode == "ACTIVE_SERVICE"


def test_completed_outputs_allow_collected_transient_unit_to_be_inactive():
    mode = validate_runtime_state(
        final_available=True,
        require_complete_outputs=True,
        heartbeat_phase="COMPLETE",
        active_state="inactive",
        load_state="not-found",
        sub_state="dead",
        main_pid=0,
        pid_alive=False,
    )
    assert mode == "COMPLETED_OUTPUTS"


def test_completed_outputs_reject_failed_or_contradictory_unit_state():
    with pytest.raises(CompletionGateError, match="failed"):
        validate_runtime_state(
            final_available=True,
            require_complete_outputs=True,
            heartbeat_phase="COMPLETE",
            active_state="failed",
            load_state="loaded",
            sub_state="failed",
            main_pid=0,
            pid_alive=False,
        )
    with pytest.raises(CompletionGateError, match="contradictory"):
        validate_runtime_state(
            final_available=True,
            require_complete_outputs=True,
            heartbeat_phase="COMPLETE",
            active_state="inactive",
            load_state="loaded",
            sub_state="dead",
            main_pid=123,
            pid_alive=False,
        )


def test_completion_mode_fails_without_final_receipt():
    with pytest.raises(CompletionGateError, match="required"):
        validate_runtime_state(
            final_available=False,
            require_complete_outputs=True,
            heartbeat_phase="SEGMENT_COMPLETE",
            active_state="active",
            load_state="loaded",
            sub_state="running",
            main_pid=123,
            pid_alive=True,
        )


def test_declared_final_output_hashes_are_exact_and_unique():
    final = {
        "event_outputs": {
            "legacy": {"path": "/tmp/LEGACY_CONTROL_EVENTS.jsonl.gz", "gzip_sha256": "1" * 64},
            "native": {"path": "/tmp/V4_NATIVE_FULL_EVENTS.jsonl.gz", "gzip_sha256": "2" * 64},
        },
        "lineage_input_outputs": {
            "legacy": {"path": "/tmp/LEGACY_CONTROL_LINEAGE_INPUTS.jsonl.gz", "gzip_sha256": "3" * 64},
            "native": {"path": "/tmp/V4_NATIVE_FULL_LINEAGE_INPUTS.jsonl.gz", "gzip_sha256": "4" * 64},
        },
        "population_outputs": {
            "legacy": {"path": "/tmp/LEGACY_CONTROL_POPULATION.jsonl.gz", "gzip_sha256": "5" * 64},
            "native": {"path": "/tmp/V4_NATIVE_FULL_POPULATION.jsonl.gz", "gzip_sha256": "6" * 64},
        },
        "crosswalk_index_outputs": {
            "legacy": {"path": "/tmp/LEGACY_CONTROL_CROSSWALK_INDEX.jsonl.gz", "gzip_sha256": "7" * 64},
            "native": {"path": "/tmp/V4_NATIVE_FULL_CROSSWALK_INDEX.jsonl.gz", "gzip_sha256": "8" * 64},
        },
        "crosswalk_output": {"path": "/tmp/DUAL_CENSUS_CROSSWALK.jsonl.gz", "gzip_sha256": "9" * 64},
        "retained_overlap_mismatches": {
            "path": "/tmp/LEGACY_CONTROL_OVERLAP_MISMATCHES.jsonl.gz",
            "gzip_sha256": "a" * 64,
        },
    }
    outputs = declared_final_output_hashes(final)
    assert len(outputs) == 10
    assert outputs["V4_NATIVE_FULL_POPULATION.jsonl.gz"] == "6" * 64
    final["retained_overlap_mismatches"]["path"] = "/tmp/DUAL_CENSUS_CROSSWALK.jsonl.gz"
    with pytest.raises(CompletionGateError, match="path drift"):
        declared_final_output_hashes(final)


def test_complete_heartbeat_must_name_the_exact_final_receipt():
    assert validate_final_receipt_heartbeat(
        {"phase": "COMPLETE", "receipt_sha256": "b" * 64}, "b" * 64
    ) is None
    with pytest.raises(CompletionGateError, match="receipt"):
        validate_final_receipt_heartbeat(
            {"phase": "COMPLETE", "receipt_sha256": "c" * 64}, "b" * 64
        )


def test_recovery_state_keeps_a_healthy_full_run_untouched():
    assert classify_recovery_state(
        final_available=False,
        active_state="active",
        load_state="loaded",
        sub_state="running",
        main_pid=123,
        pid_alive=True,
        completed_segments=7,
        expected_segments=65,
    ) == "HEALTHY_RUNNING"


def test_clean_stopped_run_resumes_or_finalizes_without_raw_replay():
    common = {
        "final_available": False,
        "active_state": "inactive",
        "load_state": "not-found",
        "sub_state": "dead",
        "main_pid": 0,
        "pid_alive": False,
        "expected_segments": 65,
    }
    assert classify_recovery_state(**common, completed_segments=64) == "RESUME_CONTROLLER"
    assert classify_recovery_state(**common, completed_segments=65) == "FINALIZE_FROM_CHILDREN"


def test_recovery_state_rejects_failed_or_impossible_state():
    with pytest.raises(CompletionGateError, match="failed"):
        classify_recovery_state(
            final_available=False,
            active_state="failed",
            load_state="loaded",
            sub_state="failed",
            main_pid=0,
            pid_alive=False,
            completed_segments=65,
            expected_segments=65,
        )
    with pytest.raises(CompletionGateError, match="cardinality"):
        classify_recovery_state(
            final_available=False,
            active_state="inactive",
            load_state="not-found",
            sub_state="dead",
            main_pid=0,
            pid_alive=False,
            completed_segments=66,
            expected_segments=65,
        )


def test_exact_one_day_recovery_provenance_is_accepted():
    launch = promoted_launch()
    launch["candidate_lock"] = {
        "engine_hashes": {"research/runner.py": "1" * 64},
        "source_manifest_sha256": SOURCE,
        "ruleset_sha256": "6" * 64,
    }
    lock = finalizer_lock()
    final = recovered_final_receipt(lock)
    mode = validate_finalization_provenance(
        final,
        launch,
        launch["candidate_lock"],
        finalizer_lock=lock,
        launch_receipt_file_sha256="3" * 64,
    )
    assert mode == "ONE_DAY_CANARY_RECOVERY_FINALIZER"


def test_recovery_provenance_rejects_unpinned_child_or_engine():
    launch = promoted_launch()
    launch["candidate_lock"] = {
        "engine_hashes": {"research/runner.py": "1" * 64},
        "source_manifest_sha256": SOURCE,
        "ruleset_sha256": "6" * 64,
    }
    lock = finalizer_lock()
    final = recovered_final_receipt(lock)
    final["child_receipt_hashes"][0] = "f" * 64
    with pytest.raises(CompletionGateError, match="child"):
        validate_finalization_provenance(
            final,
            launch,
            launch["candidate_lock"],
            finalizer_lock=lock,
            launch_receipt_file_sha256="3" * 64,
        )


def test_recovery_provenance_rejects_tampered_finalizer_lock():
    launch = promoted_launch()
    launch["candidate_lock"] = {
        "engine_hashes": {"research/runner.py": "1" * 64},
        "source_manifest_sha256": SOURCE,
        "ruleset_sha256": "6" * 64,
    }
    lock = finalizer_lock()
    final = recovered_final_receipt(lock)
    lock["recovery_scope"] = "TAMPERED"
    with pytest.raises(CompletionGateError, match="lock"):
        validate_finalization_provenance(
            final,
            launch,
            launch["candidate_lock"],
            finalizer_lock=lock,
            launch_receipt_file_sha256="3" * 64,
        )
