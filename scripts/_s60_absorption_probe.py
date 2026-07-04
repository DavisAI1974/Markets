"""_s60_absorption_probe.py — S60: SPOOF/ABSORPTION detection (Greg: "we can definitely use this").

The dive chapter §3.5 candidate, first falsifiable test, on the Coinbase books (book + trade
tape — the exact data it needs; and it is a COINBASE-venue read, so it fits the exit focus).

HYPOTHESIS (unsigned-vs-signed divergence): a DEEP taker-flow lean with NO price response =
ABSORPTION (a resting wall eating the flow). Absorbed pressure exhausts -> the price should
subsequently REVERSE against the absorbed flow. Contrast with a deep lean WITH price response
(flow moves price = genuine momentum, continuation).

DEFINITIONS (all causal, per second):
  lean_W   = trailing-W wall-clock taker imbalance (B-S)/(B+S)  [flip_detector.lean_series]
  DEEP     = |lean_W| >= L (default 0.5)
  RESPONSE = signed price move over the SAME trailing window, in units of half-spread:
             resp = sign(lean) * (mid[t]-mid[t-W]) / mid[t-W] * 1e4 / hs
             resp >  R_hi  -> flow MOVED price (momentum / continuation)
             |resp| < R_lo -> NO response (ABSORPTION candidate)
  FWD      = forward return over horizon H, SIGNED BY THE LEAN:
             fwd = sign(lean) * (mid[t+H]-mid[t]) / mid[t] * 1e4
             absorption predicts fwd < 0 (reversal against the absorbed flow).

TEST: split deep-lean seconds into {absorbed, moved} by response; compare mean forward return
(lean-signed) at horizons; a real absorption edge shows absorbed << moved AND absorbed < 0,
beyond a circular-shift tautology null on the lean.

THIN-DIVE CROSS-CHECK (dive chapter §2.1): deep leans are thin-volume; report per-class volume
so "real thin dive" vs "absorbed thick dive" is visible in the data.

Usage: python scripts/_s60_absorption_probe.py            # all 5 coinbase books
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                                    # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps         # noqa: E402
from odcore.flip_detector import lean_series                          # noqa: E402

COINS = ("sol", "eth", "btc", "doge", "xrp")
W = 300          # wall-clock seconds (books grid 0.1s -> 3000 cells)
L = 0.5          # deep-lean threshold
R_HI = 1.0       # response > 1 half-spread = moved
R_LO = 0.25      # |response| < 0.25 half-spread = no response (absorption)
HORIZONS = (150, 600, 3000)     # cells: 15s / 60s / 300s forward
N_SHUF = 3


def probe(coin):
    p = f"/tmp/{coin}_coinbase_book.jsonl.gz"
    if not os.path.exists(p):
        return None
    raw = load_book(p)
    _, g = build_channels(p, 1, 20, raw=raw)
    mid = np.asarray(g["mid"], float)
    buy = np.asarray(g["buy"], float)
    sell = np.asarray(g["sell"], float)
    n = len(mid)
    grid = (float(raw["ts"][-1]) - float(raw["ts"][0])) / max(n - 1, 1)   # sec/cell
    Wc = max(1, int(round(W / grid)))
    hs = median_spread_bps(p, raw=raw) / 2.0
    lean = lean_series(buy, sell, Wc)
    tot = np.concatenate([[0.0], np.cumsum(buy + sell)])

    def window_ret(a, w):
        out = np.full(n, np.nan)
        out[w:] = (a[w:] - a[:-w]) / a[:-w] * 1e4
        return out

    trail = window_ret(mid, Wc)                       # signed trailing return, bps
    sgn = np.sign(lean)
    resp = sgn * trail / hs                            # response in half-spreads
    deep = (np.abs(lean) >= L) & ~np.isnan(resp)
    cvol = tot                                         # len n+1 cumulative
    volv = np.full(n, np.nan)
    volv[Wc:] = cvol[Wc + 1:] - cvol[1:n - Wc + 1]     # taker volume in trailing Wc cells
    base_vol = np.nanmedian(volv[Wc:])

    def fwd(h):
        out = np.full(n, np.nan)
        out[:n - h] = sgn[:n - h] * (mid[h:] - mid[:n - h]) / mid[:n - h] * 1e4
        return out

    absorbed = deep & (np.abs(resp) < R_LO)
    moved = deep & (resp > R_HI)
    rows = []
    for h in HORIZONS:
        f = fwd(h)
        a = f[absorbed & ~np.isnan(f)]
        m = f[moved & ~np.isnan(f)]
        rows.append((h, len(a), np.mean(a) if len(a) else np.nan,
                     len(m), np.mean(m) if len(m) else np.nan))

    # circular-shift null on the forward return vs the absorbed mask (kills tautology)
    h0 = HORIZONS[1]
    f0 = fwd(h0)
    real = np.nanmean(f0[absorbed & ~np.isnan(f0)])
    nulls = []
    rng = np.random.default_rng(11)
    for _ in range(N_SHUF):
        sh = int(rng.integers(n // 4, 3 * n // 4))
        fs = np.roll(f0, sh)
        nulls.append(np.nanmean(fs[absorbed & ~np.isnan(fs)]))
    z = (real - np.mean(nulls)) / (np.std(nulls) + 1e-9)

    return dict(coin=coin, n=n, grid=grid, Wc=Wc, hs=hs, deep=int(deep.sum()),
                absorbed=int(absorbed.sum()), moved=int(moved.sum()),
                vol_abs=np.nanmean(volv[absorbed]) / base_vol if absorbed.any() else np.nan,
                vol_mov=np.nanmean(volv[moved]) / base_vol if moved.any() else np.nan,
                rows=rows, z=z, real=real, null=np.mean(nulls))


def main():
    print("=== S60 ABSORPTION/SPOOF PROBE — Coinbase books (book+trade) ===")
    print(f"W={W}s deep|lean|>={L}  moved resp>{R_HI}hs  absorbed |resp|<{R_LO}hs")
    print("fwd return SIGNED BY LEAN (absorption predicts NEGATIVE = reversal); vol = x median\n")
    for c in COINS:
        r = probe(c)
        if r is None:
            print(f"[{c}] no book"); continue
        print(f"{c}: n={r['n']} grid={r['grid']:.2f}s Wc={r['Wc']} hs={r['hs']:.2f}bp | "
              f"deep={r['deep']} absorbed={r['absorbed']} moved={r['moved']} | "
              f"vol absorbed {r['vol_abs']:.2f}x / moved {r['vol_mov']:.2f}x")
        for (h, na, ma_, nm, mm) in r["rows"]:
            hs_ = h * r["grid"]
            print(f"    fwd {hs_:>5.0f}s: absorbed {ma_:>+7.2f}bp (n={na:>5})   "
                  f"moved {mm:>+7.2f}bp (n={nm:>5})   [abs-mov {ma_-mm:>+7.2f}]")
        print(f"    NULL (60s, circular-shift): real {r['real']:>+6.2f} vs null "
              f"{r['null']:>+6.2f}  z={r['z']:>+5.1f}\n")


if __name__ == "__main__":
    main()
