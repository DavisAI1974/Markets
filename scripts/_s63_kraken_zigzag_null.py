"""_s63_kraken_zigzag_null.py — is the Kraken zigzag edge REAL mean-reversion or a sparse-tape artifact?

The kr_mk0 zigzag nets positive on BTC/ETH. Two explanations: (a) real short-horizon mean-reversion
in Kraken's tape, or (b) an artifact of the thin, forward-filled tape. Decisive test: shuffle the log
-RETURNS (destroys serial/mean-reversion structure, keeps the exact return distribution), run the
same zigzag, compare. Real edge -> real >> shuffled-null (~0). Artifact -> real ~ null.

Speed: forward-filled FLAT seconds never affect the zigzag (they don't move the extreme or trigger a
retrace), so we compress the series to its CHANGE-POINTS (identical zigzag result, ~6x fewer points).
Shuffled nulls are built from the nonzero returns and are likewise compact. Output written to a file
(not stdout) so partial results survive. Representative theta only (30bp).

Usage:  python scripts/_s63_kraken_zigzag_null.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins                              # noqa: E402
from _s63_kraken_zigzag import zigzag, CAP                             # noqa: E402

REALBINS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "realbins")
KTAPE = "/tmp/kraken_backfill"
OUT = "/tmp/kraken_backfill/_zigzag_null.txt"
CELLS = [("btc", f"{REALBINS}/btc_kraken_bins.json"),
         ("eth", f"{REALBINS}/eth_kraken_bins.json"),
         ("doge", f"{KTAPE}/XDGUSD_30d_bins.json"),
         ("sol", f"{KTAPE}/SOLUSD_30d_bins.json"),
         ("xrp", f"{KTAPE}/XRPUSD_30d_bins.json")]
THETA = 30
N_NULL = 100
SEED = 3


def emit(line, fh):
    print(line); fh.write(line + "\n"); fh.flush()


def main():
    rng = np.random.default_rng(SEED)
    fh = open(OUT, "w")
    emit("=== Kraken zigzag: REAL vs return-SHUFFLED null (kr_mk0, net $/hr @ $5k, theta=30bp) ===", fh)
    emit("  real >> null => genuine mean-reversion; real ~ null => sparse-tape artifact\n", fh)
    for coin, path in CELLS:
        if not os.path.exists(path):
            emit(f"[{coin}] not present", fh); continue
        mid, *_rest, cover, hrs = load_bins(path)
        mid = np.asarray(mid, float); lm = np.log(mid)
        dr = np.diff(lm); nz = dr[dr != 0.0]                 # nonzero log-returns (the real moves)
        # compressed real change-point price series
        chg = np.concatenate([[lm[0]], lm[0] + np.cumsum(nz)])
        real = np.sum(zigzag(np.exp(chg), THETA, 0.0)[0]) * CAP / 1e4 / hrs
        null = np.empty(N_NULL)
        for j in range(N_NULL):
            sh = rng.permutation(nz)
            m2 = np.exp(np.concatenate([[lm[0]], lm[0] + np.cumsum(sh)]))
            null[j] = np.sum(zigzag(m2, THETA, 0.0)[0]) * CAP / 1e4 / hrs
        mu = float(null.mean()); sd = float(null.std() + 1e-12)
        z = (real - mu) / sd; p = (np.sum(null >= real) + 1) / (N_NULL + 1)
        verdict = "REAL edge" if (z > 2 and real > 0) else ("~null (artifact)" if abs(z) <= 2 else "negative")
        emit(f"[{coin}]  span={len(mid)/86400:.1f}d cover={cover*100:.0f}%  chgpts={len(nz):,}", fh)
        emit(f"   real={real:>+7.1f}  null mu={mu:>+6.1f} sd={sd:>4.1f}  z={z:>+6.1f}  p={p:.3f}"
             f"   -> {verdict}\n", fh)
    fh.close()


if __name__ == "__main__":
    main()
