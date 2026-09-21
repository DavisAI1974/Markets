#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def load_events(path):
    byweek = defaultdict(dict)
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            byweek[r["week_sunday"]][int(r["sequence_index"])] = {
                "event_id": r["event_id"],
                "t0_idx": int(r["t0_idx"]),
            }
    return dict(byweek)


def load_gains(path):
    g = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            if r.get("view") != "full":
                continue
            fold = r["fold"]; week = r["week_sunday"]; model = r["model"]
            d = int(r["depth"]); t = int(r["sequence_index"])
            g[fold][week][model][(d, t)] = float(r["incremental_gain"])
    return g


def association(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 20:
        return {"n": len(pairs), "odds_ratio": None, "p_two_sided": None}
    aa = np.asarray([x > 0 for x, _ in pairs], bool)
    bb = np.asarray([y > 0 for _, y in pairs], bool)
    tab = np.asarray([
        [np.sum(~aa & ~bb), np.sum(~aa & bb)],
        [np.sum(aa & ~bb), np.sum(aa & bb)],
    ], int)
    odds, p = fisher_exact(tab)
    return {
        "n": int(len(pairs)),
        "table": tab.tolist(),
        "odds_ratio": float(odds),
        "p_two_sided": float(p),
        "first_positive_rate": float(np.mean(aa)),
        "second_positive_rate": float(np.mean(bb)),
        "joint_positive_rate": float(np.mean(aa & bb)),
        "independence_product_rate": float(np.mean(aa) * np.mean(bb)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("event_table")
    ap.add_argument("structural_gains")
    ap.add_argument("--agent7-summary")
    ap.add_argument("--base-freeze", default="research/NG_EXHAUSTION_CHAIN_PHASE1_54W_BASE_FREEZE_20260817.json")
    ap.add_argument("--out", default="NG_EXHAUSTION_CHAIN_PHASE1_LINEAGE_54W_20260817.json")
    a = ap.parse_args()

    freeze = json.load(open(a.base_freeze))
    events = load_events(a.event_table)
    if sorted(events) != freeze["base_weeks"] or len(events) != 54:
        raise SystemExit("Agent 5 canonical 54-week drift")
    gains = load_gains(a.structural_gains)
    models = ("ridge", "extra_trees", "knn")

    lineage = {}
    instance_rows = []
    survival_hist = Counter()
    elapsed_by_depth = defaultdict(list)

    for fold in sorted(gains):
        lineage[fold] = {}
        for week in sorted(gains[fold]):
            lineage[fold][week] = {}
            n = max(events[week]) + 1 if events[week] else 0
            for model in models:
                gm = gains[fold][week].get(model, {})
                assoc = {}
                for d in range(1, 12):
                    aa = []; bb = []
                    # Align gains to the same origin i: depth d targets i+d.
                    for i in range(0, n - (d + 1)):
                        aa.append(gm.get((d, i + d)))
                        bb.append(gm.get((d + 1, i + d + 1)))
                    assoc[f"D{d}_to_D{d+1}"] = association(aa, bb)
                lineage[fold][week][model] = assoc

            for i in range(n):
                rec = {
                    "fold": fold,
                    "week_sunday": week,
                    "origin_sequence_index": i,
                    "origin_event_id": events[week].get(i, {}).get("event_id"),
                    "model_positive_depths": {},
                }
                for model in models:
                    gm = gains[fold][week].get(model, {})
                    pos = []
                    consecutive = 0
                    for d in range(1, 13):
                        v = gm.get((d, i + d)) if i + d < n else None
                        if v is not None and v > 0:
                            pos.append(d)
                        if d == consecutive + 1 and v is not None and v > 0:
                            consecutive = d
                        elif d == consecutive + 1:
                            break
                    rec["model_positive_depths"][model] = pos
                    rec[f"{model}_consecutive_positive_depth"] = consecutive

                consensus = 0
                for d in range(1, 13):
                    vals = []
                    for model in models:
                        v = gains[fold][week].get(model, {}).get((d, i + d)) if i + d < n else None
                        vals.append(v)
                    if all(v is not None and v > 0 for v in vals):
                        consensus = d
                    else:
                        break
                rec["all_model_consecutive_positive_depth"] = consensus
                survival_hist[consensus] += 1
                if consensus > 0 and i + consensus in events[week] and i in events[week]:
                    elapsed = events[week][i + consensus]["t0_idx"] - events[week][i]["t0_idx"]
                    rec["consensus_elapsed_seconds"] = int(elapsed)
                    elapsed_by_depth[consensus].append(int(elapsed))
                else:
                    rec["consensus_elapsed_seconds"] = None
                instance_rows.append(rec)

    agent7 = None
    if a.agent7_summary:
        z = json.load(open(a.agent7_summary))
        if z.get("status") != "PHASE1_AGENT7_OPEN_HIGHER_ORDER_54W_PROVISIONAL_COMPLETE":
            raise SystemExit("unexpected Agent 7 status")
        agent7 = {
            "status": z["status"],
            "independent_higher_order_discovery": z.get("independent_higher_order_discovery"),
            "selected_depths_by_fold": {
                f: [int(d) for d, r in rec["depth"].items() if r.get("selected_in_training")]
                for f, rec in z["folds"].items()
            },
            "note": "Agent 7 discoveries are preserved as a separate higher-order mechanism axis; per-instance lineage is calculated from Agent 3 OOT gains unless/until an Agent 7 per-instance gain artifact is emitted.",
        }

    elapsed_summary = {}
    for d, vals in sorted(elapsed_by_depth.items()):
        a0 = np.asarray(vals, float)
        elapsed_summary[str(d)] = {
            "n": int(len(vals)),
            "median_seconds": float(np.median(a0)),
            "p25_seconds": float(np.quantile(a0, 0.25)),
            "p75_seconds": float(np.quantile(a0, 0.75)),
            "max_seconds": float(np.max(a0)),
        }

    result = {
        "status": "PHASE1_LINEAGE_54W_PROVISIONAL_COMPLETE",
        "week_count": 54,
        "temporarily_excluded_week": "20260329",
        "origin_persistence_axis": "same-origin cross-depth Fisher enrichment aligned by origin event",
        "rolling_reorigin_preserved": True,
        "inherited_origin_preserved": True,
        "instance_specific_lifespan_preserved": True,
        "lineage_association": lineage,
        "all_model_consensus_survival_depth_histogram": {str(k): int(v) for k, v in sorted(survival_hist.items())},
        "consensus_elapsed_time_by_depth": elapsed_summary,
        "agent7_context": agent7,
        "instance_count": len(instance_rows),
        "historical_phase1_complete": False,
        "phase2_allowed": False,
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
    }
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with gzip.open(Path(a.out).with_suffix(".instances.jsonl.gz"), "wt") as f:
        for r in instance_rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"status": result["status"], "instances": len(instance_rows), "survival_depths": result["all_model_consensus_survival_depth_histogram"]}, indent=2))


if __name__ == "__main__":
    main()
