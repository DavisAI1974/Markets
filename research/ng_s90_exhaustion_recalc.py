"""Independent reconstruction of the S90 NG exhaustion canary.

Uses the authoritative raw MBP-10 S3 day (2025-07-17).  It intentionally
computes several nearby interpretations of the scratchpad W/K/F notation so
we can identify the original canary by reproducing the rounded S90 rates,
rather than assuming which averaging convention Claude used.

No Frankie files are read or modified.
"""
from __future__ import annotations

import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

W = 60
K = 30
F = 60
TARGET_OE = 0.410
TARGET_TS = 0.382


def sgn(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def rate(v):
    return sum(v) / len(v) if v else float("nan")


def rolling_mean(a, n):
    out = [float("nan")] * len(a)
    s = 0.0
    q = []
    finite = 0
    for i, x in enumerate(a):
        q.append(x)
        if math.isfinite(x):
            s += x; finite += 1
        if len(q) > n:
            z = q.pop(0)
            if math.isfinite(z):
                s -= z; finite -= 1
        if len(q) == n and finite == n:
            out[i] = s / n
    return out


def parse(path: str):
    sec_sum = defaultdict(float)
    sec_n = defaultdict(int)
    sec_last = {}
    trade_last = {}
    trade_n = 0
    row_n = 0
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            row_n += 1
            t = int(float(r.get("ts_event", r.get("ts", 0.0))))
            bid = sum(float(r.get(f"bid_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
            ask = sum(float(r.get(f"ask_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
            tot = bid + ask
            if tot > 0:
                imb = (bid - ask) / tot
                sec_sum[t] += imb
                sec_n[t] += 1
                sec_last[t] = imb
            if r.get("action") == "T":
                px = float(r.get("price", 0.0) or 0.0)
                if px > 0:
                    trade_last[t] = px
                    trade_n += 1
    lo = min(sec_n)
    hi = max(sec_n)
    secs = list(range(lo, hi + 1))
    mean_imb = [sec_sum[t] / sec_n[t] if sec_n[t] else float("nan") for t in secs]
    last_imb = [sec_last.get(t, float("nan")) for t in secs]
    trade_here = [t in trade_last for t in secs]
    price = []
    lastp = float("nan")
    for t in secs:
        if t in trade_last:
            lastp = trade_last[t]
        price.append(lastp)
    return {
        "secs": secs, "mean": mean_imb, "last": last_imb, "price": price,
        "trade_here": trade_here, "trade_n": trade_n, "row_n": row_n,
    }


def eval_variant(book, price, trade_here, *, agg_name, eval_only_trade, trend_span, exhaustion_mode):
    dip = rolling_mean(book, W)
    cats = {k: [] for k in ("oppose+exhaust", "oppose+strengthen", "withtrend+exhaust", "withtrend+strengthen")}
    static_opp, static_trend = [], []
    details = []
    n = len(price)
    for i in range(max(W, K), n - F):
        if eval_only_trade and not trade_here[i]:
            continue
        if not (math.isfinite(price[i]) and math.isfinite(price[i - trend_span]) and math.isfinite(price[i + F])):
            continue
        pre = price[i] - price[i - trend_span]
        fwd = price[i + F] - price[i]
        if pre == 0 or fwd == 0 or not math.isfinite(dip[i]):
            continue
        aligned = dip[i] * sgn(pre)
        if aligned == 0:
            continue
        opposing = aligned < 0
        rev = sgn(pre) != sgn(fwd)
        static_opp.append(rev) if opposing else static_trend.append(rev)

        if exhaustion_mode == "rolling_vs_lag":
            if i - K < 0 or not math.isfinite(dip[i - K]):
                continue
            exhausting = abs(dip[i]) < abs(dip[i - K])
            early = dip[i - K]
            late = dip[i]
        elif exhaustion_mode == "half_window":
            # direct S36 definition: compare mean imbalance in first K vs last K of the W window.
            if W != 2 * K:
                raise ValueError("half_window requires W=2K")
            x = book[i - W + 1:i + 1]
            if len(x) != W or not all(math.isfinite(z) for z in x):
                continue
            early = sum(x[:K]) / K
            late = sum(x[K:]) / K
            exhausting = abs(late) < abs(early)
        else:
            raise ValueError(exhaustion_mode)

        key = ("oppose" if opposing else "withtrend") + "+" + ("exhaust" if exhausting else "strengthen")
        cats[key].append(rev)
        details.append((key, rev, pre, fwd, early, late, dip[i]))

    r = {k: {"n": len(v), "reversal": rate(v)} for k, v in cats.items()}
    exh = cats["oppose+exhaust"] + cats["withtrend+exhaust"]
    st = cats["oppose+strengthen"] + cats["withtrend+strengthen"]
    r["marginal"] = {
        "exhaust_n": len(exh), "exhaust_reversal": rate(exh),
        "strengthen_n": len(st), "strengthen_reversal": rate(st),
        "exhaust_minus_strengthen_pp": 100 * (rate(exh) - rate(st)),
        "oppose_n": len(static_opp), "oppose_reversal": rate(static_opp),
        "withtrend_n": len(static_trend), "withtrend_reversal": rate(static_trend),
        "static_oppose_minus_withtrend_pp": 100 * (rate(static_opp) - rate(static_trend)),
    }
    oe = r["oppose+exhaust"]["reversal"]
    ts = r["withtrend+strengthen"]["reversal"]
    r["target_distance"] = abs(oe - TARGET_OE) + abs(ts - TARGET_TS) if math.isfinite(oe) and math.isfinite(ts) else 999.0
    r["config"] = {"agg": agg_name, "eval_only_trade": eval_only_trade, "trend_span": trend_span, "exhaustion_mode": exhaustion_mode}
    return r, details


def main(path):
    d = parse(path)
    variants = []
    detail_by_name = {}
    for agg_name in ("mean", "last"):
        for eval_only_trade in (False, True):
            for trend_span in (W, K):
                for mode in ("rolling_vs_lag", "half_window"):
                    r, det = eval_variant(d[agg_name], d["price"], d["trade_here"], agg_name=agg_name,
                                          eval_only_trade=eval_only_trade, trend_span=trend_span,
                                          exhaustion_mode=mode)
                    variants.append(r)
                    detail_by_name[json.dumps(r["config"], sort_keys=True)] = det
    variants.sort(key=lambda x: x["target_distance"])
    best = variants[0]
    best_name = json.dumps(best["config"], sort_keys=True)
    det = detail_by_name[best_name]

    # Wilson intervals and day-halves for the best-reproducing construction.
    def wilson(v):
        n=len(v); p=rate(v)
        if n == 0: return [float("nan"), float("nan")]
        z=1.959963984540054
        den=1+z*z/n
        cen=(p+z*z/(2*n))/den
        half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
        return [cen-half, cen+half]
    best_extra = {}
    for key in ("oppose+exhaust", "oppose+strengthen", "withtrend+exhaust", "withtrend+strengthen"):
        vals=[x[1] for x in det if x[0]==key]
        best_extra[key] = {"n":len(vals), "reversal":rate(vals), "wilson95":wilson(vals)}
    half=len(det)//2
    for label, sub in (("early",det[:half]),("late",det[half:])):
        e=[x[1] for x in sub if x[0].endswith("+exhaust")]
        s=[x[1] for x in sub if x[0].endswith("+strengthen")]
        best_extra[label] = {"exhaust_n":len(e),"exhaust_reversal":rate(e),
                             "strengthen_n":len(s),"strengthen_reversal":rate(s),
                             "lift_pp":100*(rate(e)-rate(s))}

    out = {
        "source": path,
        "raw_rows": d["row_n"],
        "trade_rows": d["trade_n"],
        "seconds": len(d["secs"]),
        "target_from_s90_rounded": {"oppose+exhaust": TARGET_OE, "withtrend+strengthen": TARGET_TS},
        "best_reconstruction": best,
        "best_detail": best_extra,
        "all_variants_ranked": variants,
    }
    Path("ng_s90_exhaustion_recalc_results.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ng.jsonl.gz")
