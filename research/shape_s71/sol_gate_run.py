"""S75 CURVE-SHAPE ENTRY GATE — SOL, LIVE (Greg's spec, #0f).

Match each forming trade's WHOLE pre-fire curve to the 4 per-cell archetype SHAPES on BOTH signifiers
CONCURRENTLY — the per-cell EQUATION (fit_shapes.best_form of the archetype arc, evaluated as a curve) AND
the per-cell sampled ARC (leg_imbalance_arcs_sol.npz) — with wiggle room (each representation matches to the
NEAREST of the 4 distinct archetype shapes; no centroid, #0e-GATE). A leg FIRES only when BOTH signifiers read
a WINNER shape (short-win OR long-win); if 1 or both is a mismatch for winner, do NOT fire. Each fired leg is
TAGGED short/long winner at entry. $5k flat per fired signal — no cap models.

Injected LIVE through run_kraken_cell's entry_gate socket, so the executor's downstream state reflects every
skip. Leakage-free: the pre-fire curve at each flip is built strictly from data up to the pivot (the turn),
never past it. EXIT: baseline (current code) vs the S75 balance_exit finding — keep whichever wins.

Reuses the live builder + helpers (arc_gate / whole_legs / fit_shapes / leg_imbalance arcs). Builds no shapes
of its own; firing/direction untouched (Greg-only).
"""
import os, sys, types
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/home/user/Markets")
# shim matplotlib (not installed; no pip per the S75 rule) — arc_gate/leg_imbalance import it at module load,
# but the functions we reuse never draw. A no-op module lets the imports succeed.
if "matplotlib" not in sys.modules:
    _mpl = types.ModuleType("matplotlib"); _mpl.use = lambda *a, **k: None
    _plt = types.ModuleType("matplotlib.pyplot")
    _plt.__getattr__ = lambda name: (lambda *a, **k: None)
    _mpl.pyplot = _plt
    sys.modules["matplotlib"] = _mpl; sys.modules["matplotlib.pyplot"] = _plt
from arc_gate import load_raw, rolling_imb, build_channels, median_spread_bps  # the live builder
from whole_legs import ignition_idx, resample                                  # the curve builder pieces
from fit_shapes import best_form, eval_form                                     # the EQUATION signifier
from odcore.platform import run_kraken_cell, kraken_flips, KRAKEN               # the LIVE decision path

CPS = 10
SMOOTH_SEC = 20                      # same trade-flow smoothing as leg_imbalance.py
LOOKBACK = 150 * CPS                 # same ignition lookback as leg_imbalance.py
NRS = 100
CAP = 5000.0
CELLS = ["short-win", "short-lose", "long-win", "long-lose"]
WIN = {"short-win", "long-win"}
ARC_NPZ = os.path.join(os.path.dirname(__file__), "leg_imbalance_arcs_sol.npz")


def load_signifiers():
    """The two SOL pre-fire signifiers per cell: the sampled ARC (npz) and its EQUATION (best_form curve).
    Both are matched as SHAPES; neither is solved for a number."""
    d = np.load(ARC_NPZ)
    x = np.linspace(0, 1, NRS)
    arcs, eqs = {}, {}
    for cell in CELLS:
        a = d[f"trade|{cell}|pre"]                       # per-cell mean pre-fire arc (100 pts) = ARC signifier
        arcs[cell] = a
        (name, coeffs, _r2, _k), _ = best_form(a)        # its EQUATION
        eqs[cell] = eval_form(name, coeffs, x)           # the equation drawn as a curve (100 pts) = EQ signifier
    return arcs, eqs


def nearest(q, ref):
    """Nearest archetype SHAPE to the live curve q by whole-curve L2. The nearest-of-4 IS the wiggle room —
    a forming leg matches the closest archetype shape, never an exact numeric equality."""
    return min(CELLS, key=lambda c: float(np.sum((q - ref[c]) ** 2)))


def build_gate(buy, sell, flips, arcs, eqs, n):
    """Per-flip LIVE entry gate. At each flip build the strictly-causal pre-fire curve (birth->pivot), match
    it to the ARC signifiers and the EQUATION signifiers; FIRE only if BOTH read a winner shape. egate is keyed
    at the flip's confirm cell (what swing_maker consults). Returns (egate, tags)."""
    timb = rolling_imb(buy, sell, SMOOTH_SEC)
    egate = np.zeros(n, bool)
    tags = {}
    prev_p = -1
    for (c, p, s) in sorted(flips, key=lambda z: int(z[1])):
        c, p, s = int(c), int(p), int(s)
        lo = max(0, p - LOOKBACK, prev_p + 1)
        prev_p = p
        seg = timb[lo:p + 1] * s
        if len(seg) < 30:
            continue
        birth = lo + ignition_idx(seg)
        pre = timb[birth:p + 1] * s
        if len(pre) < 12:
            continue
        q = resample(pre, NRS)
        arc_cell = nearest(q, arcs)      # ARC signifier verdict
        eq_cell = nearest(q, eqs)        # EQUATION signifier verdict
        if arc_cell in WIN and eq_cell in WIN:                 # BOTH must read winner -> fire $5k
            egate[c] = True
            tags[c] = "short" if arc_cell == "short-win" else "long"
    return egate, tags


def summarize(res, hours, label):
    legs = res.legs
    net = np.array([l.net_bps for l in legs]) if legs else np.array([])
    nk = len(legs); tot = float(net.sum())
    wp = (net > 0).mean() * 100 if nk else float("nan")
    dph = tot / 1e4 * CAP / hours
    print(f"  [{label:28}] legs={nk:4d}  win%={wp:5.1f}  net_bps={tot:8.0f}  $/hr={dph:7.3f}", flush=True)
    return dph


def main():
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path)
    ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float)
    bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    n = len(mid); hours = n * 0.1 / 3600.0

    flips = kraken_flips(cfg, mid, buy, sell)
    arcs, eqs = load_signifiers()
    egate, tags = build_gate(buy, sell, flips, arcs, eqs, n)
    nsw = sum(v == "short" for v in tags.values()); nlw = sum(v == "long" for v in tags.values())

    print("=== S75 CURVE-SHAPE GATE — SOL, LIVE (equation + arc, BOTH must read winner) ===", flush=True)
    print(f"  book cells={n} (~{hours:.1f}h)  flips={len(flips)}  gate-fires={int(egate.sum())} "
          f"(short-winner {nsw} / long-winner {nlw})  $5k flat/signal", flush=True)
    print("  (archetypes = SOL leg_imbalance arcs + their best-form equations; in-sample vs this window)\n", flush=True)

    # UNGATED, baseline exit (current live code)
    res_u, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    summarize(res_u, hours, "UNGATED baseline exit")
    # GATED, baseline exit
    res_g, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs, entry_gate=egate)
    summarize(res_g, hours, "GATED baseline exit")
    # GATED + the S75 balance_exit finding (adopt only if it beats baseline)
    for be in [(0.15, -0.10), (0.20, 0.0), (0.10, -0.20)]:
        res_be, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs, entry_gate=egate, balance_exit=be)
        summarize(res_be, hours, f"GATED balance_exit{be}")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
