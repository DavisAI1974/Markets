#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

SEED = 20260817
RNG = np.random.default_rng(SEED)


def sign_flip_pvalue(xs, nperm=20000):
    a = np.asarray([float(x) for x in xs if x is not None and np.isfinite(float(x))], float)
    if len(a) < 3:
        return None
    obs = float(a.mean())
    if obs <= 0:
        return 1.0
    hits = 1
    for _ in range(nperm):
        signs = RNG.choice((-1.0, 1.0), size=len(a))
        if float(np.mean(a * signs)) >= obs:
            hits += 1
    return hits / float(nperm + 1)


def fold_week_gains(structural, view, depth, model, include_confirmation=False):
    out = []
    folds = structural[view]["folds"]
    for name, f in folds.items():
        if name == "untouched_confirmation" and not include_confirmation:
            continue
        z = f["depth"].get(str(depth), {}).get(model, {})
        for w, g in z.get("per_week_gain_mean", {}).items():
            out.append((name, w, float(g)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("canonical_summary")
    ap.add_argument("continuity_summary")
    ap.add_argument("structural_summary")
    ap.add_argument("causal_summary")
    ap.add_argument("lineage_summary")
    ap.add_argument("agent7_summary")
    ap.add_argument("--out", default="NG_EXHAUSTION_CHAIN_PHASE1_FALSIFIER_54W_20260817.json")
    a = ap.parse_args()

    canonical = json.load(open(a.canonical_summary))
    continuity = json.load(open(a.continuity_summary))
    structural = json.load(open(a.structural_summary))
    causal = json.load(open(a.causal_summary))
    lineage = json.load(open(a.lineage_summary))
    agent7 = json.load(open(a.agent7_summary))

    hard_failures = []
    if continuity.get("status") != "PHASE1_54W_CONTINUITY_AUDIT_PASS":
        hard_failures.append("continuity audit did not pass")
    if canonical.get("status") != "CHAIN_CANONICAL_54W_BASE_FROZEN_PROVISIONAL":
        hard_failures.append("canonical base is not frozen provisional")
    if canonical.get("week_count") != 54 or "20260329" in canonical.get("weeks", []):
        hard_failures.append("54-week canonical coverage/exclusion invariant failed")
    eq = canonical.get("target_equivalence", {})
    if eq.get("frozen_events_recovered") != 3429 or eq.get("family_mismatches") != 0 or eq.get("blind_a_post_state_mismatches") != 0:
        hard_failures.append("pilot equivalence failed")
    if canonical.get("calendar_day_chain_reset") is not False:
        hard_failures.append("calendar-day reset leaked into canonical table")
    if structural.get("characteristics_accessed") is not False:
        hard_failures.append("Agent 3 accessed forbidden characteristics")
    if causal.get("characteristics_accessed") is not False:
        hard_failures.append("Agent 4 accessed forbidden characteristics")
    if agent7.get("independent_higher_order_discovery") is not True:
        hard_failures.append("Agent 7 did not run as independent higher-order discovery")
    if lineage.get("instance_specific_lifespan_preserved") is not True:
        hard_failures.append("Agent 5 did not preserve instance-specific lifespan")

    models = ("ridge", "extra_trees", "knn")
    structural_attacks = {}
    for depth in range(1, 13):
        d = {}
        for model in models:
            rows = fold_week_gains(structural, "primary_full_path", depth, model, include_confirmation=False)
            vals = [g for _, _, g in rows]
            eras = defaultdict(list)
            for f, _, g in rows:
                eras[f].append(g)
            era_means = {f: float(np.mean(v)) for f, v in eras.items()}
            loo = {}
            for drop in sorted(eras):
                keep = [g for f, _, g in rows if f != drop]
                loo[drop] = None if not keep else float(np.mean(keep))
            conf = structural["primary_full_path"]["folds"]["untouched_confirmation"]["depth"].get(str(depth), {}).get(model, {})
            d[model] = {
                "discovery_week_n": len(vals),
                "discovery_week_mean_gain": None if not vals else float(np.mean(vals)),
                "discovery_week_positive_rate": None if not vals else float(np.mean(np.asarray(vals) > 0)),
                "week_block_sign_flip_p_one_sided": sign_flip_pvalue(vals),
                "era_mean_gains": era_means,
                "leave_one_era_out_mean_gains": loo,
                "single_era_dependence_flag": bool(vals and any(v is not None and v <= 0 for v in loo.values())),
                "untouched_confirmation_gain_mean": conf.get("gain_mean"),
                "untouched_confirmation_positive": bool(conf.get("gain_mean") is not None and float(conf["gain_mean"]) > 0),
            }
        signs = [d[m]["discovery_week_mean_gain"] for m in models]
        d["model_family_dependence"] = {
            "positive_model_count": int(sum(x is not None and x > 0 for x in signs)),
            "all_models_positive": bool(all(x is not None and x > 0 for x in signs)),
        }
        structural_attacks[str(depth)] = d

    sparse_divergence = {}
    for depth in range(1, 7):
        sparse_divergence[str(depth)] = {}
        for model in models:
            full = fold_week_gains(structural, "primary_full_path", depth, model, include_confirmation=False)
            sparse = fold_week_gains(structural, "sparse_sensitivity", depth, model, include_confirmation=False)
            fm = None if not full else float(np.mean([x[2] for x in full]))
            sm = None if not sparse else float(np.mean([x[2] for x in sparse]))
            sparse_divergence[str(depth)][model] = {
                "full_mean_gain": fm,
                "sparse_mean_gain": sm,
                "sign_disagreement": bool(fm is not None and sm is not None and (fm > 0) != (sm > 0)),
            }

    causal_attacks = {}
    for h, hz in causal.get("by_information_horizon_seconds", {}).items():
        causal_attacks[h] = {}
        for d in range(1, 7):
            rec = {}
            for model in models:
                vals = []
                for fname, f in hz.items():
                    if fname == "untouched_confirmation":
                        continue
                    z = f["depth"].get(str(d), {}).get(model, {})
                    vals.extend(float(x) for x in z.get("per_week_gain_mean", {}).values())
                conf = hz.get("untouched_confirmation", {}).get("depth", {}).get(str(d), {}).get(model, {})
                rec[model] = {
                    "discovery_week_n": len(vals),
                    "discovery_week_mean_gain": None if not vals else float(np.mean(vals)),
                    "week_block_sign_flip_p_one_sided": sign_flip_pvalue(vals),
                    "untouched_confirmation_gain_mean": conf.get("gain_mean"),
                }
            causal_attacks[h][str(d)] = rec

    agent7_attacks = {}
    for fname, f in agent7.get("folds", {}).items():
        agent7_attacks[fname] = {}
        for d, z in f.get("depth", {}).items():
            selected = bool(z.get("selected_in_training"))
            gain = z.get("gain_mean")
            tree = z.get("extra_trees_crosscheck") or {}
            agent7_attacks[fname][d] = {
                "selected_in_training": selected,
                "outer_gain_mean": gain,
                "outer_positive_if_selected": None if not selected or gain is None else bool(float(gain) > 0),
                "extra_trees_gain_mean": tree.get("gain_mean"),
                "equation_tree_agreement": None if not selected or gain is None or tree.get("gain_mean") is None else bool((float(gain) > 0) == (float(tree["gain_mean"]) > 0)),
            }

    result = {
        "status": "PHASE1_FALSIFICATION_54W_HARD_FAIL" if hard_failures else "PHASE1_FALSIFICATION_54W_COMPLETE",
        "hard_failures": hard_failures,
        "structural_week_block_null_and_stability": structural_attacks,
        "sparse_omitted_state_sensitivity": sparse_divergence,
        "causal_week_block_null": causal_attacks,
        "agent7_selection_and_nonlinear_crosscheck": agent7_attacks,
        "lineage_status": lineage.get("status"),
        "notes": [
            "A positive pooled event score is never sufficient; week-block and era stability are reported explicitly.",
            "Agent 7 outer results are promotable only for depths selected inside training eras.",
            "The temporarily excluded 20260329 week remains unavailable to every 54-week falsification calculation and will later serve as an insert-only out-of-time repair fold.",
            "Phase 2 remains locked regardless of 54-week results."
        ],
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "hard_failure_count": len(hard_failures)}, indent=2))
    if hard_failures:
        raise SystemExit("Agent 6 hard invariant failure")


if __name__ == "__main__":
    main()
