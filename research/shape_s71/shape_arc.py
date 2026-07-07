"""S71 SHAPE-of-signal first cut: map the onset->exhaustion ARC of order-flow imbalance,
second by second, for a handful of SHAPE-matched btc_kraken legs. Trades come through the
LIVE path (odcore.platform.run_kraken_cell). Descriptive; commits nothing."""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/home/user/Markets"
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _birth_probe import to_grid, _depthK
import _liquidity_dive as LD
from _liquidity_dive import build_channels, median_spread_bps
from odcore.platform import run_kraken_cell, KRAKEN, FLOW_W

BOOK = "/tmp/kbook/btc_book.jsonl"
OUT = "/tmp/claude-0/-home-user-Markets/9c530e49-5a24-51c2-b8c4-60c751ae23a0/scratchpad"

# ---- load the plain-jsonl book into the same 'raw' schema load_book produces ----
print("loading book...", flush=True)
ts, mid, buy, sell, spread = [], [], [], [], []
b1, b3, b5, b10, a1, a3, a5, a10 = [], [], [], [], [], [], [], []
with open(BOOK) as f:
    for line in f:
        r = json.loads(line)
        ts.append(r["ts"]); mid.append(r["mid"]); spread.append(r.get("spread"))
        buy.append(r.get("buy", 0.0) or 0.0); sell.append(r.get("sell", 0.0) or 0.0)
        x1, x3, x5, x10 = _depthK(r["bids"]); b1.append(x1); b3.append(x3); b5.append(x5); b10.append(x10)
        y1, y3, y5, y10 = _depthK(r["asks"]); a1.append(y1); a3.append(y3); a5.append(y5); a10.append(y10)
raw = dict(ts=np.array(ts), mid=np.array(mid), buy=np.array(buy), sell=np.array(sell),
           spread=np.array([np.nan if x is None else x for x in spread], float),
           bidK={1: np.array(b1), 3: np.array(b3), 5: np.array(b5), 10: np.array(b10)},
           askK={1: np.array(a1), 3: np.array(a3), 5: np.array(a5), 10: np.array(a10)})
print(f"  {len(ts)} book rows", flush=True)

cfg = [c for c in KRAKEN if c.coin == "btc"][0]
K = cfg.K
ch, g = build_channels(BOOK, K, FLOW_W, raw=raw)
mid = np.asarray(g["mid"], float)
bb = np.asarray(g["bidK"][1], float); ba = np.asarray(g["askK"][1], float)
gbuy = np.asarray(g["buy"], float); gsell = np.asarray(g["sell"], float)
hs = median_spread_bps(BOOK, raw=raw) / 2.0
t0 = float(raw["ts"][0])
N = len(mid)
print(f"  grid cells: {N}  (0.1s each, {N*0.1/3600:.1f}h)  half_spread={hs:.3f}bps", flush=True)

# ---- LIVE path: get the btc_kraken legs (onset/close) ----
print("running live executor run_kraken_cell...", flush=True)
res, desc = run_kraken_cell(cfg, mid, gbuy, gsell, bb, ba, hs)
legs = res.legs
print(f"  {len(legs)} legs", flush=True)

# ---- per-cell (0.1s) imbalance = (buy-sell)/(buy+sell), rolling window ----
CELLS_PER_SEC = 10
def rolling_imb(buy, sell, w_sec):
    w = int(w_sec * CELLS_PER_SEC)
    cb = np.concatenate([[0.], np.cumsum(buy)]); cs = np.concatenate([[0.], np.cumsum(sell)])
    ix = np.arange(len(buy)); lo = np.maximum(ix + 1 - w, 0)
    B = cb[ix + 1] - cb[lo]; S = cs[ix + 1] - cs[lo]; tot = B + S
    out = np.zeros(len(buy)); nz = tot > 0
    out[nz] = (B[nz] - S[nz]) / tot[nz]
    vol = (B + S) / (ix + 1 - lo)   # mean vol per cell in window
    return out, vol

SMOOTH_SEC = 20                     # 20s rolling smoothing — Kraken BTC trades are SPARSE, so a shorter
                                    # window makes per-leg |imb| a saturated 0/1 square wave; 20s recovers a
                                    # readable per-leg arc without over-blurring the turn.
imb_signed, vol_w = rolling_imb(gbuy, gsell, SMOOTH_SEC)
imb_abs = np.abs(imb_signed)

# ---- FIXED real-time window around onset: -PRE_SEC .. +POST_SEC (captures rise + peak + collapse).
#      Real-time (not duration-normalized) so peak TIMING is meaningful and matching is non-degenerate. ----
PRE_SEC, POST_SEC = 45, 25
PRE, POST = PRE_SEC * CELLS_PER_SEC, POST_SEC * CELLS_PER_SEC
WLEN = PRE + POST + 1
tsec_axis = (np.arange(WLEN) - PRE) * 0.1   # shared x-axis, t=0 at onset

def leg_traj(l):
    o = int(l.open_idx); c = int(l.close_idx)
    lo = o - PRE; hi = o + POST
    if lo < 0 or hi >= N or c <= o:
        return None
    return dict(open_idx=o, close_idx=c, close_sec=(c - o) * 0.1,
                imb_abs=imb_abs[lo:hi + 1].copy(),
                imb_signed=imb_signed[lo:hi + 1].copy(),
                vol=vol_w[lo:hi + 1].copy(),
                side=int(l.side), net=float(l.net_bps))

trajs = [t for t in (leg_traj(l) for l in legs) if t is not None]
print(f"  {len(trajs)} legs with a full -{PRE_SEC}s..+{POST_SEC}s onset window", flush=True)

# ---- event-study MEAN arc across ALL legs (robust, no cherry-pick) ----
allA = np.array([t["imb_abs"] for t in trajs])
allS = np.array([t["imb_signed"] * t["side"] for t in trajs])
allV = np.array([t["vol"] for t in trajs])
mean_abs = allA.mean(0); mean_sig = allS.mean(0); mean_vol = allV.mean(0)

# ---- PRIMARY arc object = with-trade FLOW = signed_imb x side (rises during onset force, collapses
#      through zero during exhaustion). Cleaner per-leg than |imb| under Kraken trade sparsity.
#      Shape vectors for matching: fixed-length, min-max normalized to [0,1] (level-invariant). ----
def flow_of(t):
    return t["imb_signed"] * t["side"]
def arc_shape(t):
    s = flow_of(t).astype(float)
    s = s - s.min(); rng = s.max()
    if rng < 1e-9:
        return None
    return s / rng
shapes, sidx = [], []
for i, t in enumerate(trajs):
    s = arc_shape(t)
    if s is not None:
        shapes.append(s); sidx.append(i)
shapes = np.array(shapes)
print(f"  {len(shapes)} usable FLOW-arc shapes (fixed {WLEN}-cell window)", flush=True)

# pairwise correlation matrix
def corr_mat(S):
    Sc = S - S.mean(1, keepdims=True)
    Sn = Sc / (np.linalg.norm(Sc, axis=1, keepdims=True) + 1e-12)
    return Sn @ Sn.T

C = corr_mat(shapes)
M = len(shapes)
K_PICK = 5

# genuine-ARC filter: interior peak (real onset rise + real exhaustion collapse), not a pinned flat.
# rise = (peak - window_start)/peak ; collapse = (peak - window_end)/peak ; peak in interior band.
LOB, HIB = PRE - 200, PRE + 200      # peak must land within -20s..+20s of onset
arc_ok = np.zeros(M, bool)
for j in range(M):
    s = shapes[j]; pk = int(np.argmax(s))
    rise = s[pk] - s[0]; coll = s[pk] - s[-1]
    if LOB <= pk <= HIB and rise >= 0.30 and coll >= 0.30:
        arc_ok[j] = True
cand = np.where(arc_ok)[0]
print(f"  {len(cand)} legs pass the genuine-arc filter (interior peak, rise>=.3 & collapse>=.3)", flush=True)

# tightest mutual cluster of ~5 AMONG genuine arcs
best = None
for i in cand:
    order = [j for j in np.argsort(-C[i]) if arc_ok[j]][:K_PICK]
    if len(order) < K_PICK:
        continue
    grp = np.array(order)
    sub = C[np.ix_(grp, grp)]
    mmc = (sub.sum() - K_PICK) / (K_PICK * (K_PICK - 1))
    if best is None or mmc > best[0]:
        best = (mmc, grp)
matched_mmc, grp = best
matched = [sidx[j] for j in grp]
print(f"\nMATCHED handful (n={K_PICK}, genuine arcs) mean pairwise shape-corr = {matched_mmc:.3f}", flush=True)

# controls: random handful of ANY legs, and random handful among genuine arcs
rng_ = np.random.default_rng(0)
def rand_corr(pool):
    out = []
    for _ in range(3000):
        gg = rng_.choice(pool, K_PICK, replace=False)
        sub = C[np.ix_(gg, gg)]
        out.append((sub.sum() - K_PICK) / (K_PICK * (K_PICK - 1)))
    return float(np.mean(out)), float(np.percentile(out, 95))
ctrl_mean, ctrl_p95 = rand_corr(np.arange(M))
carc_mean, carc_p95 = rand_corr(cand) if len(cand) >= K_PICK else (float('nan'), float('nan'))
print(f"RANDOM handful (any legs)   mean pairwise shape-corr = {ctrl_mean:.3f}  (95pct {ctrl_p95:.3f})", flush=True)
print(f"RANDOM handful (genuine arcs) mean pairwise shape-corr = {carc_mean:.3f}  (95pct {carc_p95:.3f})", flush=True)

colors = plt.cm.viridis(np.linspace(0, 0.85, K_PICK))

def close_marker(ax_, t, series):
    ci = PRE + int(round(t["close_sec"] * CELLS_PER_SEC))
    if 0 <= ci < WLEN:
        ax_.plot(t["close_sec"], series[ci], 'v', color='k', ms=5, alpha=0.6)

# ================= PLOT =================
fig, ax = plt.subplots(4, 1, figsize=(11, 16))

# Panel A1: RAW with-trade FLOW overlay (aligned at onset) — numbers differ, shape rhymes
for k, ii in enumerate(matched):
    t = trajs[ii]; fl = t["imb_signed"] * t["side"]
    ax[0].plot(tsec_axis, fl, color=colors[k], lw=1.4,
               label=f"leg@{t['open_idx']} close+{t['close_sec']:.1f}s net{t['net']:+.0f}bp")
    close_marker(ax[0], t, fl)
ax[0].axvline(0, color='k', ls='--', lw=1, alpha=0.7); ax[0].axhline(0, color='gray', lw=0.6)
ax[0].set_title(f"btc_kraken — onset->exhaustion arc, {K_PICK} shape-matched legs "
                f"(RAW with-trade flow = signed imb x side, {SMOOTH_SEC}s-smoothed; v = close)\n"
                f"matched mean shape-corr {matched_mmc:.2f} vs random {ctrl_mean:.2f}  "
                f"(onset t=0; rise = onset force, fall-through-zero = exhaustion)")
ax[0].set_xlabel("seconds relative to onset (t=0)"); ax[0].set_ylabel("with-trade flow (raw)")
ax[0].legend(fontsize=7, loc='lower left'); ax[0].grid(alpha=0.25)

# Panel A2: min-max normalized overlay (shape only — numbers gone, shape rhymes?)
for k, j in enumerate(grp):
    ax[1].plot(tsec_axis, shapes[j], color=colors[k], lw=1.4)
ax[1].axvline(0, color='k', ls='--', lw=1, alpha=0.7)
ax[1].set_title("SAME legs — min-max normalized [0,1] flow arc (shape only: numbers differ, shape rhymes?)")
ax[1].set_xlabel("seconds relative to onset (t=0)")
ax[1].set_ylabel("flow normalized"); ax[1].grid(alpha=0.25)

# Panel B: volume (buy+sell) for the same legs, aligned at onset
for k, ii in enumerate(matched):
    t = trajs[ii]
    ax[2].plot(tsec_axis, t["vol"], color=colors[k], lw=1.3)
    close_marker(ax[2], t, t["vol"])
ax[2].axvline(0, color='k', ls='--', lw=1, alpha=0.7)
ax[2].set_title("volume driver — mean (buy+sell) per cell, same legs, aligned at onset")
ax[2].set_xlabel("seconds relative to onset (t=0)"); ax[2].set_ylabel("volume/cell")
ax[2].grid(alpha=0.25)

# Panel C: EVENT-STUDY MEAN across ALL legs (the robust arc, no cherry-pick)
axm = ax[3]; axm2 = axm.twinx()
l1, = axm.plot(tsec_axis, mean_abs, color='C3', lw=2.0, label="mean |imbalance| (all legs)")
l2, = axm.plot(tsec_axis, mean_sig, color='C0', lw=2.0, label="mean signed imb x side")
l3, = axm2.plot(tsec_axis, mean_vol, color='C7', lw=1.4, ls='--', label="mean volume/cell (R axis)")
axm.axvline(0, color='k', ls='--', lw=1, alpha=0.7); axm.axhline(0, color='gray', lw=0.6)
axm.set_title(f"EVENT-STUDY MEAN over ALL {len(trajs)} btc_kraken legs — the average onset->exhaustion arc")
axm.set_xlabel("seconds relative to onset (t=0)"); axm.set_ylabel("imbalance")
axm2.set_ylabel("volume/cell")
axm.legend(handles=[l1, l2, l3], fontsize=8, loc='upper left'); axm.grid(alpha=0.25)

plt.tight_layout()
p1 = os.path.join(OUT, "btc_kraken_arc_matched.png")
plt.savefig(p1, dpi=110); plt.close()
print(f"\nsaved {p1}", flush=True)

# ---- signed-imbalance panel (direction) as a separate figure ----
fig2, ax2 = plt.subplots(figsize=(11, 5))
for k, ii in enumerate(matched):
    t = trajs[ii]
    ax2.plot(tsec_axis, t["imb_signed"] * t["side"], color=colors[k], lw=1.3,
             label=f"leg@{t['open_idx']}")
ax2.axhline(0, color='gray', lw=0.8); ax2.axvline(0, color='k', ls='--', lw=1, alpha=0.7)
ax2.set_title("btc_kraken — SIGNED imbalance x leg-side (with-trade flow), same matched legs")
ax2.set_xlabel("seconds relative to onset (t=0)"); ax2.set_ylabel("signed imb x side")
ax2.legend(fontsize=7); ax2.grid(alpha=0.25)
plt.tight_layout()
p2 = os.path.join(OUT, "btc_kraken_arc_signed.png")
plt.savefig(p2, dpi=110); plt.close()
print(f"saved {p2}", flush=True)

# ---- peak-timing / exhaustion stats on the matched handful (real time rel. onset) ----
print("\n--- matched-handful arc characterization (peak & collapse in real seconds) ---", flush=True)
peaks, colls = [], []
for ii in matched:
    t = trajs[ii]
    seg = t["imb_signed"] * t["side"]                # with-trade flow arc
    pk = int(np.argmax(seg)); peak_sec = (pk - PRE) * 0.1
    rng = seg[pk] - seg.min() + 1e-9
    coll = (seg[pk] - seg[-1]) / rng                 # fractional collapse peak->end-of-window
    peaks.append(peak_sec); colls.append(coll)
    print(f"  leg@{t['open_idx']:>7}  dur {t['close_sec']:5.1f}s  peak@{peak_sec:+5.1f}s rel onset  "
          f"collapse-to-window-end {coll*100:4.0f}%", flush=True)
print(f"\n  mean peak time: {np.mean(peaks):+.1f}s rel onset  (std {np.std(peaks):.1f}s)", flush=True)
print(f"  mean collapse: {np.mean(colls)*100:.0f}%  (std {np.std(colls)*100:.0f}%)", flush=True)
# event-study mean peak (on the informative signed-FLOW mean)
mpk = int(np.argmax(mean_sig))
print(f"  event-study MEAN with-trade FLOW peaks at {(mpk-PRE)*0.1:+.1f}s rel onset  "
      f"(value {mean_sig[mpk]:+.3f}; rises {mean_sig[mpk]-mean_sig[0]:+.3f} over the pre-onset limb, "
      f"then exhausts {mean_sig[-1]-mean_sig[mpk]:+.3f} to window end)", flush=True)

print("\nRESULT")
print(f"  legs total={len(legs)} usable-arcs={M} matched-n={K_PICK}")
print(f"  matched mean pairwise shape-corr = {matched_mmc:.3f}")
print(f"  random  mean pairwise shape-corr = {ctrl_mean:.3f}  (95pct {ctrl_p95:.3f})")
print(f"  PNGs: {p1}  {p2}")
