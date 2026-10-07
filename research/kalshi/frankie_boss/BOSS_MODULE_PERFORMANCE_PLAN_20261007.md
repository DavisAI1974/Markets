# BOSS module and CPU performance plan — bounded source slice implemented

Current status, 2026-10-07: Greg subsequently authorized improvements which do not change the science. The bounded B1–B3 source slice and B4 invariant hoist below are implemented; B5/B6 and all execution remain held. Original review base: `439cb0b` plus the existing uncommitted integration work visible in the shared checkout. Actual host/model/checkpoint availability and performance are unknown. Verification is source review, AST parsing without project imports and whitespace checking only: no tests, installs, model/data/scientific runs or AWS account calls.

## Implemented source slice after Greg's authorization

- **B1:** `ContextSessionRunner.prepare` now dispatches through an explicitly installed preparation callable or the unchanged serial `_prepare` body. The five-part tuple shape is typed and unchanged. A host cannot overwrite an installed provider, and release must name the identical callable. The cache accepts an optional explicit serial/parallel/recovery preparation callable; old callers may omit it. `ActualHost.prime_cache`/`close_cache` use this owned provider lifecycle rather than overwriting the instance's `_prepare`. Its existing cache receipt, source/model/teacher/QSV/checkpoint identity checks, defensive clones and release-after-checkpoint behavior remain.
- **B1/B3 callers:** context inference, `NativeForecastRefresh`, `NativeForecastLearner`, native critic preparation, `FrankieController._snapshot` and the live-controller preview all use the public preparation method. Restore and `parallel_journal.prepare_parallel` intentionally call the serial implementation, avoiding recursion. The actual classroom already reads the same cache and needs no alternate cache. No copy elision or causal-scan substitution was made.
- **B2:** `ParallelContext.encode` submits at most twice the existing worker CPU count of chunks at a time, consumes in source order and replenishes after each completed chunk. The original chunk arithmetic, reconstruction, seam/parent/age work and output construction remain. On failure pending futures receive cancellation; the executor drains running work. The existing reader/held-lane worker budget is reused, without changing lane count or affinity policy. All input and final output remain present; only queued work is bounded.
- **B4:** `NativeTrunk.represent` computes the identical positional frequency tensor once per call. Width, dtype and device are the same; each event's positions, embedding lookup, multiplication, sum order and projection remain unchanged. No alternate kernel, precision, random operation, learned-state reuse or target change was introduced.

**Precisely still open:** process-global adapters in `parallel_journal.parallel_walk` and `parallel_teacher` remain as existing pin-sensitive machinery; this slice removes host instance-method replacement only. General checkpoint-hook refactoring, new stage metrics, zero-copy ownership, causal summaries, pool reuse and broader CPU policy changes were not implemented. Retained starting state, objective/auxiliary and three-lane lineage choices remain Greg's B5 decisions. B6 numerical/kernel candidates remain deferred. No before/after speed, gradient equality or runtime success is claimed.

**Code identity:** `context_session.py`, `native_mbo_encoder.py` and the native caller sources participate in existing model/execution/config hashes. Their changes produce new code identities through those unchanged hash functions. No pin, historical artifact, checkpoint witness or acceptance guard was modified, and no migration/reinitialization was added. Existing retained state must still satisfy its declared identities; this code does not silently authorize resuming an old checkpoint under new source.

**Review evidence:** all ten changed Python files parsed with `ast.parse` without project imports; scoped `git diff --check` passed. Independent source review by the Step 9 review agent found no concrete blocker in provider call coverage/lifetime, serial restore versus provider recursion, cache clone/checkpoint guards, ordered bounded work and cancellation/draining, the frequency expression's dtype/device/operands, or unchanged identity refusal logic. This is source evidence only; no test, import, forward, gradient update, retained-state load or runtime measurement occurred.

**Source files changed by this slice:** `context_session.py`, `prepared_context_cache.py`, `parallel_context.py`, `native_mbo_encoder.py`, `native_forecast_learning.py`, `native_forecast_refresh.py`, `sunday_native_runtime.py`, `frankie_controller.py`, `granite_live_controller.py`, and `operations/run_actual_sunday.py` (only provider initialization/prime/close; preserve Step 2's independent waiter correction). No checkpoint, target, mask, control, loss, model configuration, CPU count or science formula file was changed beyond the invariant frequency hoist described above. Remaining sections retain the original proposal and decision rationale; this current status supersedes their pre-approval wording.

The API and Interface Design, Context Engineering, Using Agent Skills and Performance Optimization skills were applied, together with AWS `aws-compute` and its instance-selection guidance. Their implementation/runtime verification steps remain behind Greg's plan-confirmation and execution holds. The companion `FRANKIE_MODULE_PERFORMANCE_PLAN_20261007.md` owns Frankie's calculation planes, replay and classroom/principal boundary; this plan owns the native BOSS representation, teacher contract, native learning and checkpoint boundary. Shared experiment/controller work is coordinated through the current step reports, not a second orchestration stack. CCode's Step 8A files remain his.

## 1. Proposed order and decisions

1. Confirm the B1–B3 source scope below: document existing contracts, introduce explicit preparation-provider boundaries, and bound outstanding parallel preparation work without omitting any work. Reuse the existing cache, parallel readers and checkpoint updater.
2. Settle retained-state ownership before any native integration: name the authoritative existing model/decoder/optimizer/checkpoint, or authorize locating it on its owner. Missing state remains a refusal, never a fresh initialization.
3. Separately decide the existing native objective's use, any proposed Dipole auxiliary connection and its weight, and model lineage across the three day lanes. This plan selects no new objective, label definition, auxiliary weight or merging rule.
4. After source implementation and wiring discussions, Greg may separately authorize the one real AWS E2E and its agreed measurements. No extra test or validator framework, automatic benchmark sweep, training run, or thirty-day run follows from approving this plan.

**Recommended first approval:** B1–B3 and the narrow B4 invariant-hoisting candidate, with source-only acceptance. B5 native integration and B6 numeric/kernel changes stay separate decisions. Approving module cleanup does not establish mathematical equivalence or runtime improvement.

## 2. Nonnegotiable preserved behavior

- Exactly three held 16-CPU lanes: two main, one Linux; each has 15 worker CPUs plus the coordinator. A day retains its owning lane. BOSS work uses that lane's existing allocation; no fourth lane, Pods, automatic fleet change, or concurrent unbudgeted worker pool. Giant evidence and authoritative checkpoints stay owner-local.
- Retain every applicable record/field and teacher input, original source/forecast/request/session identities, causal receive availability, exact source ordering, raw evidence and answer walls. A bounded queue bounds work in flight, not data consumed. No subsampling, row/byte cap, output pooling, cross-run average, replacement summaries or invented labels.
- Preserve targets, states/masks, controls, representation, original native training role, actual market prices/spreads and typed identity/missingness bindings. Dates/weekdays/IDs remain grouping/identity context rather than invented numeric signals or targets. No trading-cost, fee, slippage or profit objective is introduced.
- Preserve existing configured context length, attention window, QSV setting, B1 recurrence, precision and optimizer. A historical default is not permission to impose a smaller context or a different run. Memory A remains retired; H06–H08 remain historical/not_bound.
- Preserve pending feedback and uncertain-state refusals. Teacher/classroom lesson consumption does not imply native weight training; Granite stays inference-only. Use `BossTrainingCheckpoint.apply_completed`, not a new updater or a classroom substitute.

## 3. What the current source establishes

Paths below are relative to `research/kalshi/frankie_boss/` unless prefixed otherwise. Symbols are stable review anchors; live source may advance after this review.

| Boundary | Source and current contract | Source proof and remaining limit |
|---|---|---|
| Exact event representation | `native_mbo_encoder.py`: `NativeRegistry`, `encode`, `reconstruct_payloads`, `NativeTrunk.represent` | Every supplied event has a token and exact byte span; numeric semantic views use float64 sign/high32/low32 plus explicit masks; exact identity keys build order ancestry. All bytes enter position-dependent learned embeddings. No runtime fitting or throughput follows from this. |
| Trunk and reasoning | `trunk.py`: `FieldEncoder`, `GatedDeltaCell`, `SlidingWindowAttention`, `TemporalGraphBranch`; `b1_reasoner.py`: `_run`, `forward_decision` | Separate numeric/categorical missingness and optional QSV; causal ancestry; exact QSV ablation; configured recurrence and receipt. Audited decision is batch one. `TrunkConfig.window` is 128 although the attention class docstring says full history by default: configuration/source is authoritative; correct documentation without changing it. |
| Teacher targets | `dipole_target.py`: `DipoleTargetSpec`, `DipoleTarget`, `TargetState`, `masked_mse`; `c15_teacher_r3.py`: `_paired_raw`, `JournalTeacherR3.attach` | Ordered target names/units, manifest/prefix/builder/normalizer binding, PRESENT/MISSING/INVALID/ABLATED state and receive cutoffs. R3 consumes the full verified prefix; its two raw consumers already share one ordered traversal. Do not propose that existing paired traversal as new work. |
| Teacher controls | `teacher.py`: `make_targets`, `verify_controls`, `run_experiment` | Arms `none`, `plain_aux`, `shuffled`, `random`, `dipole`; plain auxiliary derives from numeric inputs only; shuffled target and mask travel together under a derangement; random noise is refreshed; paired initialization is checked. This control experiment is a distinct path from continuing a retained native model. Do not invoke its initialization as a recovery mechanism. |
| Causal preparation | `context_session.py`: `journal_prefix`, `ContextSessionRunner._prepare`, `run`; `prepared_context_cache.py`: `PreparedContextCache` | Full prefix validation selects the declared entity context, encodes and reconstructs it, attaches teacher/QSV, and binds tensors/packets. Cache is cutoff/source/model/teacher/QSV/checkpoint bound and returns detached owned copies. It is not safe to reuse across a weight update. |
| Existing preparation acceleration | `parallel_journal.py`: `prepare_parallel`; `parallel_context.py`: `ParallelContext.encode`; `parallel_teacher.py`; `operations/run_actual_sunday.py`: `prime_cache`, `close_cache`, `phase` | Host already installs parallel preparation, primes the cache and uses `cache.prepare` until checkpoint readback/release. Retained preparation recovery also exists. The cache module's “not wired” docstring is stale. Parallel preparation uses temporary function/global replacement, which is an interface concern, not proof of current arithmetic failure. |
| Native forecast objective | `native_forecast_learning.py`: `LearningConfig`, `FrankieFeedback`, `NativeForecastLearner.step` | Explicit attested feedback, complete ordered session roster, causal labels and optimizer identity. Timing stage uses STOP presence and delay losses; path/gap stage freezes timing dependencies and fits available values. `teacher` is attached but no Dipole auxiliary loss is added here; result says `teacher_optimized=False`. A teacher receipt alone is not a trained representation. |
| Durable native update | `feedback_cycle.py`: `CycleCoordinator.run`, `complete_pending`, `_finish_feedback`; `boss_training_checkpoint.py`: `BossTrainingCheckpoint.apply_completed`; `sunday_execution.py`: `complete_pending_cycle` | Feedback validation precedes the normal updater. Request uniqueness, completed-controller binding, monotonic training cursor, single-writer transaction, exact model/optimizer/RNG state and checkpoint chain protect updates. Unknown mutation requires close/restore; pending completion preserves its original model predecessor. |
| State and runtime identity | `native_model_artifact.py`; `native_runtime_policy.py`; `sunday_native_runtime.py` | Exact snapshots and numeric/runtime identities already exist. The Sunday initializer explicitly creates an untrained development candidate. It does not establish that its state is the right retained starting state today. Thread/toolchain changes are a new declared numeric/run identity, not transparent resume. |
| Classroom boundary | `deploy/aws/box/frankie_box_boss_session.py`; `CCODE_STEP4_SOURCE_ROUTE_20261006.md` native-representation section | Code classroom and checked-knowledge consumption preserve original sessions but are not native optimizer steps. Retained starting state, objective/auxiliary combination and cross-lane lineage remain decisions. Companion Frankie plan owns this producer side. |

The file/symbol trace is evidence of source behavior only. Existing tests were read as contract references (`tests/test_boss_control_preservation.py` and the native/teacher/checkpoint test files); none were executed, and old test success is not asserted here.

## 4. Prioritized source changes after confirmation

### B1 — Make current BOSS boundaries explicit without replacing scientific code

**Files:** `context_session.py`, `prepared_context_cache.py`, `native_forecast_learning.py`, `feedback_cycle.py`, `boss_training_checkpoint.py`, `operations/run_actual_sunday.py`; adjacent contract documentation.

**Proposed interface:** one typed `PreparedContext` return containing tokens, preparation metadata, input hash, teacher attachment and ordered context rows. One narrow preparation provider takes `(as_of, through_cursor)` and returns that value. Providers are current serial preparation, existing parallel preparation, exact retained recovery and existing cache. The host chooses one explicitly. Avoid a generic plugin/service framework or new REST layer.

Keep existing public method signatures and result schemas readable through a compatibility adapter first. Expose current private host hooks through narrowly scoped methods; move cache lifecycle ownership to the host without instance/global monkeypatching. Retain restore-on-failure semantics for existing callers during transition. Name source, teacher, model, checkpoint and session identities separately; never overload one hash as another. Represent completion, pending feedback and uncertain mutation as distinct existing states at the consumer boundary.

**Expected benefit, unmeasured:** fewer hidden dependencies and accidental cross-request mutation; easier review of exactly which preparation a forecast and update consumed. No numerical speedup is claimed. Moving modules/functions changes code pins even if arithmetic is unchanged: declare the successor code identity and retained-state migration before use; do not edit old evidence or make an old checkpoint accept new code silently.

**Acceptance after source approval:** a complete caller/return/error/cancellation trace preserves every current output key and refusal; math-bearing loops and canonical encoding are unchanged; cache release occurs after committed update and on failure. Correct stale preparation-wiring and attention-default documentation. No execution is needed to claim this source-only acceptance.

### B2 — Bound parallel preparation memory and make CPU ownership explicit

**Files:** `parallel_context.py`, `parallel_journal.py`, `parallel_teacher.py`, `frankie_journal_reader.py`, `operations/run_actual_sunday.py`; share the current lane contract with the runner owners.

`ParallelContext.encode` currently builds a future for every `CHUNK` slice before consuming them in order. Propose a bounded submission window replenished by the ordered consumer, following the bounded window already present in `parallel_journal.py`. Retain every chunk, complete row reconstruction, byte partition, seam check, parent link and age calculation. Keep stateful parent/age reconstruction and teacher evolution ordered. Use the current serial fallback for unsupported readers rather than treating an unsupported optimized reader as complete.

A provider receives the held lane's explicit worker CPU set and coordinator CPU, rather than inventing a host-wide worker count. Reuse a pool only where lifetime/cancellation and memory ownership can be demonstrated; do not parallelize stateful recurrence or optimizer steps merely because 15 worker slots exist. Nested pools must fit the same allocation or run sequentially.

**Expected benefit, unmeasured:** bound queued Python rows, encoded blobs and completed futures waiting on an earlier chunk; reduce queue/RSS spikes and allocation pressure. Final tensors and retained evidence still consume their full required memory. This change does not make an arbitrarily large dense model forward fit.

**Acceptance:** every submitted source ordinal returns once in original order; an early error cancels/drains pending work and retains failure state; no success marker precedes all output/seam verification. Chunk size and queue depth are operational choices to confirm from the future authorized measurement, not new scientific windows. Existing sampled cross-checks remain; they are not described as proof of universal equivalence.

### B3 — Reuse exact preparation and remove redundant transport only where source identity permits

**Files:** `prepared_context_cache.py`, `context_session.py`, `native_forecast_learning.py`, `operations/run_actual_sunday.py`, `operations/run_actual_sunday_classroom.py`, `retained_preparation_recovery.py`.

Reuse the existing cache already used by the actual Sunday host. Do not add another cache or promise to eliminate scans it already eliminates. Separate measurements of cache construction, tensor/container cloning, live identity validation, learner causal scan and checkpoint serialization. On the new explicit provider boundary, reuse the exact preparation only for the same cutoff, source tail, entity/context declaration, teacher/normalizer/QSV state, model and checkpoint.

First retain all current copies and checks. If the authorized measurements show copies dominate, propose one caller-owned prepared view with explicit read-only ownership and clones exactly where a consumer can mutate. This is a later reviewable subchange, not removal of defensive copies by assertion. Similarly, a source-prefix causal summary may replace a repeated scan only if its exact bound validation covers the same every-row/all-session predicate; never trust a receipt which did not compute that predicate.

**Expected benefit, unmeasured:** avoid repeated full-prefix materialization where a consumer bypasses the current cache; potentially reduce clone/serialization overhead after ownership proof. Initial preparation, mutation checks and required model work remain. Unchanged identity is not enough if a consumer can mutate shared tensors.

**Acceptance:** unchanged preparations preserve all tensor dtype/shape/bits, rows, mask states, target/attachment hashes and input identities; stale source/model/checkpoint refuses. Never serve stale checked knowledge merely to improve cache hits. A correction produces its proper successor and invalidates dependent preparation through explicit lineage.

### B4 — Small invariant hoisting inside the existing representation, only with explicit code lineage

**File:** `native_mbo_encoder.py`: `NativeTrunk.represent`.

The positional frequency tensor depends on model width, device and dtype but is currently recomputed for every event's byte span. Propose computing that identical tensor once per call outside the event loop. Keep each event's positions, all bytes, embedding lookup, multiply, ordered reduction and projection unchanged. Do not introduce padded batched reductions, mixed precision, byte pooling or a trained-representation cache. Begin with this narrow candidate, not a new encoder implementation.

**Expected benefit, unmeasured:** fewer redundant tensor/exponential allocations for many events. The byte embeddings, positional sine work and every sum remain. Source equivalence is plausible from the invariant dependencies; bitwise and gradient equivalence are runtime-unknown until separately authorized verification. Any unexplained difference is a stop, not permission to loosen tolerance.

### B5 — Complete native training integration only after Greg settles its three decisions

**Files:** `native_forecast_learning.py`, `feedback_cycle.py`, `boss_training_checkpoint.py`, `sunday_execution.py`, `native_model_artifact.py`, and the existing owner-side caller. Coordinate the lawful feedback producer with the companion Frankie plan.

1. Bind the located retained native/decoder/optional teacher state, optimizer/RNG, model/config/code/source identity and last checkpoint witness. No call to `sunday_native_runtime.initialize` as a missing-state fallback.
2. Preserve the currently selected attested timing or path/gap objective. If Greg wants the existing Dipole `TeacherHead` connected to native training, present a separate mathematical change: teacher attachment point, governed target/state alignment, auxiliary weight, optimizer parameter ownership, control comparability and checkpoint migration. `NativeForecastLearner` currently requires exactly native+decoder optimizer ownership while the checkpoint can optionally contain a teacher; adding a trainable head is therefore a contract change, not wiring an unused argument.
3. Declare whether model lineage is one ordered global chain or intentionally distinct lane models. Recommended discussion starting point is one authoritative ordered update writer with predecessor-bound requests; do not let three lanes concurrently mutate one state or average their weights/outputs. This recommendation is not a selected lineage policy. The source training cursor is monotonic within its bound source, so cross-day/cross-source ordering needs an explicit mapping, not a reused local integer cursor.

**Expected benefit, unmeasured:** actual use of the intended native learning role under reliable lineage, if authorized. No forecast improvement or training-speed claim is possible from source inspection. A blocked/pending label remains pending; host timeout is not evidence of no update.

### B6 — Defer larger numerical performance changes until evidence and separate approval

`SlidingWindowAttention.forward` materializes dense `(B,H,T,T)` logits even when a finite window masks most entries. `GatedDeltaCell.forward` evolves sequential state, and B1 invokes additional attention/memory rounds. These are credible CPU/memory pressure points from code, not measured bottlenecks of the stopped current run.

Do not now change attention window/context length, reduce recurrence, replace the delta cell, introduce alternate kernels, quantize, change dtype, train fewer controls or change minibatch/reduction order. A future exact-window attention implementation could avoid computing masked logits but may change floating-point reductions and gradients; it needs an explicitly versioned numerical candidate and Greg's equivalence standard. Full-attention configurations cannot be “optimized” by silently imposing a finite window.

## 5. Mathematical and evidence impact to review

| Invariant | Required preservation / decision |
|---|---|
| Auxiliary mask | `masked_mse = sum(mask * (prediction-target)^2) / sum(mask)`; zero-present case refuses. Missing, invalid and ablated remain distinct evidence states even though none contributes to loss. No mask-to-weight reinterpretation. |
| Controls | Preserve numeric-only fixed plain auxiliary; target/mask joint derangement; per-step noise and real mask; all five arms and paired seed initialization. No “performance” omission of controls or fresh initialization of retained production state. |
| Native feedback loss | Preserve current per-session component means, explicit component/session weights and denominator over configured session weights. Preserve missing-value masking, teacher forcing, timing freeze during path/gap stage and causal label availability. No adjustment of denominators as cleanup. |
| Numeric precision | Native event/model path requires float64. Current governed teacher target construction uses float32 tensors and int8 states. Preserve each existing dtype separately; do not claim all BOSS tensors are float64 or upgrade/downcast teacher bytes silently. |
| Model representation | Every exact byte contributes; order ancestry and identity bindings stay intact; QSV remains separately governed/ablatable. Audit role annotations for current identity fields without removing existing representation inputs or promoting dates/IDs to new numerical signals. Any semantic reclassification needs its own decision. |
| Context and causality | `t_ctx` is caller-declared; all prefix rows are verified and outside-context accounting remains explicit. Keep receive order/ties, all source fields, answer walls, original source/entity selection and full teacher prefix evolution. No new arbitrary cap. |
| Identity changes | Source moves, new callable boundaries and runtime/thread changes can change model/training hashes. Keep historical artifacts immutable and provide declared successor/migration provenance. “Same maths” does not mean “same recorded code hash.” |
| Update atomicity | Unique request + matching controller result/cursor; full optimizer/model/RNG state; monotonic lineage; unknown mutation closes/restores. Never parallelize updates across an undecided predecessor chain or bypass pending outcome feedback. |

## 6. Measurement plan, held until execution is explicitly authorized

Use existing learner stage callbacks and `runtime_resource_probe.py`/host progress hooks to attribute the one agreed E2E: preparation/read/decode, encoding/reconstruction, teacher attachment, cache verification/copies, model forward, backward, optimizer, checkpoint encode/write/readback. Record actual rows/bytes, CPU time, elapsed time, process/child RSS, lane CPU affinity and artifact identities alongside existing evidence. Keep telemetry outside mathematical/canonical result payloads unless its schema change is explicitly reviewed.

AWS `aws-compute` guidance distinguishes CPU, memory and storage workloads and says durable state belongs on durable storage. Applied here: preserve the existing lanes and owner-local durable checkpoint/evidence placement; do not jump to a new instance family, Spot, Arm, GPU or additional host. Its general provisioning instructions are not invoked under this hold.

AWS documentation identifies EBS queue depth, latency, throughput/IOPS and exceeded-limit metrics as relevant to diagnosing storage pressure. If Greg authorizes monitoring during the E2E, correlate those with checkpoint/write phases and total host activity, especially the two main lanes sharing a host. Current EBS type/configuration and metric availability were not inspected. Do not infer “disk bottleneck” from a slow checkpoint alone or change provisioning without evidence and approval.

Official documentation consulted (2026-10-07, docs-only):

- [AWS guidance on EBS performance and queue depth](https://repost.aws/knowledge-center/optimize-ebs-provisioned-iops).
- [AWS EBS latency, throughput and IOPS metrics](https://aws.amazon.com/blogs/storage/understanding-and-monitoring-latency-for-amazon-ebs-volumes-using-amazon-cloudwatch/).
- AWS MCP `aws-compute` skill and `references/instance-selection.md` (retrieved through the installed AWS plugin).

No baseline or improvement percentage exists for these proposals. The permitted one E2E may establish a baseline and correctness evidence, but cannot by itself prove repeatable before/after speedup. Additional repeated benchmarking would require separate authorization. Retain an optimization only when the authorized evidence supports both preservation and benefit; do not call a source-only change a performance win.

## 7. Approval record to fill before implementation

| Decision | Proposed disposition |
|---|---|
| B1 explicit preparation/learning/checkpoint contracts | Approve source-only work after reviewing this plan; keep adapters and old evidence readable. |
| B2 bounded ordered preparation and lane budget | Approve source-only work; no data reduction, execution or new lane. |
| B3 existing-cache reuse and measurement hooks | Approve narrow provider integration first; copy elision and causal-summary substitution need demonstrated ownership/equivalence. |
| B4 frequency invariant hoist | Approve only as a small separately reviewable code-identity successor; benefit/equivalence remain unmeasured. |
| B5 retained state, objective/auxiliary and cross-lane lineage | Greg's explicit choices required; implementation remains held. |
| B6 kernels, numerical schedule and resource changes | Deferred; no implicit approval. |
| AWS E2E / runtime measurements / training / 30 days | Separate explicit authorization; this plan grants none. |

The original review wrote only this plan. The subsequent authorized source slice is listed at the top. No native state was opened through project code, changed, initialized or advanced.
