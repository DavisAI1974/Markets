# NG FORECASTER AGENTS — canonical drop-in files (S103 Greg-ordered; S104.1 = the 5-specialist era)

**The point (Greg, S103): these agent files are STATIC. You drop the SAME files into every group and
run immediately. The ONLY things that change group-to-group are (1) the BRAIN (`knowledge/ng_brain.json`,
which updates via the refine step) and (2) the GROUP DATA (the decision-state file + anchor + basis).
No re-authoring prompts per group. No per-group selftests. No re-pulling the shared stores.**

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

## WHY (the record)
S103: G15 refine ran as one agent; G16 blind as the 3-angle panel; those became canonical files.
S104: the G15 MBO refine ran as 5 day-class specialists (blind 526 -> r1 72 -> r2 66 err, 12/12) and
Greg ordered the 5-specialist structure for BOTH phases + the Friday/Monday cascade cleanup (brain
s102.5, 47 plays). S104.1: Sunday fold + E->A->B week-open chain + coordinator Friday sign-off.
From here we spin these files unchanged; only the brain + group data move.
