"""S77: PATIENT MAKER-EXIT model — the deploy gate. Greg S77: on volatile coins, sit longer and let the
oscillation bring price back to our resting exit so we fill as a MAKER (earn the -2bp rebate) instead of
crossing (pay +10bp taker). Risk modeled honestly: if the coin TRENDS through (price never returns within
W), we're forced to cross at a WORSE price after waiting.

At each exit trigger (trailing stop / max-hold) we post a maker at the signal price mid[i] and sit up to W:
  - long  (d>0): filled as maker if price bounces back UP to mid[i]  (some j in (i,i+W] with mid[j]>=mid[i])
  - short (d<0): filled as maker if price comes back DOWN to mid[i]
  fill -> realized at fav(mid[i]), exit fee = maker (-2 smallcap / 0 major)
  no fill in W -> cross taker at mid[i+W] (worse), exit fee = taker (+10 smallcap / +5 major)
Entry is always a maker (rebate/0%). Sweep W per cell; report maker-fill% + net $/hr (x0.9). W=0 == the
taker floor. Uses each cell's picked config from r2_<coin>.txt. Live entry logic (zscores + es thresholds).

    python3 exit_model.py [coin ...]
"""
import os, sys, json, types, re
import numpy as np
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
from book_swing_kraken import series_1s, zscores, CAP, FILL, MAJORS, LEG
from collections import deque

WAITS = (0, 30, 60, 120, 300)
ALL = "btc eth sol xrp doge aave ada avax bch bnb hype link ltc near sui tao ton xlm xmr xpl zec".split()


def picked(coin):
    t = open(f"/tmp/kbook/r2_{coin}.txt").read()
    m = re.search(r"horizon=(\d+)s sign=([+-]\d) enter_z=([\d.]+) minconv=([\d.]+) trail=(\d+) hold=(\d+)", t)
    return dict(ds=int(m[2]), ez=float(m[3]), mc=float(m[4]), trail=float(m[5]), mh=int(m[6])) if m else None


def run_exit(imb, mid, z, cfg, W, mk, tk):
    """Replay entries; at each exit trigger apply the patient maker-exit with wait W. Returns (net_bps[], maker_fill_flags[])."""
    n = len(imb); pos = None; pnl = []; mkfill = []
    i = 0
    while i < n:
        if pos is None:
            if abs(z[i]) >= cfg["ez"] and abs(imb[i]) >= cfg["mc"]:
                pos = {"d": cfg["ds"] if z[i] > 0 else -cfg["ds"], "entry": mid[i], "best": 0.0, "t": 0}
            i += 1; continue
        pos["t"] += 1
        fav = pos["d"] * (mid[i] - pos["entry"]) / pos["entry"] * 1e4
        pos["best"] = max(pos["best"], fav)
        if (pos["best"] - fav) >= cfg["trail"] or pos["t"] >= cfg["mh"]:
            # exit trigger at i, signal price P=mid[i]; sit up to W for a maker fill
            P = mid[i]; d = pos["d"]; filled = False; jend = min(i + W, n - 1)
            for j in range(i + 1, jend + 1):
                if (d > 0 and mid[j] >= P) or (d < 0 and mid[j] <= P):
                    filled = True; break
            if filled:
                fav_fill = d * (P - pos["entry"]) / pos["entry"] * 1e4
                pnl.append(fav_fill - mk - mk)          # entry maker + exit maker  (fees as COST; mk<0 = rebate)
                mkfill.append(1); i = j + 1
            else:
                fav_fill = d * (mid[jend] - pos["entry"]) / pos["entry"] * 1e4
                pnl.append(fav_fill - mk - tk)          # entry maker + exit taker (worse price after W)
                mkfill.append(0); i = jend + 1
            pos = None; continue
        i += 1
    return np.array(pnl), np.array(mkfill)


def main():
    coins = sys.argv[1:] or ALL
    print(f"{'coin':>6}{'bestW':>6}{'mkfill%':>8}{'net_bps':>9}{'$/hr*.9':>9}{'W0(taker)$/hr':>15}{'n':>5}")
    for c in coins:
        cfg = picked(c)
        if not cfg:
            continue
        imb, mid = series_1s(f"{os.environ.get('BOOK_DIR','/tmp/kbook')}/{c}_book.jsonl")
        n = len(imb); cut = int(n * 0.6); te_h = (n - cut) / 3600.0
        imb_te, mid_te = imb[cut:], mid[cut:]; z_te = zscores(imb_te)
        tier = "major" if c in MAJORS else "smallcap"
        mk, tk = LEG[tier]["maker"], LEG[tier]["taker"]
        if os.environ.get("RAMP_MAKER"):   # override for the pre-$10M ramp (standard Kraken fees)
            mk, tk = float(os.environ["RAMP_MAKER"]), float(os.environ["RAMP_TAKER"])
        best = None; w0 = None
        for W in WAITS:
            p, mf = run_exit(imb_te, mid_te, z_te, cfg, W, mk, tk)
            if len(p) < 3: continue
            dph = p.sum() / 1e4 * CAP / te_h * FILL
            if W == 0: w0 = dph
            if best is None or dph > best[3]:
                best = (W, mf.mean() * 100, p.mean(), dph, len(p))
        if best:
            W, mfr, nb, dph, nn = best
            print(f"{c.upper():>6}{W:>6}{mfr:>8.1f}{nb:>9.2f}{dph:>9.1f}{(w0 if w0 is not None else float('nan')):>15.1f}{nn:>5}")


if __name__ == "__main__":
    main()
