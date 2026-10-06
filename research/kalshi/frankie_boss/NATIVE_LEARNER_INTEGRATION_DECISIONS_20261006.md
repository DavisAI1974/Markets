# Native learner integration decisions — 2026-10-06

Source review only. No model/data run, test suite, installation or AWS action. This document selects no new model,
objective, update policy or execution date. Steps #2/#3 remain open; the preserved #5 draft remains unapplied.

## Settled mission and existing roles

All applicable normal ingest/calculation evidence, including full-depth FIFO and bedrock information, must reach
Frankie and both teachers alongside accumulated knowledge. Teachers should reuse the shared evidence. Completed
knowledge is available at applicable execution boundaries across all random-order days; trading-date order is not a
learning gate. Preserve exact scientific mathematics, lawful raw/answer availability and equal treatment of checked
single occurrences. Private trade-decision logic is excluded. These requirements do not need another approval.

R4 Components C14–C16 establish the original BOSS targets, complete native evidence and auxiliary representation
supervision. C16 specifies a TeacherHead and MSE loss, with output width/names bound to C14; it also names extending
evaluation beyond binary `p_up` as unfinished. C36–C38 add scientific research, exchange and school knowledge rather
than replacing that role. `SPEC-joined-teachers.md` and the current experiment directive preserve the same distinction.

The active experiment classroom calls code answer/reproduction functions and records `model_calls=0`
(`frankie_box_experiment_classroom_v2._run`). ROOT's existing source binding says it forecasts nothing through the full
pipeline. Scientific search, measured findings and code knowledge reuse are real source connections, but they do not
prove learned native representations or live recognition. The native forecast/training framework already exists
separately; reconnect its actual consumers rather than building a second learner framework.

## Reusable source contracts

| Connection | Existing implementation | Required experiment binding |
| --- | --- | --- |
| Native model and source context | `sunday_native_runtime.initialize`; `ContextSessionRunner._prepare(as_of, through_cursor)` | Restore the intended model/optimizer checkpoint; bind the journal, entity, source/input hashes and explicitly declared context. Initialization is a fresh untrained development candidate, not continuation. |
| Original targets and masks | `frankie_box_experiment_teacher` retains `teacher-attachment.pkl`; `parallel_teacher.finish` returns original `DipoleTarget` objects, raw rows and receipts | Align each target with the exact model-context cursor and prefix. `DipoleTarget.to_batch_fields()` supplies values, presence mask and states. Preserve original units and missing reasons. |
| Representation supervision | `B1Reasoner.forward_decision(...).representation`, `TeacherHead`, `dipole_target.masked_mse` | Actually connect same-input representation, governed target/mask and chosen auxiliary objective; retain its model/optimizer state. Classroom prose or six-column views cannot substitute. |
| Forecast update | `NativeForecastLearner.step` | Supply request ID, causal `as_of`/`through_cursor`, source/input hashes, full sessions and roster hash, attested `FrankieFeedback` and hash, and lawful learning cutoff. Current experiment does not author this forecast/feedback contract. |
| Durable update | `BossTrainingCheckpoint.apply_completed` | Bind completed request/result identity, a valid advancing training cursor, model/optimizer lineage and exactly-once callback. Restore after uncertain mutation. |
| Live use | `NativeForecastRefresh.update` | Reuse the trained model and causal source mapping with explicit sessions/cutoffs; connect applicable derived evidence and knowledge. Live throughput and recognition quality remain unverified. |

`sunday_native_runtime.initialize` currently constructs the existing float64 CPU B1/NativeTrunk and forecast decoder;
it does not select a pretrained external model. It installs the active teacher changes with identity normalization.
Its `context_rows` is required from the verified schedule; the Monday author sets it to the whole declared day record
count. A generic context-window mechanism is not evidence of an active 4,096-row cap. The old `SPEC-sunday-runtime.md`
contains superseded 4,096-row/normalizer/Pod descriptions; do not restore them from that historical document.

## Three integration decisions, not a new mission discussion

**1. Retained starting state.** Establish the current retained native model/decoder/optimizer checkpoint location and
independent identity before wiring continuation. `operations/run_actual_sunday.ActualHost._training` already restores
`<configuration.run_directory>/training.sqlite` against `training-witnesses/state-*.c15.json`. The historical restoration
manifest records a 107,556,864-byte database at `E:/Codex/Frankie-BOSS-20260915/actual-feedback-run/training.sqlite`, SHA256
`696cee058d911dae6733496f91b2a8a83a1cdd89fb3158238ea0287222df5e6e`, explicitly outside Git. That is historical provenance,
not proof of the current AWS location or a trained/accepted model. Locate the retained state first; only an actual
absence or incompatibility requires a fresh-initialization/migration decision from Greg.

**2. Actual BOSS learning objective and state.** R4 already establishes masked auxiliary representation supervision;
the inspected R4/current directive/specs do not select its production weight or combination with this experiment's
native learning objective. `NativeForecastLearner.step` currently optimizes forecast timing or gap/path objectives,
does not include TeacherHead loss, and reports `teacher_optimized=False`. The Sunday runtime's selected timing weights
are presence/delay one, gap/path zero. They are existing forecast settings, not an auxiliary-loss authorization.
`teacher.run_experiment` has a default auxiliary weight of `0.1`, but belongs to the older five-arm, multi-seed,
binary-`p_up` comparison harness. Do not invoke that harness or import its default as a settled production choice.
Settle the intended native objective/auxiliary combination and its versioned state migration before connecting weight
updates. `BossTrainingCheckpoint` supports an optional `teacher` model, but changing model/optimizer layout cannot
silently rewrite an existing checkpoint. This decision preserves C14's mathematics; it does not invent new targets.

**3. Execution-order model lineage across lanes.** Knowledge sharing is settled. Mutable model/optimizer sharing needs
an explicit ordering contract: the existing checkpoint is single-writer, source-identity-bound and requires strictly
increasing `training_cursor`; the old coordinator passes one source's `through_cursor`. Day-local cursors restarting at
zero cannot become a global cursor by assumption. Keep each raw prefix/cutoff intact and distinguish it from update
order. Resolve ownership, stale prepared-input/checkpoint handling and recovery before activating shared updates.

**Discussion proposal only:** one versioned model/optimizer lineage with queued updates in actual execution order.
An owning day lane obtains the next committed model version, performs its update against its own local source and
lawful target/knowledge snapshot, and publishes the next exact version before another update can commit. Preparation
made against an older model version must be explicitly rebound/recomputed where required; it cannot silently reuse an
old input identity. Other lanes may continue their authorized source/calculation work. Giant raw evidence remains on
its owning lane; model-state transfer/versioning is separately specified. No weight averaging, pooled gradient update,
trading-date gate, extra lane or change of day owner is proposed. This policy is not implemented or selected here.

## Remaining source wiring after those bindings

The native encoder currently consumes exact raw records and declared metadata. Bedrock outputs, external tables and
accumulated findings do not enter its computation merely by sharing a directory. Reconcile those lawful typed inputs
with the existing native/QSV/knowledge contracts, availability clocks and original teacher role. Preserve separately
matured future labels: learning may use them once available, while an earlier live input may not. Reuse the original
forecast/feedback coordinator's completion and checkpoint rules where applicable without importing its retired Granite,
Pod or historical arm workflow. CCode's scientific-teacher/facilitator ownership remains separate.

Sources inspected: the R4 workbook `artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx` (C14–C16, C36–C38 and auxiliary
references); `SPEC-experiment-orchestrator.md`; `SPEC-joined-teachers.md`; `SPEC-sunday-runtime.md` with the source
supersessions above; `knowledge/EXPERIMENT_DIRECTIVE_V1.json`; `sunday_native_runtime.py`; `context_session.py`;
`native_forecast_learning.py`; `native_forecast_refresh.py`; `teacher.py`; `dipole_target.py`; `boss_training_checkpoint.py`;
`feedback_cycle.py`; `sunday_execution.py`; `operations/run_actual_sunday.py`; `parallel_teacher.py`; and the existing
experiment ROOT/teacher/classroom callers. No runtime acceptance is inferred from these sources.
