from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / ".github/workflows/ng_exhaustion_step1_to_v4_prepare_20260823.yml"
VERIFY = ROOT / ".github/workflows/ng_exhaustion_mbo_5y_step1_verify_launch_20260823.yml"


def test_prepare_workflow_is_exact_key_and_non_dispatching():
    source = PREPARE.read_text(encoding="utf-8")
    for name in (
        "STEP1_DUAL_CENSUS_RECEIPT.json",
        "LEGACY_CONTROL_POPULATION.jsonl.gz",
        "V4_NATIVE_FULL_POPULATION.jsonl.gz",
        "DUAL_CENSUS_CROSSWALK.jsonl.gz",
    ):
        assert name in source
    for forbidden in (
        "list_objects_v2(",
        "aws s3 ls",
        "list-objects",
        "authorize_dispatch",
        "result_bearing=True",
        "systemd-run",
        "send-command",
    ):
        assert forbidden not in source
    assert "ng_exhaustion_step1_to_v4_registry.py" in source
    assert "validate_launch_canary" in source
    assert "--launch-receipt" in source
    assert "--finalizer-lock" in source
    assert "result_bearing_launch_authorized" in source


def test_completion_verifier_uses_shared_promotion_and_runtime_gates():
    source = VERIFY.read_text(encoding="utf-8")
    assert "validate_launch_canary" in source
    assert source.count("validate_runtime_state") >= 2
    assert "declared_final_output_hashes" in source
    assert "validate_final_receipt_heartbeat" in source
    assert "validate_finalization_provenance" in source
    assert "s3.get_object" in source
    assert "test \"$active\" = active" not in source
