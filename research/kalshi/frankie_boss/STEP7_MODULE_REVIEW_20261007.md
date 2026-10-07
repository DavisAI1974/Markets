# Step 7 module/interface and AWS review — 2026-10-07

SOURCE REVIEW ONLY / RUNTIME UNVERIFIED. Reviewed checkout `439cb0bf71968f30f94b696b85acfaa00dccc3c1`
with concurrent shared-file edits preserved. Applied using-agent-skills, context-engineering,
API and Interface Design, and AWS `aws-compute` plus its Systems Manager reference.
AWS tools retrieved documentation only. No account calls, tests, imports of project code,
installs, model/data/reproduction runs, dispatch or starts. No model, runtime, quantization,
token budget or CPU allocation was chosen. This review does not close Step 7.

## Authorized follow-up built

After Greg requested implementing the findings, the root agent assigned disjoint source
ownership for two narrow repairs:

- `done_status` and `_finish_day` no longer count retired `waiting_for_pod` handoffs as
  finished. Original receipts remain retained; the current waiting CPU route stays pending.
- `scientific_teacher.upload_jev_lessons` extracts the existing exact-byte PUT. First write
  and standalone retained-result recovery use it, so a failed lesson upload can be repaired
  without repeating scientific computation. It checks teacher schema/author/writer and
  day/stamp filename identity, and returns transport hash/length/status only. Missing `MAP_URL`
  preserves the prior optional transport behavior; it does not count as delivery. The Step 4
  owner was asked to add the same call to `Run.lessons`'s separate reuse branch.

These repairs do not implement CPU owner-local seals, persistent per-consumer delivery
receipts, consumer readback or end-to-end day completion. No client state or request identity
was rewritten. AST parsing without project imports and `git diff --check` passed for the
three touched Python modules. The initial findings below remain a record of the reviewed
boundaries; gaps 2 and 3 are narrowed by the repairs above.

## Actual module and contract map

| Boundary | Actual source / interface | Preserved contract and remaining connection |
|---|---|---|
| Classroom → blind material | `deploy/aws/box/frankie_box_experiment_classroom_v2.py`: `run`, `jev_material` receipt | Writes `jev-material/classroom-request.json` before answers; receipt carries path/hash/length. Owner CPU route must consume that exact receipt and governed attachment, not private classroom state. |
| Material → transport | `deploy/aws/box/frankie_box_jev_relay.sh`: `ACTION=material`, `material_bundle`; `JEV_DAY_MATERIAL_V1` | Carries whole classroom/external/survivor objects and missingness. CPU owner-local route is absent; retained HTTP relay is not an authorized launcher. |
| Day owner → Jev | `deploy/aws/box/frankie_box_experiment.py`: `Run.jev`, `jev_stamp` | Remote stage ownership respected; classroom-arm day requires completed classroom/material. Returns `waiting` because CPU transport is unwired. Generated stamp is stable by run/day; it does not itself schedule testing. |
| Model request → retained reply | `research/kalshi/frankie_boss/clm_sidecar/sit_in.py`: `bind_inputs`, `recorded_chat`, `begin_phase/end_phase`; `JEV_SIT_IN_PROGRESS_V2` | Binds actual material/brain/output destinations/client bytes and parameters. Saves request intent before call; whole replies and failure bytes retained. Completed replies replay; pending/failed/changed requests refuse automatic retry. Preserve original state and identities. |
| Claims → seal → comparison | Same client: `prepared_json`, `main`; `JEV_CLAIMS_V1`, `JEV_COMPARISON_V1` | Exact claims prepared before PUT. Local filed-seal equality gates reading Frankie. Comparison stays orientation only and out of Jev's brain. No consuming-owner seal readback exists. |
| Sealed claims → scientific teacher | `deploy/aws/box/frankie_box_scientific_teacher.py`: `jev_claims`, `freeze_operation`, `test`, `write`; CLI `--jev-claims` | Existing claim parser hashes consumed bytes but does not validate against a Jev seal/receipt. Existing scientific operation pins do not prove the input was the blind-sealed claim object. Reuse scientific computation on its actual owning search; do not rerun the batch. |
| Teacher → two knowledge consumers | Same teacher: `write`, `publish_lessons`; `JEV_LESSONS_V1` → Jev lesson object and Frankie `jev-tested` | First write optionally PUTs Jev lesson through `MAP_URL`, then publishes tested knowledge to Frankie immediately. Recovery only retries Frankie publication; Jev lesson delivery has a concrete gap below. |
| Day completion/reporting | `deploy/aws/box/frankie_box_frankie_queue.py`: `_finish_day`; experiment `done_status`; `clm_sidecar/jev_report.py` | Held day must retain ownership through claims, scientific test, both knowledge deliveries and reporting. Legacy handed-off completion remains accepted. Reuse existing report number; client `status=done` means client phase only, with scientific tests explicitly pending. |

`deploy/aws/box/frankie_box_durable.py` remains the common atomic/fsync/readback writer.
The retired standalone bootstrap cannot supply this repository-module dependency and must
not be revived. CCode owns Step 8A controller/workflow Pod refusal; this review changes none
of those files.

## Concrete source gaps, separate from decisions

1. **Teacher consumption has no seal witness.** `jev_claims(path)` checks `JEV_CLAIMS_V1`
   and derives `claims_sha256` from whatever bytes are present. Neither the local-file CLI
   nor legacy stamp download receives a sealed claim receipt to compare expected day, stamp,
   byte length/hash and blind material binding. A CPU owner operation must read back the
   durable claims and require that exact seal before test/publication. A model-authored blind
   flag or HTTP PUT acknowledgment alone does not establish the boundary.
2. **Jev lesson delivery is not recovered.** `write` durably saves a lesson before its
   optional Jev-brain PUT. If that upload fails or execution stops there, the retained-result
   branch in `main` calls only `publish_lessons`; `Run.lessons`'s reuse branch does the same.
   Those calls publish to Frankie but never repair the missed Jev lesson upload. Separate
   exact-byte delivery receipts are needed for both consumers; replay a completed lesson,
   never repeat the scientific test to repair delivery. The current local CPU delivery
   destination remains to be wired.
3. **Legacy handoff can still mean day completion.** `done_status` accepts
   `waiting_for_pod` plus `material_sent`; `_finish_day` accepts `HANDED_OFF` outright.
   `Run.jev` does not currently produce that status, but retained/imported legacy receipts
   can traverse the generic status contract. An old material handoff must remain retained
   as historical progress, not satisfy completed Jev science or release its day. Shared
   runner/queue owner should remove this acceptance when wiring the completion contract.
4. **Automatic lesson selection is not bound to the produced Jev result.** `Run.lessons`
   uses explicit plan `jev_stamp`, whereas `Run.jev` may generate its stamp. The scientific
   shell wrapper exposes only `JEV_STAMP`, although Python accepts `--jev-claims`.
   Its reuse lookup returns every `jev/<day>-*.json`, without selecting by sealed claim hash.
   CPU wiring needs an exact owner-local sealed result and lesson identity, not a day glob
   or a second broad batch call. Remote searches deliberately refuse central consumption.
5. **Client recovery correctly refuses unresolved calls but has no owner disposition.**
   Pending intent is uncertainty, not proof of dispatch or a fresh retry authorization.
   Keep request body/hash, response evidence, source/session/day/stamp and original attempt
   visible when reporting the refusal. A separately checked resolution/successor contract
   remains required; do not clear pending state to progress.

These involve shared teacher/runner/queue interfaces. Source ownership was requested before
the narrow follow-up above; other gaps remain with the owning root agent. A new scheduler,
generic validator framework or scientific acceptance rule is unnecessary.

## Unsettled choices that this review does not decide

- CPU runtime/build, model artifact and its exact pins; legacy `Qwen3-8B`/`model='jev'`
  strings are not a pinned CPU implementation.
- Approved subset of the held 16-CPU lane and runtime thread controls; never borrow another
  lane or overlap cores already in use. Linux-owned day evidence stays on that lane.
- Tokenizer-correct input/output room, elapsed-time policy and unresolved-call handling.
  The current characters/3 estimate and 900-second socket timeout establish neither exact
  token capacity nor an overall operation deadline.
- Exact completion policy when comparison is unavailable or claims remain unparsed, and
  the owner acknowledgment of all required artifacts. Do not infer a verdict or fabricate
  completion from the client's report/receipt.

## Compatible processing-speed work and holds

| Aid | Why it applies here | Action / limit |
|---|---|---|
| Match CPU-runtime threads to the approved held-lane subset | AWS documents that common inference libraries can spawn threads for all visible vCPUs, causing contention. | At CPU launcher wiring, bind applicable runtime thread controls and affinity to the approved subset. Exact runtime and subset are undecided; no numeric defaults, benchmark, installation or EC2 change made. This transfers a threading principle from AWS's EKS documentation, not its Pod deployment. |
| Reuse completed replies and scientific results | Existing durable request replay and retained-result path avoid duplicate model/test computation during recovery. | Preserve those paths while adding missing delivery receipts. Do not recover an upload by making another model call or rerunning science. This is existing source behavior, not a measured speedup. |
| Keep material, model service and scientific evidence on the same held owner | Proposed CPU route can avoid the legacy remote relay/download round trip and keep large evidence local. | Wire governed owner-local artifact/readback boundaries after host/runtime decision. No additional AWS service or machine proposed; no measured transfer reduction claimed. |
| Avoid repeated full-state serialization if it becomes material | `save_state` rewrites the growing request/reply history; the durable writer retains prior versions. Source inspection shows cumulative write growth as calls accumulate. | Potential later split into immutable per-call evidence plus small durable index needs an explicit versioned recovery design. Not a safe casual optimization: preserve existing pending identities, complete bytes and prior state. No evidence dropped, writer weakened or new schema introduced here. |

AWS EC2 CPU options distinguish vCPUs from physical cores/SMT threads; reducing CPU options
does not reduce ordinary instance charges. Changing instance topology is not the way to
allocate this task's existing lane. No account or topology inspection was performed.

Documentation retrieved 2026-10-07 (official sources; no account actions):

- AWS MCP skill `aws-compute`, `references/systems-manager.md`: reuse existing controlled
  SSM/instance-profile transport; command delivery is not scientific completion. No new
  credential route, service or managed node setup was performed.
- [CPU Inference and Orchestration](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-cpu-inference.html)
  — controlled inference threading; deployment examples are not this project's topology.
- [CPU options for Amazon EC2 instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-optimize-cpu.html)
  — vCPU/core/SMT semantics and CPU-option pricing distinction.

Verification: direct source/interface review, AST parsing without project imports and
whitespace checks only. No runtime verification or throughput evidence exists.
