# REFINE DIRECTIVE — the chronological forecaster refinement (S94, Greg)

STATUS: DIRECTIVE (Greg + Claude, S94). The marching orders for the NEXT phase of the NG coach forecaster
loop, running IN the Claude environment (the agent's brain = the session model; no AWS box). Supersedes the
scattered-day method. Inherits every rule in `FORECAST_AGENT_DIRECTIVE_S88.md`, `KALSHI_TRADING.md`, and the
`kalshi-backtest` discipline — this only changes the WALK SHAPE and the agent's REASONING MODE.

---

## 0. Why we changed (the scattered-day flaws, Greg S94)
Scattered warm-season days could not teach regime behavior (you cannot learn winter from isolated winter
days), could not build a running storage story, broke weather continuity, and made every day's move look
like a HUGE ISOLATED EVENT (each measured from its own open in a vacuum). The fix is to walk CHRONOLOGICALLY
and reason CONTINUOUSLY.

## 1. The walk shape (changed)
- **Week-aligned groups: 2 full weeks = 10 NG trading days each** (weekends are dark — no Sat/Sun session).
  Each group then contains whole EIA storage cycles (Thursday prints) and its Mondays/weekend-gaps.
  (Adjustable to 3 weeks / 15 trading days if we want more per run — decide per phase.)
- **CONTIGUOUS chronological.** Each group starts where the last ended; the walk flows forward through the
  year into winter (the decisive out-of-regime test). **Re-running days is fine** (Greg) — chronological
  continuity beats blind-purity gymnastics.
- **The storage + weather stories run continuously** and are the backbone (see `decision_state`: level /
  vs-5yr surplus-deficit / phase + gas-weighted degree-day regime). They tick over in weekly units.

## 2. THE BIG ONE — the agent's logic runs ONE DAY INTO THE NEXT (Greg S94, load-bearing)
Reason CONTINUOUSLY. Each day's forecast FLOWS from the prior day's close, its trajectory, and the running
state — it is NOT a fresh isolated event.
- Carry forward: the prior day's ending price/level, where the block TREND stands, the running storage
  surplus/deficit, the running weather regime.
- Forecast day N+1's OPEN relative to day N's CLOSE (the overnight / weekend gap), THEN the intraday shape
  as a CONTINUATION of, or a TURN against, the running trajectory. A Monday is Friday's state + the weekend
  info gap repricing at the Sun-eve reopen — a continuation-with-a-gap, not a standalone.
- This is WHY moves stop looking like huge isolated events and WHY direction improves: continuation of the
  running path is the base case; each day is a continuation-or-turn question, not a coin-flip from flat.

## 3. Direction — the located problem (Group-3 result)
- **Block / fundamental direction from storage WORKS.** Group-3 (Sep 8-24): a comfortable +150 Bcf surplus
  called the block's real decline (3.10 -> 2.80). KEEP this — the running fundamental is a genuine
  block-direction signal.
- **Intraday per-day direction is the OPEN problem** (it stayed coin-flip even with the block right, because
  a day can pop hard AGAINST the trend before resuming it — e.g. 0916 spiked +$1330 up inside a downtrend).
  Do NOT force a from-flat open-time side. Instead: bias each day toward the RUNNING TREND (continuation base
  case), name candidate TURNS, and treat intraday side as a continuation-of-trajectory question. The
  day-into-day logic (sec 2) IS the direction fix.
- The live flow-nowcast (`dip_imb_level`, brain `direction.flow_nowcast`) stays the EXECUTION-layer intraday
  side call (for firing on the lagging Kalshi mark) — not an open-time forecast input.

## 4. Magnitude
- Still under-forecast on the big days (per-event, Groups 2 and 3). In the continuous frame, size each day's
  expected swing RANGE relative to the running trajectory and the regime: shoulder-season smaller, WINTER
  bigger (heating-demand + storage-drawdown volatility). The scale-vs-regime question
  (`magnitude.warm_season_scale_candidate`) resolves as we walk into winter — expect and size bigger there.

## 4b. REFINE UNBLINDED — the refine step MAY see the rich tape (Greg S94, decided)
The blind wall protects the FORECAST step (the skill test) — that stays absolutely blind. But REFINEMENT is
learning FROM what happened, and the coarse scorecard (guess vs actual) cannot teach the MECHANISM. So the
refine/tuning step MAY go UNBLINDED into PAST groups' tapes (`characterize_day`: per-leg flow/dipole/
exhaustion/turning-point fingerprints, the actual intraday structure) to learn WHY days moved — especially
the located INTRADAY-DIRECTION problem (on a missed day, study how the actual flow / turns / far-side
recruitment lined up with the real legs; that is where the flow-nowcast that calls the side lives).
**Two guardrails keep the loop honest:**
1. Unblinding is ONLY the refine step, ONLY on PAST (already-scored) groups' tapes. The forecast step for any
   future group stays blind (decision-time state only).
2. Extract GENERAL MECHANISMS + n, NEVER memorized day-specific outcomes ("spikes against the block trend
   revert when far-side depth is consumed", not "0916 went up then down"). Skill is ALWAYS judged on the
   NEXT blind group (true holdout) + forward-live — never the refined-on days.

## 5. Discipline (unchanged, non-negotiable)
- **NO averaging / pooling EVER** (Greg, hard). No mean, median, "X of N", pooled rate — anywhere, in any
  output or the brain. Per-event only; an extreme rate is a LEAD, individual days pinpoint the WHEN.
- **Blind wall:** the blind forecast uses decision-time state ONLY — never the tape for the group's days.
- **Continuous overlay for scoring** (all group days as one flowing price path, not reset-to-zero panels).
- Storage/weather conditioning kept; brain MERGES never overwrite (refine confidence + add plays); net-of-fee
  at the money step; provisional-until-live; NG and WTI kept separate; weather forecaster HANDS OFF.

## 5b. SEQUENCE — one more CONSECUTIVE run BEFORE the first refine (Greg S94)
Do NOT refine yet. Run one more CHRONOLOGICAL group first (Group-4) with the two S94 updates already live
(the day-into-day continuous reasoning + the running storage/weather story), and see if they lift things on
their own. THEN refine — and refine OFF CONSECUTIVE groups only (Group-3, Group-4, ...), **NEVER the scattered
Group-2**: its per-event lessons are contaminated by the isolated-event framing we just replaced, so refining
off it would bake the old distortion back in. The brain's s92.3 Group-2 plays stay as prior knowledge, but the
REFINE draws its mechanisms from the consecutive runs.

## 6. The per-group loop (in the Claude env)
1. `forecast_harness.py decision-state --days <contiguous 2-week block>` (enriched: surprise + storage +
   weather; blind-safe).
2. Spawn the blind agent with the brain + decision-state → it forecasts each day with the DAY-INTO-DAY
   continuous logic (sec 2), no tape, no averaging → `scratchpad/grpN_forecasts.json`.
3. Score: pull the block's tape from S3, fast-score (grep-prefilter + npz cache), render the CONTINUOUS
   overlay → review per-event.
4. Merge the per-event lessons into `ng_brain.json` (version bump), append `NG_BEHAVIOR_KNOWLEDGE.md`, commit.
5. Walk to the next contiguous 2-week block. Into winter is where the real regime test lives.

## 7. Data note
- The corrupt Monday stubs (Sep 29 -> Jan 2026, the S90/S92 flush bug) are being re-pulled from Databento
  (`scratchpad/repull_mondays.py`, ~$0.15/day) so the Oct+ walk is contiguous. Verify Mondays are healthy
  (>50KB, `_mon` name on S3) before a block that includes them.
