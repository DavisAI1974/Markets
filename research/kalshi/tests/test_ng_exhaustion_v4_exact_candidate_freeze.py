import pytest

from research.kalshi.ng_exhaustion_v4_exact_candidate_freeze import (
    CandidateFreezeError,
    EngineeringCheck,
    ExactFreezeIdentity,
    REQUIRED_CHECKS,
    freeze_exact_candidate,
)

H = "a" * 64
COMMIT = "b" * 40


def identity():
    return ExactFreezeIdentity(
        candidate_commit_sha=COMMIT,
        workflow_sha256=H,
        ruleset_sha256=H,
        engine_sha256=H,
        adapter_sha256=H,
        reconciler_sha256=H,
        model_sha256=H,
        source_manifest_sha256=H,
    )


def checks():
    return tuple(EngineeringCheck(name, True, H, "passed") for name in sorted(REQUIRED_CHECKS))


def test_exact_freeze_requires_all_checks_and_grants_no_empirical_authority():
    out = freeze_exact_candidate(
        identity=identity(),
        checks=checks(),
        protected_artifact_hashes={"research/kalshi/spawn.py": H},
        release_holdout_consumed=False,
        v4_empirical_launch_performed=False,
        p0_real_evidence_executed=False,
    )
    assert out["status"] == "EXACT_CANDIDATE_ENGINEERING_FROZEN_NOT_EMPIRICALLY_AUTHORIZED"
    assert out["result_bearing_pilot_authorized"] is False
    assert out["claims_established"] == []


def test_missing_check_fails_closed():
    with pytest.raises(CandidateFreezeError):
        freeze_exact_candidate(
            identity=identity(),
            checks=checks()[:-1],
            protected_artifact_hashes={"spawn.py": H},
            release_holdout_consumed=False,
            v4_empirical_launch_performed=False,
            p0_real_evidence_executed=False,
        )


def test_empirical_activity_cannot_be_hidden_inside_engineering_freeze():
    with pytest.raises(CandidateFreezeError):
        freeze_exact_candidate(
            identity=identity(),
            checks=checks(),
            protected_artifact_hashes={"spawn.py": H},
            release_holdout_consumed=True,
            v4_empirical_launch_performed=False,
            p0_real_evidence_executed=False,
        )
