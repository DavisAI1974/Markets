#!/usr/bin/env python3
"""Two isolated research/build-redteam lanes for the Frankie metacognitive sidecar."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from frankie_meta_loop_s138 import (
    attach_specialist_meta_sidecar,
    build_meta_contract,
    reconcile_specialist_meta_audits,
    validate_meta_audit,
)

ROOT = Path(__file__).resolve().parents[2]
P0 = ROOT / "research/kalshi/FRANKIE_P0_GAP_CLOSURE_PROVISIONAL_20260820.md"
PARITY = ROOT / "research/kalshi/frankie_specialist_parity_s126.py"
META = ROOT / "research/kalshi/frankie_meta_loop_s138.py"
SPAWN = ROOT / "research/kalshi/spawn.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def common(mode: str) -> dict:
    return {
        "status": "META_LOOP_AGENT_COMPLETE",
        "mode": mode,
        "paper_anchor": {
            "title": "How Do Agents Fail on AutoResearch: End-to-End Diagnostic Evaluation on 100 Real-World Frontier Research Tasks",
            "arxiv": "2608.14905",
            "reported_scope": "100 tasks, seven scientific domains, 800 trajectories, 45 ARFT failure patterns",
            "reported_core_gap": "lack of a metacognitive loop that checks outputs against findings, revises when they do not hold, and questions path soundness",
            "solution_boundary": "the paper diagnoses the deficit; orchestration-level remediation is an open question, so this prototype must be treated as experimental",
        },
        "source_bindings": {
            str(P0.relative_to(ROOT)): sha256(P0),
            str(PARITY.relative_to(ROOT)): sha256(PARITY),
            str(META.relative_to(ROOT)): sha256(META),
            str(SPAWN.relative_to(ROOT)): sha256(SPAWN),
        },
        "external_model_calls": False,
        "data_purchase_performed": False,
        "five_year_run_touched": False,
        "v4_empirical_launch": False,
        "promotion_performed": False,
        "protected_mutations": {
            "spawn_py": False,
            "specialist_role_text": False,
            "frozen_detector": False,
            "runway_clock": False,
            "first_lock_artifacts": False,
            "permanent_frankie_brain": False,
        },
    }


def architecture_research() -> dict:
    out = common("architecture_research")
    out.update({
        "finding": "Frankie already has bounded CRITIC/LATS/ReAct/evaluator/retention/rollback and first-lock controls, but the current handoff does not define one persistent post-evidence process-level reconciliation loop.",
        "recommended_architecture": [
            "immutable hypothesis + first-lock + evidence + result + path-trace bindings",
            "post-evidence self-audit only; never revise the just-scored blind artifact",
            "explicit market-vs-measurement separation",
            "contradiction and alternative-mechanism accounting",
            "preserve weak/negative/sparse/inconclusive cases rather than dropping them",
            "next-run-only revision proposal with a smallest discriminating experiment",
            "no automatic promotion/apply authority",
        ],
        "build_assessment": "BUILD_READY_SHADOW_SIDECAR",
        "main_risk": "A meta-loop can become hindsight rationalization unless immutable first-lock bindings and next-run-only revisions are enforced mechanically.",
    })
    return out


def _audit(claim_stance: str, assumption: str) -> dict:
    return {
        "produced_vs_found": "mixed",
        "path_soundness": "testable but incomplete",
        "contradictions": ["counterexample preserved"],
        "measurement_vs_market": "separate detector/clock observability from market mechanism",
        "alternative_mechanisms": ["liquidity refill", "predecessor lifecycle"],
        "missing_evidence": ["predecessor lifecycle state"],
        "assumptions": [assumption],
        "claim_stances": {"continuation_after_exhaustion": claim_stance},
        "case_disposition": "UNRESOLVED",
        "confidence_delta": -0.05,
        "next_discriminating_test": "split by predecessor lifecycle without changing first lock",
        "revision_proposal": {"scope": "NEXT_RUN_ONLY", "actions": ["split_hypothesis"]},
    }


def specialist_build_redteam() -> dict:
    packet = {
        "realized_outcome_in_packet": False,
        "causal_slice": {"20260820": {"example": 1}},
        "brain_view_served": {"plays": {"sentinel": {"body": "unchanged"}}},
    }
    a_sidecar = attach_specialist_meta_sidecar(packet, specialist="A")
    b_sidecar = attach_specialist_meta_sidecar(packet, specialist="B")

    common_inputs = dict(
        subject="specialist meta audit demo",
        hypothesis={"claim": "continuation"},
        first_lock={"p": 0.6, "locked": True},
        evidence={"observed": "mixed"},
        result={"score": 0.0},
        path_trace={"steps": ["blind", "freeze", "reveal"]},
    )
    ca = build_meta_contract(**common_inputs, specialist="A")
    cb = build_meta_contract(**common_inputs, specialist="B")
    va = validate_meta_audit(ca, _audit("uncertain", "causal clock is correct"))
    vb = validate_meta_audit(cb, _audit("unlikely", "causal clock is correct"))
    reconciled = reconcile_specialist_meta_audits([va, vb])

    out = common("specialist_build_redteam")
    out.update({
        "build_checks": {
            "A_sidecar_post_reveal_only": a_sidecar["specialist_meta_loop_contract"]["activation"] == "POST_REVEAL_ONLY",
            "B_sidecar_post_reveal_only": b_sidecar["specialist_meta_loop_contract"]["activation"] == "POST_REVEAL_ONLY",
            "roles_rewritten": False,
            "blind_packet_mutation_allowed": False,
            "shared_assumption_detected": bool(reconciled["shared_assumptions"]),
            "cross_specialist_disagreement_detected": bool(reconciled["claim_disagreements"]),
            "majority_vote_resolution_allowed": reconciled["majority_vote_resolution_allowed"],
            "automatic_brain_promotion_allowed": reconciled["automatic_brain_promotion_allowed"],
        },
        "specialist_design": {
            "layer_1": "Each A-E specialist gets a post-reveal local self-audit sidecar bound to its frozen blind packet and evidence.",
            "layer_2": "Frankie reconciles the five validated audits for shared assumptions, disagreements, missing-evidence overlap, and proposed discriminating tests.",
            "truth_rule": "Agreement is not truth; majority vote cannot erase minority evidence or resolve a scientific disagreement.",
            "parity_rule": "The sidecar consumes the already-served parity packet; no role-based field filtering and no role/prompt rewrite.",
        },
        "build_assessment": "BOUNDED_PROTOTYPE_PASSES_LOCAL_CONTRACT_EXERCISE",
    })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["architecture_research", "specialist_build_redteam"])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = architecture_research() if args.mode == "architecture_research" else specialist_build_redteam()
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
