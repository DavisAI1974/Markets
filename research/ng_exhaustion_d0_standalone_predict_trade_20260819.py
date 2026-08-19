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

EXPECTED_EXACT = {0: 135860, 1: 18837, 2: 1592, 3: 124, 4: 8, 5: 1}
D0_THRESHOLDS = (0.75, 0.85, 0.90, 0.95, 0.975)
HOLD_SECONDS = (5, 10, 20, 30, 60, 120, 300)
ORIENTATIONS = ("WITH_ROOT_POLARITY", "AGAINST_ROOT_POLARITY")


def invert_to_d0_cases(cases):
    out = []
    for c in cases:
        z = dict(c)
        z["y"] = 1 - int(c["y"])
        out.append(z)
    return out


def load_inputs(base_path, held_path, base_lineage, held_lineage, raw_dir):
    events = base.load_events(base_path, held_path)
    lineage = base.load_lineage(base_lineage, held_lineage)
    exact = Counter(int(r["depth"]) for r in lineage)
    assert dict(sorted(exact.items())) == EXPECTED_EXACT, (dict(sorted(exact.items())), EXPECTED_EXACT)
    birth_cases, censored = base.birth_cases(events, lineage, 1)
    d0_cases = invert_to_d0_cases(birth_cases)
    d0_pos = sum(int(c["y"] == 1) for c in d0_cases)
    cont_neg = sum(int(c["y"] == 0) for c in d0_cases)
    assert d0_pos == 135823, d0_pos
    assert cont_neg == 20562, cont_neg
    assert len(censored) == 37, len(censored)
    weeks = sorted({c["week"] for c in d0_cases})
    cache = {"times": {}, "prices": {}, "snap": {}}
    for w in weeks:
        t, p = base.load_week_prices(raw_dir, w)
        if len(t) == 0:
            raise RuntimeError(f"authoritative raw price tape missing for D0 week={w}")
        cache["times"][w] = t
        cache["prices"][w] = p
    return d0_cases, censored, cache, exact


def direct_predict(d0_cases, censored, cache, exact):
    tested = []
    winner = None
    for h in base.HGRID:
        p = base.evaluate_point(d0_cases, 1, "prior", h, cache)
        tested.append(p)
        if p["validated"]:
            winner = {"timing_class": "PRIOR_D0_TERMINALITY_PREDICTION", "H_seconds": int(h), "point": p}
            break
        vn = max((z["blocks"].get("validation", {}).get("n", 0) for z in p["models"].values()), default=0)
        if vn == 0:
            break
    return {
        "status": "D0_STANDALONE_PREDICTOR_COMPLETE",
        "primary_target": "PREDICT_ROOT_EXHAUSTION_TERMINATES_AS_D0_BEFORE_NEXT_CANONICAL_EVENT",
        "independent_of_D1_v2_result": True,
        "exact_d0_preserved_n": int(exact[0]),
        "executable_d0_positive_n": 135823,
        "D1plus_continuation_control_n": 20562,
        "censored_d0_n": len(censored),
        "H_grid": list(base.HGRID),
        "price_structure_mode": v2.PRICE_STRUCTURE_MODE,
        "price_structure_per_occurrence": True,
        "price_structure_availability_used_as_feature": False,
        "earliest_validated": winner,
        "tested_points": tested,
        "D1_complement_role": "LATER_CONSISTENCY_AND_CALIBRATION_CROSSCHECK_ONLY",
        "realized_exact_d0_used_as_input_feature": False,
        "promotion_performed": False,
        "protected_mutations": {
            "detector": False,
            "canonical_rows": False,
            "phase1": False,
            "phase2": False,
            "runway_clock": False,
            "permanent_frankie": False,
            "frankie_1": False,
            "spawn_py": False,
            "ssos_play": False,
        },
    }


def prediction_rows(d0_cases, train_blocks, test_blocks, h, cache, params):
    train = base.split_cases(d0_cases, tuple(train_blocks))
    test = base.split_cases(d0_cases, tuple(test_blocks))
    Xtr, ytr, _, _, _ = base.dataset(train, 1, "prior", h, cache, "long")
    Xte, yte, ids, weeks, leads = base.dataset(test, 1, "prior", h, cache, "long")
    if not len(yte):
        return []
    probs = []
    for name in base.MODELS:
        param = params.get(name)
        if param is None:
            raise RuntimeError(f"missing frozen D0 model parameter for {name}")
        probs.append(base.predict_probability(name, param, Xtr, ytr, Xte))
    p0 = np.median(np.vstack(probs), axis=0)
    case_by_id = {c["id"]: c for c in test}
    rows = []
    for cid, yy, w, lead, pp in zip(ids, yte, weeks, leads, p0):
        c = case_by_id[cid]
        rows.append({
            "id": cid,
            "week": w,
            "block": c["block"],
            "actual_d0": int(yy),
            "d0_probability": float(pp),
            "lead_seconds_to_next_event": int(lead),
            "case": c,
        })
    return rows


def fill_trade(cache, pred_row, signal_h, hold, orientation):
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
    return {
        "id": pred_row["id"],
        "week": pred_row["week"],
        "actual_d0": pred_row["actual_d0"],
        "d0_probability": pred_row["d0_probability"],
        "lead_seconds_to_next_event": pred_row["lead_seconds_to_next_event"],
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
        "path_efficiency": abs(float(gross)) / max(rng, 1e-9),
    }


def mean(xs):
    return float(np.mean(xs)) if xs else None


def summarize(rows):
    if not rows:
        return {"n": 0}
    byweek = defaultdict(list)
    for r in rows:
        byweek[r["week"]].append(r["net_1_ticks"])
    week_means = [float(np.mean(v)) for v in byweek.values()]
    return {
        "n": len(rows),
        "actual_d0_fraction": mean([r["actual_d0"] for r in rows]),
        "mean_lead_seconds_to_next_event": mean([r["lead_seconds_to_next_event"] for r in rows]),
        "mean_gross_ticks": mean([r["gross_ticks"] for r in rows]),
        "mean_net_0_5_ticks": mean([r["net_0_5_ticks"] for r in rows]),
        "mean_net_1_ticks": mean([r["net_1_ticks"] for r in rows]),
        "mean_net_2_ticks": mean([r["net_2_ticks"] for r in rows]),
        "mean_mfe_ticks": mean([r["mfe_ticks"] for r in rows]),
        "mean_mae_ticks": mean([r["mae_ticks"] for r in rows]),
        "mean_path_efficiency": mean([r["path_efficiency"] for r in rows]),
        "positive_week_fraction_net_1": float(np.mean([x > 0 for x in week_means])) if week_means else None,
        "weeks": len(byweek),
    }


def candidate_rows(pred_rows, cache, h, threshold, hold, orientation):
    rows = []
    for p in pred_rows:
        if p["d0_probability"] < threshold:
            continue
        z = fill_trade(cache, p, h, hold, orientation)
        if z is not None:
            rows.append(z)
    return rows


def trade_from_direct(direct, d0_cases, cache):
    winner = direct.get("earliest_validated")
    protected = dict(direct["protected_mutations"])
    if winner is None or winner.get("timing_class") != "PRIOR_D0_TERMINALITY_PREDICTION":
        return {
            "status": "D0_STANDALONE_TRADE_BLOCKED_NO_VALIDATED_PRIOR",
            "exact_d0_preserved_n": 135860,
            "executable_d0_n": 135823,
            "censored_d0_n": 37,
            "next_research": "DIRECT_CAUSAL_D0_SURVIVORSHIP_FALLBACK",
            "promotion_performed": False,
            "protected_mutations": protected,
        }

    h = int(winner["H_seconds"])
    point = winner["point"]
    params = {m: point["models"][m]["params"]["long"] for m in base.MODELS}
    tune_pred = prediction_rows(d0_cases, ("discovery_fit",), ("discovery_tune",), h, cache, params)

    scored = []
    for threshold in D0_THRESHOLDS:
        for hold in HOLD_SECONDS:
            for orientation in ORIENTATIONS:
                rows = candidate_rows(tune_pred, cache, h, threshold, hold, orientation)
                scored.append({
                    "threshold": threshold,
                    "hold_seconds": hold,
                    "orientation": orientation,
                    "discovery_tune": summarize(rows),
                })

    eligible = [
        x for x in scored
        if x["discovery_tune"].get("n", 0) >= 200
        and x["discovery_tune"].get("mean_net_1_ticks") is not None
    ]
    eligible.sort(
        key=lambda x: (
            x["discovery_tune"]["mean_net_1_ticks"],
            x["discovery_tune"].get("positive_week_fraction_net_1") or -1,
            x["discovery_tune"]["n"],
        ),
        reverse=True,
    )
    selected = dict(eligible[0]) if eligible else None

    oot = {}
    if selected is not None:
        for block in ("validation", "confirmation", "held"):
            pred = prediction_rows(
                d0_cases,
                ("discovery_fit", "discovery_tune"),
                (block,),
                h,
                cache,
                params,
            )
            rows = candidate_rows(
                pred,
                cache,
                h,
                selected["threshold"],
                selected["hold_seconds"],
                selected["orientation"],
            )
            oot[block] = summarize(rows)

    valid = False
    if selected is not None:
        va = oot.get("validation", {})
        co = oot.get("confirmation", {})
        he = oot.get("held", {})
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
        "status": "D0_STANDALONE_TRADE_AGENT_COMPLETE",
        "signal_source": "DIRECT_D0_PRIOR_MODEL",
        "D0_prior_H_seconds": h,
        "probability_aggregation": "MEDIAN_OF_ALL_THREE_PREDECLARED_DIRECT_D0_MODELS",
        "exact_d0_preserved_n": 135860,
        "executable_d0_n": 135823,
        "censored_d0_n": 37,
        "candidate_grid": {
            "d0_probability_thresholds": list(D0_THRESHOLDS),
            "hold_seconds": list(HOLD_SECONDS),
            "orientations": list(ORIENTATIONS),
        },
        "discovery_selected_candidate": selected,
        "top_discovery_candidates": eligible[:10],
        "frozen_candidate_OOT_blocks": oot,
        "historically_validated_candidate": bool(valid),
        "trade_window_capped_at_next_canonical_exhaustion": True,
        "entry_fill": "FIRST_AUTHORITATIVE_TRADE_AT_OR_AFTER_SIGNAL",
        "exit_fill": "FIRST_AUTHORITATIVE_TRADE_AT_OR_AFTER_HORIZON_OR_NEXT_EVENT_CAP",
        "promotion_performed": False,
        "protected_mutations": protected,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--base-lineage", required=True)
    ap.add_argument("--held-lineage", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    d0_cases, censored, cache, exact = load_inputs(
        a.base, a.held, a.base_lineage, a.held_lineage, a.raw_dir
    )
    predictor = direct_predict(d0_cases, censored, cache, exact)
    trade = trade_from_direct(predictor, d0_cases, cache)
    result = {
        "status": "D0_STANDALONE_PREDICT_AND_TRADE_COMPLETE",
        "date": "2026-08-19",
        "predictor": predictor,
        "trade": trade,
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
        "all_original_depth_counts_preserved": EXPECTED_EXACT,
        "D1_v2_required": False,
        "promotion_performed": False,
        "protected_mutations": dict(predictor["protected_mutations"]),
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": result["status"],
        "earliest_D0": None if predictor["earliest_validated"] is None else {
            "timing_class": predictor["earliest_validated"]["timing_class"],
            "H_seconds": predictor["earliest_validated"]["H_seconds"],
        },
        "historically_validated_trade": trade.get("historically_validated_candidate"),
    }, indent=2))


if __name__ == "__main__":
    main()
