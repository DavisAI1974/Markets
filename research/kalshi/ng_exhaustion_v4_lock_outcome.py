#!/usr/bin/env python3
"""Complete lock-outcome recomputation for the isolated V4 ledger.

Extends the provisional lock helper by ensuring NO_RELIABLE_LOCK is also bound to
the exact final probability entry and decision time, so abstention uses the same
sealed handoff path instead of a second execution path.
"""
from __future__ import annotations
from research.kalshi.ng_exhaustion_v4_mechanics import FirstLock,ProbabilityEntry,V4ContractError,_prob,_sha,stable_hash,validate_probability_movie


def recompute_lock_outcome(entries:list[ProbabilityEntry] | tuple[ProbabilityEntry,...], *, threshold:float,
                           persistence:int, lock_policy_sha256:str)->FirstLock:
    validate_probability_movie(entries)
    t=_prob(threshold,"threshold")
    if persistence<1: raise V4ContractError("persistence must be >=1")
    policy=_sha(lock_policy_sha256,"lock_policy_sha256")
    streak_class=None; streak=[]
    for e in entries:
        best=max(range(len(e.probabilities)),key=lambda i:e.probabilities[i])
        if e.probabilities[best] < t:
            streak_class=None; streak=[]; continue
        if streak_class==best: streak.append(e)
        else: streak_class=best; streak=[e]
        if len(streak)>=persistence:
            evidence=tuple(x.entry_hash for x in streak[-persistence:])
            core={"status":"LOCKED","entry_hash":e.entry_hash,"lock_decided_at":e.causal_evaluation_at,
                  "decision_available_at":e.decision_available_at,"class_index":best,
                  "evidence_entry_hashes":list(evidence),"lock_policy_sha256":policy}
            return FirstLock(**{**core,"evidence_entry_hashes":evidence},lock_hash=stable_hash(core))
    last=entries[-1]
    evidence=(last.entry_hash,)
    core={"status":"NO_RELIABLE_LOCK","entry_hash":last.entry_hash,"lock_decided_at":last.causal_evaluation_at,
          "decision_available_at":last.decision_available_at,"class_index":None,
          "evidence_entry_hashes":list(evidence),"lock_policy_sha256":policy}
    return FirstLock(**{**core,"evidence_entry_hashes":evidence},lock_hash=stable_hash(core))
