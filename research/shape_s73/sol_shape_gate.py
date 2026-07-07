"""S73 — RUDIMENTARY shape-strategy test on SOL alone (Greg's spec, kept as simple as possible).

WHAT THIS IS
  LIVE code = the current lean + running exit, VERBATIM through run_kraken_cell (SOL cfg has bail=None,
  so NO deep-bail; exit = detector's next flow turn + cover_grace 300). The shape strategy is layered on
  as an ENTRY GATE ONLY: enter or don't.

THE GATE (per Greg S73): lift the VALUES + SHAPES of SOL winners / losers / shorts / longs from SOL's own
  legs -> 4 archetype centroids (short/long x winner/loser) in standardized pre-onset-shape space. Each
  trade is matched to its NEAREST archetype by its OWN pre-onset ascent shape; ENTER iff nearest is a
  WINNER archetype, else SKIP. This is a per-trade SHAPE MATCH (#0e: the curve, not an AUC scalar; #0d:
  each trade decided on its own shape, the centroids are only the archetype PICTURE), NOT a fitted
  classifier. Direction/firing untouched (Greg-only).

  Rudimentary "ascent algebra" = the general-shape fit of the pre-onset ignition limb: start level
  (above/below zero), peak height, ascent slope, blade (last-10s slope), curvature. No coarseness tuning.

SCOPE: SOL only, first 5000 legs, no capacity / cap-utilization / counter-capacity (trade $5k when a
  signal is available, as normal). In-sample (Greg's literal "lift and gate") AND a 60/40 time-split OOS
  reported side by side so the number isn't trivially circular. Not tuned.
Additive research; commits nothing to the live path.
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/user/Markets"
for p in (ROOT, os.path.join(ROOT, "scripts"), os.path.join(ROOT, "research", "shape_s71")):
    if p not in sys.path:
        sys.path.insert(0, p)
from _liquidity_dive import build_channels, median_spread_bps
from odcore.platform import run_kraken_cell, KRAKEN
from arc_gate import load_raw, rolling_imb, CPS, PRE, POST, PRE_SEC, POST_SEC  # reuse S71 extraction

OUT = "/tmp/claude-0/-home-user-Markets/eb1a607f-25db-5f11-813f-08b83d3712c1/scratchpad"
os.makedirs(OUT, exist_ok=True)
CAP = 5000.0        # $5k per trade, as normal (no capacity model)
NMAX = 5000         # first 5000 legs
SMOOTH_SEC = 20     # trailing flow smoothing (same as S71)

# ---- the rudimentary ascent-algebra shape features of the PRE-ONSET ignition limb (leakage-free) ----
FEATNAMES = ["start", "peak", "slope", "blade", "curv"]
def shape_feats(pre):
    """pre = signed with-trade flow over the strictly pre-onset limb [-45s .. 0]. General shape only."""
    x = (np.arange(len(pre)) - PRE) * 0.1                 # seconds -45..0
    start = float(pre[0])                                 # start above/below zero
    peak = float(pre.max())                               # peak height of the ignition limb
    slope = float(np.polyfit(x, pre, 1)[0])               # rate of ascent (flow/s)
    blade = float(np.polyfit(x[-10*CPS:], pre[-10*CPS:], 1)[0])  # last-10s slope (the hockey-stick blade)
    curv = float(np.polyfit(x, pre, 2)[0])                # curvature / acceleration
    return [start, peak, slope, blade, curv]

def run_sol():
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    print(f"  SOL cfg: side={cfg.side} rev={cfg.rev} eps={cfg.eps} bail={cfg.bail} grace={cfg.grace} "
          f"improve={cfg.improve}  (bail=None -> NO deep-bail; exit = flow turn + cover-grace)", flush=True)
    raw = load_raw(path)
    ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    N = len(mid); hours = N * 0.1 / 3600.0
    print(f"  gridded cells={N}  ({hours:.1f}h)  running LIVE run_kraken_cell ...", flush=True)
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)            # LIVE decision path, verbatim
    imb = rolling_imb(buy, sell, SMOOTH_SEC)

    X, net, arcs, dur, opent = [], [], [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx); lo = o - PRE; hi = o + POST
        if lo < 0 or hi >= N or c <= o:
            continue
        f = imb[lo:hi+1] * int(l.side)                                   # sign to the trade's side
        X.append(shape_feats(f[:PRE+1]))
        net.append(float(l.net_bps)); arcs.append(f.copy())
        dur.append((c - o) * 0.1); opent.append(o)
        if len(X) >= NMAX:
            break
    return (np.array(X), np.array(net), np.array(arcs), np.array(dur),
            np.array(opent), hours, len(res.legs), N)

# ---- 4-archetype nearest-centroid SHAPE GATE ----
def build_centroids(Xz, win, short):
    """Xz = standardized features. Returns {bucket: centroid}, bucket in {'SW','LW','SL','LL'}."""
    cents = {}
    masks = {"SW": win & short, "LW": win & ~short, "SL": ~win & short, "LL": ~win & ~short}
    for k, m in masks.items():
        if m.sum() >= 1:
            cents[k] = Xz[m].mean(0)
    return cents

def gate(Xz, cents):
    """nearest archetype; ENTER iff nearest is a winner bucket (SW/LW)."""
    keys = list(cents); C = np.array([cents[k] for k in keys])
    d = ((Xz[:, None, :] - C[None, :, :]) ** 2).sum(2)                   # (n, k) sq-dist
    nearest = np.array(keys)[d.argmin(1)]
    return np.array([k in ("SW", "LW") for k in nearest]), nearest

def money(net, keep, hours, tag):
    ung = net.sum(); n = len(net)
    g = net[keep].sum(); nk = int(keep.sum())
    win_all = float((net > 0).mean()); win_kept = float((net[keep] > 0).mean()) if nk else float("nan")
    print(f"    [{tag}] legs={n} ({hours:.1f}h)", flush=True)
    print(f"       UNGATED: net_bps={ung:8.0f}  bps/hr={ung/hours:7.2f}  ${ung/1e4*CAP:8.0f}  "
          f"$/hr={ung/1e4*CAP/hours:7.3f}  win%={win_all*100:.1f}", flush=True)
    print(f"       GATED  : net_bps={g:8.0f}  bps/hr={g/hours:7.2f}  ${g/1e4*CAP:8.0f}  "
          f"$/hr={g/1e4*CAP/hours:7.3f}  win%={win_kept*100:.1f}  kept={nk} ({keep.mean()*100:.0f}%)  "
          f"PnL-retained={100*g/ung if ung else float('nan'):.0f}%", flush=True)
    return dict(ung=ung, g=g, nk=nk)

def main():
    print("=== S73 RUDIMENTARY SHAPE-GATE TEST — SOL alone, first 5000 legs, LIVE lean+exit ===", flush=True)
    X, net, arcs, dur, opent, hours_all, n_all, N = run_sol()
    n = len(X)
    hours = n / n_all * hours_all if n_all else hours_all   # hours spanned by the legs we took
    print(f"  usable legs (full pre-onset window): {n} of {n_all} total  (~{hours:.1f}h)\n", flush=True)
    if n < 50:
        print("  too few legs; abort"); return

    win = net > 0
    med_dur = float(np.median(dur)); short = dur < med_dur
    print(f"  labels: winner=net>0 ({win.mean()*100:.1f}%)  |  median duration={med_dur:.0f}s  "
          f"short<med ({short.mean()*100:.1f}%)", flush=True)
    # ---- lift the VALUES + SHAPES per bucket (what Greg asked to see) ----
    print("\n  --- lifted archetype VALUES (raw feature means per bucket) ---", flush=True)
    print(f"    {'bucket':8}{'n':>6}  " + "".join(f"{nm:>9}" for nm in FEATNAMES) +
          f"{'net/leg':>9}", flush=True)
    for k, m in [("SHORT-WIN", win & short), ("LONG-WIN", win & ~short),
                 ("SHORT-LOSE", ~win & short), ("LONG-LOSE", ~win & ~short)]:
        if m.sum() == 0:
            continue
        mv = X[m].mean(0)
        print(f"    {k:8}{m.sum():>6}  " + "".join(f"{v:9.3f}" for v in mv) +
              f"{net[m].mean():9.3f}", flush=True)

    # ================= IN-SAMPLE (Greg's literal: lift from all, gate all) =================
    print("\n  ===== GATE RESULTS =====", flush=True)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xz = (X - mu) / sd
    cents = build_centroids(Xz, win, short)
    keep_is, near_is = gate(Xz, cents)
    money(net, keep_is, hours, "IN-SAMPLE")

    # ================= 60/40 TIME-SPLIT OOS (honest) =================
    cut = int(n * 0.6)
    tr = slice(0, cut); te = slice(cut, n)
    mu_t, sd_t = X[tr].mean(0), X[tr].std(0) + 1e-9
    cents_t = build_centroids((X[tr] - mu_t) / sd_t, win[tr], short[tr])
    keep_oos, _ = gate((X[te] - mu_t) / sd_t, cents_t)
    hours_te = hours * (n - cut) / n
    money(net[te], keep_oos, hours_te, "OOS last40%")

    # ---- picture: the 4 archetype mean arcs (reference only, NOT the grader) ----
    tsec = (np.arange(PRE + POST + 1) - PRE) * 0.1
    fig, ax = plt.subplots(figsize=(10, 5))
    for k, m, col in [("SHORT-WIN", win & short, "C2"), ("LONG-WIN", win & ~short, "C0"),
                      ("SHORT-LOSE", ~win & short, "C3"), ("LONG-LOSE", ~win & ~short, "C1")]:
        if m.sum() == 0:
            continue
        ax.plot(tsec, arcs[m].mean(0), color=col, lw=2, label=f"{k} (n={int(m.sum())})")
    ax.axvline(0, color="k", ls="--", lw=1, alpha=0.6); ax.axhline(0, color="gray", lw=0.6)
    ax.axvspan(-PRE_SEC, 0, color="k", alpha=0.05)
    ax.set_title("SOL — mean with-trade FLOW arc per archetype (shaded=pre-onset, the readable-live limb) "
                 "[PICTURE only; gate matches each trade's OWN shape]")
    ax.set_xlabel("seconds relative to onset (t=0)"); ax.set_ylabel("mean signed flow")
    ax.legend(fontsize=8); ax.grid(alpha=0.25)
    pp = os.path.join(OUT, "sol_shape_archetypes.png")
    plt.tight_layout(); plt.savefig(pp, dpi=110); plt.close()
    print(f"\n  saved {pp}", flush=True)
    print("DONE", flush=True)

if __name__ == "__main__":
    main()
