"""_trend_gate.py — S41: PRICE is primary; the dipole is an ADDITIVE filter to cut false signals.

Greg (load-bearing): PRICE is the most important thing in a trade. The problem was a bunch of
FALSE signals (price turns firing on every little wiggle). The dipole trend-line / midline /
fast-deep override is an ADDITION on top of the price signal to REMOVE those false signals --
not a replacement for price.

ARCHITECTURE:
  PRIMARY  = price turns (ZigZag pivots on mid). low pivot -> candidate LONG, high pivot -> SHORT.
             This is the timing + the move we capture (S40: 1-sec price reversal). It also fires
             a lot -> the false-signal problem.
  FILTER   = the DIPOLE lean (trailing-W taker imbalance, +buy / -sell). A candidate price turn is
             KEPT only if the dipole CONFIRMS it; otherwise it's judged a little-dip false signal
             and DROPPED. Confirmation = ANY of:
               (M) MIDLINE side  -- long needs lean on the + (buy) side, short needs the - (sell)
                   side. "if it's going neg we want to dump even if it's moving gently" => a long is
                   not confirmed once flow is negative; fires/holds shorts there regardless of speed.
               (T) TREND-LINE break -- the dipole broke its adaptive pivot trend line in the trade's
                   direction (the flow trend rolled over), or
               (O) FAST+DEEP override -- the dipole moved fast and deep in the trade's direction (the
                   soft escape hatch: a violent flow move is never walled off by the filter).

FALSIFICATION (per cell, sign-aligned, never pooled): does PRICE+dipole-filter cut the fire count
AND raise mean |forward move| / net-of-cost vs PRICE-only? Big-vs-small cut (big = |move| >= 22bps).
Renders price (primary) + its pivot trend line + kept/dropped turns + the dipole midline panel.
"""
from __future__ import annotations
import argparse, json
import numpy as np
from odcore.io import load_bins
from odcore.flip_detector import lean_series


def zigzag_pivots(x: np.ndarray, thr: float):
    """Causal ZigZag pivots. Returns list of (idx, value, kind) kind=+1 high / -1 low."""
    n = len(x); piv = []
    d = 1; ext = x[0]; exti = 0
    for t in range(1, n):
        v = x[t]
        if d == 1:
            if v > ext: ext, exti = v, t
            elif v <= ext - thr:
                piv.append((exti, ext, +1)); d = -1; ext, exti = v, t
        else:
            if v < ext: ext, exti = v, t
            elif v >= ext + thr:
                piv.append((exti, ext, -1)); d = +1; ext, exti = v, t
    return piv


def run(cell, W, price_thr_bps, lean_piv, buf, kvel, override, horizon, fee_bps, render):
    s = load_bins(f"realbins/{cell}_bins.json")
    mid = s.mid; n = len(mid)
    logmid = np.nan_to_num(np.log(np.where(mid > 0, mid, np.nan)), nan=0.0)
    lean = lean_series(s.buy, s.sell, W)

    # PRIMARY: price turns (the trade timing + the false-signal source)
    price_piv = zigzag_pivots(logmid, price_thr_bps / 1e4)
    # dipole pivots -> the adaptive flow trend line for the (T) filter
    lean_pivs = zigzag_pivots(lean, lean_piv)

    def fwd(i, side):
        j = min(i + horizon, n - 1)
        if mid[i] <= 0 or mid[j] <= 0: return 0.0
        return side * np.log(mid[j] / mid[i]) * 1e4

    def line_at(p2, p1, t):
        (i0, v0), (i1, v1) = p2, p1
        if i1 == i0: return v1
        return v1 + (v1 - v0) / (i1 - i0) * (t - i1)

    kept, dropped = [], []
    li = 0  # pointer into lean_pivs
    for (idx, val, kind) in price_piv:
        ci = min(idx + 1, n - 1)               # confirm one bar after the price pivot
        side = -1 if kind == +1 else +1        # high->short, low->long
        move = fwd(ci, side)
        # ---- dipole confirmation as of ci (causal) ----
        while li < len(lean_pivs) and lean_pivs[li][0] <= ci:
            li += 1
        seen = lean_pivs[:li]
        L = [(i, v) for (i, v, k) in seen if k == -1]
        H = [(i, v) for (i, v, k) in seen if k == +1]
        reasons = []
        # (M) midline side
        if (side == +1 and lean[ci] >= 0) or (side == -1 and lean[ci] <= 0):
            reasons.append("midline")
        # (T) flow trend-line break in the trade direction
        if side == -1 and len(L) >= 2 and L[-1][1] > L[-2][1] and lean[ci] < line_at(L[-2], L[-1], ci) - buf:
            reasons.append("break")
        if side == +1 and len(H) >= 2 and H[-1][1] < H[-2][1] and lean[ci] > line_at(H[-2], H[-1], ci) + buf:
            reasons.append("break")
        # (O) fast + deep override
        if ci > kvel:
            vel = lean[ci] - lean[ci - kvel]
            lb = max(0, ci - 5 * kvel)
            if side == -1 and vel < 0 and (-vel) * (np.max(lean[lb:ci + 1]) - lean[ci]) >= override:
                reasons.append("override")
            if side == +1 and vel > 0 and vel * (lean[ci] - np.min(lean[lb:ci + 1])) >= override:
                reasons.append("override")
        rec = (ci, side, move, reasons)
        (kept if reasons else dropped).append(rec)

    def stats(recs):
        a = np.array([r[2] for r in recs], float)
        if a.size == 0: return dict(n=0, mean=0.0, net=0.0, hit=0.0, big_frac=0.0)
        return dict(n=int(a.size), mean=round(float(a.mean()), 3),
                    net=round(float((a - fee_bps).sum()), 1),
                    hit=round(float((a > 0).mean()), 3),
                    big_frac=round(float((np.abs(a) >= 22).mean()), 3))

    allp = kept + dropped
    res = dict(cell=cell, W=W, price_thr_bps=price_thr_bps, lean_piv=lean_piv, buf=buf,
               kvel=kvel, override=override, horizon=horizon, fee_bps=fee_bps,
               price_only=stats(allp), price_plus_dipole=stats(kept), dropped=stats(dropped),
               n_dropped=len(dropped), fire_reduction=round(len(dropped) / max(1, len(allp)), 3),
               kept_by={r: sum(1 for k in kept if r in k[3]) for r in ("midline", "break", "override")})
    print(json.dumps(res, indent=2))
    if render:
        _render(cell, mid, lean, price_piv, lean_pivs, kept, dropped, W)
    return res


def _render(cell, mid, lean, price_piv, lean_pivs, kept, dropped, W):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(mid)
    cis = np.array([k[0] for k in kept]) if kept else np.array([n // 2])
    c0 = int(np.median(cis)); half = 90 * 60
    a = max(0, c0 - half); b = min(n, c0 + half)
    x = np.arange(a, b) / 60.0
    fig, ax = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                           gridspec_kw=dict(height_ratios=[3, 2]))
    # PRIMARY price panel + its pivot trend line
    ax[0].plot(x, mid[a:b], color="#888", lw=0.8, label="mid (PRIMARY)")
    pp = [(i, v, k) for (i, v, k) in price_piv if a <= i < b]
    if len(pp) >= 2:
        ax[0].plot([p[0] / 60.0 for p in pp], [np.exp(0) * np.nan for p in pp])  # spacing noop
    # draw price trend line through consecutive same-kind pivots (the picture)
    Lp = [(i, np.exp(0)) for i in []]
    for kind, col in [(-1, "#237804"), (+1, "#cf1322")]:
        ku = [(i, mid[i]) for (i, v, k) in pp if k == kind]
        if len(ku) >= 2:
            ax[0].plot([p[0] / 60.0 for p in ku], [p[1] for p in ku],
                       color=col, lw=1.3, alpha=0.6, ls="--",
                       label="support" if kind == -1 else "resistance")
    for (ci, side, move, reasons) in kept:
        if a <= ci < b:
            ax[0].scatter([ci / 60.0], [mid[ci]], marker="v" if side == -1 else "^",
                          s=85, color="#cf1322" if side == -1 else "#237804", zorder=6,
                          edgecolor="k", linewidth=0.8)
    for (ci, side, move, reasons) in dropped:
        if a <= ci < b:
            ax[0].scatter([ci / 60.0], [mid[ci]], marker="x", s=35, color="#bbb", zorder=4)
    ax[0].set_ylabel("price"); ax[0].legend(loc="upper left", fontsize=9)
    ax[0].set_title(f"{cell}: PRICE primary + dipole filter   colored=KEPT  grey x=dropped (false signal)")
    # dipole filter panel + midline
    ax[1].plot(x, lean[a:b], color="#722ed1", lw=0.9, label="dipole lean (filter)")
    ax[1].axhline(0, color="k", lw=1.4, label="midline (buy+ / sell-)")
    seen = [(i, v, k) for (i, v, k) in lean_pivs if a <= i < b]
    for kind, col, lab in [(-1, "#237804", "flow support"), (+1, "#cf1322", "flow resistance")]:
        ku = [(i, v) for (i, v, k) in seen if k == kind]
        if len(ku) >= 2:
            ax[1].plot([p[0] / 60.0 for p in ku], [p[1] for p in ku],
                       color=col, lw=1.4, marker="o", ms=3, alpha=0.7, label=lab)
    ax[1].set_ylabel("lean"); ax[1].set_xlabel("minutes"); ax[1].legend(loc="upper left", fontsize=8)
    fig.tight_layout(); out = f"_trend_gate_{cell}.png"
    fig.savefig(out, dpi=110); plt.close(fig); print(f"[render] {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", default="btc_bybit_perp")
    ap.add_argument("--W", type=int, default=60, help="dipole lean window (s)")
    ap.add_argument("--price_thr_bps", type=float, default=8.0, help="price ZigZag pivot threshold (bps)")
    ap.add_argument("--lean_piv", type=float, default=0.15, help="dipole ZigZag pivot threshold")
    ap.add_argument("--buf", type=float, default=0.05, help="flow trend-line break buffer")
    ap.add_argument("--kvel", type=int, default=15, help="velocity window (s) for fast+deep override")
    ap.add_argument("--override", type=float, default=0.10, help="|vel|*depth override threshold")
    ap.add_argument("--horizon", type=int, default=600, help="forward-move horizon (s)")
    ap.add_argument("--fee_bps", type=float, default=10.0)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run(a.cell, a.W, a.price_thr_bps, a.lean_piv, a.buf, a.kvel, a.override,
        a.horizon, a.fee_bps, not a.no_render)
