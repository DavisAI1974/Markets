"""_render_turn.py — the TURN as a DIRECTIONAL flow trend (not a magnitude average).
Per second, the net SIGNED flow over a trailing-W "trend" window (volume-weighted direction), sign-aligned
to the winning side, slid 1s through the turn. Watch the lean slide from old-direction -> 0 -> new-direction.
Averaged over covered BTC/ETH bybit winners."""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from odcore.io import load_bins

LB = 1800; H = 60; W = 60; CAP = 500     # view +/-60s; trailing 60s directional TREND


def main():
    offs = np.arange(-H, H + 1)
    P, D, V = [], [], []
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
                dvec = np.empty(len(offs)); vvec = np.empty(len(offs)); pvec = np.empty(len(offs))
                m0 = mid[E - H]
                for k, o in enumerate(offs):
                    end = E + o
                    B = cb[end + 1] - cb[end - W + 1]      # trailing-W taker buy
                    Sv = cs[end + 1] - cs[end - W + 1]      # trailing-W taker sell
                    tot = B + Sv
                    dvec[k] = sgn * (B - Sv) / tot if tot > 0 else 0.0   # signed DIRECTION toward winside
                    vvec[k] = tot
                    pvec[k] = sgn * np.log(mid[end] / m0) * 1e4
                D.append(dvec); V.append(vvec); P.append(pvec); cnt += 1
    P = np.array(P); D = np.array(D); V = np.array(V); n = len(P)

    fig, ax = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
    fig.suptitle(f"The TURN — directional flow trend (trailing {W}s), {n} BTC/ETH bybit winners, x=turn",
                 fontsize=12)
    ax[0].plot(offs, P.mean(0), color="black"); ax[0].set_ylabel("price toward\nwinside (bps)")
    ax[0].set_title("the swing — down into the turn, up out of it", fontsize=9)
    ax[1].plot(offs, D.mean(0), color="darkorange"); ax[1].axhline(0, color="gray", lw=.7)
    ax[1].set_ylabel(f"net flow direction\n(trend {W}s -> winside)")
    ax[1].set_title("the LEAN slides from old direction (-) through 0 to new (+)", fontsize=9)
    ax[2].plot(offs, V.mean(0), color="seagreen"); ax[2].set_ylabel(f"volume\n(trailing {W}s)")
    ax[2].set_title("volume", fontsize=9)
    for a in ax:
        a.axvline(0, color="royalblue", ls="--", lw=1); a.grid(alpha=.25)
    ax[2].set_xlabel("seconds from the turn")
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig("turn_signature.png", dpi=120)
    md = D.mean(0)
    print(f"n={n}  wrote turn_signature.png")
    print(f"\ndirectional lean (trend {W}s -> winside), second-by-second near the turn:")
    for o in range(-20, 21, 4):
        print(f"  {o:+3d}s  lean={md[o + H]:+.4f}")


if __name__ == "__main__":
    main()
