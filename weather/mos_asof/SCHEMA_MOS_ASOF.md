# MOS as-of forecast feed (S97 JOB 2.2)

What the NWS MOS point forecast **said** as of the **evening of D-1**, gas-weighted to the same 16 demand
metros the realized feed uses. Built because the gas market reprices on the forecast and on the
**run-to-run change** in the forecast, not on the temperature that actually turned out.

Built by `research/kalshi/nws_temp_feed.py --mos-asof --start YYYY-MM-DD --end YYYY-MM-DD`.

## Source

IEM MOS archive (verified live, S97):

```
GET https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py
    ?station=K<4char>&model=<GFS|NAM|MEX>&sts=<ISO Z>&ets=<ISO Z>&format=csv
```

CSV columns: `runtime,ftime,model,n_x,tmp,dpt,cld,wdr,wsp,...,station`

- `runtime` = model **initialization** time (UTC) — the blind-wall key
- `ftime` = valid/forecast time (UTC)
- `tmp` = forecast temperature (F)

Model codes as actually served: `GFS` = GFS-MOS **MAV** (3-hourly, ~+72h), `NAM` = NAM-MOS **MET**
(3-hourly, ~+84h), `MEX` = GFS extended MOS (12-hourly, ~+192h).

Climatological normals come from the NWS normals IEM serves with the daily ASOS summary
(`/cgi-bin/request/daily.py`, fields `climo_high_f` / `climo_low_f`) — published NWS normals, real data.

## The blind wall

A target day D may only ever see runs with `runtime <= D-1T23:59Z`. In the gas-day reference tz
(`America/Chicago`) that instant is **17:59 CT on D-1** — unambiguously the evening of D-1. It admits the
18Z D-1 cycle and **excludes the 00Z cycle of D itself**. Enforced by `_mos_cutoff_utc` plus a hard assert
in `_runset_asof`, covered by `--selftest`, and re-verified on the built data: **0 violations across all
11,648 (day x horizon x metro) run stamps.**

`run_delta` compares the D-1 evening batch against the D-2 evening batch, so it too is strictly behind the
wall.

## Missing is explicit, never zero

Any metro/day/run without usable coverage yields `null`, never `0`. A zeroed HDD in January would read to
the forecast agent as "no heating demand" — a catastrophic false signal. Weights are renormalized over the
metros actually present; `coverage` is the retained weight fraction; anything short of full coverage is
`partial: true` with the missing metros **named** in `metros_missing`. Verified: **0 cells carry an exact
0.0 HDD.**

## Files

| Path | Contents |
|---|---|
| `mos_asof_index.json` | `{ "YYYY-MM-DD": <day record> }` — the feed |
| `climo_normals.json` | `{ metro: { "MM-DD": climo_tmean_F } }` — NWS normals |
| `raw/` | `{METRO}_{MODEL}_{sts}_{ets}.json` raw MOS rows, verbatim (fetch cache, ~51 MB) |

## Day record

```jsonc
{
  "date": "2026-01-20",
  "asof_utc": "2026-01-19T23:59Z",       // the blind wall for this day
  "asof_note": "...",
  "forecast_gw_hdd": 32.399,             // D+0, gas-weighted, null if uncovered
  "forecast_gw_cdd": 0.0,
  "forecast_regime": "hard_heat",        // same regime_bucket() vocabulary as the realized feed
  "forecast_vs_normal": 5.199,           // forecast gw_hdd minus NWS-normal gw_hdd
  "forecast_run_delta": -0.402,          // THE REPRICING DRIVER: D-1 batch minus D-2 batch, same target
  "forecast_run_delta_cdd": 0.0,
  "fwd7_gw_hdd_span": [27.39, 41.573],   // shape descriptor only; per-horizon values are canonical
  "complete": true,                      // D+0 forecast AND D+0 run-delta both fully covered
  "coverage_note": "...",
  "horizons": [ { "horizon": 0, "target_date": "2026-01-20", "forecast_gw_hdd": 32.399,
                  "forecast_gw_cdd": 0.0, "regime": "hard_heat",
                  "normal_gw_hdd": 27.2, "normal_gw_cdd": 0.0, "forecast_vs_normal": 5.199,
                  "coverage": 1.0, "n_metros": 16, "partial": false, "metros_missing": [],
                  "coverage_note": "complete: all 16 gas-demand metros present",
                  "source_by_metro": { "ORD": "GFS@2026-01-19 18:00:00", ... } }, ... ],
  "run_delta":  [ { "horizon": 0, "target_date": "2026-01-20", "d_gw_hdd": -0.402, "d_gw_cdd": 0.0,
                    "coverage": 1.0, "n_metros": 16, "partial": false, "metros_missing": [],
                    "coverage_note": "complete: all 16 metros in both batches" }, ... ]
}
```

`source_by_metro` stamps **which model and which run** produced every metro-day. Nothing is silently
substituted; the model preference walk is GFS (MAV) -> NAM (MET) -> MEX, and MEX is reached only where MAV
and MET physically cannot (beyond ~+72/84h).

`run_delta` is computed on the **common metro set only** (metros present in both batches), so a change in
coverage can never masquerade as a change in the forecast.

## decision_state wiring (additive)

`forecast_harness.decision_state()` gains a `weather_forecast` key **alongside** the existing `weather`
key. The realized-proxy read is untouched — both coexist so the refine can settle which one the market
actually trades. Absent feed file -> `weather_forecast: None`, never a zero.

## Per-day, never pooled

Every value is per-day and per-horizon. `fwd7_gw_hdd_span` is a shape descriptor for the agent, never a
final answer; the per-horizon arrays are canonical (Greg's no-pooling rule).
