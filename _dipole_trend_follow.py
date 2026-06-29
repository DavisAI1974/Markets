"""_dipole_trend_follow.py — S41: the OTHER big discovery — the dipole as a TREND FOLLOWER.

Greg: trading is nothing but one trend, then a flip, then another trend. The dipole is really
good at trend-following. We over-focused on catching every flip (the flip detector fired
24k-100k times = fee suicide). The dipole's real job is to RIDE the trend and only FLIP on a
strong opposite lean.

STRATEGY (causal, hysteresis = the 'ride through the wiggles' band):
  lean(t) = trailing-W taker (buy-sell)/(buy+sell)            (the dipole; +buy / -sell)
  go/stay LONG  when lean >= +thr ;  go/stay SHORT when lean <= -thr ;  else HOLD prior position.
  -> you only flip when the lean DECISIVELY crosses to the other side. Wider thr = ride more,
     trade less (more trend-following). trades = sign changes; each pays the round-trip fee.

FALSIFICATION (per cell, net-of-cost): does trend-following the dipole BEAT buy-hold AND beat
the over-firing flip detector, net of fees? Sweep (W, thr): wider band should trade less and,
if the dipole really follows trend, keep more of the move.
"""
from __future__ import annotations
import argparse, json
import numpy as np
from odcore.io import load_bins
from odcore.flip_detector import lean_series


def trend_follow(lean, mid, thr, fee_bps):
    """Hysteresis trend-follower. Returns dict of net-of-cost stats (bps)."""
    n = len(lean); pos = np.zeros(n, dtype=np.int8); cur = 0
    for t in range(n):
        if lean[t] >= thr: cur = 1
        elif lean[t] <= -thr: cur = -1
        pos[t] = cur                                  # else carry prior (the ride)
    lr = np.zeros(n)
    good = mid > 0
    lr[1:] = np.where(good[1:] & good[:-1], np.log(np.where(good[1:], mid[1:], 1)) -
                      np.log(np.where(good[:-1], mid[:-1], 1)), 0.0)
    strat = pos[:-1] * lr[1:] * 1e4                    # bps per second, position held from t to t+1
    flips = int(np.sum(np.abs(np.diff(pos)) > 0))
    gross = float(strat.sum())
    net = gross - flips * fee_bps
    in_mkt = float((pos != 0).mean())
    bh = float((np.log(mid[good][-1]) - np.log(mid[good][0])) * 1e4) if good.sum() > 1 else 0.0
    return dict(thr=thr, flips=flips, gross_bps=round(gross, 1), net_bps=round(net, 1),
                in_mkt=round(in_mkt, 2), buyhold_bps=round(bh, 1),
                per_flip=round(net / max(1, flips), 2))


def run(cells, W, thrs, fee_bps, render):
    out = {}
    for cell in cells:
        try:
            s = load_bins(f"realbins/{cell}_bins.json")
        except Exception as e:
            print(f"{cell}: load failed {e}"); continue
        lean = lean_series(s.buy, s.sell, W)
        print(f"\n== {cell}  (n={len(s):,}s, {(s.ts[-1]-s.ts[0])/3600:.0f}h, W={W}s) ==")
        print(f"   buy-hold = {((np.log(s.mid[s.mid>0][-1])-np.log(s.mid[s.mid>0][0]))*1e4):+.0f} bps")
        print(f"   {'thr':>5} {'flips':>7} {'gross':>9} {'net':>9} {'per_flip':>9} {'in_mkt':>7}")
        res = []
        for thr in thrs:
            r = trend_follow(lean, s.mid, thr, fee_bps)
            res.append(r)
            print(f"   {thr:>5.2f} {r['flips']:>7d} {r['gross_bps']:>9.0f} {r['net_bps']:>9.0f} "
                  f"{r['per_flip']:>9.2f} {r['in_mkt']:>7.2f}")
        out[cell] = dict(W=W, buyhold=res[0]["buyhold_bps"], sweep=res)
    json.dump(out, open("_dipole_trend_follow_results.json", "w"), indent=2)
    print("\n[saved] _dipole_trend_follow_results.json")
    if render and cells:
        _render(cells[0], W, thrs, fee_bps)


def _render(cell, W, thrs, fee_bps):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    s = load_bins(f"realbins/{cell}_bins.json")
    lean = lean_series(s.buy, s.sell, W)
    thr = thrs[len(thrs) // 2]
    n = len(lean); pos = np.zeros(n, np.int8); cur = 0
    for t in range(n):
        if lean[t] >= thr: cur = 1
        elif lean[t] <= -thr: cur = -1
        pos[t] = cur
    a = 0; b = min(n, 6 * 3600)                        # first 6h zoom
    x = np.arange(a, b) / 3600
    fig, ax = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.5]))
    ax[0].plot(x, s.mid[a:b], color="#333", lw=0.8)
    ax[0].fill_between(x, s.mid[a:b].min(), s.mid[a:b].max(), where=pos[a:b] > 0,
                       color="#237804", alpha=0.12, label="LONG (riding up-trend)")
    ax[0].fill_between(x, s.mid[a:b].min(), s.mid[a:b].max(), where=pos[a:b] < 0,
                       color="#cf1322", alpha=0.12, label="SHORT (riding down-trend)")
    ax[0].set_ylabel("price"); ax[0].legend(loc="upper left", fontsize=9)
    ax[0].set_title(f"{cell}: dipole TREND-FOLLOWING (W={W}s, thr={thr}) — ride the trend, flip on strong opposite lean")
    ax[1].plot(x, lean[a:b], color="#722ed1", lw=0.7); ax[1].axhline(0, color="k", lw=0.5)
    ax[1].axhline(thr, color="g", ls="--", lw=0.6); ax[1].axhline(-thr, color="r", ls="--", lw=0.6)
    ax[1].set_ylabel("dipole lean"); ax[1].set_xlabel("hours")
    fig.tight_layout(); fig.savefig(f"_dipole_trend_follow_{cell}.png", dpi=110); plt.close(fig)
    print(f"[render] _dipole_trend_follow_{cell}.png")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="btc_bybit_perp,eth_bybit_perp")
    ap.add_argument("--W", type=int, default=300, help="dipole lean window (s) — longer = trend")
    ap.add_argument("--thrs", default="0.05,0.10,0.15,0.20,0.30,0.40")
    ap.add_argument("--fee_bps", type=float, default=10.0)
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    run(a.cells.split(","), a.W, [float(x) for x in a.thrs.split(",")], a.fee_bps, not a.no_render)
