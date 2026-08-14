# S126 M-13 Recovery Status

Branch: `chatgpt/burn-hh-12m-s125`
Current code-side head: `95b41415f44d077d47de391b572c757cb5a81ded`

## Scope

M-13 is the remaining staging blocker after the S114 wind/solar path was verified intact. The three stale stores are:

- `storage_consensus`
- `weather_forecast_cycle`
- `freeze_risk`

This recovery does **not** change Frankie, specialist roles A-E, Frankie settings/schema/inputs, `spawn.py`, the S114 wind/solar methodology, or closed S125 burn/HH and national-storage work.

## Code-side recovery: BUILT AND GREEN

Recovery wrapper:

`research/kalshi/frankie_m13_recover_s126.py`

Blind-safe forward consensus provenance:

`research/kalshi/data_records/storage_consensus_forward_s126.json`

Focused tests:

`research/kalshi/tests/test_frankie_m13_recover_s126.py`

Focused CI:

`.github/workflows/frankie_m13_recover_s126_ci.yml`

Green GitHub Actions run:

- workflow: `S126 Frankie M13 Recovery Invariant`
- run id: `31765327861`
- result: `success`
- focused tests: `5 passed`

The branch diff from the prior S126 AWS-stage truth at `a5d84a9e305f013ff17487d92b78deb047f4489c` contains only the M-13 wrapper, its evidence record, its focused tests, and its CI workflow. No protected Frankie or S114/S125 implementation files were changed.

## Storage consensus provenance pinned

The recovery uses only point-in-time collector observations whose actual poll timestamp was strictly before the corresponding Thursday 10:30 ET EIA print. Durable `consensus.jsonl` is not treated as sufficient provenance because its forecast field is updated in place.

Pinned forward vintages:

- 2026-07-16: `45 Bcf`, observed `2026-07-16T13:50:18Z`, print `14:30Z`
- 2026-07-23: `29 Bcf`, observed `2026-07-23T14:06:50Z`, print `14:30Z`
- 2026-07-30: `37 Bcf`, observed `2026-07-30T14:02:59Z`, print `14:30Z`
- 2026-08-06: `30 Bcf`, observed `2026-08-06T14:14:57Z`, print `14:30Z`
- 2026-08-13: `31 Bcf`, observed `2026-08-13T08:49:47Z`, print `14:30Z`

A later 2026-08-13 collector poll that executed after the print is explicitly rejected as provenance.

## What the recovery wrapper does

With `--execute`, the wrapper:

1. restores the current private S3 substrate through the existing `restore_substrate.py` path;
2. merges only the pinned strictly-pre-print consensus observations into the existing `storage_consensus` history without overwriting a conflicting archived headline value;
3. extends demand MOS input using the existing `nws_temp_feed` source and rebuilds the existing `mos_cycle_feed` store;
4. extends producing-basin MOS using the existing `freeze_risk_feed` pull/build path;
5. validates g24 coverage locally for all three M-13 blocks;
6. pushes only through the sanctioned `platform_sync.py` S3 door;
7. GETs every pushed source file back from S3 and requires byte-identical SHA256 plus manifest equality;
8. runs canonical `stage_group.py g24 --suffix _m13check` and requires `state_health` hard failures = 0 and all three M-13 blocks non-empty on every g24 day.

It fails closed if `--execute` is omitted, if consensus evidence crosses the print timestamp, if local coverage is missing, if S3 read-back differs, or if rehearsal staging is unhealthy.

## AWS execution: PENDING

The current ChatGPT session does not have the credentialed Markets AWS shell/data plane, so the final M-13 mutation and staging proof must run on the existing Markets AWS environment.

Claude does not need to redesign or edit anything. Run exactly:

```bash
cd <repo-root>
git checkout chatgpt/burn-hh-12m-s125
git pull --ff-only

env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
  python research/kalshi/frankie_m13_recover_s126.py g24 \
  --through 2026-08-13 --execute
```

Expected terminal success line:

```text
PASS: M-13 g24 stores rebuilt, S3 SHA256 read-back verified, staged state health hard=0
```

If and only if that passes, immediately run the existing canonical S126 stage/re-slice verification:

```bash
env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
  python research/kalshi/frankie_aws_stage_s126.py g24
```

Expected terminal success line:

```text
PASS: g24 restored, re-staged, causal slices rebuilt, S114 wind/solar served end-to-end
```

Return the complete output from both commands. Do not change Frankie, A-E roles, schemas, settings, inputs, `spawn.py`, S114 forcing methodology, or closed S125 work to make a failing command pass.

## Failure classification

If the first command fails, classify before changing code:

- AWS auth/credential failure: fix runtime credentials only.
- IEM/network retrieval failure: retry the same existing source path; do not invent substitute weather data.
- missing or malformed S3 baseline: inspect the named object/prefix before rebuilding anything else.
- consensus blind-wall/provenance failure: leave the affected value null rather than using a post-print value.
- S3 SHA256/manifest mismatch: stop; do not stage from unverified remote bytes.
- state-health/rehearsal failure: investigate the named store or staging seam; do not weaken the gate.

If the second command fails after the first passes, M-13 is recovered and the remaining problem is canonical S126 staging/slicing; investigate that seam without rebuilding S114 wind/solar.
