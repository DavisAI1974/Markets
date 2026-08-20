from __future__ import annotations
from research.kalshi.ng_exhaustion_v4_lock_outcome import recompute_lock_outcome
from research.kalshi.ng_exhaustion_v4_mechanics import GENESIS,make_probability_entry,seal_execution_handoff,validate_execution_binding
A="a"*64;B="b"*64;C="c"*64;D="d"*64;E="e"*64;F="f"*64

def p(t,prior=GENESIS,probs=(.55,.45)):
    return make_probability_entry(signal_lane_id="l",instance_id="i",head_id="h",causal_evaluation_at=t,decision_available_at=t+.1,probabilities=probs,state_movie_hash=D,model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,missingness_manifest_sha256=E,prior_entry_hash=prior)

def test_no_reliable_lock_binds_last_probability_entry_and_can_seal_abstention():
    e1=p(10);e2=p(11,e1.entry_hash,(.58,.42))
    lock=recompute_lock_outcome([e1,e2],threshold=.8,persistence=2,lock_policy_sha256=F)
    assert lock.status=="NO_RELIABLE_LOCK"
    assert lock.entry_hash==e2.entry_hash and lock.decision_available_at==e2.decision_available_at
    h=seal_execution_handoff(signal_id="s",execution_handoff_id="x",lane_id="l",instance_id="i",probability_entry_hash=e2.entry_hash,first_lock_hash=lock.lock_hash,state_movie_hash=D,model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,eligibility_state="ABSTAIN_NO_RELIABLE_LOCK",decision_available_at=e2.decision_available_at)
    validate_execution_binding(h,probability_entry=e2,first_lock=lock,state_movie_hash=D)
