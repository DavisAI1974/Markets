# GROUP PRECHECK REGISTRY — S103 (streamlined: pre-checks done ONCE, per Greg)

Pre-checks split into SHARED (done once, cover every group) and PER-GROUP (tape day-files +
decision-state build + anchor). This registry records the shared work + the roll map so each group
is turnkey (no re-pull, no selftest per group).

## SHARED SUBSTRATE — done once this session (covers all groups)
- AWS creds: STS PASS, account ...4170 (scratchpad/aws.env + ~/.aws/credentials). Run platform_sync
  / boto3 with the placeholder env vars stripped: `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`
  (the container placeholders override setdefault otherwise — the S100 trap; this is the fix).
- Full-history stores pulled once: weather, cot, cot_combined, storage_regional, storage_vintage,
  steo_vintage, consensus(->data/storage_consensus), cash_basis, grid_stack, model_disagreement,
  ngwu, nuclear_outages, solar_calendar, vol_regime, contract_structure, nymex_curve,
  eia(->data/eia_surprise.json), flow_calendar. These are time-series — no per-group re-pull.
- Skipped (masked-in-blind or excluded): options_ng/cl/bridge (price-derived, masked), nymex raw,
  ng_l1, kalshi/kalshi_echo, deploy.

## ROLL MAP (Kalshi underlying = 5bd before LTD; verified from NG_structure.json)
- April/NGJ26 LTD 2026-03-27 -> roll 2026-03-20 (G15 seam, done).
- May/NGK26  LTD 2026-04-28 -> roll 2026-04-21.
- June/NGM26 LTD 2026-05-27 -> roll 2026-05-20.

## GROUP WINDOWS + BASIS
- **G16** Sun 03-29 -> Fri 04-10 (11 sessions; Good Friday 04-03 DARK = extended 3-day weekend;
  EIA 04-02 & 04-09). Basis: **May/996 whole block, no seam.** Anchor Fri 03-27 close 3.035,
  last-hour UP. STATUS: decision-state built (grp16_state.json); 3-agent blind panel RUNNING.
- **G17** Sun 04-12 -> Fri 04-24 (2 weeks). Basis: **May/996 through 04-20, June/NGM26 from 04-21**
  (seam at 0421 — TWO-LEG block like G15; measure the seam, mark never-traded). Anchor = 04-10
  actual close. STATUS: window+basis known; build state + pull tape when reached (turnkey).
- **G18** Sun 04-26 -> Fri 05-08. Basis: **June/NGM26 clean** (June roll 05-20 is outside).
  STATUS: window+basis known; turnkey.

## PER-GROUP STEPS (when a group is reached — the only repeated work)
1. Pull that group's tape day-files (nymex_cont_n0 for the front leg; the roll-contract-specific
   store for the pre-roll leg during a seam block, as G15 used nymex_cont_ngj26 for the April leg).
2. `forecast_harness.py decision-state --days <sessions> --mask-after <anchor date> --out grpN_state.json`.
3. Anchor = the prior Friday's actual close + last-hour dir (decision-time-legit, outside the block).
4. Spawn the 3-agent blind panel (shared directive + the 3 angles) -> synthesize per-event -> score -> render.
