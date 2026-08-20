from __future__ import annotations
from types import SimpleNamespace
import pytest

from research.kalshi.ng_exhaustion_v4_causal_clock import CausalClockError,make_receipt
from research.kalshi.ng_exhaustion_v4_causal_entry_adapter import activate_frozen_runway,authorize_v4_evaluation

A="a"*64;B="b"*64


def receipt(known=12,canonical=10):
    return make_receipt(event_id="e",session_id="s",detector_revision="replay-v1",detector_source_sha256=A,source_manifest_sha256=B,source_object_id="raw",source_range_id="r",source_ts_event=9,source_ts_recv=11,detector_marked_at=12,event_known_by=known,canonical_t0=canonical,mark_mode="CAUSAL_REPLAY")


class FakeEngine:
    def __init__(self,last):
        self.feed=SimpleNamespace(last_seen_second=last); self.calls=[]
    def mark_event(self,**kwargs):
        self.calls.append(kwargs); return {"frozen":kwargs}


def test_canonical_t0_does_not_activate_runway_before_event_known_by():
    e=FakeEngine(11)
    with pytest.raises(CausalClockError): activate_frozen_runway(receipt=receipt(),runway_engine=e)
    assert e.calls==[]


def test_runway_keeps_structural_t0_but_activation_is_known_by():
    e=FakeEngine(12)
    a=activate_frozen_runway(receipt=receipt(),runway_engine=e)
    assert a.canonical_t0==10 and a.event_known_by==12 and a.activation_second==12
    assert e.calls==[{"event_id":"e","session_id":"s","t0_second":10}]


def test_v4_evaluation_cannot_backdate_to_canonical_t0():
    r=receipt()
    with pytest.raises(CausalClockError): authorize_v4_evaluation(receipt=r,feature_available_at=10,model_evaluated_at=10.5,decision_available_at=11)
    assert authorize_v4_evaluation(receipt=r,feature_available_at=12,model_evaluated_at=12.1,decision_available_at=12.2)["event_known_by"]==12
