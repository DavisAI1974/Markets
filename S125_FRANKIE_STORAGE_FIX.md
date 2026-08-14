# S125 Frankie Storage Fix

Branch: `chatgpt/burn-hh-12m-s125`

## Status

CLOSED for the storage-null defect seen in S124.

The top-level `storage` block was not missing from Frankie's schema. `forecast_harness.decision_state()` already serves `storage`, `storage_regional`, `storage_consensus`, and `storage_vintage`. The null arose because the legacy national path depends on generated `data/eia_surprise.json`, which is not guaranteed to exist in a fresh checkout and whose older generator depends on an EIA API key / DEMO_KEY path.

## Fix

Two deterministic, no-key components are now committed:

- `research/kalshi/eia_storage_compat.py`
  - rebuilds the existing `KXNATGASD` compatibility shape expected by `forecast_harness._storage_series()`;
  - derives it from the official EIA WNGSR history workbook through the already-existing `storage_regional` code;
  - does not change Frankie's schema or add a new signal.

- `research/kalshi/frankie_storage_preflight.py`
  - rebuilds the regional WNGSR store and the national compatibility store from EIA's official public workbook;
  - requires no API key;
  - cross-checks the latest Lower-48 level and weekly change between the national and regional views;
  - fails closed if the stores are absent or disagree.

## Mandatory state-build order

Before generating or re-staging a Frankie decision state, run:

```bash
cd research/kalshi
python frankie_storage_preflight.py
python forecast_harness.py decision-state --days <D1,D2,...> [--group <gid>] [--mask-after <YYYYMMDD>] --out <state.json>
```

The preflight is data plumbing only. The existing decision-state schema and forecaster logic remain unchanged.

Do not launch specialists from an old committed state whose `storage` block is null. Re-stage that state after the preflight.

## Acceptance: S124 blind dates

Using the official no-key EIA workbook, CI rebuilt both stores and checked 2026-04-27 through 2026-04-30. On every date national storage was non-null, matched the regional Lower-48 row, and respected the strict-before-day blind wall.

For 2026-04-27, 2026-04-28, 2026-04-29, and the 2026-04-30 pre-print open, the visible record is:

- release/as-of: `2026-04-23`
- storage period: `2026-04-17`
- Lower-48 working gas: `2063 Bcf`
- weekly change: `+103 Bcf`
- versus 5-year level: `+112 Bcf`
- phase: `inject`

The 2026-04-30 open correctly does NOT see its own 10:30 ET storage release.

Data-integrity workflow: `.github/workflows/storage_data_integrity_s125.yml`.

## Preflight CI

`.github/workflows/storage_preflight_ci_s125.yml` runs the canonical preflight from a clean checkout.

Latest passing result at S125 close:

- status: `READY`
- regional reports: `867`
- national reports: `866`
- latest release: `2026-08-13`
- latest storage period: `2026-08-07`
- latest Lower-48 level: `3153 Bcf`
- latest weekly change: `+36 Bcf`
- source: `EIA_WNGSR_ngshistory_xls`
- API key required: `false`

## Vintage rule remains in force

This fix does not replace `storage_vintage`. For historical decisions before a later EIA reclassification was published, the as-printed vintage remains the decision-time truth. The compatibility/current-series view and `storage_vintage` remain additive, not substitutes.

## Wind / solar note for the next session

The S124 forward wind/solar complaint is not a fresh build item anymore. Current `forecast_harness.py` already contains the S114 `weather_forcing_forecast` / `_weather_forcing_block()` using D-1 GEFS wind and solar forcing with causal timestamps and separate wind/solar proxies. After the specialist update, verify that this block is populated in the current live/rehearsal slices; do not rebuild it unless that verification fails.

## Next build order

1. Start a new chat.
2. Update the A-E specialist shared contract/wiring to the current Frankie build without rewriting the specialist roles.
3. Verify `weather_forcing_forecast` is actually populated/served end to end.
4. Continue Frankie testing with the existing 1800+ data universe; do not add new data points merely to fill the toolbox.
