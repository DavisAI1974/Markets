"""_s55_walkthrough_probes.py — the S55 walkthrough rounds, wired as rerunnable probes.

Every measurement from the S55 leg walkthrough with Greg (see S55_WALKTHROUGH_NOTES.md), one
subcommand per round, so nothing lives only in a chat transcript:

  python scripts/_s55_walkthrough_probes.py flip-test       R1: sides-reversed test on the S54 leg CSVs
  python scripts/_s55_walkthrough_probes.py anatomy         R1: annotated worst-leg render (xrp zz150)
  python scripts/_s55_walkthrough_probes.py window          R2: Greg's pencil vs detectors overlay (XRP 06-05)
  python scripts/_s55_walkthrough_probes.py descriptor      R4: divergence class at opening flip vs outcome (+ shuffle z)
  python scripts/_s55_walkthrough_probes.py lag             R5: theta-confirm vs fine-25 confirm lag on all zz150 turns
  python scripts/_s55_walkthrough_probes.py two-scale       R6/R7: v0 (free-running fine exits) + v1 trailing-X grid
  python scripts/_s55_walkthrough_probes.py exit-anatomy    R8: THE INVERTED GRAPH (flow aligned to leg EXIT turns)

Headline results (2026-07-03, 30d x 5 Bybit bins; full detail in S55_WALKTHROUGH_NOTES.md):
  flip-test:    NO side inversion; flipping loses more everywhere.
  descriptor:   zz150 reversal-class only positive class (+30.2/leg, 4/5 coins) but z=1.82 < bar;
                zz100 INVERTED -> dipole descriptions are SCALE-LOCAL.
  lag:          theta-confirm 151bp/54min from the true pivot; fine-25 confirm 26bp/1min = 125bp/side.
  two-scale:    v0 −80/hr, v1 −47..−13/hr (churn fees) -> fine execution must be ARMED, coarse cadence.
  exit-anatomy: flow CLIMAXES at the exact top (+0.40) and collapses through zero in ~60s at ~28bp
                giveback (vs 151bp theta-exit) -> exit-side saving ~123bp; the top IS the maker
                "can't refuse" moment.
Needs bins in /tmp/backfill/ (S55 kickoff re-pull commands) and, for `window`/`anatomy`, XRP bins.
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS          # noqa: E402
from _s52_accum_vs_oneshot import _price_zigzag, DIVW     # noqa: E402
from odcore.info_dipole import divergence                 # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "renders", "s55", "legs")
RT_BYBIT = 11.0
CAP = 5000.0


def _bins(sym):
    p = f"/tmp/backfill/{sym}_30d_bins.json"
    mid, buy, sell, cover, hrs = load_bins(p)
    with open(p) as f:
        t0 = min(float(k) for k in json.load(f).keys())
    return (np.asarray(mid, float), np.asarray(buy, float), np.asarray(sell, float), hrs, t0)


def _utc(t):
    return datetime.fromtimestamp(t, tz=timezone.utc)


# ---------------- R1: flip test on the S54 leg CSVs ----------------
def flip_test():
    for fname in ("_s54_legs_zigzag_bybit30d.csv", "_s54_legs_bigline_bybit30d.csv",
                  "_s54_legs_bigline_coinbase.csv"):
        path = os.path.join(ROOT, fname)
        if not os.path.exists(path):
            continue
        agg = {}
        with open(path) as f:
            for r in csv.DictReader(f):
                rt = 10.0 if "coinbase" in r["cell"] and not r["cell"].endswith("_bybit") else 11.0
                g = float(r["gross_bps"])
                st = agg.setdefault(r["engine"], [0, 0.0, 0, 0.0, 0])
                st[0] += 1; st[1] += g - rt; st[2] += (g - rt > 0)
                st[3] += -g - rt; st[4] += (-g - rt > 0)
        print(f"=== {fname} ===")
        print(f"{'engine':<12}{'legs':>6}{'net/leg':>9}{'win%':>7}{'FLIPPED net/leg':>17}{'win%':>7}")
        for e, (n, net, w, fn, fw) in sorted(agg.items()):
            print(f"{e:<12}{n:>6}{net / n:>9.1f}{100 * w / n:>6.1f}%{fn / n:>17.1f}{100 * fw / n:>6.1f}%")
        print()


# ---------------- R4: descriptor class vs outcome ----------------
def descriptor():
    for th in (150.0, 100.0):
        nets, cls = [], []
        for (coin, sym) in COINS:
            mid, b, s_, hrs, t0 = _bins(sym)
            fl = _price_zigzag(mid, th)
            for a, bb in zip(fl[:-1], fl[1:]):
                ci, pi, sd = int(a[0]), int(a[1]), int(a[2])
                cj = int(bb[0])
                lo = max(0, pi - DIVW)
                if pi - lo < 12:
                    continue
                d = divergence(b[lo:pi + 1], s_[lo:pi + 1], float(mid[pi] - mid[lo]))
                if d is None:
                    continue
                nets.append(sd * (mid[cj] - mid[ci]) / mid[ci] * 1e4 - RT_BYBIT)
                cls.append(d["expect"])
        nets = np.array(nets); cls = np.array(cls)
        print(f"=== zz{th:.0f} — legs by dipole class at the OPENING flip ===")
        for k in ("reversal", "flip_risk", "weakening", "continue"):
            m = cls == k
            if m.any():
                print(f"  {k:<11} n={m.sum():>4}  win {100 * (nets[m] > 0).mean():5.1f}%  "
                      f"net/leg {nets[m].mean():+7.1f}")
        rev = nets[cls == "reversal"]
        if len(rev) > 5:
            rng = np.random.default_rng(7)
            null = np.array([nets[rng.permutation(len(nets))[:len(rev)]].mean()
                             for _ in range(10000)])
            print(f"  shuffle null: reversal mean {rev.mean():+.1f} -> "
                  f"z={(rev.mean() - null.mean()) / null.std():.2f}, p={(null >= rev.mean()).mean():.4f}\n")


# ---------------- R5: lag measurement ----------------
def lag(r_fine=25.0, th=150.0):
    rows = []
    for (coin, sym) in COINS:
        mid, b, s_, hrs, t0 = _bins(sym)
        fl = _price_zigzag(mid, th)
        for a, bb in zip(fl[:-1], fl[1:]):
            ci, pi, sd = int(a[0]), int(a[1]), int(a[2])
            cj = int(bb[0])
            gross = sd * (mid[cj] - mid[ci]) / mid[ci] * 1e4
            fine_i, ext = None, mid[pi]
            for t in range(pi + 1, min(ci + 1, len(mid))):
                if sd > 0:
                    ext = min(ext, mid[t])
                    if (mid[t] - ext) / ext * 1e4 >= r_fine:
                        fine_i = t; break
                else:
                    ext = max(ext, mid[t])
                    if (ext - mid[t]) / ext * 1e4 >= r_fine:
                        fine_i = t; break
            if fine_i is None:
                fine_i = ci
            rows.append((gross - RT_BYBIT > 0,
                         abs(mid[ci] - mid[pi]) / mid[pi] * 1e4, ci - pi,
                         abs(mid[fine_i] - mid[pi]) / mid[pi] * 1e4, fine_i - pi))
    rows = np.array(rows, float)
    print(f"zz{th:.0f} turns n={len(rows)} ({int(rows[:, 0].sum())} real)")
    print(f"theta-confirm lag: median {np.median(rows[:, 1]):.0f}bp / {np.median(rows[:, 2]) / 60:.0f}min")
    print(f"fine-{r_fine:.0f} confirm lag: median {np.median(rows[:, 3]):.0f}bp / {np.median(rows[:, 4]) / 60:.0f}min")
    print(f"lag SAVED: median {np.median(rows[:, 1] - rows[:, 3]):.0f}bp/side")


# ---------------- R6/R7: two-scale v0 + v1 ----------------
def _run_two_scale_v0(mid, fine, coarse, reverse=False):
    cd = np.zeros(len(mid), dtype=np.int8)
    for (c, p, s) in coarse:
        cd[int(c):] = -s if reverse else s
    pos, entry, trades = 0, 0.0, []
    for (c, p, s) in fine:
        c, s = int(c), int(s)
        if pos != 0 and s != pos:
            trades.append(pos * (mid[c] - entry) / entry * 1e4 - RT_BYBIT); pos = 0
        if pos == 0 and s == cd[c] and cd[c] != 0:
            pos, entry = s, mid[c]
    return np.array(trades) if trades else np.zeros(0)


def _run_two_scale_v1(mid, fine, coarse, X, reverse=False):
    n = len(mid)
    cd = np.zeros(n, dtype=np.int8); cflip = np.zeros(n, bool)
    for (c, p, s) in coarse:
        c = int(c); cd[c:] = -s if reverse else s; cflip[c] = True
    fmap = {int(c): int(s) for (c, p, s) in fine}
    pos, entry, best, trades, x = 0, 0.0, 0.0, [], X / 1e4
    for t in range(n):
        if pos != 0:
            best = max(best, mid[t]) if pos > 0 else min(best, mid[t])
            adverse = (best - mid[t]) / best if pos > 0 else (mid[t] - best) / best
            if adverse >= x or (cflip[t] and cd[t] != pos):
                trades.append(pos * (mid[t] - entry) / entry * 1e4 - RT_BYBIT); pos = 0
        if pos == 0 and t in fmap and fmap[t] == cd[t] and cd[t] != 0:
            pos, entry, best = cd[t], mid[t], mid[t]
    return np.array(trades) if trades else np.zeros(0)


def two_scale():
    data = {}
    for (coin, sym) in COINS:
        mid, b, s_, hrs, t0 = _bins(sym)
        data[coin] = (mid, _price_zigzag(mid, 25.0), _price_zigzag(mid, 150.0), hrs)
    print("v0 (fine zz25 executes, exit on any fine flip against, coarse zz150 side):")
    tot = 0.0
    for coin, (mid, fine, coarse, hrs) in data.items():
        tr = _run_two_scale_v0(mid, fine, coarse)
        v = tr.sum() * CAP / 1e4 / hrs; tot += v
        print(f"  {coin:<6} {len(tr) / (hrs / 24):6.1f} tr/day  net/leg {tr.mean():6.1f}  ${v:7.2f}/hr")
    print(f"  TOTAL ${tot:.2f}/hr")
    print("v1 trailing-X grid ($/hr total across 5, forward | reversed):")
    for X in (40.0, 60.0, 80.0):
        t_f = sum(_run_two_scale_v1(m, f, c, X).sum() * CAP / 1e4 / h
                  for m, f, c, h in data.values())
        t_r = sum(_run_two_scale_v1(m, f, c, X, reverse=True).sum() * CAP / 1e4 / h
                  for m, f, c, h in data.values())
        print(f"  X={X:.0f}: {t_f:+8.2f} | reversed {t_r:+8.2f}")


# ---------------- R8: the inverted graph ----------------
def exit_anatomy(W=600, lean_w=60, dive_d=10, th=150.0):
    os.makedirs(OUT, exist_ok=True)
    price_stack, lean_stack = [], []
    for (coin, sym) in COINS:
        mid, b, s_, hrs, t0 = _bins(sym)
        cb, cs = np.cumsum(b), np.cumsum(s_)
        fl = _price_zigzag(mid, th)
        for a, bb in zip(fl[:-1], fl[1:]):
            side, pj = int(a[2]), int(bb[1])
            if pj - W - lean_w < 0 or pj + W + 1 > len(mid):
                continue
            t = np.arange(pj - W, pj + W + 1)
            bw, sw = cb[t] - cb[t - lean_w], cs[t] - cs[t - lean_w]
            tot = bw + sw
            lean = np.where(tot > 0, (bw - sw) / np.maximum(tot, 1e-9), 0.0)
            price_stack.append(side * (mid[t] - mid[pj]) / mid[pj] * 1e4)
            lean_stack.append(side * lean)
    P = np.mean(np.array(price_stack), axis=0)
    L = np.mean(np.array(lean_stack), axis=0)
    x = np.arange(-W, W + 1)
    dive = np.full_like(L, np.nan); dive[dive_d:] = L[dive_d:] - L[:-dive_d]
    prate = np.full_like(P, np.nan); prate[dive_d:] = (P[dive_d:] - P[:-dive_d]) / dive_d
    n = len(price_stack)
    for tt in (-300, -60, -30, 0, 30, 60, 300):
        i = tt + W
        print(f"  t={tt:+4d}s  lean {L[i]:+.3f}  price {P[i]:+.1f}bp")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    ax1.plot(x, L, color="#e8930c", lw=1.8, label="flow lean (signed WITH the ride)")
    ax1.set_ylabel("flow lean", color="#e8930c")
    ax1b = ax1.twinx(); ax1b.plot(x, P, color="black", lw=1.8, label="price (bps, ride coords)")
    ax1b.set_ylabel("price (bps)")
    ax1.axvline(0, ls="--", color="#4466cc", lw=1)
    ax1.set_title(f"THE INVERTED GRAPH — {n} zz{th:.0f} legs aligned to the EXIT turn (x=0)")
    ax1.legend(loc="upper left", fontsize=9); ax1b.legend(loc="upper right", fontsize=9)
    ax1.grid(alpha=0.25, lw=0.4)
    ax2.plot(x, dive, color="#8a1a9b", lw=1.6, label=f"dipole DIVE (Δlean/{dive_d}s)")
    ax2.axhline(0, color="#888", lw=0.7); ax2.set_ylabel("dipole rate", color="#8a1a9b")
    ax2b = ax2.twinx(); ax2b.plot(x, prate, color="#2a7f62", lw=1.4, label="price rate")
    ax2.axvline(0, ls="--", color="#4466cc", lw=1)
    ax2.set_xlabel("seconds from the EXIT turn")
    ax2.legend(loc="upper left", fontsize=9); ax2b.legend(loc="upper right", fontsize=9)
    ax2.grid(alpha=0.25, lw=0.4)
    fig.tight_layout()
    f = os.path.join(OUT, "inverted_exit_anatomy.png")
    fig.savefig(f, dpi=110); plt.close(fig)
    print(f"-> {f}")


# ---------------- R1b/R2: annotated anatomy + Greg-window overlay (XRP 06-05) ----------------
def anatomy():
    os.makedirs(OUT, exist_ok=True)
    mid, b, s_, hrs, t0 = _bins("XRPUSDT")
    fl = _price_zigzag(mid, 150.0)
    tgt = datetime(2026, 6, 5, 20, 5, 22, tzinfo=timezone.utc).timestamp()
    a, bb = min(zip(fl[:-1], fl[1:]), key=lambda ab: abs(t0 + ab[0][0] - tgt))
    ci, pi, sd = int(a[0]), int(a[1]), int(a[2]); cj = int(bb[0])
    lo, hi = max(0, pi - 2400), min(len(mid) - 1, cj + 2400)
    idx = np.arange(lo, hi + 1)
    fig, ax = plt.subplots(figsize=(15, 7))
    ax.plot(idx, mid[lo:hi + 1], lw=0.7, color="#334")
    ax.plot(pi, mid[pi], marker="o", ms=9, mfc="none", mec="#b3121b", mew=2)
    ax.plot([pi, ci], [mid[pi], mid[ci]], color="#b3121b", lw=2, ls=":")
    ax.plot(ci, mid[ci], marker="^", ms=12, color="#b3121b")
    ax.plot(cj, mid[cj], marker="v", ms=12, color="#b3121b")
    ax.axvspan(ci, cj, color="#b3121b", alpha=0.08)
    ax.set_title("ANATOMY OF A WORST LEG — the θ-trigger move IS the fakeout ripple, so the "
                 "confirm lands at the extreme on the wrong side by construction")
    ax.grid(alpha=0.25, lw=0.4)
    f = os.path.join(OUT, "anatomy_worst_leg.png")
    fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig)
    print(f"-> {f}")


def window():
    os.makedirs(OUT, exist_ok=True)
    mid, b, s_, hrs, t0 = _bins("XRPUSDT")
    w0 = int(datetime(2026, 6, 5, 19, 8, tzinfo=timezone.utc).timestamp() - t0)
    w1 = int(datetime(2026, 6, 5, 20, 49, tzinfo=timezone.utc).timestamp() - t0)
    seg = mid[w0:w1 + 1]
    piv, lo_i, hi_i, mode = [], 0, 0, 0
    thf = 60.0 / 1e4
    for t in range(1, len(seg)):
        if seg[t] < seg[lo_i]: lo_i = t
        if seg[t] > seg[hi_i]: hi_i = t
        if mode >= 0 and seg[t] <= seg[hi_i] * (1 - thf):
            piv.append((hi_i, -1)); mode = -1; lo_i = t
        elif mode <= 0 and seg[t] >= seg[lo_i] * (1 + thf):
            piv.append((lo_i, +1)); mode = +1; hi_i = t
    fig, ax = plt.subplots(figsize=(16, 7.5))
    ax.plot(np.arange(w0, w1 + 1), seg, lw=0.7, color="#334", zorder=1)
    for aa, bb in zip(piv[:-1], piv[1:]):
        i, si = aa; j, _ = bb
        c = "#0a7a2f" if si > 0 else "#b3121b"
        ax.annotate("", xy=(w0 + j, seg[j]), xytext=(w0 + i, seg[i]),
                    arrowprops=dict(arrowstyle="->", color=c, lw=2.2, alpha=0.85))
        ax.plot(w0 + i, seg[i], marker="o", ms=9, mfc="none", mec=c, mew=2, zorder=4)
    for th, mk, cl in ((150.0, "X", "#b3121b"), (100.0, "s", "#d68400"), (60.0, "^", "#1f5fc4")):
        for (c_, p_, sflip) in _price_zigzag(mid, th):
            c_ = int(c_)
            if w0 <= c_ <= w1:
                ax.plot(c_, mid[c_], marker=mk, ms=11 if th == 150 else 8,
                        mec=cl, mfc="none", mew=2.2, zorder=5)
    ax.set_title("Greg's pencil (oracle θ60 arrows) vs zz60/zz100/zz150 confirms — XRP 06-05")
    ax.grid(alpha=0.25, lw=0.4)
    f = os.path.join(OUT, "greg_window_overlay.png")
    fig.tight_layout(); fig.savefig(f, dpi=110); plt.close(fig)
    print(f"-> {f}")


CMDS = {"flip-test": flip_test, "descriptor": descriptor, "lag": lag, "two-scale": two_scale,
        "exit-anatomy": exit_anatomy, "anatomy": anatomy, "window": window}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in CMDS:
        print(__doc__)
    else:
        CMDS[cmd]()
