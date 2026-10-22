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

import ng_exhaustion_chain_phase1_discovery_20260817 as discovery
import ng_exhaustion_chain_phase1_structural_54w_20260817 as structural
import ng_exhaustion_chain_phase1_causal_20260817 as causal_pilot
import ng_exhaustion_chain_phase1_causal_54w_20260817 as causal54
import ng_exhaustion_chain_phase1_agent7_open_mechanism_54w_20260817 as agent7


HELD = "20260329"
MODELS = ("ridge", "extra_trees", "knn")


def jload(path):
    return json.load(open(path))


def finite(x):
    try:
        return math.isfinite(float(x))
    except Exception:
        return False


def merge_week_dicts(a, b):
    overlap = set(a) & set(b)
    if overlap:
        raise SystemExit(f"week overlap forbidden: {sorted(overlap)}")
    out = dict(a)
    out.update(b)
    return out


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


def structural_held(base_table, held_table, summary, out_gains):
    base = discovery.load_rows(base_table)
    held = discovery.load_rows(held_table)
    if sorted(held) != [HELD]:
        raise SystemExit("held structural table drift")
    byweek = merge_week_dicts(base, held)
    result = {}
    gain_rows = []

    for view, frozen_key, max_depth in (
        ("full", "primary_full_path", 12),
        ("sparse", "sparse_sensitivity", 6),
    ):
        arrays, valid = discovery.make_view(byweek, view)
        frozen = summary[frozen_key]["folds"]["era4"]
        train_weeks = frozen["train_weeks"]
        if HELD in train_weeks:
            raise SystemExit("held week leaked into structural training")
        rec = {"train_weeks": train_weeks, "test_week": HELD, "depth": {}}

        for depth in range(1, max_depth + 1):
            rec["depth"][str(depth)] = {}
            for model in MODELS:
                settings = frozen["depth"][str(depth)][model]
                ps = settings.get("short_param")
                pl = settings.get("long_param")
                if pl is None:
                    rec["depth"][str(depth)][model] = {"n": 0, "gain_mean": None}
                    continue
                zs = structural.score_once(
                    model, ps, train_weeks, [HELD], byweek, arrays, valid,
                    depth, depth - 1, inner=False
                )
                zl = structural.score_once(
                    model, pl, train_weeks, [HELD], byweek, arrays, valid,
                    depth, depth, inner=False
                )
                if zs is None or zl is None or zs["meta"] != zl["meta"]:
                    raise SystemExit(f"structural held paired-sample drift view={view} d={depth} m={model}")
                gain = zs["loss"] - zl["loss"]
                rec["depth"][str(depth)][model] = {
                    "n": int(len(gain)),
                    "short_param_frozen": ps,
                    "long_param_frozen": pl,
                    "gain_mean": float(gain.mean()),
                    "gain_median": float(np.median(gain)),
                    "gain_positive_rate": float(np.mean(gain > 0)),
                    "short_mse": zs["mse"],
                    "long_mse": zl["mse"],
                }
                if view == "full":
                    for g, (w, seq, eid) in zip(gain, zs["meta"]):
                        gain_rows.append({
                            "fold": "held_insert_era4",
                            "week_sunday": w,
                            "sequence_index": int(seq),
                            "target_event_id": eid,
                            "model": model,
                            "depth": depth,
                            "incremental_gain": float(g),
                            "view": "full",
                        })
        result[view] = rec

    with gzip.open(out_gains, "wt") as f:
        for r in gain_rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return result, gain_rows


def held_lineage(held_table, gain_rows, prior_lineage_summary, prior_instances_path):
    events = {}
    with gzip.open(held_table, "rt") as f:
        for line in f:
            r = json.loads(line)
            events[int(r["sequence_index"])] = {
                "event_id": r["event_id"],
                "t0_idx": int(r["t0_idx"]),
            }
    n = max(events) + 1 if events else 0
    gains = defaultdict(dict)
    for r in gain_rows:
        gains[r["model"]][(int(r["depth"]), int(r["sequence_index"]))] = float(r["incremental_gain"])

    assoc = {}
    for model in MODELS:
        gm = gains[model]
        assoc[model] = {}
        for d in range(1, 12):
            aa, bb = [], []
            for i in range(0, n - (d + 1)):
                aa.append(gm.get((d, i + d)))
                bb.append(gm.get((d + 1, i + d + 1)))
            assoc[model][f"D{d}_to_D{d+1}"] = association(aa, bb)

    held_instances = []
    held_hist = Counter()
    for i in range(n):
        rec = {
            "fold": "held_insert_era4",
            "week_sunday": HELD,
            "origin_sequence_index": i,
            "origin_event_id": events.get(i, {}).get("event_id"),
            "model_positive_depths": {},
        }
        for model in MODELS:
            gm = gains[model]
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
            vals = [
                gains[m].get((d, i + d)) if i + d < n else None
                for m in MODELS
            ]
            if all(v is not None and v > 0 for v in vals):
                consensus = d
            else:
                break
        rec["all_model_consecutive_positive_depth"] = consensus
        held_hist[consensus] += 1
        if consensus > 0 and i + consensus in events and i in events:
            rec["consensus_elapsed_seconds"] = int(
                events[i + consensus]["t0_idx"] - events[i]["t0_idx"]
            )
        else:
            rec["consensus_elapsed_seconds"] = None
        held_instances.append(rec)

    combined_hist = Counter({int(k): int(v) for k, v in prior_lineage_summary["all_model_consensus_survival_depth_histogram"].items()})
    combined_hist.update(held_hist)

    elapsed = defaultdict(list)
    prior_instance_count = 0
    with gzip.open(prior_instances_path, "rt") as f:
        for line in f:
            r = json.loads(line)
            prior_instance_count += 1
            d = int(r.get("all_model_consecutive_positive_depth", 0))
            e = r.get("consensus_elapsed_seconds")
            if d > 0 and e is not None:
                elapsed[d].append(int(e))
    for r in held_instances:
        d = int(r["all_model_consecutive_positive_depth"])
        e = r["consensus_elapsed_seconds"]
        if d > 0 and e is not None:
            elapsed[d].append(int(e))

    elapsed_summary = {}
    for d, vals in sorted(elapsed.items()):
        a = np.asarray(vals, float)
        elapsed_summary[str(d)] = {
            "n": int(len(vals)),
            "median_seconds": float(np.median(a)),
            "p25_seconds": float(np.quantile(a, 0.25)),
            "p75_seconds": float(np.quantile(a, 0.75)),
            "max_seconds": float(np.max(a)),
        }

    return {
        "held_week_instance_count": len(held_instances),
        "prior_54w_oot_instance_count": prior_instance_count,
        "final_55w_oot_instance_count": prior_instance_count + len(held_instances),
        "held_week_survival_depth_histogram": {str(k): int(v) for k, v in sorted(held_hist.items())},
        "final_55w_survival_depth_histogram": {str(k): int(v) for k, v in sorted(combined_hist.items())},
        "final_55w_consensus_elapsed_time_by_depth": elapsed_summary,
        "held_week_same_origin_association": assoc,
        "held_instances": held_instances,
    }


def causal_held(base_table, held_table, summary):
    base = causal_pilot.load_rows(base_table)
    held = causal_pilot.load_rows(held_table)
    if sorted(held) != [HELD]:
        raise SystemExit("held causal table drift")
    byweek = merge_week_dicts(base, held)
    out = {}

    for h in causal54.HORIZONS:
        frozen = summary["by_information_horizon_seconds"][str(h)]["era4"]
        train_weeks = frozen["train_weeks"]
        if HELD in train_weeks:
            raise SystemExit("held week leaked into causal training")
        hz = {"train_weeks": train_weeks, "test_week": HELD, "depth": {}}
        for depth in causal54.DEPTHS:
            hz["depth"][str(depth)] = {}
            for model in causal54.MODELS:
                settings = frozen["depth"][str(depth)][model]
                ps = settings.get("short_param")
                pl = settings.get("long_param")
                if pl is None:
                    hz["depth"][str(depth)][model] = {"n": 0, "gain_mean": None}
                    continue
                a = causal54.score(model, ps, train_weeks, [HELD], byweek, h, depth, depth - 1, inner=False)
                b = causal54.score(model, pl, train_weeks, [HELD], byweek, h, depth, depth, inner=False)
                if a is None or b is None or a["meta"] != b["meta"]:
                    raise SystemExit(f"causal held paired-sample drift h={h} d={depth} m={model}")
                g = a["loss"] - b["loss"]
                hz["depth"][str(depth)][model] = {
                    "n": int(len(g)),
                    "short_param_frozen": ps,
                    "long_param_frozen": pl,
                    "gain_mean": float(g.mean()),
                    "gain_median": float(np.median(g)),
                    "gain_positive_rate": float(np.mean(g > 0)),
                    "short_mse": a["mse"],
                    "long_mse": b["mse"],
                }
        out[str(h)] = hz
    return out


def agent7_frozen_pair(train_weeks, test_weeks, byweek, arrays, valid, depth, short_alpha, long_alpha):
    XS_tr, XL_tr, Ytr, _ = agent7.paired_week_matrices(train_weeks, byweek, arrays, valid, depth)
    XS_te, XL_te, Yte, meta = agent7.paired_week_matrices(test_weeks, byweek, arrays, valid, depth)
    if not len(Ytr) or not len(Yte):
        return None
    XS_tr, XL_tr, Ytr, _ = agent7.deterministic_sample(
        XS_tr, XL_tr, Ytr, [("", 0, "")] * len(Ytr), 24000
    )
    XS_te, XL_te, Yte, meta = agent7.deterministic_sample(
        XS_te, XL_te, Yte, meta, 9000
    )
    Ytrz, Ytez = agent7.standardize_y(Ytr, Yte)
    XS_trz, XS_tez, _, _ = agent7.standardize_train_test(XS_tr, XS_te)
    XL_trz, XL_tez, _, _ = agent7.standardize_train_test(XL_tr, XL_te)
    if depth == 1:
        ls = np.mean(Ytez ** 2, axis=1)
    else:
        ls, _ = agent7.ridge_loss(short_alpha, XS_trz, Ytrz, XS_tez, Ytez)
    ll, _ = agent7.ridge_loss(long_alpha, XL_trz, Ytrz, XL_tez, Ytez)
    g = ls - ll
    return {
        "n": int(len(g)),
        "gain_mean": float(g.mean()),
        "gain_median": float(np.median(g)),
        "gain_positive_rate": float(np.mean(g > 0)),
    }


def agent7_held(base_table, held_table, summary):
    base = discovery.load_rows(base_table)
    held = discovery.load_rows(held_table)
    byweek = merge_week_dicts(base, held)
    arrays, valid = discovery.make_view(byweek, "full")
    frozen = summary["folds"]["era4"]
    train_weeks = frozen["train_weeks"]
    if HELD in train_weeks:
        raise SystemExit("held week leaked into Agent7 training")
    out = {"train_weeks": train_weeks, "test_week": HELD, "depth": {}}
    for d in range(1, agent7.MAX_DEPTH + 1):
        z = frozen["depth"][str(d)]
        rec = {
            "selected_in_training_frozen": bool(z.get("selected_in_training")),
            "inner_validation_gain_frozen": z.get("inner_validation_gain"),
            "short_alpha_frozen": z.get("short_alpha"),
            "long_alpha_frozen": z.get("long_alpha"),
        }
        if z.get("long_alpha") is not None:
            rec.update(agent7_frozen_pair(
                train_weeks, [HELD], byweek, arrays, valid, d,
                z.get("short_alpha"), z.get("long_alpha")
            ) or {"n": 0, "gain_mean": None})
        if rec["selected_in_training_frozen"]:
            rec["extra_trees_crosscheck"] = agent7.extra_trees_crosscheck(
                train_weeks, [HELD], byweek, arrays, valid, d
            )
        out["depth"][str(d)] = rec
    return out


def summarize_structural_signs(held_structural, prior_summary):
    out = {}
    for d in range(1, 13):
        ds = {}
        for model in MODELS:
            h = held_structural["full"]["depth"][str(d)][model].get("gain_mean")
            prior = prior_summary["aggregate"][str(d)][model]
            ds[model] = {
                "held_gain_mean": h,
                "held_positive": bool(finite(h) and h > 0),
                "prior_discovery_eras_positive": prior["discovery_eras_positive"],
                "prior_confirmation_gain_mean": prior["confirmation_gain_mean"],
            }
        out[str(d)] = ds
    return out


def summarize_causal_signs(held_causal, prior_falsifier):
    out = {}
    prior = prior_falsifier["causal_week_block_null"]
    for h, hz in held_causal.items():
        out[h] = {}
        for d, row in hz["depth"].items():
            rr = {}
            for model in MODELS:
                g = row[model].get("gain_mean")
                p = prior[h][d][model]
                rr[model] = {
                    "held_gain_mean": g,
                    "held_positive": bool(finite(g) and g > 0),
                    "prior_discovery_week_mean_gain": p["discovery_week_mean_gain"],
                    "prior_untouched_confirmation_gain_mean": p["untouched_confirmation_gain_mean"],
                }
            out[h][d] = rr
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-table", required=True)
    ap.add_argument("--base-summary", required=True)
    ap.add_argument("--held-table", required=True)
    ap.add_argument("--held-summary", required=True)
    ap.add_argument("--structural-summary", required=True)
    ap.add_argument("--causal-summary", required=True)
    ap.add_argument("--lineage-summary", required=True)
    ap.add_argument("--lineage-instances", required=True)
    ap.add_argument("--falsifier-summary", required=True)
    ap.add_argument("--agent7-summary", required=True)
    ap.add_argument("--out-prefix", default="NG_EXHAUSTION_CHAIN_PHASE1_55W_RECONCILED_20260817")
    args = ap.parse_args()

    base_summary = jload(args.base_summary)
    held_summary = jload(args.held_summary)
    structural_summary = jload(args.structural_summary)
    causal_summary = jload(args.causal_summary)
    lineage_summary = jload(args.lineage_summary)
    falsifier = jload(args.falsifier_summary)
    a7_summary = jload(args.agent7_summary)

    hard_failures = []
    if base_summary.get("week_count") != 54:
        hard_failures.append("base_week_count_not_54")
    if base_summary.get("event_count") != 231532:
        hard_failures.append("base_event_count_drift")
    if held_summary.get("week_sunday") != HELD or held_summary.get("event_count") != 3638:
        hard_failures.append("held_week_identity_or_event_count_drift")
    if held_summary.get("synthetic_empty_raw_file_created") is not False:
        hard_failures.append("synthetic_closure_file_forbidden")
    if held_summary.get("explicit_closure_dates") != ["20260403"]:
        hard_failures.append("closure_witness_drift")
    b_schema = base_summary.get("table", {}).get("schema_sha256")
    h_schema = held_summary.get("table", {}).get("schema_sha256")
    if b_schema and h_schema and b_schema != h_schema:
        hard_failures.append("held_schema_mismatch")
    if falsifier.get("hard_failures"):
        hard_failures.append("54w_falsifier_hard_failure")

    held_gains_path = args.out_prefix + "_HELD_STRUCTURAL_GAINS.jsonl.gz"
    held_structural, gain_rows = structural_held(
        args.base_table, args.held_table, structural_summary, held_gains_path
    )
    held_lineage_result = held_lineage(
        args.held_table, gain_rows, lineage_summary, args.lineage_instances
    )
    held_causal = causal_held(args.base_table, args.held_table, causal_summary)
    held_a7 = agent7_held(args.base_table, args.held_table, a7_summary)

    final_event_count = int(base_summary["event_count"]) + int(held_summary["event_count"])
    result = {
        "status": "PHASE1_HISTORICAL_55W_INSERT_ONLY_RECONCILED_COMPLETE" if not hard_failures else "PHASE1_55W_RECONCILIATION_FAILED_CLOSED",
        "historical_phase1_complete": not hard_failures,
        "phase2_allowed": not hard_failures,
        "week_count": 55,
        "event_count": final_event_count,
        "base_54w_preserved_immutable": True,
        "held_week_insert_only": True,
        "held_week": HELD,
        "component_hashes": {
            "base_54w_event_table_gzip_sha256": base_summary.get("table", {}).get("gzip_sha256"),
            "base_54w_event_table_uncompressed_sha256": base_summary.get("table", {}).get("uncompressed_jsonl_sha256"),
            "held_event_table_gzip_sha256": held_summary.get("table", {}).get("gzip_sha256"),
            "held_event_table_uncompressed_sha256": held_summary.get("table", {}).get("uncompressed_jsonl_sha256"),
            "schema_sha256": h_schema or b_schema,
        },
        "hard_failures": hard_failures,
        "structural_held_week": held_structural,
        "structural_55w_sign_reconciliation": summarize_structural_signs(held_structural, structural_summary),
        "lineage_55w": {k: v for k, v in held_lineage_result.items() if k != "held_instances"},
        "causal_held_week": held_causal,
        "causal_55w_sign_reconciliation": summarize_causal_signs(held_causal, falsifier),
        "agent7_held_week": held_a7,
        "agent7_promotion_rule": "Only depths selected inside the frozen Era 4 training set are eligible for held-week promotion; all other held scores are descriptive only.",
        "source_54w_falsifier_status": falsifier.get("status"),
        "source_54w_falsifier_hard_failures": falsifier.get("hard_failures"),
        "runway_clock_mutated": False,
        "permanent_frankie_mutated": False,
        "notes": [
            "20260329 was scored as an out-of-time insert inside the original Era 4 chronology using models/settings frozen before the held-week outcome was evaluated.",
            "No 54-week base event row, event id, detector semantic, score, or tuning result was rewritten.",
            "Phase 2 unlock here is procedural: it means the 55-week historical Phase-1 evidence set is complete. It does not imply every depth or model family survived.",
        ],
    }

    Path(args.out_prefix + "_SUMMARY.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with gzip.open(args.out_prefix + "_HELD_LINEAGE_INSTANCES.jsonl.gz", "wt") as f:
        for r in held_lineage_result["held_instances"]:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")

    print(json.dumps({
        "status": result["status"],
        "week_count": result["week_count"],
        "event_count": result["event_count"],
        "phase2_allowed": result["phase2_allowed"],
        "held_survival_histogram": result["lineage_55w"]["held_week_survival_depth_histogram"],
        "final_survival_histogram": result["lineage_55w"]["final_55w_survival_depth_histogram"],
    }, indent=2))


if __name__ == "__main__":
    main()
