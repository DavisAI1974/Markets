# S126 Frankie Specialists + S114 Weather Verification

Branch: `chatgpt/burn-hh-12m-s125`
Base authority: `S125_FRANKIE_STORAGE_FIX.md` at `6441a2772a19cb19a390bc5c81fab28f9d9fb2f1`.

## Specialist A-E update: CLOSED

The current Frankie specialist seam is `research/kalshi/frankie_specialist_parity_s126.py`, installed through `research/kalshi/frankie_s121_curve_restore.py`.

It is wiring only:

- Frankie remains coordinator.
- Specialists remain A, B, C, D, E with their existing role files unchanged.
- Every specialist receives the same complete already-served causal slice for its decision day.
- Every specialist retains the full canonical Frankie brain; `play_index` is consultation guidance only, never an availability filter.
- No role-based data filtering is permitted.
- `realized_outcome_in_packet` must remain false in BLIND.
- Reduced-brain packets fail closed.
- Frankie settings, schema, inputs, masks, thresholds, ownership, and execution authority are unchanged.
- `research/kalshi/spawn.py` is unchanged and remains protected.

Focused parity tests cover all five specialists and the S121 installed packet path.

## S114 weather_forcing_forecast verification: FAILED at the committed artifact layer

The existing S114 implementation itself is still installed correctly:

1. `forecast_harness._weather_forcing_block()` reads `data/gefs_forcing/gefs_forcing.json` and exposes separate `wind_cf_proxy` and `solar_irradiance_proxy` with forecast-vintage metadata.
2. `forecast_harness.decision_state()` serves it as `weather_forcing_forecast`.
3. `state_health.REQUIRED_EVERY_DAY` requires it.
4. `restore_substrate.py` restores `nymex/gefs_forcing/` to `data/gefs_forcing`.
5. S114 commit `62382e2872b823cedad10681ebdf002671d66927` records that the store was built for all 11 sessions with 31/31 GEFS members and pushed to S3, then read back.

But the CURRENT committed g24 artifacts do not contain the block:

- `research/kalshi/renders/ng_refine_s95/grp24_state.json`: `weather_forcing_forecast` absent.
- `research/kalshi/renders/ng_refine_s95/g24_causal_slices/state_20260720.json`: `weather_forcing_forecast` absent; the same stale-state family applies to the current slice set.

Therefore the end-to-end claim is NOT satisfied. The producer exists, but the currently committed decision state/slices are stale relative to the S114 data-plane fix.

This is a staging/restoration defect, not evidence that the S114 wind/solar model needs redesign.

## Why no replacement wind/solar system was invented here

The original S114 generated JSON was intentionally a data-plane artifact, not a Git-tracked file. It was never committed under either `data/gefs_forcing/gefs_forcing.json` or `research/kalshi/data/gefs_forcing/gefs_forcing.json`.

S114 records the exact authoritative copy as S3 `nymex/gefs_forcing/gefs_forcing.json`. The sanctioned restore path requires the local Markets AWS credential file through `creds.aws_client`; GitHub Actions currently has no AWS credentials configured, so CI cannot re-read that private object.

The public source research remains available in `research/kalshi/CHATGPT_S112_SIX_WORKSTREAMS.md`: NOAA GEFS control + p01-p30 can be reconstructed from the public date-partitioned `noaa-gefs-pds` archive if the authoritative S114 S3 object is truly lost. That should be a recovery fallback, not the first move, because the surviving S114 record does not preserve enough detail to assert a byte-identical proxy reconstruction.

## Required recovery order

Do NOT build a different wind/solar model first.

On an environment with the existing Markets AWS credentials:

```bash
cd <repo-root>
python research/kalshi/restore_substrate.py
```

Then verify `data/gefs_forcing/gefs_forcing.json` exists and `_weather_forcing_block(day)` is non-null for every g24 day.

Re-stage g24 with the current `forecast_harness.py` and rebuild its causal slices using the existing canonical staging/slice commands. Do not overwrite an immutable historical blind artifact if the repo's blind-vs-refine naming rules prohibit it; write/promote only through the existing canonical staging contract.

Finally run the S126 verification workflow. It now hard-fails if the committed `grp24_state.json` or any current g24 causal slice lacks `weather_forcing_forecast`, so a code-path-only green run can no longer hide this defect.

## Current truth

- S125 burn/HH: CLOSED; untouched.
- S125 national storage-null repair: CLOSED; untouched.
- A-E specialist update to current Frankie: CLOSED.
- Frankie coordinator/settings/schema/inputs/roles: unchanged.
- S114 wind/solar producer: present and wired.
- S114 authoritative store: recorded on private S3; not re-readable from the current GitHub Actions environment.
- Current committed g24 state/slices: STALE with respect to `weather_forcing_forecast`.
- End-to-end wind/solar verification: FAILED until restore + re-stage produces populated committed artifacts.
