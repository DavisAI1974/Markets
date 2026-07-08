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


WIGGLE = 0.15                        # a little wiggle room: a winner up to 15% farther than the nearest
                                     # loser still counts (the archetype is an average; live legs won't match exactly)


def znorm(y):
    """Shape-only: map a curve to its own [0,1] range so we compare FORM (rise -> kink -> flatten), not level.
    'It doesn't matter if it reaches a value — the shape is what matters' (Greg)."""
    lo, hi = float(y.min()), float(y.max())
    return (y - lo) / (hi - lo + 1e-9)


def winner_match(qz, refz):
    """Match the live SHAPE qz to the 4 archetype SHAPES; fire if a WINNER shape is within wiggle of the
    nearest loser shape. Returns (fire, tag)."""
    d = {c: float(np.sum((qz - refz[c]) ** 2)) for c in CELLS}
    win_d = min(d["short-win"], d["long-win"])
    lose_d = min(d["short-lose"], d["long-lose"])
    fire = win_d <= lose_d * (1.0 + WIGGLE)                    # winner gets a little wiggle benefit
    tag = "short" if d["short-win"] <= d["long-win"] else "long"
    return fire, tag


def build_gates(buy, sell, flips, arcs_z, eqs_z, n):
    """Per-flip LIVE entry gates, built SEPARATELY for each signifier (arc-shape ALONE, equation ALONE).
    At each flip build the strictly-causal pre-fire curve (birth->pivot), normalize to SHAPE, match to the 4
    archetype shapes with wiggle; fire if a winner shape wins. egate keyed at the flip's confirm cell.
    Returns (arc_gate, eq_gate, arc_tags, eq_tags)."""
    timb = rolling_imb(buy, sell, SMOOTH_SEC)
    a_g = np.zeros(n, bool); e_g = np.zeros(n, bool); a_t = {}; e_t = {}
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
        qz = znorm(resample(pre, NRS))                        # the live leg's pre-fire SHAPE
        fa, ta = winner_match(qz, arcs_z)                     # ARC signifier alone
        fe, te = winner_match(qz, eqs_z)                      # EQUATION signifier alone
        if fa:
            a_g[c] = True; a_t[c] = ta
        if fe:
            e_g[c] = True; e_t[c] = te
    return a_g, e_g, a_t, e_t


def summarize(res, hours, label):
    legs = res.legs
    net = np.array([l.net_bps for l in legs]) if legs else np.array([])
    nk = len(legs); tot = float(net.sum())
    wp = (net > 0).mean() * 100 if nk else float("nan")
    dph = tot / 1e4 * CAP / hours
    print(f"  [{label:28}] legs={nk:4d}  win%={wp:5.1f}  net_bps={tot:8.0f}  $/hr={dph:7.3f}", flush=True)
    return dph


def main():
    # mode selects the ONE signifier this test uses: "arc" = sampled-arc shape alone, "eq" = equation alone.
    # The two are run as SEPARATE tests, in parallel (Greg, S75).
    mode = sys.argv[1] if len(sys.argv) > 1 else "arc"
    assert mode in ("arc", "eq"), "mode must be 'arc' or 'eq'"
    SIG = "ARC-shape" if mode == "arc" else "EQUATION"

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
    arcs_z = {c: znorm(arcs[c]) for c in CELLS}
    eqs_z = {c: znorm(eqs[c]) for c in CELLS}
    a_g, e_g, a_t, e_t = build_gates(buy, sell, flips, arcs_z, eqs_z, n)
    egate, tags = (a_g, a_t) if mode == "arc" else (e_g, e_t)
    nsw = sum(v == "short" for v in tags.values()); nlw = sum(v == "long" for v in tags.values())

    print(f"=== S75 SHAPE GATE — SOL, LIVE — SIGNIFIER: {SIG} ALONE (shape-normalized, wiggle={WIGGLE}) ===", flush=True)
    print(f"  book cells={n} (~{hours:.1f}h)  flips={len(flips)}  gate-fires={int(egate.sum())} "
          f"(short-winner {nsw} / long-winner {nlw})  $5k flat/signal", flush=True)
    print("  (archetypes = SOL leg_imbalance pre-fire arcs / their best-form equations; in-sample this window)\n", flush=True)

    res_u, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)                       # control
    summarize(res_u, hours, "UNGATED baseline")
    res_g, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs, entry_gate=egate)     # the test
    summarize(res_g, hours, f"GATED {SIG} baseline exit")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
