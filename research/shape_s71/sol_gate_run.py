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


def winner_match(q, ref):
    """Match the live RAW curve q (native amplitude — NO normalize/average/smooth; the raw curve IS the edge)
    to the 4 archetype curves; fire if a WINNER curve is within wiggle of the nearest loser. Returns (fire, tag)."""
    d = {c: float(np.sum((q - ref[c]) ** 2)) for c in CELLS}
    win_d = min(d["short-win"], d["long-win"])
    lose_d = min(d["short-lose"], d["long-lose"])
    fire = win_d <= lose_d * (1.0 + WIGGLE)                    # winner gets a little wiggle benefit
    tag = "short" if d["short-win"] <= d["long-win"] else "long"
    return fire, tag


def classify_eqpeak(q, eqs, peaks):
    """EQUATION is primary; if the top-2 equation matches look ALIKE (within wiggle), the PEAK decides
    (nearest archetype onset-peak: SOL SW .123, SL .146, LL .306, LW .374). Returns (fire, cell)."""
    d = {c: float(np.sum((q - eqs[c]) ** 2)) for c in CELLS}
    ranked = sorted(CELLS, key=lambda c: d[c])
    best, second = ranked[0], ranked[1]
    if d[second] <= d[best] * (1.0 + WIGGLE):             # equation ambiguous -> the peak is the decider
        lp = float(q[-1])                                 # this leg's pre-fire onset peak
        cell = min((best, second), key=lambda c: abs(lp - peaks[c]))
    else:
        cell = best
    return (cell in WIN), cell


def build_eqpeak(buy, sell, flips, eqs, peaks, n):
    """LIVE entry gate: equation-primary + peak-decider. Fire only when the chosen cell is a winner."""
    timb = rolling_imb(buy, sell, SMOOTH_SEC)
    g = np.zeros(n, bool); tg = {}
    prev_p = -1
    for (c, p, s) in sorted(flips, key=lambda z: int(z[1])):
        c, p, s = int(c), int(p), int(s)
        lo = max(0, p - LOOKBACK, prev_p + 1); prev_p = p
        seg = timb[lo:p + 1] * s
        if len(seg) < 30:
            continue
        birth = lo + ignition_idx(seg); pre = timb[birth:p + 1] * s
        if len(pre) < 12:
            continue
        q = resample(pre, NRS)
        fire, cell = classify_eqpeak(q, eqs, peaks)
        if fire:
            g[c] = True; tg[c] = "short" if cell == "short-win" else "long"
    return g, tg


def build_gates(buy, sell, flips, arcs, eqs, n):
    """Per-flip LIVE entry gates, built SEPARATELY for each signifier (arc-shape ALONE, equation ALONE).
    At each flip build the strictly-causal RAW pre-fire curve (birth->pivot; native amplitude, no normalize/
    average/smooth), match to the 4 archetype curves with wiggle; fire if a winner curve wins. egate keyed at
    the flip's confirm cell. Returns (arc_gate, eq_gate, arc_tags, eq_tags)."""
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
        q = resample(pre, NRS)                                # the live leg's RAW pre-fire curve (native amplitude)
        fa, ta = winner_match(q, arcs)                        # ARC signifier alone
        fe, te = winner_match(q, eqs)                         # EQUATION signifier alone
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


def ramp(y):
    """Descriptors Greg reads by eye: peak (energy at onset), ascent SLOPE (steepness), and LINEARITY R²
    (loser = flatter + more linear/straight; winner = steeper + curved hockey). Native amplitude."""
    x = np.linspace(0, 1, len(y))
    b = np.polyfit(x, y, 1); yh = np.polyval(b, x)
    ss = ((y - y.mean()) ** 2).sum()
    r2 = 1.0 - ((y - yh) ** 2).sum() / (ss + 1e-12)
    return float(y[-1]), float(b[0]), float(r2)          # peak, slope, linear-R²


def _legs_with_peak():
    """Run SOL through the LIVE executor and lift each leg's (pre-fire onset PEAK, net_bps, dur, hours).
    Peak = the with-side trade-imbalance at onset (native amplitude, raw). Leakage-free (birth->onset)."""
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; hours = len(mid) * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    timb = rolling_imb(buy, sell, SMOOTH_SEC)
    legs = sorted(res.legs, key=lambda z: int(z.open_idx)); prev_close = -1
    peak, net, dur = [], [], []
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        lo = max(0, o - LOOKBACK, prev_close + 1); prev_close = c
        if c <= o:
            continue
        seg = timb[lo:o + 1] * s
        if len(seg) < 30:
            continue
        birth = lo + ignition_idx(seg); pre = timb[birth:o + 1] * s
        if len(pre) < 12:
            continue
        peak.append(float(pre[-1])); net.append(float(l.net_bps)); dur.append((c - o) * 0.1)
    return np.array(peak), np.array(net), np.array(dur), hours


def strength():
    """Repoint the dipole (Greg): NOT direction (that's a wall) — use it to tell STRENGTH (how big the move)
    and, within the SMALL trades, small-winner vs small-loser. Entry stays 'barely late' (SOL natural cadence).
    Causal dipole at each leg's pivot (leakage-free)."""
    from odcore.info_dipole import divergence
    from odcore.platform import kraken_flips
    DIVW = 600
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; hours = len(mid) * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    flips = kraken_flips(cfg, mid, buy, sell); piv = {int(c): int(p) for (c, p, s) in flips}
    legs = res.legs
    net = np.array([float(l.net_bps) for l in legs]); dur = np.array([(int(l.close_idx) - int(l.open_idx)) * 0.1 for l in legs])
    conv, ali = [], []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); plo = max(0, p - DIVW)
        dv = divergence(buy[plo:p + 1], sell[plo:p + 1], float(mid[p] - mid[plo])) if p - plo >= 12 else None
        conv.append(float(dv["reversal_conviction"]) if dv else np.nan)
        ali.append(abs(float(dv["aligned_flow"])) if dv else np.nan)
    conv = np.array(conv); ali = np.array(ali)
    n = len(net); win = net > 0; med = np.median(dur); short = dur < med
    ok = ~np.isnan(conv)

    print(f"=== SOL DIPOLE as STRENGTH + small-win/loser — {n} legs, {hours:.1f}h (causal) ===", flush=True)
    # 1) does dipole STRENGTH track move MAGNITUDE?
    def corr(a, b):
        a = a[ok]; b = b[ok]; return float(np.corrcoef(a, b)[0, 1])
    print(f"  strength vs magnitude:  corr(reversal_conv, |net|)={corr(conv, np.abs(net)):+.3f}   "
          f"corr(|aligned_flow|, |net|)={corr(ali, np.abs(net)):+.3f}", flush=True)
    # 2) within SMALL (short) and BIG (long): win% + mean |net| by dipole strength quartile
    for name, m in (("SMALL (short-dur)", short & ok), ("BIG (long-dur)", ~short & ok)):
        c = conv[m]; w = win[m]; a = np.abs(net[m])
        if len(c) < 20:
            continue
        q = np.quantile(c, [0.25, 0.5, 0.75])
        print(f"\n  {name}  n={m.sum()} — by dipole reversal_conviction quartile:", flush=True)
        print(f"    {'quartile':10}{'n':>5}{'win%':>7}{'mean_net':>10}{'mean|net|':>11}", flush=True)
        edges = [-np.inf, q[0], q[1], q[2], np.inf]
        for i in range(4):
            qm = (c > edges[i]) & (c <= edges[i + 1])
            if not qm.sum():
                continue
            print(f"    Q{i+1:<9}{int(qm.sum()):>5}{w[qm].mean()*100:>7.1f}{net[m][qm].mean():>10.2f}{a[qm].mean():>11.2f}", flush=True)
    print("DONE", flush=True)


def dipole():
    """Causal dipole DIRECTION test (Greg): does divergence() call the SOL side at entry? For each live leg
    read the dipole at its pivot (pre-pivot window, leakage-free); group win%/net by expect class; then FLIP
    the side on the 'reversal' calls (opposite trade ~= -gross) and measure $/hr. Tests whether the dipole
    converts the 82%-flippable losers WITHOUT peeking."""
    from odcore.info_dipole import divergence
    from odcore.platform import kraken_flips
    DIVW = 600
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0; hours = len(mid) * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    flips = kraken_flips(cfg, mid, buy, sell); piv = {int(c): int(p) for (c, p, s) in flips}
    legs = res.legs
    net = np.array([float(l.net_bps) for l in legs]); gross = np.array([float(l.gross_bps) for l in legs])
    expect = []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); plo = max(0, p - DIVW)
        dv = divergence(buy[plo:p + 1], sell[plo:p + 1], float(mid[p] - mid[plo])) if p - plo >= 12 else None
        expect.append(dv["expect"] if dv else "n/a")
    expect = np.array(expect); n = len(net); win = net > 0
    dph = lambda v: v.sum() / 1e4 * CAP / hours

    print(f"=== SOL DIPOLE DIRECTION TEST — {n} live legs, {hours:.1f}h (causal, leakage-free) ===", flush=True)
    print(f"  UNGATED win%={win.mean()*100:.1f}  $/hr={dph(net):.3f}\n", flush=True)
    print(f"  {'dipole expect':14}{'n':>6}{'win%':>7}{'mean_net':>10}", flush=True)
    for cls in ("reversal", "flip_risk", "weakening", "continue", "n/a"):
        m = expect == cls
        if not m.sum():
            continue
        print(f"  {cls:14}{int(m.sum()):>6}{win[m].mean()*100:>7.1f}{net[m].mean():>10.2f}", flush=True)

    print("\n  --- FLIP the side on dipole calls (opposite trade ~= -gross) ---", flush=True)
    for label, classes in (("reversal only", {"reversal"}),
                           ("reversal+flip_risk", {"reversal", "flip_risk"})):
        fm = np.isin(expect, list(classes))
        v = net.copy(); v[fm] = -gross[fm]
        conv = (net[fm] < 0) & (-gross[fm] > 0)                 # losers this flip converted to winners
        print(f"  flip {label:20}: flipped {int(fm.sum())} legs  win%={ (v>0).mean()*100:.1f}  "
              f"$/hr={dph(v):.3f}  (of flipped, {int(conv.sum())} losers->winners)", flush=True)
    # precision/recall of 'reversal' as a wrong-direction detector
    rev = expect == "reversal"; lose = ~win
    if rev.sum():
        prec = (rev & lose).sum() / rev.sum(); rec = (rev & lose).sum() / lose.sum()
        print(f"\n  'reversal' as a loser-detector: precision={prec*100:.0f}% (of flagged are losers)  "
              f"recall={rec*100:.0f}% (of losers flagged)", flush=True)
    print("DONE", flush=True)


def flip():
    """Greg's mirror test: are SOL's LONG-LOSERS just winners entered BACKWARDS? For each leg the opposite-side
    trade over the SAME [open,close] window nets ~= -gross_bps (mid-symmetric; off by ~2x half-spread). Measure
    how many losers flip positive and the $/hr if we'd reversed the long-losers. LIVE executor legs."""
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    hours = len(mid) * 0.1 / 3600.0
    legs = res.legs
    net = np.array([float(l.net_bps) for l in legs]); gross = np.array([float(l.gross_bps) for l in legs])
    dur = np.array([(int(l.close_idx) - int(l.open_idx)) * 0.1 for l in legs])
    n = len(net); win = net > 0; med = np.median(dur); short = dur < med
    masks = {"short-win": short & win, "short-lose": short & ~win, "long-win": ~short & win, "long-lose": ~short & ~win}
    flip_net = -gross                                       # opposite side over the same window (maker fees ~0)

    print(f"=== SOL FLIP TEST — {n} live legs, {hours:.1f}h — are losers backwards winners? ===", flush=True)
    print(f"  {'bucket':11}{'n':>5}{'mean_net':>10}{'mean_gross':>12}", flush=True)
    for c in ("short-win", "short-lose", "long-win", "long-lose"):
        m = masks[c]
        print(f"  {c:11}{int(m.sum()):>5}{net[m].mean():>10.2f}{gross[m].mean():>12.2f}", flush=True)

    print("\n  --- reverse the LOSERS (opposite side, same window ~= -gross) ---", flush=True)
    for c in ("long-lose", "short-lose"):
        m = masks[c]; f = flip_net[m]
        print(f"  {c:11}: n={int(m.sum())}  mean orig net={net[m].mean():+.2f}  ->  flipped={f.mean():+.2f}  "
              f"({(f > 0).mean()*100:.0f}% become winners)", flush=True)

    print("\n  --- S62 mirror check (long-win vs long-lose gross) ---", flush=True)
    lw, ll = masks["long-win"], masks["long-lose"]
    print(f"  long-win mean gross={gross[lw].mean():+.2f}   long-lose mean gross={gross[ll].mean():+.2f}   "
          f"(mirror if ~equal & opposite)", flush=True)

    print("\n  --- $/hr if we had REVERSED the long-losers ---", flush=True)
    dph = lambda v: v.sum() / 1e4 * CAP / hours
    flipped_all = net.copy(); flipped_all[ll] = flip_net[ll]
    print(f"  ungated               $/hr={dph(net):7.3f}", flush=True)
    print(f"  reverse long-losers   $/hr={dph(flipped_all):7.3f}  (hindsight ceiling — proves the direction lever)", flush=True)
    both = ll | masks["short-lose"]; flipped_both = net.copy(); flipped_both[both] = flip_net[both]
    print(f"  reverse ALL losers    $/hr={dph(flipped_both):7.3f}", flush=True)
    print("DONE", flush=True)


def buckets():
    """Split ALL live legs into the 4 buckets (short/long by median dur x win/lose by net>0) and show each
    bucket's pre-fire onset PEAK distribution — do the categories live in distinct peak bands, or bleed over?"""
    pk, net, dur, hours = _legs_with_peak()
    n = len(pk); win = net > 0; med = np.median(dur); short = dur < med
    masks = {"short-win": short & win, "short-lose": short & ~win,
             "long-win": ~short & win, "long-lose": ~short & ~win}
    print(f"=== SOL — {n} live legs split into 4 buckets; PRE-FIRE PEAK distribution per bucket ===", flush=True)
    print(f"  (median dur = {med:.0f}s; peak = with-side trade-imbalance at onset, native amplitude)\n", flush=True)
    print(f"  {'bucket':11}{'n':>5}{'mean':>8}{'min':>8}{'p10':>8}{'p25':>8}{'p50':>8}{'p75':>8}{'p90':>8}{'max':>8}", flush=True)
    stats = {}
    for cell, m in masks.items():
        p = pk[m]; stats[cell] = p
        qs = np.percentile(p, [0, 10, 25, 50, 75, 90, 100])
        print(f"  {cell:11}{int(m.sum()):>5}{p.mean():>8.3f}" + "".join(f"{v:>8.3f}" for v in qs), flush=True)

    # bleed-over: within each DURATION, how much do winner and loser peak ranges overlap?
    def overlap(a, b):
        # fraction of the loser legs whose peak falls inside the winner's [p25,p75] band, and vice versa
        wlo, whi = np.percentile(a, [25, 75]); llo, lhi = np.percentile(b, [25, 75])
        loser_in_win = ((b >= wlo) & (b <= whi)).mean()
        win_in_loser = ((a >= llo) & (a <= lhi)).mean()
        return wlo, whi, llo, lhi, loser_in_win, win_in_loser
    print("\n  --- WITHIN-DURATION winner vs loser peak overlap (IQR bands) ---", flush=True)
    for dcls, w, l in (("SHORT", "short-win", "short-lose"), ("LONG", "long-win", "long-lose")):
        wlo, whi, llo, lhi, li, wi = overlap(stats[w], stats[l])
        print(f"  {dcls:6}: WIN IQR[{wlo:+.3f},{whi:+.3f}] med={np.median(stats[w]):+.3f}   "
              f"LOSE IQR[{llo:+.3f},{lhi:+.3f}] med={np.median(stats[l]):+.3f}", flush=True)
        print(f"          bleed: {li*100:.0f}% of losers sit inside the winner IQR; "
              f"{wi*100:.0f}% of winners sit inside the loser IQR", flush=True)
    print("DONE", flush=True)


def eqpeak_run():
    """The gate Greg specced: EQUATION shape primary, PEAK on top as the decider when two equation-matches
    look alike. $5k flat. LIVE via run_kraken_cell. SOL."""
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    n = len(mid); hours = n * 0.1 / 3600.0
    flips = kraken_flips(cfg, mid, buy, sell)
    arcs, eqs = load_signifiers()
    peaks = {c: float(arcs[c][-1]) for c in CELLS}                 # archetype onset peaks: .123 .146 .306 .374
    egate, tags = build_eqpeak(buy, sell, flips, eqs, peaks, n)
    nsw = sum(v == "short" for v in tags.values()); nlw = sum(v == "long" for v in tags.values())
    print("=== S75 GATE — SOL, LIVE — EQUATION primary + PEAK decider (raw curve, wiggle={:.2f}) ===".format(WIGGLE), flush=True)
    print("  archetype peaks: " + "  ".join(f"{c}={peaks[c]:+.3f}" for c in CELLS), flush=True)
    print(f"  book cells={n} (~{hours:.1f}h)  flips={len(flips)}  gate-fires={int(egate.sum())} "
          f"(short-winner {nsw} / long-winner {nlw})  $5k flat/signal\n", flush=True)
    res_u, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)
    summarize(res_u, hours, "UNGATED (fire every flip)")
    res_g, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs, entry_gate=egate)
    summarize(res_g, hours, "eq+peak ENTRY yes/no")
    print("DONE", flush=True)


def peak():
    """Greg's read: 'focus on the peak — watch it move up, the highest one is the biggest winner.'
    Bin the live legs by their pre-fire onset PEAK and show net/win% climbing with it; then a fire-only-above
    threshold sweep ($5k flat)."""
    pk, net, dur, hours = _legs_with_peak()
    n = len(pk); order = np.argsort(pk); win = net > 0
    print(f"=== SOL PEAK vs OUTCOME — {n} live legs, {hours:.1f}h  (peak = with-side trade-imbalance at onset) ===", flush=True)
    print(f"  UNGATED: win%={win.mean()*100:.1f}  net_bps={net.sum():.0f}  $/hr={net.sum()/1e4*CAP/hours:.3f}\n", flush=True)
    print("  --- legs sorted into 10 equal PEAK deciles (low peak -> high peak) ---", flush=True)
    print(f"  {'decile':>7}{'peak-range':>18}{'n':>5}{'mean_net':>10}{'win%':>7}{'mean_dur':>10}", flush=True)
    for d in range(10):
        idx = order[d * n // 10:(d + 1) * n // 10]
        pr = pk[idx]
        print(f"  {d+1:>7}{f'{pr.min():+.3f}..{pr.max():+.3f}':>18}{len(idx):>5}"
              f"{net[idx].mean():>10.2f}{win[idx].mean()*100:>7.1f}{dur[idx].mean():>10.1f}", flush=True)
    print("\n  --- FIRE ONLY legs with peak >= threshold ($5k flat) ---", flush=True)
    print(f"  {'peak>=':>8}{'legs':>6}{'win%':>7}{'net_bps':>10}{'$/hr':>9}", flush=True)
    for thr in (-0.1, 0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35):
        keep = pk >= thr; g = net[keep].sum()
        wp = win[keep].mean() * 100 if keep.sum() else float("nan")
        print(f"  {thr:>8.2f}{int(keep.sum()):>6}{wp:>7.1f}{g:>10.0f}{g/1e4*CAP/hours:>9.3f}", flush=True)
    print("DONE", flush=True)


def walk():
    """Worst-loser walkthrough (Greg): the q0 (worst-decile) LOSING legs the EQUATION gate FIRED on — how
    each slipped through. Shows raw peak/slope/linearity vs the archetypes, and normalized-vs-raw verdicts."""
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)                  # ungated LIVE legs
    timb = rolling_imb(buy, sell, SMOOTH_SEC)
    arcs, eqs = load_signifiers()

    # archetype reference descriptors (native amplitude)
    print("=== SOL archetype pre-fire descriptors (native amplitude — what winners/losers actually look like) ===", flush=True)
    for c in CELLS:
        pk, sl, r2 = ramp(arcs[c])
        print(f"  {c:11}  peak={pk:+.3f}  slope={sl:+.3f}  linear-R²={r2:.3f}", flush=True)

    legs = sorted(res.legs, key=lambda z: int(z.open_idx)); prev_close = -1
    durs = np.array([(int(l.close_idx) - int(l.open_idx)) * 0.1 for l in legs if int(l.close_idx) > int(l.open_idx)])
    med = float(np.median(durs))
    recs = []
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        lo = max(0, o - LOOKBACK, prev_close + 1); prev_close = c
        if c <= o:
            continue
        seg = timb[lo:o + 1] * s
        if len(seg) < 30:
            continue
        birth = lo + ignition_idx(seg); pre = timb[birth:o + 1] * s
        if len(pre) < 12:
            continue
        q = resample(pre, NRS)
        pk, sl, r2 = ramp(q)
        fe, te = winner_match(q, eqs)                                          # the gate (raw equation)
        near_raw = min(CELLS, key=lambda cc: float(np.sum((q - arcs[cc]) ** 2)))   # raw arc nearest
        recs.append(dict(net=float(l.net_bps), dur=(c - o) * 0.1, peak=pk, slope=sl, r2=r2,
                         fire=fe, tag=te, near_raw=near_raw))

    fired_losers = [r for r in recs if r["net"] < 0 and r["fire"]]
    fired_losers.sort(key=lambda r: r["net"])                                  # worst first
    k = max(10, len(fired_losers) // 10)                                       # q0 = worst decile (>= 10)
    print(f"\n=== q0 WORST LOSERS the EQUATION gate FIRED on ({k} of {len(fired_losers)} fired-losers; "
          f"{sum(r['fire'] for r in recs)} fires / {len(recs)} legs) ===", flush=True)
    print(f"  {'net_bps':>8}{'dur/s':>7}{'cls':>7} | {'peak':>7}{'slope':>7}{'linR²':>7} | "
          f"{'gate(eq)':>12}{'raw-arc-near':>14}", flush=True)
    for r in fired_losers[:k]:
        cls = "short" if r["dur"] < med else "long"
        print(f"  {r['net']:8.1f}{r['dur']:7.1f}{cls:>7} | {r['peak']:+7.3f}{r['slope']:+7.3f}{r['r2']:7.3f} | "
              f"{'FIRE '+r['tag']:>12}{r['near_raw']:>14}", flush=True)
    print("DONE", flush=True)


def main():
    # mode selects the ONE signifier this test uses: "arc" = sampled-arc shape alone, "eq" = equation alone.
    # The two are run as SEPARATE tests, in parallel (Greg, S75). "walk" = worst-loser walkthrough.
    mode = sys.argv[1] if len(sys.argv) > 1 else "arc"
    if mode == "walk":
        walk(); return
    if mode == "peak":
        peak(); return
    if mode == "eqpeak":
        eqpeak_run(); return
    if mode == "buckets":
        buckets(); return
    if mode == "flip":
        flip(); return
    if mode == 'strength':
        strength(); return
    if mode == 'dipole':
        dipole(); return
    assert mode in ('arc', 'eq'), 'unknown mode'
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
    a_g, e_g, a_t, e_t = build_gates(buy, sell, flips, arcs, eqs, n)
    egate, tags = (a_g, a_t) if mode == "arc" else (e_g, e_t)
    nsw = sum(v == "short" for v in tags.values()); nlw = sum(v == "long" for v in tags.values())

    print(f"=== S75 SHAPE GATE — SOL, LIVE — SIGNIFIER: {SIG} ALONE (raw curve, wiggle={WIGGLE}) ===", flush=True)
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
