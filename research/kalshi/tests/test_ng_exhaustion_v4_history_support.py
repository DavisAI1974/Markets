from __future__ import annotations

import pytest

from research.kalshi.ng_exhaustion_v4_history_support import (
    HistorySupportError, NativeObject, SessionCoverage, SymbologyBinding,
    assert_detector_unchanged, binding_hash, build_additive_case_ledger,
    make_session_coverage, validate_native_manifest,
)

A="a"*64; B="b"*64; C="c"*64; D="d"*64

def native(symbol="NG.v.0",key="nymex/ng_mbo_5y_v0/native/a.dbn.zst",sha=A):
    return NativeObject(key,100,sha,"job1","GLBX.MDP3","mbo",symbol,"continuous","2021-08-20","2021-08-21")

def test_native_manifest_rejects_roll_substitution():
    assert len(validate_native_manifest([native()]))==64
    with pytest.raises(HistorySupportError): validate_native_manifest([native("NG.n.0")],required_symbol="NG.v.0")

def test_symbology_binding_binds_roll_to_requested_series():
    b=SymbologyBinding("NG.v.0","v",123,"NGU21","2021-08-20","2021-08-21",A,B)
    assert len(binding_hash(b))==64
    with pytest.raises(HistorySupportError): SymbologyBinding("NG.v.0","n",123,"NGU21","x","y",A,B).validate()

def test_verified_mbo_requires_native_identity():
    with pytest.raises(HistorySupportError):
        make_session_coverage(session_id="s",requested_symbol="NG.v.0",mbo="VERIFIED",mbp10="MISSING",l1="MISSING",native_object_sha256s=(),symbology_binding_hashes=())
    c=make_session_coverage(session_id="s",requested_symbol="NG.v.0",mbo="VERIFIED",mbp10="MISSING",l1="MISSING",native_object_sha256s=(A,),symbology_binding_hashes=(B,))
    assert len(c.coverage_manifest_hash)==64

def test_detector_hash_drift_blocks_outside_history_run():
    assert_detector_unchanged(expected_sha256=A,actual_sha256=A)
    with pytest.raises(HistorySupportError): assert_detector_unchanged(expected_sha256=A,actual_sha256=B)

def test_additive_ledger_keeps_all_cases_and_never_overwrites_frozen():
    cases=[
        {"case_id":"o1","depth":"D4","outcome":"losing"},
        {"case_id":"o2","depth":"D5","outcome":"censored"},
        {"case_id":"o3","depth":"D3","outcome":"false"},
    ]
    out=build_additive_case_ledger(frozen_case_ids=["f1"],outside_cases=cases,detector_sha256=A,canonical_rules_sha256=B)
    assert out["outside_case_count"]==3
    assert out["depth_counts"]["D4"]==1 and out["depth_counts"]["D5"]==1
    assert {x["case_id"] for x in out["cases"]}=={"o1","o2","o3"}
    with pytest.raises(HistorySupportError):
        build_additive_case_ledger(frozen_case_ids=["o1"],outside_cases=cases,detector_sha256=A,canonical_rules_sha256=B)
