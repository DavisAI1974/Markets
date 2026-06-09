# CLAUDE.md — DavisAI / Markets — auto-loaded session context

This thin file is the ONE thing Claude Code auto-loads every session (a file named
exactly `CLAUDE.md`). It pulls in the CURRENT lightweight state via the `@`-imports
below — so a fresh chat starts oriented WITHOUT reading the 207 KB `CLAUDE (5).md`
(that file is deep archive; open it only for history).

**Per-session ritual:** when you write a new daily note / handoff / kickoff, update the
three `@`-import lines below to the newest dated files (one edit), commit, push. That
is what keeps startup auto-loading the latest state.

## Current state (auto-imported — bump these each session)
@CLAUDE_session_note_2026-06-09_S28.md
@SESSION_HANDOFF_2026-06-09_S28.md
@KICKOFF_2026-06-10_S29.md
@CLEANUP_RUNBOOK.md

## Standing rules
- KEEP PAIRS SEPARATE; never pool; never standardize; zero synthetic data; Result Discipline.
- Heavy coeff-gen + win/lose pool building are refrag-bound (`E:\refrag`, `F:\Factory`,
  `live_data_history`) → run on Greg's LOCAL box, not this cloud container. From cloud you have
  the repo code + the `data/*` bins branches (materialized to `realbins/` by the SessionStart hook).
- Knowledge JSONs → 3 copies (OD `E:\refrag\discoveries` + Refrag `E:\refrag\docs` + Factory
  `F:\Factory\knowledge`); they're read downstream, so corrected JSONs must be re-archived to all 3.
- Canonical OD branch: `claude/beautiful-shaw-040328` (mirror `claude/zealous-cannon-aej9yf`).
  Live collectors: workflow YAML from default `new-session-o3vnm`, collector code from
  `continue-phase-2-pipeline-UFiGY`.
- Deep archive (don't auto-read): `CLAUDE (5).md`.
