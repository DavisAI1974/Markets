from __future__ import annotations
import dataclasses,pytest
from research.kalshi.ng_exhaustion_v4_causal_clock import make_receipt
from research.kalshi.ng_exhaustion_v4_gate_verifier import DetectorIntensityResolution,GateVerificationError,SparseStagePolicy,verify_prelaunch_gates
from research.kalshi.ng_exhaustion_v4_history_support import make_session_coverage
from research.kalshi.ng_exhaustion_v4_lock_outcome import recompute_lock_outcome
from research.kalshi.ng_exhaustion_v4_mechanics import CausalField,LifecycleState,Missingness,PredecessorLifecycle,make_probability_entry,make_state_row,seal_execution_handoff
A="a"*64;B="b"*64;C="c"*64;D="d"*64;E="e"*64;F="f"*64

def bundle():
    d=make_receipt(event_id="e",session_id="s",detector_revision="replay-v1",detector_source_sha256=A,source_manifest_sha256=B,source_object_id="raw",source_range_id="r",source_ts_event=4,source_ts_recv=5,detector_marked_at=5,event_known_by=5,canonical_t0=3,mark_mode="CAUSAL_REPLAY")
    f=CausalField("x",Missingness.OBSERVED,1.0,8,9,10,A)
    s=make_state_row(instance_id="i",causal_second=10,event_known_by=5,fields=(f,),source_manifest_sha256=B,transform_sha256=C)
    l=PredecessorLifecycle("i","p",5,10,LifecycleState.UNRESOLVED,5)
    cov=make_session_coverage(session_id="s",requested_symbol="NG.v.0",mbo="VERIFIED",mbp10="MISSING",l1="MISSING",native_object_sha256s=(D,),symbology_binding_hashes=(E,))
    p=make_probability_entry(signal_lane_id="lane",instance_id="i",head_id="h",causal_evaluation_at=10,decision_available_at=10.1,probabilities=(.85,.15),state_movie_hash=s.row_hash,model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,missingness_manifest_sha256=D)
    lock=recompute_lock_outcome([p],threshold=.8,persistence=1,lock_policy_sha256=F)
    h=seal_execution_handoff(signal_id="sig",execution_handoff_id="x",lane_id="lane",instance_id="i",probability_entry_hash=p.entry_hash,first_lock_hash=lock.lock_hash,state_movie_hash=s.row_hash,model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,eligibility_state="ELIGIBLE",decision_available_at=lock.decision_available_at)
    return d,s,l,cov,p,lock,h

def test_all_nine_mechanical_gates_recompute_without_authorizing_launch():
    d,s,l,cov,p,lock,h=bundle()
    out=verify_prelaunch_gates(discovery=d,feature_available_at=10,model_evaluated_at=10,decision_available_at=10.1,state_rows=[s],lifecycles=[l],coverage=[cov],intensity=DetectorIntensityResolution("OMITTED"),probability_entries=[p],claimed_first_lock=lock,lock_threshold=.8,lock_persistence=1,lock_policy_sha256=F,handoff=h,sparse_policy=SparseStagePolicy(8,1,True,False,False))
    assert len(out["gates"])==9 and all(out["gates"].values())
    assert out["trusted_v4_empirical_launch_authorized"] is False
    assert out["p0_six_real_receipts_satisfied_by_this_receipt"] is False

def test_claimed_lock_tamper_is_rejected():
    d,s,l,cov,p,lock,h=bundle()
    bad=dataclasses.replace(lock,lock_hash=A)
    with pytest.raises(GateVerificationError):
        verify_prelaunch_gates(discovery=d,feature_available_at=10,model_evaluated_at=10,decision_available_at=10.1,state_rows=[s],lifecycles=[l],coverage=[cov],intensity=DetectorIntensityResolution("OMITTED"),probability_entries=[p],claimed_first_lock=bad,lock_threshold=.8,lock_persistence=1,lock_policy_sha256=F,handoff=h,sparse_policy=SparseStagePolicy(8,1,True,False,False))

def test_proxy_cannot_masquerade_as_native_intensity():
    with pytest.raises(GateVerificationError): DetectorIntensityResolution("EXPLICIT_PROXY",proxy_namespace="detector_native_intensity").validate()
