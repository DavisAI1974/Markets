"""_series_tools.py: series loader, zigzag pivots and trailing order-flow imbalance.

Measurement helpers only (no cost, fee or fill term). Carried over unchanged from the removed
_info_dipole_swing_backtest.py for the leakage and incremental canaries and the timing test.
"""
from __future__ import annotations

import glob
import json

import numpy as np


def load_series(source="testbars"):
    """Return {venue: (ts, close, buy_vol, sell_vol)} from either source.

    source='testbars' : fingerprint_dataset/test_bars/*.json  (1-min bars, 2026-05-23..24).
    source='realbins'  : realbins/*_bins.json                 (1-SEC bins, the format the live collectors
                          write — dict keyed by ts, each {buy, sell, mid, ...}). This is the live-ready path.
    """
    out = {}
    if source == "testbars":
        for fp in glob.glob("fingerprint_dataset/test_bars/*.json"):
            d = json.load(open(fp)); a, v = d["asset"].lower(), d["venue"].lower()
            B = sorted(d["bars"], key=lambda b: b["ts"])
            out[f"{a}_{v}"] = (np.array([b["ts"] for b in B], float),
                               np.array([b["close"] for b in B], float),
                               np.array([b.get("buy_vol", 0.) for b in B], float),
                               np.array([b.get("sell_vol", 0.) for b in B], float))
    elif source == "realbins":
        for fp in sorted(glob.glob("realbins/*_bins.json")):
            name = fp.split("/")[-1].replace("_bins.json", "")     # e.g. btc_bybit_perp
            d = json.load(open(fp))
            ks = sorted(d.keys(), key=float)
            ts = np.array([float(k) for k in ks], float)
            close = np.array([d[k].get("mid") or d[k].get("close") or 0.0 for k in ks], float)
            buy = np.array([d[k].get("buy", 0.0) for k in ks], float)
            sell = np.array([d[k].get("sell", 0.0) for k in ks], float)
            ok = close > 0                                          # drop any bins with no price
            out[name] = (ts[ok], close[ok], buy[ok], sell[ok])
    else:
        raise ValueError(f"unknown source {source!r}")
    return out


def zigzag(p, theta):
    """True peaks/valleys: a pivot is confirmed once price reverses by `theta` (fraction) off the extreme.

    Returns list of (idx, 'H'|'L') at the actual extreme bars (oracle uses these exact tops/bottoms).
    """
    piv = []
    n = len(p)
    if n < 2:
        return piv
    mode = 0                 # 0 unknown, +1 in up-leg (seeking a High), -1 in down-leg (seeking a Low)
    ext_i, ext_v = 0, p[0]
    for i in range(1, n):
        if mode == 0:        # unknown: p[0] is the implicit first pivot; first theta move sets direction
            if p[i] >= p[0] * (1 + theta):
                piv.append((0, "L")); mode = 1; ext_i, ext_v = i, p[i]
            elif p[i] <= p[0] * (1 - theta):
                piv.append((0, "H")); mode = -1; ext_i, ext_v = i, p[i]
        elif mode == 1:      # up-leg: track the running high; confirm peak on a theta reversal down
            if p[i] > ext_v:
                ext_i, ext_v = i, p[i]
            elif p[i] <= ext_v * (1 - theta):
                piv.append((ext_i, "H")); mode = -1; ext_i, ext_v = i, p[i]
        else:                # down-leg: track the running low; confirm valley on a theta reversal up
            if p[i] < ext_v:
                ext_i, ext_v = i, p[i]
            elif p[i] >= ext_v * (1 + theta):
                piv.append((ext_i, "L")); mode = 1; ext_i, ext_v = i, p[i]
    return piv


def trailing_imbalance(ts, bv, sv, win_s):
    """Per-bar order-flow imbalance over the trailing win_s window (vectorized via cumsum + searchsorted)."""
    cb = np.concatenate([[0.0], np.cumsum(bv)])
    cs = np.concatenate([[0.0], np.cumsum(sv)])
    lo = np.searchsorted(ts, ts - win_s, side="left")
    idx = np.arange(len(ts)) + 1
    B = cb[idx] - cb[lo]; S = cs[idx] - cs[lo]
    tot = B + S
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(tot > 0, (B - S) / np.where(tot > 0, tot, 1.0), 0.0)
