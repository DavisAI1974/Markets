"""_turn_quadratic.py — the turn as a QUADRATIC: direction + rate + curvature (Greg's read).

The directional lean (trailing-W net flow toward winside) descends into the turn, hits a vertex, ascends out
- a parabola. We fit lean(t) ~ a + b*t + c*t^2 near the turn: vertex = -b/2c (the turn), c = curvature (how
sharp the turn is). Then test: does turn SHARPNESS (curvature) track trade quality (net_bps)? Renders the
average lean + its parabola. Covered BTC/ETH bybit winners."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from odcore.io import load_bins

LB = 1800; H = 30; W = 60; CAP = 500


def main():
    offs = np.arange(-H, H + 1).astype(float)
    leans, nets = [], []
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
                leans.append(lean); nets.append(float(r.get("net_bps") or 0.0)); cnt += 1
    L = np.array(leans); net = np.array(nets); n = len(L)

    # per-winner quadratic fit: lean ~ a + b t + c t^2
    abc = np.array([np.polyfit(offs, L[j], 2) for j in range(n)])   # [c, b, a]
    c = abc[:, 0]; b = abc[:, 1]
    vertex = -b / (2 * c + 1e-12)
    curv = c                                  # >0 = U (valley of lean = the turn), sharper = bigger
    print(f"n={n}")
    print(f"avg vertex (turn) location = {np.median(vertex):+.1f}s  (should sit near 0)")
    print(f"curvature c: median={np.median(curv):.2e}  (>0 = parabola opening up, the turn is its bottom)")
    # does SHARPNESS predict trade quality?
    valid = (curv > 0) & (np.abs(vertex) <= H)
    cc = np.corrcoef(curv[valid], net[valid])[0, 1]
    print(f"\ncorr(curvature, net_bps) = {cc:+.3f}  (does a sharper turn = better trade?)")
    q = np.quantile(curv[valid], [0, .25, .5, .75, 1.0])
    print("net_bps by curvature quartile (sharpness):")
    for lo, hi, lab in zip(q[:-1], q[1:], ["Q1 gentle", "Q2", "Q3", "Q4 sharp"]):
        m = valid & (curv >= lo) & (curv <= hi)
        print(f"  {lab:9s} curv[{lo:.1e},{hi:.1e}]  net_bps={net[m].mean():7.1f}  (n={m.sum()})")

    # render: average lean + its parabola
    avg = L.mean(0); fit = np.polyfit(offs, avg, 2); par = np.polyval(fit, offs)
    vx = -fit[1] / (2 * fit[0])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(offs, avg, color="darkorange", lw=2, label="directional lean (trailing 60s)")
    ax.plot(offs, par, color="navy", ls="--", lw=1.5, label=f"parabola fit (curv={fit[0]:.2e})")
    ax.axvline(0, color="royalblue", ls=":", lw=1); ax.axvline(vx, color="crimson", lw=1, label=f"vertex={vx:+.1f}s")
    ax.axhline(0, color="gray", lw=.6)
    ax.set_xlabel("seconds from the turn"); ax.set_ylabel("net flow lean -> winside")
    ax.set_title(f"The turn is a QUADRATIC — lean descends, bottoms at the vertex, ascends ({n} winners)")
    ax.legend(); ax.grid(alpha=.25)
    fig.tight_layout(); fig.savefig("turn_quadratic.png", dpi=120)
    print("\nwrote turn_quadratic.png")


if __name__ == "__main__":
    main()
