"""
eia_surprise.py — historical EIA release SURPRISE for the NYMEX-canary release windows (S86).

The event_move / lag work needs each release tagged by its SURPRISE (beat/miss x big/small) so the cells
split — but the street CONSENSUS is only archived forward (ForexFactory is current-week-only; consensus.jsonl
has no history for the Apr-Jul 2026 windows). So for HISTORICAL releases we use the established honest PROXY
(EVENT_WEIGHT_STUDY, eia_bucket_study.py): surprise = actual weekly change - 5-yr average change for the SAME
ISO calendar week (the SEASONAL expectation). This captures the seasonal surprise, NOT the exact desk number
-- legitimate for crude (seasonally driven), weaker for natgas in withdrawal season (weather-driven). Our
windows are Apr-Jul = injection / power-burn, where the seasonal proxy is more defensible. When real consensus
is present (consensus.jsonl, forward), event_move_baseline prefers it and tags surprise_source accordingly.

Actuals: EIA API v2, free DEMO_KEY (register a real key for production; DEMO is rate-limited).
  NG national working gas  : natural-gas/stor/wkly  series NW2_EPG0_SWO_R48_BCF  (Bcf level -> weekly change)
  Crude national ex-SPR    : petroleum/stoc/wstk    series WCESTUS1              (Mbbl level -> /1000 = M bbl)

Output: data/eia_surprise.json = {series: {release_iso: {actual, seasonal_exp, surprise, prev_level, unit}}}.
Convention (both): a storage BUILD bigger than seasonal = more supply = bearish (expect price DOWN). The
surprise SIGN is (actual - seasonal_exp); event_move_baseline maps sign->beat/miss and |surprise|->big/small.

Usage:
    EIA_API_KEY=DEMO_KEY python research/kalshi/eia_surprise.py --out data/eia_surprise.json
    python research/kalshi/eia_surprise.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from collections import defaultdict

EIA_BASE = "https://api.eia.gov/v2"
# (series, route, facet, scale, release_weekday) — scale converts the level to the release-native unit.
SERIES = {
    "KXNATGASD": {"route": "natural-gas/stor/wkly", "facet": "NW2_EPG0_SWO_R48_BCF",
                  "scale": 1.0, "unit": "Bcf", "rel_wd": 3},          # Thu
    "KXWTI":     {"route": "petroleum/stoc/wstk", "facet": "WCESTUS1",
                  "scale": 1 / 1000.0, "unit": "Mbbl", "rel_wd": 2},   # Wed (thousand bbl -> million bbl)
}


def fetch_levels(route: str, facet: str, scale: float, key: str, length: int = 5000):
    """[(period_date, level)] weekly national level series, ascending, deduped on period."""
    url = (f"{EIA_BASE}/{route}/data/?api_key={key}&frequency=weekly&data[0]=value"
           f"&facets[series][]={facet}&sort[0][column]=period&sort[0][direction]=desc&length={length}")
    with urllib.request.urlopen(url, timeout=60) as r:
        d = json.load(r)
    seen = {}
    for row in d.get("response", {}).get("data", []):
        try:
            per = dt.date.fromisoformat(row["period"])
            seen[per] = float(row["value"]) * scale
        except (ValueError, TypeError):
            continue
    return sorted(seen.items())


def weekly_changes(levels):
    """[(period_date, change, prev_level)] weekly net change (skip gaps that are not ~7 days)."""
    out = []
    for i in range(1, len(levels)):
        d, v = levels[i]
        dp, vp = levels[i - 1]
        if 5 <= (d - dp).days <= 10:
            out.append((d, v - vp, vp))
    return out


def seasonal_surprise(changes, yrs=5, min_prior=3):
    """surprise = change - mean(same-ISO-week change over the prior `yrs` years). Needs >=min_prior years."""
    by_week = defaultdict(list)
    for d, ch, _ in changes:
        by_week[d.isocalendar()[1]].append((d.year, ch))
    out = []
    for d, ch, prev in changes:
        wk = d.isocalendar()[1]
        prior = [c for (yr, c) in by_week[wk] if d.year - yrs <= yr < d.year]
        if len(prior) >= min_prior:
            exp = sum(prior) / len(prior)
            out.append((d, ch, exp, ch - exp, prev))
    return out


def next_weekday_after(d, wd):
    n = d + dt.timedelta(days=1)
    while n.weekday() != wd:
        n += dt.timedelta(days=1)
    return n


def build(key: str):
    out = {}
    for series, cfg in SERIES.items():
        levels = fetch_levels(cfg["route"], cfg["facet"], cfg["scale"], key)
        surp = seasonal_surprise(weekly_changes(levels))
        rel_map = {}
        for d, actual, exp, s, prev in surp:
            rel = next_weekday_after(d, cfg["rel_wd"])           # period week-ending -> report release day
            rel_map[rel.isoformat()] = {"period": d.isoformat(), "actual": round(actual, 3),
                                        "seasonal_exp": round(exp, 3), "surprise": round(s, 3),
                                        "prev_level": round(prev, 3), "unit": cfg["unit"]}
        out[series] = rel_map
        print(f"[eia] {series}: {len(levels)} levels -> {len(surp)} surprises "
              f"({min(rel_map) if rel_map else '-'}..{max(rel_map) if rel_map else '-'})")
    return out


def selftest():
    """Unit-check the change/seasonal math on a constructed level series (NOT market data)."""
    ok = True
    # 5 years of the same ISO week: level rises by [10,10,10,10] then a +40 week -> surprise +30 vs 10-avg.
    base = dt.date(2020, 7, 3)
    levels = []
    lvl = 1000.0
    for yr in range(6):
        d = base.replace(year=2020 + yr)
        prev = d - dt.timedelta(days=7)
        step = 10.0 if yr < 5 else 40.0
        levels += [(prev, lvl), (d, lvl + step)]
        lvl += step + 5
    ch = weekly_changes(sorted(levels))
    surp = seasonal_surprise(ch, yrs=5, min_prior=3)
    last = [x for x in surp if x[0].year == 2025]
    if not last or abs(last[0][3] - 30.0) > 1e-6:
        print(f"  FAIL seasonal surprise: {last and last[0]}  (expected +30)"); ok = False
    else:
        print(f"  ok  seasonal surprise = {last[0][3]:+.1f} (actual {last[0][1]:+.0f} vs exp {last[0][2]:+.0f})")
    if next_weekday_after(dt.date(2026, 7, 3), 3) != dt.date(2026, 7, 9):
        print("  FAIL release-day map (Fri period -> Thu release)"); ok = False
    else:
        print("  ok  release-day map: 2026-07-03 (Fri, week-ending) -> 2026-07-09 (Thu release)")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return ok


def main():
    ap = argparse.ArgumentParser(description="Historical EIA release surprise (seasonal-proxy) for the canary")
    ap.add_argument("--out", default="data/eia_surprise.json")
    ap.add_argument("--key", default=os.environ.get("EIA_API_KEY", "DEMO_KEY"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        sys.exit(0 if selftest() else 1)
    out = build(args.key)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=2)
    print(f"[eia] wrote {args.out}")


if __name__ == "__main__":
    main()
