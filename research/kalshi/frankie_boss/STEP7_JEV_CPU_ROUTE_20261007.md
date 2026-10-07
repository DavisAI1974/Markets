# Step 7 — Jev CPU route, source trace and first correction

Greg started step 7 on 2026-10-06 at 22:49 ET. At 22:52 ET he confirmed Pods are eliminated;
the alternatives under consideration were GitHub CPU, the existing small AWS box, and local.
At 22:53 ET he asked why Jev cannot use the day's existing 16-CPU lane. Codex recommends that
route: a bounded subset of the already-booked CPUs, sequential with other day compute, no
fourth experimental lane or second booking. This is the proposal for discussion, not a chosen
CPU count, pinned model runtime or authorization to execute. Those lanes are CPUs, not GPUs.

SOURCE-BUILT / RUNTIME-UNVERIFIED. No tests, installs, model/data/project runs, reproduction,
AWS inspection/action, start, dispatch or E2E. The source brain-reader correction below is
independent of host choice. Granite's pins and code remain with CCode's step-6 work.

## Why Jev was separate

The separate machine is inherited deployment code, not an isolation requirement that needs a
Pod. `clm_sidecar/launch.py --jev` creates the old GPU service; `pod_bootstrap.sh` starts its
model server; `sit_in.py` talks to the chat endpoint. The active `Run.jev` currently returns
waiting with the prepared classroom material because that Pod path is retired. It cannot
complete a day. Do not enable the old launcher as a fallback.

Jev's scientific role stays a blind outside student: same permitted classroom material,
his own prior claims and teacher lessons, proposed claims sealed before any Frankie answers,
then a labelled comparison. His model outputs are hypotheses; the scientific teacher owns
checks and resulting teaching. Host sharing does not by itself expose Frankie answers;
the selected input files and sealed-claim boundary must enforce that separation.

## Existing path and exact remaining work

| Boundary | Existing implementation | Remaining work |
|---|---|---|
| Material | `experiment_classroom_v2` writes `jev-material/classroom-request.json` before answers; relay builds the governed material/external/survivor bundle | Reuse the material receipt and exact available survivor pins on CPU; never open whole private classroom state to Jev. |
| Model | `sit_in.jev` calls an OpenAI-compatible chat endpoint; old bootstrap serves the existing Jev model on a GPU | Pin an explicit CPU runtime/model artifact; verify context/token budgeting and CPU allocation without changing Granite's configuration. No throughput claim yet. |
| Progress | `sit_in` now uses the shared durable writer, binds selected contents, records each request intent and whole reply, and replays completed replies while rebuilding packs | CPU model/runtime identity and operation orchestration still need wiring. An uncertain call refuses automatic retry; owner recovery/successor handling remains open. Legacy state is refused, never reset. |
| Seal | `sit_in.main` now durably prepares exact claim bytes before PUT and verifies the saved local seal before reading Frankie outputs; comparison bytes are likewise prepared | A retry after PUT reuses identical bytes without model regeneration. CPU owner-local claim artifact and remote/consumer readback verification still need wiring; local state plus HTTP acceptance is not that consumer verification. |
| Brain | `load_brain` renders Jev's entries and teacher lessons; comparison stays out of his brain | First source fix below retains every lesson and whole objects. The client now binds actual selected contents on retry; CPU source inventory and runtime identities still need integration. |
| Scientific test | `ST.jev_claims`, `ST.test`, `ST.write`, `ST.publish_lessons` already read labelled claims and immediately publish tested Jev knowledge as `jev-tested` | Bind the consumed claims to the sealed receipt, call this existing scientific path on the owning completed search, return lessons to Jev and publish immediately to Frankie. Do not treat the model comparison as a test. |
| Completion | `_finish_day` calls `Run.jev` last; accepts FINISHED or the legacy handed-off status | Define completed claims/testing/publication/brain/report receipts for CPU; material handoff alone must not claim finished scientific work. Preserve owner/slot recovery. |
| Reports | Existing numbered Jev reports and the day report number | Reuse the day's number and retained whole evidence; avoid a new numbering or reporting subsystem. |

`Run.lessons` only schedules Jev when the plan entry has `jev_stamp`; the generated stamp in
`Run.jev` is not sufficient by itself. The CPU route must schedule testing from the sealed
result on its actual owner, including when that owner is the Linux lane. Existing scientific
CLI accepts `--jev-claims`; its shell wrapper currently exposes the legacy stamp transport.
Do not call the whole batch a second time or assume worker-local searches are readable centrally.

## First source correction built

`clm_sidecar/sit_in.load_brain` used a dict keyed by claims hash, so the last teacher lesson for
a claim set overwrote the previous one. It also projected claims to selected fields and omitted
lessons without a carried entry. It now retains each lesson, renders complete included entry
and lesson objects, and labels unmatched lessons by their own binding. It verifies supplied
byte/hash witnesses and explicitly records when a legacy selection had no expected hash.

The student prompt now preserves older knowledge and asks for research of conflicts about the
same thing. It keeps both accounts while unresolved and preserves unaffected knowledge under
partial replacement. A newer result alone establishes no replacement. No automatic scientific
adjudication, model change, training or host choice was introduced.

Checks: direct source/interface review, AST parsing without project imports, git diff --check.
No runtime result is established by this source correction.

## Recovery and prepared-claim source correction

The client now records `JEV_SIT_IN_PROGRESS_V2` through the existing
`deploy.aws.box.frankie_box_durable` writer: fsync/readback, atomic replacement and retained
previous bytes. It must be invoked as a repository module; the retired standalone Pod bootstrap
is not a supported deployment. Failed saves propagate. Malformed state, another day/stamp and
legacy state without the new binding refuse instead of being discarded.

Before model work, the state binds the actual material bundle, full rendered brain and consumed
brain byte/hash witnesses, output destinations, client-source hash and current client parameters.
Presigned credential refreshes for the same object are allowed; object/version query parameters
remain part of the destination identity. This does not pin an unselected CPU model/runtime.

Every model request has a durable pre-send intent. Complete raw reply bytes (including malformed,
non-JSON and cut-off replies) are saved before interpretation. Caught read failures retain received
chunks and failure evidence. On restart, note/claim traversal reconstructs from the same replies;
request mismatch or an unknown/failed outcome refuses automatic model retry. A pre-send intent
is explicitly not proof the server received a call. No pending call is silently marked completed.
The current 900-second socket timeout is still the legacy client setting, not an overall operation
deadline; CPU runtime, exact token budgeting, elapsed-time policy and interrupted-operation
reporting remain open. A hard process kill may leave received-but-not-durably-saved bytes unknown;
the retained intent makes that uncertainty explicit and prevents repeating the request.

Claims and comparison documents now have exact prepared bytes/hash/length retained before PUT.
A crash after a successful PUT reuses identical bytes and timestamps, never regenerates claims.
The local filed seal must match prepared claim bytes before Frankie material is opened. Selected
comparison material is bound and a changed/missing retry refuses. Transcript gzip metadata is
stable on retry. Existing reports still say scientific tests are pending; no teacher call or
scientific completion is invented. Model accounting distinguishes recorded replies from intents
with no reply. Full recovery evidence remains in owner-local state for the future CPU route.

Checks were source/interface review, `ast.parse` without project imports and whitespace checks
only. This is host-independent source work; no client, model or upload was invoked.

## Hosting discussion

Current recommendation after Greg's 22:53 ET question: run Jev on the owning day's existing
AWS CPU lane, with the existing held booking and a bounded CPU subset. It keeps the local
material/search/results together and avoids an additional remote dispatch/import chain. It
also occupies the lane longer; actual model duration/memory use remains unmeasured. Do not
start Jev while another process is using the same reserved cores. The exact CPU subset,
model/runtime pins and completion policy still need settlement before the CPU path is wired.

Other options examined without any execution:

- Standard GitHub Linux runners have 4 CPUs/16 GB RAM for public repositories and 2 CPUs/8 GB
  for private repositories. Which entitlement applies must be verified; no repository visibility
  change is proposed. The official Jev 8B GGUF has a roughly 5.03 GB Q4_K_M weights file, before
  context/runtime memory. Inference: the private 8 GB runner is a tight candidate for the
  existing 32k context; file size alone is not a fit or speed measurement. No quantization chosen.
- The handoff names an existing `r6i.2xlarge` small box; AWS documents 8 vCPUs and 64 GiB for that
  type. That is capacity information, not a fresh inspection of the instance or its installed
  runtime. A separate host still needs the bound material/claims/result return path.
- Local execution depends on which machine Greg means and its OS/CPU/RAM; those facts are not
  known here. The chat execution workspace is not assumed to be Greg's permanent local host.

Official sources read 2026-10-07 UTC (no binaries downloaded):
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://huggingface.co/Qwen/Qwen3-8B-GGUF
- https://aws.amazon.com/ec2/instance-types/r6i/

The repo's `experiment-orchestrator` skill and step-1 handoff explicitly reserve Jev CPU and
day-completion choices for discussion. They do not require pausing independent source repairs;
they do require not silently choosing a host/runtime or treating this discussion as AWS go.
Step 7 remains incomplete.
