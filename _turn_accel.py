"""_turn_accel.py — the turn's ACCELERATION/DECELERATION, not a constant-curvature parabola (Greg).

A single parabola assumes constant curvature. The real directional lean accelerates into the turn (climax)
and decelerates as it bottoms. Compute the empirical velocity (d lean/dt) and acceleration (d2 lean/dt2)
across the turn, and find whether DECELERATION LEADS the vertex (an earlier turn warning than rate=0).
Renders lean / velocity / acceleration aligned to the turn. Covered BTC/ETH bybit winners."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from odcore.io import load_bins

LB = 1800; H = 60; W = 60; CAP = 500


def smooth(a, k=5):
    ker = np.ones(k) / k
    return np.convolve(a, ker, mode="same")


def main():
    offs = np.arange(-H, H + 1).astype(float)
    leans = []
    for cv in ("btc_bybit_perp", "eth_bybit_perp"):
        if not Path(f"realbins/{cv}_bins.json").exists():
            continue
        bs = load_bins(f"realbins/{cv}_bins.json"); ts, mid, bvol, svol = bs.ts, bs.mid, bs.buy, bs.sell
        cb = np.concatenate([[0.0], np.cumsum(bvol)]); cs = np.concatenate([[0.0], np.cumsum(svol)])
        t0, t1 = ts[0], ts[-1]
        for side in ("buy", "sell"):
            fp = Path(f"_alt_labels/{cv}_{side}_winner_onsets.json")
            if not fp.exists():
                continue
            sgn = 1.0 if side == "buy" else -1.0; cnt = 0
            for r in json.load(open(fp)):
                if cnt >= CAP:
                    break
                dts = float(r["decision_ts_utc"])
                if not (t0 + LB <= dts <= t1):
                    continue
                i = int(np.searchsorted(ts, dts, "right")) - 1
                w = mid[i - LB:i + 1]
                if (w <= 0).any():
                    continue
                E = i - LB + (int(np.argmin(w)) if side == "buy" else int(np.argmax(w)))
                if (i - E) < H or (E - H - W) < 0 or (E + H + 1) > len(ts):
                    continue
                lean = np.empty(len(offs))
                for k, o in enumerate(offs):
                    end = int(E + o)
                    B = cb[end + 1] - cb[end - W + 1]; Sv = cs[end + 1] - cs[end - W + 1]; tot = B + Sv
                    lean[k] = sgn * (B - Sv) / tot if tot > 0 else 0.0
                leans.append(lean); cnt += 1
    L = np.array(leans); n = len(L)
    avg = smooth(L.mean(0), 5)
    vel = np.gradient(avg)            # rate
    acc = np.gradient(vel)            # acceleration (rate of the rate)

    inner = (offs >= -40) & (offs <= 40)
    vmin = offs[inner][np.argmin(vel[inner])]    # steepest descent (accel crosses 0, max climax speed)
    vtx = offs[inner][np.argmin(np.abs(vel[inner]))]  # vertex (rate ~ 0 = the turn)
    amin = offs[inner][np.argmin(acc[inner])]    # peak acceleration of the descent
    print(f"n={n}")
    print(f"peak descent ACCELERATION at {amin:+.0f}s   (descent speeding up)")
    print(f"steepest descent (vel min) at {vmin:+.0f}s   (max climax speed; deceleration begins after)")
    print(f"vertex / rate=0 (the turn)  at {vtx:+.0f}s")
    print(f"\n=> deceleration LEADS the vertex by ~{vtx - vmin:.0f}s  (early-turn warning before rate=0)")

    fig, ax = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
    fig.suptitle(f"The turn's dynamics — lean / velocity / acceleration ({n} winners, x=turn)", fontsize=12)
    ax[0].plot(offs, avg, color="darkorange"); ax[0].set_ylabel("lean -> winside")
    ax[0].set_title("directional lean", fontsize=9)
    ax[1].plot(offs, vel, color="purple"); ax[1].axhline(0, color="gray", lw=.6)
    ax[1].axvline(vmin, color="crimson", ls=":", lw=1, label=f"steepest descent {vmin:+.0f}s")
    ax[1].set_ylabel("velocity (rate)"); ax[1].set_title("rate — zero at the vertex (the turn)", fontsize=9); ax[1].legend(fontsize=8)
    ax[2].plot(offs, acc, color="teal"); ax[2].axhline(0, color="gray", lw=.6)
    ax[2].set_ylabel("acceleration"); ax[2].set_title("acceleration — NOT constant: descent speeds up then eases (the parabola can't show this)", fontsize=8)
    for a in ax:
        a.axvline(0, color="royalblue", ls="--", lw=1); a.grid(alpha=.25)
    ax[2].set_xlabel("seconds from the turn")
    fig.tight_layout(rect=[0, 0, 1, 0.98]); fig.savefig("turn_accel.png", dpi=120)
    print("\nwrote turn_accel.png")


if __name__ == "__main__":
    main()
