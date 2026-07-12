"""
kalshi_score.py — settlement + scoring harness for Kalshi contracts (S78 Option A).

The engine that answers "does a forecast beat the market". For any laddered contract
(weather high-temp, WTI, natural gas, electricity) it:

  1. fetches the REALIZED settlement (ground truth) from the Kalshi API — each settled
     market exposes result=yes/no, floor/cap strike, and expiration_value (the exact number);
  2. builds the MARKET-IMPLIED distribution over the strike ladder (from live bins or the
     settled markets' final prices) — the crowd's forecast;
  3. scores ANY forecast distribution vs (a) the realized outcome and (b) the market
     baseline, via Brier score and log-loss. Edge = the forecast beats the market AND is right.

This is forecast-agnostic: the OD-weather forecaster (and climatology / persistence
baselines) plug in as a distribution or a (value, sigma) point estimate. It is the scoreboard
the whole weather-via-OD thesis is measured on — edge on the OUTCOME, not the microstructure.

Ladder types handled:
  * PARTITION ladder (weather: [<=81][82-83]...[90+]) -> mids ARE P(bucket); normalize.
  * CUMULATIVE ladder (energy: all "Above $X") -> P(bucket) = mid_i - mid_{i+1} (difference).
Auto-detected from floor/cap structure.

CLI:
  python research/kalshi/kalshi_score.py --series KXHIGHNY --lookback-days 6
      -> market self-calibration baseline (market implied vs realized) — sanity check.
  python research/kalshi/kalshi_score.py --series KXHIGHNY --lookback-days 6 \
      --forecast forecasts.json
      -> scores an external forecast vs realized AND vs the market baseline.
      forecasts.json: {"<event_ticker or YYYY-MM-DD>": {"value": 84.0, "sigma": 2.0}}
                   or {"<event>": {"82-83": 0.4, "84-85": 0.35, ...}}  (explicit bucket dist)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kalshi_collector import RateLimitedClient, _cents, _f  # noqa: E402

INF = float("inf")


# --- ladder geometry ------------------------------------------------------------------------
def bucket_range(m: dict) -> tuple[float, float]:
    """(lo, hi) numeric range a market covers, from floor/cap strike. Open-ended -> +-inf."""
    lo = _f(m.get("floor_strike"))
    hi = _f(m.get("cap_strike"))
    return (lo if lo is not None else -INF, hi if hi is not None else INF)


def bucket_key(lo: float, hi: float) -> str:
    if lo == -INF:
        return f"<={hi:g}"
    if hi == INF:
        return f">={lo:g}"
    return f"{lo:g}-{hi:g}"


def bucket_mid_value(lo: float, hi: float, span_for_open: float = 2.0) -> float:
    """Representative numeric value for a bucket (for realized-value / point forecasts)."""
    if lo == -INF:
        return hi - span_for_open
    if hi == INF:
        return lo + span_for_open
    return 0.5 * (lo + hi)


def ladder_distribution(entries: list[dict]) -> dict[str, dict[str, Any]]:
    """entries: [{lo, hi, mid_cents}]. -> {bucket_key: {lo, hi, prob}} summing to 1.
    Auto-detects partition vs cumulative ladders."""
    ents = [e for e in entries if e.get("mid_cents") is not None]
    if not ents:
        return {}
    caps = [e["hi"] for e in ents]
    floors = [e["lo"] for e in ents]
    n_open_hi = sum(1 for c in caps if c == INF)
    n_open_lo = sum(1 for f in floors if f == -INF)
    probs: dict[str, dict[str, Any]] = {}

    # CUMULATIVE-ABOVE: (nearly) every market is "Above X" (cap=inf) -> mids are P(>=lo).
    if n_open_hi >= len(ents) - 1 and n_open_hi >= 2:
        s = sorted(ents, key=lambda e: e["lo"])          # ascending threshold
        for i, e in enumerate(s):
            nxt = s[i + 1]["mid_cents"] / 100.0 if i + 1 < len(s) else 0.0
            p = max(0.0, e["mid_cents"] / 100.0 - nxt)
            hi = s[i + 1]["lo"] if i + 1 < len(s) else INF
            probs[bucket_key(e["lo"], hi)] = {"lo": e["lo"], "hi": hi, "prob": p}
    # CUMULATIVE-BELOW: every market "Below X" (floor=-inf) -> mids are P(<=hi).
    elif n_open_lo >= len(ents) - 1 and n_open_lo >= 2:
        s = sorted(ents, key=lambda e: e["hi"])
        for i, e in enumerate(s):
            prv = s[i - 1]["mid_cents"] / 100.0 if i > 0 else 0.0
            p = max(0.0, e["mid_cents"] / 100.0 - prv)
            lo = s[i - 1]["hi"] if i > 0 else -INF
            probs[bucket_key(lo, e["hi"])] = {"lo": lo, "hi": e["hi"], "prob": p}
    # PARTITION ladder (weather): mids are P(bucket) directly.
    else:
        for e in ents:
            probs[bucket_key(e["lo"], e["hi"])] = {
                "lo": e["lo"], "hi": e["hi"], "prob": max(0.0, e["mid_cents"] / 100.0)}

    total = sum(v["prob"] for v in probs.values())
    if total > 0:
        for v in probs.values():
            v["prob"] /= total
    return probs


def value_to_bucket(value: float, dist: dict[str, dict[str, Any]]) -> Optional[str]:
    for k, v in dist.items():
        if v["lo"] <= value < v["hi"] or (v["hi"] == INF and value >= v["lo"]):
            return k
    return None


# --- scoring --------------------------------------------------------------------------------
def brier(dist: dict[str, dict[str, Any]], winner: str) -> float:
    """Multi-class Brier: sum_k (p_k - [k==winner])^2."""
    return sum((v["prob"] - (1.0 if k == winner else 0.0)) ** 2 for k, v in dist.items())


def log_loss(dist: dict[str, dict[str, Any]], winner: str, eps: float = 1e-4) -> float:
    p = dist.get(winner, {}).get("prob", 0.0)
    return -math.log(max(p, eps))


def gaussian_over_buckets(mu: float, sigma: float,
                          template: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Turn a point forecast (mu, sigma) into a bucket distribution over the ladder buckets."""
    sigma = max(sigma, 1e-6)
    def cdf(x: float) -> float:
        if x == INF:
            return 1.0
        if x == -INF:
            return 0.0
        return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))
    out = {}
    for k, v in template.items():
        out[k] = {"lo": v["lo"], "hi": v["hi"], "prob": max(0.0, cdf(v["hi"]) - cdf(v["lo"]))}
    tot = sum(x["prob"] for x in out.values()) or 1.0
    for x in out.values():
        x["prob"] /= tot
    return out


# --- settlement (ground truth) --------------------------------------------------------------
def fetch_settled_events(client: RateLimitedClient, series: str,
                         lookback_days: float = 7.0) -> list[dict]:
    """Group settled markets by event -> realized winner bucket + expiration_value."""
    markets: list[dict] = []
    cursor = None
    while True:
        params = {"series_ticker": series, "status": "settled", "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = client.get("/markets", params)
        if not d:
            break
        markets.extend(d.get("markets", []))
        cursor = d.get("cursor")
        if not cursor or len(markets) >= 1000:
            break

    by_event: dict[str, list[dict]] = defaultdict(list)
    for m in markets:
        by_event[m.get("event_ticker") or m.get("ticker")].append(m)

    events = []
    for ev, ms in by_event.items():
        winner = next((m for m in ms if str(m.get("result")).lower() == "yes"), None)
        if not winner:
            continue
        lo, hi = bucket_range(winner)
        exp_val = _f(winner.get("expiration_value"))
        realized = exp_val if exp_val is not None else bucket_mid_value(lo, hi)
        entries = []
        for m in ms:
            b_lo, b_hi = bucket_range(m)
            entries.append({"lo": b_lo, "hi": b_hi,
                            "mid_cents": _cents(m.get("last_price_dollars")),
                            "ticker": m.get("ticker")})
        events.append({
            "event": ev,
            "close_time": winner.get("close_time"),
            "winner_ticker": winner.get("ticker"),
            "winner_bucket": bucket_key(lo, hi),
            "realized_value": realized,
            "entries": entries,
        })
    events.sort(key=lambda e: e.get("close_time") or "")
    return events


# --- driver ---------------------------------------------------------------------------------
def implied_from_bins(series: str, event: str, close_time: Optional[str],
                      lead_minutes: float, bins_dir: str) -> list[dict]:
    """Market ladder entries from accrued bins at ~(close_time - lead_minutes) — the proper,
    non-post-hoc market FORECAST at a lead time. Empty if no bins cover this event yet."""
    path = os.path.join(bins_dir, f"{series}_bins.jsonl")
    if not close_time or not os.path.exists(path):
        return []
    from datetime import datetime, timezone
    ct = datetime.fromisoformat(close_time.replace("Z", "+00:00")).timestamp()
    target = ct - lead_minutes * 60.0
    # nearest snapshot per market of this event, at/just before target
    best: dict[str, tuple[float, dict]] = {}
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("event") != event or r.get("mid") is None or r.get("ts") is None:
                continue
            dt = abs(float(r["ts"]) - target)
            tkr = r.get("ticker")
            if tkr not in best or dt < best[tkr][0]:
                best[tkr] = (dt, r)
    entries = []
    for _dt, r in best.values():
        lo = _f(r.get("floor_strike")); hi = _f(r.get("cap_strike"))
        entries.append({"lo": lo if lo is not None else -INF,
                        "hi": hi if hi is not None else INF,
                        "mid_cents": r.get("mid"), "ticker": r.get("ticker")})
    return entries


_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def _forecast_date_keys(event: dict) -> list[str]:
    """Date strings a forecast may be keyed by: the date embedded in the event ticker
    (the FORECAST day, e.g. KXHIGHNY-26JUL05 -> 2026-07-05) and the close_time date.
    Weather events close ~05:00 UTC next day, so these differ by one — accept both."""
    keys: list[str] = []
    import re
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event.get("event", ""))
    if m and m.group(2) in _MONTHS:
        yy, mon, dd = int(m.group(1)), _MONTHS[m.group(2)], int(m.group(3))
        keys.append(f"20{yy:02d}-{mon:02d}-{dd:02d}")
    if event.get("close_time"):
        keys.append(event["close_time"][:10])
    return keys


def score_event(event: dict, forecast: Optional[dict],
                bins_entries: Optional[list[dict]] = None) -> Optional[dict]:
    """Market-implied vs realized, and optionally a forecast. Uses lead-time bins entries for
    the market distribution when provided (proper baseline); else settled last-price (post-hoc)."""
    market_dist = ladder_distribution(bins_entries if bins_entries else event["entries"])
    if not market_dist:
        return None
    winner = event["winner_bucket"]
    if winner not in market_dist:                       # realized bucket must be scorable
        winner = value_to_bucket(event["realized_value"], market_dist) or winner
    if winner not in market_dist:
        return None
    row = {
        "event": event["event"],
        "close_time": event["close_time"],
        "realized_value": event["realized_value"],
        "winner_bucket": winner,
        "market_implied_p_winner": round(market_dist[winner]["prob"], 4),
        "market_brier": round(brier(market_dist, winner), 4),
        "market_logloss": round(log_loss(market_dist, winner), 4),
        "n_buckets": len(market_dist),
    }
    if forecast is not None:
        if "value" in forecast:
            fdist = gaussian_over_buckets(float(forecast["value"]),
                                          float(forecast.get("sigma", 2.0)), market_dist)
        else:                                            # explicit bucket->prob dist
            fdist = {k: {"lo": v["lo"], "hi": v["hi"],
                         "prob": float(forecast.get(k, 0.0))} for k, v in market_dist.items()}
            tot = sum(x["prob"] for x in fdist.values()) or 1.0
            for x in fdist.values():
                x["prob"] /= tot
        row.update({
            "forecast_p_winner": round(fdist.get(winner, {}).get("prob", 0.0), 4),
            "forecast_brier": round(brier(fdist, winner), 4),
            "forecast_logloss": round(log_loss(fdist, winner), 4),
            "brier_edge_vs_market": round(row["market_brier"] - brier(fdist, winner), 4),
        })
    return row


def main() -> None:
    p = argparse.ArgumentParser(description="Kalshi settlement + forecast scoring harness")
    p.add_argument("--series", required=True, help="e.g. KXHIGHNY, KXWTI, KXPOWERKWH")
    p.add_argument("--lookback-days", type=float, default=7.0)
    p.add_argument("--forecast", default="", help="JSON: {event_or_date: {value,sigma} | {bucket:prob}}")
    p.add_argument("--bins-dir", default="data/kalshi",
                   help="use accrued bins for the market baseline at --lead-minutes (proper, non-post-hoc)")
    p.add_argument("--lead-minutes", type=float, default=60.0,
                   help="how far before close to read the market forecast from bins")
    p.add_argument("--out", default="", help="optional JSON output path")
    args = p.parse_args()

    client = RateLimitedClient()
    events = fetch_settled_events(client, args.series, args.lookback_days)
    forecasts = json.load(open(args.forecast)) if args.forecast else {}

    rows = []
    n_bins_baseline = 0
    for ev in events:
        fc = forecasts.get(ev["event"])                 # exact event ticker (unambiguous)
        for key in _forecast_date_keys(ev):             # or any date form (ticker date / close date)
            if fc is not None:
                break
            fc = forecasts.get(key)
        bins_entries = implied_from_bins(args.series, ev["event"], ev["close_time"],
                                         args.lead_minutes, args.bins_dir)
        if bins_entries:
            n_bins_baseline += 1
        r = score_event(ev, fc, bins_entries)
        if r:
            r["market_source"] = "bins@lead" if bins_entries else "settled_last_price(post-hoc)"
            rows.append(r)
    if n_bins_baseline:
        print(f"[score] market baseline from lead-time bins on {n_bins_baseline}/{len(rows)} events "
              f"(rest post-hoc last-price until bins accrue)")
    else:
        print("[score] NOTE: no accrued bins cover these settled events yet -> market baseline is "
              "post-hoc settled last-price (near-certain). Real baseline activates as bins accrue.")

    scored = [r for r in rows if "forecast_brier" in r]
    print(f"[score] {args.series}: {len(rows)} settled events scored"
          + (f", {len(scored)} with a forecast" if scored else " (market baseline only)"))
    if rows:
        mkt_brier = sum(r["market_brier"] for r in rows) / len(rows)
        mkt_ll = sum(r["market_logloss"] for r in rows) / len(rows)
        print(f"[score] MARKET baseline: mean Brier={mkt_brier:.4f}  mean logloss={mkt_ll:.4f}")
    if scored:
        fc_brier = sum(r["forecast_brier"] for r in scored) / len(scored)
        edge = sum(r["brier_edge_vs_market"] for r in scored) / len(scored)
        wins = sum(1 for r in scored if r["brier_edge_vs_market"] > 0)
        print(f"[score] FORECAST: mean Brier={fc_brier:.4f}  mean edge_vs_market={edge:+.4f}  "
              f"(beats market on {wins}/{len(scored)} events)")
        print("[score] EDGE = positive edge_vs_market AND high forecast_p_winner -> tradeable.")
    for r in rows[-8:]:
        base = (f"  {r['event']:<26} realized={r['realized_value']} won={r['winner_bucket']:<8} "
                f"mkt_p={r['market_implied_p_winner']} mkt_brier={r['market_brier']}")
        if "forecast_brier" in r:
            base += f" | fc_p={r['forecast_p_winner']} edge={r['brier_edge_vs_market']:+.3f}"
        print(base)

    if args.out:
        json.dump({"series": args.series, "n": len(rows), "rows": rows}, open(args.out, "w"), indent=2)
        print(f"[score] wrote {args.out}")


if __name__ == "__main__":
    main()
