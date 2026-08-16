"""Continuous/event-level NG dipole exhaustion audit.

Purpose: evaluate whether book-imbalance collapse toward balance supplies an independent
live reversal/authority discriminator without reducing the result to one pooled binary average.

Fixed concept (from S36/S90): compare adjacent halves of a 60s window.  Positive collapse
means the absolute 10-level book imbalance is smaller in the last 30s than in the first 30s.

Primary outputs:
- collapse-strength quintiles -> forward reversal probability AND magnitude;
- the same curves inside flow-opposed vs flow-confirming states;
- non-overlapping extreme-collapse vs strengthening episodes;
- per-day results first, then equal-weight per-day summaries (never volume-weighted pooling).

This is research only and does not touch Frankie.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median

WINDOW = 60
HALF = 30
HORIZONS = (15, 30, 60, 120)
MIN_PRE_TICKS = 1.0
TICK = 0.001
EPS = 1e-9


def sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def quantile(xs, q):
    a = sorted(float(x) for x in xs if math.isfinite(float(x)))
    if not a:
        return float("nan")
    if len(a) == 1:
        return a[0]
    z = q * (len(a) - 1)
    i = int(math.floor(z)); j = min(i + 1, len(a) - 1); w = z - i
    return a[i] * (1 - w) + a[j] * w


def summarize_outcomes(rows):
    if not rows:
        return {"n": 0}
    rev = [r["signed_reversal_ticks"] > 0 for r in rows]
    mag = [r["signed_reversal_ticks"] for r in rows]
    return {
        "n": len(rows),
        "reversal_rate": mean(rev),
        "mean_signed_reversal_ticks": mean(mag),
        "median_signed_reversal_ticks": median(mag),
        "q25_signed_reversal_ticks": quantile(mag, 0.25),
        "q75_signed_reversal_ticks": quantile(mag, 0.75),
        "mean_abs_forward_ticks": mean([abs(r["future_ticks"]) for r in rows]),
    }


def rankdata(xs):
    # average ranks for ties, numpy/scipy-free.
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    k = 0
    while k < len(order):
        j = k + 1
        while j < len(order) and xs[order[j]] == xs[order[k]]:
            j += 1
        r = 0.5 * (k + j - 1) + 1.0
        for p in range(k, j):
            ranks[order[p]] = r
        k = j
    return ranks


def corr(x, y):
    if len(x) < 3 or len(x) != len(y):
        return float("nan")
    mx, my = mean(x), mean(y)
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(vx * vy)


@dataclass
class DaySeries:
    day: str
    imbalance_last: list[float]
    imbalance_mean: list[float]
    price: list[float]
    rows: int
    trades: int


def load_day(path: str) -> DaySeries:
    # Epoch-day raw files are exactly UTC days. Keep 86400 fixed slots.
    sec_sum = [0.0] * 86400
    sec_n = [0] * 86400
    sec_last = [float("nan")] * 86400
    trade_last = [float("nan")] * 86400
    rows = trades = 0
    day = Path(path).stem.split("_")[-1].split(".")[0]
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line); rows += 1
            ts = float(r.get("ts_event", r.get("ts", 0.0)))
            sec = int(ts) % 86400
            bid = sum(float(r.get(f"bid_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
            ask = sum(float(r.get(f"ask_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
            tot = bid + ask
            if tot > 0:
                imb = (bid - ask) / tot
                sec_sum[sec] += imb; sec_n[sec] += 1; sec_last[sec] = imb
            if r.get("action") == "T":
                px = float(r.get("price", 0.0) or 0.0)
                if px > 0:
                    trade_last[sec] = px; trades += 1

    # A book state persists until changed; same for last trade. Forward-fill physically persistent states.
    last_i = float("nan"); last_p = float("nan")
    imb_last = []
    imb_mean = []
    price = []
    for s in range(86400):
        if math.isfinite(sec_last[s]):
            last_i = sec_last[s]
        if math.isfinite(trade_last[s]):
            last_p = trade_last[s]
        imb_last.append(last_i)
        imb_mean.append(sec_sum[s] / sec_n[s] if sec_n[s] else last_i)
        price.append(last_p)
    return DaySeries(day, imb_last, imb_mean, price, rows, trades)


def build_rows(book, price, horizon):
    out = []
    for t in range(WINDOW - 1, 86400 - horizon):
        if not (math.isfinite(price[t - WINDOW + 1]) and math.isfinite(price[t]) and math.isfinite(price[t + horizon])):
            continue
        early = book[t - WINDOW + 1:t - HALF + 1]
        late = book[t - HALF + 1:t + 1]
        if len(early) != HALF or len(late) != HALF or not all(math.isfinite(x) for x in early + late):
            continue
        ie = mean(early); il = mean(late)
        pre_ticks = (price[t] - price[t - WINDOW + 1]) / TICK
        if abs(pre_ticks) < MIN_PRE_TICKS:
            continue
        future_ticks = (price[t + horizon] - price[t]) / TICK
        if future_ticks == 0:
            continue
        # Positive = absolute leader imbalance contracted; normalized so different depth regimes compare.
        collapse = (abs(ie) - abs(il)) / (abs(ie) + EPS)
        aligned = il * sign(pre_ticks)
        out.append({
            "t": t,
            "collapse": collapse,
            "early_imb": ie,
            "late_imb": il,
            "aligned": aligned,
            "state": "oppose" if aligned < 0 else "withtrend",
            "pre_ticks": pre_ticks,
            "future_ticks": future_ticks,
            "signed_reversal_ticks": -sign(pre_ticks) * future_ticks,
        })
    return out


def quintile_curve(rows):
    if len(rows) < 20:
        return {}
    cuts = [quantile([r["collapse"] for r in rows], q) for q in (0.2, 0.4, 0.6, 0.8)]
    bins = [[] for _ in range(5)]
    for r in rows:
        q = 0
        while q < 4 and r["collapse"] > cuts[q]:
            q += 1
        bins[q].append(r)
    return {
        f"Q{i+1}": {"collapse_mean": mean([r["collapse"] for r in b]), **summarize_outcomes(b)}
        for i, b in enumerate(bins)
    }


def extreme_episodes(rows, refractory=60):
    if len(rows) < 50:
        return {"collapse": [], "strengthen": []}
    hi = quantile([r["collapse"] for r in rows], 0.80)
    lo = quantile([r["collapse"] for r in rows], 0.20)
    by_t = {r["t"]: r for r in rows}
    events = {"collapse": [], "strengthen": []}
    last = {"collapse": -10**9, "strengthen": -10**9}
    for r in rows:
        t = r["t"]
        # Local 11-second extremum so adjacent seconds are one episode, then refractory.
        neigh = [by_t[u]["collapse"] for u in range(t - 5, t + 6) if u in by_t]
        if r["collapse"] >= hi and r["collapse"] == max(neigh) and t - last["collapse"] >= refractory:
            events["collapse"].append(r); last["collapse"] = t
        if r["collapse"] <= lo and r["collapse"] == min(neigh) and t - last["strengthen"] >= refractory:
            events["strengthen"].append(r); last["strengthen"] = t
    return events


def day_audit(ds: DaySeries, book_name: str, horizon: int):
    book = ds.imbalance_last if book_name == "last" else ds.imbalance_mean
    rows = build_rows(book, ds.price, horizon)
    if not rows:
        return {"n": 0}
    x = [r["collapse"] for r in rows]
    y = [r["signed_reversal_ticks"] for r in rows]
    yrank = rankdata(y); xrank = rankdata(x)
    episodes = extreme_episodes(rows)
    out = {
        "n": len(rows),
        "collapse_vs_signed_reversal_pearson": corr(x, y),
        "collapse_vs_signed_reversal_spearman": corr(xrank, yrank),
        "all": summarize_outcomes(rows),
        "quintiles": quintile_curve(rows),
        "by_state": {},
        "episodes": {
            "collapse": summarize_outcomes(episodes["collapse"]),
            "strengthen": summarize_outcomes(episodes["strengthen"]),
        },
    }
    ec = out["episodes"]["collapse"]; es = out["episodes"]["strengthen"]
    if ec.get("n", 0) and es.get("n", 0):
        out["episodes"]["collapse_minus_strengthen_reversal_pp"] = 100 * (ec["reversal_rate"] - es["reversal_rate"])
        out["episodes"]["collapse_minus_strengthen_mean_signed_ticks"] = ec["mean_signed_reversal_ticks"] - es["mean_signed_reversal_ticks"]
    for state in ("oppose", "withtrend"):
        z = [r for r in rows if r["state"] == state]
        out["by_state"][state] = {
            "n": len(z),
            "quintiles": quintile_curve(z),
            "pearson": corr([r["collapse"] for r in z], [r["signed_reversal_ticks"] for r in z]) if z else float("nan"),
            "spearman": corr(rankdata([r["collapse"] for r in z]), rankdata([r["signed_reversal_ticks"] for r in z])) if z else float("nan"),
        }
    q = out["quintiles"]
    if q and q["Q1"].get("n", 0) and q["Q5"].get("n", 0):
        out["Q5_minus_Q1_reversal_pp"] = 100 * (q["Q5"]["reversal_rate"] - q["Q1"]["reversal_rate"])
        out["Q5_minus_Q1_mean_signed_ticks"] = q["Q5"]["mean_signed_reversal_ticks"] - q["Q1"]["mean_signed_reversal_ticks"]
    return out


def main(paths):
    days = [load_day(p) for p in paths]
    result = {
        "definition": {
            "window_s": WINDOW,
            "half_s": HALF,
            "collapse": "(|mean_imb first30|-|mean_imb last30|)/(|mean_imb first30|+eps)",
            "positive_means": "book leader weakens toward balance",
            "min_pre_move_ticks": MIN_PRE_TICKS,
            "outcome": "signed reversal ticks = -sign(prior60s move) * forward move",
            "independence_control": "extreme episodes use local extrema + 60s refractory",
        },
        "days": {},
        "equal_weight_day_summary": {},
    }
    for d in days:
        day = {"raw_rows": d.rows, "trade_rows": d.trades, "books": {}}
        for book_name in ("last", "mean"):
            day["books"][book_name] = {}
            for h in HORIZONS:
                day["books"][book_name][str(h)] = day_audit(d, book_name, h)
        result["days"][d.day] = day

    # Equal-weight by day: each date gets one vote, avoiding a busy session dominating.
    for book_name in ("last", "mean"):
        result["equal_weight_day_summary"][book_name] = {}
        for h in HORIZONS:
            vals = []
            eps = []
            for d in days:
                a = result["days"][d.day]["books"][book_name][str(h)]
                if "Q5_minus_Q1_reversal_pp" in a:
                    vals.append(a["Q5_minus_Q1_reversal_pp"])
                e = a.get("episodes", {}).get("collapse_minus_strengthen_reversal_pp")
                if e is not None and math.isfinite(e):
                    eps.append(e)
            result["equal_weight_day_summary"][book_name][str(h)] = {
                "days": len(vals),
                "Q5_minus_Q1_reversal_pp_mean": mean(vals),
                "Q5_minus_Q1_reversal_pp_median": median(vals) if vals else float("nan"),
                "Q5_gt_Q1_day_fraction": mean([v > 0 for v in vals]) if vals else float("nan"),
                "episode_collapse_minus_strengthen_reversal_pp_mean": mean(eps),
                "episode_positive_day_fraction": mean([v > 0 for v in eps]) if eps else float("nan"),
            }

    out = Path("ng_dipole_state_audit_results.json")
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("pass one or more raw NG day .jsonl.gz files")
    main(sys.argv[1:])
