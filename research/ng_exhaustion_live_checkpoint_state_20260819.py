#!/usr/bin/env python3
from __future__ import annotations

import gzip, json, math, re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import numpy as np

TICK = 0.001
PRICE_LAGS = (1,2,3,5,10,20,30,60,120)
RANGE_WINDOWS = (5,20,60)
FLOW_WINDOWS = (1,3,5,10,20,30,60)
BOOK_LAGS = (0,1,2,3,5,10,20,30,60)
DENSE_PATH_SECONDS = 60
DENSE_BOOK_SECONDS = 20
POLICY = "USE_OBSERVED_PRICE_DIRECTION_DENSE_PRICE_PATH_DENSE_ROLL20_DIPOLE_PATH_FLOW_BOOK_PATH_AND_CLOCK_STATE_THROUGH_EACH_CHECKPOINT_WITHOUT_REQUIRING_TARGET_POLARITY_OR_TARGET_CONFIRMATION"


def _day(p: Path):
    m = re.search(r"(20\d{6})", p.name)
    if not m:
        raise RuntimeError(f"cannot parse raw day {p}")
    return m.group(1)


def _from_dict(d):
    if not d:
        return np.empty(0,float), np.empty(0,float)
    ks = np.asarray(sorted(d), float)
    return ks, np.asarray([d[int(k)] for k in ks], float)


def load_week(raw_dir: str, week: str):
    """Collapse raw tape to causal one-second sufficient state."""
    sun = datetime.strptime(week, "%Y%m%d")
    price_last = {}
    flow_signed = defaultdict(float)
    flow_abs = defaultdict(float)
    book_sum = defaultdict(float)
    book_n = defaultdict(int)
    book_last = {}

    for p in sorted(Path(raw_dir).glob("NG_*.jsonl.gz")):
        di = (datetime.strptime(_day(p), "%Y%m%d") - sun).days
        if di < 0 or di > 5:
            continue
        with gzip.open(p, "rt") as f:
            for line in f:
                r = json.loads(line)
                try:
                    ts = float(r.get("ts_event", r.get("ts")))
                except Exception:
                    continue
                sec = di * 86400 + (int(ts) % 86400)

                bid = sum(float(r.get(f"bid_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
                ask = sum(float(r.get(f"ask_sz_{j:02d}", 0.0) or 0.0) for j in range(10))
                if bid + ask > 0:
                    imb = (bid - ask) / (bid + ask)
                    book_sum[sec] += imb
                    book_n[sec] += 1
                    book_last[sec] = imb

                if r.get("action") != "T":
                    continue
                try:
                    px = float(r.get("price", 0.0) or 0.0)
                except Exception:
                    px = 0.0
                if px > 0:
                    price_last[sec] = px
                try:
                    sz = float(r.get("size", r.get("qty", 0.0)) or 0.0)
                    b0 = float(r.get("bid_px_00", 0.0) or 0.0)
                    a0 = float(r.get("ask_px_00", 0.0) or 0.0)
                except Exception:
                    continue
                if not (px > 0 and sz > 0 and b0 > 0 and a0 > 0 and a0 >= b0):
                    continue
                mid = 0.5 * (b0 + a0)
                if px > mid:
                    flow_signed[sec] += sz; flow_abs[sec] += sz
                elif px < mid:
                    flow_signed[sec] -= sz; flow_abs[sec] += sz

    pt, pv = _from_dict(price_last)
    ft, fs = _from_dict(flow_signed)
    _, fa = _from_dict(flow_abs)
    book_avg = {s: book_sum[s] / book_n[s] for s in book_n}
    bt, ba = _from_dict(book_avg)
    _, bl = _from_dict(book_last)
    if len(pt) == 0:
        raise RuntimeError(f"no authoritative NG trades week={week}")
    return {
        "times": pt, "prices": pv,
        "flow_times": ft, "flow_signed": fs, "flow_abs": fa,
        "book_times": bt, "book_avg": ba, "book_last": bl,
        "first_trade": float(pt[0]), "last_trade": float(pt[-1]),
    }


def load_cache(cases, raw_dir: str):
    keys = ("times","prices","flow_times","flow_signed","flow_abs","book_times","book_avg","book_last","first_trade","last_trade")
    c = {k:{} for k in keys}
    for w in sorted({x["week"] for x in cases}):
        q = load_week(raw_dir, w)
        for k in keys:
            c[k][w] = q[k]
    return c


def last_at(t, v, x):
    j = int(np.searchsorted(t, float(x), side="right")) - 1
    return None if j < 0 else float(v[j])


def book_at(cache, w, sec):
    t = cache["book_times"][w]
    if len(t) == 0:
        return None
    j = int(np.searchsorted(t, float(sec), side="left"))
    if j < len(t) and int(t[j]) == int(sec):
        return float(cache["book_avg"][w][j])
    j -= 1
    return None if j < 0 else float(cache["book_last"][w][j])


def flow_ratio(cache, w, lo, hi):
    t = cache["flow_times"][w]; s = cache["flow_signed"][w]; a = cache["flow_abs"][w]
    i = int(np.searchsorted(t, float(lo), side="left")); j = int(np.searchsorted(t, float(hi), side="right"))
    if j <= i:
        return 0.0, 0.0, 0.0, 0.0
    signed = float(np.sum(s[i:j])); total = float(np.sum(a[i:j])); ratio = signed / total if total > 0 else 0.0
    return 1.0, signed, total, ratio


def parts(cache, w: str, cutoff: int):
    t = cache["times"][w]; p = cache["prices"][w]
    now = last_at(t, p, cutoff)
    if now is None:
        raise RuntimeError(f"no causal price week={w} cutoff={cutoff}")

    price = [1.0, math.log(max(now, 1e-12))]
    for lag in PRICE_LAGS:
        q = last_at(t, p, cutoff - lag)
        price += [0.0,0.0] if q is None else [1.0, math.asinh((now-q)/TICK)]
    for win in RANGE_WINDOWS:
        start = cutoff - win + 1
        q = last_at(t, p, start)
        i = int(np.searchsorted(t, float(start), side="left")); j = int(np.searchsorted(t, float(cutoff), side="right"))
        if q is None:
            price += [0.0] * 5
            continue
        seg = np.concatenate((np.asarray([q]), p[i:j])) if j > i else np.asarray([q])
        hi = float(np.max(seg)); lo = float(np.min(seg))
        price += [1.0, math.asinh((now-q)/TICK), math.asinh((hi-q)/TICK), math.asinh((lo-q)/TICK), math.asinh((hi-lo)/TICK)]

    # Dense causal one-second price path over the last minute. This is raw market
    # direction, not target-polarity-oriented direction.
    pbase = last_at(t, p, cutoff - DENSE_PATH_SECONDS)
    for sec in range(cutoff - DENSE_PATH_SECONDS, cutoff + 1):
        q = last_at(t, p, sec)
        if pbase is None or q is None:
            price += [0.0, 0.0]
        else:
            price += [1.0, math.asinh((q - pbase) / TICK)]

    micro = []
    for win in FLOW_WINDOWS:
        known, signed, total, ratio = flow_ratio(cache, w, cutoff-win+1, cutoff)
        micro += [known, math.asinh(signed), math.asinh(total), ratio]
    _,_,_,cur20 = flow_ratio(cache, w, cutoff-19, cutoff)
    _,_,_,prev20 = flow_ratio(cache, w, cutoff-39, cutoff-20)
    micro += [cur20, prev20, cur20-prev20, abs(cur20)]

    # Exact causal roll-20 path over the last 61 seconds. This is the live shape
    # from which exhaustion polarity/family can later be inferred when an event is marked.
    for sec in range(cutoff - DENSE_PATH_SECONDS, cutoff + 1):
        known, _, _, ratio = flow_ratio(cache, w, sec-19, sec)
        micro += [known, ratio]

    hist = {}
    for lag in BOOK_LAGS:
        q = book_at(cache, w, cutoff-lag); hist[lag] = q
        micro += [0.0,0.0] if q is None else [1.0,q]
    bnow = hist[0]
    for lag in (5,20,60):
        q = hist[lag]
        micro += [0.0,0.0] if bnow is None or q is None else [1.0,bnow-q]

    # Dense recent book path keeps the evolving microstructure visible rather than
    # reducing it to a single confirmation-time value.
    for sec in range(cutoff - DENSE_BOOK_SECONDS, cutoff + 1):
        q = book_at(cache, w, sec)
        micro += [0.0,0.0] if q is None else [1.0,q]

    hour = (float(cutoff) % 86400.0) / 3600.0; th = 2 * math.pi * hour / 24.0
    first = float(cache["first_trade"][w])
    micro += [math.sin(th), math.cos(th), math.asinh(max(0.0,float(cutoff)-first)/3600.0), max(0.0,min(1.0,float(cutoff)/(6*86400.0)))]
    return price, micro
