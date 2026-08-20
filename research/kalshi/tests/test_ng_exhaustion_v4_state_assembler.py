from __future__ import annotations

import pytest

from research.kalshi.ng_exhaustion_v4_mechanics import Missingness
from research.kalshi.ng_exhaustion_v4_state_assembler import (
    CausalStateAssembler, FieldPolicy, Observation, StateAssemblerError,
)

A="a"*64;B="b"*64;C="c"*64;D="d"*64


def assembler():
    return CausalStateAssembler([
        FieldPolicy("zero_ok",A,5),
        FieldPolicy("carry",B,5),
        FieldPolicy("notyet",C,5,structurally_known_at=20),
        FieldPolicy("na",D,5,applicable=False),
    ],transform_sha256=A)


def obs(name,value,event,recv,avail,sha,oid):
    return Observation(name,value,event,recv,avail,sha,oid)


def by_name(fields): return {f.name:f for f in fields}


def test_true_zero_is_observed_not_missing():
    fields=by_name(assembler().assemble_fields(cutoff=10,observations=[obs("zero_ok",0.0,9,10,10,A,"z")]))
    assert fields["zero_ok"].status==Missingness.OBSERVED
    assert fields["zero_ok"].value==0.0


def test_future_observation_cannot_backfill_earlier_state():
    observations=[obs("carry",1.0,9,10,10,B,"old"),obs("carry",99.0,10,12,12,B,"future")]
    f10=by_name(assembler().assemble_fields(cutoff=10,observations=observations))["carry"]
    f12=by_name(assembler().assemble_fields(cutoff=12,observations=observations))["carry"]
    assert f10.value==1.0 and f10.status==Missingness.OBSERVED
    assert f12.value==99.0 and f12.status==Missingness.OBSERVED


def test_carry_stale_missing_notyet_and_not_applicable_are_distinct():
    observations=[obs("carry",2.0,8,9,9,B,"c")]
    f12=by_name(assembler().assemble_fields(cutoff=12,observations=observations))
    assert f12["carry"].status==Missingness.PAST_CARRY and f12["carry"].age_seconds==3
    assert f12["zero_ok"].status==Missingness.MISSING
    assert f12["notyet"].status==Missingness.STRUCTURALLY_NOT_YET_KNOWN
    assert f12["na"].status==Missingness.NOT_APPLICABLE
    f16=by_name(assembler().assemble_fields(cutoff=16,observations=observations))
    assert f16["carry"].status==Missingness.STALE and f16["carry"].age_seconds==7


def test_no_carry_policy_becomes_missing_after_observation_time():
    a=CausalStateAssembler([FieldPolicy("instant",A,5,carry_allowed=False)],transform_sha256=B)
    f=by_name(a.assemble_fields(cutoff=11,observations=[obs("instant",3,9,10,10,A,"i")]))["instant"]
    assert f.status==Missingness.MISSING and f.value is None


def test_source_identity_drift_fails_closed():
    with pytest.raises(StateAssemblerError):
        assembler().assemble_fields(cutoff=10,observations=[obs("zero_ok",1,9,10,10,B,"wrong-source")])


def test_immutable_movie_rejects_overwrite_or_backfill():
    a=assembler()
    r10=a.append_state(instance_id="i",cutoff=10,event_known_by=5,source_manifest_sha256=C,
                       observations=[obs("zero_ok",0,9,10,10,A,"z")])
    r11=a.append_state(instance_id="i",cutoff=11,event_known_by=5,source_manifest_sha256=C,
                       observations=[obs("zero_ok",0,9,10,10,A,"z")],prior_rows=[r10])
    assert r11.prior_row_hash==r10.row_hash
    with pytest.raises(StateAssemblerError):
        a.append_state(instance_id="i",cutoff=10,event_known_by=5,source_manifest_sha256=C,
                       observations=[],prior_rows=[r10,r11])


def test_state_cannot_exist_before_event_known_by():
    with pytest.raises(StateAssemblerError):
        assembler().append_state(instance_id="i",cutoff=4,event_known_by=5,source_manifest_sha256=C,observations=[])
