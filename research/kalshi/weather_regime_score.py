"""
weather_regime_score.py — per-REGIME weather scoreboard (S84).

Scoreboard-side ONLY. The weather FORECASTER is Greg's spec (HANDS OFF); this scores the naive
baselines that define the bar to beat, PER CELL, and is a drop-in for the OD operator's
(value, sigma) when it firms up (same gaussian_over_buckets path via --forecast on kalshi_score).

What it adds over the S82 baseline table (which reported per-regime MEANS of persistence only):
  * distributions NOT means  — per-cell Brier median / IQR / max + right-bucket hit-rate (Rule 2).
  * climatology per regime   — S82 split only persistence by regime; climatology was pooled.
  * swing direction          — warming vs cooling transition kept separate (a weather cell).
  * leakage gate FIRST       — every (value,sigma) forecast is proven invariant to FUTURE days.

Baselines (both walk-forward, strictly pre-event -> pass the leakage gate trivially):
  * persistence : forecast(today) = realized(yesterday); sigma = trailing std of |day-over-day Delta|.
  * climatology : forecast(today) = trailing mean of realized highs; sigma = trailing std.

Regime is classified POST-HOC on |realized_today - realized_yesterday| purely to CHARACTERIZE the
baseline's failure mode (exactly as WEATHER_BASELINE_S82.md does) — a LIVE signal must call the
transition BEFORE the day resolves; that pre-hoc classifier is the operator's job, not this.

Ladder settlement + scoring primitives are reused verbatim from kalshi_score.py; realized highs +
ladders come from the Kalshi settlement API. Zero synthetic. Per-cell never pooled.

CLI:
  python research/kalshi/weather_regime_score.py --cities KXHIGHDEN,KXHIGHNY,KXHIGHCHI \
      --lookback-days 400 --clim-window 21 --transition-threshold 3 --out weather_regime.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from collections import defaultdict
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kalshi_collector import RateLimitedClient  # noqa: E402
from kalshi_score import (  # noqa: E402
    brier, fetch_settled_events, gaussian_over_buckets,
    ladder_distribution, value_to_bucket,
)

SIGMA_FLOOR = 1.5  # degF — do not let a trailing std collapse a Gaussian to a spike


# --- realized series -------------------------------------------------------------------------
def build_series(client: RateLimitedClient, series: str, lookback_days: float) -> list[dict]:
    """Settled events for a city, sorted by forecast date, each carrying the realized high and
    the market ladder template (bucket geometry). One clean row per calendar day."""
    evs = fetch_settled_events(client, series, lookback_days)
    rows: list[dict] = []
    seen: set[str] = set()
    for e in evs:
        ct = e.get("close_time")
        rv = e.get("realized_value")
        if not ct or rv is None:
            continue
        date = ct[:10]
        if date in seen:            # one row per day (dedupe re-listed events)
            continue
        template = ladder_distribution(e["entries"])
        if not template:
            continue
        seen.add(date)
        rows.append({"date": date, "series": series, "realized": float(rv),
                     "template": template, "winner": e["winner_bucket"]})
    rows.sort(key=lambda r: r["date"])
    return rows


# --- baselines (walk-forward) ----------------------------------------------------------------
def persistence(prior_realized: list[float]) -> Optional[tuple[float, float]]:
    if len(prior_realized) < 2:
        return None
    deltas = [abs(prior_realized[i] - prior_realized[i - 1]) for i in range(1, len(prior_realized))]
    sigma = max(st.pstdev(deltas) if len(deltas) >= 2 else deltas[-1], SIGMA_FLOOR)
    return prior_realized[-1], sigma


def climatology(prior_realized: list[float], window: int) -> Optional[tuple[float, float]]:
    w = prior_realized[-window:]
    if len(w) < 3:
        return None
    return st.mean(w), max(st.pstdev(w), SIGMA_FLOOR)


# --- regime / cell ---------------------------------------------------------------------------
def regime_of(delta: float, thr: float) -> str:
    return "transition" if abs(delta) > thr else "calm"


def swing_of(delta: float) -> str:
    return "warm" if delta > 0 else "cool"


# --- leakage gate (mandatory, Gate 0) --------------------------------------------------------
def leakage_check(rows: list[dict], clim_window: int) -> tuple[bool, int]:
    """A walk-forward baseline forecast for day i must be BYTE-INVARIANT to any realized value on
    day > i. Recompute each day's (value,sigma) on the true prefix and on a prefix with the FUTURE
    tail perturbed; assert identical. Returns (passed, n_checked)."""
    realized = [r["realized"] for r in rows]
    n = len(realized)
    checks = 0
    for i in range(2, n):
        prefix = realized[:i]
        base_p = persistence(prefix)
        base_c = climatology(prefix, clim_window)
        # perturb the FUTURE (days >= i) by +100 degF and recompute the SAME day-i forecast
        poisoned = prefix + [v + 100.0 for v in realized[i:]]
        pois_p = persistence(poisoned[:i])
        pois_c = climatology(poisoned[:i], clim_window)
        if base_p != pois_p or base_c != pois_c:
            return False, checks
        checks += 1
    return True, checks


# --- distribution readout (Rule 2: never a bare mean) ----------------------------------------
def summarize(briers: list[float], hits: list[int]) -> dict:
    b = sorted(briers)
    n = len(b)
    def q(p: float) -> float:
        if n == 1:
            return b[0]
        idx = p * (n - 1)
        lo = int(idx)
        frac = idx - lo
        return b[lo] if lo + 1 >= n else b[lo] * (1 - frac) + b[lo + 1] * frac
    return {
        "n": n,
        "brier_median": round(q(0.5), 3),
        "brier_p25": round(q(0.25), 3),
        "brier_p75": round(q(0.75), 3),
        "brier_max": round(b[-1], 3),
        "brier_mean_footnote": round(sum(b) / n, 3),
        "hit_rate": round(sum(hits) / n, 3),
    }


# --- driver ----------------------------------------------------------------------------------
def fingerprint(per_event: list[dict]) -> dict:
    """Rule 2 done right: DO NOT lead with a cell mean. Break the cell to the individual day, split
    by best-naive Brier into edge/mid/whiff, and report the WINNER FINGERPRINT of each cluster —
    tail-vs-interior bucket + swing. The mechanical structural signal the cell median blurs away."""
    days = []
    for r in per_event:
        briers = [b for b in (r.get("pers_brier"), r.get("clim_brier")) if b is not None]
        if not briers:
            continue
        best = min(briers)
        who = "clim" if r.get("clim_brier") == best else "pers"
        w = r["winner"]
        days.append({"date": r["date"], "best": best, "who": who, "swing": r["swing"],
                     "regime": r["regime"], "tail": w.startswith("<=") or w.startswith(">="),
                     "winner": w, "realized": r["realized"]})

    def fp(grp: list[dict]) -> dict:
        n = len(grp)
        if not n:
            return {"n": 0}
        return {"n": n,
                "tail_win_frac": round(sum(g["tail"] for g in grp) / n, 3),
                "warm_frac": round(sum(g["swing"] == "warm" for g in grp) / n, 3),
                "clim_best_frac": round(sum(g["who"] == "clim" for g in grp) / n, 3),
                "days": [f"{g['date'][5:]}:{g['swing'][0]}->{g['winner']}(b{g['best']:.2f})"
                         for g in sorted(grp, key=lambda z: z["best"])]}

    edge = [d for d in days if d["best"] < 0.5]
    mid = [d for d in days if 0.5 <= d["best"] <= 1.5]
    whiff = [d for d in days if d["best"] > 1.5]

    # TIME-BUCKET the fingerprint — the pooled 68-day number flattens spring-frontal -> summer-ridge
    # (different synoptic worlds). Half-month buckets show how the warm-spike room evolves. Small-n
    # by construction (the room is rare); counts reported raw, no averaging.
    def half(dstr: str) -> str:
        return dstr[:7] + ("a" if int(dstr[8:10]) <= 15 else "b")
    by_time: dict[str, dict] = {}
    for d in sorted(days, key=lambda z: z["date"]):
        b = by_time.setdefault(half(d["date"]),
                                {"n": 0, "edge_n": 0, "whiff_n": 0, "whiff_warm_n": 0})
        b["n"] += 1
        if d["best"] < 0.5:
            b["edge_n"] += 1
        if d["best"] > 1.5:
            b["whiff_n"] += 1
            if d["swing"] == "warm":
                b["whiff_warm_n"] += 1

    return {"n": len(days), "edge": fp(edge), "mid": fp(mid), "whiff": fp(whiff),
            "by_time_halfmonth": by_time}


def score_city(rows: list[dict], clim_window: int, thr: float) -> dict:
    """Per-day walk-forward baseline scoring, bucketed into cells. Returns per-cell distributions
    for persistence and climatology, plus the post-hoc market placeholder."""
    cells: dict[tuple, dict[str, list]] = defaultdict(
        lambda: {"pers_b": [], "pers_h": [], "clim_b": [], "clim_h": [], "mkt_b": []})
    per_event = []
    realized = [r["realized"] for r in rows]

    for i, r in enumerate(rows):
        if i < 2:
            continue
        prior = realized[:i]
        delta = r["realized"] - realized[i - 1]
        regime = regime_of(delta, thr)
        swing = swing_of(delta)
        tmpl = r["template"]
        winner = r["winner"] if r["winner"] in tmpl else value_to_bucket(r["realized"], tmpl)
        if winner is None:
            continue

        row = {"date": r["date"], "realized": r["realized"], "delta": round(delta, 1),
               "regime": regime, "swing": swing, "winner": winner}

        # market baseline (post-hoc settled last-price placeholder — flagged, not sized off)
        mkt_b = brier(tmpl, winner)
        row["market_brier_posthoc"] = round(mkt_b, 3)

        for name, fc in (("pers", persistence(prior)), ("clim", climatology(prior, clim_window))):
            if fc is None:
                continue
            fdist = gaussian_over_buckets(fc[0], fc[1], tmpl)
            b = brier(fdist, winner)
            hit = 1 if max(fdist, key=lambda k: fdist[k]["prob"]) == winner else 0
            row[f"{name}_value"] = round(fc[0], 1)
            row[f"{name}_sigma"] = round(fc[1], 2)
            row[f"{name}_brier"] = round(b, 3)
            row[f"{name}_hit"] = hit
            cells[(regime,)][f"{name}_b"].append(b)
            cells[(regime,)][f"{name}_h"].append(hit)
            if regime == "transition":
                cells[(regime, swing)][f"{name}_b"].append(b)
                cells[(regime, swing)][f"{name}_h"].append(hit)
        cells[(regime,)]["mkt_b"].append(mkt_b)
        per_event.append(row)

    fp = fingerprint(per_event)

    out_cells = {}
    for key, d in cells.items():
        cell_name = " x ".join(key)
        entry = {}
        if d["pers_b"]:
            entry["persistence"] = summarize(d["pers_b"], d["pers_h"])
        if d["clim_b"]:
            entry["climatology"] = summarize(d["clim_b"], d["clim_h"])
        if d["mkt_b"]:
            mb = sorted(d["mkt_b"])
            entry["market_posthoc"] = {"n": len(mb),
                                       "brier_median": round(mb[len(mb) // 2], 3)}
        out_cells[cell_name] = entry
    return {"fingerprint": fp, "cells": out_cells, "per_event": per_event}


def main() -> None:
    p = argparse.ArgumentParser(description="Per-regime weather scoreboard (naive baselines)")
    p.add_argument("--cities", default="KXHIGHDEN,KXHIGHNY,KXHIGHCHI")
    p.add_argument("--lookback-days", type=float, default=400.0)
    p.add_argument("--clim-window", type=int, default=21)
    p.add_argument("--transition-threshold", type=float, default=3.0,
                   help="|realized_today - realized_yesterday| > thr => transition (post-hoc label)")
    p.add_argument("--out", default="")
    args = p.parse_args()

    client = RateLimitedClient()
    result = {"config": {"clim_window": args.clim_window, "thr": args.transition_threshold},
              "cities": {}}

    for series in [c.strip() for c in args.cities.split(",") if c.strip()]:
        rows = build_series(client, series, args.lookback_days)
        if len(rows) < 5:
            print(f"[{series}] only {len(rows)} settled days — skipping")
            continue

        ok, n_chk = leakage_check(rows, args.clim_window)
        print(f"[{series}] LEAKAGE GATE: {'PASS' if ok else 'FAIL'} ({n_chk} days checked)")
        if not ok:
            print(f"[{series}] leakage FAILED — not scoring (a baseline saw the future).")
            continue

        scored = score_city(rows, args.clim_window, args.transition_threshold)
        result["cities"][series] = scored
        print(f"\n[{series}]  {len(rows)} settled days ({rows[0]['date']} -> {rows[-1]['date']})")

        # LEAD with the per-day fingerprint (never the cell mean) — Rule 2.
        fp = scored["fingerprint"]
        print("  PER-DAY FINGERPRINT (best-naive Brier; the edge the cell-average hides):")
        for tag, label in (("edge", "EDGE  <0.5"), ("whiff", "WHIFF >1.5")):
            g = fp[tag]
            if g["n"]:
                print(f"    {label}: n={g['n']:<3} ({g['n']/fp['n']:.0%})  "
                      f"tail-bucket-win={g['tail_win_frac']:.0%}  warm={g['warm_frac']:.0%}  "
                      f"clim-best={g['clim_best_frac']:.0%}")
        print("    -> naive is FREE on wide open-tail wins (nobody's edge), BLIND on interior "
              "warm-spike wins (the operator's room).")
        print("  BY HALF-MONTH (the pooled number flattens spring-frontal -> summer-ridge; "
              "warm-spike room = whiff_warm):")
        for period, b in sorted(fp["by_time_halfmonth"].items()):
            print(f"    {period}  n={b['n']:<3} edge={b['edge_n']:<2} whiff={b['whiff_n']:<2} "
                  f"whiff_warm(room)={b['whiff_warm_n']}")

        # cell medians kept only as the DEMOTED footnote they are (the average that misleads)
        print("  cell medians (FOOTNOTE — the averages Greg's rule says never to lead with):")
        order = ["calm", "transition", "transition x warm", "transition x cool"]
        for cell in order:
            e = scored["cells"].get(cell)
            if not e:
                continue
            ps = e.get("persistence", {}); cs = e.get("climatology", {})
            print(f"    {cell:<20} n={ps.get('n','-'):<3} pers_med={ps.get('brier_median','-')} "
                  f"clim_med={cs.get('brier_median','-')}  (mkt* {e.get('market_posthoc',{}).get('brier_median','-')})")
        print("  * market_posthoc = settled last-price placeholder, NOT the real lead-time bar "
              "(activates as KXHIGH bins accrue).")

    if args.out:
        json.dump(result, open(args.out, "w"), indent=2)
        print(f"\n[out] wrote {args.out}")


if __name__ == "__main__":
    main()
