# REFINEMENT ARCHITECTURE DOCTRINE (Greg, S103) - MERGE INTO ng_brain.json AFTER the G15 MBO run

STATUS: **SUPERSEDED S115 - DO NOT READ THIS FILE, AND DO NOT PUT IT BACK IN ANY READ LIST.**
The brain is the only copy. Its last un-merged field (the FLOW line below) was merged at S115
into `doctrine.refinement_architecture`, and RFN-1's read list no longer names this file.
Kept as a dated RECORD of what was written at S103, never as a source. Greg, S115: 'merge the
reasoning file' - two copies of one doctrine with one of them served to agents is the S105
defect (blind_shared.md said USE the firehose while blind_class_* said NO MBO), and it cost a
session to diagnose.

ORIGINAL STATUS LINE: MERGED (S103, brain s102.4). Now lives in ng_brain.json ->
doctrine_tier3.refinement_architecture_s103, effective G16/G17 MBO. The G15 MBO refine result and the
5-specialist lesson proposals landed alongside it at doctrine_tier3.mbo_refinement_g15_findings. This
file is kept as the human-readable source of the doctrine.

## THE LOAD-BEARING PRINCIPLE
The OLD prediction framework STAYS as the CORE forecasting model - it already produces useful
directional/path information. The new L1 + trades + MBO work is NOT a replacement predictor. It is a
CAUSAL REFINEMENT LAYER that decides whether the original (blind) forecast is still valid as the session
unfolds. Do NOT replace a working predictor with a reactive order-flow model. The refined output is a
POSTERIOR UPDATE OF THE IMMUTABLE BLIND, not a new forecast from scratch.

## THE PIECES, IN ORDER
1. IMMUTABLE BLIND FORECAST = the starting map (direction, magnitude, timing, turns, daily path; from
   pre-cutoff info only). Never rewritten.
2. FRIDAY ANCHOR = the starting market state (final traded hour before the block: price, direction,
   volume, signed flow, activity, efficiency, contract identity, queue). First Sunday update is
   interpreted RELATIVE to this - the only way to tell genuine weekend repricing from noise.
3. NORMALIZED L1 + TRADES + DEFINITIONS + MBO = one chronological evidence stream feeding ONE feature
   engine (none predict independently). Definitions = active contract/instrument; Trades = executed
   pressure; L1 = best bid/ask/spread/top liquidity; MBO = order add/cancel/modify/deplete/replenish.
4. NGLiveOperator + FEATURE STATES = events -> behavior (signed flow, flow accel, activity, price
   efficiency, queue depletion/replenishment, far-side recruitment, divergence, exhaustion, spread
   condition, data quality). Emit ONLY at valid completed-event boundaries - never chase ticks or react
   to incomplete books.
5. SESSION SPECIALISTS = interpret the SAME feature state by session structure (a feature means
   different things Sunday vs normal Tue vs EIA Thu vs expiry/roll Fri).
6. COORDINATOR = selects the specialist matching the day + market state; NEVER averages opposing
   forecasts; records which specialist, why, what dissent, why the alternative was rejected.
7. POSTERIOR REFINEMENT AGENT = starts from the blind probabilities and adjusts ONLY when causal
   evidence is MATERIAL. Can confirm / reduce confidence / delay the move / resize magnitude / identify
   a turn / change continuation-vs-reversal / stand down. Emits SEPARATE outputs, not one vague call:
   direction-by-horizon; expected magnitude; onset & turn timing; trend-vs-chop; continuation-vs-
   reversal; path quantiles; confidence; invalidation conditions. Explains meaningful STATE changes, not
   every tick.
8. DATA QUALITY / STAND-DOWN = controls authority. MBO gets authority only when the reconstructed book
   is trustworthy. Sequence gaps / bad defs / corrupt sessions / backward timestamps / incomplete
   snapshots / implausible queue -> reduce confidence or disable book-based conclusions. Book unreliable
   but trades valid -> fall back to trade-flow + L1 and LABEL the limitation. Weak data must never
   create false precision.
9. SCORING = what actually improved. Score blind vs refined SEPARATELY; direction alone is insufficient
   - measure magnitude, intraday path, onset, turns, MFE, MAE, trend-vs-chop, confidence calibration.
   This distinguishes genuine improvement from merely REACTING after the move.
10. LESSON PROPOSALS = learn without contaminating the model. Propose mechanisms with supporting events,
    counterexamples, scope, n, confidence, and forward validation on G16/G17. Never auto-rewrite the brain.

## FLOW
old framework produces the map -> Friday anchor sets the starting state -> normalized market data ->
feature states -> session specialist interprets -> coordinator selects -> posterior agent UPDATES the
blind -> scoring decides if the update helped -> lesson proposals tested forward.

GOAL: preserve what the old framework did well; use the new data to improve TIMING, MAGNITUDE, TURNS,
and CONFIDENCE - not to replace it.
