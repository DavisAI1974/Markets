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
3. **Blind**: spawn the 5 specialists (model opus, background) behind the wall; each owns its
   day-classes; E emits handoff_out per Friday; A delivers B the weekend bridge read.
4. **Coordinate (per-event)**: the coordinator SELECTS the owner per day under the GUARD (+ Friday
   sign-off) and assembles ONE `forecasts/grp<N>.json`. No votes, no averages, no fallbacks.
5. **Score + render**: `continuous_score.py` + the two-leg hand-roll actual (coordinate_g15_mbo.py
   `build_actual` pattern on a seam block; `continuous_rt.py` generic only for clean blocks).
   Render = actual + own p50 path only. PRINT the render.
6. **HARD PAUSE** -> Greg reviews the blind score.
7. **Refine**: the SAME 5 specialists, unblinded (`mbo_refine_shared.md` + lenses), each on its owned
   days -> coordinator re-assembles (guarded) -> proposal file(s), NEVER a direct brain edit.
   Adjudicate (incumbents byte-identical), render, PRINT, HARD PAUSE, MERGE on Greg's go. Commit+push.

## WHY (the record)
S103: G15 refine ran as one agent; G16 blind as the 3-angle panel; those became canonical files.
S104: the G15 MBO refine ran as 5 day-class specialists (blind 526 -> r1 72 -> r2 66 err, 12/12) and
Greg ordered the 5-specialist structure for BOTH phases + the Friday/Monday cascade cleanup (brain
s102.5, 47 plays). S104.1: Sunday fold + E->A->B week-open chain + coordinator Friday sign-off.
From here we spin these files unchanged; only the brain + group data move.
