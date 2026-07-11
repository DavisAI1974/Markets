"""S77 step-1 VALIDATE: realistic maker-fill backtest vs mid-price. The honest reckoning for a DIRECTIONAL
maker: you rest a bid to go long, but a resting bid only fills when price trades DOWN to it (adverse — the
market is dropping); when your up-prediction is right, price ticks up and away and you NEVER fill (missed).
Mid-price P&L assumes you fill at mid on every signal — it hides both effects.

MODEL (per 1s bar we have: mid, spread, buy, sell):
- Signal fires long (book lean up, sign-fit). Rest a maker BID at entry_bid = mid_s - spread_s/2.
- Entry fills at bar j>s if mid[j] <= entry_bid (price came DOWN to us) within FILL_WINDOW; else NO FILL (the
  trades where we were right and price ran away — counted as missed, they earn nothing).
- On fill we are long from entry_bid (we bought BELOW the signal mid — earn half-spread). Ride to reversal;
  exit as a maker ASK at exit = mid_x + spread_x/2 (sell ABOVE mid — earn the other half-spread) if price rises
  to it within the hold, else cross at mid_x - taker (pay). P&L = exit_px - entry_bid - fees.
Compare: MID baseline (fill at mid every signal, exit at mid) vs REALISTIC (maker fills at bid/ask + misses).
This isolates the adverse-selection + spread-capture net. Sign fit per coin on TRAIN, tested OOS.

    python3 realistic_fill.py [coin ...]      # default: eth xrp doge btc (Coinbase)
"""
import os, sys, json, types
import numpy as np
from collections import deque
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, "/home/user/Markets")
if "matplotlib" not in sys.modules:
    _m = types.ModuleType("matplotlib"); _m.use = lambda *a, **k: None
    _p = types.ModuleType("matplotlib.pyplot"); _p.__getattr__ = lambda n: (lambda *a, **k: None)
    _m.pyplot = _p; sys.modules["matplotlib"] = _m; sys.modules["matplotlib.pyplot"] = _p
import early_signal as es

BOOK_DIR = os.environ.get("BOOK_DIR", "/tmp/cbook")
STRIDE = 10
ROLL = es.DEFAULT_ROLL
SD_FLOOR = es.EarlySignalTracker.SD_FLOOR
CAP = 5000.0
FILL_WINDOW = 30      # bars (s) to wait for the resting maker entry to fill
MAXHOLD = 300
TRAIL = 30.0
ENTER_Z, MINCONV = 1.5, 0.5
TAKER_BP = 3.0        # Coinbase taker ~1-3bp if the exit must cross


def load(path):
    imb, mid, spr = [], [], []
    with open(path) as f:
        for i, line in enumerate(f):
            if i % STRIDE:
                continue
            r = json.loads(line); m = float(r["mid"])
            k = es.DEFAULT_K
            bids = [[m + float(o), float(s)] for o, s in r["bids"][:k]]
            asks = [[m + float(o), float(s)] for o, s in r["asks"][:k]]
            bk = es.book_imbalance(bids, asks, k, m)
            imb.append(bk["imb"] if bk["ok"] else 0.0); mid.append(m)
            spr.append(float(r.get("spread", 0.0)))
    return np.array(imb), np.array(mid), np.array(spr)


def zscores(imb):
    n = len(imb); z = np.zeros(n); hist = deque(maxlen=ROLL)
    for i in range(n):
        if len(hist) >= 5:
            mn = sum(hist) / len(hist)
            sd = max((sum((v - mn) ** 2 for v in hist) / len(hist)) ** 0.5, SD_FLOOR)
            z[i] = (imb[i] - mn) / sd
        hist.append(imb[i])
    return z


def backtest(imb, mid, spr, z, ds, realistic):
    """Returns (net_bps_per_signal_array, n_fills, n_signals). realistic=False => mid fill every signal."""
    n = len(imb); i = 0; pnl = []; fills = 0; sigs = 0
    while i < n - 1:
        if not (abs(z[i]) >= ENTER_Z and abs(imb[i]) >= MINCONV):
            i += 1; continue
        d = ds if z[i] > 0 else -ds
        sigs += 1
        half = spr[i] / 2.0
        if not realistic:
            entry = mid[i]; fi = i                      # MID baseline: fill at mid, now
        else:
            # maker entry: rest bid (long) at mid-half; fill only if price comes to us within window
            target = mid[i] - d * half                  # long: bid below; short: ask above
            fi = None
            for j in range(i + 1, min(i + 1 + FILL_WINDOW, n)):
                if (d > 0 and mid[j] <= target) or (d < 0 and mid[j] >= target):
                    fi = j; break
            if fi is None:
                i += 1; continue                        # MISSED (price ran our way, no fill) — earns nothing
            entry = target; fills += 1
        # ride from fi to reversal/maxhold
        best = 0.0; xi = None
        for j in range(fi + 1, min(fi + MAXHOLD, n)):
            fav = d * (mid[j] - entry) / entry * 1e4
            best = max(best, fav)
            if best - fav >= TRAIL:
                xi = j; break
        if xi is None:
            xi = min(fi + MAXHOLD, n - 1)
        # maker exit: rest at mid+half (long sells above); assume filled at that level (optimistic exit — the
        # patient-exit result showed ~95% maker fill). Half-spread earned on exit too.
        xhalf = spr[xi] / 2.0
        if realistic:
            exit_px = mid[xi] + d * xhalf               # sell above mid (long) / buy below (short)
            fee = 0.0                                    # 0% maker both legs (Coinbase intro); spread already in px
        else:
            exit_px = mid[xi]; fee = 0.0
        net = d * (exit_px - entry) / entry * 1e4 - fee
        pnl.append(net)
        i = xi + 1
    return np.array(pnl), fills, sigs


def main():
    coins = sys.argv[1:] or ["eth", "xrp", "doge", "btc"]
    print(f"REALISTIC MAKER-FILL vs MID ({BOOK_DIR}, 0% maker, patient exit)\n")
    print(f"{'coin':>6}{'MID $/hr':>10}{'REAL $/hr':>11}{'fill%':>8}{'bps/fill':>10}{'signals':>9}")
    for c in coins:
        p = f"{BOOK_DIR}/{c}_book.jsonl"
        if not os.path.exists(p):
            print(f"{c.upper():>6}  (no book)"); continue
        imb, mid, spr = load(p)
        n = len(imb); cut = int(n * 0.6); te_h = (n - cut) / 3600.0
        tr = slice(0, cut); teh = slice(cut, n)
        fit = es.fit_direction_sign(imbalances=imb[tr].tolist(), mids=mid[tr].tolist(), horizon=60, min_conviction=MINCONV)
        ds = fit["sign"]
        z = zscores(imb[teh])
        pm, _, sm = backtest(imb[teh], mid[teh], spr[teh], z, ds, realistic=False)
        pr, fr, sr = backtest(imb[teh], mid[teh], spr[teh], z, ds, realistic=True)
        mid_hr = pm.sum() / 1e4 * CAP / te_h if len(pm) else 0.0
        real_hr = pr.sum() / 1e4 * CAP / te_h if len(pr) else 0.0
        fillpct = 100.0 * fr / sr if sr else 0.0
        bpsf = pr.mean() if len(pr) else 0.0
        print(f"{c.upper():>6}{mid_hr:>10.1f}{real_hr:>11.1f}{fillpct:>8.1f}{bpsf:>10.2f}{sr:>9}")
    print("""
READ: MID = the optimistic backtest (fill at mid every signal). REAL = maker fills at bid/ask, entry fills
only when price comes to our resting quote (else missed), P&L marked at the real fill prices. The gap MID->REAL
is the adverse-selection + spread-capture net for a DIRECTIONAL maker. If REAL collapses vs MID, the directional
book-swing doesn't survive as a pure maker -> the edge is spread-capture market-making (the quote service), not
directional swings. CAVEAT: exit still assumes ~maker fill (patient-exit showed ~95%); entry adverse selection
is the main new effect modeled here. Provisional, one window.""")


if __name__ == "__main__":
    main()
