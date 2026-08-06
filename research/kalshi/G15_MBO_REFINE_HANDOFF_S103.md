# G15 MBO 5-SPECIALIST CAUSAL REFINE - HANDOFF (S103, chatgpt/ng-forecaster-s103-audit branch)

The first FULL run of the causal refinement LAYER on real MBO data. Result, honest helped/hurt verdict,
the 5 specialists' change requests, the HE24->HE1 coordination spec, and the next-iteration plan.

## RESULT

blind 9/12 dir (mean abs err 526 usd) -> refined 12/12 dir (mean abs err 72 usd).
Two-leg NGJ26(1008 pre-roll)->NGK26(996 post-roll) basis, 0320 seam never-traded, anchor 3.132 (NGJ26).
5 day-class specialists produce per-day posteriors; the coordinator SELECTS the owner per day (never
averages). Posterior update of the IMMUTABLE blind (forecasts/grp15.json untouched).

Renders: renders/ng_refine_s95/g15_mbo_blind_continuous.png, g15_mbo_refined_continuous.png.
Scores: renders/ng_refine_s95/g15_mbo_comparison.json.
Refined assembly: forecasts/grp15_mbo_refined.json. Per-specialist: forecasts/grp15_mbo_specialist_{A..E}.json.

The three big blind misses, fixed CAUSALLY (not curve-fit):
- 0318 Wed: blind called DOWN (-400); actual was a give-back-exhaustion TURN UP (+1900). Refined +1500
  (honest - the +1900 tail was partly reactive; the confirmed base was +1500). Owner C (core tape).
- 0326 Thu: blind OVER-sized a counter-print +900; actual round-tripped to ~flat (-60). Refined caught
  the absorption round-trip. Owner D (EIA).
- 0327 Fri (April expiry): blind called -350 crest-trim; actual RALLIED +1160 (covering-into-settle).
  Refined +1050. Owner E (expiry/roll).

## HONEST HELPED-OR-HURT VERDICT (falsification-first, per Greg)

- MBO TRADE-FLOW layer HELPED - decisive on 0327, 0323, 0326.
- MBO BOOK-RECONSTRUCTION layer HURT - div/imb whipsawed at every event boundary; trusted tick-by-tick
  it would have faded the 0327 covering rally and sold into the 0318 low. It was correctly STOOD DOWN:
  execution_authority=False on all 12 days, div_conviction <= 0.15. The book layer works AGAINST the
  call when trusted raw; it is only safe as confirmation once gated behind a trustworthiness floor.
- THE DISCRIMINATOR THAT WORKS: signed-flow-vs-price CONVICTION per phase leg
  (flow_conviction = sign(signed_flow)*sign(price_change)). ALIGNED delivers the band; NEGATIVE-under-
  rising = absorption/covering -> reversal/round-trip. onset_dir / absorb-flag / print-direction were
  IDENTICAL on 0319 and 0326 yet resolved oppositely - only flow-conviction separates them.
- DIRECTION stays with the D-1 trade tilt the blind already consumes; MBO is TURN + ABSORPTION
  confirmation only. The 0318 anticipatory bid-build was already in the D-1 tape the open-conditions
  blind saw - MBO's role there was confirmation, not anticipation (improved-vs-reacted test).

## THE 5 SPECIALISTS' CHANGE REQUESTS (folded into the brain, forward-test G16/G17 MBO)

Engine / feature-emission:
- ONE session-level data-quality verdict (book_trustworthy bit = execution_authority AND
  conviction>=floor AND book_complete) + only material transition bars - NOT 150+ repeated stand-down
  rows (Sunday tape was ~90% stand-down noise; the real decision "book trustworthy?" got buried).
- Phase-first, not tick-first: feed the phase table + session turns as the PRIMARY object; demote the
  minute-grain imb_flow series to a diagnostic (it flips faster than its own autocorrelation - a
  sampling artifact that actively misled on Mondays and 0324).
- Print-anchored windows on EIA-Thu: reset phases at the 10:30 ET print (pre-print / delivery /
  post-delivery), not volume-based boundaries that straddle the print and blur the causal read.
- Roll seam a first-class engine object: a leg_map (raw_symbol per date) + explicit seam_event
  traded=false so overnight_gap is forced to 0 and the offset is scoring-only.
- A named absorption_flag = signed-flow-vs-price-sign per phase (the 0327 covering diagnosis, currently
  hand-reconstructed).

## HE24 -> HE1 COORDINATION SPEC (the next-iteration build)

Principle: the day-boundary handoff carries STATE, never the day-net number. Each specialist starts from
the prior day's MARKET CONDITION so the block is one continuous path, not siloed guesses.

Carried state: close price + last-hour direction; running chain polarity + age (sessions since last
turn); cum-from-anchor vs nearest origin shelf; exhaustion-state flag (absorption building / climax
printed / turn confirmed-or-pending); flow-conviction verdict; data-quality state (was the read
trade-flow-only?); armed C1 flip-watch (never front-run); spent-vs-unrealized-ahead driver tag.

Turn ownership: a turn firing in the overnight HE24->HE1 seam belongs to the boundary - whoever owns the
day it REALIZES into inherits it, but sizes it using the PRIOR day's exhaustion-state flag (so 0318
doesn't compound a possibly-overshot tail).

Weekend seam: Sunday inherits the Friday CLOSE + chain state, not the Friday day-move; the reopen gap
SIGN is a non-derivable handoff (forecast the day-move from the anchor, treat the gap as noise).
Spent-vs-unrealized-ahead is the gap-ownership key: crest-trim -> Sunday can gap-fade; covering/holding
-> Sunday reopen likely continues the bid. A weekend carrying a contract roll passes the leg change as
never-traded.

## RENDER (S103 end - form-fit + the squiggle fix)

The render now FORM-FITS the intraday p50 path (shape from the forecast's own guess_curve /
path_p50_curve, close scaled to the scored day-move) instead of straight open->close segments, and adds a
dashed "re-anchored to actual open" line that isolates direction/shape skill from the compounding level
drift (Greg's "if blind started off on the price" point - on the blind figure the compound line drifts
low while the re-anchored line hugs the actual all block). SQUIGGLE FIX: the 2-hourly path grid runs
20->22->00->..->16->18->20 and wraps past midnight; the (hour-18)%24 x-mapping sent the post-midnight
tail back to the left edge so the line doubled back across each day. `_curve_pts` now UNWRAPS the clock.
DEFERRED (Greg, next session): print only the ACTUAL curve + the specialists' ACTUAL p50 path - drop the
"angular things" (the re-anchored dashed lines / any scaled reconstruction).

## NEXT ITERATION (state at S103 close)

1. HE24->HE1 handoff: the BUILDER IS BUILT + validated (`he24_he1_handoff.py` ->
   `forecasts/g15_he24_he1_handoffs.json`, the full G15 boundary chain carrying prior-day realized exit
   STATE, not the day-net). The round-2 specialist re-run WITH the handoff injected was launched but
   STOPPED before writing (committed round-1 12/12 state intact) - DEFERRED to next session: re-run the
   5 specialists round 2, re-coordinate, re-score, re-render; target honest under-100 every day.
2. WATCH THE COORDINATOR: `coordinate_g15_mbo.py` today only SELECTS the owner per day (the OWNER map)
   and assembles - no forecast/average logic. Next session add an explicit GUARD asserting it never
   emits a day-move no specialist owns (enforce, do not assume).
3. Engine change requests (book_trustworthy bit, phase-first emission, print-anchored EIA windows,
   leg_map/seam_event, absorption_flag) - speed + safety wins that remove the manual triage this run.
4. Then carry the layer forward to G16/G17 MBO as the forward test. "Refine the refinement" until the
   numbers are better before the layer is trusted on unseen blocks.

## BRAIN

Merged to s102.4 (36 plays preserved, no play changes): doctrine_tier3.refinement_architecture_s103
(the doctrine) + doctrine_tier3.mbo_refinement_g15_findings (this result + the lesson proposals, forward
target G16/G17 MBO). Human-readable doctrine source: knowledge/refinement_architecture_doctrine.md.
