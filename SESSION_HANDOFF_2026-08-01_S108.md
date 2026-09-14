# SESSION HANDOFF - 2026-08-01, S108 (G20 refine done; G21 walked; EIGHT data holes; brain s103.2 -> s103.6)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain **s103.2 -> s103.6, 67 plays**.

This session completed G20, walked G21 end to end, and found **three more silent data holes** - one of
which had been corrupting the blind's primary input on 40% of a block. It also **retracted a play merged
one group earlier**, on the author's own evidence.

## THE HEADLINE

- **G20 refine r2: 10/10, mean abs err 64**, forward-curve drift -2560 -> -360.
- **G21 blind 5/10** (per-day |err| [1500,1080,960,790,620,470,430,240,160,70], sum 6320) ->
  **refine r1 10/10, EVERY DAY UNDER 100, worst day 80** (per-day [80,60,30,30,30,20,20,20,20,20],
  sum 330). Five direction flips, each on named causal evidence.
- **The persistent DOWN lean is gone.** Blind block cum ran -2040 / -1720 / -1220 / -700 across
  G17-G20 and is **+740** on G21 - the first positive of the walk.
- **THREE NEW DATA HOLES (#7, #8, and the filename collision) - ALL THREE FIXED**, plus five other
  harness/brain fixes and a **retraction of a play merged one group earlier**.

## THE SCORING RULE THAT CHANGED (Greg, load-bearing)

**We cannot average above and below.** A day high by 4,000 and a day low by 4,000 net to zero on a
forecaster that was catastrophically wrong twice. And **mean error is a dashboard number, never a
diagnosis - fix off individual events.**

This lands directly on the metric the session had been leading with. Measured across the walk, with
"survives" = |drift| as a share of total absolute error (everything else CANCELLED):

```
grp  sum|err|    DRIFT  survives  >1000  >500
 17      4510     -970       22%      1     3
 18      5210    -2330       45%      0     6
 19      9390    -2370       25%      3     9
 20      7880    -2560       32%      4     5
 21      6320     +960       15%      2     5
```

**G21 has the LOWEST survival rate of any block** - drift flatters it MORE than any group measured.
Stated honestly: drift -2560 -> +960 is a "62% improvement"; sum|err| 7880 -> 6320 is a **20%**
improvement. The 42-point gap is cancellation. The lean fix DE-CORRELATED the errors; it did not shrink
them. `blind_score_nonpooled.py` now prints per-day, sum|err|, drift AND the survival ratio together.

**The cost of ignoring this rule, measured**: G20 credited D's pre-print generator with 2,090 **from day
nets - the intraday check was never run**. G21 decomposed all four prints it has produced and found the
SELECTION limb survives 4/4 while the **TIMING limb is refuted 1 of 4** (on 0618, its own firing day, the
06:00-10:00 window delivered exactly zero; onset was 11:06, 36 minutes AFTER the print). A right day-net
carried a false mechanism into the brain, and the mechanism is what gets extrapolated.

## THE EIGHT HOLES - and the progression matters

S107 found six, all EMPTY blocks. `state_health` was built for exactly that. This session found two more
and they are each a different KIND, which is why the existing gate could not see them:

| # | defect | kind | caught by |
|---|--------|------|-----------|
| 1-6 | S107's six | **empty** | `state_health` (presence) |
| 7 | `nws_temp` fetch tail | **wrong value** | reconciling a day against a later pull |
| 8 | `tape_conditions` off-instrument after a roll | **off-instrument** | reconciling against the scored leg |

**#7 THE PARTIAL FETCH TAIL.** The LAST day of any `nws_temp` fetch is computed on incomplete hours and
is wrong, while reporting `coverage: 1.0` and `n_stations: 16`. Measured twice: 2026-07-13 read gw_cdd
**8.034 / mod_cool** as a pull tail and **13.548 / hard_cool** once a later day was fetched - a 68% error
and a REGIME FLIP on a day inside G23's window, against neighbours of 14.2 and 15.5. 07-16, which had a
successor inside its own pull, was byte-identical across both. Now flagged `provisional_tail` and HARD in
`state_health`; a later pull clears the flag by itself.

**#8 OFF-INSTRUMENT, and the hardest of the eight.** `_tape_day_stats` and `flow_read._load_trades` both
select their source by "whichever continuous store has MORE trades". After a roll that is the DEFERRED
contract:

```
session   NGN26 leg (scored)   tape_conditions served   ratio   source_store
20260610             43572                    43572     1.00   nymex_cont_n0
20260615             34221                     6262     0.18   nymex_cont_n0
20260616             37477                     6923     0.18   nymex_cont_n0
20260617             44127                    18317     0.42   nymex_cont_n1
20260618             37378                    22490     0.60   nymex_cont_n1
```

Served `session_signed_flow` was **SIGN-FLIPPED on 0615 and 0617 and destroyed on 0618** (-1 against a
real -3,670). `tape_conditions` is the blind's ONLY open-time flow channel and is declared
`never_masked` - so on four days the blind was ALSO handed a wrong-instrument, sign-flipped flow read.
**The doctrine says the blind's one deliberate mask is the price curve.** This was an undeclared handicap.

**Why it is the hardest**: the block is fully populated, internally consistent, and recomputes coherently
off a different contract. It even MANUFACTURED A FALSE MECHANISM - C's blind-run "week-2 delivery-window
thinning", with three corroborating markers (spread doubling, unsided fraction tripling, `leg_count`
preserved), every one of which is also what an off-instrument read looks like. **D independently
"verified" the same artifact as a real liquidity migration by checking internal consistency.**
Consistency was never the test. Only RECONCILIATION against an independent measurement of the same
session on the SAME instrument settles it.

FIXED AT THE SOURCE: `decision_state` takes a group, `stage_group` passes `--group`, and both the harness
and `flow_read` resolve `gc.leg_for(gid, session)` and read the SCORED LEG - which is authoritative and
never overridden on trade count. `source_store` now declares `leg:ng_mbo_ngq26`. `tape_reconcile.py`
blocks any residual case at stage time. Blast radius: **G20 clean, G21 four days, G22 clean, G23 one day
(now fixed and unblocked)**.

## THE B_SHARE NORMALIZATION DEFECT (the lean)

Every `*_b_share` divided by TOTAL volume, but the tape carries a third side value ('N') worth **13.49%
of volume** across 223 sessions - denominator only, never numerator.

```
session_b_share AS SERVED    mean 0.4078   clears 0.50 on   5/223  =  2.2%
session_b_share TWO-SIDED    mean 0.4999   clears 0.50 on 107/223  = 48.0%
```

**0.4999 is the tell** - two-sided aggressor balance over 223 sessions lands exactly on the 50/50 the
physics requires. Not a constant shift: corr 0.532, and the two disagree about which side of 0.50 a
session sits on **45.7%** of the time. `session_signed_flow` was never affected (no denominator), which
is why nothing looked broken.

Fixed ADDITIVELY - both series served plus `unsided_volume_frac`. Only THEORETICALLY-motivated 0.50 bars
moved; empirically-fitted bars keep reading the original series.

**And the first fix was INCOMPLETE.** C found that `structure.accumulation_arm_turn` carries the semantic
in PROSE ("under a sub-0.50 sell tape") alongside a fitted 0.55 bar - my regex over numeric bars missed
it, and it is a SIGN play. `selector.midblock_right_the_ship` inherits it. **A semantic can live in prose
as well as in a bar.** Both re-pointed in s103.5; `midweek.giveback_exhaustion_reversal_recognition` was
checked and recorded CLEAR so the partially-correct claim is not re-litigated.

## THE MONDAY STUB

`_tape_conditions_block` returned the FIRST day with a tape file, so on a Monday it stopped at the ~2h
Sunday reopen and **the Friday was never consulted**: 78-1,245 trades with 0-2 big prints against
30,000-58,000 on every other day - 0.2% to 3% of a normal tape, on the one day class the walk declares as
its focus. Fixed additively: `tape_conditions.prior_full_session` carries the Friday alongside the stub,
with `prior_session_is_reopen_stub` declaring itself. A stub is identified by the CME trade-date
convention (the reopen falls on a Sunday), not a magic threshold.

**It paid immediately.** A's G21 bridge surfaced a generator E structurally could not see - E was
forecasting 0612 and could not see 0612's own tape, which reaches B as `prior_full_session` (+2,716 sflow,
+2,865 of the entire session net in the final phase, big prints 0.597 on 68).

## WHAT ELSE WAS BUILT

- **`session_bootstrap.py`** - one command from empty to ready (writes keys chmod 600, STS-verifies
  printing only the account tail, restores, prints the gate).
- **SessionStart hook** extended to restore automatically when creds are present and **no-op LOUDLY**
  when they are not.
- **Stage-time exit states** - the last thing in a staged group's run cycle that reached into `data/`.
  A group staged at S108+ runs BOTH rounds with no data plane at all. Proven byte-identical with the
  legs moved off disk.
- **Blind coordinator speaks the engine schema natively** - removing a per-run hand-built alias that
  lived in the scratchpad and did not survive a session. Regression-proven byte-identical on G20.
- **`chain_regime_age_sessions`** - resolves a three-way definition collision additively. Reproduces E's
  prediction independently (0605 chain_age 2 -> regime age 7, so the age>=5 arm fires).
- **`phase_volume_lots`** - E filed this against its OWN play; two plays merged as blind-available were
  refine-only as served.
- **`squeeze_watch` calendar limb derived live** - it reported `active: false` at dte=14 against a live
  dte of 7/6/5, a confident FALSE NEGATIVE inside its own window, on four days.
- **`blind_score_nonpooled.py`, `blind_drift_trend.py`, `blind_lean_decomp.py`,
  `bshare_normalization_probe.py`, `blind_input_audit.py`** - all committed reproducible.

## THE FILENAME COLLISION - FIXED at close-out, third occurrence

The blind writes `grp<N>_mbo_specialist_<X>.json`; the refine round 1 wants the SAME name; the archive
step used `cp`. **Every existing guard passed on the stale blind file** - present, correct day, numeric
magnitude, right owner. All of those are true of the blind's own output, which is exactly why it kept
surviving. On G21 **six of ten days were one command from being assembled as the refine**: B's refine
never wrote (its agent died) and C wrote to a slipped filename, leaving the blind copies in place for
both.

FIXED, with two defences deliberately different in kind:

- **`archive_blind.py`** archives by **MOVE**, so the canonical name is left ABSENT and a specialist that
  fails to write produces a HARD "owner posterior missing" failure instead of a silent blind read. It
  refuses to run before the blind is coordinated, so the blind's own numbers cannot be lost.
- **`group_coordinate_refine.assert_not_the_blind()`** hashes every round-1 posterior against its blind
  archive and refuses a byte-identical match - catching a hand-recopy that the move discipline misses.

NEGATIVE-TESTED on the exact G21 near-miss: planting the blind B at the refine filename hard-fails with
the cause and the fix named; restoring the real refine coordinates normally at 10/10, mean 33.

**The transferable lesson**: the only thing distinguishing a stale blind file from a refine is the BYTES.
Every field-level check passes. That is the same shape as hole #8, where the block was populated and
self-consistent and only reconciliation against an independent measurement settled it. **Field checks
cannot catch a wrong-but-well-formed input; only a comparison against an independent source can.**

## STATE OF THE WALK

- **G20 COMPLETE**: blind 6/10 err 788 -> r1 10/10 err 79 -> **r2 10/10 err 64**, drift -2560 -> -360.
- **G21 COMPLETE (r1)**: blind 5/10 err 632 -> **refine 10/10, worst day 80**. Round 2 NOT run.
- **G22 and G23 staged, PASSING, and reconciling** on s103.6 with all fixes live.
- **Brain s103.6, 67 plays.** Backups at s103.2 / s103.3 / s103.4 / s103.5.

## OPEN

1. **The live orchestrator** - A's own day and B's block-open day have no upstream dependency, yet the
   fixed E->A->B order serializes them. ~2 of 3 waves recoverable on a block like G21.
2. **`options_surface` strike ladder** still off the contract's price scale (top-OI strikes 0.25-0.35
   against a ~2.9 front), so the pin read is not computable on the day it matters.
3. **G21 refine round 2** was not run (r1 already at worst-day 80).
4. **Per-day blind state slices** - measured: the token win is small (11% de-dup, 8% run-timestamps) and
   causal slicing costs MORE than it saves. The real constraint is wall-clock, not tokens.
5. **KEYS DO NOT ROTATE DURING THE WALK** - standing decision, do not act on it and do not re-raise.

CLOSED at close-out: the filename collision (above), and all three of the fixes queued for G22
(the b_share re-point completion, `phase_volume`, the live `squeeze_watch` calendar limb).

## THE THING TO CARRY FORWARD

Every defect this session was found by a specialist reading carefully, not by a gate. `state_health`
catches empty; it cannot catch wrong-value, off-instrument, or stale-file. **Three specialists refuted or
withdrew their OWN merged work this run** - D the timing limb, A both `thin_session_range_invariance` and
its own COT-residual meter, C its week-2 thinning finding. That is the machine working, and it is worth
more than any single group's score.
