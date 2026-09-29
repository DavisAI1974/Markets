---
name: experiment-orchestrator
description: Experiment orchestrator - runbook for the stripped-down Frankie experiment path (fetch -> ingest -> derive without bedrock -> export calculations -> series/search -> survivors -> confirmation), with the classroom arm on the first and last two discovery days. Covers what is built vs spec, the day-class and discovery/confirmation walls, the build order, and what can be dispatched today. Use before building, dispatching, monitoring or reporting any experiment-orchestrator work. For the full daily run use full-run-orchestrator instead.
---

# Experiment orchestrator

Greg: "a stripped down version of today's run." Its own workflow, calling ONLY the pieces of the
full run the experiment needs (reused, never copied), with a new search engine attached behind
it. Frankie's cycle (context, teacher, principal, Granite, classroom) is NOT called, except the
teacher and the code classroom on the three classroom-arm days. Everything is code on the box's CPUs.

**As of 2026-09-29 (late) - read before anything below:**
- **Granite is decoupled.** It is ONLY the full run's B2 shadow critic (C21-C24) on the Pod, plus one
  labelled self-assessment (`SPEC-decouple-granite.md`, DECISION + BUILT). **The experiment makes no
  Granite call anywhere**: not in the search, not over the survivors, not in the classroom arm. The
  classroom is Frankie's code (`deploy/aws/box/frankie_box_classroom_code.py`) under the confirmed
  rules file `research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V1.json` (R01-R17; R17 = no model
  voice in the classroom).
- **The teachers are tied** (`SPEC-scientific-teacher.md`, confirmed): three seats, none a model -
  Frankie (learner, his findings are claims, R11), the BOSS teacher (JournalTeacherR3 + classroom
  package + teacher key), and the **scientific teacher = this experiment's search** (its
  classroom-facing side: claim -> tests -> counts, challenges worded "the data is showing this
  instead" (R07), untested combinations listed). The two teachers keep separate roles (R12) and never
  see Frankie's decision process or graded outcomes (R09, R10). Reuse `dipole_teacher_discussion.py`
  and `dipole_scientific_review.py` schemas (a turn becomes a test result, not a model prompt); swap
  out `frankie_box_scientific_dialogue.py` (it sends turns to Granite). Until the search exists the
  tied teachers stay unwired (`classroom_scientific_dialogue: false`).

**Source of truth: `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md`** on the run
branch (as of 2026-09-29 `claude/frankie-monday-cycle-0-urozez`). If this file and the spec
disagree, the spec wins and you tell Greg.

**Shared mechanics live in `full-run-orchestrator`**: HOLD/go per step, dispatch through
`frankie_box_run.yml`, stage-then-no-push, probes, receipts-not-green-checks, `[skip ci]`,
the never-bend rules. Read its sections 0, 3, 5 and 7 first. They all apply here.

## 1. Pipeline and build status (as of 2026-09-29 - check `git log` before trusting)

| # | Step | Piece | Status |
|---|---|---|---|
| 1 | fetch | `frankie_box_ingest_block.sh ACTION=fetch MANIFEST=...` (presigned map, sha256 + size verified) | built (full run's) |
| 2 | ingest | `frankie_box_ingest_block.sh ACTION=canary\|ingest\|status` - sealed compact journal + receipt | built (full run's) |
| 3 | calculations | derive stage with a new `bedrock=False` switch skipping `_derive_bedrock` | **NOT built** - `bedrock=False` exists only in the digest render, not in `Session.derive` |
| 4 | export | `frankie_box_export_calcs.sh` -> `frankie_box_brain.export_calculations`; also runs automatically after every cycle from `brain_entry()` (a failure is noted, never blocks the cycle). Store: `/opt/frankie-box/work/experiment-calcs/<day>/cycle-<NN>/` = the derive stage's JSON layer files + `derive.json`, hard-linked, + MANIFEST (bytes, sha256); bedrock layers are NOT exported | **built** (f751ccbe) |
| - | orchestrator | `frankie_box_experiment.py` + `frankie_experiment.yml` (`ACTION=start\|status\|stop`) | **NOT built** |
| 5 | series | one causal time axis per day from the journal + calc JSON | NOT built |
| 6 | search | series x transforms x lags x cells x conditions x targets | NOT built (start from the joined-teacher builder, dfe08ca7) |
| 6b | scientific teacher | the search's classroom-facing turn: claims (Frankie's, labelled) -> tests -> counts + challenges + untested combinations, tied to the BOSS teacher | NOT built (`SPEC-scientific-teacher.md` build order 3-5) |
| 7 | survivors | symbolic regression (`odcore/symbolic.py`); no Granite pass, no model | NOT built |
| 8 | confirmation | frozen survivor list on confirmation days, per cell, net of fees maker AND taker | NOT built |
| C | classroom arm | teacher + `prepare_integrated_cycle` + the principal's classroom stage answered by Frankie's code (no Granite) + the scientific teacher's turn (6b) | reuses the full run; waits on r10 showing the code classroom end to end |

## 2. Build order - each step on Greg's go

1. **Greg adds the track to the Excel build plan** (`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`),
   with the scientific teacher and the rules file, BEFORE anything is built. Unplanned = unwired.
2. `bedrock=False` switch in the derive stage. Frankie's cycle keeps its bedrock, so the default stays unchanged.
3. Orchestrator for steps 1-4, first on Tue 2021-10-05 and Wed 2021-10-06, plus the Monday export.
4. Series + search (5-6), attached to the orchestrator.
5. The scientific teacher's turn on the search (6b); the tied teachers switch on.
6. Survivors + confirmation (7-8).
7. Classroom arm (after r10 runs the code classroom end to end).

## 3. What can be dispatched today (each on Greg's go)

- **Monday calc export** (read-only on the root, no model call, hard links so no extra disk):
  `frankie_box_export_calcs.sh CODE_ROOT=<staged> WORK=/opt/frankie-box/work/monday-calculations/<root>/work DAY=20211004 CYCLE=00`
  -> `/opt/frankie-box/work/experiment-calcs/20211004/cycle-00/` + MANIFEST (bytes, sha256).
  Take `<root>` from the current drop-in (as of 2026-09-29 `full-20211004-20260927-r1-48`).
- **Tue/Wed fetch/ingest**: the committed manifest is
  `research/kalshi/frankie_boss/blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json`.
  **It includes Monday 20211004, whose ingest is the gold standard and is never rebuilt.** Before
  any `ACTION=ingest` on it, confirm with Greg whether it re-ingests Monday. The likely answer
  is a Tue/Wed-only manifest. `ACTION=status` is read-only and safe.
- **Tue/Wed calculations: not dispatchable as-is.** `frankie_box_monday_calculations.sh` demands
  a Monday `AUTHORSHIP` receipt. Adapting it is part of build step 3.

## 4. Walls that never bend (experiment-specific)

- **Day classes never mix; every day is reported on its own.** Midweek Tue/Wed first; Thursday
  (EIA print) is its own class, later; Monday its own class.
- **Discovery = October days of 2021-2023. Confirmation = October days of 2024-2025.** Then widen
  to every year, reported per season. Confirmation days stay UNTOUCHED by the search, the teacher
  and Frankie until the survivor list is frozen. Never fetch-and-peek, never "just check one".
- **Classroom arm on exactly three days**: the FIRST discovery day and the LAST TWO before the
  freeze. It runs only on discovery days, never on a confirmation day (R15). The classroom itself is
  code and the launch is not called, so these days are CPU only too: no critic, no Granite, no Pod.
- **The loop (three seats)**: search survivors go to the BOSS teacher and the classroom as material.
  Frankie's findings come back as HYPOTHESES (claims, never truth, R11); the search, as the
  scientific teacher, tests them across every discovery day with the chance check and hands back
  counts; the BOSS teacher answers within its own role (R12). A survivor is reported as a scoped
  finding with its days named.
- **Every test gets its own circular-shift chance check. The finding is COUNTS, never an average**
  (D37; an R2, a pooled correlation or a fitted slope is an average - use `per_event.py`).
  Coefficients are kept where they are read per pair/cell/day with their overlap count (Greg: "We
  want the coefficients, just not a bunch of dipole results flattened or normalized"); never pooled.
- **Leakage gate (`odcore/leakage.py`) on every target.** Every series row carries only what was
  knowable at that moment (causal clocks).
- **Zero data dropped**: every event, every book level, fills, FIFO, and unknown-side trades carried.
- **Source**: the 5-year NG MBO pull on S3 (`nymex/ng_mbo_5y_v0`). **List it to confirm coverage
  before assigning days.** Nothing here charges Databento.

## 5. How the orchestrator runs (once built)

- One dispatch starts `frankie_box_experiment.py` on its own lock `box-experiment-*`, so it runs
  beside Frankie's runs and never queues behind them.
- Per-day, per-step receipt in `/opt/frankie-box/work/experiment/<run>/`. A restart skips finished
  steps. Save progress on every stop, and stop-and-save at a disk floor.
- Days run in parallel across CPUs where steps allow; the ingest's causal parent stays one per day.
- Workflow inputs: day list, class, discovery/confirmation assignment, stage range.
- Probe every run: `frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment/<run>`.
- **Disk: measure the first day's bytes (journal + calc JSON) and extrapolate before queueing
  many days.** The Monday journal alone is ~23.7 GB.
- For quick data checks off the box, DuckDB is in the session setup script (SQL over gz
  JSON/CSV/Parquet, including on S3 with credentials).

## 6. Open / contradictory - ask Greg, do not resolve

- The spec calls a 1-2 minute canary "the standing rule for measurements". The drop-in and
  CLAUDE.md say "no canaries". Ask which applies to the disk measurement.
- **Do not confuse with `SPEC-experiment-locks.md` / `SPEC-experiment-runner.md`**: those are the
  paired-arm experiment for BOSS models (plan G20-G22: arm locks, reveal ledger, scoring). That is
  a different "experiment", not this orchestrator.
