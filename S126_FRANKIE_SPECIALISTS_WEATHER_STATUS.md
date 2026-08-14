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

Therefore the end-to-end claim is NOT satisfied yet. The producer exists, but the currently committed decision state/slices are stale relative to the S114 data-plane fix.

This is a staging/restoration defect, not evidence that the S114 wind/solar model needs redesign.

## S126 AWS recovery invariant: BUILT

`research/kalshi/frankie_aws_stage_s126.py` is now the fail-closed AWS staging preflight for this defect. It does not create a new weather signal and does not alter Frankie.

For a requested group it:

1. invokes the existing `restore_substrate.py --group <gid>` path, which restores the S3 substrate (including `nymex/gefs_forcing/`) and canonically re-stages the group through `stage_group.py`;
2. inherits the existing `state_health.assert_healthy()` completeness gate from canonical staging;
3. rebuilds `g<N>_causal_slices` from the newly staged state using `build_causal_slices.py`;
4. proves every group day has non-null wind and solar, wind/solar remain separate, timestamps are strictly causal, every specialist slice carries the exact canonical forcing block, and no slice contains a future day block;
5. hashes the S114 historical blind artifact before/after and fails if recovery changes it.

Focused tests in `research/kalshi/tests/test_frankie_aws_stage_s126.py` cover the green path plus missing-forcing, stale-slice, and future-day failures. `.github/workflows/frankie_aws_stage_s126_ci.yml` compiles the preflight, runs those tests, and proves it reuses the existing S114 restore/canonical staging/slice paths.

This closes the code-side staging seam that allowed a freshly restored canonical state and old specialist slices to coexist.

## Why no replacement wind/solar system was invented here

The original S114 generated JSON was intentionally a data-plane artifact, not a Git-tracked file. It was never committed under either `data/gefs_forcing/gefs_forcing.json` or `research/kalshi/data/gefs_forcing/gefs_forcing.json`.

S114 records the exact authoritative copy as S3 `nymex/gefs_forcing/gefs_forcing.json`. The sanctioned restore path requires the Markets AWS credential chain through `creds.aws_client`; GitHub Actions currently has no AWS credentials configured, so CI cannot re-read that private object.

The public source research remains available in `research/kalshi/CHATGPT_S112_SIX_WORKSTREAMS.md`: NOAA GEFS control + p01-p30 can be reconstructed from the public date-partitioned `noaa-gefs-pds` archive if the authoritative S114 S3 object is truly lost. That is a recovery fallback, not the first move, because the surviving S114 record does not preserve enough detail to assert a byte-identical proxy reconstruction.

## Required recovery order

Do NOT build a different wind/solar model first.

On the Frankie AWS environment with the existing Markets credential path, run the single recovery command:

```bash
cd <repo-root>
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
  python research/kalshi/frankie_aws_stage_s126.py g24
```

A PASS means the existing S114 S3 store was restored, canonical state was rebuilt through the current harness and health checks, causal specialist slices were rebuilt, wind + solar are non-null and causal end-to-end, and the S114 blind artifact stayed unchanged.

A FAIL means Frankie must not run from those artifacts. If the failure is S3 object absence/corruption after legitimate AWS credentialed access, the user-authorized condition for rebuilding the wind/solar feed has finally been met. Until then, recovery stays on the existing S114 signal.

After a PASS, promote/commit only the canonical current state and causal slice artifacts required by the existing artifact contract; do not rewrite historical blind evidence.

Finally run the S126 specialist/weather verification workflow. It hard-fails if the committed `grp24_state.json` or any current g24 causal slice lacks `weather_forcing_forecast`, so a code-path-only green run can no longer hide this defect.

## Current truth

- S125 burn/HH: CLOSED; untouched.
- S125 national storage-null repair: CLOSED; untouched.
- A-E specialist update to current Frankie: CLOSED.
- Frankie coordinator/settings/schema/inputs/roles: unchanged.
- S114 wind/solar producer: present and wired.
- S126 AWS restore/re-stage/re-slice fail-closed wrapper: BUILT.
- S114 authoritative store: recorded on private S3; not re-readable from the current GitHub Actions environment.
- Current committed g24 state/slices: STALE with respect to `weather_forcing_forecast`.
- End-to-end wind/solar verification: PENDING one legitimate AWS run of `frankie_aws_stage_s126.py g24`; Frankie is blocked from using the stale artifacts until that passes.
