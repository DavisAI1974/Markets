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
- Brain: `research/kalshi/knowledge/ng_brain.json` **s92.3**, 11 plays (canary: all prior plays preserved).
- Branch `claude/ng-coach-agent-loop-5ha5bf` pushed (commits: overlay/gitignore, brain s92.2, brain s92.3,
  storage/weather conditioning, grp3 overlay, refine directive).
- Scratchpad (gitignored): grp2/grp3 `_state`/`_forecasts`/`_score` json, `fast_score2.py`,
  `continuous_overlay.py`, `repull_mondays.py`, `aws.env` (keys).

## GROUP-4 RAN this session (Sep 24 -> Oct 7, 14 calendar days = 10 trading days, CONSECUTIVE from G3)
Blind-forecast on s92.3 with the day-into-day continuous reasoning + storage/weather/holiday conditioning.
KEY RESULT (per-event): **the block REVERSED UP (2.86 -> 3.51, ~+$6500), flipping Group-3's downtrend.** The
agent, anchored to G3's DOWN-trajectory, guessed DOWN for week 1 and was WRONG on the turn (0925 guess -$330
/ actual +$1160; 0929 Mon -$640 / +$1240; 0930 -$470 / +$820); it caught the up-move only in week 2 (1001
+$1170, 1002 up, 1006 up, 1007 +$1620 — direction OK 0926/1001/1002/1006/1007). Its fundamental up-call at the
-40.8 Oct-2 bullish miss was RIGHT but LATE (the market turned ~0925, front-running the print). Magnitude
still under on the big days. LESSON (for the refine off G3+G4): **cross-block trend-continuation is DANGEROUS
— the market turned between blocks**; the agent mechanically extended a dead trend across the boundary and
needs a TURN-DETECTOR at the handoff + the live last-hour anchor (below), not a continuation assumption.
Overlay: `research/kalshi/renders/ng_learn_s92/grp4_continuous.png`.

## HONEST-ANCHOR CHANGE for the NEXT run (Greg S94, decided)
Feed the agent the ACTUAL trade price of the LAST HOUR before the block's first hour — a past/known number
(decision-time-legit), so it flows from the freshest real price + momentum, not a stale block-old trend
narrative. Block-START anchor only (outside the block = blind-safe); within-block days still flow from the
agent's own forecasts. Group-4 proved why this matters (the down-anchor from the stale prior block misled).

## NEXT (new chat)
1. Verify the Monday re-pull finished (all 18 `NG_*_mon.jsonl.gz` >50KB on S3); re-pull stragglers.
2. **Implement the last-hour actual anchor** (compute the real last-hour trade price before the block start;
   feed it to the blind agent as the point to flow from) + add a handoff TURN-DETECTOR to the agent's logic.
3. **Group-5 = the next consecutive 14-calendar-day block** continuing from Oct 7 (Oct 8 -> ~Oct 21; watch the
   Oct 13 Columbus_Day thin flag), blind-forecast with the last-hour anchor -> continuous overlay -> score.
4. **THEN the REFINE pass** per `REFINE_DIRECTIVE_S94.md` — UNBLINDED off the CONSECUTIVE groups (G3, G4, G5),
   NEVER the scattered Group-2. Extract general mechanisms (the cross-block-turn problem + intraday direction).
5. Walk into **winter** (Nov fill-peak -> Dec drawdown, surplus collapse) — the real regime test.

## RULES (unchanged): each event individually NEVER pool/average; per-cell; distributions not means; blind
wall (decision-time only) + leakage gate; exclude settle window; net-of-fee maker AND taker at the money step;
zero synthetic; provisional-until-live; git=CODE S3=DATA; NG and WTI SEPARATE; weather forecaster HANDS OFF;
keys are SECRETS (ROTATE).
