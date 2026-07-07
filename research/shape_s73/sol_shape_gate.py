"""S73 — TEST THE STRENGTH OF THE INDIVIDUAL-PIECE SHAPE PLAN on SOL alone (Greg's spec).

WHAT THIS IS
  LIVE code = current lean + running exit, VERBATIM through run_kraken_cell (SOL cfg has bail=None -> NO
  deep-bail; exit = detector's next flow turn + cover_grace 300; one-sided maker, front-of-line). The shape
  strategy is layered on as an ENTRY GATE ONLY: trade / don't-trade, $5k per trade, every signal.

THE GATE (per Greg S73 — NO AVERAGING; test the INDIVIDUAL-PIECE plan with WIGGLE ROOM):
  The 4 archetypes (short/long x winner/loser) are FOUR SEPARATE SETS OF INDIVIDUAL CURVES — never collapsed
  to a mean/centroid. Each forming trade is matched to its k NEAREST INDIVIDUAL historical curves (the exact
  curve shapes), in the DISTINCT-DIFFERENCE feature space last session identified. The k neighbours are the
  WIGGLE ROOM (a trade need not match exactly). The neighbours VOTE trade / don't by whether they were
  winners or losers; ENTER iff the nearest exact curves were winners. Per-trade shape match (#0e), NO
  averaging anywhere (#0d / #0e-GATE). Direction/firing untouched (Greg-only).

WHERE THE DISTINCT DIFFERENCES ARE (last session, S71 handoff + two_shapes.py):
  - Clean separating pair = the DIAGONAL: long-winner ("took and rode": tall onset peak, long sustain) vs
    short-loser ("tried and died": low peak, immediate collapse).
  - The leakage-free PRE-ONSET tell = the onset-force PEAK/RISE (+ blade), carried by `preonset_features`
    (last session validated these carry the tell). We match on THOSE features — NOT the raw saturated arc
    (whose peak pins ~0.92 and washes the tell; that was the S73 first-cut mistake).

SCOPE: SOL only; every leg the lean fires is a $5k trade; no capacity / counter-capacity. In-sample
  (leave-one-out) AND 60/40 time-split OOS. Rudimentary; not tuned. Additive research; live path untouched.
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
# reuse the agent's exhaustion-graph extraction VERBATIM (minor changes only):
from arc_gate import load_raw, rolling_imb, preonset_features, false_start, FEATNAMES, CPS, PRE, POST, PRE_SEC

OUT = "/tmp/claude-0/-home-user-Markets/eb1a607f-25db-5f11-813f-08b83d3712c1/scratchpad"
os.makedirs(OUT, exist_ok=True)
CAP = 5000.0        # $5k per trade, every signal (no capacity model)
SMOOTH_SEC = 20     # same trailing flow smoothing as S71

def desc_feats(f):
    """DESCRIPTIVE full-arc tells (for the lifted table / picture ONLY — uses post-onset, not the gate):
    onset-peak height, sustain (took-and-rode vs tried-and-died), rise. From two_shapes.py."""
    seg = f[PRE-50:PRE+150]                         # -5..+15s around onset
    pk_rel = int(np.argmax(seg)); pk = seg[pk_rel]; pk_i = PRE-50+pk_rel
    half = 0.5*pk if pk > 0 else -1
    post = f[pk_i:]; below = np.where(post < half)[0]
    sustain = (below[0]*0.1) if (half > 0 and len(below)) else (len(post)*0.1)
    pre = f[:pk_i+1]; bl = np.where(pre < half)[0]
    rise = ((pk_i-bl[-1])*0.1) if (half > 0 and len(bl)) else pk_i*0.1
    return pk, sustain, rise

def run_sol():
    path = "/tmp/kbook/sol_book.jsonl"
    cfg = [c for c in KRAKEN if c.coin == "sol"][0]
    print(f"  SOL cfg (from strategy doc / KRAKEN registry): side={cfg.side} rev={cfg.rev} eps={cfg.eps} "
          f"bail={cfg.bail} grace={cfg.grace} improve={cfg.improve}  (bail=None -> NO deep-bail; one-sided "
          f"maker; exit = flow turn + cover-grace)", flush=True)
    raw = load_raw(path)
    ch, g = build_channels(path, cfg.K, 20, raw=raw)
    mid = np.asarray(g["mid"], float); bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
    buy = np.asarray(g["buy"], float); sell = np.asarray(g["sell"], float)
    hs = median_spread_bps(path, raw=raw) / 2.0
    N = len(mid); hours = N * 0.1 / 3600.0
    print(f"  gridded cells={N} ({hours:.1f}h)  running LIVE run_kraken_cell ...", flush=True)
    res, _ = run_kraken_cell(cfg, mid, buy, sell, bb, ba, hs)           # LIVE decision path, verbatim
    imb = rolling_imb(buy, sell, SMOOTH_SEC)
    X, net, arcs, dur, dfeat = [], [], [], [], []
    for l in res.legs:
        o = int(l.open_idx); c = int(l.close_idx); lo = o-PRE; hi = o+POST
        if lo < 0 or hi >= N or c <= o:
            continue
        f = imb[lo:hi+1] * int(l.side)                                  # sign to the trade's side
        pre = f[:PRE+1]                                                 # strictly pre-onset (leakage-free)
        X.append(preonset_features(pre) + [false_start(pre)[4]])       # last session's validated descriptors
        net.append(float(l.net_bps)); arcs.append(f.copy())
        dur.append((c-o)*0.1); dfeat.append(desc_feats(f))
    return (np.array(X), np.array(net), np.array(arcs), np.array(dur), np.array(dfeat), hours, len(res.legs))

# ---- per-trade SHAPE GATE = k nearest INDIVIDUAL curves, WIGGLE ROOM = k (NO averaging, NO centroid) ----
def knn_winfrac(A_ref, y_ref, A_q, k, exclude_self=False):
    """Match each query curve to its k NEAREST INDIVIDUAL reference curves (exact shapes, no template),
    return the winner-fraction among those k neighbours. The k neighbours ARE the wiggle room."""
    q2 = (A_q**2).sum(1)[:, None]; r2 = (A_ref**2).sum(1)[None, :]
    d = q2 + r2 - 2.0 * A_q @ A_ref.T
    if exclude_self:
        np.fill_diagonal(d, np.inf)
    idx = np.argpartition(d, k, axis=1)[:, :k]
    return y_ref[idx].mean(1)

def money(net, keep, hours, tag):
    ung = net.sum(); n = len(net); g = net[keep].sum(); nk = int(keep.sum())
    win_all = float((net > 0).mean()); win_k = float((net[keep] > 0).mean()) if nk else float("nan")
    print(f"    [{tag}] legs={n} ({hours:.1f}h)", flush=True)
    print(f"       UNGATED: net_bps={ung:8.0f}  $/hr={ung/1e4*CAP/hours:7.3f}  win%={win_all*100:.1f}", flush=True)
    print(f"       GATED  : net_bps={g:8.0f}  $/hr={g/1e4*CAP/hours:7.3f}  win%={win_k:.3f} "
          f"kept={nk} ({keep.mean()*100:.0f}%)  PnL-ret={100*g/ung if ung else float('nan'):.0f}%", flush=True)

def main():
    print("=== S73 INDIVIDUAL-PIECE SHAPE-GATE STRENGTH TEST — SOL alone, $5k/trade, LIVE lean+exit ===", flush=True)
    X, net, arcs, dur, dfeat, hours, n_all = run_sol()
    n = len(X)
    print(f"  SOL legs (all traded @ $5k): {n} of {n_all}  (~{hours:.1f}h)\n", flush=True)
    if n < 60:
        print("  too few legs; abort"); return

    win = net > 0
    med_dur = float(np.median(dur)); short = dur < med_dur
    print(f"  labels: winner=net>0 ({win.mean()*100:.1f}%)  |  median dur={med_dur:.0f}s  short<med ({short.mean()*100:.1f}%)\n", flush=True)

    # ---- lift SOL's distinct-difference numbers per bucket (PICTURE only; NOT the gate) ----
    print("  --- lifted SOL archetype tells per bucket (descriptive; NOT averaged into the gate) ---", flush=True)
    print(f"    {'bucket':11}{'n':>5}{'onset-peak':>11}{'sustain(s)':>11}{'rise(s)':>9}{'net/leg':>9}", flush=True)
    for k, m in [("LONG-WIN", win & ~short), ("SHORT-LOSE", ~win & short),
                 ("SHORT-WIN", win & short), ("LONG-LOSE", ~win & ~short)]:
        if m.sum() == 0:
            continue
        pk, sus, ri = dfeat[m].mean(0)
        print(f"    {k:11}{m.sum():>5}{pk:>11.3f}{sus:>11.1f}{ri:>9.1f}{net[m].mean():>9.3f}", flush=True)
    print("    (last-session tell: LONG-WIN 'took&rode' = tall peak/long sustain; SHORT-LOSE 'tried&died' = low peak/short sustain)\n", flush=True)

    # ================= THE GATE: individual-curve k-NN, wiggle = k (NO averaging) =================
    print("  ===== INDIVIDUAL-PIECE GATE (k nearest EXACT curves; k = wiggle room) =====", flush=True)
    cut = int(n*0.6); tr = slice(0, cut); te = slice(cut, n)
    for k in (5, 11, 21):
        print(f"\n  --- wiggle k={k} nearest individual curves ---", flush=True)
        # IN-SAMPLE (leave-one-out; z-score on all)
        mu, sd = X.mean(0), X.std(0)+1e-9; Xz = (X-mu)/sd
        wf_is = knn_winfrac(Xz, win.astype(float), Xz, k, exclude_self=True)
        money(net, wf_is > 0.5, hours, f"IN-SAMPLE k={k}")
        # OOS (train = ref library, test = query; z-score on train)
        mu_t, sd_t = X[tr].mean(0), X[tr].std(0)+1e-9
        wf_oos = knn_winfrac((X[tr]-mu_t)/sd_t, win[tr].astype(float), (X[te]-mu_t)/sd_t, k)
        hours_te = hours*(n-cut)/n
        money(net[te], wf_oos > 0.5, hours_te, f"OOS-last40% k={k}")

    # ---- picture: the 4 archetype mean arcs (reference ONLY, NOT the grader) ----
    tsec = (np.arange(PRE+POST+1)-PRE)*0.1
    fig, ax = plt.subplots(figsize=(10, 5))
    for k, m, col, lw in [("LONG-WIN", win & ~short, "C2", 2.2), ("SHORT-LOSE", ~win & short, "C3", 2.2),
                          ("SHORT-WIN", win & short, "C1", 1.2), ("LONG-LOSE", ~win & ~short, "C4", 1.2)]:
        if m.sum() == 0:
            continue
        ax.plot(tsec, arcs[m].mean(0), color=col, lw=lw, label=f"{k} (n={int(m.sum())})")
    ax.axvline(0, color="k", ls="--", lw=1, alpha=0.6); ax.axhline(0, color="gray", lw=0.6)
    ax.axvspan(-PRE_SEC, 0, color="k", alpha=0.05)
    ax.set_title("SOL — mean with-trade FLOW arc per archetype (PICTURE only; gate matches each trade's OWN "
                 "shape to individual curves)")
    ax.set_xlabel("seconds relative to onset (t=0)"); ax.set_ylabel("mean signed flow")
    ax.legend(fontsize=8); ax.grid(alpha=0.25)
    pp = os.path.join(OUT, "sol_shape_archetypes.png")
    plt.tight_layout(); plt.savefig(pp, dpi=110); plt.close()
    print(f"\n  saved {pp}\nDONE", flush=True)

if __name__ == "__main__":
    main()
