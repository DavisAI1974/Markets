#!/usr/bin/env python3
"""Immutable precommit contract for Frankie's six real P0 empirical receipts.

This does not execute a model, evaluator, mutation, rollback, or consume any holdout.
It only makes the required real-evidence package hash-bindable before execution.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib,json,re
from typing import Any,Mapping,Sequence

SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
SCHEMA="FRANKIE_P0_REAL_EVIDENCE_PLAN_V1"
RECEIPTS=("HELD_OUT_PAIRED_PERFORMANCE","CALIBRATION_SELECTIVE_RISK","PLANTED_NULL_CONTAMINATION","PROTECTED_RETENTION_MATRIX","EVALUATOR_INDEPENDENCE","BYTE_EXACT_LIVE_ROLLBACK")
class EvidencePlanError(ValueError): pass

def _id(v:Any,f:str)->str:
    x=str(v or "").strip()
    if not x: raise EvidencePlanError(f"{f} must be non-empty")
    return x

def _sha(v:Any,f:str)->str:
    x=str(v or "").strip().lower()
    if not SHA256_RE.fullmatch(x): raise EvidencePlanError(f"{f} must be lowercase SHA-256")
    return x

def _hash(x:Mapping[str,Any])->str:
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

@dataclass(frozen=True)
class Partition:
    partition_id:str
    role:str
    manifest_sha256:str
    exposed_to_candidate_development:bool
    def validate(self)->"Partition":
        _id(self.partition_id,"partition_id"); _sha(self.manifest_sha256,"manifest_sha256")
        allowed={"DEVELOPMENT_SUPPORT","CALIBRATION_FIT","CALIBRATION_EVAL","PROTECTED_RETENTION","PLANTED_NULL_HIDDEN","UNTOUCHED_FORWARD","RELEASE_HOLDOUT"}
        if self.role not in allowed: raise EvidencePlanError("invalid partition role")
        if self.role in {"PLANTED_NULL_HIDDEN","UNTOUCHED_FORWARD","RELEASE_HOLDOUT"} and self.exposed_to_candidate_development:
            raise EvidencePlanError(f"{self.role} cannot be exposed to candidate development")
        return self

@dataclass(frozen=True)
class EvidencePlan:
    candidate_sha256:str
    baseline_sha256:str
    runner_sha256:str
    evaluator_sha256:str
    evaluator_canary_manifest_sha256:str
    control_manifest_sha256:str
    budget_manifest_sha256:str
    seed_manifest_sha256:str
    policy_manifest_sha256:str
    validator_bundle_sha256:str
    partitions:tuple[Partition,...]
    disposable_rollback_target_id:str
    rollback_baseline_sha256:str
    external_backend_authority_id:str
    evaluator_owner_id:str
    mutation_authority_id:str
    plan_hash:str=""

    def core(self)->dict[str,Any]:
        d=asdict(self); d.pop("plan_hash",None); return {"schema":SCHEMA,**d}
    def validate(self)->"EvidencePlan":
        for f in ("candidate_sha256","baseline_sha256","runner_sha256","evaluator_sha256","evaluator_canary_manifest_sha256","control_manifest_sha256","budget_manifest_sha256","seed_manifest_sha256","policy_manifest_sha256","validator_bundle_sha256","rollback_baseline_sha256"):
            _sha(getattr(self,f),f)
        for f in ("disposable_rollback_target_id","external_backend_authority_id","evaluator_owner_id","mutation_authority_id"):
            _id(getattr(self,f),f)
        if self.candidate_sha256==self.evaluator_sha256:
            raise EvidencePlanError("candidate and evaluator must be independent artifacts")
        roles={}; ids=set(); hashes=set()
        for p in self.partitions:
            p.validate()
            if p.partition_id in ids or p.manifest_sha256 in hashes: raise EvidencePlanError("partition identity/hash reused")
            ids.add(p.partition_id); hashes.add(p.manifest_sha256); roles.setdefault(p.role,0); roles[p.role]+=1
        required={"DEVELOPMENT_SUPPORT","CALIBRATION_FIT","CALIBRATION_EVAL","PROTECTED_RETENTION","PLANTED_NULL_HIDDEN","UNTOUCHED_FORWARD","RELEASE_HOLDOUT"}
        if set(roles)!=required or any(roles[r]!=1 for r in required): raise EvidencePlanError("exactly one partition per required role is required")
        expected=_hash(self.core())
        if self.plan_hash and self.plan_hash!=expected: raise EvidencePlanError("plan hash mismatch")
        return self

def make_plan(**kwargs:Any)->EvidencePlan:
    p=EvidencePlan(**kwargs); p.validate()
    return EvidencePlan(**{**asdict(p),"partitions":p.partitions,"plan_hash":_hash(p.core())}).validate()

def validate_receipt_bundle(plan:EvidencePlan, receipts:Sequence[Mapping[str,Any]])->dict[str,Any]:
    plan.validate()
    if len(receipts)!=len(RECEIPTS): raise EvidencePlanError("exactly six receipts required")
    seen=set()
    for r in receipts:
        kind=_id(r.get("receipt_type"),"receipt_type")
        if kind not in RECEIPTS or kind in seen: raise EvidencePlanError("missing/duplicate/unknown receipt type")
        seen.add(kind)
        if r.get("plan_hash")!=plan.plan_hash: raise EvidencePlanError(f"{kind} plan hash mismatch")
        for f in ("candidate_sha256","baseline_sha256","runner_sha256","evaluator_sha256"):
            if r.get(f)!=getattr(plan,f): raise EvidencePlanError(f"{kind} {f} mismatch")
        if r.get("executed") is not True or r.get("gate_passed") is not True:
            raise EvidencePlanError(f"{kind} is not real passing executed evidence")
        _sha(r.get("source_validator_receipt_sha256"),"source_validator_receipt_sha256")
    return {"status":"COMPLETE_REAL_EVIDENCE_BUNDLE","plan_hash":plan.plan_hash,"receipt_types":sorted(seen)}
