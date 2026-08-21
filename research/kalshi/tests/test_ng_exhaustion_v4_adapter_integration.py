from __future__ import annotations

import dataclasses
import pytest

from research.kalshi.ng_exhaustion_v4_adapter_integration import (
    AdapterAvailability,
    AdapterIntegrationError,
    AdapterIntegrationInput,
    IntegratedV4Adapter,
)
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
    V4LaneRegistry,
)

A="a"*64; B="b"*64; C="c"*64; D="d"*64; E="e"*64; F="f"*64


def registry():
    r=V4LaneRegistry()
    spec=V4LaneSpec("D0","WALK_FORWARD",A,B,C,D,F)
    r.register(RegisteredLane(spec,C,"D0_FROZEN","label-v1","coords-v1",{"adaptation_allowed":True},False))
    return r


def discovery():
    return make_receipt(
        event_id="e1",session_id="s1",detector_revision="replay-v1",detector_source_sha256=A,
        source_manifest_sha256=C,source_object_id="raw",source_range_id="range",source_ts_event=4,
        source_ts_recv=5,detector_marked_at=5,event_known_by=5,canonical_t0=3,mark_mode="CAUSAL_REPLAY",
    )


def engine_input(*, evaluation_at=10.0, discovery_receipt=None):
    disc=discovery_receipt or discovery()
    coverage=make_session_coverage(
        session_id="s1",requested_symbol="NG.v.0",mbo="VERIFIED",mbp10="MISSING",l1="MISSING",
        native_object_sha256s=(D,),symbology_binding_hashes=(E,),
    )
    life=PredecessorLifecycle("i1","pred",5,10,LifecycleState.UNRESOLVED,5)
    case=CaseEnvelope(
        case_id="case1",instance_id="i1",group_id="g1",start_timestamp=10,end_timestamp=12,
        reveal_timestamp=20,discovery=disc,coverage=(coverage,),lifecycles=(life,),
        sparse_policy=SparseStagePolicy(8,1,True,False,False),intensity=DetectorIntensityResolution("OMITTED"),
        case_manifest_sha256=E,
    )
    field=CausalField("flow",Missingness.OBSERVED,0.25,8,9,10,A)
    state=make_state_row(instance_id="i1",causal_second=10,event_known_by=5,fields=(field,),source_manifest_sha256=C,transform_sha256=D)
    p=make_probability_entry(
        signal_lane_id="D0",instance_id="i1",head_id="head",causal_evaluation_at=evaluation_at,
        decision_available_at=evaluation_at+.1,probabilities=(.85,.15),state_movie_hash=state.row_hash,
        model_sha256=A,snapshot_sha256=B,source_manifest_sha256=C,missingness_manifest_sha256=D,
    )
    return EngineInput(
        lane_id="D0",case=case,state_rows=(state,),probability_entries=(p,),lock_threshold=.8,
        lock_persistence=1,lock_policy_sha256=F,model_sha256=A,snapshot_sha256=B,
        source_manifest_sha256=C,eligibility_state="ELIGIBLE",candidate_update_requested=False,
    )


def payload(**kwargs):
    disc=kwargs.pop("discovery", discovery())
    inp=kwargs.pop("engine_input", engine_input(discovery_receipt=disc))
    avail=kwargs.pop("availability", AdapterAvailability(9.5,10.0,10.1))
    assert not kwargs
    return AdapterIntegrationInput(disc,avail,inp)


def test_full_adapter_chain_reconciles_and_preserves_reveal_wall():
    out=IntegratedV4Adapter(registry()).run(payload())
    assert out["status"]=="V4_ADAPTER_INTEGRATION_RECONCILED"
    assert out["first_lock_independently_recomputed"] is True
    assert out["execution_handoff_sealed"] is True
    assert out["reveal_wall_preserved"] is True
    assert out["v4_empirical_launch"] is False


def test_feature_availability_before_event_known_by_fails_closed():
    with pytest.raises(Exception):
        IntegratedV4Adapter(registry()).run(payload(availability=AdapterAvailability(4.9,10,10.1)))


def test_case_discovery_identity_mismatch_fails_closed():
    d1=discovery()
    d2=make_receipt(
        event_id="e2",session_id="s1",detector_revision="replay-v1",detector_source_sha256=A,
        source_manifest_sha256=C,source_object_id="raw",source_range_id="range2",source_ts_event=4,
        source_ts_recv=5,detector_marked_at=5,event_known_by=5,canonical_t0=3,mark_mode="CAUSAL_REPLAY",
    )
    with pytest.raises(AdapterIntegrationError):
        IntegratedV4Adapter(registry()).run(payload(discovery=d1,engine_input=engine_input(discovery_receipt=d2)))


def test_probability_before_lawful_feature_availability_fails_closed():
    inp=engine_input(evaluation_at=9.0)
    with pytest.raises(AdapterIntegrationError):
        IntegratedV4Adapter(registry()).run(payload(engine_input=inp,availability=AdapterAvailability(9.5,10,10.1)))


def test_probability_at_reveal_is_rejected():
    inp=engine_input(evaluation_at=20.0)
    with pytest.raises(Exception):
        IntegratedV4Adapter(registry()).run(payload(engine_input=inp,availability=AdapterAvailability(9.5,20,20.1)))


def test_state_event_known_by_drift_is_rejected():
    inp=engine_input()
    bad_state=dataclasses.replace(inp.state_rows[0],event_known_by=4)
    bad=dataclasses.replace(inp,state_rows=(bad_state,))
    with pytest.raises(Exception):
        IntegratedV4Adapter(registry()).run(payload(engine_input=bad))
