"""S77 MAJORS SHAPE-FOLLOW ENTRY GATE — BTC / ETH (then XRP / DOGE).

Greg's #0f whole-curve shape-match, aimed at the MAJORS (S75 built it on SOL — the wrong coin, and SOL has no
direction so it capped at ~62%). Here we REBUILD the 4 archetype shapes PER MAJOR and ask: does firing only on
WINNER shapes / skipping LOSER shapes LIFT $/hr over ungated, with a NON-patient ride-to-reversal exit?

Reuses the S75 machinery verbatim:
  - executor entries  = odcore.platform.run_kraken_cell legs (FIRING LOCKED — Greg only; the gate only FILTERS)
  - pre-fire curve    = leg_imbalance.py construction: causal birth->onset ignition arc of the with-side TRADE
                        imbalance ratio (rolling_imb), native amplitude, resampled to NRS=100. Leakage-free.
  - archetypes        = per-cell MEAN pre-fire arc (4 DISTINCT buckets: short/long x win/lose). No centroid.
  - gate              = fit_shapes.wholecurve_fire: nearest-archetype L2 over the WHOLE raw curve; fire if the
                        nearest of the 4 is a WINNER archetype (+ optional winner-wiggle, sol_gate style).
  - exit              = book_swing_kraken.swing ride-to-reversal: ride until price retraces TRAIL bps from the
                        best favorable excursion, or MAXHOLD. NON-patient (majors, per Greg this session).

HARD RULES obeyed: NEVER normalize/average/smooth the per-leg curve (raw amplitude IS the edge); SHAPE/RATIO only
(imbalance ratio in [-1,1], no raw volume/price); 4 buckets kept SEPARATE (no mean/centroid gate); leakage-free
(only the causal pre-onset limb is visible at decision time); walk-forward (archetypes + median-split on first 60%,
test the gate on the held-out 40%; labels defined by the RIDE outcome so the gate predicts what we actually trade).

The four tiny numeric helpers (load_raw, rolling_imb, ignition_idx, resample) are copied VERBATIM from
research/shape_s71/{arc_gate.py, whole_legs.py} so this driver imports only numpy + the executor (the S75
arc_gate/fit_shapes modules pull sklearn/scipy, which the import chain in this container breaks).

    python3 majors_shape_gate.py [btc eth xrp doge ...]
"""
import os, sys, json, types
import numpy as np
sys.path.insert(0, "/home/user/Markets")
# shim matplotlib (executor's dep chain imports it at module load; we never draw)
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
from _birth_probe import _depthK
from _liquidity_dive import build_channels, median_spread_bps
from odcore.platform import run_kraken_cell, KRAKEN

# --- knobs (from leg_imbalance.py / book_swing_kraken.py) ---
CPS = 10                       # cells per second (0.1s book)
SMOOTH_SEC = 20                # rolling imbalance window
LOOKBACK = 150 * CPS           # up to 150s back to find natural birth
NRS = 100                      # resample points on the pre-fire curve
CAP = 5000.0                   # $ flat per fired signal
CELLS = ["short-win", "short-lose", "long-win", "long-lose"]
WIN = {"short-win", "long-win"}
TRAIL = 30.0                   # wide ride-to-reversal trailing stop (bps), the paper's spec
MAXHOLD_S = 600                # ~10 min max hold
FEES = [0.0, 5.0, 10.0]        # round-trip bps: 0=both-maker (Coinbase 0% intro), 5=1 taker leg, 10=both taker
WIGGLE = 0.15                  # winner-wiggle: a winner within 15% of the nearest loser still fires (sol_gate #0e)


# ---------------- verbatim S75 helpers (numpy only) ----------------
def load_raw(path):                                            # arc_gate.load_raw (verbatim)
    ts, mid, buy, sell, spread = [], [], [], [], []
    b1, b3, b5, b10, a1, a3, a5, a10 = [], [], [], [], [], [], [], []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            ts.append(r["ts"]); mid.append(r["mid"]); spread.append(r.get("spread"))
            buy.append(r.get("buy", 0.0) or 0.0); sell.append(r.get("sell", 0.0) or 0.0)
            x = _depthK(r["bids"]); b1.append(x[0]); b3.append(x[1]); b5.append(x[2]); b10.append(x[3])
            y = _depthK(r["asks"]); a1.append(y[0]); a3.append(y[1]); a5.append(y[2]); a10.append(y[3])
    return dict(ts=np.array(ts), mid=np.array(mid), buy=np.array(buy), sell=np.array(sell),
                spread=np.array([np.nan if v is None else v for v in spread], float),
                bidK={1: np.array(b1), 3: np.array(b3), 5: np.array(b5), 10: np.array(b10)},
                askK={1: np.array(a1), 3: np.array(a3), 5: np.array(a5), 10: np.array(a10)})


def rolling_imb(buy, sell, w_sec):                             # arc_gate.rolling_imb (verbatim)
    w = int(w_sec * CPS); cb = np.concatenate([[0.], np.cumsum(buy)]); cs = np.concatenate([[0.], np.cumsum(sell)])
    ix = np.arange(len(buy)); lo = np.maximum(ix + 1 - w, 0)
    B = cb[ix + 1] - cb[lo]; S = cs[ix + 1] - cs[lo]; tot = B + S
    out = np.zeros(len(buy)); nz = tot > 0; out[nz] = (B[nz] - S[nz]) / tot[nz]
    return out


def ignition_idx(seg):                                         # whole_legs.ignition_idx (verbatim)
    m = np.minimum.accumulate(seg[::-1])[::-1]
    cand = np.where(seg <= m + 1e-9)[0]
    ig = cand[0] if len(cand) else 0
    ig = ig + int(np.argmin(seg[ig:]))
    return ig


def resample(limb, n=NRS):                                     # whole_legs.resample (verbatim)
    L = len(limb)
    xs = np.linspace(0, 1, n)
    return np.interp(xs, np.linspace(0, 1, L), limb)


# ---------------- ride-to-reversal exit (book_swing_kraken.swing, vectorized) ----------------
def ride(o, s, mid, trail=TRAIL, maxhold_cells=MAXHOLD_S * CPS):
    """Enter at index o on side s; ride the favorable mid excursion, exit when it retraces `trail` bps from
    its best, or at maxhold. Returns (gross_bps_at_exit, hold_seconds). Fees applied by caller."""
    entry = mid[o]; hi = min(len(mid) - 1, o + maxhold_cells)
    if hi <= o:
        return None
    fav = s * (mid[o + 1:hi + 1] - entry) / entry * 1e4          # favorable bps path (native, mid frame)
    run_max = np.maximum.accumulate(fav)
    draw = run_max - fav
    hit = np.where(draw >= trail)[0]
    if len(hit):
        j = int(hit[0]); return float(fav[j]), (j + 1) * 0.1
    return float(fav[-1]), len(fav) * 0.1


# ---------------- per-leg pre-fire curve + ride ----------------
def build_legs(coin):
    """Run the LIVE executor, then per entry leg build (a) the causal pre-fire arc and (b) the ride-exit PnL.
    Returns a dict of aligned arrays; entries are in time order (open_idx ascending)."""
    path = f"/tmp/kbook/{coin}_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == coin][0]
    raw = load_raw(path); ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    N = len(mid); hours = N * 0.1 / 3600.0
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)       # FIRING (entries) — Greg-locked
    imb = rolling_imb(buy, sell, SMOOTH_SEC)                        # with-trade flow imbalance ratio [-1,1]
    legs = sorted(res.legs, key=lambda z: int(z.open_idx)); prev_close = -1
    arcs, gross, hold, side, exec_net, exec_dur, opens = [], [], [], [], [], [], []
    for l in legs:
        o = int(l.open_idx); c = int(l.close_idx); s = int(l.side)
        lo = max(0, o - LOOKBACK, prev_close + 1); prev_close = c
        if c <= o:
            continue
        seg = imb[lo:o + 1] * s
        if len(seg) < 30:
            continue
        birth = lo + ignition_idx(seg)
        pre = imb[birth:o + 1] * s                                  # causal pre-fire limb (native amplitude)
        if len(pre) < 12:
            continue
        rd = ride(o, s, mid)
        if rd is None:
            continue
        arcs.append(resample(pre)); gross.append(rd[0]); hold.append(rd[1]); side.append(s)
        exec_net.append(float(l.net_bps)); exec_dur.append((c - o) * 0.1); opens.append(o)
    return dict(coin=coin, hours=hours, N=N, half_spread=hs, mid=mid, opens=np.array(opens),
                arcs=np.array(arcs), gross=np.array(gross), hold=np.array(hold),
                side=np.array(side), exec_net=np.array(exec_net), exec_dur=np.array(exec_dur))


# ---------------- archetypes + gate (fit_shapes logic) ----------------
def cell_masks(net, dur):
    """4 buckets: WIN/LOSE by ride outcome (net>0, what the ride exit realizes), SHORT/LONG by the leg's natural
    (executor) duration median-split — the leg_imbalance archetype axis (the ride-hold saturates at maxhold and
    can't split duration, so the natural leg length is the honest short/long signifier)."""
    win = net > 0; med = np.median(dur); short = dur < med
    return {"short-win": short & win, "short-lose": short & ~win,
            "long-win": ~short & win, "long-lose": ~short & ~win}, med


def build_archetypes(arcs, masks, idx):
    """Mean pre-fire curve per cell (native amplitude), TRAIN legs only. No centroid across cells."""
    sel = np.zeros(len(arcs), bool); sel[idx] = True
    arche = {}
    for c in CELLS:
        m = masks[c] & sel
        if m.sum() >= 5:
            arche[c] = arcs[m].mean(0)
    return arche


def wholecurve_fire(arcs, arche, wiggle=0.0):
    """Nearest-archetype L2 over the whole raw curve. fire if nearest is a WINNER archetype. With wiggle>0,
    a winner archetype within (1+wiggle)x the nearest LOSER distance still fires (sol_gate winner_match)."""
    cells = list(arche.keys())
    haswin = [c for c in cells if c in WIN]; haslose = [c for c in cells if c not in WIN]
    A = np.stack([arche[c] for c in cells])
    fire = np.zeros(len(arcs), bool); nearest = np.empty(len(arcs), dtype=object)
    for i, arc in enumerate(arcs):
        d = ((A - arc) ** 2).sum(1)
        j = int(np.argmin(d)); nearest[i] = cells[j]
        if wiggle > 0 and haswin and haslose:
            wd = min(d[cells.index(c)] for c in haswin)
            ld = min(d[cells.index(c)] for c in haslose)
            fire[i] = wd <= ld * (1.0 + wiggle)
        else:
            fire[i] = cells[j] in WIN
    return fire, nearest


# ---------------- reporting ----------------
def ramp(y):
    """Shape descriptors Greg reads by eye: peak (energy at onset), ascent SLOPE, LINEARITY R^2, below-0 frac,
    born-depth (min). Native amplitude — NO normalization."""
    x = np.linspace(0, 1, len(y)); b = np.polyfit(x, y, 1); yh = np.polyval(b, x)
    ss = ((y - y.mean()) ** 2).sum(); r2 = 1.0 - ((y - yh) ** 2).sum() / (ss + 1e-12)
    return float(y[-1]), float(b[0]), float(r2), float((y < 0).mean()), float(y.min())


def dph(net, hours):
    return net.sum() / 1e4 * CAP / hours if len(net) else 0.0


def report(d, wiggle=0.0):
    coin = d["coin"]; arcs = d["arcs"]; gross = d["gross"]; hold = d["hold"]; side = d["side"]; hours = d["hours"]
    dur = d["exec_dur"]; n = len(gross)
    masks, med = cell_masks(gross, dur)                               # win/lose=ride outcome, short/long=exec dur
    out = {"coin": coin, "n": n, "hours": round(hours, 1), "med_dur_s": round(float(med), 1)}
    print(f"\n{'='*92}\n### {coin.upper()}_kraken — SHAPE-FOLLOW gate, ride-to-reversal exit (trail={TRAIL:.0f}bp, "
          f"maxhold={MAXHOLD_S}s, wiggle={wiggle})", flush=True)
    print(f"  legs={n}  hours={hours:.1f}  median-dur={med:.0f}s  mean-ride-hold={hold.mean():.0f}s  "
          f"half-spread={d['half_spread']:.2f}bp  exec-base-win%(patient exit)={ (d['exec_net']>0).mean()*100:.1f}",
          flush=True)
    print(f"  cell counts (whole window): " + "  ".join(f"{c}={int(masks[c].sum())}" for c in CELLS), flush=True)

    # walk-forward split
    cut = int(n * 0.6); idx_tr = np.arange(cut); te = slice(cut, n)
    hrs_te = hours * (n - cut) / n
    gross_te, dur_te, side_te = gross[te], dur[te], side[te]
    win_te = gross_te > 0

    # archetypes on TRAIN only
    arche = build_archetypes(arcs, masks, idx_tr)
    print(f"\n  -- 4 archetype pre-fire SHAPES (built on TRAIN 60%={cut} legs; native amplitude) --", flush=True)
    print(f"     {'cell':11}{'n_tr':>5}{'peak':>8}{'slope':>8}{'linR2':>7}{'below0%':>9}{'born-dip':>9}", flush=True)
    shp = {}
    for c in CELLS:
        if c not in arche:
            print(f"     {c:11}  (fewer than 5 train legs — skipped)", flush=True); continue
        pk, sl, r2, b0, dip = ramp(arche[c]); shp[c] = dict(peak=pk, slope=sl, linR2=r2, below0=b0, dip=dip)
        ntr = int((masks[c] & (np.arange(n) < cut)).sum())
        print(f"     {c:11}{ntr:>5}{pk:>+8.3f}{sl:>+8.3f}{r2:>7.3f}{b0*100:>8.0f}%{dip:>+9.3f}", flush=True)
    out["shapes"] = shp

    # winner-vs-loser archetype separation (are the 4 buckets distinct shapes?)
    def sep(a, b):
        return float(np.sqrt(((arche[a] - arche[b]) ** 2).sum())) if a in arche and b in arche else float("nan")
    print(f"     archetype L2 separation: SW-SL={sep('short-win','short-lose'):.3f}  "
          f"LW-LL={sep('long-win','long-lose'):.3f}  SW-LW={sep('short-win','long-win'):.3f}  "
          f"SL-LL={sep('short-lose','long-lose'):.3f}", flush=True)

    # the gate on OOS
    fire, nearest = wholecurve_fire(arcs, arche, wiggle=wiggle)
    fire_te = fire[te]
    print(f"\n  -- OOS (held-out last 40% = {n-cut} legs, {hrs_te:.1f}h) --", flush=True)
    print(f"     {'variant':24}{'legs':>6}{'fire%':>7}{'win%':>7}{'$/hr@0':>9}{'$/hr@5':>9}{'$/hr@10':>9}", flush=True)

    def line(label, mask):
        g = gross_te[mask]; wk = (g > 0).mean() * 100 if len(g) else float("nan")
        row = [f"{label:24}{int(mask.sum()):>6}{mask.mean()*100:>6.0f}%{wk:>7.1f}"]
        res = {"legs": int(mask.sum()), "fire_pct": round(float(mask.mean()*100), 1), "win_pct": round(float(wk), 1)}
        for fee in FEES:
            v = dph(g - fee, hrs_te); row.append(f"{v:>9.3f}"); res[f"dph_fee{int(fee)}"] = round(v, 3)
        print("     " + "".join(row), flush=True)
        return res

    out["ungated"] = line("UNGATED", np.ones(n - cut, bool))
    out["gated"] = line("SHAPE-GATE", fire_te)

    # random-skip control: skip the same COUNT at random, avg over 200 draws -> is shape-selection > chance?
    rng = np.random.default_rng(0); k = int(fire_te.sum()); m = n - cut
    if 0 < k < m:
        rvals = []
        for _ in range(200):
            sel = np.zeros(m, bool); sel[rng.choice(m, k, replace=False)] = True
            rvals.append(dph(gross_te[sel], hrs_te))
        rmean, rstd = float(np.mean(rvals)), float(np.std(rvals))
        gate0 = out["gated"]["dph_fee0"]
        z = (gate0 - rmean) / (rstd + 1e-9)
        print(f"     random-skip control (same {k} kept, 200 draws): $/hr@0 mean={rmean:.3f}±{rstd:.3f}  "
              f"-> shape-gate z={z:+.2f}", flush=True)
        out["random_skip"] = {"mean_dph0": round(rmean, 3), "std": round(rstd, 3), "gate_z": round(z, 2)}

    # skip breakdown: of what the gate SKIPPED on OOS, how many were losers (good) vs winners (bad)?
    skip = ~fire_te
    sl = (~win_te) & (dur_te < med); ll = (~win_te) & (dur_te >= med)
    sw = win_te & (dur_te < med); lw = win_te & (dur_te >= med)
    print(f"     SKIP breakdown (OOS): losers-skipped SL={int((skip&sl).sum())}/{int(sl.sum())} "
          f"LL={int((skip&ll).sum())}/{int(ll.sum())} | winners-skipped SW={int((skip&sw).sum())}/{int(sw.sum())} "
          f"LW={int((skip&lw).sum())}/{int(lw.sum())}", flush=True)
    out["skip"] = dict(SL=[int((skip&sl).sum()), int(sl.sum())], LL=[int((skip&ll).sum()), int(ll.sum())],
                       SW=[int((skip&sw).sum()), int(sw.sum())], LW=[int((skip&lw).sum()), int(lw.sum())])

    # the DIRECTION wall (S75 flip test on the ride frame): are OOS losers just winners entered backwards?
    lose = gross_te <= 0
    if lose.sum():
        flipped = -gross_te[lose]            # opposite side over same window ~= -gross (mid-symmetric)
        conv = (flipped > 0).mean() * 100
        allrev = gross_te.copy(); allrev[lose] = -gross_te[lose]
        print(f"     DIRECTION check: {conv:.0f}% of OOS losers flip to winners if side reversed  "
              f"(reverse-all-losers ceiling $/hr@0={dph(allrev, hrs_te):.3f} vs ungated {out['ungated']['dph_fee0']:.3f})",
              flush=True)
        out["direction"] = {"losers_flip_pct": round(float(conv), 1),
                            "reverse_all_ceiling_dph0": round(dph(allrev, hrs_te), 3)}
    return out


def trail_sweep(d):
    """Exit-parameter sensitivity: ungated ride win%/$/hr@0 across trailing-stop widths (OOS 40%). Shows whether
    the 30bp/600s ride saturates at maxhold (mean-hold ~ maxhold => trail rarely bites)."""
    mid = d["mid"]; opens = d["opens"]; side = d["side"]; hours = d["hours"]; n = len(opens)
    cut = int(n * 0.6); te = np.arange(cut, n); hrs_te = hours * (n - cut) / n
    print(f"  -- exit sensitivity (ungated ride, OOS): trail width sweep --", flush=True)
    print(f"     {'trail':>7}{'win%':>7}{'mean-hold':>11}{'$/hr@0':>9}{'$/hr@10':>9}", flush=True)
    for tr in (10.0, 15.0, 20.0, 30.0, 50.0):
        g = []; h = []
        for i in te:
            rd = ride(int(opens[i]), int(side[i]), mid, trail=tr)
            if rd: g.append(rd[0]); h.append(rd[1])
        g = np.array(g); h = np.array(h)
        print(f"     {tr:>7.0f}{(g>0).mean()*100:>7.1f}{h.mean():>11.0f}{dph(g, hrs_te):>9.3f}{dph(g-10, hrs_te):>9.3f}",
              flush=True)


def main():
    coins = sys.argv[1:] or ["btc", "eth"]
    allout = {}
    for coin in coins:
        print(f"\n... loading + running executor for {coin} ...", flush=True)
        d = build_legs(coin)
        allout[coin] = report(d, wiggle=0.0)
        allout[coin + "_wiggle"] = report(d, wiggle=WIGGLE)
        trail_sweep(d)
    op = os.path.join(os.path.dirname(__file__), "majors_shape_gate_results.json")
    with open(op, "w") as f:
        json.dump(allout, f, indent=2, default=float)
    print(f"\nsaved {op}\nDONE", flush=True)


if __name__ == "__main__":
    main()
