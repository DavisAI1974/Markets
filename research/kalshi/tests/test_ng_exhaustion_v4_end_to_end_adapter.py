import pytest

from research.kalshi.ng_exhaustion_v4_causal_clock import make_receipt
from research.kalshi.ng_exhaustion_v4_end_to_end_adapter import (
    EndToEndInput,
    EndToEndV4Error,
    EvaluationClock,
    reconcile_isolated_adapter,
    run_isolated_adapter,
)
from research.kalshi.ng_exhaustion_v4_mechanics import LifecycleState, PredecessorLifecycle
from research.kalshi.ng_exhaustion_v4_state_assembler import FieldPolicy, Observation

H = "a" * 64
H2 = "b" * 64
H3 = "c" * 64


def discovery():
    return make_receipt(
        event_id="e1",
        session_id="s1",
        detector_revision="det-r1",
        detector_source_sha256=H,
        source_manifest_sha256=H2,
        source_object_id="obj",
        source_range_id="range",
        source_ts_event=9.0,
        source_ts_recv=10.0,
        detector_marked_at=10.0,
        event_known_by=10.0,
        canonical_t0=8.0,
        mark_mode="CAUSAL_REPLAY",
    )


def base_input(**overrides):
    row = dict(
        lane_id="D1",
        instance_id="e1",
        discovery=discovery(),
        reveal_timestamp=20.0,
        field_policies=(FieldPolicy("x", H, 100.0),),
        observations=(
            Observation("x", 1.0, 10.0, 10.0, 10.0, H, "o1"),
            Observation("x", 2.0, 11.0, 11.0, 11.0, H, "o2"),
        ),
        evaluation_clocks=(
            EvaluationClock(10.0, 10.0, 10.1),
            EvaluationClock(11.0, 11.0, 11.1),
        ),
        predecessor_lifecycles=(
            PredecessorLifecycle(
                instance_id="e1",
                predecessor_id="p0",
                predecessor_known_by=9.0,
                evaluated_at=10.0,
                state=LifecycleState.UNRESOLVED,
                unresolved_age_seconds=1.0,
            ),
        ),
        source_manifest_sha256=H2,
        transform_sha256=H3,
        model_sha256=H,
        snapshot_sha256=H2,
        missingness_manifest_sha256=H3,
        lock_policy_sha256=H,
        lock_threshold=0.7,
        lock_persistence=2,
        head_id="continuation",
        eligibility_state="ELIGIBLE",
    )
    row.update(overrides)
    return EndToEndInput(**row)


def model(fields, clock):
    assert fields
    return (0.8, 0.2)


def test_end_to_end_pipeline_builds_movies_lock_handoff_and_reconciles():
    inp = base_input()
    artifact = run_isolated_adapter(inp, model)
    assert len(artifact.state_rows) == 2
    assert len(artifact.probability_entries) == 2
    assert artifact.first_lock.status == "LOCKED"
    out = reconcile_isolated_adapter(inp, artifact, model)
    assert out["status"] == "ISOLATED_V4_ADAPTER_RECOMPUTED"
    assert out["result_bearing_launch_authorized"] is False
    assert out["release_holdout_consumed"] is False


def test_event_known_by_and_reveal_wall_fail_closed():
    with pytest.raises(Exception):
        run_isolated_adapter(
            base_input(evaluation_clocks=(EvaluationClock(9.0, 9.0, 9.1),)),
            model,
        )
    with pytest.raises(EndToEndV4Error):
        run_isolated_adapter(
            base_input(evaluation_clocks=(EvaluationClock(10.0, 10.0, 20.0),)),
            model,
        )


def test_reconciler_recomputes_not_trusts_tampered_artifact():
    inp = base_input()
    artifact = run_isolated_adapter(inp, model)
    tampered = artifact.__class__(**{**artifact.__dict__, "overall_hash": H3})
    with pytest.raises(EndToEndV4Error):
        reconcile_isolated_adapter(inp, tampered, model)


def test_no_reliable_lock_uses_same_sealed_path():
    inp = base_input(lock_threshold=0.95)
    artifact = run_isolated_adapter(inp, model)
    assert artifact.first_lock.status == "NO_RELIABLE_LOCK"
    assert artifact.execution_handoff.first_lock_hash == artifact.first_lock.lock_hash
