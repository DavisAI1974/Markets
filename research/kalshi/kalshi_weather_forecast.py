"""
kalshi_weather_forecast.py — wire the OD-weather storage-NUMBER forecaster into the kalshi_score
scoreboard (S80 queued item).

WHAT / WHY (from the S79 event-weight study, load-bearing):
  * weather -> STORAGE NUMBER is a STRONG link  (LINK A: pooled R^2=0.73 on the surprise, winter
    R^2=0.85, surprise-sign hit 0.91). So an OD-weather degree-day forecaster IS an EIA-storage-print
    forecaster -> a real, NON-ARBED edge on any contract that settles ON the storage NUMBER.
  * weather/surprise -> PRICE is ~NULL       (LINK B: winter dir-hit 0.52 — sell-the-news; the number
    is so weather-predictable it is priced by release). So this does NOT claim a price edge; KXNATGASD
    strikes are PRICES (e.g. $3.145), so scoring THIS forecaster against KXNATGASD is the null LINK B.
    The storage-NUMBER edge needs a storage-number-settled ladder (awaiting Kalshi coverage); meanwhile
    the forecaster is validated DIRECTLY against realized EIA numbers here.

HONEST SCOPE (unchanged): OD-weather's defensible first claim is to BEAT climatology + persistence on
the settlement variable — NOT to out-forecast ECMWF. This module measures climatology + persistence on
REAL EIA history (walk-forward, no look-ahead) as the baselines, exposes the OD-weather LINK-A anomaly
adjustment as the plug (live once the CPC gas-weighted degree-day anomaly feed is wired), and scores
every forecaster through the ACTUAL kalshi_score primitives (gaussian_over_buckets + brier) so the wire
into the scoreboard is literal. Emits forecasts.json in the exact `kalshi_score --forecast` schema.

Data: EIA v2 API (free; DEMO_KEY works) — Weekly Lower-48 Working Gas (duoarea R48, process SWO). Zero
synthetic data.

Usage:
    python research/kalshi/kalshi_weather_forecast.py                 # backtest baselines + emit forward
    python research/kalshi/kalshi_weather_forecast.py --emit data/kalshi/weather_forecasts.json
    # then score against a storage-number ladder when one exists:
    #   python research/kalshi/kalshi_score.py --series <STORAGE_SERIES> --forecast data/kalshi/weather_forecasts.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                       # kalshi_score lives alongside
from kalshi_score import gaussian_over_buckets, brier, value_to_bucket, bucket_key  # noqa: E402

EIA = ("https://api.eia.gov/v2/natural-gas/stor/wkly/data/?api_key={key}"
       "&frequency=weekly&data[0]=value&facets[duoarea][]=R48&facets[process][]=SWO"
       "&sort[0][column]=period&sort[0][direction]=asc&length=5000")

# committed LINK-A weather->storage-surprise skill, per discovered regime (natgas_weather_results.json).
# R2 on the SURPRISE (actual - seasonal); used to (a) size the OD-weather sigma reduction over
# climatology and (b) apply the anomaly adjustment when a CPC anomaly is supplied.
LINK_A_R2 = {"winter-withdrawal": 0.854, "summer-withdrawal": 0.295,
             "spring-injection": 0.638, "fall-injection": 0.279, "ALL": 0.731}


# ---- data ---------------------------------------------------------------------------------
def fetch_eia_changes(api_key: str = "DEMO_KEY") -> list[dict]:
    """Weekly Lower-48 working-gas LEVEL -> weekly CHANGE series (the number the print settles on)."""
    req = urllib.request.Request(EIA.format(key=api_key), headers={"User-Agent": "Mozilla/5.0"})
    rows = json.loads(urllib.request.urlopen(req, timeout=30).read())["response"]["data"]
    lv = sorted({r["period"]: float(r["value"]) for r in rows}.items())
    out = []
    for i in range(1, len(lv)):
        (p0, v0), (p1, v1) = lv[i - 1], lv[i]
        d = date.fromisoformat(p1)
        out.append({"week_ending": p1, "level": v1, "change": v1 - v0,
                    "iso_week": d.isocalendar()[1], "year": d.year, "date": d})
    return out


def _regime(d: date) -> str:
    """Coarse map to the study's 4 regimes by month (data-discovered split ~ these months)."""
    m = d.month
    if m in (11, 12, 1, 2, 3):
        return "winter-withdrawal"
    if m in (6, 7, 8):
        return "summer-withdrawal"
    if m in (4, 5):
        return "spring-injection"
    return "fall-injection"


# ---- forecasters (walk-forward; only data strictly before the target week) ------------------
def climatology(changes: list[dict], i: int, lookback_yrs: int = 5) -> tuple[float, float] | None:
    """5yr same-ISO-week mean change + its std (the study's seasonal 'consensus proxy' baseline)."""
    tgt = changes[i]
    prior = [c["change"] for c in changes[:i]
             if c["iso_week"] == tgt["iso_week"] and tgt["year"] - lookback_yrs <= c["year"] < tgt["year"]]
    if len(prior) < 3:
        return None
    mu = sum(prior) / len(prior)
    sd = (sum((x - mu) ** 2 for x in prior) / (len(prior) - 1)) ** 0.5 if len(prior) > 1 else 8.0
    return mu, max(sd, 3.0)


def persistence(changes: list[dict], i: int, roll: int = 8) -> tuple[float, float] | None:
    """Last realized change; sigma from the recent rolling residual (naive baseline)."""
    if i < 1:
        return None
    mu = changes[i - 1]["change"]
    window = [c["change"] for c in changes[max(0, i - roll):i]]
    if len(window) > 1:
        m = sum(window) / len(window)
        sd = (sum((x - m) ** 2 for x in window) / (len(window) - 1)) ** 0.5
    else:
        sd = 10.0
    return mu, max(sd, 3.0)


def od_weather(changes: list[dict], i: int, weather_anom: float | None = None) -> tuple[float, float] | None:
    """Climatology + LINK-A weather-anomaly adjustment.

    OD-weather predicts the SURPRISE (deviation from seasonal) from the gas-weighted degree-day
    anomaly. Forecast = climatology_mu + beta * weather_anom; sigma shrinks by sqrt(1 - R2_regime)
    (the LINK-A variance explained). With no anomaly supplied it FALLS BACK to climatology (so the
    plug is inert until the CPC feed lands) — flagged by returning the climatology sigma unshrunk.
    """
    clim = climatology(changes, i)
    if clim is None:
        return None
    cmu, csd = clim
    reg = _regime(changes[i]["date"])
    r2 = LINK_A_R2.get(reg, LINK_A_R2["ALL"])
    if weather_anom is None:
        return cmu, csd                                   # inert: == climatology (no live anomaly)
    # convention: high degree-day anomaly => more demand => bigger draw => NEGATIVE surprise
    beta = -math.sqrt(max(r2, 0.0)) * (csd / 1.0)          # scale to surprise units (std-normalized anom)
    mu = cmu + beta * weather_anom
    sd = csd * math.sqrt(max(1.0 - r2, 0.02))
    return mu, max(sd, 2.0)


FORECASTERS = {"climatology": climatology, "persistence": persistence, "od_weather": od_weather}


# ---- scoring through the kalshi_score primitives -------------------------------------------
def number_ladder(center: float, half_width: float = 60.0, step: float = 10.0) -> dict:
    """A partition ladder of storage-CHANGE buckets (BCF) — the template kalshi_score scores over."""
    lo0 = math.floor((center - half_width) / step) * step
    tmpl = {}
    x = lo0
    while x < center + half_width:
        tmpl[bucket_key(x, x + step)] = {"lo": x, "hi": x + step, "prob": 0.0}
        x += step
    # open tails so every realized value lands in a bucket
    first = min(v["lo"] for v in tmpl.values()); last = max(v["hi"] for v in tmpl.values())
    tmpl[bucket_key(-math.inf, first)] = {"lo": -math.inf, "hi": first, "prob": 0.0}
    tmpl[bucket_key(last, math.inf)] = {"lo": last, "hi": math.inf, "prob": 0.0}
    return tmpl


def backtest(changes: list[dict], start_i: int = 60) -> dict:
    """Walk-forward: each release, each forecaster -> (mu,sigma); score abs-err + kalshi_score Brier."""
    stats = {name: {"abs_err": [], "brier": [], "n": 0} for name in FORECASTERS}
    for i in range(start_i, len(changes)):
        realized = changes[i]["change"]
        tmpl = number_ladder(realized)
        winner = value_to_bucket(realized, tmpl)
        for name, fn in FORECASTERS.items():
            res = fn(changes, i)
            if res is None:
                continue
            mu, sigma = res
            dist = gaussian_over_buckets(mu, sigma, tmpl)
            stats[name]["abs_err"].append(abs(mu - realized))
            stats[name]["brier"].append(brier(dist, winner))
            stats[name]["n"] += 1
    out = {}
    for name, s in stats.items():
        if not s["abs_err"]:
            continue
        ae = s["abs_err"]; br = s["brier"]
        out[name] = {"n": s["n"],
                     "MAE_bcf": round(sum(ae) / len(ae), 2),
                     "RMSE_bcf": round((sum(x * x for x in ae) / len(ae)) ** 0.5, 2),
                     "brier": round(sum(br) / len(br), 4)}
    # projected OD-weather skill from the committed LINK-A R2 (pending live CPC anomaly)
    if "climatology" in out:
        clim_mae = out["climatology"]["MAE_bcf"]
        out["od_weather_projected"] = {
            "note": "PROJECTED from committed LINK-A R2 (natgas_weather_results.json); needs live CPC "
                    "gas-wtd degree-day anomaly to realize. MAE ~ clim_MAE * sqrt(1-R2).",
            "pooled_R2": LINK_A_R2["ALL"],
            "winter_R2": LINK_A_R2["winter-withdrawal"],
            "MAE_bcf_pooled": round(clim_mae * math.sqrt(max(1 - LINK_A_R2["ALL"], 0.02)), 2),
            "MAE_bcf_winter": round(clim_mae * math.sqrt(max(1 - LINK_A_R2["winter-withdrawal"], 0.02)), 2)}
    return out


# ---- forward forecast + kalshi_score schema emit -------------------------------------------
def next_thursday(d: date) -> date:
    return d + timedelta(days=(3 - d.weekday()) % 7 or 7)


def forward_forecast(changes: list[dict]) -> dict:
    """Forecast the NEXT weekly storage change (the print after the last observed week)."""
    i = len(changes)                                       # forecasting one step past the last row
    padded = changes + [{"iso_week": (changes[-1]["date"] + timedelta(days=7)).isocalendar()[1],
                         "year": (changes[-1]["date"] + timedelta(days=7)).year,
                         "date": changes[-1]["date"] + timedelta(days=7), "change": None}]
    fc = {}
    for name, fn in FORECASTERS.items():
        res = fn(padded, i)
        if res is not None:
            fc[name] = {"value": round(res[0], 1), "sigma": round(res[1], 1)}
    for_week_ending = changes[-1]["date"] + timedelta(days=7)
    rel = next_thursday(for_week_ending)                   # EIA releases the Thursday after the gas week
    return {"release_date": rel.isoformat(),
            "for_week_ending": for_week_ending.isoformat(),
            "forecasters": fc}


def emit_kalshi_forecasts(fwd: dict, which: str = "od_weather") -> dict:
    """kalshi_score --forecast schema: {'<YYYY-MM-DD or event>': {'value':.., 'sigma':..}}."""
    f = fwd["forecasters"].get(which) or fwd["forecasters"].get("climatology")
    return {fwd["release_date"]: {"value": f["value"], "sigma": f["sigma"],
                                  "_forecaster": which, "_units": "BCF weekly storage change",
                                  "_for_week_ending": fwd["for_week_ending"]}}


def main() -> None:
    ap = argparse.ArgumentParser(description="OD-weather storage-number forecaster -> kalshi_score bridge")
    ap.add_argument("--api-key", default=os.environ.get("EIA_API_KEY", "DEMO_KEY"))
    ap.add_argument("--emit", default=None, help="write kalshi_score forecasts.json here")
    ap.add_argument("--which", default="od_weather", choices=list(FORECASTERS),
                    help="which forecaster to emit forward (default od_weather; inert==climatology until CPC feed)")
    ap.add_argument("--start-i", type=int, default=60, help="backtest warm-up rows")
    args = ap.parse_args()

    changes = fetch_eia_changes(args.api_key)
    print(f"[eia] {len(changes)} weekly changes {changes[0]['week_ending']} .. {changes[-1]['week_ending']}")

    # recap the most recent released print (answers 'what happened this Thursday')
    last = changes[-1]
    clim = climatology(changes, len(changes) - 1)
    if clim:
        print(f"[recap] week ending {last['week_ending']}: actual change = {last['change']:+.0f} B ; "
              f"climatology {clim[0]:+.0f}+/-{clim[1]:.0f} B ; surprise vs clim = {last['change']-clim[0]:+.0f} B")

    print("\n[backtest] walk-forward vs realized EIA numbers (baselines are the honest scope):")
    bt = backtest(changes, args.start_i)
    for name in ("climatology", "persistence", "od_weather", "od_weather_projected"):
        if name in bt:
            v = bt[name]
            if name == "od_weather_projected":
                print(f"  {name:<22} pooled MAE~{v['MAE_bcf_pooled']}  winter MAE~{v['MAE_bcf_winter']}  ({v['note'][:60]}...)")
            else:
                print(f"  {name:<22} n={v['n']:<4} MAE={v['MAE_bcf']:<6} RMSE={v['RMSE_bcf']:<6} Brier={v['brier']}")

    fwd = forward_forecast(changes)
    print(f"\n[forward] release {fwd['release_date']} (week ending {fwd['for_week_ending']}):")
    for name, f in fwd["forecasters"].items():
        print(f"    {name:<14} {f['value']:+.1f} +/- {f['sigma']:.1f} B")

    if args.emit:
        os.makedirs(os.path.dirname(args.emit) or ".", exist_ok=True)
        payload = emit_kalshi_forecasts(fwd, args.which)
        json.dump(payload, open(args.emit, "w"), indent=2)
        print(f"\n[emit] {args.emit}  (kalshi_score --forecast schema; forecaster='{args.which}')")
        print("       -> score vs a storage-NUMBER ladder when Kalshi lists one; KXNATGASD is PRICE (LINK B null).")


if __name__ == "__main__":
    main()
