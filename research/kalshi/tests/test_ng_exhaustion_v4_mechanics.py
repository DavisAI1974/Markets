from __future__ import annotations

import dataclasses
import pytest

from research.kalshi.ng_exhaustion_v4_mechanics import (
    GENESIS,
    CausalField,
    ExecutionHandoff,
    LifecycleState,
    Missingness,
    PredecessorLifecycle,
    V4ContractError,
    V4LaneSpec,
    make_probability_entry,
    make_state_row,
    recompute_first_lock,
    registry_hash,
    seal_execution_handoff,
    validate_execution_binding,
    validate_probability_movie,
    validate_state_movie,
)

A="a"*64; B="b"*64; C="c"*64; D="d"*64; E="e"*64; F="f"*64


def field(name="x", *, value=0.0, status=Missingness.OBSERVED, avail=10.0, recv=9.0, age=None):
    return CausalField(name,status,value,8.0 if recv is not None else None,recv,avail,A,age)


def state_row(second=10.0, prior=GENESIS, fields=None):
    return make_state_row(
        instance_id="i1", causal_second=second, event_known_by=5.0,
        fields=tuple(fields or [field()]), source_manifest_sha256=B,
        transform_sha256=C, prior_row_hash=prior,
    )


def prob(t, prior=GENESIS, probs=(0.7,0.3), state_hash=D):
    return make_probability_entry(
        signal_lane_id="lane", instance_id="i1", head_id="h1",
        causal_evaluation_at=t, decision_available_at=t+0.25,
        probabilities=tuple(probs), state_movie_hash=state_hash,
        model_sha256=A, snapshot_sha256=B, source_manifest_sha256=C,
        missingness_manifest_sha256=E, prior_entry_hash=prior,
    )


def test_missing_is_not_true_zero_and_future_availability_fails_closed():
    with pytest.raises(V4ContractError):
        field(status=Missingness.MISSING, value=0.0, recv=None).validate(cutoff=10.0)
    field(status=Missingness.MISSING, value=None, recv=None).validate(cutoff=10.0)
    with pytest.raises(V4ContractError):
        field(avail=11.0).validate(cutoff=10.0)


def test_state_movie_is_immutable_hash_chain():
    r1=state_row(10.0)
    r2=state_row(11.0, r1.row_hash, [field(value=1.0,avail=11.0,recv=10.0)])
    assert validate_state_movie([r1,r2]) == r2.row_hash
    bad=dataclasses.replace(r2, prior_row_hash=A)
    with pytest.raises(V4ContractError): validate_state_movie([r1,bad])


def test_past_carry_and_stale_require_age_and_source_time():
    with pytest.raises(V4ContractError):
        field(status=Missingness.PAST_CARRY,recv=8.0,age=None).validate(cutoff=10.0)
    field(status=Missingness.STALE,recv=8.0,age=2.0).validate(cutoff=10.0)


def test_unresolved_lifecycle_is_prospective_and_censored_explicitly():
    PredecessorLifecycle("i","p",10.0,15.0,LifecycleState.UNRESOLVED,5.0).validate()
    PredecessorLifecycle("i","p",10.0,15.0,LifecycleState.CENSORED,5.0,censor_reason="session_end").validate()
    with pytest.raises(V4ContractError):
        PredecessorLifecycle("i","p",10.0,15.0,LifecycleState.RESOLVED,5.0,resolved_at=16.0).validate()


def test_lane_registry_is_identity_bound_and_duplicate_rejected():
    spec=V4LaneSpec("D0","WALK_FORWARD",A,B,C,D,E)
    h=registry_hash([spec]); assert len(h)==64
    with pytest.raises(V4ContractError): registry_hash([spec,spec])


def test_probability_movie_and_first_lock_are_recomputed_not_asserted():
    # This test preserves the original provisional helper's semantic LOCKED behavior.
    # The authoritative V4 path uses ng_exhaustion_v4_lock_outcome.recompute_lock_outcome,
    # which additionally seals NO_RELIABLE_LOCK to an exact probability/decision identity.
    e1=prob(10.0,probs=(0.79,0.21))
    e2=prob(11.0,e1.entry_hash,(0.81,0.19))
    e3=prob(12.0,e2.entry_hash,(0.82,0.18))
    assert validate_probability_movie([e1,e2,e3]) == e3.entry_hash
    lock=recompute_first_lock([e1,e2,e3],threshold=.80,persistence=2,lock_policy_sha256=F)
    assert lock.status=="LOCKED" and lock.entry_hash==e3.entry_hash
    assert tuple(lock.evidence_entry_hashes)==(e2.entry_hash,e3.entry_hash)


def test_probability_hash_chain_rejects_reveal_mutation():
    e1=prob(10.0); e2=prob(11.0,e1.entry_hash)
    mutated=dataclasses.replace(e1, probabilities=(0.1,0.9))
    with pytest.raises(V4ContractError): validate_probability_movie([mutated,e2])


def test_no_reliable_lock_is_explicit():
    # Legacy/provisional helper behavior is preserved for compatibility only.
    # The authoritative sealed no-lock behavior is separately tested in
    # test_ng_exhaustion_v4_lock_outcome.py.
    e1=prob(10.0,probs=(0.55,0.45)); e2=prob(11.0,e1.entry_hash,(0.58,0.42))
    lock=recompute_first_lock([e1,e2],threshold=.8,persistence=2,lock_policy_sha256=F)
    assert lock.status=="NO_RELIABLE_LOCK" and lock.entry_hash is None


def test_execution_handoff_forbids_reprediction_retiming_and_view_substitution():
    e1=prob(10.0,probs=(0.85,0.15))
    lock=recompute_first_lock([e1],threshold=.8,persistence=1,lock_policy_sha256=F)
    h=seal_execution_handoff(
        signal_id="s1",execution_handoff_id="x1",lane_id="lane",instance_id="i1",
        probability_entry_hash=e1.entry_hash,first_lock_hash=lock.lock_hash,state_movie_hash=D,
        model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,eligibility_state="ELIGIBLE",
        decision_available_at=lock.decision_available_at,
    )
    validate_execution_binding(h,probability_entry=e1,first_lock=lock,state_movie_hash=D)
    with pytest.raises(V4ContractError):
        validate_execution_binding(dataclasses.replace(h,state_movie_hash=E,handoff_hash=""),probability_entry=e1,first_lock=lock,state_movie_hash=E)
