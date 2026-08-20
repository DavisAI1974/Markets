#!/usr/bin/env python3
"""Recompute the nine V4 clean-source prelaunch gates from typed artifacts.

A PASS here means the isolated contracts are mechanically satisfied for the supplied
artifact bundle. It never authorizes empirical V4 dispatch, promotion, permanent Frankie
mutation, or substitutes for the six P0 real-evidence receipts.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,re
from typing import Any,Mapping,Sequence

from research.kalshi.ng_exhaustion_v4_causal_clock import CausalDiscoveryReceipt,validate_availability_chain
from research.kalshi.ng_exhaustion_v4_history_support import SessionCoverage
from research.kalshi.ng_exhaustion_v4_lock_outcome import recompute_lock_outcome
from research.kalshi.ng_exhaustion_v4_mechanics import ExecutionHandoff,FirstLock,PredecessorLifecycle,ProbabilityEntry,StateMovieRow,validate_execution_binding,validate_probability_movie,validate_state_movie

SCHEMA="NG_EXHAUSTION_V4_PRELAUNCH_GATE_RECEIPT_V1"
SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
class GateVerificationError(ValueError): pass

def _hash(x:Mapping[str,Any])->str:
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()

@dataclass(frozen=True)
class DetectorIntensityResolution:
    mode:str
    source_sha256:str|None=None
    proxy_namespace:str|None=None
    def validate(self):
        if self.mode=="OMITTED":
            if self.source_sha256 or self.proxy_namespace: raise GateVerificationError("OMITTED intensity carries no source/proxy")
        elif self.mode=="PROVEN_NATIVE":
            if not self.source_sha256 or not SHA256_RE.fullmatch(self.source_sha256) or self.proxy_namespace: raise GateVerificationError("PROVEN_NATIVE requires one valid source hash")
        elif self.mode=="EXPLICIT_PROXY":
            if not self.proxy_namespace or self.proxy_namespace in {"detector_native_intensity","native_exhaustion_intensity"}:
                raise GateVerificationError("proxy must be explicitly non-native")
        else: raise GateVerificationError("unknown detector intensity resolution")
        return self

@dataclass(frozen=True)
class SparseStagePolicy:
    d4_case_count:int
    d5_case_count:int
    every_case_preserved:bool
    d4_d5_population_law_claimed:bool
    d0_d3_blocked_by_sparse_d4_d5:bool
    def validate(self):
        if self.d4_case_count<0 or self.d5_case_count<0: raise GateVerificationError("negative sparse counts")
        if not self.every_case_preserved: raise GateVerificationError("sparse cases must all be preserved")
        if self.d4_d5_population_law_claimed: raise GateVerificationError("D4/D5 population law forbidden while sparse")
        if self.d0_d3_blocked_by_sparse_d4_d5: raise GateVerificationError("D0-D3 cannot be blocked solely by sparse D4/D5")
        return self

def verify_prelaunch_gates(*,discovery:CausalDiscoveryReceipt,feature_available_at:float,model_evaluated_at:float,decision_available_at:float,state_rows:Sequence[StateMovieRow],lifecycles:Sequence[PredecessorLifecycle],coverage:Sequence[SessionCoverage],intensity:DetectorIntensityResolution,probability_entries:Sequence[ProbabilityEntry],claimed_first_lock:FirstLock,lock_threshold:float,lock_persistence:int,lock_policy_sha256:str,handoff:ExecutionHandoff,sparse_policy:SparseStagePolicy)->dict[str,Any]:
    gates={}
    discovery.validate(); validate_availability_chain(discovery,feature_available_at=feature_available_at,model_evaluated_at=model_evaluated_at,decision_available_at=decision_available_at)
    gates["1_causal_exhaustion_discovery_clock"]=True
    movie_hash=validate_state_movie(state_rows)
    if any(r.event_known_by!=discovery.event_known_by for r in state_rows): raise GateVerificationError("state movie event_known_by drift")
    gates["2_field_and_channel_multi_clock_provenance"]=True
    if not coverage: raise GateVerificationError("coverage manifest required")
    for c in coverage: c.validate()
    gates["3_exact_source_contract_roll_coverage"]=True
    gates["4_missingness_safe_immutable_causal_state_movie"]=True
    if not lifecycles: raise GateVerificationError("predecessor lifecycle evidence required")
    for l in lifecycles: l.validate()
    gates["5_unresolved_predecessor_lifecycle"]=True
    intensity.validate(); gates["6_detector_intensity_semantic_resolution"]=True
    prob_hash=validate_probability_movie(probability_entries)
    recomputed=recompute_lock_outcome(probability_entries,threshold=lock_threshold,persistence=lock_persistence,lock_policy_sha256=lock_policy_sha256)
    if recomputed.lock_hash!=claimed_first_lock.lock_hash: raise GateVerificationError("claimed first lock does not recompute")
    gates["7_immutable_probability_first_lock_ledger"]=True
    bound=next((e for e in probability_entries if e.entry_hash==claimed_first_lock.entry_hash),None)
    if bound is None: raise GateVerificationError("lock/no-lock outcome is not bound to a probability entry")
    validate_execution_binding(handoff,probability_entry=bound,first_lock=claimed_first_lock,state_movie_hash=movie_hash)
    gates["8_sealed_prediction_to_execution_handoff"]=True
    sparse_policy.validate(); gates["9_sparse_stage_scope_preservation"]=True
    core={"schema":SCHEMA,"gates":gates,"state_movie_hash":movie_hash,"probability_movie_hash":prob_hash,"first_lock_hash":claimed_first_lock.lock_hash,"execution_handoff_hash":handoff.handoff_hash,"intensity_mode":intensity.mode,"mechanical_prelaunch_contracts_pass":all(gates.values()),"trusted_v4_empirical_launch_authorized":False,"promotion_authorized":False,"p0_six_real_receipts_satisfied_by_this_receipt":False}
    return {**core,"receipt_hash":_hash(core)}
