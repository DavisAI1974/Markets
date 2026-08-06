# DROP-IN BOX - S109 (start a FRESH session with this)

## BOX 1 - BRANCH. PASTE THIS ALONE, FIRST, AND READ THE VERDICT BEFORE CONTINUING.

```bash
B=claude/kalshi-agents-coordinator-guard-1175nr
git fetch origin $B && git checkout -B $B origin/$B
echo "--------------------------------------------------------------"
echo "branch : $(git rev-parse --abbrev-ref HEAD)"
echo "tip    : $(git log --oneline -1)"
echo "tree   : $(git ls-files | wc -l) files tracked"
echo "expect : S108 close-out (or later)"
test -f research/kalshi/tape_reconcile.py \
  && test -f SESSION_HANDOFF_2026-08-01_S108.md \
  && test "$(git rev-parse --abbrev-ref HEAD)" = "$B" \
  && echo "BRANCH OK - safe to paste the drop-in box" \
  || echo "BRANCH FAILED - do NOT continue. Re-run this box; if it fails again, say so."
```

Why this is separate: the harness assigns every session its own auto-named branch and that branch is
NEVER the work. Two traps it guards. The STALE-TIP trap: the session is cut from an old tip and looks
fine. The EMPTY-CHECKOUT trap: the assigned branch does not exist on the remote, so the container comes
up on an orphan `master` with ZERO commits and an EMPTY TREE - every file read fails and the session
looks broken. The two sentinel files were both created in S108, so their presence rules out both traps
in one test. This box deliberately does NOT touch credentials or data, so a branch failure can never be
confused with a creds failure.

## 0. Read order (only after BOX 1 reports BRANCH OK)

`SESSION_HANDOFF_2026-08-01_S108.md` (in full) -> `research/kalshi/agents/README.md` -> `CLAUDE.md`
header.

## 1. ONE COMMAND FROM EMPTY TO READY

```bash
pip install --quiet numpy pandas matplotlib boto3 databento
python research/kalshi/session_bootstrap.py --aws-id <ID> --aws-secret <SECRET> --bento <KEY>
```

Writes all three key files chmod 600, STS-verifies (printing ONLY pass/fail and the account tail),
restores the data plane, rebuilds `vol_regime`, then prints the completeness gate per group.

Keys are NEVER committed and do NOT survive a session. That is expected, not a bug. Neither does
`data/`, nor the scratchpad - anything worth keeping must be committed.

**A group staged at S108 or later runs BOTH rounds with NO data plane at all.** The restore is needed
for STAGING and for pre-S108 groups' round-2 handoff only. `session_bootstrap.py --verify-only` reports
what is present without writing anything.

ALWAYS run AWS/boto3 under `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY` if you call it directly -
the container injects PLACEHOLDER creds that OVERRIDE `~/.aws/credentials` in boto3's precedence, so a
known-good key returns `InvalidClientTokenId`. `session_bootstrap.py` does this for you.

## 2. STATE

- **Brain s103.6, 67 plays.** Backups at s103.2 / s103.3 / s103.4 / s103.5.
- **G20 COMPLETE**: blind 6/10 err 788 -> r1 79 -> **r2 64**, drift -2560 -> -360.
- **G21 COMPLETE (r1)**: blind 5/10 err 632 -> **refine 10/10, every day under 100, worst day 80**.
  Round 2 not run.
- **G22 and G23 staged, PASSING `state_health` AND reconciling to the scored leg.**
- **NEXT = G22.**

## 3. THE TWO RULES THAT CHANGED IN S108 (Greg, load-bearing)

- **NEVER average above and below.** Drift is a SUM OF SIGNED ERRORS and cancels: a day high by 4,000
  and a day low by 4,000 net to zero on a forecaster that was catastrophically wrong twice. Report
  per-day, `sum|err|`, drift AND the survival ratio together: `blind_score_nonpooled.py`.
- **MEAN ERROR IS A DASHBOARD NUMBER, NEVER A DIAGNOSIS - fix off individual events.** Where a
  specialist claims a MECHANISM, check the mechanism was tested and not just the net. That check is what
  caught G20 banking a pre-print generator from day nets whose TIMING limb was refuted 1 of 4.

## 4. DO THIS, IN ORDER

1. **G22 blind.** Sequenced spawn C+D+E -> A -> B, model opus. Blind input = brain + the price-masked
   `grp22_state.json` ONLY. Coordinate with `group_coordinate_blind.py g22` (it speaks the engine schema
   natively now - no hand-built alias). Score PER-DAY, render, **verify the curve is actually drawn**
   (real intraday points, not the 2-point stub), HARD PAUSE for Greg.
2. **Archive the blind before the refine**: `python research/kalshi/archive_blind.py g22`. It MOVES, so
   the canonical names are left ABSENT and a specialist that fails to write hard-fails the guard instead
   of silently serving blind numbers. The refine coordinator additionally hashes every round-1 posterior
   against the blind archive and refuses a byte-identical match.
3. **G22 refine** (same sequenced spawn, unblinded), coordinate, PRINT, HARD PAUSE, adjudicate, merge on
   Greg's go. Then round 2 if warranted.
4. **G23** - staged and reconciling; run after G22 completes.
5. Optional: **G21 round 2** (r1 already at worst-day 80); the **live orchestrator** (A's own day and
   B's block-open day have no upstream dependency, yet the fixed E->A->B order serializes them - on a
   block like G21 that is ~2 of 3 waves recoverable).

## 5. WHAT S108 CHANGED THAT YOU WILL NOTICE

- `tape_conditions` reads the **SCORED LEG**; `source_store` says e.g. `leg:ng_mbo_ngq26`.
- `tape_reconcile.py` HARD-FAILS staging if the tape is off-instrument. **Do not route around it.**
- Mondays carry `prior_full_session` (the Friday) beside the Sunday reopen stub.
- Both b_share bases served plus `unsided_volume_frac`; absolute 0.50 bars read `*_two_sided`, and bars
  fitted empirically keep reading the ORIGINAL series.
- `phase_volume_lots` / `phase_n_trades` served; `squeeze_watch` carries a live calendar limb and an
  explicit `active_false_negative` when the frozen and live limbs disagree.
- `nws_temp` flags `provisional_tail` on the last day of any fetch; `state_health` treats it as HARD.
- Stage time also precomputes the round-2 exit states, so a staged group needs no `data/`.

## 6. OPEN, highest value first

1. **The live orchestrator** (see 4.5).
2. **`options_surface` strike ladder** is not on the contract's price scale (top-OI strikes 0.25-0.35
   against a ~2.9 front) - the pin read is not computable on the day it matters.
3. **G21 round 2**, not run.
4. **Per-day blind state slices** - measured in S108 and the token win is small (11% de-dup, 8%
   run-timestamps) while causal slicing costs more than it saves. The real constraint is wall-clock.
5. **KEYS DO NOT ROTATE DURING THE WALK.** Standing decision - do not act on it, do not re-raise.

## 7. STANDING DOCTRINE

- Scoreboard = **per-day error first**, forward curve second, never a mean alone.
- One group = two weeks. Stage all, RUN ONE at a time. Windows: Sunday reopen -> the SECOND Friday.
- FOCUS = FRIDAY AND MONDAY. Target: honest under-100 every day.
- The blind's ONLY deliberate mask is the PRICE CURVE. **If it is missing anything else, that is a
  DEFECT, not a handicap** - S108 found a case where it was also handed a wrong-instrument, sign-flipped
  flow read on 4 of 10 days.
- Magnitudes DERIVED from measurable state, never fitted. A reactive tail is not ours to claim.
- Never pool or average as the final word - each event individually.
- git = code, S3 = data, `data/` disposable. Committer noreply@anthropic.com. No emojis.
- Brain merges are PROPOSAL FILES + adjudication (incumbents byte-identical), never a direct edit.
- **A silently wrong input is the recurring enemy, and it has now worn three different faces**: EMPTY
  (S107's six), WRONG VALUE (the weather fetch tail), and OFF-INSTRUMENT (the tape after a roll).
  `state_health` catches only the first. When something reads as "no data" or reads as coherent,
  RECONCILE it against an independent measurement before reasoning over it.
