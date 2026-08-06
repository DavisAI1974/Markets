# SESSION HANDOFF — S94 (work date 2026-07-14) — the loop RUNS IN THE CLAUDE ENV; chronological pivot + running storage/weather story; Groups 2 & 3 done

Branch: came up on the stale S70 tip; reset onto the s79 trunk (`claude/kalshi-s79-kickoff-ij8t9o`, the real
latest — s88 is its ancestor) and worked on the designated branch `claude/ng-coach-agent-loop-5ha5bf`
(== s79 tip + this session's commits, pushed). Read `research/kalshi/REFINE_DIRECTIVE_S94.md` FIRST next
session, then this file.

## HEADLINE — the S94 pivot (Greg)
Abandon the AWS coach-agent build; **run the forecaster loop IN the Claude environment — the agent's brain
IS the session model.** The whole loop is in-git and ran here end-to-end: decision-state -> a spawned blind
agent forecasts from `ng_brain.json` -> score vs the S3 tape -> merge per-event lessons -> commit. No box,
no Bedrock, no OpenAI. Completed **Group-2** (scored + merged to brain **s92.3**) and **Group-3** (the first
CHRONOLOGICAL group), and pivoted the METHOD to chronological contiguous week-aligned blocks with a running
storage+weather story and day-into-day reasoning.

## WHAT RAN / WAS BUILT
- **S3 unblocked.** The env AWS keys were bad (truncated secret -> `InvalidAccessKeyId`); the full secret
  from Greg's screenshot fixed it (IAM user `Claude`, acct 568968024170, bucket
  `bento-568968024170-us-east-2-an`, region us-east-2). The NG/CL MBP-10 tape lives on S3 (git=CODE, S3=DATA).
  Keys (AWS + Databento) are in `scratchpad/aws.env` (gitignored, chmod 600). **ROTATE — the AWS key ID is
  now in a chat image.**
- **All S89-S93 work IS in git on s79** (brain, forecaster machinery, handoffs) — earlier "not in git" was a
  wrong read off the older s88 branch.
- **Group-2** (12 scattered warm days): blind agent forecast from brain s92.1 -> scored vs tape -> **merged to
  s92.3**, 3 new plays (all PER-EVENT, NO averages — Greg's hard rule): `daytype.monday_weekend_gap` (Monday =
  big mover, side uncertain), `daytype.storage_thursday_magnitude` (Thursdays big), `magnitude.warm_season_
  scale_candidate` (under-forecast on range/storage days, OVER-forecast on the surprise-magnitude trend bets
  0820/0826 which also went the wrong side; anti-lock-in: scale-vs-regime unresolved).
- **Brain also s92.2**: added `timing.subsecond_reversal_exhaustion` — the coin/BTC sub-second look-ahead
  (S36/S37 price-reversal + dipole EXHAUSTION) tested on NG futures (S90, faint +2.7pp right-signed, real edge
  is native-tick/ms). Execution-layer; never a blind curve input. Distinct from the futures->Kalshi lag AND
  from the dipole DIRECTION nowcast.
- **Group-3** (the FIRST chronological group, contiguous **Sep 8-24**, 10-ish healthy days incl. 3 Mondays):
  blind agent forecast on s92.3 + the enriched decision-state (with day-into-day continuous framing) ->
  scored -> CONTINUOUS overlay. **RESULT (per-event): the storage-surplus fundamental CALLED THE BLOCK
  DOWN-TRAJECTORY** (price walked 3.10 -> 2.80 over the block; the agent's +150 Bcf-surplus down-bias tracked
  it) = the chronological pivot working. **Intraday per-day direction still coin-flip** (a day pops hard
  against the trend then resumes — 0916 +$1330 up inside a downtrend). **Magnitude still under** on big days.
- **decision_state ENRICHED** (`forecast_harness.py`): now carries a running **storage-capacity story**
  (working-gas level Bcf + surplus/deficit vs 5-yr avg + inject/withdraw phase, from EIA prints) and
  **weather** (gas-weighted HDD/CDD regime, S88 nws feed) — blind-safe. The Nov-fill -> Dec-drawdown surplus
  collapse (+201 -> +15 Bcf) is the winter fundamental to watch.
- **Fast scoring**: `scratchpad/fast_score2.py` (grep-prefilter trade lines + npz price cache) = ~45s/group
  (was 15+ min on the raw-MBP-10 decode). `scratchpad/continuous_overlay.py` renders a group as one flowing
  price path.
- **Monday re-pull IN PROGRESS** (`scratchpad/repull_mondays.py`): the ~18 corrupt Monday stubs (Sep 29 2025
  -> Jan 26 2026, the S90/S92 flush bug) are being re-pulled NG-only from Databento to S3 (~$0.15/day, ~$2.70
  total), uploaded as `NG_YYYYMMDD_mon.jsonl.gz`, stub deleted. **NEXT SESSION: verify all 18 landed >50KB
  (`_mon` name); re-pull any stragglers.** This opens the contiguous Oct+ walk.
- **REFINE_DIRECTIVE_S94.md** written (the next-phase marching orders — read it first).

## METHOD DECISIONS (Greg S94) — in the REFINE DIRECTIVE
- **Chronological CONTIGUOUS walk, week-aligned 2-week (10-trading-day) blocks**; groups flow into each other;
  walk forward into winter (the decisive regime). **Re-running days is fine.**
- **THE BIG ONE: the agent's logic runs ONE DAY INTO THE NEXT** — each day's forecast flows from the prior
  day's close/trajectory/running state; a continuation-or-turn of the running path, never an isolated event.
  This is the fix for both direction (block trend carries) and the "huge isolated events" magnitude framing.
- **NO averaging / pooling EVER** (Greg, hard — caught a median/"6-of-12" line and killed it). Per-event only.
- **Fix Mondays in parallel** while the agent forecasts a group that doesn't need them.
- Direction is LOCATED: block/fundamental direction (storage) works; INTRADAY direction is the open problem.

## STATE
- Brain: `research/kalshi/knowledge/ng_brain.json` **s92.6**, **12 plays** — CURRENT with the consecutive groups
  (blinded per-group merges G2 -> G3 -> G4 -> G5). New play `direction.cross_block_reversion` (see below);
  refined `monday_weekend_gap` / `storage_thursday_magnitude` / `warm_season_scale_candidate` /
  `surprise_magnitude`. Canary: all prior plays preserved, no averages.
- The 18 corrupt NG Mondays (Sep 29 2025 -> Jan 26 2026) are ALL re-pulled clean on S3 (`_mon`, >50KB).
- Branch `claude/ng-coach-agent-loop-5ha5bf` pushed (all S94 commits).
- Scratchpad (gitignored): grp{2,3,4,5} `_state`/`_forecasts`/`_score` json, `fast_score2.py`,
  `continuous_overlay.py`, `repull_mondays.py`, `aws.env` (keys).

## GROUPS 3/4/5 RAN + MERGED this session (chronological, CONSECUTIVE, 14-cal-day = 10-trading-day blocks)
- **G3 (Sep 8-24):** block fell 3.10->2.80; the +150 Bcf storage SURPLUS correctly called the block DOWN
  trajectory. Intraday direction coin-flip; magnitude under.
- **G4 (Sep 24-Oct 7):** block REVERSED UP 2.86->3.51 — the agent extended G3's downtrend, WRONG week 1
  (0925 +$1160, 0929 Mon +$1240 both guessed down), caught the up-move week 2. Magnitude under.
- **G5 (Oct 8-21):** a V, fell 3.51->2.92 then rallied 3.52 — agent leaned UP, WRONG week 1 (1008 -$1980
  guessed up), but the improvements HELPED the 2nd half: caught the 1016 turn-DOWN, the 1020 Monday REVERSAL
  UP (+$2770 but guessed +$580 = ~5x under), and handled the Oct 13 Columbus Day thin-flag right.
- **THE LEAD (new play `direction.cross_block_reversion`, HYPOTHESIS n=3):** each block tends to REVERSE / give
  back the prior block's move (G3 down -> G4 up -> G5 down-then-up), so the agent's block-OPEN directional lean
  kept landing CONTRA the market. LEAN AGAINST the prior block, do NOT extend it. Also: weekend-gap Monday
  REVERSALS are huge + badly under-sized; fundamentals (surplus/HDD) are a slow BACKDROP, not an intraday-timing
  signal. Overlays: `renders/ng_learn_s92/grp{3,4,5}_continuous.png`.
- **PROCESS CORRECTED (Greg):** the brain is merged (BLINDED, from scorecards) after EACH group so the next
  blinded group uses the updated json; the UNBLINDED refine is a separate deeper pass off the consecutive set.

## BUILDS DONE this session (for the walk): running storage-capacity + weather conditioning in `decision_state`
(level/vs-5yr/phase + gas-weighted HDD/CDD regime); weekday HOLIDAY flag {name,effect}; block-start ACTUAL
last-hour anchor (fed in the prompt); hr24->hr1 day-into-day reasoning + handoff turn-detector; fast grep+npz
scoring; continuous-price-path overlay. All in `REFINE_DIRECTIVE_S94.md`.

## NEXT (new chat) — BUILD LEFT FOR NEXT SESSION (Greg)
1. **BUILD the CONTINUOUS-CURVE representation** ("days still aren't flowing" — Greg). The forecast schema is
   still per-day (each curve resets to [20,0]=cumulative-from-that-day's-open) and the render re-anchors each
   day at the actual open, so the guess visually/numerically RESETS every morning. FIX: represent the forecast
   as ONE continuous cumulative-$ curve from the block-START actual anchor, each day flowing from the prior
   day's GUESSED close (hr24 of day N = hr1 of day N+1, adjacent points); render as one unbroken dashed line
   (it will DIVERGE from actual as the forecast errs = the honest "if you followed it" path); score vs the
   continuous actual. Schema + `continuous_overlay.py` + `fast_score2.py` all change together.
2. **Group-6** = next consecutive 14-cal-day block from **Oct 22** (Oct 22 -> Nov 4; walking toward winter),
   blind-forecast on s92.6 with the continuous-curve rep + the last-hour anchor -> score -> BLINDED per-group
   merge into the brain before the next group.
3. **UNBLINDED REFINE** off the consecutive groups (G3/4/5/6) per `REFINE_DIRECTIVE_S94.md` — the deep
   mechanism dig via `characterize_day` (flow/turn fingerprints) on the pivotal turn days; test the
   cross-block-reversion lead + the intraday-direction problem. NEVER off the scattered Group-2.
4. Walk into **winter** (Nov fill-peak -> Dec drawdown, surplus collapse +201->+15 Bcf) — the real regime test.

## RULES (unchanged): each event individually NEVER pool/average; per-cell; distributions not means; blind
wall (decision-time only) + leakage gate; exclude settle window; net-of-fee maker AND taker at the money step;
zero synthetic; provisional-until-live; git=CODE S3=DATA; NG and WTI SEPARATE; weather forecaster HANDS OFF;
keys are SECRETS (ROTATE).
