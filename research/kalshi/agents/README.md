# NG FORECASTER AGENTS — canonical drop-in files (S103 Greg-ordered; S104.1 = the 5-specialist era)

**The point (Greg, S103): these agent files are STATIC. You drop the SAME files into every group and
run immediately. The ONLY things that change group-to-group are (1) the BRAIN (`knowledge/ng_brain.json`,
which updates via the refine step) and (2) the GROUP DATA (the decision-state file + anchor + basis).
No re-authoring prompts per group. No per-group selftests. No re-pulling the shared stores.**

## THE DATA DOCTRINE (Greg, LOAD-BEARING, stated repeatedly — read this first)
**BOTH agents get EVERYTHING — the whole kitchen sink — to choose from. The blind's ONE and ONLY
deliberate mask is the PRICE CURVE.** The blind AND the refine both receive: all fundamentals, structure,
calendar, positioning/COT, weather, storage, AND the FULL MBO order-flow read (signed-flow imbalance,
UNBALANCED SIDES = buy-vs-sell aggressor, absorption/divergence) of every decision-legit window (prior
sessions in full + the current day's PRE-DECISION reopen/overnight flow for a rolling daily forecast).
The ONLY thing withheld from the blind is the PRICE CURVE — settles, nets, day-moves, levels, spreads,
and the target-day price PATH it forecasts. Nothing else. (Causality still holds: neither sees the
FUTURE — that is physics, not a mask.) The `dip_imb_level`-forbidden rule is REPEALED for decision-legit
windows.

**WHY we mask only the price curve — it is not a handicap, it is how he LEARNS (Greg).** We are not
trying to make it harder or trick him. Denying ONLY the answer (the price) forces him to build the
forecast from the underlying MARKET FORCES themselves — order-flow imbalance and unbalanced sides,
positioning/COT extremity, absorption/divergence, fundamentals, weather, storage, structure, the
futures->Kalshi lead. Read the price and he learns nothing; read the forces and he sharpens his mastery
of every one of them. That mastery IS the edge — it is what makes him a better FORWARD-CURVE BUILDER,
which is the whole product. So give him EVERY market force in full; withhold only the price he is there
to predict.

## PROCESS DISCIPLINE (Greg, S105): stage ALL groups' DATA ready, but RUN one group at a time
Have every group "sitting ready with its data fixed" — turnkey, so all we do is turn the key. But NEVER
start running (forecasting) multiple groups at once: **one group = two weeks**, finish its full cycle,
then the next. Running ahead is scope creep waiting to happen.

## THE OPERATING FRAME (Greg, S104 — supersedes the 3-angle-panel loop below for new groups)
- **FIVE day-class specialists for BOTH blind and refine, every run**: A weekend-seam / B Monday /
  C core / D Thu-EIA / E Fri-expiry. Day-class lenses = `mbo_specialist_{A..E}.md` (refine);
  the blind runs the same five roles behind the `blind_shared.md` wall (thin blind lens files
  `blind_class_{A..E}.md` — write once from the specialist lenses minus realized/MBO content).
- **FOCUS = FRIDAY AND MONDAY.** Friday is the cascade root (11/22 Fridays wrong-signed; 10/14 bad
  Mondays root to a mis-read Friday exit). E must emit the 9-field weekend `handoff_out`
  (exit_type + monday_bias); E carries the PRIOR-OVER-STATE fix (a turn/exhaustion GATE checked
  before any Friday sign is emitted — his self-analysis: one flaw owned 72% of his misses).
- **SUNDAY FOLD (decided S104.1)**: the ~2h Sunday reopen belongs to MONDAY (CME trade-date
  convention). Monday = Fri close -> Mon close. A owns holiday/extended-weekend reopens ONLY.
- **WEEKEND SEAM PAIRING (S104.1)**: the week-open chain is **E -> A -> B**. A bridges E's Friday
  exit to B's Monday (bridge read: exit sanity-check, reopen scenarios, gap ownership,
  driver-realization check, live reopen watch). **A informs, B decides — B alone owns the Monday
  number.** B records taken-vs-overridden.
- **COORDINATOR: SELECT/ASSEMBLE under the GUARD** (pattern: `coordinate_g15_mbo.py`): every emitted
  day-move must be verbatim the single owner's number — missing/non-numeric/wrong-owner = hard
  failure, never a fallback. **+ FRIDAY SIGN-OFF**: the coordinator refuses to assemble any
  weekend-feeding day whose posterior lacks `handoff_out` (existence enforced; content stays the
  owner's call). Port the guard to every new coordinator.
- **RENDERS**: actual curve + the forecast's OWN p50 path only — no re-anchored/scaled lines, no
  bridges across closed market. **Group windows: Sunday reopen -> the SECOND Friday, always.**
  Target: **honest under-100 every day**.

## The files (do NOT rewrite per group)
- `blind_shared.md` — shared blind directive (the wall + output contract; group-agnostic).
- `mbo_refine_shared.md` + `mbo_specialist_{A,B,C,D,E}.md` — the 5-specialist day-class files
  (shared doctrine + per-role lenses, incl. A's weekend-seam role, B's hand-in-hand consumption,
  the round-2 HE24->HE1 handoff protocol, and the coordinator contract).
- `refine.md` — the single-agent unblinded refine directive (pre-S104 pattern; kept for reference).
- `blind_angle_{storage,positioning,weather}.md` — the S103 3-angle blind panel (SUPERSEDED for new
  groups by the 5-specialist blind; kept for the walked record and as evidence-angle references).

## SHARED SUBSTRATE — done ONCE per session (see GROUP_PRECHECK_S103.md)
Creds (env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY for platform_sync/boto3) + full-history
stores pulled once + the roll map. Covers every group. Do not repeat.

## PER-GROUP LOOP (5-specialist era — turnkey)
1. **State**: `forecast_harness.py decision-state --days <sessions> --mask-after <anchorDate> --out
   renders/ng_refine_s95/grp<N>_state.json` (sessions per the SUNDAY FOLD — no standalone Sundays;
   anchor = prior Fri actual close + last-hour dir).
2. **Tape**: pull the group's day-files on the PER-CONTRACT legs (NG.n.0 is the wrong leg near a
   Kalshi roll — G15 pattern: `nymex/ng_mbo_ngj26/` pre-roll + year-pull post-roll).
3. **Blind — SEQUENCED SPAWN, NOT parallel (S105 fix; the E->A->B chain must be LIVE).** Parallel
   spawn broke the week-open chain in G17: A and B ran simultaneously, so B never consumed A's bridge
   and over-sized the worst Monday (0420 blind -400 vs -60 actual; B's post-mortem: ~79% of that miss
   was the missing live bridge, ~21% skill). The chain has a DEPENDENCY ORDER, so spawn in waves:
   - **Wave 1 (parallel):** C (core) + D (EIA) + E (Fri/roll). They have no cross-specialist
     dependency. E emits its 9-field `handoff_out` on every weekend-feeding Friday.
   - **Wave 2:** A (weekend-seam) — spawn AFTER E finishes; A consumes E's `handoff_out` and produces
     the weekend bridge read per Monday.
   - **Wave 3:** B (Monday) — spawn AFTER A finishes; B consumes A's bridge LIVE before committing the
     Monday number (A informs, B decides, B owns it).
   All behind the wall (blind_shared.md), model opus. Sequencing alone recovers ~80% of the 0420
   magnitude miss and makes the Monday number decision-legit instead of borrowed.
   **ESCALATION (Greg S105): if a fixed sequence still causes issues (a dependency that a static order
   can't satisfy, ordering conflicts), build a LIVE ORCHESTRATOR** that resolves the dependency graph
   dynamically (C,D,E -> A -> B) rather than a hand-sequenced spawn — the coordinator becomes an
   orchestrator, not just a post-hoc selector.
4. **Coordinate (per-event)**: the coordinator SELECTS the owner per day under the GUARD (+ Friday
   sign-off) and assembles ONE `forecasts/grp<N>.json`. No votes, no averages, no fallbacks. NOTE: this
   is the POST-HOC assembly guard - it does NOT orchestrate the live handoff (that is the sequenced
   spawn in step 3). A selector can only pick an already-committed number; the E->A->B fix is upstream.
5. **Score + render**: `continuous_score.py` + the two-leg hand-roll actual (coordinate_g15_mbo.py
   `build_actual` pattern on a seam block; `continuous_rt.py` generic only for clean blocks).
   Render = actual + own p50 path only. PRINT the render.
6. **HARD PAUSE** -> Greg reviews the blind score.
7. **Refine**: the SAME 5 specialists, unblinded (`mbo_refine_shared.md` + lenses), **same SEQUENCED
   spawn as step 3** (C,D,E wave 1 -> A wave 2 -> B wave 3) so B consumes A's bridge live here too
   (in G17 the refine ran parallel and B's Monday number was ~half-carried by A's bridge anyway - a
   sequenced refine makes that dependency explicit and decision-legit). Each on its owned days ->
   coordinator re-assembles (guarded) -> proposal file(s), NEVER a direct brain edit. Adjudicate
   (incumbents byte-identical), render, PRINT, HARD PAUSE, MERGE on Greg's go. Commit+push.

## HE24 -> HE1 COORDINATION — THE ROUND-2 PASS, FOR BOTH RUNS (Greg, load-bearing)
A block is ONE continuous path, not 10 siloed days: each day's last hour (HE24 exit) hands off to the
next day's first hour (HE1 open). BOTH the blind and the refine run this **two-round coordinated
structure** — round 1 alone is not enough (it leaves the days independent; the curve does not flow):

- **Round 1**: specialists forecast their owned days (blind: sequenced spawn per step 3; refine per step 7).
- **Build the HE24->HE1 handoff chain**: `group_he24_he1_handoff.py --source {blind|actual} <gid>`.
  Each day's `handoff_in` = the PRIOR day's exit STATE (close, last-hour dir/flow, close_off_low, low/high
  timing, chain polarity+age, cum-from-anchor) + the prior owner's round-1 read. It carries STATE, NEVER
  a day-net number — the receiver interprets it.
  - **REFINE `--source actual`**: exit state from the ACTUAL prior-day MBO tape (the refine sees price).
    Precomputed once, injected into a PARALLEL round-2 re-run.
  - **BLIND `--source blind`**: exit state from each day's ROUND-1 FORECAST (from `grp<N>.json`), because
    the blind is walled from the actual price. Carries the forecast close + forecast chain state +
    forecast last-hour dir (signed flow is null in the blind - price masked, per the data doctrine).
- **Round 2**: each specialist STARTS FROM its round-1 posterior and TIGHTENS magnitude/timing off the
  incoming handoff — a turn realizing in the overnight seam is sized by the prior-day exhaustion, never
  front-run; direction changes need NEW causal evidence, not re-reading. Emit the OUTGOING handoff.
  Coordinate round 2 under the guard.
- **Evidence it works (magnitude/timing only, zero direction changes)**: G15 refine 72 -> 66; G17 refine
  24 -> 11 (10/10 held). The day-into-day coordination roughly HALVED the error.

The two mechanisms are complementary: the **live sequenced spawn** (step 3) is the WITHIN-round
coordination the blind needs because it has no precomputed actual to inject; the **round-2 HE24->HE1
handoff** is the BETWEEN-round coordination both runs use. Blind gets both; refine gets the round-2 pass
(its handoffs are precomputed from the actual, so it can run round-2 parallel).

## WHY (the record)
S103: G15 refine ran as one agent; G16 blind as the 3-angle panel; those became canonical files.
S104: the G15 MBO refine ran as 5 day-class specialists (blind 526 -> r1 72 -> r2 66 err, 12/12) and
Greg ordered the 5-specialist structure for BOTH phases + the Friday/Monday cascade cleanup (brain
s102.5, 47 plays). S104.1: Sunday fold + E->A->B week-open chain + coordinator Friday sign-off.
From here we spin these files unchanged; only the brain + group data move.

S105 (brain -> s102.9): the mid-block under-action fixes (turn/exhaustion gate, EIA over-extension gate,
accumulation arm, right-the-ship, covering-self-limiting) + the DATA DOCTRINE build (the blind now gets
the full non-price MBO+L1 flow read - flow_read.py - masked only on price) + the sequenced E->A->B panel
+ the two-round HE24->HE1 coordination for both runs. Forward record:
- **G17**: blind 5/10 -> refine r1 10/10 (err 24) -> r2 10/10 (err 11).
- **G18** (first UN-HAMSTRUNG blind, covering-rally block): blind 5/10 BUT net P&L +440 (a naive
  always-short LOST -610) - the blind sized its catches (0430, 0505) bigger than its misses. **P&L is the
  scoreboard, not direction hit-rate.** Refine r1 10/10 (err 30) - flipped every covering-up day the
  price-walled blind called down. The un-hamstrung read demonstrably sharpened reasoning (D split a
  same-net-flow pair via big_print_b_share; C differentiated 3 same-b_share sessions) - NECESSARY but not
  sufficient: the block-level regime prior still leaned bearish vs a covering rally (the open gap).
- **The covering-absorption discriminator** (new play, G18 A/B/C/E convergent): signed-flow-vs-price
  CONVICTION, not raw imbalance, sorts direction - SELL absorbed under rising price = covering -> UP;
  BUY absorbed under falling price = failing -> DOWN; ALIGNED = delivered. A crowded short covering-
  absorbed at the Friday close reprices UP on the Monday catch-up (buy-absorption at the close is a
  directional tell, not exhaustion).
