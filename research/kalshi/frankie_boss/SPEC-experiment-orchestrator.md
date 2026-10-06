# Spec: the 30-day experiment orchestrator

Status: **CANONICAL WORKFLOW RECONCILED 2026-10-06.** This replaces the conflicting September 29/30 workflow tables.
The repository is brownfield: reuse the existing orchestrator, 16-CPU booking ledger, FIFO queues, receipts, ROOT,
teacher, classroom, data/search and scientific-teacher pieces. Do not rebuild working machinery. Survivors,
confirmation, the full search surface, and the remote worker's ROOT-to-finish path remain incomplete.

Greg, 2026-10-06:
- One real end-to-end ROOT-to-finish test, then fix actual failures. Do not build a new validation/test framework.
- A day owns its **same box, same 16-CPU lane and same worker allocation from ROOT until that day is finished**.
- A 16-CPU day lane uses the existing **15 worker + 1 coordinator/ordered-consumer** rule and the CPU booking ledger.
- The current 30-day ingests and retained progress are evidence: never re-ingest, delete, move or overwrite them casually.
- The expensive AWS boxes are execution engines, not development environments. Settle and wire the workflow before
  starting paid compute.
- **Immediate brain:** whenever a stage produces new legally available knowledge/calculations, commit it to Frankie's
  brain before the workflow advances. End-of-day retention is consolidation, not the first brain update. This
  supersedes any older deferred/no-auto-teaching behavior for this 30-day experiment.

## Immediate brain / live-learning rule

The experiment is not testing Frankie by withholding knowledge. It is trying to make Frankie as capable as possible
while the evidence arrives. Therefore:

- ROOT calculation findings enter his brain immediately after ROOT.
- The BOSS teacher's measured knowledge enters immediately after its read; the classroom may then use the same source
  directly without waiting for an end-of-day merge.
- Classroom findings/corrections enter immediately when the classroom closes (already implemented).
- Search/coupling discoveries enter immediately after the search.
- Scientific-teacher test results on Frankie's claims enter immediately (already implemented as <day>-lessons).
- The three-way exchange and teachers' findings enter immediately (already implemented as <day>-exchange).
- Jev remains independent only until his own claim file is sealed. Once Jev's claims have been tested, those tested
  results may enter Frankie immediately; the blind wall is not an indefinite knowledge handicap.
- Every survivor/candidate update and later confirmation finding enters immediately when produced.

The exact large evidence files do not need to be duplicated into the brain. A brain entry may hold a digest-bound
knowledge record pointing to the complete retained source where the source is too large, while the active workflow
continues to read the exact source directly. Nothing is silently summarized away or dropped.

Causal/future leakage remains forbidden. "Immediate" means as soon as knowledge is legally available, never before.

## 0. Canonical experiment workflow

The table below is execution authority. Older planning text below is retained only for provenance and implementation
detail; where it conflicts with this table, this table wins.

| # | Stage | When / dependency | What it does | Owner / compute |
|---|---|---|---|---|
| 0 | Preflight / resume reconciliation | Before paid execution; existing checks only | Pin commit and plan, find existing receipts/progress, confirm day ownership, 16 CPUs, disk floor and no duplicate active day. This is not a new validator project. | Existing controller/ledger/receipts |
| 1 | Fetch + ingest | Already complete for retained days; only for a genuinely missing day | Produces the sealed causal journal and receipt. Never redo a finished ingest. | Existing ingest code |
| 2 | Day file | Before ROOT/teacher/search when causally available | Attaches the stamped historical/external data once beside the ingest for every permitted reader. | Existing day-file code |
| 3 | ROOT | Start of the held day lane | Frankie's whole-day calculations, bedrock/model calls off; row spools and governed calculation surfaces retained; **brain commit before advancing**. | 16 CPUs, 15 workers + coordinator |
| 4 | BOSS teacher read | Immediately after ROOT | JournalTeacherR3 reads the whole retained ingest/book and writes the teacher/Dipole rows; **measured teacher knowledge enters Frankie's brain before classroom**. It keeps the original math/representation/targets/masks/controls role. | Same held 16-CPU lane |
| 5 | Frankie classroom | **Immediately after BOSS teacher** on classroom-arm discovery days | Frankie learns from ROOT + BOSS teacher, covers the governed classroom components, is graded/corrected, files new findings as claims, and **commits the classroom brain entry immediately**. | Same held lane; class order remains sequential |
| 6 | Data export | After teacher; after classroom on classroom-arm days | Exposes the permitted ROOT/day/teacher material with a manifest while withholding Frankie's private decision process and graded answer key. | Same held lane |
| 7 | Causal series + search | After data export | Builds the per-day causal axis and tests relationships per cell/lag/transform with the leakage gate and each test's circular-shift chance check. Counts/days are the findings; coefficients stay scoped, never pooled; **search knowledge commits immediately**. | **Scientific teacher's evidence engine**, same held lane |
| 8 | Scientific teacher: carried claims | After the day's search | Tests historical claims and causally prior Frankie/Jev claims against all discovery searches available so far; reports counts, scoped support/contradiction/unresolved states and proposed tests. | Same held lane |
| 9 | Scientific teacher: today's Frankie findings | After classroom + search, before the meeting | Tests today's new/novel Frankie claims against the searches available so far. | Same held lane |
| 10 | Survivor/candidate update | **Batch/cross-day boundary, not a per-day lane blocker** | Builds scoped candidate/survivor relationships from completed discovery evidence. A day's classroom may consume only survivors completed before that classroom; no same-day circular promotion. | Cross-day code; NOT fully built |
| 11 | Three-way meeting | After today's Frankie findings have been tested | Frankie + BOSS teacher + scientific teacher discuss the tested findings. Granite may only voice the three code-generated seats under R17; it does no calculation or decision. | Meeting is sequential in classroom order; voice transport not yet wired |
| 12 | Frankie end of day | After meeting (or after the recorded voice-not-wired state) | Consolidates the brain/lessons/exchange already written during the day into school knowledge and numbered reports; **not the first knowledge write**. | Same held lane |
| 13 | Jev blind comparison | Classroom-arm discovery days; governed material only | Jev receives the classroom material/survivors but never Frankie's answers before filing his own claims. His claims are labelled and feed later scientific-teacher testing. Prefer local/small CPU hosting if sufficient; no standing GPU Pod requirement. | Jev |
| 14 | Freeze discovery survivors | After the discovery set is complete | Freeze the survivor list once; no confirmation data has been used to select it. | Cross-day code; NOT fully built |
| 15 | Confirmation | Only after survivor freeze | Run the frozen relationships on untouched 2024-2025 confirmation days, per cell, including maker/taker/net-cost treatment where applicable. | CPU; NOT fully built |

### Non-classroom discovery days

They still run ROOT -> BOSS teacher -> data export -> causal search -> carried-claim scientific-teacher work. They do not
run Frankie classroom, meeting, school retention or Jev unless the plan explicitly marks them as a classroom-arm day.

### Cross-day timing rules

- **Scientific teacher = search/evidence engine.** The later 2026-09-29 scientific-teacher decision supersedes the
  earlier joined-teacher wording that made the BOSS teacher the search owner. The BOSS teacher consumes and discusses
  the evidence while retaining its original teaching/math role.
- **Survivors are cross-day.** They update at batch boundaries from already-completed discovery evidence; they do not
  block every individual day and are never built using confirmation days.
- **Single-occurrence findings receive equal treatment (Greg, 2026-10-06).** One occurrence is just as valid and
  certain as multiple occurrences when its mathematics and science check out after the work is double-checked.
  Double-check the actual calculation, source evidence, timing/leakage and scientific test for the stated claim.
  Once those checks hold, use the same acceptance, survivor, teaching and knowledge treatment as for any other
  checked finding. No minimum-days/occurrences gate, rarity-based uncertainty label, confidence discount or automatic
  hypothesis-only status. Occurrence counts are descriptive evidence, not an acceptance handicap. Preserve the exact
  scope of the checked result and list actual errors, contradictions or incomplete checks on their merits. A day
  without the relevant condition supplies no new test opportunity and does not downgrade an already checked finding.
  This explicitly supersedes the older R06 prohibition on promotion after one appearance. Existing causal, answer-wall
  and discovery/confirmation ordering rules still apply; the double-check is part of scientific work, not a new test farm.
- **No same-day circular teaching.** A classroom cannot be taught a survivor that depends on that same classroom day's
  findings. It may use only an earlier completed survivor set.
- **Jev stays blind.** His governed input may be produced after Frankie's classroom files physically exist, but the
  relay must contain only the material Frankie was allowed to see, never Frankie's answers. Jev's claims are evidence
  for later scientific-teacher passes, not truth.
- **Confirmation wall remains hard.** Confirmation days stay untouched until the discovery survivor list is frozen.

### Lane and traffic-controller rule

A day is assigned once at ROOT and remains on that same box and 16-CPU booking until its last applicable day stage
finishes or the run is explicitly stopped/saved. The stage changes; the execution lane does not. On a 32-vCPU box this
means two simultaneous day lanes. A 16-vCPU worker is one lane. Worker processes are pinned inside the booked CPU set;
no cross-day CPU double booking.

The main-box ROOT/class traffic controller already implements held slots. The remote worker agent is still ROOT-only and
must be changed to execute the same ROOT-to-finish day runner instead of shipping a day back immediately after ROOT.

### Testing rule

Do not build a test harness, extra validators or canary suite for this workflow. After the wiring is complete, perform
**one real ROOT-to-finish end-to-end run** on an already-ingested discovery day using the real receipts and lane logic.
Fix actual failures as they appear and resume from retained receipts. After that succeeds, feed the 30-day pipeline.


### Granite final experiment role (Greg 2026-10-06)

Granite 4.2 is the **bounded active coordinator/facilitator** of the post-class three-seat discussion. It is not merely
a voice, but it is also not a scientific seat. Charter:
`knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`; classroom rule R17:
`knowledge/CLASSROOM_RULES_V3.json`.

Granite may ask bounded follow-up questions, surface scope disagreements, keep unresolved items and next tests organized,
and request that a code seat perform/name the next test. It may never calculate, grade, select survivors, confirm a
hypothesis, alter confirmation, forecast or trade. Any requested calculation runs in the appropriate code stage and
returns source-bound evidence before the discussion continues. Useful discussion knowledge enters Frankie's brain
immediately.

The old B2 critic/self-assessment role remains historical/full-system code but is **not part of this 30-day experiment**.

Hosting priority for this small coordinator role:
1. local if practical;
2. standard public-repo GitHub Actions CPU runner with official Granite 4.2 8B GGUF/llama.cpp if meeting latency is acceptable;
3. an existing small AWS CPU box, started only for meetings;
4. paid GPU only as a fallback.

No standing Granite GPU/Pod is part of the experiment.

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
- **Data access (Greg, 2026-09-29):** both teachers read every bit of Frankie's ingest data (the journal, every book
  level) and every calculation layer directly, except the files Frankie generates himself to reason toward forecasts
  (R09); no teacher data is built a second or third time. Full text: `SPEC-scientific-teacher.md`, "Data access".
- **Frankie's 13 historical data points ride with his ingest (Greg, 2026-09-29; the 13th, the futures curve shape, has
  a time-only leak guard like the ingest: everything up to a decision's cutoff, refused past it):** "everyone who sees his ingest should
  see these data points too". One file per trading day beside the sealed ingest (native resolution, publication time
  on every value), read by Frankie, both teachers and the search alike; built once. Text: `SPEC-scientific-teacher.md`.
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
| 3 ROOT | the calculations root (Greg, 2026-09-29: "we forgot root in the experiment"), WITHOUT the bedrock | `frankie_box_monday_calculations.py` (`Session.derive(bedrock=False, digest=False)` / `frankie_box_monday_calculations.sh BEDROCK=off DIGEST=off`, BUILT 2026-09-29, not run: the ROOT's four processes are (1) the legacy pass, (2) the bedrock traversal, (3) the bedrock projection, (4) the Markdown digest; the experiment runs (1) only; still Monday-only until the day parameter is built) | the ROOT's own outputs: `derive.json`, the 5 legacy layers, and the row spools `work/derived/.rows/*.jsonl` (every INPUT record decoded, prices, book frames, structures, failures), with the pin, source binding and receipt |
| 4 export | every data JSON of the day and cycle from ROOT, CONFIG and CYCLE (built 2026-09-29, not run) | `frankie_box_experiment_data.sh ACTION=plan\|export` (`frankie_box_experiment_data.py`, a catalog) | `/opt/frankie-box/work/experiment-data/<day>/cycle-<NN>/<stage>/...` hard-linked + MANIFEST: files, excluded (R09 Frankie's reasoning, R10 grades, bedrock, mixed, other models' output, each with its reason), missing (a stage that never got that far), unclaimed (listed with bytes). Replaces the calc-only `export_calculations` for the experiment; that one still runs from `brain_entry` and no longer leaks the two bedrock section files |

Not called:
- the trading-day preparation (native context, the teacher);
- the principal inputs, the launch, the Pods and Granite, on every day; the brain entry and the classroom, except on the
  three classroom-arm days below (where it is Frankie's code, still without the launch, Granite or a Pod);
- the digest render (Frankie's read format; the experiment reads the JSON).

## The new part (built after the orchestrator)
5. **Series:** from the exported day data (step 4): the ROOT's row spools (every INPUT record already decoded by ROOT, so
   the journal is NOT decoded a second time), the legacy layers, the schedule, the teacher's Dipole measurements and the
   cycle records. Where a field exists only in the sealed journal (e.g. every resting order at a group close), the journal
   is read in place through `FrankieCompactReader`, never re-written. Everything goes on one time axis per day ordered by
   the entry ordinal / cursor (receive clocks can run backwards), and every row carries only what was knowable at that
   moment (the causal clocks).
6. **Search:** series x transforms x lags x cells x conditions x targets.
   - Every test gets its own circular-shift chance check.
   - Results are reported as counts, never coefficients or averages (D37).
   - The leakage gate (`odcore/leakage.py`) runs on every target.
   - Start from the joined-teacher builder (dfe08ca7): its sign-step coupling and cells, pointed at the journal and the calculation JSON instead of the bedrock.
   - FIRST SLICE BUILT 2026-09-29, not run: `deploy/aws/box/frankie_box_experiment_search.py` (+ `.sh`,
     `box-experiment-*` lock). Series from the exported day data on the F_LAST axis via DuckDB ASOF; the leakage gate
     runs odcore on each source's real alignment (a hollow first version that could not fail was caught and replaced
     before commit); sign-of-step couplings at every lag -L..L per cell with the joined teacher's statistic and
     circular-shift chance check, as counts; discovery days only unless a frozen survivor list is given; one day per
     run; the not-yet-searched sources, transforms, conditions, targets and claims listed in the MANIFEST. DuckDB is
     installed into the box venv by `frankie_box_venv_duckdb.sh` (duckdb 1.5.5 + bundled extensions + pyarrow; Greg's go).
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

## The classroom arm: EVERY DAY (Greg, 2026-09-29, latest)
"Just run every pair will get teach and class. It's easier that way unless we see that process is taking a long time."
The orchestrator default is now `--classroom-arm-cycle 5/5`: every discovery day gets the teacher and the classroom,
pairs in order (the second day of a pair carries the first's classroom history). The 2/5 cycle below is kept as an
option if the classroom step turns out slow.

## The classroom arm (Greg, 2026-09-29: "just at the beginning run and last 2 runs"; REVISED the same day)
REVISED (Greg, 2026-09-29, later): "I'm going to have it run on day 1 & 2 so they can apply their findings and then off
3,4,5 then back on for 1,2 and so on. If we are finding that their part is pretty quick, I might go back to all 5 but
I'll see how days 1 and 2 go first." So the arm runs on discovery days 1 and 2 of every five in date order, off on 3-5
(orchestrator `--classroom-arm-cycle 2/5`, the default; `5/5` = every day; an explicit `--classroom-arm` list wins).
The first-and-last-two rule below is superseded by this cycle.
(Superseded:) The FIRST discovery day and the LAST TWO discovery days (before the survivor list is frozen) also run the plan's governed dipole classroom (C14/D5), so the teacher and Frankie work on
new dipole data and push the dipole research forward (D51: the dipole is open research).
- **The added pieces of today's run it calls** (all reused):
  - the teacher on that day's journal: JournalTeacherR3 with the teacher changes (all levels, the whole day, unknown trades carried), read once beside the context walk (saved walk blocks, the concurrent teacher);
  - the classroom package: `prepare_integrated_cycle`, without the scientific dialogue per the plan;
  - the principal's classroom stage, answered by Frankie's code (`frankie_box_classroom_code.py`, no Granite): the 19
    components, the summary and the correction, under `knowledge/CLASSROOM_RULES_V1.json`;
  - Frankie's brain entry (Greg, 2026-09-29: his outputs and his lessons from the teacher go into his brain): the day's
    classroom ledgers and analysis through `frankie_box_brain.write_entry`, as in the full run, plus the scientific
    teacher's lessons on his claims (the same JEV_LESSONS_V1 shape, author frankie), carried into his next
    classroom-arm day. Not built: part of the classroom-arm build (step 8);
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
- **His brain (Greg, 2026-09-29: "his outputs should go into his knowledge base in his brain too", "and his lessons
  from the teacher while he's learning"). BUILT 2026-09-29, not run.** On S3 (D34) under `clm-sidecar/jev-brain/`:
  - `entries/<day>-<stamp>.json` (JEV_BRAIN_ENTRY_V1), written at the end of each of his days: his claims whole, the
    unparsed answers, the material pins, the brain files he carried in, `claims_sha256`, `include: true`.
  - `lessons/<day>-<stamp>.json` (JEV_LESSONS_V1), written by the scientific teacher once it has tested that day's
    claims, bound to the entry by `claims_sha256`: `{schema, day, stamp, claims_sha256, written_by:
    "scientific_teacher", results: [{claim_id, tests: [{series, transform, lag, cell, condition, target, days,
    counts, chance_check}], disposition (orientation only, R14), challenge ("the data is showing this instead ...",
    R07), untested: [..]}]}`. Counts, never an average (D37). Its writer is part of the search build (6b).
  - On his next day `launch.py --jev` hands him every entry and lessons file; `sit_in.py` reads them whole, puts them
    beside the day's material as YOUR BRAIN (each earlier claim with the teacher's lesson on it, or "pending"), and
    tells him to build on what held and to say what he claims instead where the data showed something else.
  - The same day is never run twice (a second entry for a day declines the run). His brain NEVER carries Frankie's
    answers or the comparison: that would make his next claims lean on Frankie's and end their independence.
- **Before it is built:** Greg adds Jev to the Excel build plan with this track (unplanned = unwired).

## The teacher's Dipole rows: 1 day in 5, batched (Greg, 2026-09-29)
Greg: "Just for the sake of speed we decide to do 1 of 5 days and when it runs it will take the accumulated data from
off days and run it on 5th." The teacher (JournalTeacherR3, CPU only, no Pod, no model) runs on every 5th discovery day
over the accumulated days since its last run, so every day ends with its Dipole rows:
- Each day is its OWN walk on its own sealed journal, starting fresh; the batch never walks across days (that would
  carry one day's state into the next: pooling, and a broken causal wall).
- The days of a batch run in parallel on the box's CPUs (the speed is there: one wall-time of a day for five).
- The search runs on the same rhythm: teacher x5, then search x5, then the scientific teacher's lessons; searching
  daily without the Dipole and again later would build the same thing twice.
- Lessons on Dipole claims lag by up to four days; until then a brain shows them "pending".
- A classroom-arm day already has its Dipole rows from the launch; the batch skips it (duplicate data declines).
- Built next: the teacher-only step (the retained_preparation_recovery call, as a box script).

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
