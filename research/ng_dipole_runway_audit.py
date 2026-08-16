"""NG onset->exhaustion live-tail structural audit (scratch research only).

Question: once a directional NG leg is underway, do current sign-aligned dipole
mean-flow authority and its dive from onset tell us whether the leg still has
runway 20 seconds later?

This deliberately does NOT reuse the old S36 binary exhaustion rule. Directional
legs are retrospective ZigZag labels used only as outcomes; all dipole features
at age A use data available at or before onset+A. We sweep several NG-native
reversal tolerances so no conclusion depends on one imported crypto threshold.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median

TICK = 0.001
THRESH_TICKS = (2, 3, 5, 8, 13)
AGES = (20, 30)
TAIL = 20
FLOW_WIN = 60
MIN_N = 20


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def quantile(xs, q):
    a = sorted(float(x) for x in xs if math.isfinite(float(x)))
    if not a:
        return float("nan")
    if len(a) == 1:
        return a[0]
    z = q * (len(a) - 1)
    i = int(math.floor(z))
    j = min(i + 1, len(a) - 1)
    w = z - i
    return a[i] * (1 - w) + a[j] * w


def rankdata(xs):
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


def auc(scores, labels):
    pairs = [(float(s), int(y)) for s, y in zip(scores, labels) if math.isfinite(float(s))]
    pos = sum(y for _, y in pairs)
    neg = len(pairs) - pos
    if pos == 0 or neg == 0:
        return float("nan")
    rs = rankdata([s for s, _ in pairs])
    rpos = sum(r for r, (_, y) in zip(rs, pairs) if y)
    return (rpos - pos * (pos + 1) / 2) / (pos * neg)


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
class Day:
    day: str
    book: list[float]
    price: list[float]
    buy_vol: list[float]
    sell_vol: list[float]
    rows: int
    trades: int
    lr_classified: int
    lr_midpoint_skipped: int
    lr_no_book_skipped: int


def load_day(path):
    bsum = [0.0] * 86400
    bn = [0] * 86400
    blast = [float("nan")] * 86400
    plast = [float("nan")] * 86400
    buy = [0.0] * 86400
    sell = [0.0] * 86400
    rows = trades = classified = midpoint_skip = nobook_skip = 0
    day = Path(path).stem.split("_")[-1].split(".")[0]

    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            rows += 1
            ts = float(r.get("ts_event", r.get("ts", 0.0)))
            sec = int(ts) % 86400
            bid_sz = sum(float(r.get(f"bid_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
            ask_sz = sum(float(r.get(f"ask_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
            tot = bid_sz + ask_sz
            if tot > 0:
                imb = (bid_sz - ask_sz) / tot
                bsum[sec] += imb
                bn[sec] += 1
                blast[sec] = imb

            if r.get("action") == "T":
                trades += 1
                px = float(r.get("price", 0.0) or 0.0)
                if px > 0:
                    plast[sec] = px
                sz = float(r.get("size", r.get("qty", 0.0)) or 0.0)
                bid0 = float(r.get("bid_px_00", 0.0) or 0.0)
                ask0 = float(r.get("ask_px_00", 0.0) or 0.0)
                if not (px > 0 and sz > 0 and bid0 > 0 and ask0 > 0 and ask0 >= bid0):
                    nobook_skip += 1
                    continue
                mid = 0.5 * (bid0 + ask0)
                if px > mid:
                    buy[sec] += sz
                    classified += 1
                elif px < mid:
                    sell[sec] += sz
                    classified += 1
                else:
                    midpoint_skip += 1

    book = []
    price = []
    li = lp = float("nan")
    for s in range(86400):
        if math.isfinite(blast[s]):
            li = blast[s]
        if math.isfinite(plast[s]):
            lp = plast[s]
        book.append(bsum[s] / bn[s] if bn[s] else li)
        price.append(lp)
    return Day(day, book, price, buy, sell, rows, trades, classified, midpoint_skip, nobook_skip)


def zigzag_legs(price, threshold_ticks):
    """Retrospective pivot-to-pivot directional legs on 1s ffilled trade price."""
    thr = threshold_ticks * TICK
    valid = [i for i, p in enumerate(price) if math.isfinite(p)]
    if len(valid) < 3:
        return []
    first = valid[0]
    hi = lo = price[first]
    hi_i = lo_i = first
    mode = 0
    pivots = []
    for i in valid[1:]:
        p = price[i]
        if mode == 0:
            if p > hi:
                hi, hi_i = p, i
            if p < lo:
                lo, lo_i = p, i
            if hi - lo >= thr:
                if hi_i > lo_i:
                    pivots.append((lo_i, lo))
                    mode = 1
                    hi, hi_i = p, i
                else:
                    pivots.append((hi_i, hi))
                    mode = -1
                    lo, lo_i = p, i
        elif mode == 1:
            if p > hi:
                hi, hi_i = p, i
            if hi - p >= thr:
                pivots.append((hi_i, hi))
                mode = -1
                lo, lo_i = p, i
        else:
            if p < lo:
                lo, lo_i = p, i
            if p - lo >= thr:
                pivots.append((lo_i, lo))
                mode = 1
                hi, hi_i = p, i
    if mode == 1:
        pivots.append((hi_i, hi))
    elif mode == -1:
        pivots.append((lo_i, lo))

    legs = []
    for (i0, p0), (i1, p1) in zip(pivots, pivots[1:]):
        if i1 <= i0 or p1 == p0:
            continue
        d = 1 if p1 > p0 else -1
        legs.append({"start": i0, "end": i1, "dir": d, "duration": i1 - i0,
                     "ticks": abs(p1 - p0) / TICK})
    return legs


def flow_imb(day, t):
    lo = max(0, t - FLOW_WIN + 1)
    b = sum(day.buy_vol[lo:t + 1])
    s = sum(day.sell_vol[lo:t + 1])
    tot = b + s
    return (b - s) / tot if tot > 0 else float("nan")


def book_state(day, t):
    lo = max(0, t - FLOW_WIN + 1)
    z = [x for x in day.book[lo:t + 1] if math.isfinite(x)]
    return mean(z) if z else float("nan")


def leg_rows(day, threshold_ticks, age, source):
    rows = []
    for leg in zigzag_legs(day.price, threshold_ticks):
        if leg["duration"] < age:
            continue
        start = leg["start"]
        now = start + age
        end = leg["end"]
        d = leg["dir"]
        if source == "flow":
            onset_raw = flow_imb(day, start)
            current_raw = flow_imb(day, now)
        else:
            onset_raw = book_state(day, start)
            current_raw = book_state(day, now)
        if not (math.isfinite(onset_raw) and math.isfinite(current_raw)):
            continue
        onset = d * onset_raw
        current = d * current_raw
        dive = onset - current
        rows.append({
            "day": day.day,
            "threshold_ticks": threshold_ticks,
            "age": age,
            "source": source,
            "duration": leg["duration"],
            "remaining": max(0, end - now),
            "alive_tail": 1 if end >= now + TAIL else 0,
            "onset_authority": onset,
            "current_authority": current,
            "dive": dive,
            "leg_ticks": leg["ticks"],
        })
    return rows


def summarize(rows):
    if len(rows) < MIN_N:
        return {"n": len(rows)}
    y = [r["alive_tail"] for r in rows]
    cur = [r["current_authority"] for r in rows]
    less_dive = [-r["dive"] for r in rows]
    rc = rankdata(cur)
    rd = rankdata(less_dive)
    combo = [(a + b) / 2 for a, b in zip(rc, rd)]

    cuts = [quantile(cur, q) for q in (0.2, 0.4, 0.6, 0.8)]
    bins = [[] for _ in range(5)]
    for r in rows:
        q = 0
        while q < 4 and r["current_authority"] > cuts[q]:
            q += 1
        bins[q].append(r)
    qsum = {}
    for i, b in enumerate(bins):
        qsum[f"Q{i + 1}"] = {
            "n": len(b),
            "current_mean": mean([r["current_authority"] for r in b]),
            "alive_20s_rate": mean([r["alive_tail"] for r in b]),
            "median_remaining_s": median([r["remaining"] for r in b]) if b else float("nan"),
        }

    return {
        "n": len(rows),
        "alive_rate": mean(y),
        "auc_current_authority": auc(cur, y),
        "auc_less_dive": auc(less_dive, y),
        "auc_rank_combo": auc(combo, y),
        "corr_current_remaining_s": corr(cur, [r["remaining"] for r in rows]),
        "corr_dive_remaining_s": corr([r["dive"] for r in rows], [r["remaining"] for r in rows]),
        "Q5_minus_Q1_alive_pp": 100 * (qsum["Q5"]["alive_20s_rate"] - qsum["Q1"]["alive_20s_rate"]),
        "Q5_minus_Q1_median_remaining_s": qsum["Q5"]["median_remaining_s"] - qsum["Q1"]["median_remaining_s"],
        "quintiles": qsum,
    }


def main(paths):
    days = [load_day(p) for p in paths]
    out = {
        "definition": {
            "question": "At age A into an NG directional leg, do current sign-aligned dipole authority and its dive from onset predict that the leg remains alive 20s later?",
            "ages_s": AGES,
            "tail_s": TAIL,
            "rolling_flow_window_s": FLOW_WIN,
            "zigzag_threshold_ticks": THRESH_TICKS,
            "flow_dipole": "direction-aligned 60s signed trade-volume imbalance; trade sign inferred causally from price vs concurrent top-of-book mid",
            "book_companion": "direction-aligned 60s mean 10-level MBP imbalance",
            "dive": "onset authority - current authority; positive means loss of directional authority",
            "threshold_policy": "sweep multiple NG-native reversal tolerances; no imported crypto cutoff",
            "label_note": "ZigZag start/end are retrospective structural labels. At a tested age, survival to that age is observable; all dipole features use data <= that age.",
            "combo_note": "rank-average(current authority, less dive), no outcome-fitted weights",
        },
        "day_meta": {},
        "results": {},
        "equal_weight_day": {},
    }
    allrows = {}
    for d in days:
        out["day_meta"][d.day] = {
            "raw_rows": d.rows,
            "trade_rows": d.trades,
            "lee_ready_classified": d.lr_classified,
            "midpoint_trades_skipped": d.lr_midpoint_skipped,
            "no_book_trades_skipped": d.lr_no_book_skipped,
            "classified_fraction": d.lr_classified / d.trades if d.trades else float("nan"),
        }
        for src in ("flow", "book"):
            for th in THRESH_TICKS:
                for age in AGES:
                    key = f"{src}|{th}t|age{age}"
                    rs = leg_rows(d, th, age, src)
                    allrows.setdefault(key, []).extend(rs)
                    out["results"].setdefault(key, {})[d.day] = summarize(rs)

    for key, rs in allrows.items():
        out["results"][key]["ALL_POOLED"] = summarize(rs)
        vals = []
        for d in days:
            s = out["results"][key].get(d.day, {})
            if s.get("n", 0) >= MIN_N and "auc_current_authority" in s:
                vals.append(s)
        if vals:
            out["equal_weight_day"][key] = {
                "days": len(vals),
                "auc_current_authority_mean": mean([v["auc_current_authority"] for v in vals]),
                "auc_less_dive_mean": mean([v["auc_less_dive"] for v in vals]),
                "auc_rank_combo_mean": mean([v["auc_rank_combo"] for v in vals]),
                "Q5_minus_Q1_alive_pp_mean": mean([v["Q5_minus_Q1_alive_pp"] for v in vals]),
                "Q5_minus_Q1_median_remaining_s_mean": mean([v["Q5_minus_Q1_median_remaining_s"] for v in vals]),
                "authority_auc_gt_0_5_day_fraction": mean([v["auc_current_authority"] > 0.5 for v in vals]),
                "less_dive_auc_gt_0_5_day_fraction": mean([v["auc_less_dive"] > 0.5 for v in vals]),
                "combo_auc_gt_0_5_day_fraction": mean([v["auc_rank_combo"] > 0.5 for v in vals]),
            }

    p = Path("ng_dipole_runway_audit_results.json")
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out["day_meta"], indent=2, sort_keys=True))
    print(json.dumps(out["equal_weight_day"], indent=2, sort_keys=True))
    print(f"RESULT_FILE={p}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("pass one or more raw NG day .jsonl.gz files")
    main(sys.argv[1:])
