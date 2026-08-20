#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

CORE_DEFAULT = "research/generated/ng_exhaustion_d0_d5_full_causal_v3_20260819/NG_EXHAUSTION_D0_D5_FULL_CAUSAL_V3_ALL_RESULTS_20260819.json"
FOUND_DEFAULT = "research/generated/ng_exhaustion_v3_foundation_trade_20260819/NG_EXHAUSTION_V3_FOUNDATION_TRADE_ALL_RESULTS_20260819.json"
TRADE_DEFAULT = "research/generated/ng_exhaustion_d0_d3_model_specific_trade_v3_20260819/NG_EXHAUSTION_D0_D3_MODEL_SPECIFIC_TRADE_ALL_RESULTS_20260819.json"
CORE_DIR = "research/generated/ng_exhaustion_d0_d5_full_causal_v3_20260819"
OUT_DEFAULT = "research/generated/ng_exhaustion_v3_final_synthesis_20260819"
PROTECTED = {
    "detector": False, "canonical_rows": False, "phase1": False, "phase2": False,
    "runway_clock": False, "permanent_frankie": False, "frankie_1": False,
    "spawn_py": False, "ssos_play": False,
}


def load(path: str):
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"required synthesis input missing: {path}")
    return json.loads(p.read_text())


def validate_inputs(core, foundation, trade):
    assert core["status"] == "NG_EXHAUSTION_D0_D5_FULL_CAUSAL_V3_RECONCILED"
    assert core["authority"].startswith("AUTHORITATIVE_RECOVERY_PASS")
    assert core["target_polarity_is_primary_question"] is False
    assert core["same_flip_role"] == "SECONDARY_ANNOTATION_CONTEXT_ONLY"
    assert core["model_voting_used"] is False
    assert foundation["status"] == "NG_EXHAUSTION_V3_FOUNDATION_TRADE_RECONCILED"
    assert foundation["model_voting_used"] is False
    assert foundation["model_probability_aggregation_used"] is False
    assert trade["status"] == "NG_EXHAUSTION_D0_D3_MODEL_SPECIFIC_TRADE_V3_RECONCILED"
    assert trade["model_voting_used"] is False
    assert trade["model_probability_aggregation_used"] is False
    assert trade["target_polarity_direction_source_used"] is False
    assert trade["future_canonical_event_exit_cap_used"] is False
    assert not any(core["protected_mutations"].values())
    assert not any(foundation["protected_mutations"].values())
    assert not any(trade["protected_mutations"].values())


def timing_text(e):
    if e is None:
        return "UNRESOLVED_EARLY_BAND"
    if "root_age_seconds_after_confirmation" in e:
        return f"ROOT_AGE_{int(e['root_age_seconds_after_confirmation'])}S"
    if e.get("timing_class") == "PRIOR_BEFORE_BIRTH":
        return f"PRIOR_AGE_{int(e['prior_age_seconds'])}S"
    if "H_seconds_after_t0" in e:
        return f"H_PLUS_{int(e['H_seconds_after_t0'])}S"
    return str(e)


def core_agent_docs():
    paths = sorted(glob.glob(f"{CORE_DIR}/NG_EXHAUSTION_D*_V3_*_20260819.json"))
    docs = []
    for p in paths:
        try:
            d = json.loads(Path(p).read_text())
        except Exception:
            continue
        if d.get("status") in (
            "NG_D0_FULL_CAUSAL_RECOVERY_V3_MODEL_AGENT_COMPLETE",
            "NG_CHAIN_BIRTH_DEPTH_TYPE_MODEL_AGENT_V3_COMPLETE",
        ):
            docs.append(d)
    return docs


def ablation_evidence(docs):
    rows = []
    for d in docs:
        stage = 0 if d["status"].startswith("NG_D0_") else int(d["stage"])
        model = d["model"]
        for target, rec in d["results"].items():
            for p in rec.get("tested", []):
                views = p.get("views", {})
                if not all(k in views for k in ("FULL_CAUSAL", "NO_PRICE_CAUSAL", "PRICE_POLARITY_ONLY")):
                    continue
                full = views["FULL_CAUSAL"]
                nop = views["NO_PRICE_CAUSAL"]
                price = views["PRICE_POLARITY_ONLY"]
                row = {
                    "stage": stage, "model": model, "target": target,
                    "phase": p["phase"],
                    "seconds": p.get("root_age_seconds_after_confirmation", p.get("prior_age_seconds", p.get("H_seconds_after_t0", p.get("seconds")))),
                    "full_validated": bool(full.get("independently_validated", False)),
                    "no_price_validated": bool(nop.get("independently_validated", False)),
                    "price_only_validated": bool(price.get("independently_validated", False)),
                    "blocks": {},
                }
                for b in ("validation", "confirmation", "held"):
                    f = full.get("blocks", {}).get(b, {})
                    n = nop.get("blocks", {}).get(b, {})
                    q = price.get("blocks", {}).get(b, {})
                    if f.get("n") and n.get("n") and q.get("n"):
                        row["blocks"][b] = {
                            "n": int(f["n"]),
                            "price_increment_log_loss": float(n["log_loss"] - f["log_loss"]),
                            "price_increment_brier": float(n["brier"] - f["brier"]),
                            "structure_micro_increment_log_loss_vs_price": float(q["log_loss"] - f["log_loss"]),
                            "structure_micro_increment_brier_vs_price": float(q["brier"] - f["brier"]),
                        }
                rows.append(row)
    return rows


def summarize_ablations(rows):
    return {
        "tested_points": len(rows),
        "full_validated_points": sum(r["full_validated"] for r in rows),
        "full_only_vs_no_price": sum(r["full_validated"] and not r["no_price_validated"] for r in rows),
        "full_only_vs_price_only": sum(r["full_validated"] and not r["price_only_validated"] for r in rows),
        "no_price_also_validated": sum(r["full_validated"] and r["no_price_validated"] for r in rows),
        "price_only_also_validated": sum(r["full_validated"] and r["price_only_validated"] for r in rows),
    }


def build_brain_proposal(core, foundation, trade, ablation_summary):
    valid = [r for r in core["independent_model_findings"] if r.get("earliest") is not None]
    unresolved = [r for r in core["independent_model_findings"] if r.get("earliest") is None]
    root_valid = foundation.get("root_increment_independently_validated_points", [])
    trade_valid = trade.get("historically_validated_candidates", [])
    return {
        "name": "NG exhaustion chain V3 full-causal proposal",
        "date": "2026-08-19",
        "status": "PROPOSAL_ONLY_NO_PERMANENT_BRAIN_MUTATION",
        "methodology_supersession": {
            "historical_chain_birth_v2_proposal_retained": True,
            "superseded_for_active_recovery": [
                "pre_birth_H_naming",
                "global_characteristics_wall",
                "2_of_3_model_gate",
                "transition_inclusive_primary_type_target",
                "future_event_capped_trade_exit",
            ],
        },
        "proposal_lessons": [
            {
                "id": "exhaustion.chain.full_causal_market_movie",
                "lesson": "Observe the continuously evolving causal price, roll20/dipole, signed flow and book state at every checkpoint. Unknown future target polarity never suppresses the live market movie.",
                "status": "METHOD_PROPOSAL",
            },
            {
                "id": "exhaustion.chain.separate_targets",
                "lesson": "Treat chain existence/continuation, eventual depth and P/O/S/X structural family as separate prediction questions with independently recorded earliest causal times.",
                "status": "METHOD_PROPOSAL",
            },
            {
                "id": "exhaustion.chain.clock_separation",
                "lesson": "D0 uses ROOT_AGE. D1-D5 use PRIOR strictly before target t0 and H only after frozen t0 for questions unresolved in PRIOR. Do not call pre-birth age H.",
                "status": "METHOD_PROPOSAL",
            },
            {
                "id": "exhaustion.chain.independent_models",
                "lesson": "Preserve Logistic, ExtraTrees and KNN as independent evidence lanes. Do not require a 2-of-3 vote or aggregate probabilities to decide whether an independent OOT finding exists.",
                "status": "METHOD_PROPOSAL",
            },
            {
                "id": "exhaustion.chain.modular_grammar_boundary",
                "lesson": "Carry Phase-2 modular P/O/S/X recurrence, extension winners and losers, timing families and true/false decompositions as structural context. Recurrence alone is not a trade authorization.",
                "status": "HISTORICAL_BOUNDARY_PROPOSAL",
            },
            {
                "id": "exhaustion.chain.root_memory",
                "lesson": "Retain root information through deeper D stages whenever it is causally available; use matched root ablation to quantify whether the root still adds incremental predictive value rather than discarding ancestry by construction.",
                "status": "EVIDENCE_BACKED_PROPOSAL" if root_valid else "RESEARCH_METHOD_PROPOSAL",
                "validated_root_increment_points": len(root_valid),
            },
            {
                "id": "exhaustion.chain.trade_execution",
                "lesson": "Trade research begins at each independently validated causal signal. Direction comes only from causally observed predecessor/live market state and exits use fixed discovery-selected horizons; realized target polarity and future canonical events are forbidden execution inputs.",
                "status": "EVIDENCE_BACKED_PROPOSAL" if trade_valid else "RESEARCH_METHOD_PROPOSAL",
                "historically_validated_trade_candidates": len(trade_valid),
            },
            {
                "id": "exhaustion.chain.event_mark_uncertainty",
                "lesson": "Raw market state is continuously observable, but event-specific polarity/family labels enter only when the upstream detector actually marks the event. Post-birth H live execution remains unresolved until that mark clock is proven.",
                "status": "OPEN_INFRASTRUCTURE_BOUNDARY",
            },
            {
                "id": "exhaustion.chain.sparse_depth_boundary",
                "lesson": "Keep D4/D5 as case studies at current support; do not force a universal deep-chain law.",
                "status": "FROZEN_SUPPORT_BOUNDARY",
            },
        ],
        "empirical_summary": {
            "independently_resolved_model_target_pairs": len(valid),
            "unresolved_early_band_model_target_pairs": len(unresolved),
            "validated_root_increment_points": len(root_valid),
            "historically_validated_fixed_horizon_trade_candidates": len(trade_valid),
            "ablation_summary": ablation_summary,
        },
        "promotion_boundary": {
            "permanent_frankie_mutation": False,
            "frankie_1_mutation": False,
            "detector_mutation": False,
            "canonical_row_mutation": False,
            "phase1_mutation": False,
            "phase2_mutation": False,
            "runway_clock_mutation": False,
            "spawn_py_mutation": False,
            "play_freeze": False,
            "requirement": "Deliberate later adjudication and any required fresh prospective/OOT contract.",
        },
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
    }


def build_trade_proposal(trade):
    rows = trade["independent_trade_results"]
    return {
        "name": "NG exhaustion D0-D3 V3 fixed-horizon trade proposal",
        "date": "2026-08-19",
        "status": "HISTORICAL_RESEARCH_PROPOSAL_ONLY",
        "authoritative_execution_contract": "FIXED_HORIZON_NO_FUTURE_EVENT_CAP_NO_REALIZED_TARGET_POLARITY",
        "independent_results": rows,
        "historically_validated_candidates": trade.get("historically_validated_candidates", []),
        "live_candidate_subset": [r for r in trade.get("historically_validated_candidates", []) if r.get("signal_phase") == "PRIOR"],
        "post_birth_historical_only_subset": [r for r in trade.get("historically_validated_candidates", []) if r.get("signal_phase") == "POST_BIRTH"],
        "promotion_performed": False,
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", default=CORE_DEFAULT)
    ap.add_argument("--foundation", default=FOUND_DEFAULT)
    ap.add_argument("--trade", default=TRADE_DEFAULT)
    ap.add_argument("--out-dir", default=OUT_DEFAULT)
    a = ap.parse_args()

    core = load(a.core); foundation = load(a.foundation); trade = load(a.trade)
    validate_inputs(core, foundation, trade)
    docs = core_agent_docs()
    if len(docs) != 12:
        raise SystemExit(f"expected 12 modeled D0-D3 V3 core agent docs for ablation synthesis, got {len(docs)}")
    ablations = ablation_evidence(docs)
    ab_summary = summarize_ablations(ablations)

    findings = []
    unresolved = []
    for r in core["independent_model_findings"]:
        z = {
            "stage": int(r["stage"]), "model": r["model"], "target": r["target"],
            "earliest": r.get("earliest"), "timing": timing_text(r.get("earliest")),
        }
        findings.append(z)
        if r.get("earliest") is None:
            unresolved.append({
                **z,
                "next_search": "LATER_ROOT_AGE" if int(r["stage"]) == 0 else "LATER_PRIOR_FIRST_THEN_LATER_POST_BIRTH_H_ONLY_IF_PRIOR_STILL_FAILS",
            })

    out = {
        "status": "NG_EXHAUSTION_V3_FINAL_SYNTHESIS_COMPLETE",
        "date": "2026-08-19",
        "authority": "FINAL_SYNTHESIS_OF_FINALIZED_DENSE_LIVE_V3_RECOVERY_AND_FIXED_HORIZON_TRADE_RESEARCH",
        "independent_model_findings": findings,
        "unresolved_queue": unresolved,
        "D4_D5_case_studies": core["D4_D5_case_studies"],
        "D0_D1_complement_calibration": foundation.get("complement_points", []),
        "root_increment_independently_validated_points": foundation.get("root_increment_independently_validated_points", []),
        "root_increment_nonvalidated_or_mixed_points": foundation.get("root_increment_nonvalidated_or_mixed_points", []),
        "ablation_summary": ab_summary,
        "ablation_points": ablations,
        "authoritative_trade_results": trade["independent_trade_results"],
        "historically_validated_trade_candidates": trade.get("historically_validated_candidates", []),
        "ignored_trade_evidence": "FOUNDATION_RECONCILIATION_INDEPENDENT_D0_TRADE_RESULTS_IGNORED_BECAUSE_OLD_PROTOTYPE_USED_FUTURE_NEXT_EVENT_CAP",
        "phase2_preservation": {
            "modular_recurrence": True,
            "extension_winners_and_losers": True,
            "timing_families": True,
            "true_false_context_decomposition": True,
            "pox_reset_reentry_doctrine_unchanged": True,
            "new_phase2_play_promoted": False,
        },
        "target_polarity_is_primary_question": False,
        "same_flip_role": "SECONDARY_CONTEXT_ONLY",
        "model_voting_used": False,
        "promotion_performed": False,
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
        "protected_mutations": dict(PROTECTED),
    }

    brain = build_brain_proposal(core, foundation, trade, ab_summary)
    strategy = build_trade_proposal(trade)
    outdir = Path(a.out_dir); outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "NG_EXHAUSTION_V3_FINAL_ALL_RESULTS_20260819.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    (outdir / "NG_EXHAUSTION_V3_UNRESOLVED_QUEUE_20260819.json").write_text(json.dumps({"status":"UNRESOLVED_QUEUE","rows":unresolved,"promotion_performed":False}, indent=2, sort_keys=True) + "\n")
    (outdir / "NG_EXHAUSTION_V3_BRAIN_PROPOSAL_20260819.json").write_text(json.dumps(brain, indent=2, sort_keys=True) + "\n")
    (outdir / "NG_EXHAUSTION_V3_TRADE_STRATEGY_PROPOSAL_20260819.json").write_text(json.dumps(strategy, indent=2, sort_keys=True) + "\n")

    lines = [
        "# NG Exhaustion V3 Final Synthesis — 2026-08-19", "",
        "Status: **proposal-only synthesis of finalized dense-live V3 recovery and corrected fixed-horizon trade research.**", "",
        "Target polarity is not a primary prediction target. The model observes raw market direction/flow/book continuously; P/O/S/X is the primary structural-family target.", "",
        "## Independent earliest causal findings", "",
    ]
    for r in findings:
        lines.append(f"- D{r['stage']} / {r['model']} / {r['target']}: {r['timing']}.")
    lines += ["", "## Foundation", "",
              f"- Matched D0/D1 complement calibration points: {len(foundation.get('complement_points', []))}.",
              f"- Independently validated D2/D3 root-increment checkpoints: {len(foundation.get('root_increment_independently_validated_points', []))}.",
              f"- Preserved nonvalidated/mixed root checkpoints: {len(foundation.get('root_increment_nonvalidated_or_mixed_points', []))}.",
              "", "## Information ablations", "",
              f"- Modeled V3 ablation checkpoints examined: {ab_summary['tested_points']}.",
              f"- FULL_CAUSAL independently validated checkpoints: {ab_summary['full_validated_points']}.",
              f"- FULL_CAUSAL-valid / no-price-not-valid checkpoints: {ab_summary['full_only_vs_no_price']}.",
              f"- FULL_CAUSAL-valid / price-only-not-valid checkpoints: {ab_summary['full_only_vs_price_only']}.",
              "", "## Corrected fixed-horizon trade research", ""]
    for r in trade["independent_trade_results"]:
        lines.append(f"- D{r['stage']} / {r['model']}: {r['status']}; {r.get('signal_phase')} {r.get('signal_seconds')}s; validated={r['historically_validated_candidate']}.")
    lines += ["", "## Phase-2 preservation", "",
              "- Pair/triplet modular recurrence remains structural evidence, not automatic trade authorization.",
              "- Stable extension patterns, below-baseline patterns and regime flips all remain preserved.",
              "- D2/D3 timing families remain a separate chain axis; D4/D5 stay sparse case studies.",
              "- True/false cases remain subject to deeper ancestry/timing/regime decomposition rather than deletion.",
              "- Existing P-O-X reset/re-entry doctrine and frozen SSOS play remain unchanged.",
              "", "## Unresolved queue", ""]
    for r in unresolved:
        lines.append(f"- D{r['stage']} / {r['model']} / {r['target']}: {r['next_search']}.")
    lines += ["", "## Promotion boundary", "",
              "- No permanent Frankie/Frankie 1 merge was performed.",
              "- No detector, canonical row, Phase 1/2, runway clock, `spawn.py`, or SSOS mutation was performed.",
              "- Historical validation is not live promotion. Any permanent merge/play requires later deliberate adjudication.",
              "- `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains in force.", ""]
    (outdir / "NG_EXHAUSTION_V3_FINAL_ALL_FINDINGS_20260819.md").write_text("\n".join(lines))
    print(json.dumps({
        "status": out["status"],
        "resolved": sum(r["earliest"] is not None for r in findings),
        "unresolved": len(unresolved),
        "validated_root_increment_points": len(out["root_increment_independently_validated_points"]),
        "historically_validated_trade_candidates": len(out["historically_validated_trade_candidates"]),
    }, indent=2))


if __name__ == "__main__":
    main()
