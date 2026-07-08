"""S74-corrected FITTING + WHOLE-CURVE GATE + TAIL/EXIT read.
Loads /tmp/kbook/{coin}_whole.npz (native-amplitude, normalized-time whole limbs from the LIVE path).

Keeps the 4 cells (short-win, short-lose, long-win, long-lose) DISTINCT — never collapses to one shape.
Per cell fits TWO separate equations split at the fire (onset t=0):
  (a) PRE-FIRE  archetype eq  — best functional form PER CELL (may differ per cell) + coeffs + start-y/end-y.
  (c) TAIL      archetype eq  — best form per cell on whole close-aligned legs + start-y/end-y.
  (d) EXHAUSTION/FLATTEN point from each distinct tail eq.
  (b) ENTRY GATE: match each forming trade's OWN pre-fire curve (whole curve, native amp, norm time) to the
      4 DISTINCT archetype pre-curves by nearest-L2; fire if nearest=winner archetype, skip if loser.
      Run vs UNGATED and vs the 4-anchor ENERGY gate. In-sample + walk-forward. CAP=$5000/leg.
"""
import os, sys, json
import numpy as np
from scipy.optimize import curve_fit
sys.path.insert(0, os.path.dirname(__file__))
CAP = 5000.0
COINS = ["sol", "btc", "eth", "xrp"]
NRS = 100
CELLS = ["short-win", "short-lose", "long-win", "long-lose"]
WIN_CELLS = {"short-win", "long-win"}


# ----------------------------- functional-form fitting -----------------------------
def _r2(y, yh):
    ss = ((y - y.mean())**2).sum()
    return 1.0 - ((y - yh)**2).sum()/(ss + 1e-12)


def fit_poly(x, y, deg):
    c = np.polyfit(x, y, deg)
    return c, _r2(y, np.polyval(c, x)), deg + 1


def fit_hockey(x, y):
    """2-segment continuous piecewise-linear; search breakpoint. Returns (xb, y at 0, slope1, slope2)."""
    best = None
    for xb in np.linspace(0.15, 0.85, 29):
        # basis: 1, x, relu(x-xb)  -> continuous kink
        A = np.column_stack([np.ones_like(x), x, np.clip(x - xb, 0, None)])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        yh = A @ coef
        r2 = _r2(y, yh)
        if best is None or r2 > best[1]:
            best = ((xb, coef[0], coef[1], coef[1] + coef[2]), r2, 4)  # slope1=coef1, slope2=coef1+coef2
    return best


def fit_exp(x, y):
    def f(x, a, b, k):
        return a + b*(np.exp(k*x) - 1.0)
    try:
        p, _ = curve_fit(f, x, y, p0=[y[0], (y[-1]-y[0]), 1.0], maxfev=6000)
        return p, _r2(y, f(x, *p)), 3
    except Exception:
        return None, -9, 3


def best_form(y):
    """Fit candidate forms to a mean arc y over normalized x in [0,1]; pick best by adjusted R^2."""
    x = np.linspace(0, 1, len(y))
    n = len(y)
    cands = []
    for deg, name in [(1, "linear"), (2, "quadratic"), (3, "cubic")]:
        c, r2, k = fit_poly(x, y, deg)
        cands.append((name, c, r2, k))
    hk = fit_hockey(x, y); cands.append(("hockey", hk[0], hk[1], hk[2]))
    ex = fit_exp(x, y)
    if ex[0] is not None:
        cands.append(("exp", ex[0], ex[1], ex[2]))
    # adjusted R^2 penalizing params
    def adj(r2, k):
        return 1 - (1 - r2)*(n - 1)/max(1, (n - k - 1))
    cands.sort(key=lambda z: adj(z[2], z[3]), reverse=True)
    return cands[0], cands  # (name, coeffs, r2, k)


def fmt_form(name, coeffs):
    if name == "linear":
        b, a = coeffs; return f"y = {a:+.3f} {b:+.3f}·x"
    if name == "quadratic":
        c, b, a = coeffs; return f"y = {a:+.3f} {b:+.3f}·x {c:+.3f}·x²"
    if name == "cubic":
        d, c, b, a = coeffs; return f"y = {a:+.3f} {b:+.3f}·x {c:+.3f}·x² {d:+.3f}·x³"
    if name == "hockey":
        xb, y0, s1, s2 = coeffs
        return f"y = {y0:+.3f} + {s1:+.3f}·x (x≤{xb:.2f}), blade-slope {s2:+.3f} (x>{xb:.2f})"
    if name == "exp":
        a, b, k = coeffs; return f"y = {a:+.3f} {b:+.3f}·(e^({k:+.2f}·x)−1)"
    return str(coeffs)


def eval_form(name, coeffs, x):
    if name in ("linear", "quadratic", "cubic"):
        return np.polyval(coeffs, x)
    if name == "hockey":
        xb, y0, s1, s2 = coeffs
        return y0 + s1*x + (s2 - s1)*np.clip(x - xb, 0, None)
    if name == "exp":
        a, b, k = coeffs; return a + b*(np.exp(k*x) - 1.0)


# ----------------------------- shape descriptors -----------------------------
def limb_stats(y):
    x = np.linspace(0, 1, len(y))
    start, end, mn = float(y[0]), float(y[-1]), float(y.min())
    below0 = float((y < 0).mean())
    # ignition timing: last normalized-time the curve is below zero (leaves the hole)
    neg = np.where(y < 0)[0]
    t_ign = float(x[neg[-1]]) if len(neg) else 0.0
    blade = float(np.polyfit(x[-NRS//3:], y[-NRS//3:], 1)[0])   # last-third slope
    return dict(start=start, end=end, dip=mn, below0=below0, t_ign=t_ign, blade=blade)


# ----------------------------- data / cells -----------------------------
def load(coin):
    d = np.load(f"/tmp/kbook/{coin}_whole.npz")
    return {k: d[k] for k in d.files}


def cell_masks(net, dur):
    win = net > 0; med = np.median(dur); short = dur < med
    return {"short-win": short & win, "short-lose": short & ~win,
            "long-win": ~short & win, "long-lose": ~short & ~win}, win, short


# ----------------------------- gate metrics -----------------------------
def metrics(fire, net, win, short, hours):
    g = net[fire].sum()
    wk = (net[fire] > 0).mean()*100 if fire.sum() else float("nan")
    sl = (~win) & short; ll = (~win) & ~short
    return dict(winpct=wk, dph=g/1e4*CAP/hours, fired=int(fire.sum()), n=len(net),
                firedpct=fire.mean()*100,
                sl_skip=int((~fire & sl).sum()), sl_tot=int(sl.sum()),
                ll_skip=int((~fire & ll).sum()), ll_tot=int(ll.sum()),
                w_skip=int((~fire & win).sum()), w_tot=int(win.sum()))


def energy_gate(pre_end, net, dur):
    """4-anchor nearest-energy on onset flow (pre_end). Fire mask."""
    win = net > 0; med = np.median(dur); short = dur < med
    def m(mask): return float(pre_end[mask].mean()) if mask.sum() else 0.0
    a_sl, a_sw = m((~win) & short), m(win & short)
    a_ll, a_lw = m((~win) & ~short), m(win & ~short)
    d_lose = np.minimum(np.abs(pre_end - a_sl), np.abs(pre_end - a_ll))
    d_win = np.minimum(np.abs(pre_end - a_sw), np.abs(pre_end - a_lw))
    return ~(d_lose < d_win)


def build_archetypes(pre_arcs, masks, idx=None):
    """Mean pre-fire curve per cell (native amp, normalized time). idx restricts which legs are used."""
    arche = {}
    for cell in CELLS:
        m = masks[cell].copy()
        if idx is not None:
            sel = np.zeros(len(m), bool); sel[idx] = True; m = m & sel
        if m.sum() >= 5:
            arche[cell] = pre_arcs[m].mean(0)
    return arche


def wholecurve_fire(pre_arcs, arche):
    """Nearest-archetype (L2 over whole normalized curve). Fire if nearest is a winner archetype."""
    cells = list(arche.keys())
    A = np.stack([arche[c] for c in cells])            # (n_arch, NRS)
    fire = np.zeros(len(pre_arcs), bool)
    nearest = np.empty(len(pre_arcs), dtype=object)
    for i, arc in enumerate(pre_arcs):
        d = ((A - arc)**2).sum(1)
        j = int(np.argmin(d)); nearest[i] = cells[j]
        fire[i] = cells[j] in WIN_CELLS
    return fire, nearest


# ----------------------------- tail flatten -----------------------------
def flatten_point(name, coeffs, med_ext):
    """From the fitted TAIL eq, find the exhaustion/flatten point: first interior sign change of the
    derivative (peak/valley), else where |deriv| drops below 15% of its early magnitude (flattening)."""
    xg = np.linspace(0, 1, 400)
    yg = eval_form(name, coeffs, xg)
    dv = np.gradient(yg, xg)
    # sign change (peak or valley)
    sgn = np.sign(dv)
    chg = np.where((sgn[:-1] * sgn[1:] < 0))[0]
    if len(chg):
        tstar = float(xg[chg[0]])
        kind = "peak" if dv[0] > 0 else "valley"
    else:
        d0 = np.abs(dv[:40]).mean() + 1e-9
        below = np.where(np.abs(dv) < 0.15*d0)[0]
        if len(below):
            tstar = float(xg[below[0]]); kind = "flatten"
        else:
            tstar = 1.0; kind = "monotone"
    return tstar, kind, tstar*med_ext, float(eval_form(name, coeffs, np.array([tstar]))[0])


# ----------------------------- main per coin -----------------------------
def run(coin, report):
    d = load(coin)
    net, dur, hours = d["net"], d["dur"], float(d["hours"])
    pre_arcs, tail_arcs = d["pre_arcs"], d["tail_arcs"]
    masks, win, short = cell_masks(net, dur)
    n = len(net)
    report.append(f"\n{'='*78}\n## {coin.upper()}  n={n}  hours={hours:.1f}  base-win%={win.mean()*100:.1f}  "
                  f"med-dur={np.median(dur):.0f}s")
    report.append(f"  cell counts: " + "  ".join(f"{c}={int(masks[c].sum())}" for c in CELLS))

    # ---------- (a) 4 DISTINCT pre-fire equations ----------
    report.append(f"\n### (a) PRE-FIRE archetype equations — 4 DISTINCT curves (normalized time x: 0=birth, 1=fire)")
    pre_forms = {}
    for cell in CELLS:
        if masks[cell].sum() < 5:
            continue
        y = pre_arcs[masks[cell]].mean(0)
        (name, coeffs, r2, k), _ = best_form(y)
        st = limb_stats(y); pre_forms[cell] = (name, coeffs)
        report.append(f"  [{cell:11}] {fmt_form(name, coeffs)}   (R²={r2:.3f})")
        report.append(f"      start-y={st['start']:+.3f}  end-y(peak)={st['end']:+.3f}  born-depth(min)={st['dip']:+.3f}  "
                      f"below-0={st['below0']*100:.0f}%  ignition-t={st['t_ign']:.2f}  blade-slope={st['blade']:+.3f}")

    # ---------- (b) WHOLE-CURVE nearest-archetype ENTRY gate ----------
    report.append(f"\n### (b) ENTRY GATE — whole-curve nearest-archetype (native amp, whole pre-fire curve)")
    ung = metrics(np.ones(n, bool), net, win, short, hours)
    report.append(f"  UNGATED:            win%={ung['winpct']:.1f}  $/hr={ung['dph']:.3f}  legs={n}")
    fireE = energy_gate(d["pre_end"], net, dur); mE = metrics(fireE, net, win, short, hours)
    report.append(f"  ENERGY gate:        win%={mE['winpct']:.1f}  $/hr={mE['dph']:.3f}  fired={mE['firedpct']:.0f}%  "
                  f"SL-skip={mE['sl_skip']}/{mE['sl_tot']} LL-skip={mE['ll_skip']}/{mE['ll_tot']} WIN-skip={mE['w_skip']}/{mE['w_tot']}")
    # in-sample whole-curve
    arche_is = build_archetypes(pre_arcs, masks)
    fireW, nearest = wholecurve_fire(pre_arcs, arche_is); mW = metrics(fireW, net, win, short, hours)
    report.append(f"  WHOLE-CURVE (in-s): win%={mW['winpct']:.1f}  $/hr={mW['dph']:.3f}  fired={mW['firedpct']:.0f}%  "
                  f"SL-skip={mW['sl_skip']}/{mW['sl_tot']} LL-skip={mW['ll_skip']}/{mW['ll_tot']} WIN-skip={mW['w_skip']}/{mW['w_tot']}")
    # walk-forward: archetypes on first 60% (time order), score last 40%
    cut = int(n*0.6); idx_tr = np.arange(cut)
    arche_wf = build_archetypes(pre_arcs, masks, idx=idx_tr)
    fireW2, _ = wholecurve_fire(pre_arcs, arche_wf)
    te = slice(cut, n); hrs_te = hours*(n-cut)/n
    net_te, win_te, short_te = net[te], win[te], short[te]
    mWte = metrics(fireW2[te], net_te, win_te, short_te, hrs_te)
    ungte = metrics(np.ones(n-cut, bool), net_te, win_te, short_te, hrs_te)
    fireEte = energy_gate(d["pre_end"], net, dur)[te]; mEte = metrics(fireEte, net_te, win_te, short_te, hrs_te)
    report.append(f"  -- walk-forward (archetypes built on first 60%, scored on last 40%, {n-cut} legs) --")
    report.append(f"     UNGATED(OOS):     win%={ungte['winpct']:.1f}  $/hr={ungte['dph']:.3f}")
    report.append(f"     ENERGY(OOS):      win%={mEte['winpct']:.1f}  $/hr={mEte['dph']:.3f}  fired={mEte['firedpct']:.0f}%")
    report.append(f"     WHOLE-CURVE(OOS): win%={mWte['winpct']:.1f}  $/hr={mWte['dph']:.3f}  fired={mWte['firedpct']:.0f}%  "
                  f"SL-skip={mWte['sl_skip']}/{mWte['sl_tot']} LL-skip={mWte['ll_skip']}/{mWte['ll_tot']} WIN-skip={mWte['w_skip']}/{mWte['w_tot']}")
    # per cell x category breakdown of the in-sample whole-curve gate
    report.append(f"  per-cell fire (in-sample whole-curve): "
                  + "  ".join(f"{c}:{int(fireW[masks[c]].sum())}/{int(masks[c].sum())}fired" for c in CELLS))

    # ---------- (c) 4 DISTINCT tail equations ----------
    report.append(f"\n### (c) TAIL archetype equations — 4 DISTINCT curves (normalized time x: 0=fire, 1=close)")
    tail_forms = {}; tail_medext = {}
    for cell in CELLS:
        if masks[cell].sum() < 5:
            continue
        y = tail_arcs[masks[cell]].mean(0)
        (name, coeffs, r2, k), _ = best_form(y)
        st = limb_stats(y); tail_forms[cell] = (name, coeffs)
        tail_medext[cell] = float(np.median(d["tail_ext"][masks[cell]]))
        report.append(f"  [{cell:11}] {fmt_form(name, coeffs)}   (R²={r2:.3f})")
        report.append(f"      start-y={st['start']:+.3f}  end-y={st['end']:+.3f}  tail-ext-med={tail_medext[cell]:.0f}s")

    # ---------- (d) exhaustion / flatten point ----------
    report.append(f"\n### (d) EXHAUSTION / FLATTEN point per cell (from each distinct tail eq)")
    for cell in CELLS:
        if cell not in tail_forms:
            continue
        name, coeffs = tail_forms[cell]
        tstar, kind, tsec, yval = flatten_point(name, coeffs, tail_medext[cell])
        report.append(f"  [{cell:11}] {kind:8} at norm-t={tstar:.2f}  (~{tsec:.0f}s after fire, y={yval:+.3f})")

    return dict(coin=coin, pre_forms=pre_forms, tail_forms=tail_forms,
                mW=mW, mE=mE, ung=ung, mWte=mWte, mEte=mEte, ungte=ungte)


if __name__ == "__main__":
    coins = sys.argv[1:] or COINS
    report = ["# S74-corrected — 4 DISTINCT per-cell curves, 2 eqs each (pre-fire / tail), whole-curve gate"]
    summary = {}
    for coin in coins:
        if not os.path.exists(f"/tmp/kbook/{coin}_whole.npz"):
            report.append(f"\n## {coin.upper()}: whole.npz not ready, skipped"); continue
        summary[coin] = run(coin, report)
    txt = "\n".join(report)
    print(txt)
    with open(os.path.join(os.path.dirname(__file__), "_fit_output.txt"), "w") as f:
        f.write(txt)
    print("\nDONE", flush=True)
