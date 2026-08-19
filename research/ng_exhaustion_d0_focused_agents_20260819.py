#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819 as v2

base = v2.base

D0_THRESHOLDS = (0.75, 0.85, 0.90, 0.95, 0.975)
HOLD_SECONDS = (5, 10, 20, 30, 60, 120, 300)
ORIENTATIONS = ("WITH_ROOT_POLARITY", "AGAINST_ROOT_POLARITY")
EXPECTED_EXACT = {0: 135860, 1: 18837, 2: 1592, 3: 124, 4: 8, 5: 1}


def load_json(path):
    return json.loads(Path(path).read_text())


def assert_v2(d):
    assert d["status"] == "D1_D5_CHAIN_BIRTH_V2_AGENTS_RECONCILED"
    assert d["price_structure_mode"] == "PER_OCCURRENCE_CAUSAL_ONE_SECOND_PATH_PREFIX"
    assert d["price_structure_availability_used_as_feature"] is False
    assert d["promotion_performed"] is False
    assert not any(d["protected_mutations"].values())


def _inc(rec, field):
    x = rec.get(field)
    return None if x is None else float(x)


def root_value(v2_results):
    assert_v2(v2_results)
    out = {
        "status": "D0_ROOT_INCREMENTAL_AUDIT_COMPLETE",
        "question": "DOES_CAUSAL_ROOT_STAGE_INFORMATION_ADD_INCREMENTAL_SKILL_FOR_DEEPER_CHAIN_BIRTH",
        "realized_exact_d0_label_used_as_feature": False,
        "results": {},
        "promotion_performed": False,
        "protected_mutations": dict(v2_results["protected_mutations"]),
    }

    out["results"]["D1"] = {
        "verdict": "ROOT_IS_SOLE_PREDECESSOR_FOR_D1",
        "interpretation": "D1 birth prediction is itself the direct root-stage information test.",
    }

    for stage in (2, 3):
        r = v2_results["results"][f"D{stage}"]
        winner = r.get("earliest_validated")
        if winner is None:
            out["results"][f"D{stage}"] = {
                "verdict": "NO_VALIDATED_STAGE_SIGNAL_TO_ABLATE",
                "root_incremental_models": 0,
            }
            continue
        point = winner["point"]
        model_rows = {}
        supporters = 0
        for name, z in point["models"].items():
            blocks = z.get("blocks", {})
            rec = {}
            ok = True
            for b in ("validation", "confirmation", "held"):
                q = blocks.get(b, {})
                ll = _inc(q, "incremental_log_loss_gain_D_vs_Dminus1")
                br = _inc(q, "incremental_brier_gain_D_vs_Dminus1")
                rec[b] = {
                    "n": int(q.get("n", 0)),
                    "positive_n": int(q.get("positive_n", 0)),
                    "negative_n": int(q.get("negative_n", 0)),
                    "incremental_log_loss_gain_root_vs_ablated": ll,
                    "incremental_brier_gain_root_vs_ablated": br,
                }
                if b in ("validation", "confirmation") and not (ll is not None and br is not None and ll > 0 and br > 0):
                    ok = False
            held = rec["held"]
            if held["positive_n"] >= 5 and held["negative_n"] >= 20:
                if not (
                    held["incremental_log_loss_gain_root_vs_ablated"] is not None
                    and held["incremental_brier_gain_root_vs_ablated"] is not None
                    and held["incremental_log_loss_gain_root_vs_ablated"] >= 0
                    and held["incremental_brier_gain_root_vs_ablated"] >= 0
                ):
                    ok = False
            rec["supports_root_incremental"] = bool(ok)
            supporters += int(ok)
            model_rows[name] = rec

        if supporters >= 2:
            verdict = "ROOT_INFORMATION_VALIDATED_INCREMENTAL"
        elif supporters == 0:
            verdict = "ROOT_INFORMATION_NOT_INCREMENTAL"
        else:
            verdict = "ROOT_INFORMATION_MIXED"
        out["results"][f"D{stage}"] = {
            "timing_class": winner["timing_class"],
            "H_seconds": int(winner["H_seconds"]),
            "verdict": verdict,
            "root_incremental_models": int(supporters),
            "models": model_rows,
        }

    for stage in (4, 5):
        out["results"][f"D{stage}"] = {
            "verdict": "LOW_SUPPORT_ROOT_INFORMATION_CASE_STUDY_ONLY",
            "positive_n": int(v2_results["results"][f"D{stage}"]["positive_n"]),
            "negative_n": int(v2_results["results"][f"D{stage}"]["negative_n"]),
        }
    return out


def _dataset_predictions(cases, train_blocks, test_blocks, h, cache, params):
    train = base.split_cases(cases, tuple(train_blocks))
    test = base.split_cases(cases, tuple(test_blocks))
    Xtr, ytr, _, _, _ = base.dataset(train, 1, "prior", h, cache, "long")
    Xte, yte, ids, weeks, leads = base.dataset(test, 1, "prior", h, cache, "long")
    if not len(yte):
        return []
    probs = []
    for name in base.MODELS:
        p = params.get(name)
        if p is None:
            raise RuntimeError(f"missing frozen parameter for model={name}")
        probs.append(base.predict_probability(name, p, Xtr, ytr, Xte))
    d1p = np.median(np.vstack(probs), axis=0)
    d0p = 1.0 - d1p
    case_by_id = {c["id"]: c for c in test}
    rows = []
    for cid, yy, w, lead, p0 in zip(ids, yte, weeks, leads, d0p):
        c = case_by_id[cid]
        rows.append({
            "id": cid,
            "week": w,
            "block": c["block"],
            "actual_d0": int(yy == 0),
            "d0_probability": float(p0),
            "lead_seconds_to_next_event": int(lead),
            "case": c,
        })
    return rows


def _fill_trade(cache, pred_row, signal_h, hold, orientation):
    c = pred_row["case"]
    root = c["preds"][0]
    confirm = base.event_confirm(root)
    if confirm is None:
        return None
    signal = int(confirm) + int(signal_h)
    next_t0 = int(c["target"]["t0_idx"])
    if signal > next_t0:
        return None
    boundary = min(signal + int(hold), next_t0)
    times = cache["times"][c["week"]]
    prices = cache["prices"][c["week"]]
    ie = int(np.searchsorted(times, float(signal), side="left"))
    ix = int(np.searchsorted(times, float(boundary), side="left"))
    if ie >= len(times) or ix >= len(times) or ix < ie:
        return None
    entry = float(prices[ie])
    exitp = float(prices[ix])
    seg = prices[ie : ix + 1]
    sign = float(root["polarity"])
    if orientation == "AGAINST_ROOT_POLARITY":
        sign *= -1.0
    path = sign * (seg - entry) / base.TICK
    gross = sign * (exitp - entry) / base.TICK
    mfe = float(np.max(path)) if len(path) else 0.0
    mae = float(np.min(path)) if len(path) else 0.0
    rng = float(np.max(path) - np.min(path)) if len(path) else 0.0
    eff = abs(float(gross)) / max(rng, 1e-9)
    return {
        "id": pred_row["id"],
        "week": pred_row["week"],
        "actual_d0": pred_row["actual_d0"],
        "d0_probability": pred_row["d0_probability"],
        "signal_time": int(signal),
        "entry_time": float(times[ie]),
        "exit_time": float(times[ix]),
        "planned_hold_seconds": int(hold),
        "next_event_capped": bool(signal + int(hold) >= next_t0),
        "orientation": orientation,
        "gross_ticks": float(gross),
        "net_0_5_ticks": float(gross - 0.5),
        "net_1_ticks": float(gross - 1.0),
        "net_2_ticks": float(gross - 2.0),
        "mfe_ticks": mfe,
        "mae_ticks": mae,
        "path_range_ticks": rng,
        "path_efficiency": float(eff),
    }


def _mean(xs):
    return float(np.mean(xs)) if xs else None


def _summarize_trade_rows(rows):
    if not rows:
        return {"n": 0}
    byweek = defaultdict(list)
    for r in rows:
        byweek[r["week"]].append(r["net_1_ticks"])
    week_means = [float(np.mean(v)) for v in byweek.values()]
    return {
        "n": len(rows),
        "actual_d0_fraction": _mean([r["actual_d0"] for r in rows]),
        "mean_gross_ticks": _mean([r["gross_ticks"] for r in rows]),
        "mean_net_0_5_ticks": _mean([r["net_0_5_ticks"] for r in rows]),
        "mean_net_1_ticks": _mean([r["net_1_ticks"] for r in rows]),
        "mean_net_2_ticks": _mean([r["net_2_ticks"] for r in rows]),
        "mean_mfe_ticks": _mean([r["mfe_ticks"] for r in rows]),
        "mean_mae_ticks": _mean([r["mae_ticks"] for r in rows]),
        "mean_path_efficiency": _mean([r["path_efficiency"] for r in rows]),
        "positive_week_fraction_net_1": float(np.mean([x > 0 for x in week_means])) if week_means else None,
        "weeks": len(byweek),
    }


def _candidate_rows(pred_rows, cache, h, threshold, hold, orientation):
    out = []
    for p in pred_rows:
        if p["d0_probability"] < threshold:
            continue
        z = _fill_trade(cache, p, h, hold, orientation)
        if z is not None:
            out.append(z)
    return out


def trade(v2_results, base_path, held_path, base_lineage, held_lineage, raw_dir):
    assert_v2(v2_results)
    d1 = v2_results["results"]["D1"]
    winner = d1.get("earliest_validated")
    protected = dict(v2_results["protected_mutations"])
    if winner is None or winner.get("timing_class") != "PRIOR_BIRTH_PREDICTION":
        return {
            "status": "D0_PRIMARY_TERMINALITY_TRADE_BLOCKED_NO_VALIDATED_D1_PRIOR",
            "exact_d0_preserved_n": 135860,
            "executable_d0_n": 135823,
            "censored_d0_n": 37,
            "next_direct_research": "CAUSAL_D0_SURVIVORSHIP_FALLBACK_ONLY_IF_PRIMARY_COMPLEMENT_FAILS",
            "promotion_performed": False,
            "protected_mutations": protected,
        }

    h = int(winner["H_seconds"])
    point = winner["point"]
    params = {m: point["models"][m]["params"]["long"] for m in base.MODELS}
    events = base.load_events(base_path, held_path)
    lineage = base.load_lineage(base_lineage, held_lineage)
    exact = Counter(int(r["depth"]) for r in lineage)
    assert dict(sorted(exact.items())) == EXPECTED_EXACT
    cases, censored = base.birth_cases(events, lineage, 1)
    neg = sum(int(c["y"] == 0) for c in cases)
    pos = sum(int(c["y"] == 1) for c in cases)
    assert neg == 135823 and pos == 20562 and len(censored) == 37

    weeks = sorted({c["week"] for c in cases})
    cache = {"times": {}, "prices": {}, "snap": {}}
    for w in weeks:
        t, p = base.load_week_prices(raw_dir, w)
        if len(t) == 0:
            raise RuntimeError(f"authoritative raw price tape missing for D0 trade week={w}")
        cache["times"][w] = t
        cache["prices"][w] = p

    tune_pred = _dataset_predictions(cases, ("discovery_fit",), ("discovery_tune",), h, cache, params)
    scored = []
    for threshold in D0_THRESHOLDS:
        for hold in HOLD_SECONDS:
            for orientation in ORIENTATIONS:
                rows = _candidate_rows(tune_pred, cache, h, threshold, hold, orientation)
                s = _summarize_trade_rows(rows)
                scored.append({
                    "threshold": threshold,
                    "hold_seconds": hold,
                    "orientation": orientation,
                    "discovery_tune": s,
                })
    eligible = [x for x in scored if x["discovery_tune"].get("n", 0) >= 200 and x["discovery_tune"].get("mean_net_1_ticks") is not None]
    eligible.sort(
        key=lambda x: (
            x["discovery_tune"]["mean_net_1_ticks"],
            x["discovery_tune"].get("positive_week_fraction_net_1") or -1,
            x["discovery_tune"]["n"],
        ),
        reverse=True,
    )
    if not eligible:
        selected = None
    else:
        selected = dict(eligible[0])

    block_results = {}
    if selected is not None:
        for block in ("validation", "confirmation", "held"):
            pred = _dataset_predictions(
                cases,
                ("discovery_fit", "discovery_tune"),
                (block,),
                h,
                cache,
                params,
            )
            rows = _candidate_rows(
                pred,
                cache,
                h,
                selected["threshold"],
                selected["hold_seconds"],
                selected["orientation"],
            )
            block_results[block] = _summarize_trade_rows(rows)

    valid = False
    if selected is not None:
        va = block_results.get("validation", {})
        co = block_results.get("confirmation", {})
        he = block_results.get("held", {})
        valid = (
            va.get("n", 0) >= 200
            and co.get("n", 0) >= 100
            and va.get("mean_net_1_ticks", -math.inf) > 0
            and co.get("mean_net_1_ticks", -math.inf) > 0
            and va.get("positive_week_fraction_net_1", 0) >= 0.5
            and co.get("positive_week_fraction_net_1", 0) >= 0.5
        )
        if he.get("n", 0) >= 50 and he.get("mean_net_1_ticks", -math.inf) < 0:
            valid = False

    return {
        "status": "D0_TERMINALITY_TRADE_AGENT_COMPLETE",
        "primary_signal_source": "COMPLEMENT_OF_VALIDATED_D1_PRIOR_BIRTH_PROBABILITY",
        "D1_prior_H_seconds": h,
        "probability_aggregation": "MEDIAN_OF_ALL_THREE_PREDECLARED_V2_MODELS",
        "exact_d0_preserved_n": int(exact[0]),
        "executable_d0_n": neg,
        "censored_d0_n": len(censored),
        "d1_birth_positive_n": pos,
        "candidate_grid": {
            "d0_probability_thresholds": list(D0_THRESHOLDS),
            "hold_seconds": list(HOLD_SECONDS),
            "orientations": list(ORIENTATIONS),
        },
        "discovery_selected_candidate": selected,
        "top_discovery_candidates": eligible[:10],
        "frozen_candidate_OOT_blocks": block_results,
        "historically_validated_candidate": bool(valid),
        "trade_window_capped_at_next_canonical_exhaustion": True,
        "entry_fill": "FIRST_AUTHORITATIVE_TRADE_AT_OR_AFTER_SIGNAL",
        "exit_fill": "FIRST_AUTHORITATIVE_TRADE_AT_OR_AFTER_HORIZON_OR_NEXT_EVENT_CAP",
        "promotion_performed": False,
        "protected_mutations": protected,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("root-value", "trade"), required=True)
    ap.add_argument("--v2-results", required=True)
    ap.add_argument("--base")
    ap.add_argument("--held")
    ap.add_argument("--base-lineage")
    ap.add_argument("--held-lineage")
    ap.add_argument("--raw-dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    vr = load_json(a.v2_results)
    if a.mode == "root-value":
        result = root_value(vr)
    else:
        for x in (a.base, a.held, a.base_lineage, a.held_lineage, a.raw_dir):
            if not x:
                raise SystemExit("trade mode requires canonical/lineage/raw inputs")
        result = trade(vr, a.base, a.held, a.base_lineage, a.held_lineage, a.raw_dir)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"]}, indent=2))


if __name__ == "__main__":
    main()
