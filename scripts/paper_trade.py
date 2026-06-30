"""paper_trade.py — forward paper-trading harness for the maker-at-the-turn swing strategy + two-factor
conviction sizing, ALL cells (Greg S47: "bring them all into paper trades, see how they shake out").

CAUSAL by construction: trades come from the validated causal executor (odcore.swing_maker.simulate_swing_maker
over odcore.flip_detector.detect_flips); the conviction SIZE multiplier is normalized on a TRAILING window of
PRIOR trades only (no look-ahead). Net-of-fee with a configurable maker/taker model (S47: needs maker <= 0).

Appends to a persistent JSONL ledger, deduped by (cell, entry_ts), so repeated runs over the rolling book
window accumulate a genuine FORWARD record. Run on a schedule (the book cron rolls the window forward); over
time the ledger IS the multi-window out-of-sample test the one-window backtest could not give us.

DOES NOT trade real money. DOES NOT modify the executor. Per-cell; partial coverage is not failure — the
forward ledger decides which cells earn deployment.
"""
from __future__ import annotations
import sys, os, json, gzip, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _liquidity_dive import build_channels, median_spread_bps
from _birth_probe import load_book
from odcore.flip_detector import lean_series, detect_flips
from odcore.swing_maker import simulate_swing_maker

FLOW_W, TRAIN_FRAC, WFLIP, REV, DIVW = 20, 0.6, 600, 0.1, 600
CELLS = [("sol", 1), ("doge", 1), ("xrp", 1), ("eth", 1), ("btc", 10)]
LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper_ledger.jsonl")


def _z(x):
    x = np.asarray(x, float); s = x.std()
    return (x - x.mean()) / (s + 1e-12)


def cell_trades(coin, K, maker_fee, taker_fee, alpha, roll):
    path = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(path):
        return []
    ch, g = build_channels(path, K, FLOW_W)
    mid = np.asarray(g["mid"], float)
    bb, ba = np.asarray(g["bidK"][1], float), np.asarray(g["askK"][1], float)
    buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
    sret = ch["signed_ret"]
    n = len(mid); hs = median_spread_bps(path) / 2.0
    t0 = float(load_book(path)["ts"][0])                     # grid idx -> ts = t0 + idx*0.1
    vol = buy + sell; cvol = np.concatenate([[0.0], np.cumsum(vol)])
    vm = lambda t, w: (cvol[t + 1] - cvol[max(0, t + 1 - w)]) / (t + 1 - max(0, t + 1 - w))
    lean = lean_series(buy, sell, WFLIP)
    allf = detect_flips(lean, REV)[0]
    piv = {int(c): int(p) for (c, p, s) in allf}
    res = simulate_swing_maker(mid, bb, ba, buy, sell, allf, half_spread_bps=hs,
                               maker_fee_bps=maker_fee, taker_fee_bps=taker_fee)
    # per-leg causal features at the flip (decision) cell
    legs = res.legs
    clmx, size_score = [], []
    for l in legs:
        ci = int(l.flip_idx); p = piv.get(ci, ci); lo = max(0, ci - DIVW)
        cx = vm(ci, 60) / (vm(ci, 600) + 1e-12)
        v60 = vm(ci, 60); vlt = float(np.std(sret[max(0, ci - 120):ci + 1])) * 1e4
        rnp = abs(mid[ci] - mid[lo]) / mid[lo] * 1e4; dp = abs(lean[p])
        clmx.append(cx); size_score.append(v60 + vlt + rnp + dp)   # crude SIZE proxy (predicts |move|)
    # pass 1: CAUSAL conviction = rank(quality) x rank(size) vs the trailing `roll` PRIOR legs only (0..1)
    conv = np.full(len(legs), 0.25)
    for i in range(len(legs)):
        lo = max(0, i - roll)
        if i - lo >= 20:
            pr = list(range(lo, i))
            rq = float((np.array([clmx[j] for j in pr]) < clmx[i]).mean())
            rs = float((np.array([size_score[j] for j in pr]) < size_score[i]).mean())
            conv[i] = rq * rs                              # E[net] ~ P(reversal)*E[|move|]
    out = []
    for i, l in enumerate(legs):
        # pass 2: matched-capital, CAUSAL size multiplier — trailing z of conv, centered on 1 (mean size ~= 1)
        lo = max(0, i - roll)
        if i - lo >= 20:
            pr = conv[lo:i]; sd = pr.std()
            zc = (conv[i] - pr.mean()) / (sd + 1e-9)
            size_mult = float(np.clip(1.0 + alpha * zc, 0.25, 4.0))
        else:
            size_mult = 1.0                                  # warmup: flat
        ts = t0 + int(l.open_idx) * 0.1
        out.append(dict(cell=f"{coin}_coinbase", coin=coin, ts=round(ts, 3), side=int(l.side),
                        entry=round(float(l.open_px), 6), exit=round(float(l.close_px), 6),
                        net_bps=round(float(l.net_bps), 4), size_mult=round(size_mult, 3),
                        sized_net=round(float(l.net_bps) * size_mult, 4),
                        swing_bps=round(float(l.swing_bps), 3), maker_close=bool(l.close_maker)))
    return out


def load_ledger():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER) as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maker", type=float, default=0.0); ap.add_argument("--taker", type=float, default=5.0)
    ap.add_argument("--alpha", type=float, default=1.0); ap.add_argument("--roll", type=int, default=200)
    a = ap.parse_args()
    existing = load_ledger()
    seen = {(r["cell"], r["ts"]) for r in existing}
    new = []
    for coin, K in CELLS:
        try:
            for tr in cell_trades(coin, K, a.maker, a.taker, a.alpha, a.roll):
                if (tr["cell"], tr["ts"]) not in seen:
                    new.append(tr); seen.add((tr["cell"], tr["ts"]))
        except Exception as e:
            print(f"# {coin} ERR {e}")
    with open(LEDGER, "a") as f:
        for tr in new:
            f.write(json.dumps(tr) + "\n")
    print(f"# paper_trade: +{len(new)} new trades (maker={a.maker} taker={a.taker} alpha={a.alpha})")
    ledger = existing + new
    print(f"# LEDGER TOTAL {len(ledger)} trades across all runs. per-cell shakeout (net-of-fee):")
    print(f"# {'cell':16s}{'n':>6}{'flat_net':>10}{'sized_net':>11}{'win%':>6}{'taker%':>8}{'mean_sz':>9}")
    for coin, _ in CELLS:
        rs = [r for r in ledger if r["coin"] == coin]
        if not rs:
            print(f"# {coin+'_coinbase':16s}{0:>6}"); continue
        fn = sum(r["net_bps"] for r in rs); sn = sum(r["sized_net"] for r in rs)
        win = 100 * np.mean([r["net_bps"] > 0 for r in rs]); tk = 100 * np.mean([not r["maker_close"] for r in rs])
        msz = float(np.mean([r["size_mult"] for r in rs]))
        print(f"# {coin+'_coinbase':16s}{len(rs):>6}{fn:>+10.1f}{sn:>+11.1f}{win:>6.0f}{tk:>8.0f}{msz:>9.2f}")


if __name__ == "__main__":
    main()
