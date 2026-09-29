# Spec: the experiment orchestrator (Greg, 2026-09-29)

Status: SPEC. Nothing is built beyond the per-cycle calculation export (f751ccbe). It goes into the Excel build plan
(`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`) as a research track before it is built.

## What it is
Greg: "a stripped down version of today's run". The experiment orchestrator is its own workflow. It calls ONLY the
pieces of today's run that the experiment needs. The new part, the search engine, is then built and attached behind it.
Frankie's cycle (context, teacher, principal, Granite, classroom) is not called; the experiment is code on the box's CPUs.

## Today's pieces it calls (reused, not copied)
| Step | Piece of today's run | Script / module | What the experiment keeps |
|---|---|---|---|
| 1 fetch | the trading-day partitions from S3 | `frankie_box_ingest_block.sh ACTION=fetch` (presigned map) | the DBN partitions, verified by sha256 and size |
| 2 ingest | the gold-standard trading-day ingest | `frankie_box_ingest_block.sh ACTION=ingest` | the sealed compact journal and its receipt (record count measured at ingest, the seal) |
| 3 calculations | the derive stage WITHOUT the bedrock | `frankie_box_monday_calculations.py` / `Session.derive` with a new `bedrock=False` switch that skips `_derive_bedrock` | the legacy layers and the pin's calculation layers |
| 4 export | the per-cycle calculation export | `frankie_box_brain.export_calculations` (built, f751ccbe) | `/opt/frankie-box/work/experiment-calcs/<day>/cycle-<NN>/`: the JSON layer files hard-linked, plus MANIFEST |

Not called:
- the trading-day preparation (native context, the teacher);
- the principal inputs, the launch, the Pods, Granite, the classroom and the brain entry;
- the digest render (Frankie's read format; the experiment reads the JSON).

## The new part (built after the orchestrator)
5. **Series:** from each day's compact journal (every event, every book level, fills, FIFO, unknown-side trades carried) and the exported calculation JSON. Everything goes on one time axis per day, and every row carries only what was knowable at that moment (the causal clocks).
6. **Search:** series x transforms x lags x cells x conditions x targets.
   - Every test gets its own circular-shift chance check.
   - Results are reported as counts, never coefficients or averages (D37).
   - The leakage gate (`odcore/leakage.py`) runs on every target.
   - Start from the joined-teacher builder (dfe08ca7): its sign-step coupling and cells, pointed at the journal and the calculation JSON instead of the bedrock.
7. **Survivors:**
   - symbolic regression (`odcore/symbolic.py`);
   - then one short Granite reasoning pass over the survivor list (mechanisms, novel findings). This is the only model use.
8. **Confirmation:** the frozen survivor list is run on the confirmation days, untouched until then. Any trade idea is judged per cell, net of fees at maker and taker.

## Days
- The day-class doctrine applies: classes are never mixed, and every day is reported on its own.
  - Midweek Tuesday/Wednesday comes first. Tue 2021-10-05 and Wed 2021-10-06 are already fetched to the box in the staged block 20211004-20211006.
  - Thursday (the EIA print) is its own class, later.
  - Monday is its own class, and its calculations exist already: export them with `frankie_box_export_calcs.sh`.
- Discovery: the October days of 2021-2023. Confirmation: the October days of 2024-2025. Then widen to every year, reported per season.
- Source: the 5-year NG MBO pull on S3 (`nymex/ng_mbo_5y_v0`). List it first to confirm coverage.

## The classroom arm (Greg, 2026-09-29: the dipole teacher and the classroom on 1 of every 5 experiment runs)
Every fifth experiment day also runs the plan's governed dipole classroom (C14/D5), so the teacher and Frankie work on
new dipole data and push the dipole research forward (D51: the dipole is open research).
- **The added pieces of today's run it calls** (all reused):
  - the teacher on that day's journal: JournalTeacherR3 with the teacher changes (all levels, the whole day, unknown trades carried), read once beside the context walk (saved walk blocks, the concurrent teacher);
  - the classroom package: `prepare_integrated_cycle`, without the scientific dialogue per the plan;
  - the principal's classroom stage on the BOSS: the 19 components, the summary and the correction.
  - That arm alone needs Granite and a Pod.
- **The loop between the two arms:**
  - The search's survivors go to the teacher and the classroom as material to teach and examine.
  - Frankie's classroom findings and novel findings come back to the search as HYPOTHESES (rule 3: claims, never truth). The search then tests them across every discovery day, with the chance check.
  - A novel finding from the classroom that survives the search on other days is a scoped finding with its days named.
- **Only discovery days.** A classroom day is always a discovery day, never a confirmation day: the confirmation days stay untouched by the search, the teacher and Frankie until the survivor list is frozen.
- **Cost:** only the classroom arm uses a Pod (about $1.59/h per A100). The other four of every five days are CPU only.

## How the orchestrator runs
- **A box-side orchestrator** (`frankie_box_experiment.py`), started by one workflow dispatch, with:
  - its own concurrency lock `box-experiment-*`, so it runs beside Frankie's runs and never queues behind them;
  - a per-day, per-step receipt in `/opt/frankie-box/work/experiment/<run>/`, so a restart skips every finished step (save progress on every stop);
  - days run in parallel across the CPUs where the steps allow; the ingest's causal parent stays one per day;
  - a probe on every run (`frankie_box_progress.sh DIRECTORY=<run>`);
  - a stop and save at a disk floor.
- **A workflow** `frankie_experiment.yml` (or a script through `frankie_box_run.yml`) with `ACTION=start|status|stop`. Inputs: the day list, the class, the discovery/confirmation assignment, and the stage range.
- **Disk:** without the bedrock a day is about the journal plus the calculation JSON. Measure the first day's bytes and extrapolate before queueing many days (a 1-2 minute canary is the standing rule for measurements).

## Build order (each on Greg's go)
1. Add the track to the Excel build plan.
2. `bedrock=False` in the derive stage (a switch; Frankie's cycle keeps its bedrock).
3. The orchestrator for steps 1-4, run on Tue 2021-10-05 and Wed 2021-10-06, plus the Monday export.
4. The search (steps 5-6), attached to the orchestrator.
5. Survivors and confirmation (steps 7-8).
6. The classroom arm on every fifth discovery day (after r10 shows the plan classroom running end to end).
