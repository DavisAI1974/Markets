"""
regime_feature_audit.py — per-regime feature signature audit.

Goal: make WHALE vs HERD vs EQUILIBRIUM vs DEPLETED differentiation visible
at the level of individual feature values, not just final regime labels.

The Phase 1.5 classifier (regime_classifier.py) decides on these thresholds:

  HERD_*   :  rv > 1.8 * baseline_rv  AND  vol_ratio > 1.5  AND  |dipole| > 0.1
  WHALE_*  :  acl1 > 0.4 AND |dipole| > 0.15
              OR  kyle < 0.3 * baseline_kyle AND vol_ratio > 1.3 AND |dipole| > 0.15
              OR  oscillation: peak_pow > 0.3 AND 0.05 < peak_freq < 0.4 AND |dipole| > 0.15
  EQUIL    :  |dipole| < 0.25  OR  acl1 < 0.2

Decision order: DEPLETED -> WASH -> HERD -> WHALE -> EQUIL -> UNKNOWN.
HERD is checked BEFORE WHALE so a high-vol cascade with sustained one-side
pressure gets HERD label (multi-actor) rather than WHALE (single-actor).

Usage:
    python regime_feature_audit.py --asset ETH \\
        --cb-bins eth_coinbase_bins.json --kr-bins eth_kraken_bins.json
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, stdev

from phase1_5_evaluator import classify_venue, load_bars
from regime_classifier import classify_regime


def fmt_stat(values: list[float], fmt: str = "{:+.3f}") -> str:
    if not values:
        return "n=0"
    if len(values) == 1:
        return f"n=1 {fmt.format(values[0])}"
    m = mean(values)
    s = stdev(values)
    return f"n={len(values)} {fmt.format(m)} ±{fmt.format(s).lstrip('+')}"


def audit_venue(label: str, bins_path: str, multi_signal_pelt: bool = True):
    bars = load_bars(bins_path)
    chunks, results, base, _ = classify_venue(
        bars, label, chunk_max=30, chunk_min=10,
        multi_signal_pelt=multi_signal_pelt,
    )
    feats_by_regime: dict[str, list] = defaultdict(list)
    for c, r in zip(chunks, results):
        # Re-extract MarketFeatures so we can read the discriminators
        # (results only carry the Regime label and notes, not feature values)
        from markets_adapter import MarketChunkEncoder
        enc = MarketChunkEncoder(d_enc=64)
        f = enc._extract(c)
        feats_by_regime[r.regime.value].append((c, r, f))

    print(f"\n=== {label} feature signatures ===")
    print(f"  baselines: rv={base.rv:.5f}  kyle={base.kyle:.6f}  "
          f"vol={base.chunk_volume:.3f}")
    print()
    print(f"  {'regime':<24} | {'|dipole|':<22} | {'acl1':<22} | "
          f"{'vol_ratio':<22} | {'rv_ratio':<22}")
    print(f"  {'-'*24} | {'-'*22} | {'-'*22} | {'-'*22} | {'-'*22}")
    for regime in sorted(feats_by_regime, key=lambda r: -len(feats_by_regime[r])):
        items = feats_by_regime[regime]
        dips = [abs(f.mean_dipole) for _, _, f in items]
        acls = [f.dipole_autocorr_lag1 for _, _, f in items]
        vrs = [f.chunk_total_volume / max(base.chunk_volume, 1e-9) for _, _, f in items]
        rvs = [f.realized_vol / max(base.rv, 1e-9) for _, _, f in items]
        print(f"  {regime:<24} | {fmt_stat(dips):<22} | {fmt_stat(acls):<22} | "
              f"{fmt_stat(vrs, '{:.2f}'):<22} | {fmt_stat(rvs, '{:.2f}'):<22}")

    # Spotlight HERD chunks individually with the rule trace
    herd_items = [it for r, items in feats_by_regime.items() if "HERD" in r for it in items]
    if herd_items:
        print(f"\n  -- HERD detail ({len(herd_items)} chunk(s)) --")
        for c, r, f in herd_items:
            ts0 = datetime.fromtimestamp(c.bars[0].ts, tz=timezone.utc) \
                .strftime("%Y-%m-%d %H:%M")
            vr = f.chunk_total_volume / max(base.chunk_volume, 1e-9)
            rv = f.realized_vol / max(base.rv, 1e-9)
            print(f"    {ts0}  {r.regime.value:<11}  bars={len(c.bars):>3}  "
                  f"|dipole|={abs(f.mean_dipole):.3f}  vol_ratio={vr:.2f}x  "
                  f"rv_ratio={rv:.2f}x  notes={r.notes}")
    else:
        print(f"\n  -- HERD detail: NONE --")
        # Show borderline candidates: high rv_ratio chunks that didn't make HERD
        print("    Borderline candidates (rv_ratio > 1.0):")
        for regime, items in feats_by_regime.items():
            for c, r, f in items:
                rv = f.realized_vol / max(base.rv, 1e-9)
                vr = f.chunk_total_volume / max(base.chunk_volume, 1e-9)
                if rv > 1.0:
                    ts0 = datetime.fromtimestamp(c.bars[0].ts, tz=timezone.utc) \
                        .strftime("%H:%M")
                    fail_reason = []
                    if rv <= 1.8:
                        fail_reason.append(f"rv_ratio={rv:.2f} (<1.8)")
                    if vr <= 1.5:
                        fail_reason.append(f"vol_ratio={vr:.2f} (<1.5)")
                    if abs(f.mean_dipole) <= 0.1:
                        fail_reason.append(f"|dipole|={abs(f.mean_dipole):.2f} (<0.1)")
                    print(f"      {ts0}  classified={r.regime.value:<22}  "
                          f"|dipole|={abs(f.mean_dipole):.2f}  vr={vr:.2f}  "
                          f"rv={rv:.2f}  fail: {', '.join(fail_reason) or '(none)'}")

    # WHALE detail too
    whale_items = [it for r, items in feats_by_regime.items() if "WHALE" in r for it in items]
    if whale_items:
        print(f"\n  -- WHALE detail ({len(whale_items)} chunk(s)) --")
        for c, r, f in whale_items[:6]:
            ts0 = datetime.fromtimestamp(c.bars[0].ts, tz=timezone.utc) \
                .strftime("%Y-%m-%d %H:%M")
            vr = f.chunk_total_volume / max(base.chunk_volume, 1e-9)
            kyle_r = f.kyle_proxy / max(base.kyle, 1e-9)
            print(f"    {ts0}  {r.regime.value:<11}  bars={len(c.bars):>3}  "
                  f"dipole={f.mean_dipole:+.3f}  acl1={f.dipole_autocorr_lag1:+.2f}  "
                  f"vol_ratio={vr:.2f}x  kyle_ratio={kyle_r:.2f}x")
        if len(whale_items) > 6:
            print(f"    ... ({len(whale_items) - 6} more)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asset", type=str, required=True)
    p.add_argument("--cb-bins", type=str, required=True)
    p.add_argument("--kr-bins", type=str, required=True)
    args = p.parse_args()
    audit_venue(f"CB-{args.asset}", args.cb_bins)
    audit_venue(f"KR-{args.asset}", args.kr_bins)


if __name__ == "__main__":
    main()
