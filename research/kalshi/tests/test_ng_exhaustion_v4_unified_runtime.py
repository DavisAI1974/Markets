from __future__ import annotations

import dataclasses
import pytest

from research.kalshi.ng_exhaustion_v4_causal_clock import make_receipt
from research.kalshi.ng_exhaustion_v4_gate_verifier import DetectorIntensityResolution, SparseStagePolicy
from research.kalshi.ng_exhaustion_v4_history_support import make_session_coverage
from research.kalshi.ng_exhaustion_v4_mechanics import (
    CausalField,
    LifecycleState,
    Missingness,
    PredecessorLifecycle,
    V4LaneSpec,
    make_probability_entry,
    make_state_row,
)
from research.kalshi.ng_exhaustion_v4_unified_runtime import (
    CaseEnvelope,
    EngineInput,
    RegisteredLane,
    UnifiedV4Error,
    UnifiedV4Orchestrator,
    UnifiedV4Reconciler,
    V4LaneRegistry,
)

A="a"*64; B="b"*64; C="c"*64; D="d"*64; E="e"*64; F="f"*64


def lane(lane_id: str, mode: str, *, population: str, non_promotable: bool=False, restrictions=None):
    spec=V4LaneSpec(
        lane_id=lane_id,mode=mode,population_manifest_sha256=A,
        feature_schema_sha256=B,adapter_sha256=C,reveal_policy_sha256=D,lock_policy_sha256=F,
    )
    rules=restrictions if restrictions is not None else {"adaptation_allowed": mode=="WALK_FORWARD"}
    return RegisteredLane(spec,C,population,"label-v1","coords-v1",rules,non_promotable)


def registry():
    r=V4LaneRegistry()
    r.register(lane("D0","WALK_FORWARD",population="D0_FROZEN"))
    r.register(lane("D4","CASE_STUDY_NO_ADAPTATION",population="D4_PRESERVED_8"))
    r.register(lane("POX_MEMBERSHIP","WALK_FORWARD",population="POX_MEMBERSHIP_FULL"))
    r.register(lane("POX_FIXED_BRANCH","WALK_FORWARD_POSTHOC_ORACLE_CONDITIONED",population="POX_FIXED_3429",non_promotable=True))
    return r


def case(instance="i1"):
    discovery=make_receipt(
        event_id="e1",session_id="s1",detector_revision="replay-v1",detector_source_sha256=A,
        source_manifest_sha256=C,source_object_id="raw",source_range_id="range",source_ts_event=4,
        source_ts_recv=5,detector_marked_at=5,event_known_by=5,canonical_t0=3,mark_mode="CAUSAL_REPLAY",
    )
    coverage=make_session_coverage(
        session_id="s1",requested_symbol="NG.v.0",mbo="VERIFIED",mbp10="MISSING",l1="MISSING",
        native_object_sha256s=(D,),symbology_binding_hashes=(E,),
    )
    life=PredecessorLifecycle(instance,"pred",5,10,LifecycleState.UNRESOLVED,5)
    return CaseEnvelope(
        case_id="case1",instance_id=instance,group_id="g1",start_timestamp=10,end_timestamp=12,
        reveal_timestamp=20,discovery=discovery,coverage=(coverage,),lifecycles=(life,),
        sparse_policy=SparseStagePolicy(8,1,True,False,False),intensity=DetectorIntensityResolution("OMITTED"),
        case_manifest_sha256=E,
    )


def engine_input(lane_id: str, *, candidate_update_requested=True, evaluation_at=10.0):
    field=CausalField("flow",Missingness.OBSERVED,0.25,8,9,10,A)
    state=make_state_row(instance_id="i1",causal_second=10,event_known_by=5,fields=(field,),source_manifest_sha256=C,transform_sha256=D)
    p=make_probability_entry(
        signal_lane_id=lane_id,instance_id="i1",head_id="head",causal_evaluation_at=evaluation_at,
        decision_available_at=evaluation_at+.1,probabilities=(.85,.15),state_movie_hash=state.row_hash,
        model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,missingness_manifest_sha256=D,
    )
    return EngineInput(
        lane_id=lane_id,case=case(),state_rows=(state,),probability_entries=(p,),lock_threshold=.8,
        lock_persistence=1,lock_policy_sha256=F,model_sha256=A,snapshot_sha256=B,
        source_manifest_sha256=C,eligibility_state="ELIGIBLE",candidate_update_requested=candidate_update_requested,
    )


def test_walk_forward_case_uses_shared_engine_but_never_applies_update_here():
    r=registry(); a=UnifiedV4Orchestrator(r).evaluate(engine_input("D0"))
    assert a.lane_mode=="WALK_FORWARD"
    assert a.update_eligible is True and a.update_applied is False
    assert a.execution_handoff.lane_id=="D0"


def test_d4_case_study_is_same_engine_and_cannot_adapt():
    r=registry(); a=UnifiedV4Orchestrator(r).evaluate(engine_input("D4"))
    assert a.lane_mode=="CASE_STUDY_NO_ADAPTATION"
    assert a.update_eligible is False and a.update_applied is False


def test_posthoc_pox_branch_is_permanently_non_promotable_and_nonadaptive():
    r=registry(); a=UnifiedV4Orchestrator(r).evaluate(engine_input("POX_FIXED_BRANCH"))
    assert a.permanently_non_promotable is True
    assert a.update_eligible is False


def test_membership_and_fixed_branch_population_identities_are_distinct():
    r=registry()
    assert r.get("POX_MEMBERSHIP").adapter_population_id != r.get("POX_FIXED_BRANCH").adapter_population_id


def test_registry_rejects_posthoc_lane_without_permanent_nonpromotion():
    r=V4LaneRegistry()
    with pytest.raises(UnifiedV4Error):
        r.register(lane("bad","WALK_FORWARD_POSTHOC_ORACLE_CONDITIONED",population="oracle",non_promotable=False))


def test_registry_rejects_case_study_that_allows_adaptation():
    spec=V4LaneSpec("D5","CASE_STUDY_NO_ADAPTATION",A,B,C,D,F)
    bad=RegisteredLane(spec,C,"D5_PRESERVED_1","label","coords",{"adaptation_allowed":True},False)
    with pytest.raises(UnifiedV4Error): V4LaneRegistry().register(bad)


def test_registered_restrictions_are_detached_from_caller_mutation():
    rules={"adaptation_allowed":True,"note":"original"}
    r=V4LaneRegistry(); r.register(lane("D1","WALK_FORWARD",population="D1_FROZEN",restrictions=rules))
    before=r.registry_hash
    rules["note"]="mutated-after-register"
    assert r.registry_hash==before
    assert r.get("D1").restrictions["note"]=="original"


def test_reveal_boundary_is_engine_invariant():
    with pytest.raises(UnifiedV4Error):
        UnifiedV4Orchestrator(registry()).evaluate(engine_input("D0",evaluation_at=20.0))


def test_model_or_snapshot_substitution_is_rejected_before_handoff():
    inp=engine_input("D0")
    with pytest.raises(UnifiedV4Error):
        UnifiedV4Orchestrator(registry()).evaluate(dataclasses.replace(inp,model_sha256=E))


def test_reconciler_recomputes_and_rejects_tamper():
    r=registry(); inp=engine_input("D0"); artifact=UnifiedV4Orchestrator(r).evaluate(inp)
    receipt=UnifiedV4Reconciler(r).reconcile(inp,artifact)
    assert receipt["recomputed"] is True and receipt["v4_empirical_launch_authorized"] is False
    with pytest.raises(UnifiedV4Error):
        UnifiedV4Reconciler(r).reconcile(inp,dataclasses.replace(artifact,update_eligible=False))


def test_unregistered_lane_has_no_execution_path():
    with pytest.raises(UnifiedV4Error):
        UnifiedV4Orchestrator(registry()).evaluate(engine_input("UNKNOWN"))
