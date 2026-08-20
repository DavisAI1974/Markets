#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import ng_exhaustion_d1_d5_chain_birth_agents_20260819 as raw
from ng_exhaustion_chain_recovery_features_v3_20260819 import (
    DATE,
    CAUSAL_OVERLAP_FIX_REVISION,
    CAUSAL_OVERLAP_POLICY,
    EXPECTED_EXACT,
    MODELS,
    POST_H,
    PRIOR_AGES,
    TICK,
    build_cases,
    checkpoint,
    event_confirm,
    load_events_full,
    load_lineage,
    load_price_cache,
    split_cases,
    dataset,
)
from ng_exhaustion_chain_recovery_models_v3_20260819 import (
    align_probs,
    evaluate,
    predict_probs,
    tune_param,
)

IMPLEMENTATION_REVISION = "V3_CONTINUOUS_LIVE_MARKET_STATE_FIXED_HORIZON_TRADE"
TARGET = "CONTINUATION"
THRESHOLD_QUANTILES = (0.50, 0.70, 0.80, 0.90, 0.95)
HOLDS = (5, 10, 20, 30, 60, 120, 300)
ORIENTATIONS = (
    "WITH_LAST_PREDECESSOR_POLARITY",
    "AGAINST_LAST_PREDECESSOR_POLARITY",
    "WITH_LIVE_PRICE_5S",
    "AGAINST_LIVE_PRICE_5S",
    "WITH_LIVE_FLOW20",
    "AGAINST_LIVE_FLOW20",
)
TUNE_MIN_N = {0: 500, 1: 200, 2: 50, 3: 15}
OOT_MIN = {
    0: {"validation": 200, "confirmation": 100},
    1: {"validation": 100, "confirmation": 50},
    2: {"validation": 30, "confirmation": 15},
    3: {"validation": 10, "confirmation": 5},
}
MAX_ENTRY_DELAY_S = 5.0
MAX_EXIT_DELAY_S = 10.0


def invert_d0(cases):
    out = []
    for c in cases:
        z = dict(c)
        z["continuation"] = 1 - int(c["continuation"])
        out.append(z)
    return out


def build_trade_cases(events, lineage, stage: int):
    if stage == 0:
        d1, censored = build_cases(events, lineage, 1)
        cases = invert_d0(d1)
        assert sum(int(c["continuation"] == 1) for c in cases) == 135823
        assert sum(int(c["continuation"] == 0) for c in cases) == 20562
        assert len(censored) == 37
        return cases, censored, 1
    cases, censored = build_cases(events, lineage, stage)
    return cases, censored, stage


def signal_scan(model: str, cases, engine_stage: int, trade_stage: int, cache):
    tested = []
    for age in PRIOR_AGES:
        q = evaluate(model, cases, engine_stage, "PRIOR", age, cache, "FULL_CAUSAL", TARGET)
        tested.append({
            "phase": "PRIOR",
            "seconds": int(age),
            "independently_validated": bool(q["independently_validated"]),
            "param": q.get("param"),
            "blocks": q.get("blocks", {}),
        })
        if q["independently_validated"]:
            return "PRIOR", int(age), q.get("param"), tested
    if trade_stage == 0:
        return None, None, None, tested
    for h in POST_H:
        q = evaluate(model, cases, engine_stage, "POST_BIRTH", h, cache, "FULL_CAUSAL", TARGET)
        tested.append({
            "phase": "POST_BIRTH",
            "seconds": int(h),
            "independently_validated": bool(q["independently_validated"]),
            "param": q.get("param"),
            "blocks": q.get("blocks", {}),
        })
        if q["independently_validated"]:
            return "POST_BIRTH", int(h), q.get("param"), tested
    return None, None, None, tested


def probability_rows(model, param, trainset, testset, engine_stage, phase, sec, cache):
    Xtr, ytr, _, _, _ = dataset(trainset, engine_stage, phase, sec, cache, "FULL_CAUSAL", TARGET)
    Xte, yte, weeks, leads, ids = dataset(testset, engine_stage, phase, sec, cache, "FULL_CAUSAL", TARGET)
    if len(yte) == 0 or len(np.unique(ytr)) < 2:
        return []
    rawp, classes = predict_probs(model, param, Xtr, ytr, Xte)
    if rawp is None:
        return []
    p = align_probs(rawp, classes, ["0", "1"])[:, 1]
    cmap = {c["id"]: c for c in testset}
    return [
        {
            "id": cid,
            "week": w,
            "actual_positive": int(y),
            "probability": float(pp),
            "lead_seconds": int(lead),
            "case": cmap[cid],
        }
        for cid, y, w, lead, pp in zip(ids, yte, weeks, leads, p)
    ]


def exec_cache(cases, raw_dir: str):
    out = {"times": {}, "prices": {}}
    for w in sorted({c["week"] for c in cases}):
        t, p = raw.load_week_prices(raw_dir, w)
        if len(t) == 0:
            raise RuntimeError(f"no authoritative execution tape week={w}")
        out["times"][w] = t
        out["prices"][w] = p
    return out


def last_at(t, v, x):
    j = int(np.searchsorted(t, float(x), side="right")) - 1
    return None if j < 0 else float(v[j])


def first_at_or_after(t, x):
    j = int(np.searchsorted(t, float(x), side="left"))
    return None if j >= len(t) else j


def sign_nonzero(x):
    if x is None or not math.isfinite(float(x)) or abs(float(x)) < 1e-12:
        return None
    return 1.0 if float(x) > 0 else -1.0


def live_direction(feature_cache, case, cutoff: int, orientation: str):
    w = case["week"]
    if orientation in ("WITH_LAST_PREDECESSOR_POLARITY", "AGAINST_LAST_PREDECESSOR_POLARITY"):
        s = float(case["preds"][-1]["polarity"])
        return s if orientation.startswith("WITH_") else -s
    if orientation in ("WITH_LIVE_PRICE_5S", "AGAINST_LIVE_PRICE_5S"):
        t = feature_cache["times"][w]; p = feature_cache["prices"][w]
        now = last_at(t, p, cutoff); prev = last_at(t, p, cutoff - 5)
        s = None if now is None or prev is None else sign_nonzero(now - prev)
        if s is None:
            return None
        return s if orientation.startswith("WITH_") else -s
    if orientation in ("WITH_LIVE_FLOW20", "AGAINST_LIVE_FLOW20"):
        t = feature_cache["flow_times"][w]
        s = feature_cache["flow_signed"][w]
        a = feature_cache["flow_abs"][w]
        i = int(np.searchsorted(t, float(cutoff - 19), side="left"))
        j = int(np.searchsorted(t, float(cutoff), side="right"))
        if j <= i:
            return None
        total = float(np.sum(a[i:j]))
        signed = float(np.sum(s[i:j]))
        q = None if total <= 0 else sign_nonzero(signed / total)
        if q is None:
            return None
        return q if orientation.startswith("WITH_") else -q
    raise ValueError(orientation)


def cutoff_for_row(case, phase: str, sec: int):
    z = checkpoint(case, phase, sec)
    return None if z is None else int(z[0])


def fill_trade(feature_cache, execution_cache, row, phase, sec, hold, orientation):
    c = row["case"]
    signal = cutoff_for_row(c, phase, sec)
    if signal is None:
        return None
    direction = live_direction(feature_cache, c, signal, orientation)
    if direction is None:
        return None
    w = c["week"]
    times = execution_cache["times"][w]
    prices = execution_cache["prices"][w]
    ie = first_at_or_after(times, signal)
    ix = first_at_or_after(times, signal + int(hold))
    if ie is None or ix is None or ix < ie:
        return None
    entry_delay = float(times[ie]) - float(signal)
    exit_delay = float(times[ix]) - float(signal + int(hold))
    if entry_delay > MAX_ENTRY_DELAY_S or exit_delay > MAX_EXIT_DELAY_S:
        return None
    entry = float(prices[ie]); exitp = float(prices[ix])
    seg = prices[ie:ix + 1]
    if len(seg) == 0:
        return None
    path = float(direction) * (seg - entry) / TICK
    gross = float(direction) * (exitp - entry) / TICK
    rng = float(np.max(path) - np.min(path))
    return {
        "id": row["id"],
        "week": row["week"],
        "actual_positive": int(row["actual_positive"]),
        "probability": float(row["probability"]),
        "lead_seconds": int(row["lead_seconds"]),
        "signal_phase": phase,
        "signal_seconds": int(sec),
        "signal_time": int(signal),
        "entry_time": float(times[ie]),
        "exit_time": float(times[ix]),
        "entry_delay_seconds": entry_delay,
        "exit_delay_seconds": exit_delay,
        "planned_hold_seconds": int(hold),
        "orientation": orientation,
        "direction_sign": int(direction),
        "gross_ticks": gross,
        "net_0_5_ticks": gross - 0.5,
        "net_1_ticks": gross - 1.0,
        "net_2_ticks": gross - 2.0,
        "mfe_ticks": float(np.max(path)),
        "mae_ticks": float(np.min(path)),
        "path_range_ticks": rng,
        "path_efficiency": abs(gross) / max(rng, 1e-9),
    }


def summary(rows):
    if not rows:
        return {"n": 0}
    by = defaultdict(list)
    for r in rows:
        by[r["week"]].append(r["net_1_ticks"])
    wmeans = [float(np.mean(v)) for v in by.values()]
    def mean(k):
        return float(np.mean([r[k] for r in rows]))
    return {
        "n": int(len(rows)),
        "actual_positive_fraction": mean("actual_positive"),
        "mean_probability": mean("probability"),
        "mean_lead_seconds": mean("lead_seconds"),
        "mean_entry_delay_seconds": mean("entry_delay_seconds"),
        "mean_exit_delay_seconds": mean("exit_delay_seconds"),
        "mean_gross_ticks": mean("gross_ticks"),
        "mean_net_0_5_ticks": mean("net_0_5_ticks"),
        "mean_net_1_ticks": mean("net_1_ticks"),
        "mean_net_2_ticks": mean("net_2_ticks"),
        "mean_mfe_ticks": mean("mfe_ticks"),
        "mean_mae_ticks": mean("mae_ticks"),
        "mean_path_efficiency": mean("path_efficiency"),
        "positive_week_fraction_net_1": float(np.mean([x > 0 for x in wmeans])) if wmeans else None,
        "weeks": int(len(by)),
    }


def threshold_grid(tune_rows):
    if not tune_rows:
        return []
    p = np.asarray([r["probability"] for r in tune_rows], float)
    out = []
    for q in THRESHOLD_QUANTILES:
        out.append({"quantile": float(q), "probability_threshold": float(np.quantile(p, q))})
    uniq = {}
    for r in out:
        uniq[round(r["probability_threshold"], 12)] = r
    return list(uniq.values())


def candidate(rows, feature_cache, execution_cache, phase, sec, threshold, hold, orientation):
    out = []
    for r in rows:
        if r["probability"] < float(threshold):
            continue
        z = fill_trade(feature_cache, execution_cache, r, phase, sec, hold, orientation)
        if z is not None:
            out.append(z)
    return out


def validate_trade(stage: int, oot: dict[str, dict[str, Any]]):
    for block in ("validation", "confirmation"):
        q = oot.get(block, {})
        if q.get("n", 0) < OOT_MIN[stage][block]:
            return False
        if q.get("mean_net_1_ticks", -math.inf) <= 0:
            return False
        if q.get("positive_week_fraction_net_1", 0) < 0.5:
            return False
    held = oot.get("held", {})
    if held.get("n", 0) >= max(5, OOT_MIN[stage]["confirmation"] // 2):
        if held.get("mean_net_1_ticks", -math.inf) < 0:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=int, required=True, choices=(0,1,2,3))
    ap.add_argument("--model", required=True, choices=MODELS)
    ap.add_argument("--base", required=True)
    ap.add_argument("--held", required=True)
    ap.add_argument("--base-lineage", required=True)
    ap.add_argument("--held-lineage", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    events = load_events_full(a.base, a.held)
    lineage = load_lineage(a.base_lineage, a.held_lineage)
    exact = Counter(int(r["depth"]) for r in lineage)
    assert dict(sorted(exact.items())) == EXPECTED_EXACT
    cases, censored, engine_stage = build_trade_cases(events, lineage, a.stage)
    feature_cache = load_price_cache(cases, a.raw_dir)
    execution_cache = exec_cache(cases, a.raw_dir)

    phase, sec, reproduced_param, signal_audit = signal_scan(a.model, cases, engine_stage, a.stage, feature_cache)
    result: dict[str, Any]
    if phase is None:
        result = {
            "status": "BLOCKED_NO_INDEPENDENTLY_VALIDATED_CONTINUATION_SIGNAL",
            "signal_reproduction": signal_audit,
            "historically_validated_candidate": False,
        }
    else:
        fit = split_cases(cases, ("discovery_fit",))
        tune = split_cases(cases, ("discovery_tune",))
        train = fit + tune
        param = tune_param(a.model, fit, tune, engine_stage, phase, sec, feature_cache, "FULL_CAUSAL", TARGET)
        if param is None or param != reproduced_param:
            raise RuntimeError(f"signal parameter reproduction mismatch stage={a.stage} model={a.model} phase={phase} sec={sec} eval={reproduced_param} trade={param}")
        tune_rows = probability_rows(a.model, param, fit, tune, engine_stage, phase, sec, feature_cache)
        grids = threshold_grid(tune_rows)
        scored = []
        for th in grids:
            for hold in HOLDS:
                for orientation in ORIENTATIONS:
                    rows = candidate(tune_rows, feature_cache, execution_cache, phase, sec, th["probability_threshold"], hold, orientation)
                    s = summary(rows)
                    scored.append({
                        "threshold_quantile": th["quantile"],
                        "probability_threshold": th["probability_threshold"],
                        "hold_seconds": int(hold),
                        "orientation": orientation,
                        "discovery_tune": s,
                    })
        eligible = [
            x for x in scored
            if x["discovery_tune"].get("n", 0) >= TUNE_MIN_N[a.stage]
            and x["discovery_tune"].get("positive_week_fraction_net_1", 0) >= 0.5
        ]
        eligible.sort(key=lambda x: (
            x["discovery_tune"].get("mean_net_1_ticks", -math.inf),
            x["discovery_tune"].get("positive_week_fraction_net_1", -1),
            x["discovery_tune"].get("n", 0),
        ), reverse=True)
        selected = dict(eligible[0]) if eligible else None
        oot = {}
        valid = False
        if selected is not None:
            for block in ("validation", "confirmation", "held"):
                pr = probability_rows(a.model, param, train, split_cases(cases, (block,)), engine_stage, phase, sec, feature_cache)
                tr = candidate(
                    pr, feature_cache, execution_cache, phase, sec,
                    selected["probability_threshold"], selected["hold_seconds"], selected["orientation"],
                )
                oot[block] = summary(tr)
            valid = validate_trade(a.stage, oot)
        result = {
            "status": "MODEL_SPECIFIC_TRADE_AGENT_COMPLETE",
            "signal_phase": phase,
            "signal_seconds": int(sec),
            "signal_timing_interpretation": (
                "LIVE_EXECUTABLE_PRIOR_SIGNAL" if phase == "PRIOR" else
                "HISTORICAL_POST_BIRTH_SIGNAL; LIVE_EXECUTION_REQUIRES_PROVEN_UPSTREAM_EVENT_MARK_TIME"
            ),
            "model_param": param,
            "signal_reproduction": signal_audit,
            "candidate_grid": {
                "threshold_quantiles": list(THRESHOLD_QUANTILES),
                "hold_seconds": list(HOLDS),
                "orientations": list(ORIENTATIONS),
                "future_event_exit_cap": False,
                "target_polarity_direction_source": False,
            },
            "all_discovery_candidates": scored,
            "discovery_selected_candidate": selected,
            "top_discovery_candidates": eligible[:10],
            "frozen_candidate_OOT_blocks": oot,
            "historically_validated_candidate": bool(valid),
            "probability_aggregation": "NONE_MODEL_SPECIFIC_ONLY",
        }

    out = {
        "status": "NG_EXHAUSTION_D0_D3_MODEL_SPECIFIC_TRADE_V3_COMPLETE",
        "date": DATE,
        "implementation_revision": IMPLEMENTATION_REVISION,
        "causal_overlap_fix_revision": CAUSAL_OVERLAP_FIX_REVISION,
        "causal_overlap_policy": CAUSAL_OVERLAP_POLICY,
        "stage": int(a.stage),
        "model": a.model,
        "signal_target": "D0_TERMINALITY" if a.stage == 0 else "CHAIN_CONTINUATION",
        "direction_contract": "CAUSAL_LIVE_MARKET_OR_CONFIRMED_PREDECESSOR_ONLY; REALIZED_TARGET_POLARITY_FORBIDDEN",
        "execution_contract": "FIXED_HORIZON_FROM_CAUSAL_SIGNAL; NO_FUTURE_CANONICAL_EVENT_CAP",
        "entry_fill": "FIRST_AUTHORITATIVE_RAW_TRADE_AT_OR_AFTER_SIGNAL_WITH_MAX_5S_DELAY",
        "exit_fill": "FIRST_AUTHORITATIVE_RAW_TRADE_AT_OR_AFTER_FIXED_HORIZON_WITH_MAX_10S_DELAY",
        "result": result,
        "frozen_exact_depth_counts": dict(sorted(exact.items())),
        "censored_n": int(len(censored)),
        "cross_model_vote_used": False,
        "target_polarity_is_primary_question": False,
        "promotion_performed": False,
        "policy": "FLAG_AND_DECOMPOSE_NOT_AUTO_KILL",
        "protected_mutations": {
            "detector": False, "canonical_rows": False, "phase1": False, "phase2": False,
            "runway_clock": False, "permanent_frankie": False, "frankie_1": False,
            "spawn_py": False, "ssos_play": False,
        },
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": out["status"], "stage": a.stage, "model": a.model,
        "trade_status": result["status"],
        "signal_phase": result.get("signal_phase"),
        "signal_seconds": result.get("signal_seconds"),
        "historically_validated_candidate": result.get("historically_validated_candidate", False),
    }, indent=2))


if __name__ == "__main__":
    main()
