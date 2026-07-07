"""_s68_tune_kraken.py — S68 per-coin full-stack tuner (findings only; live path untouched).

Drives EVERY config through the LIVE executor exactly like scripts/grade_coin_kraken.py::run_side
and odcore.platform.run_kraken_cell — this file ONLY adds the parameter loop + reporting.
It never re-implements the executor/fill/fees/sizing.

Stack knobs: side, rev, eps (early-arm retime_flips), bail (exit_spec price_stop), grace, improve.
Fee frame: kr_mk0 (maker=0, taker=5, front fill, improve=0.5). Cap=$5000. WFLIP from flip_detector.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.io import load_bins                                          # noqa: E402
from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402
from odcore.platform import run_stream, WFLIP                            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REALBINS = os.path.join(ROOT, "realbins")
CAP = 5000.0
MAKER_FEE, TAKER_FEE = 0.0, 5.0
NWIN = 7


def load_coin(coin):
    p = os.path.join(REALBINS, f"{coin}_kraken_bins.json")
    if not os.path.exists(p):
        return None
    s = load_bins(p)
    mid = np.asarray(s.mid, float)
    hs = float(np.median((s.spread[mid > 0] / mid[mid > 0]) / 2.0) * 1e4) if np.any(mid > 0) else 0.0
    return dict(mid=mid, buy=np.asarray(s.buy, float), sell=np.asarray(s.sell, float),
                hs=hs, n=len(mid), hours=len(mid) / 3600.0)


def _flips(bk, side, rev, eps):
    """Compose the flip stream EXACTLY as odcore.platform.kraken_flips does."""
    if eps is not None:
        flips = retime_flips(bk["mid"], bk["buy"], bk["sell"], WFLIP, rev, eps)[0]
    else:
        flips = detect_flips(lean_series(bk["buy"], bk["sell"], WFLIP), rev)[0]
    if side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    return flips


def run_cfg(bk, side, rev, eps=None, bail=None, grace=300, improve=0.5,
            buy=None, sell=None, mid=None):
    """One full-stack config through the LIVE run_stream, front-of-line, kr_mk0.
    Mirrors run_kraken_cell's threading of eps (retime) + bail (exit_spec price_stop)."""
    b = bk["buy"] if buy is None else buy
    s = bk["sell"] if sell is None else sell
    m = bk["mid"] if mid is None else mid
    if eps is not None:
        flips = retime_flips(m, b, s, WFLIP, rev, eps)[0]
    else:
        flips = detect_flips(lean_series(b, s, WFLIP), rev)[0]
    if side < 0:
        flips = [(c, p, -sg) for (c, p, sg) in flips]
    exit_spec = {"kind": "price_stop", "x_bp": float(bail), "action": "flat", "side": 0} \
        if bail is not None else None
    res, _ = run_stream(m, b, s, flips, half_spread_bps=bk["hs"],
                        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, grace=grace,
                        exit_spec=exit_spec, fill_model="front", close_improve_bps=improve)
    return res


def clip_recent(bk, days):
    """Return a bk restricted to the LAST `days` of tape (same live path; lean_series warmup
    (WFLIP=600s) is negligible vs a multi-day window). Mirrors a trader starting fresh on recent data."""
    if bk is None:
        return None
    keep = int(days * 86400)
    if keep >= bk["n"]:
        return bk
    lo = bk["n"] - keep
    m = bk["mid"][lo:]
    return dict(mid=m, buy=bk["buy"][lo:], sell=bk["sell"][lo:], hs=bk["hs"],
                n=len(m), hours=len(m) / 3600.0)


def dph(res, hours):
    return res.total_net_bps / 1e4 * CAP / hours if hours else 0.0


def base_run_side(bk, side, rev):
    """Bit-identical to grade_coin_kraken.run_side (no eps/bail, grace=300, improve=0.5)."""
    flips, _ = detect_flips(lean_series(bk["buy"], bk["sell"], WFLIP), rev)
    if side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    res, _ = run_stream(bk["mid"], bk["buy"], bk["sell"], flips, half_spread_bps=bk["hs"],
                        maker_fee=MAKER_FEE, taker_fee=TAKER_FEE, grace=300,
                        fill_model="front", close_improve_bps=0.5)
    return res


def shift_null(bk, side, rev, eps, bail, grace, improve, nshift):
    """Circular-shift FLOW null floor for the FULL config (mirrors grade_coin_kraken.shift_null,
    extended to carry eps/bail/grace/improve so the gated config == the recommended config)."""
    n = bk["n"]
    rng = np.random.default_rng(12345)
    out = []
    for _ in range(nshift):
        k = int(rng.integers(n // 10, n - n // 10))
        b2 = np.roll(bk["buy"], k); s2 = np.roll(bk["sell"], k)
        res = run_cfg(bk, side, rev, eps=eps, bail=bail, grace=grace, improve=improve,
                      buy=b2, sell=s2, mid=bk["mid"])
        out.append(dph(res, bk["hours"]))
    return np.asarray(out)


def per_window(bk, side, rev, eps, bail, grace, improve, nwin=NWIN):
    res = run_cfg(bk, side, rev, eps=eps, bail=bail, grace=grace, improve=improve)
    n = bk["n"]; edges = np.linspace(0, n, nwin + 1).astype(int)
    dphs = []
    for i in range(nwin):
        lo, hi = edges[i], edges[i + 1]
        pnl = sum(float(l.net_bps) for l in res.legs if lo <= int(l.close_idx) < hi)
        hrs = (hi - lo) / 3600.0
        dphs.append(pnl / 1e4 * CAP / hrs if hrs else 0.0)
    return np.asarray(dphs)


def halves(bk, side, rev, eps, bail, grace, improve):
    """$/hr on first vs second half (coarse window-fragility read)."""
    w = per_window(bk, side, rev, eps, bail, grace, improve, nwin=2)
    return float(w[0]), float(w[1])
