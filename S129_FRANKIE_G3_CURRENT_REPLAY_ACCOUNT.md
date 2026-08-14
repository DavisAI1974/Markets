# S129 Frankie G3 current-state historical replay account

## Run identity

- Window: 2025-09-08 through 2025-09-19 (10 CME sessions)
- Starter anchor: 2025-09-05 close 3.026, last-hour direction down
- Contract through this window: NGV25. The historical RT seam is 2025-09-25, outside the run.
- Frankie state/brain generation: current S128 repaired decision-state path on `chatgpt/burn-hh-12m-s125`.
- Current-state workflow run: 31792711198, artifact 9216129154, digest `sha256:b34c6a2b39207302050e95ab58f5bf4538fde714d5f5ed5e35b169a31d323fe5`.
- Frozen forecast commit: `8c0b48ac5a44cbae7569ccd28e05c176744500f8`.
- Score commit: `8370d3dfc1b2ffba958a86a7326102f331326fb2`.
- G24 was not touched.

## Integrity classification

This is a historical learning replay, not a pristine blind holdout. The current brain already contains historical provenance from older G3-era learning, and old outcome artifacts were encountered during setup. The operator guard for the frozen forecast was to use current state triggers and generalized plays rather than target-date outcome lookup. Forecasts were committed before the score pass.

## Current-state coverage finding

The S128 builder itself now runs successfully for the September window. It emits the current 31-channel state schema, but only four channels are populated from the repositories/public caches available to the Actions runner:

- `dow`
- `curve_regime` (`unknown`)
- `cot` (rebuilt from CFTC futures-only + combined archives, including ICE sub-books)
- `flow_calendar`

The other 27 current channels are unavailable/null, including storage/consensus/vintage, NGWU, STEO, contract structure, options/squeeze/vol, cash basis, grid/nuclear/solar, weather forecast and disagreement stack, freeze risk, and tape conditions.

This is the load-bearing result of S129. It means the replay is not equivalent to giving Frankie the populated G24-era live data surface. The schema and current brain are current; historical cache coverage is not.

## Frozen coordinator calls

| Date | Owner | Call | P50 day move | Actual | Abs error | Dir |
|---|---|---|---:|---:|---:|---|
| 09-08 | B | ABSTAIN | -250 | +190 | 440 | miss |
| 09-09 | C | CALL | -300 | +120 | 420 | miss |
| 09-10 | C | CALL | -250 | -750 | 500 | hit |
| 09-11 | D | ABSTAIN | -550 | -1010 | 460 | hit |
| 09-12 | E | ABSTAIN | -200 | +280 | 480 | miss |
| 09-15 | B | ABSTAIN | -250 | +200 | 450 | miss |
| 09-16 | C | CALL | +250 | +1200 | 950 | hit |
| 09-17 | C | CALL | +150 | -430 | 580 | miss |
| 09-18 | D | ABSTAIN | -450 | -1360 | 910 | hit |
| 09-19 | E | ABSTAIN | -150 | -250 | 100 | hit |

Metrics:

- endpoint MAE: **$529/day**
- endpoint RMSE: **$578.1/day**
- max absolute endpoint error: **$950**
- p50 direction: **5/10**
- CALL-only direction: **2/4**
- day-local 13-point intraday curve MAE: **$336.8**

## What Frankie did correctly under the handicap

- He did not fabricate unavailable weekend-cycle data: A emitted zero p50 gap rather than inventing a September 8 reopen.
- D treated storage Thursday as a magnitude/range event and abstained on direction without same-print consensus or causal post-print tape.
- C captured the Sep 10 downside, Sep 16 upside turn, and the two D paths captured the downside sign on Sep 11 and Sep 18.
- E did not invent a Sep 19 roll seam. The actual historical seam is Sep 25.

## What failed

The largest errors line up with absent current channels rather than a need for a new signal family:

1. Sep 8: actual weekend reopen gap was +460; the current historical state had no weekend-cycle evidence, so Frankie correctly refused to invent it. The cumulative path was displaced immediately.
2. Sep 11 and Sep 18: Frankie got the downside sign but undersized both storage-day moves because the storage-consensus/tape-delivery stack was absent.
3. Sep 16: C correctly moved to a covering/upside read after the scheduled roll windows cleared and COT improved, but with no tape/weather/structure authority the +250 p50 badly undersized the +1200 day.
4. Sep 17: the COT-covering continuation was wrong without delivery evidence to invalidate it.

## S129 lesson / next action

**Do not write a new Frankie market lesson from this score and do not add datapoints.** The correct next action is historical availability work: reconstruct/backfill the *existing* current feed stores for old windows, then rerun this same September block through the same current S128 state/brain path. Missing historical values must remain unavailable until a causally valid source is restored; no realized proxy or same-day print may be substituted.

The new `frankie_g3_s129_current_state.yml` workflow is the reusable fast historical-state launcher. It already rebuilds the public CFTC futures/combined positioning stores and successfully emits the ten-day current decision state. Extend that launcher/store preparation, not Frankie’s schema.
