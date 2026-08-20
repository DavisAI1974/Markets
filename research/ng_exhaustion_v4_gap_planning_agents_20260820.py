#!/usr/bin/env python3
"""Planning-only parallel lanes for remaining Frankie NG Exhaustion V4 gates.

These lanes may declare BUILD_READY, but they never launch V4, promote a candidate,
mutate permanent Frankie, or modify frozen detector/canonical/runway artifacts.

Trigger revision: user authorized BUILD_READY lanes to continue into isolated builds.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROTECTED = {
    "frozen_detector": False,
    "frozen_canonical_evidence": False,
    "frozen_runway_clock": False,
    "permanent_frankie": False,
    "frankie_1": False,
    "spawn_py": False,
}

def hits(tokens, limit=24):
    out=[]
    toks=[t.lower() for t in tokens]
    for p in ROOT.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in {'.py','.md','.json','.yml','.yaml'}: continue
        rel=str(p.relative_to(ROOT)).replace('\\','/')
        try: text=p.read_text(encoding='utf-8',errors='ignore').lower()
        except OSError: continue
        score=sum(t in rel.lower() or t in text for t in toks)
        if score: out.append((score,rel))
    return [r for _,r in sorted(out,key=lambda x:(-x[0],x[1]))[:limit]]

def common(mode):
    return {
        "status":"PLANNING_AGENT_COMPLETE",
        "mode":mode,
        "planning_only":True,
        "v4_empirical_launch":False,
        "promotion_performed":False,
        "protected_mutations":dict(PROTECTED),
        "authority_files":[
            "research/NG_EXHAUSTION_V4_CLEAN_SOURCE_PRELAUNCH_GATES_20260820.md",
            "research/NG_EXHAUSTION_V4_CLEAN_SOURCE_DEEP_DIVE_GAP_MATRIX_20260820.json",
            "research/NG_EXHAUSTION_V4_REMAINING_GAP_PARALLEL_RESEARCH_20260820.md",
            "research/kalshi/FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md",
            "research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md",
        ],
    }

def plan(mode):
    d=common(mode)
    if mode=='causal_clock':
        d.update({
            "build_ready":True,
            "objective":"Close detector_marked_at/event_known_by without rewriting the frozen detector.",
            "candidate_files":hits(['mark_event','event_known_by','detector_marked_at','ng_exhaustion_live_clock','t0_second']),
            "implementation_steps":[
                "Add an isolated V4 causal-discovery receipt with source hashes, ts_event, ts_recv/observed_at, detector_marked_at, event_known_by, detector revision, and retrospective canonical_t0 kept separate.",
                "Support prospective mark capture and receive-ordered causal replay behind the same receipt validator.",
                "Make the new V4 adapter fail closed when event_known_by is absent; do not alter the frozen runway path.",
                "Enforce event_known_by <= feature_available_at <= model_evaluated_at <= decision_available_at.",
            ],
            "tests":["no retrospective-t0 backdating","receive-order governs availability","deterministic receipt hash","future-row deletion leaves mark unchanged","frozen runway behavior invariant"],
            "done_when":"Every V4 event can carry a source-hashed causal discovery receipt and tests make t0 substitution impossible.",
        })
    elif mode=='v4_mechanics':
        d.update({
            "build_ready":True,
            "objective":"Implement isolated unified-V4 contracts for clocks, missingness, lifecycle, ledger, lock, handoff and reconciliation.",
            "candidate_files":hits(['first_lock','reconciler','missingness','snapshot','execution_handoff','reveal_timestamp','probability']),
            "implementation_steps":[
                "Create one immutable V4LaneSpec registry and adapter contract.",
                "Create causal state movie schema with OBSERVED/PAST_CARRY/STALE/MISSING/STRUCTURALLY_NOT_YET_KNOWN/NOT_APPLICABLE/true-zero semantics and availability clocks.",
                "Create prospective UNRESOLVED/RESOLVED/CENSORED predecessor lifecycle and ordered known-ancestry representation.",
                "Create append-only probability movie and independently recomputable first-lock/no-lock/no-reliable-lock ledger.",
                "Create sealed signal_id/execution_handoff_id contract that execution cannot rebuild or retime.",
                "Create registry-driven reconciler/tamper-test contract; D4/D5 use same engine contract in CASE_STUDY_NO_ADAPTATION.",
            ],
            "tests":["causal-window","snapshot freeze","learn-after-reveal","no-mid-instance-update","reveal embargo","first-lock recomputation","tamper detection","roll v/n/c identity fail-closed"],
            "done_when":"Mechanical contracts and adversarial tests are green in isolated V4 modules without launching a run.",
        })
    elif mode=='p0_evidence':
        d.update({
            "build_ready":False,
            "objective":"Turn six P0 readiness receipts into an executable evidence package without consuming release holdout during development.",
            "candidate_files":hits(['evaluate_p0_readiness','calibration','planted_null','retention_matrix','judge_independence','rollback','paired_repeated_seed']),
            "implementation_steps":[
                "Predeclare development/support, calibration-fit, protected-retention, planted-null-parent, and untouched-forward/release-holdout manifests before candidate development touches new chronology.",
                "Bind one immutable evaluation-plan hash across candidate, baseline, runner, evaluator, partitions, budgets, seeds, controls, policies and six validators.",
                "Execute held-out paired performance, calibration/selective risk, planted-null contamination, protected retention, evaluator-independence and byte-exact rollback only when real backends/evaluator/sandbox authority exist.",
            ],
            "external_dependencies":["real callback/model/tool backends with metering authority","independent locked evaluator and canaries","disposable mutation/rollback target with explicit authority"],
            "done_when":"All six real executed receipts share exact plan/candidate/baseline/runner/evaluator hashes and pass registry validation.",
        })
    elif mode=='history_support':
        d.update({
            "build_ready":True,
            "objective":"Integrate five-year native MBO archive as provenance-certified outside chronology and measure D3-D5 support under unchanged detector rules.",
            "candidate_files":hits(['full_history','phase1','lineage','coverage','mbo','manifest','continuous']),
            "implementation_steps":[
                "Verify S3 DBN hashes/manifests and build exact per-session MBO/MBP/L1 coverage manifest.",
                "Resolve continuous symbol to instrument/raw contract/effective interval and preserve v/n/c distinction.",
                "Run unchanged frozen detector/canonical rules on outside chronology in a separate additive corpus; never overwrite the frozen 55-week population.",
                "Preserve every generated true/false/losing/censored/low-support case and report D0-D5 counts plus chronology independence.",
                "Reserve untouched future chronology for forward evidence; backfill is support expansion, not virgin release holdout.",
            ],
            "tests":["native DBN hash verification","coverage no-overclaim","roll identity","unchanged detector hash","no frozen-row mutation","all cases retained"],
            "done_when":"Outside-history case ledger and coverage/provenance manifests are reproducible and D3-D5 support is measured without detector changes.",
        })
    elif mode=='integration_redteam':
        d.update({
            "build_ready":True,
            "objective":"Reconcile all plans into dependency order and block any build that weakens a gate or duplicates the engine.",
            "candidate_files":hits(['prelaunch gates','unified framework','gap matrix','registry','reconciler']),
            "implementation_steps":[
                "Dependency order: source/coverage + causal discovery receipt -> causal state/lifecycle -> probability/lock ledger -> sealed execution handoff -> unified reconciler -> empirical evidence package.",
                "Require one registry/engine/reconciler; reject alternate D4/D5 execution path or silent v/n/c normalization.",
                "Require every claimed boolean causal property to be recomputable from artifacts rather than asserted.",
                "Do not mark P0 evidence BUILD_READY until external evaluator/backends/rollback authority exist.",
            ],
            "done_when":"Reconciled plan has no circular dependencies, no protected mutation, no gate weakening, and a mechanically testable build order.",
        })
    else: raise SystemExit(mode)
    return d

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mode',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    d=plan(a.mode); Path(a.out).write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(d,indent=2,sort_keys=True))
if __name__=='__main__': main()
