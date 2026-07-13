# Weather forecast -> trade interface (S90)

The contract between Greg's OD temperature forecaster (HANDS OFF - its internals are Greg's spec) and our
trade/scoreboard side. This says ONLY what the forecaster should EMIT so it plugs straight into (1) the
Kalshi KXHIGH* daily-high markets and (2) the NG demand path forecaster. It does not touch how the forecast
is made. Written S90 from the `od_weather_discovery_knowledge.json` part-1 drop + the S82/S84 market notes.

## Why this exists (the two gaps the current JSON has for trading)
The part-1 finding (`regime_breakdown_2023_oos`) is a FORECAST-ACCURACY result (MAE per regime) on stations
KGJT (terrain target) + KDDC (flat control). Two changes turn it into a tradeable feed:
1. **Real market cities, not KGJT/KDDC.** KGJT/KDDC are the science contrast (terrain-vs-flat honesty), not
   Kalshi markets. Trading needs the actual KXHIGH stations. Keep a flat control station for the honesty
   check, but it is not a market.
2. **Residual DISTRIBUTIONS, not MAE.** A 2F-wide ladder bucket is priced by P(high in bucket) - that needs
   the residual's CENTER + SPREAD + TAIL per cell, not a mean absolute error. MAE cannot price a bucket.

## Emit this (per city, per forecast day, per lead)
The minimum our bridge consumes is `(value, sigma)`; the fuller (better) form adds the tail. One JSON record
per `(city, target_date, lead)`:

```
{
  "city": "KXHIGHNY",              // Kalshi series ticker (see city list below)
  "station": "KNYC",               // the official settlement station
  "target_date": "2026-01-15",     // the day whose HIGH resolves
  "issue_time": "2026-01-13T00Z",  // when the forecast was made (leakage anchor; must be < target_date open)
  "lead": "f048",                  // f048/f072/f096/f120 = Day 2..5 (+ nearer leads if produced)
  "value": 41.3,                   // OD-corrected expected high (F) = GFS + OD error correction
  "sigma": 2.6,                    // predictive SD of the high (F) FOR THIS CELL - the load-bearing new field
  "resid_quantiles": {             // OPTIONAL but preferred: OD residual distribution for this cell (F)
     "p05": -4.1, "p25": -1.6, "p50": 0.1, "p75": 1.7, "p95": 4.4
  },
  "regime": "hard_cold",           // PRE-HOC regime label (see below) - must be knowable at issue_time
  "od_deployed": true,             // true = OD is the routed method for this cell; false = route-away
  "route_to": "climo"              // when od_deployed=false: "raw" | "climo" (which method wins this cell)
}
```

- **`sigma` is the piece that unlocks pricing.** Emit it PER CELL - the whole OD result is that error shrinks
  on hard regimes (winter, 32-50F, hot), so sigma is regime-dependent, not a global constant.
- **`resid_quantiles`** lets the bridge price fat/asymmetric tails exactly (warming-spike days are skewed);
  if absent we fall back to a Gaussian from `(value, sigma)`.
- **`regime` must be PRE-HOC** - a label computable at `issue_time` (recent variance, ensemble spread, a
  front in the guidance), never `|realized - yesterday|`. Leakage-critical: our scoreboard rejects any cell
  whose assignment peeks at the outcome.
- **`od_deployed` / `route_to`** carry the routing the OD program already produces (deploy where OD wins,
  hand easy <=2F / <32F / 50-70F cells to raw/climo). We trade the routed predictor, so we need to know per
  cell which method is live.

## City list (v1 = the KXHIGH markets)
`KXHIGHNY, KXHIGHCHI, KXHIGHLAX, KXHIGHDEN, KXHIGHAUS` + `KXHIGHT*` for ATL/BOS/DAL/HOU/PHX/SATX/SFO.
Plus ONE flat/marine control station (KDDC-style) carried as an honesty check, flagged `market:false`.

## Leads
The JSON's f048-f120 (Day 2-5) is the current set. KXHIGH contracts skew nearer-term, so ALSO emit the
nearest leads the forecaster produces (f024 / same-morning if available) and CONFIRM the edge holds there -
the market edge lives at the lead the contract actually settles on, which may be tighter than Day 2-5.

## Where it plugs in on our side (no forecaster changes)
1. **Weather-probability markets (direct).** `(value, sigma[, resid_quantiles])` -> the existing
   `(value,sigma) -> bucket-prob` bridge in `kalshi_score.py` / `weather_regime_score.py`: integrate the
   residual distribution across that day's re-centered ~2F ladder -> P(bucket) -> compare to the market mid
   -> per-line edge (see the trade-distribution math). Scored PER CELL vs the market baseline, leakage-gated.
2. **NG demand path (driver).** The corrected forward high -> `nws_temp_feed.py` forward gas-weighted
   HDD/CDD (path B) -> conditions `bucket_continuation.py`'s NG temp cells. Same forecast, consumed as a
   feature, not a tradeable.

## Discipline (unchanged)
Per cell never pooled; distributions/fingerprints never means; leakage gate before any scoring; report
"edge on {cell}, not {cell}" never a pooled Brier; the forecaster itself is Greg's - we only score + route +
size. Depth/capacity of the edge is UNKNOWN until the rerun (Greg: "we don't know if it's tall") - bank the
shape, not the magnitude.
