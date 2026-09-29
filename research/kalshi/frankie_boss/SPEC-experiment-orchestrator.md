# Spec: the experiment orchestrator (Greg, 2026-09-29)

Status: SPEC. Nothing is built beyond the per-cycle calculation export (f751ccbe). It goes into the Excel build plan
(`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`) as a research track before it is built (Greg adds it).

## UPDATE 2026-09-29 (late): the teachers are tied and Granite is out of the classroom. This supersedes the text below.
- **Granite** (`SPEC-decouple-granite.md`, DECISION and BUILT blocks): Granite is ONLY the B2 shadow critic (C21-C24) on
  the R4 Pod, plus one labelled self-assessment of how it performed as the critic. C35 is no longer a Granite role.
  Greg: "Granite has absolutely nothing to do with classroom anymore." The experiment makes NO Granite call anywhere:
  not in the search, not over the survivors, not in the classroom arm.
- **The classroom is Frankie's code** (`deploy/aws/box/frankie_box_classroom_code.py`): TEACH answered in the parsers'
  own shapes (counts, extremes, each of the 171 pairs' Pearson coefficient over its own window with its overlap count,
  plus its co-movement counts, nothing flattened or normalized); GUIDED/SOCRATIC/VERIFY refused with the reason; novel
  findings filed as HYPOTHESIS only where a computation surfaces them. The rules file
  `knowledge/CLASSROOM_RULES_V1.json` (R01-R17, confirmed) is loaded and witnessed in the classroom receipt.
- **The teachers are tied** (`SPEC-scientific-teacher.md`, confirmed): three seats, none of them a model (rule R17):
  - Frankie: the learner; his findings are claims, never truth (R11). Source: his code, calculations and brain.
  - The BOSS teacher: mathematics, representation supervision, targets, masks, controls. Source: JournalTeacherR3 on
    the day's journal, the classroom package, the teacher key.
  - **The scientific teacher IS this experiment's search** (its classroom-facing side): every claim becomes a
    testable statement over the day's series, with its own circular-shift chance check, the leakage gate, results as
    counts with the days named (D37), a disposition word as orientation only (R14), "the data is showing this
    instead" where a subclaim is contradicted (R07), and the untested combinations listed, never dropped.
  - The two teachers keep separate roles (R12); neither sees Frankie's decision process or graded outcomes (R09, R10).
  - Reused, not copied: `dipole_teacher_discussion.py` (roles, positions, schemas; only what produces a turn changes,
    from a model prompt to a test result), `dipole_scientific_review.py` (request, exchange, disposition schemas), the
    joined-teacher builder (dfe08ca7, the starting slice of the tests). Swapped out:
    `deploy/aws/box/frankie_box_scientific_dialogue.py` (it sends teacher turns to Granite).
  - Until the search exists the tied teachers stay unwired; the full run's classroom runs with the BOSS teacher and
    Frankie's code only (config `classroom_scientific_dialogue: false`).
- **Consequence for this spec:** step 7 has no Granite pass; the classroom arm is code (teacher + classroom package +
  Frankie's classroom code + the scientific teacher's turn from the search). It does not run the launch, so there is
  no critic, no Granite and no Pod on any experiment day: the whole experiment is CPU only.

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
- the principal inputs, the launch, the Pods, Granite and the brain entry, on every day; the classroom, except on the
  three classroom-arm days below (where it is Frankie's code, still without the launch, Granite or a Pod);
- the digest render (Frankie's read format; the experiment reads the JSON).

## The new part (built after the orchestrator)
5. **Series:** from each day's compact journal (every event, every book level, fills, FIFO, unknown-side trades carried) and the exported calculation JSON. Everything goes on one time axis per day, and every row carries only what was knowable at that moment (the causal clocks).
6. **Search:** series x transforms x lags x cells x conditions x targets.
   - Every test gets its own circular-shift chance check.
   - Results are reported as counts, never coefficients or averages (D37).
   - The leakage gate (`odcore/leakage.py`) runs on every target.
   - Start from the joined-teacher builder (dfe08ca7): its sign-step coupling and cells, pointed at the journal and the calculation JSON instead of the bedrock.
7. **Survivors** (no Granite, no model of any kind, per `SPEC-decouple-granite.md` and rule R17):
   - symbolic regression (`odcore/symbolic.py`);
   - the survivor list goes to the classroom arm as material, and to confirmation.
8. **Confirmation:** the frozen survivor list is run on the confirmation days, untouched until then. Any trade idea is judged per cell, net of fees at maker and taker.

## Days
- The day-class doctrine applies: classes are never mixed, and every day is reported on its own.
  - Midweek Tuesday/Wednesday comes first. Tue 2021-10-05 and Wed 2021-10-06 are already fetched to the box in the staged block 20211004-20211006.
  - Thursday (the EIA print) is its own class, later.
  - Monday is its own class, and its calculations exist already: export them with `frankie_box_export_calcs.sh`.
- Discovery: the October days of 2021-2023. Confirmation: the October days of 2024-2025. Then widen to every year, reported per season.
- Source: the 5-year NG MBO pull on S3 (`nymex/ng_mbo_5y_v0`). List it first to confirm coverage.

## The classroom arm (Greg, 2026-09-29: "just at the beginning run and last 2 runs")
The FIRST discovery day and the LAST TWO discovery days (before the survivor list is frozen) also run the plan's governed dipole classroom (C14/D5), so the teacher and Frankie work on
new dipole data and push the dipole research forward (D51: the dipole is open research).
- **The added pieces of today's run it calls** (all reused):
  - the teacher on that day's journal: JournalTeacherR3 with the teacher changes (all levels, the whole day, unknown trades carried), read once beside the context walk (saved walk blocks, the concurrent teacher);
  - the classroom package: `prepare_integrated_cycle`, without the scientific dialogue per the plan;
  - the principal's classroom stage, answered by Frankie's code (`frankie_box_classroom_code.py`, no Granite): the 19
    components, the summary and the correction, under `knowledge/CLASSROOM_RULES_V1.json`;
  - the scientific teacher's turn (`SPEC-scientific-teacher.md`): this experiment's search, tied to the BOSS teacher.
  - No Granite and no Pod in this arm (superseded 2026-09-29: it used to say "needs Granite and a Pod"). The launch
    is not called (see "Not called" above), so its B2 critic does not run here.
- **The loop between the two arms:**
  - The search's survivors go to the teacher and the classroom as material to teach and examine.
  - Frankie's classroom findings and novel findings come back to the search as HYPOTHESES (rule R11: claims, never truth). The search, as the scientific teacher, tests them across every discovery day, with the chance check, and hands back counts, challenges and the tests not yet run; the BOSS teacher answers within its own role (R12).
  - A novel finding from the classroom that survives the search on other days is a scoped finding with its days named.
- **Only discovery days.** A classroom day is always a discovery day, never a confirmation day: the confirmation days stay untouched by the search, the teacher and Frankie until the survivor list is frozen.
- **Why these three days:**
  - The first seeds the search with Frankie's and the teacher's hypotheses from day one.
  - The last two examine everything the search has accumulated, while that material is still discovery data. Their findings are the last hypotheses the search tests before the list is frozen.
- **Cost:** every day is CPU only for Frankie, the teachers and the search. The three classroom-arm days also run
  Jev on his own Pod (section "Jev" below); no other day uses a Pod.

## Jev: the blind outside student (Greg, 2026-09-29: "yes, include him")
- **Who:** Jev, Qwen3-8B chat on his OWN Pod (never the Granite Pod). A different model from anything else in the
  loop, which is the only way a model may hold a seat (`SPEC-scientific-teacher.md`, open item "one seat only, a
  different model"). He is NOT one of the three classroom seats and never speaks in the classroom (R17 stands).
- **What he sees:** the same material Frankie gets on that day - the classroom package (the dipole material, the
  171 pairs with their coefficients, overlap counts and co-movement counts) and the search's survivor list so far.
  **Blind to Frankie:** he never sees Frankie's answers, analysis or novel findings before filing his own, so
  agreement between them is independent evidence.
- **What he produces:** CLAIMS only, labelled as Jev's (R11 applies to him as to Frankie): proposed mechanisms,
  novel findings, and "test this next" combinations. No grades, no corrections, no teaching.
- **Where his claims go:** to the search, which as the scientific teacher tests every one like Frankie's claims -
  its own circular-shift chance check, the leakage gate, counts with the days named (D37), orientation word only
  (R14), untested combinations listed, never dropped. A surviving Jev claim is a scoped finding with his name and
  its days on it.
- **What he never touches:** Frankie's session, the BOSS teacher's measurements, the classroom grade, the teachers'
  exchange, and confirmation days (R15). Nothing he writes enters Frankie's input.
- **When:** the three classroom-arm days only (the first discovery day and the last two before the freeze). Those
  are the experiment's only Pod days, and the Pod is Jev's.
- **How he keeps the seat:** by counts, per day: how many of his claims survive the search, set beside the
  hypotheses Frankie's code surfaces that day. If his survive at no better than chance, he comes out.
- **Code (BUILT 2026-09-29, py_compile only, not run):**
  - `clm_sidecar/sit_in.py`: material -> STUDENT claims (JEV_CLAIMS_V1, filed with sha256 and filed_at) -> only then
    Frankie's outputs -> comparison (JEV_COMPARISON_V1, orientation only) -> report, transcript, receipt
    (JEV_SIT_IN_RECEIPT_V1, granite_calls 0). The old Granite "Frankie" step is gone.
  - `deploy/aws/box/frankie_box_jev_relay.sh`: ACTION=material (JEV_DAY_MATERIAL_V1: classroom package + survivors,
    refuses anything under a classroom/out directory and any day not DAY_ROLE=discovery) and ACTION=frankie
    (JEV_FRANKIE_OUTPUTS_V1: ledgers, classroom receipt, analysis; refuses until the receipt exists). Replaces the
    heartbeat relay (on 2026-09-28 his 58 feed bundles carried only a derive-stage heartbeat and he filed nothing).
  - `clm_sidecar/launch.py --jev --day` + `pod_bootstrap.sh` JEV_ONLY: his Pod serves only his chat; no Granite key.
  - `frankie_box_jev_pod.sh` (runner marker) + the "Jev Pod" step in `frankie_box_run.yml` (own lock, always deleted).
  - The claims file is what the scientific teacher reads; its reader is part of the search build (6b).
- **Before it is built:** Greg adds Jev to the Excel build plan with this track (unplanned = unwired).

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
5. The scientific teacher's turn on top of the search, with the discussion schemas (`SPEC-scientific-teacher.md` build
   order 4); then the classroom loads the rules file and the tied teachers switch on.
6. Survivors and confirmation (steps 7-8).
7. Jev's sit-in reworked (section "Jev"), after Greg adds him to the build plan.
8. The classroom arm on the first and the last two discovery days (after r10 shows the plan classroom running end to end).
