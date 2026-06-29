"""_turn_symmetry.py — the turn's near-symmetry, split into EVEN (mirror) + ODD (the edge) (Greg).

Greg saw it: the turn looks almost symmetric. Perfect symmetry around the vertex would be time-reversible =
no edge. Decompose each turn signal f(t) into even part (f(t)+f(-t))/2 [the symmetric bowl] and odd part
(f(t)-f(-t))/2 [the asymmetry]. The ODD component IS where prediction lives. Quantify the even/odd energy
split and render. Covered BTC/ETH bybit winners."""
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
    leans, prices, vols = [], [], []
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
                lean = np.empty(len(offs)); pr = np.empty(len(offs)); vv = np.empty(len(offs))
                for k, o in enumerate(offs):
                    end = int(E + o)
                    B = cb[end + 1] - cb[end - W + 1]; Sv = cs[end + 1] - cs[end - W + 1]; tot = B + Sv
                    lean[k] = sgn * (B - Sv) / tot if tot > 0 else 0.0
                    vv[k] = tot
                    pr[k] = sgn * np.log(mid[end] / mid[E]) * 1e4
                leans.append(lean); prices.append(pr); vols.append(vv); cnt += 1
    L = np.array(leans).mean(0); P = np.array(prices).mean(0); V = np.array(vols).mean(0)
    n = len(leans)

    def split(f):
        fr = f[::-1]
        even = (f + fr) / 2; odd = (f - fr) / 2
        e = float(np.sum(even**2)); o = float(np.sum(odd**2)); tot = e + o + 1e-12
        return even, odd, e / tot, o / tot

    print(f"n={n}   even=symmetric/mirror, odd=asymmetry (the edge)")
    for name, f in [("lean", L), ("price", P), ("volume", V)]:
        _, _, ef, of = split(f)
        print(f"  {name:7s}: even {ef:5.1%}   ODD {of:5.1%}")

    le, lo, _, lof = split(L)
    fig, ax = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
    fig.suptitle(f"The turn's symmetry — lean = even (mirror) + ODD (the edge); odd={lof:.1%} ({n} winners)",
                 fontsize=11)
    ax[0].plot(offs, L, color="darkorange"); ax[0].set_ylabel("lean"); ax[0].set_title("the lean", fontsize=9)
    ax[1].plot(offs, le, color="steelblue"); ax[1].set_ylabel("EVEN\n(symmetric)")
    ax[1].set_title("even part — the mirror bowl (no edge here: time-reversible)", fontsize=9)
    ax[2].plot(offs, lo, color="crimson"); ax[2].axhline(0, color="gray", lw=.6)
    ax[2].set_ylabel("ODD\n(asymmetry)"); ax[2].set_title("odd part — the symmetry BREAK = where prediction lives", fontsize=9)
    for a in ax:
        a.axvline(0, color="royalblue", ls="--", lw=1); a.grid(alpha=.25)
    ax[2].set_xlabel("seconds from the turn")
    fig.tight_layout(rect=[0, 0, 1, 0.98]); fig.savefig("turn_symmetry.png", dpi=120)
    print("\nwrote turn_symmetry.png")


if __name__ == "__main__":
    main()
