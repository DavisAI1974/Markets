---
name: experiment-orchestrator
description: Experiment orchestrator - runbook for the stripped-down Frankie experiment path (fetch -> ingest -> derive without bedrock -> export calculations -> series/search -> survivors -> confirmation), with the classroom arm on the first and last two discovery days. Covers what is built vs spec, the day-class and discovery/confirmation walls, the build order, and what can be dispatched today. Use before building, dispatching, monitoring or reporting any experiment-orchestrator work. For the full daily run use full-run-orchestrator instead.
---

# Experiment orchestrator

Greg: "a stripped down version of today's run." Its own workflow, calling ONLY the pieces of the
full run the experiment needs (reused, never copied), with a new search engine attached behind
it. Frankie's cycle (context, teacher, principal, Granite, classroom) is NOT called, except on
the three classroom-arm days. Everything else is code on the box's CPUs.

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
| 4 | export | `frankie_box_export_calcs.sh` -> `frankie_box_brain.export_calculations` | **built** (f751ccbe) |
| - | orchestrator | `frankie_box_experiment.py` + `frankie_experiment.yml` (`ACTION=start\|status\|stop`) | **NOT built** |
| 5 | series | one causal time axis per day from the journal + calc JSON | NOT built |
| 6 | search | series x transforms x lags x cells x conditions x targets | NOT built (start from the joined-teacher builder, dfe08ca7) |
| 7 | survivors | symbolic regression (`odcore/symbolic.py`) | NOT built |
| 8 | confirmation | frozen survivor list on confirmation days, per cell, net of fees maker AND taker | NOT built |
| C | classroom arm | teacher + `prepare_integrated_cycle` (no scientific dialogue) + principal classroom stage | reuses the full run; waits on r10 showing the plan classroom end to end |

## 2. Build order - each step on Greg's go

1. **Add the track to the Excel build plan** (`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`)
   BEFORE building anything. Unplanned = unwired.
2. `bedrock=False` switch in the derive stage. Frankie's cycle keeps its bedrock, so the default stays unchanged.
3. Orchestrator for steps 1-4, first on Tue 2021-10-05 and Wed 2021-10-06, plus the Monday export.
4. Series + search (5-6), attached to the orchestrator.
5. Survivors + confirmation (7-8).
6. Classroom arm (after r10 runs the plan classroom end to end).

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
  freeze. It runs only on discovery days, never on a confirmation day. Only these days use a Pod
  (~$1.59/h per A100); every other day is CPU only.
- **The loop**: search survivors go to the teacher/classroom as material. Frankie's findings come
  back as HYPOTHESES (claims, never truth), and the search tests them across every discovery day
  with the chance check. A survivor is reported as a scoped finding with its days named.
- **Every test gets its own circular-shift chance check. Results are COUNTS, never coefficients
  or averages** (D37; an R2, a correlation or a fitted slope is an average - use `per_event.py`).
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

- Spec step 7 header says the Granite pass is REMOVED (per `SPEC-decouple-granite.md`), but its
  body still lists "one short Granite reasoning pass ... the only model use". Treat it as removed
  until Greg says otherwise.
- The spec calls a 1-2 minute canary "the standing rule for measurements". The drop-in and
  CLAUDE.md say "no canaries". Ask which applies to the disk measurement.
- `SPEC-decouple-granite.md` itself is a draft (is C14 an original role?). That decides whether the
  classroom arm stays as written.
- **Do not confuse with `SPEC-experiment-locks.md` / `SPEC-experiment-runner.md`**: those are the
  paired-arm experiment for BOSS models (plan G20-G22: arm locks, reveal ledger, scoring). That is
  a different "experiment", not this orchestrator.
