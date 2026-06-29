"""_dipole_price_overlay.py — overlay the dipole (flow lean) and price; correlate dipole DIVE vs price
rate-of-change, with lead/lag (Greg). Aligned to the turn, covered BTC/ETH bybit winners."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from odcore.io import load_bins

LB = 1800; H = 60; W = 60; CAP = 500


def main():
    offs = np.arange(-H, H + 1).astype(float)
    LE, PR = [], []
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
                lean = np.empty(len(offs)); pr = np.empty(len(offs))
                for k, o in enumerate(offs):
                    end = int(E + o)
                    B = cb[end + 1] - cb[end - W + 1]; Sv = cs[end + 1] - cs[end - W + 1]; tot = B + Sv
                    lean[k] = sgn * (B - Sv) / tot if tot > 0 else 0.0
                    pr[k] = sgn * np.log(mid[end] / mid[E]) * 1e4
                LE.append(lean); PR.append(pr); cnt += 1
    LE = np.array(LE); PR = np.array(PR); n = len(LE)
    lean = LE.mean(0); price = PR.mean(0)
    lrate = np.gradient(lean); prate = np.gradient(price)   # dipole dive vs price rate-of-change

    # pooled rate-to-rate correlation + lead/lag (does the dipole dive LEAD price velocity?)
    Lr = np.gradient(LE, axis=1); Pr = np.gradient(PR, axis=1)
    c0 = np.corrcoef(Lr.ravel(), Pr.ravel())[0, 1]
    print(f"n={n}")
    print(f"corr(dipole rate, price rate) contemporaneous = {c0:+.3f}")
    print("lead/lag corr(dipole_rate[t], price_rate[t+k])  (k>0 => dipole LEADS):")
    best = (0, -9);
    for k in range(-8, 9, 2):
        if k >= 0:
            a = Lr[:, :Lr.shape[1] - k].ravel(); b = Pr[:, k:].ravel()
        else:
            a = Lr[:, -k:].ravel(); b = Pr[:, :Pr.shape[1] + k].ravel()
        cc = np.corrcoef(a, b)[0, 1]
        if cc > best[1]:
            best = (k, cc)
        print(f"  k={k:+d}s : {cc:+.3f}")
    print(f"=> peak at k={best[0]:+d}s ({'dipole leads' if best[0] > 0 else 'price leads' if best[0] < 0 else 'coincident'}), corr {best[1]:+.3f}")

    fig, ax = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
    fig.suptitle(f"Dipole (flow) over Price — {n} winners, aligned to the turn (x=0)", fontsize=12)
    a0 = ax[0]; a0b = a0.twinx()
    l1, = a0.plot(offs, lean, color="darkorange", label="dipole / flow lean")
    l2, = a0b.plot(offs, price, color="black", label="price -> winside (bps)")
    a0.set_ylabel("flow lean", color="darkorange"); a0b.set_ylabel("price (bps)")
    a0.set_title("the two pictures overlaid", fontsize=9); a0.legend(handles=[l1, l2], fontsize=8)
    a1 = ax[1]; a1b = a1.twinx()
    r1, = a1.plot(offs, lrate, color="purple", label="dipole DIVE (d lean/dt)")
    r2, = a1b.plot(offs, prate, color="seagreen", label="price rate (d price/dt)")
    a1.axhline(0, color="gray", lw=.6); a1.set_ylabel("dipole rate", color="purple"); a1b.set_ylabel("price rate")
    a1.set_title(f"rates: dipole dive vs price velocity (corr {c0:+.2f})", fontsize=9)
    a1.legend(handles=[r1, r2], fontsize=8)
    for a in (a0, a1):
        a.axvline(0, color="royalblue", ls="--", lw=1); a.grid(alpha=.2)
    a1.set_xlabel("seconds from the turn")
    fig.tight_layout(rect=[0, 0, 1, 0.98]); fig.savefig("dipole_price_overlay.png", dpi=120)
    print("\nwrote dipole_price_overlay.png")


if __name__ == "__main__":
    main()
