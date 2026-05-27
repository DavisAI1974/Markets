"""
dipole_state_forward_returns.py

Replays a market-only dipole proxy over BTC Bybit 1-second bins and produces
the empirical state -> forward-return distribution table. This is the
calibration input the quote-service spread function needs to replace the
placeholder MVP adverse-selection constant.

V1 scope (intentional):
  - Bybit only, BTC only, two days of data (all that's durable in
    live_data_history at the moment).
  - Market-only dipole proxy. News / on-chain / strategy-family channels
    are not in this dataset; full DipoleCoupling.coupling_state replay
    needs status snapshots that aren't in the bin JSONL.
  - States are derived from empirical quintiles of the dipole proxy
    magnitude, NOT hardcoded thresholds. No invented numbers.

Output: _dipole_state_forward_returns_out/summary.json + printed table.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev

MARKETS_ROOT = Path(r"E:\Markets")
HISTORY_ROOT = MARKETS_ROOT / "live_data_history"
DEFAULT_OUT = MARKETS_ROOT / "_dipole_state_forward_returns_out"

# Quote-validity-relevant horizons (seconds).
FORWARD_HORIZONS_S = [1, 5, 15, 30, 60, 300]

# Rolling-window lengths (seconds) for feature computation.
VOL_WINDOW_S = 30      # realized vol of mid log-returns
IMB_WINDOW_S = 30      # cumulative volume imbalance
PERSIST_WINDOW_S = 60  # sign-persistence window

# Number of empirical states from dipole-magnitude quintiles.
N_STATES = 5


@dataclass
class Bin:
    ts: float
    mid: float
    spread_bps: float        # (ask - bid) / mid * 10000, nan if not quotable
    buy: float
    sell: float
    n_trades: int


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------

def load_bins(asset: str, venue: str, dates: list[str]) -> list[Bin]:
    stem = f"{asset.lower()}_{'bybit_perp' if venue.lower() == 'bybit' else venue.lower()}_bins.jsonl"
    out: list[Bin] = []
    last_mid: float | None = None
    for d in dates:
        p = HISTORY_ROOT / d / stem
        if not p.exists():
            continue
        with p.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    b = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = float(b.get("ts") or 0.0)
                if ts <= 0:
                    continue
                mid_raw = b.get("mid")
                try:
                    mid_val = float(mid_raw) if mid_raw is not None else 0.0
                except (TypeError, ValueError):
                    mid_val = 0.0
                if mid_val <= 0:
                    # Carry forward last good mid through inactive bins.
                    if last_mid is None:
                        continue
                    mid_val = last_mid
                last_mid = mid_val

                ask = float(b.get("ask") or 0.0)
                bid = float(b.get("bid") or 0.0)
                if ask > 0 and bid > 0 and ask >= bid:
                    spread_bps = (ask - bid) / mid_val * 10000.0
                else:
                    spread_bps = float("nan")

                out.append(Bin(
                    ts=ts,
                    mid=mid_val,
                    spread_bps=spread_bps,
                    buy=float(b.get("buy") or 0.0),
                    sell=float(b.get("sell") or 0.0),
                    n_trades=int(b.get("n_trades") or 0),
                ))
    out.sort(key=lambda x: x.ts)
    return out


# ----------------------------------------------------------------------------
# Feature engineering (no numpy dep — keep it portable & auditable)
# ----------------------------------------------------------------------------

def compute_log_returns(bins: list[Bin]) -> list[float]:
    """1-bin log-returns from mid. r[0] = nan since no prior."""
    r = [float("nan")]
    for i in range(1, len(bins)):
        a, b = bins[i - 1].mid, bins[i].mid
        if a > 0 and b > 0:
            r.append(math.log(b / a))
        else:
            r.append(float("nan"))
    return r


def rolling_realized_vol(returns: list[float], window: int) -> list[float]:
    """Std of returns over trailing window (excluding the bin itself).
    Output[i] uses returns[i-window+1 : i+1]."""
    out: list[float] = [float("nan")] * len(returns)
    if len(returns) < window:
        return out
    for i in range(window - 1, len(returns)):
        seg = [x for x in returns[i - window + 1: i + 1] if not math.isnan(x)]
        if len(seg) >= max(5, window // 3):
            mu = mean(seg)
            var = sum((x - mu) ** 2 for x in seg) / max(1, len(seg) - 1)
            out[i] = math.sqrt(var)
    return out


def rolling_imbalance(bins: list[Bin], window: int) -> list[float]:
    """Sum(buy - sell) / Sum(buy + sell) over trailing window. Bounded [-1, 1]."""
    out: list[float] = [float("nan")] * len(bins)
    if len(bins) < window:
        return out
    csum_diff = 0.0
    csum_abs = 0.0
    diffs = [b.buy - b.sell for b in bins]
    absvs = [b.buy + b.sell for b in bins]
    # Prime first window
    for i in range(window):
        csum_diff += diffs[i]
        csum_abs += absvs[i]
    if csum_abs > 0:
        out[window - 1] = csum_diff / csum_abs
    for i in range(window, len(bins)):
        csum_diff += diffs[i] - diffs[i - window]
        csum_abs += absvs[i] - absvs[i - window]
        if csum_abs > 0:
            out[i] = csum_diff / csum_abs
    return out


def rolling_sign_persistence(returns: list[float], window: int) -> list[float]:
    """Fraction of same-sign returns in trailing window, signed by majority side.
    Result in [-1, 1]: 0.8 means 80% same direction (positive). 0 means balanced."""
    out: list[float] = [float("nan")] * len(returns)
    for i in range(window - 1, len(returns)):
        pos = neg = 0
        for x in returns[i - window + 1: i + 1]:
            if math.isnan(x) or x == 0:
                continue
            if x > 0:
                pos += 1
            else:
                neg += 1
        total = pos + neg
        if total >= max(5, window // 3):
            net = (pos - neg) / total
            out[i] = net
    return out


def dipole_proxy(
    imbalance: list[float],
    persistence: list[float],
) -> list[float]:
    """
    Market-only dipole proxy in [-1, 1]. Sign = directional pressure side.
    Magnitude = strength × confirmation. Confirmation rises when imbalance
    sign agrees with recent return-sign persistence (volume agrees with price).
    Mirrors DipoleCoupling.market_dipole shape, not its exact production formula.
    """
    out: list[float] = [float("nan")] * len(imbalance)
    for i, (imb, per) in enumerate(zip(imbalance, persistence)):
        if math.isnan(imb) or math.isnan(per):
            continue
        # Confirmation in [0, 1] — high when imbalance and persistence agree in sign,
        # low when they disagree.
        if imb * per > 0:
            confirm = min(1.0, abs(per))
        else:
            confirm = max(0.0, 1.0 - abs(per))  # mild penalty when disagreeing
        signed = math.copysign(min(1.0, abs(imb)) * (0.5 + 0.5 * confirm), imb)
        out[i] = max(-1.0, min(1.0, signed))
    return out


# ----------------------------------------------------------------------------
# State assignment via empirical quantiles
# ----------------------------------------------------------------------------

def quantile_thresholds(values: list[float], n_bins: int) -> list[float]:
    """Empirical quantile cuts for n_bins states. Returns n_bins-1 thresholds."""
    clean = sorted(x for x in values if not math.isnan(x))
    if not clean:
        return [0.0] * (n_bins - 1)
    cuts = []
    for k in range(1, n_bins):
        q = k / n_bins
        idx = int(q * (len(clean) - 1))
        cuts.append(clean[idx])
    return cuts


def assign_state(value: float, thresholds: list[float]) -> int:
    """Returns state index 0..n_states-1 by binning value into the threshold ranges."""
    if math.isnan(value):
        return -1
    for i, t in enumerate(thresholds):
        if value <= t:
            return i
    return len(thresholds)


# ----------------------------------------------------------------------------
# Forward return computation
# ----------------------------------------------------------------------------

def build_ts_index(bins: list[Bin]) -> dict[int, int]:
    """Map int(floor(ts)) -> position in bins[]. For sub-second-gap robustness,
    we round timestamps to integer seconds."""
    out: dict[int, int] = {}
    for i, b in enumerate(bins):
        key = int(b.ts)
        # Keep the FIRST bin at a given second; subsequent same-second bins (rare)
        # are accessible by linear scan if ever needed.
        if key not in out:
            out[key] = i
    return out


def forward_log_return_bps(bins: list[Bin], ts_index: dict[int, int],
                           i: int, horizon_s: int) -> float:
    """Forward log return from bins[i] to bins at ts+horizon_s, in bps. nan if missing."""
    target_ts = int(bins[i].ts) + horizon_s
    j = ts_index.get(target_ts)
    if j is None:
        # Search forward up to a small slack for sparsity (some seconds skip)
        for delta in range(1, 4):
            j = ts_index.get(target_ts + delta)
            if j is not None:
                break
        if j is None:
            return float("nan")
    a, b = bins[i].mid, bins[j].mid
    if a <= 0 or b <= 0:
        return float("nan")
    return math.log(b / a) * 10000.0


# ----------------------------------------------------------------------------
# Summary stats
# ----------------------------------------------------------------------------

def pct(values: list[float], q: float) -> float:
    clean = sorted(x for x in values if not math.isnan(x))
    if not clean:
        return float("nan")
    idx = max(0, min(len(clean) - 1, int(q * (len(clean) - 1))))
    return clean[idx]


def summarize(values: list[float]) -> dict[str, float]:
    clean = [x for x in values if not math.isnan(x)]
    if not clean:
        return {"n": 0}
    abs_clean = [abs(x) for x in clean]
    return {
        "n": len(clean),
        "mean_bps": round(mean(clean), 3),
        "stdev_bps": round(pstdev(clean), 3) if len(clean) >= 2 else 0.0,
        "abs_mean_bps": round(mean(abs_clean), 3),
        "abs_p25_bps": round(pct(abs_clean, 0.25), 3),
        "abs_p50_bps": round(pct(abs_clean, 0.50), 3),
        "abs_p75_bps": round(pct(abs_clean, 0.75), 3),
        "abs_p95_bps": round(pct(abs_clean, 0.95), 3),
    }


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="BTC")
    ap.add_argument("--venue", default="Bybit")
    ap.add_argument("--dates", nargs="+", default=["2026-05-23", "2026-05-24"])
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading bins: asset={args.asset} venue={args.venue} dates={args.dates}")
    bins = load_bins(args.asset, args.venue, args.dates)
    print(f"  loaded {len(bins)} bins, "
          f"ts range {bins[0].ts:.0f} -> {bins[-1].ts:.0f}" if bins else "  EMPTY")
    if not bins:
        return

    print("Computing features...")
    returns = compute_log_returns(bins)
    vol = rolling_realized_vol(returns, VOL_WINDOW_S)
    imb = rolling_imbalance(bins, IMB_WINDOW_S)
    per = rolling_sign_persistence(returns, PERSIST_WINDOW_S)
    dipole = dipole_proxy(imb, per)

    print(f"  dipole proxy: "
          f"n_valid={sum(1 for x in dipole if not math.isnan(x))} / {len(dipole)}")

    # Bin by quintile of |dipole|.
    abs_dipole = [abs(x) if not math.isnan(x) else float("nan") for x in dipole]
    cuts = quantile_thresholds(abs_dipole, N_STATES)
    print(f"  |dipole| quintile cuts: {[round(c, 4) for c in cuts]}")

    states = [assign_state(x, cuts) for x in abs_dipole]
    state_counts = defaultdict(int)
    for s in states:
        state_counts[s] += 1
    print(f"  state counts: {dict(state_counts)}")

    print(f"Computing forward returns at horizons {FORWARD_HORIZONS_S}s...")
    ts_index = build_ts_index(bins)

    # Per-state buckets: state -> horizon -> list[forward_bps]
    bucket: dict[int, dict[int, list[float]]] = {
        s: {h: [] for h in FORWARD_HORIZONS_S} for s in range(N_STATES)
    }
    for i in range(len(bins)):
        s = states[i]
        if s < 0:
            continue
        for h in FORWARD_HORIZONS_S:
            r = forward_log_return_bps(bins, ts_index, i, h)
            if not math.isnan(r):
                bucket[s][h].append(r)

    # Quoted-spread distribution (control)
    spreads = [b.spread_bps for b in bins if not math.isnan(b.spread_bps)]
    spread_summary = {
        "n_quotable_bins": len(spreads),
        "mean_quoted_spread_bps": round(mean(spreads), 4) if spreads else float("nan"),
        "p25_quoted_spread_bps": round(pct(spreads, 0.25), 4),
        "p50_quoted_spread_bps": round(pct(spreads, 0.50), 4),
        "p75_quoted_spread_bps": round(pct(spreads, 0.75), 4),
        "p95_quoted_spread_bps": round(pct(spreads, 0.95), 4),
    }

    # Realized 1-bin vol (median, p25, p75) as a baseline.
    rvol_bps = [v * 10000.0 for v in vol if not math.isnan(v)]
    vol_summary = {
        "n_valid": len(rvol_bps),
        "p25_1s_realized_vol_bps": round(pct(rvol_bps, 0.25), 4),
        "p50_1s_realized_vol_bps": round(pct(rvol_bps, 0.50), 4),
        "p75_1s_realized_vol_bps": round(pct(rvol_bps, 0.75), 4),
        "p95_1s_realized_vol_bps": round(pct(rvol_bps, 0.95), 4),
    }

    # Per-state forward-return summary
    state_summary = {}
    for s in range(N_STATES):
        lower = 0.0 if s == 0 else cuts[s - 1]
        upper = cuts[s] if s < len(cuts) else 1.0
        state_summary[f"state_{s}"] = {
            "abs_dipole_band": [round(lower, 4), round(upper, 4)],
            "count_bins_in_state": state_counts[s],
            "forward_return_by_horizon_s": {
                str(h): summarize(bucket[s][h]) for h in FORWARD_HORIZONS_S
            },
        }

    out = {
        "config": {
            "asset": args.asset,
            "venue": args.venue,
            "dates": args.dates,
            "vol_window_s": VOL_WINDOW_S,
            "imb_window_s": IMB_WINDOW_S,
            "persist_window_s": PERSIST_WINDOW_S,
            "n_states": N_STATES,
            "forward_horizons_s": FORWARD_HORIZONS_S,
        },
        "sample": {
            "n_bins_total": len(bins),
            "ts_start": bins[0].ts,
            "ts_end": bins[-1].ts,
        },
        "control_quoted_spread": spread_summary,
        "control_1s_realized_vol": vol_summary,
        "state_summary": state_summary,
        "caveats": [
            "Sample is 2 days. Numbers will move with more data.",
            "Market-only dipole proxy: news/onchain/family channels not included.",
            "Forward returns are signed by market move; for MM adverse-selection "
            "interpretation, use abs_mean_bps as the lower bound on half-spread.",
            "Quintile cuts on |dipole| are empirical to this 2-day sample; "
            "recompute when you have a longer window.",
        ],
    }

    summary_path = out_dir / "summary.json"
    with summary_path.open("w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {summary_path}")

    # Print human-readable table
    print("\n=== STATE -> FORWARD RETURN (bps) ===")
    print(f"  Control: quoted spread mean={spread_summary['mean_quoted_spread_bps']} bps, "
          f"p50={spread_summary['p50_quoted_spread_bps']} bps")
    print(f"  Control: 1s realized vol p50={vol_summary['p50_1s_realized_vol_bps']} bps")
    print()
    header = f"{'state':<8}{'|dipole| band':<20}{'n':<8}" + "".join(
        f"{h}s |mean|".rjust(12) for h in FORWARD_HORIZONS_S
    )
    print(header)
    print("-" * len(header))
    for s in range(N_STATES):
        ss = state_summary[f"state_{s}"]
        band = f"[{ss['abs_dipole_band'][0]:.3f},{ss['abs_dipole_band'][1]:.3f}]"
        row = f"{s:<8}{band:<20}{ss['count_bins_in_state']:<8}"
        for h in FORWARD_HORIZONS_S:
            d = ss["forward_return_by_horizon_s"][str(h)]
            v = d.get("abs_mean_bps", float("nan"))
            row += f"{v:>12.3f}" if v == v else f"{'nan':>12}"
        print(row)
    print()
    print("Interpretation: abs_mean_bps at each horizon is the empirical mean")
    print("|forward move| during that horizon, conditional on dipole state.")
    print("That's the LOWER BOUND on half-spread for a quote with that validity")
    print("window, before adding hedge-leg cost and safety pad.")


if __name__ == "__main__":
    main()
