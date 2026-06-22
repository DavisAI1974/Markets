"""Class separation on the algebraic-dipole axes.

The fit confirmed H_a^2 = poly(H_a*H_b) per pair (R^2 0.5-0.96). The fit
tells us the CONSTRAINT surface exists, but says nothing about whether
winners and losers cluster in different regions of it. This script tests
per-pair Cohen's d between win-class and lose-class on each axis the
dipole reads:

  H_a            (alignment with win centroid)
  H_b            (alignment with lose centroid)
  H_a * H_b      (cross term, the equation's x)
  H_a^2          (equation's y)
  delta = H_a - H_b   (signed margin — how much more win-aligned)

|d| >= 0.8 is large effect; >= 0.5 medium; >= 0.2 small. d >= 1.0 = strong
predictor signal in a single dimension.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

DISC = Path(r"E:\refrag\discoveries\operator_discoveries")
WIN_SUFFIX: str | None = None
LOSE_SUFFIX: str | None = None

def _win_sfx() -> str:
    return f"_{WIN_SUFFIX}" if WIN_SUFFIX else ""

def _lose_sfx() -> str:
    return f"_{LOSE_SUFFIX}" if LOSE_SUFFIX else ""
PAIRS = [
    "markets_btc_bybit_buy", "markets_btc_bybit_sell",
    "markets_btc_coinbase_buy", "markets_btc_coinbase_sell",
    "markets_btc_kraken_buy", "markets_btc_kraken_sell",
    "markets_eth_bybit_buy", "markets_eth_bybit_sell",
    "markets_eth_coinbase_buy", "markets_eth_coinbase_sell",
    "markets_eth_kraken_buy", "markets_eth_kraken_sell",
]

def load_coefs(domain: str) -> list[list[float]]:
    d = DISC / domain
    if not d.is_dir():
        return []
    out: list[list[float]] = []
    for p in d.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        coefs = obj.get("result", {}).get("operator_coefficients")
        if isinstance(coefs, list) and coefs:
            out.append([float(c) for c in coefs])
    return out

def vec_mean(vs):
    n = len(vs); d = len(vs[0])
    out = [0.0] * d
    for v in vs:
        for i in range(d):
            out[i] += v[i]
    return [x / n for x in out]

def dot(a, b): return sum(x * y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a))

def cohens_d(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2: return 0.0
    sa = statistics.pstdev(a); sb = statistics.pstdev(b)
    pooled = math.sqrt((sa * sa + sb * sb) / 2.0)
    if pooled == 0: return 0.0
    return (statistics.mean(a) - statistics.mean(b)) / pooled

def main():
    global WIN_SUFFIX, LOSE_SUFFIX
    ap = argparse.ArgumentParser()
    ap.add_argument("--win-domain-suffix", type=str, default=None)
    ap.add_argument("--lose-domain-suffix", type=str, default=None)
    args = ap.parse_args()
    WIN_SUFFIX = args.win_domain_suffix.strip().lower() if args.win_domain_suffix else None
    LOSE_SUFFIX = args.lose_domain_suffix.strip().lower() if args.lose_domain_suffix else None
    if WIN_SUFFIX or LOSE_SUFFIX:
        print(f"[win{_win_sfx()}/, lose{_lose_sfx()}/]")

    print(f"{'pair':30s}  {'d(H_a)':>7s}  {'d(H_b)':>7s}  {'d(H_a*H_b)':>10s}  {'d(H_a^2)':>9s}  {'d(H_a-H_b)':>11s}")
    print("-" * 95)
    rows = []
    for pair in PAIRS:
        cw = load_coefs(f"{pair}_win{_win_sfx()}")
        cl = load_coefs(f"{pair}_lose{_lose_sfx()}")
        if not cw or not cl:
            print(f"{pair:30s}  --       --       --          --         --          (incomplete)")
            continue
        c_w = vec_mean(cw); c_l = vec_mean(cl)
        nw = norm(c_w) or 1.0; nl = norm(c_l) or 1.0
        Ha_w = [dot(c, c_w) / nw for c in cw]
        Hb_w = [dot(c, c_l) / nl for c in cw]
        Ha_l = [dot(c, c_w) / nw for c in cl]
        Hb_l = [dot(c, c_l) / nl for c in cl]
        d_Ha = cohens_d(Ha_w, Ha_l)
        d_Hb = cohens_d(Hb_w, Hb_l)
        d_HaHb = cohens_d([a*b for a,b in zip(Ha_w,Hb_w)], [a*b for a,b in zip(Ha_l,Hb_l)])
        d_Ha2 = cohens_d([x*x for x in Ha_w], [x*x for x in Ha_l])
        d_delta = cohens_d([a-b for a,b in zip(Ha_w,Hb_w)], [a-b for a,b in zip(Ha_l,Hb_l)])
        rows.append((pair, d_Ha, d_Hb, d_HaHb, d_Ha2, d_delta))
        print(f"{pair:30s}  {d_Ha:+7.3f}  {d_Hb:+7.3f}  {d_HaHb:+10.3f}  {d_Ha2:+9.3f}  {d_delta:+11.3f}")

    # summary stats
    if rows:
        for label, idx in (("H_a", 1), ("H_b", 2), ("H_a*H_b", 3), ("H_a^2", 4), ("H_a-H_b", 5)):
            vals = [abs(r[idx]) for r in rows]
            print(f"  mean |d({label})| = {sum(vals)/len(vals):.3f}, max = {max(vals):.3f}")

if __name__ == "__main__":
    main()
