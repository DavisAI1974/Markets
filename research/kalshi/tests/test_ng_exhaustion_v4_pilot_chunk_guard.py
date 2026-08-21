import pytest

from research.kalshi.ng_exhaustion_v4_pilot_chunk_guard import (
    ChildResult,
    ExactCandidateIdentity,
    PilotChunkManifest,
    PilotGuardError,
    ResultBearingLaunchAuthorization,
    authorize_dispatch,
    emit_downstream_handoff,
    reconcile_chunk,
)

H = "a" * 64
H2 = "b" * 64


def identity(**overrides):
    base = dict(
        candidate_sha256=H,
        workflow_sha256=H,
        ruleset_sha256=H,
        engine_sha256=H,
        adapter_sha256=H,
        reconciler_sha256=H,
        model_sha256=H,
        source_sha256=H,
    )
    base.update(overrides)
    return ExactCandidateIdentity(**base)


def manifest(**overrides):
    base = dict(
        pilot_id="pilot-d2-2024",
        d_lane="D2",
        year=2024,
        start_date="2024-01-01",
        end_date_exclusive="2025-01-01",
        identity=identity(),
        selection_manifest_sha256=H,
        membership_manifest_sha256=H2,
        child_ids=("s1", "s2"),
    )
    base.update(overrides)
    return PilotChunkManifest(**base)


def test_synthetic_guardrail_dispatch_does_not_authorize_result_bearing():
    out = authorize_dispatch(manifest(), result_bearing=False)
    assert out["result_bearing"] is False
    assert out["release_holdout_consumed"] is False


def test_generic_proceed_cannot_authorize_result_bearing():
    m = manifest()
    auth = ResultBearingLaunchAuthorization(
        authorization_id="generic-proceed",
        manifest_hash=m.manifest_hash,
        identity_hash=m.identity.identity_hash,
        candidate_sha256=H,
        workflow_sha256=H,
        ruleset_sha256=H,
        explicitly_result_bearing=False,
    )
    with pytest.raises(PilotGuardError):
        authorize_dispatch(m, result_bearing=True, authorization=auth)


def test_exact_authorization_must_match_exact_candidate_workflow_ruleset():
    m = manifest()
    auth = ResultBearingLaunchAuthorization(
        authorization_id="explicit-v4-pilot",
        manifest_hash=m.manifest_hash,
        identity_hash=m.identity.identity_hash,
        candidate_sha256=H2,
        workflow_sha256=H,
        ruleset_sha256=H,
        explicitly_result_bearing=True,
    )
    with pytest.raises(PilotGuardError):
        authorize_dispatch(m, result_bearing=True, authorization=auth)


def test_release_holdout_is_forbidden():
    with pytest.raises(PilotGuardError):
        manifest(release_holdout_included=True).validate()


def test_one_d_one_year_is_enforced():
    with pytest.raises(PilotGuardError):
        manifest(d_lane="D6").validate()
    with pytest.raises(PilotGuardError):
        manifest(start_date="2023-12-31").validate()


def test_child_parent_reconciliation_is_exact_and_streams_without_sibling_barrier():
    m = manifest()
    rows = [
        ChildResult("s1", m.manifest_hash, H),
        ChildResult("s2", m.manifest_hash, H2),
    ]
    rec = reconcile_chunk(m, rows)
    assert rec["sibling_barrier_required"] is False
    handoff = emit_downstream_handoff(m, rec)
    assert handoff["status"] == "D_YEAR_CHUNK_DOWNSTREAM_READY"
    assert handoff["sibling_barrier_required"] is False
    assert handoff["result_bearing_launch_authorized"] is False


def test_wrong_parent_or_missing_child_fails_closed():
    m = manifest()
    with pytest.raises(PilotGuardError):
        reconcile_chunk(m, [ChildResult("s1", H2, H), ChildResult("s2", m.manifest_hash, H2)])
    with pytest.raises(PilotGuardError):
        reconcile_chunk(m, [ChildResult("s1", m.manifest_hash, H)])


# 2026-08-21 readiness rerun after verified Frankie registry runtime-hash rebind.
