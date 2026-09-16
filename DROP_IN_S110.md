# DROP-IN BOX - S110 (start a FRESH session with this)

## BOX 1 - BRANCH. PASTE THIS ALONE, FIRST, AND READ THE VERDICT BEFORE CONTINUING.

```bash
B=claude/kalshi-agents-coordinator-guard-1175nr
git fetch origin $B && git checkout -B $B origin/$B
echo "--------------------------------------------------------------"
echo "branch : $(git rev-parse --abbrev-ref HEAD)"
echo "tip    : $(git log --oneline -1)"
echo "tree   : $(git ls-files | wc -l) files tracked"
echo "expect : S109 close-out (or later)"
test -f research/kalshi/agents/state_auditor.md \
  && test -f SESSION_HANDOFF_2026-08-01_S109.md \
  && test "$(git rev-parse --abbrev-ref HEAD)" = "$B" \
  && echo "BRANCH OK - safe to paste the drop-in box" \
  || echo "BRANCH FAILED - do NOT continue. Re-run this box; if it fails again, say so."
```

Why this is separate: the harness assigns every session its own auto-named branch and that branch is
NEVER the work. Two traps it guards. The STALE-TIP trap: the session is cut from an old tip and looks
fine. The EMPTY-CHECKOUT trap: the assigned branch does not exist on the remote, so the container comes
up on an orphan `master` with ZERO commits and an EMPTY TREE - every file read fails and the session
looks broken. Both sentinel files were created in S109, so their presence rules out both traps at once.
This box deliberately does NOT touch credentials or data, so a branch failure can never be confused with
a creds failure.

---

## 0. Read order (only after BOX 1 reports BRANCH OK)

`SESSION_HANDOFF_2026-08-01_S109.md` (in full) -> `research/kalshi/agents/state_auditor.md` ->
`research/kalshi/G22_REASONING_LEDGER_S109.md` -> `research/kalshi/agents/README.md` -> `CLAUDE.md` header.

The ledger is new and is the point: it carries WHY each specialist decided what it did, not just what.

## 1. ONE COMMAND FROM EMPTY TO READY

```bash
pip install --quiet numpy pandas matplotlib boto3 databento
python research/kalshi/session_bootstrap.py --aws-id <ID> --aws-secret <SECRET> --bento <KEY>
```

Keys are NEVER committed and do NOT survive a session. That is expected, not a bug. Neither does
`data/`, nor the scratchpad. **A group staged at S108+ runs BOTH rounds with NO data plane at all** -
the restore is needed for STAGING and for pre-S108 groups only. `--verify-only` reports without writing.

Run AWS/boto3 under `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY` if calling it directly - the
container injects PLACEHOLDER creds that override `~/.aws/credentials` in boto3's precedence.
`session_bootstrap.py` does this for you.

## 2. STATE

- **Brain s103.7, 68 plays.** Backup at `knowledge/ng_brain_s103.6_backup.json`.
- **G22 BLIND COMPLETE**: 4/10 dir, **sum|err| 5,965**, drift -1,815, survives 30%. Second-best blind of
  the walk on sum|err|; worst on direction.
- **G22 REFINE NOT RUN** - that is the next job.
- G23 staged and passing. G20/G21 complete.

## 3. THE FIVE RULES THAT NOW GOVERN A RUN

- **NEVER average above and below.** Report per-day, sum|err|, drift AND the survival ratio together:
  `blind_score_nonpooled.py`.
- **Mean error is a dashboard number, never a diagnosis.** Where a specialist claims a MECHANISM, check
  the mechanism was tested, not the net.
- **Causality is physics, not a mask.** Specialists run on **per-day causal slices**
  (`build_causal_slices.py`). A specialist with two jobs at two decision points needs two slices.
- **Audit and forecast are SEPARATE roles.** The auditor reads the whole block and emits no numbers; the
  specialists forecast on slices. Do not merge them back together.
- **A hill slopes, it does not gap.** Weather is THE driver as a continuous asymmetric SLOPE;
  `anomaly x duration x constraint` is a MULTIPLIER on top. Confusing the two cost G22 its largest day.

## 4. DO THIS, IN ORDER

1. **STATE AUDITOR on G23** - `agents/state_auditor.md`, full state, no forecasts, findings to
   `forecasts/grp23_state_audit.json`. It runs BEFORE the blind now. Adjudicate, then fix phase.
2. **G22 REFINE** - same 10 per-day runs, unblinded. Two named targets, not an aggregate: **the missed
   hill** (drift -1,815 = the hill the blind could not see) and **0629's slope-treated-as-spike**
   (forecast gap +480, actual +50, session -1,160).
3. **Merge on Greg's go** - proposal file + adjudication, incumbents byte-identical. Start from
   `S109_MERGE_PROPOSAL_G22.md` (P0 through P0.8, each with a falsifier).
4. **G23** - blind, then refine.
5. **Backfill `grid_stack` G7-G13** (EIA-930, free, historical) and re-run `gas_call_residual.py` in COLD.

## 5. WHAT S109 CHANGED THAT YOU WILL NOTICE

- **Specialists get a per-day SLICE, not the block state.** Their `state.json` ends at their own day.
- **`build_anchor_block.py`** - anchors are chain-verified against the prior group's actual close and
  carry `direction_caveat` / `close_in_range` / `net_ticks`. Both G22 and G23 anchors sit at the price
  RESOLUTION FLOOR (2 ticks / 1 tick) - do not lean on `anchor_lasthr_dir`.
- **`state_health` has two new RECONCILIATION guards** - the b_share identity and the
  squeeze_watch-vs-flow_calendar cross-check. Reconciliations, not presence checks.
- **`squeeze_watch._live` limbs are re-derived**; `calendar_limb_satisfied_live` is **null** (unevaluable
  under the price mask) - treat as UNKNOWN, never as a negative.
- **CDD ladder served** - `forecast_gw_cdd`, `d_gw_cdd`, `fwd7_gw_cdd_span`, plus `gw_cdd_d0` and
  `d_gw_cdd` on `sunday_reopen`, plus a `seam_delta_warning`.
- **`merge_perday.py`** joins per-day posteriors into the per-specialist shape under an owner guard.
- **Brain carries an LNG vessel play** (WIRED_UNPROVEN - context, not a signal).

## 6. THE TRAPS THAT ARE STILL LIVE

- **`storage_consensus` LOOK-AHEAD, unfixed** - the served consensus is captured AFTER the print it
  precedes. On the 06-25 print it destroys ~78% of the decision-time surprise. Reconstruct the
  decision-time value from `estimates[]` and cross-check the gap against `house_disagreement_bcf`.
- **HDD-keyed plays are UNEVALUABLE in summer, and every one degrades BEARISH** -
  `divergence_resolution` (16.4, unreachable) and `shoulder_weather_band_void` (13.5, trivially
  satisfied). An unreachable absolute bar is UNKNOWN, not satisfied and not refuted.
- **Run deltas are structurally blind across a seam** - they baseline run-over-run, not
  session-over-session. Across a weekend difference the LEVELS.
- **A weekend Friday carrying an EXPIRY confounds its own exit tells on the surviving leg** - the roll
  prints as BUY on the deferred contract. Settle it against an independent quantity.
- **NO TROPICAL/HURRICANE FEED EXISTS** and Aug-Oct is live. The Gulf carries the liquefaction fleet
  (Sabine Pass, Corpus Christi, Freeport, Cameron) AND a large share of production, and a storm pulls
  price in OPPOSITE directions through those two. `freeze_risk` is the winter analogue with no summer
  counterpart. The vessel line CONFIRMS an export disruption but LAGS it - never an early warning.
- **`options_surface` strikes are 10x off**; `vol_regime`'s v0 basis is entirely null; no session CLOSE
  TIME is served on shortened sessions; phases carry no clock boundaries.

## 7. STANDING DOCTRINE

- Scoreboard = **per-day error first**, forward curve second, never a mean alone.
- One group = two weeks. Stage all, RUN ONE at a time. Windows: Sunday reopen -> the SECOND Friday.
- FOCUS = FRIDAY AND MONDAY. Target: honest under-100.
- The blind's ONLY deliberate mask is the PRICE CURVE. Missing anything else is a DEFECT, not a handicap.
  **And it must not see the FUTURE - that is physics, not a mask.**
- Magnitudes DERIVED from measurable state, never fitted. A reactive tail is not ours to claim.
- git = code, S3 = data, `data/` disposable. Committer noreply@anthropic.com. No emojis.
- Brain merges are PROPOSAL FILES + adjudication (incumbents byte-identical), never a direct edit.
- **KEYS DO NOT ROTATE DURING THE WALK.** Decided - do not act on it, do not re-raise.
- **THE RECURRING ENEMY IS "SERVED BUT UNREAD."** The renewable subtractor was served and unread.
  `session_b_share` was served and broken. The CDD ladder was computed and dropped. The vessel line is
  live with zero consumers. All present, well-formed, in range - and wrong or invisible. **Field checks
  cannot catch it; only reconciliation against an independent source can.**
