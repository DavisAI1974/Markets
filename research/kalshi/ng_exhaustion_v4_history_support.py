#!/usr/bin/env python3
"""Provenance/coverage contracts for additive V4 outside chronology.

The five-year historical archive is support expansion only. This module never mutates
the frozen 55-week population or changes detector/canonical rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
SCHEMA_VERSION="NG_EXHAUSTION_V4_HISTORY_SUPPORT_V1"

class HistorySupportError(ValueError): pass

def _id(v:Any,f:str)->str:
    x=str(v or "").strip()
    if not x: raise HistorySupportError(f"{f} must be non-empty")
    return x

def _sha(v:Any,f:str)->str:
    x=str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(x): raise HistorySupportError(f"{f} must be lowercase SHA-256")
    return x

def _hash(x:Mapping[str,Any])->str:
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

@dataclass(frozen=True)
class NativeObject:
    s3_key:str
    bytes:int
    sha256:str
    databento_job_id:str
    dataset:str
    schema:str
    requested_symbol:str
    stype_in:str
    segment_start:str
    segment_end:str

    def validate(self)->"NativeObject":
        _id(self.s3_key,"s3_key"); _sha(self.sha256,"sha256"); _id(self.databento_job_id,"databento_job_id")
        if self.bytes<=0: raise HistorySupportError("native object bytes must be positive")
        if self.dataset!="GLBX.MDP3" or self.schema!="mbo": raise HistorySupportError("unexpected dataset/schema")
        if self.requested_symbol not in {"NG.v.0","NG.n.0","NG.c.0"}: raise HistorySupportError("requested continuous symbol must be explicit")
        if self.stype_in!="continuous": raise HistorySupportError("historical support requires explicit continuous input type")
        _id(self.segment_start,"segment_start"); _id(self.segment_end,"segment_end")
        return self

@dataclass(frozen=True)
class SymbologyBinding:
    requested_symbol:str
    roll_rule:str
    instrument_id:int
    raw_symbol:str
    effective_start:str
    effective_end:str
    definition_sha256:str
    mapping_source_sha256:str

    def validate(self)->"SymbologyBinding":
        expected={"NG.v.0":"v","NG.n.0":"n","NG.c.0":"c"}
        if self.requested_symbol not in expected or self.roll_rule!=expected[self.requested_symbol]:
            raise HistorySupportError("continuous symbol/roll rule mismatch")
        if type(self.instrument_id) is not int or self.instrument_id<=0: raise HistorySupportError("instrument_id must be positive int")
        _id(self.raw_symbol,"raw_symbol"); _id(self.effective_start,"effective_start"); _id(self.effective_end,"effective_end")
        _sha(self.definition_sha256,"definition_sha256"); _sha(self.mapping_source_sha256,"mapping_source_sha256")
        return self

@dataclass(frozen=True)
class SessionCoverage:
    session_id:str
    requested_symbol:str
    mbo:str
    mbp10:str
    l1:str
    native_object_sha256s:tuple[str,...]
    symbology_binding_hashes:tuple[str,...]
    coverage_manifest_hash:str=""

    def core(self)->dict[str,Any]:
        return {
            "schema":SCHEMA_VERSION,"session_id":self.session_id,"requested_symbol":self.requested_symbol,
            "mbo":self.mbo,"mbp10":self.mbp10,"l1":self.l1,
            "native_object_sha256s":list(self.native_object_sha256s),
            "symbology_binding_hashes":list(self.symbology_binding_hashes),
        }
    def validate(self)->"SessionCoverage":
        _id(self.session_id,"session_id")
        if self.requested_symbol not in {"NG.v.0","NG.n.0","NG.c.0"}: raise HistorySupportError("ambiguous requested symbol")
        allowed={"VERIFIED","MISSING","PARTIAL","NOT_APPLICABLE"}
        for f in ("mbo","mbp10","l1"):
            if getattr(self,f) not in allowed: raise HistorySupportError(f"invalid {f} coverage state")
        for h in self.native_object_sha256s: _sha(h,"native_object_sha256")
        for h in self.symbology_binding_hashes: _sha(h,"symbology_binding_hash")
        if self.mbo=="VERIFIED" and not self.native_object_sha256s:
            raise HistorySupportError("MBO cannot be VERIFIED without native object identity")
        expected=_hash(self.core())
        if self.coverage_manifest_hash and self.coverage_manifest_hash!=expected: raise HistorySupportError("coverage manifest hash mismatch")
        return self

def binding_hash(b:SymbologyBinding)->str:
    b.validate(); return _hash({"schema":SCHEMA_VERSION,"binding":asdict(b)})

def make_session_coverage(**kwargs:Any)->SessionCoverage:
    c=SessionCoverage(**kwargs); c.validate()
    return SessionCoverage(**{**asdict(c),"native_object_sha256s":c.native_object_sha256s,
                              "symbology_binding_hashes":c.symbology_binding_hashes,
                              "coverage_manifest_hash":_hash(c.core())}).validate()

def validate_native_manifest(rows:Sequence[NativeObject], *, required_symbol:str="NG.v.0")->str:
    if not rows: raise HistorySupportError("native manifest cannot be empty")
    keys=set(); hashes=set(); payload=[]
    for r in rows:
        r.validate()
        if r.requested_symbol!=required_symbol: raise HistorySupportError("v/n/c source substitution detected")
        if r.s3_key in keys: raise HistorySupportError("duplicate S3 key")
        if r.sha256 in hashes: raise HistorySupportError("duplicate native content hash")
        keys.add(r.s3_key); hashes.add(r.sha256); payload.append(asdict(r))
    return _hash({"schema":SCHEMA_VERSION,"required_symbol":required_symbol,"objects":sorted(payload,key=lambda x:x["s3_key"])})

def assert_detector_unchanged(*, expected_sha256:str, actual_sha256:str)->None:
    if _sha(expected_sha256,"expected_detector_sha256")!=_sha(actual_sha256,"actual_detector_sha256"):
        raise HistorySupportError("frozen detector hash changed; outside-history run forbidden")

def build_additive_case_ledger(*, frozen_case_ids:Sequence[str], outside_cases:Sequence[Mapping[str,Any]],
                               detector_sha256:str, canonical_rules_sha256:str)->dict[str,Any]:
    _sha(detector_sha256,"detector_sha256"); _sha(canonical_rules_sha256,"canonical_rules_sha256")
    frozen={_id(x,"frozen_case_id") for x in frozen_case_ids}
    kept=[]; seen=set()
    depth_counts={f"D{i}":0 for i in range(6)}
    for row in outside_cases:
        cid=_id(row.get("case_id"),"case_id")
        if cid in frozen: raise HistorySupportError("outside chronology overlaps frozen case identity")
        if cid in seen: raise HistorySupportError("duplicate outside case id")
        seen.add(cid)
        depth=str(row.get("depth") or "")
        if depth not in depth_counts: raise HistorySupportError(f"invalid depth {depth}")
        # No outcome filtering: true/false/losing/censored/weak/model-disagreement rows are all retained.
        kept.append(dict(row)); depth_counts[depth]+=1
    core={
        "schema":SCHEMA_VERSION,
        "policy":"ADDITIVE_OUTSIDE_CHRONOLOGY_NO_FROZEN_MUTATION_NO_CASE_DROPS",
        "detector_sha256":detector_sha256,
        "canonical_rules_sha256":canonical_rules_sha256,
        "outside_case_count":len(kept),
        "depth_counts":depth_counts,
        "cases":kept,
    }
    return {**core,"ledger_hash":_hash(core)}
