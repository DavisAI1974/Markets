# CCode Step 7 caller supplement — 2026-10-07

This is the narrow caller contract for the source-built Jev CPU route. It supplements
the existing Step 8 assignment without transferring ownership of its recovery code.
The Jev source received independent source review, including comparison evidence,
completion policy and isolated peer transport. It has not been executed or deployed.
At preparation these changes are in the shared integration working tree; the coordinating
agent publishes the commit. Read the published integration tip before wiring the caller.

## Ownership and required call

CCode owns `Run.jev`, `Run.child`, retained main/class continuation and `cores.DAY_RUN_STAGES`.
Add `jev` to that existing stage list and invoke `frankie_box_jev_cpu.sh` through the
original held-day child path (`cores run --inside`), with `JEV_REQUEST`, `MARKETS_SHA` and
`CODE_ROOT`. The helper enters with exactly the retained 16 CPUs. Its explicitly configured
worker subset excludes the coordinator CPU and runs sequentially on that same lane.
There is no new booking, host, provider, Pod or fourth lane. Preserve the fixed three lanes.

Only a discovery classroom-arm day is accepted (`day_role: discovery`). Do not route a
holdout day through this helper or silently count missing configuration as completion.
Existing legacy Jev code/Pod strings do not provide a configured CPU runtime.

## Immutable request and configuration

Persist `JEV_CPU_REQUEST_V1` before dispatch, retaining these original fields:

| Fields | Meaning |
|---|---|
| `run`, `day`, `day_role`, `stamp`, `attempt`, `owner`, `host` | Original run/day/ROOT attempt and consuming owner. Assign the Jev stamp once. |
| `plan_sha256`, `slot_booking`, `cpus` | Original plan, live day booking and its exact ordered 16-CPU list. |
| `source: {commit, code_root}`, `save_marker` | Original staged source and the existing exact day save marker path. |
| `output`, `brain`, `jev_brain` | Absolute owner-local continuation, Frankie brain and Jev brain directories. Reuse them on resume. |
| `report_number` | The already-assigned positive day report number; allocate no replacement number. |
| `classroom_receipt`, `search`, `runtime` | Exact `{path, bytes, sha256}` pins. Use the actual completed classroom producer receipt, the owning day's search `MANIFEST.json`, and explicit runtime config. |
| Optional `prior_brain` | Owner-local copied Jev entry/lesson pins with `kind: entries|lessons` and optional stable `key`. Never foreign-owner absolute paths. |

The helper retains request/source/classroom session identity in `owner.json`. It pins the
classroom receipt's governed `jev_material`; it seals claims before reading Frankie's
answers. Required comparison files are `ledgers.json` and the receipt, plus
`external-code-answers.json` for the V2 classroom receipt. Optional analysis can be unavailable.
Do not replace producer evidence with an orchestrator step-status receipt.

Runtime must be a supplied `JEV_CPU_RUNTIME_V1` with `engine: llama.cpp-cpu`, exact binary
and model pins, `model_name`, explicit worker `cpus` within the original `cpus[1:]`, and
positive `context_size`, `max_output_tokens`, `min_output_tokens`, `token_margin`,
`piece_chars`, `process_seconds`. Supply `completion: {comparison: required, unparsed:
requires_review}` or the explicitly chosen `listed` disposition. CPU count, model/build/
quantization identity and token/time budgets remain concrete setup choices; invent none.
The shared transport supports `cpu_only=True` using `--n-gpu-layers 0` and checks affinity.

Resume the same request bytes, stamp, output, source and attempt. Unknown model dispatch
cannot be resent. Changed inputs or source require explicit owner recovery, not a fresh
forecast under a replacement identity. Frozen prior knowledge is checked for corrections;
stale selection refuses continuation rather than silently changing an existing inference.

## Completion, save and gained knowledge

| Child outcome | Required parent evidence and disposition |
|---|---|
| Exit 0 | Exact `receipt.json`, schema `JEV_CPU_RECEIPT_V1`, `status: done`, matching original owner/request, claims seal, frozen scientific result, both consumer delivery witnesses, client and numbered-report pins. Only then satisfy Jev. |
| Exit 5 | Retained receipt with pending comparison disposition, or `JEV_CPU_STATUS_V1` diagnostic. Preserve waiting/unknown and the original continuation. Do not retry ambiguous model calls. |
| Exit 75 | `status.json`, schema `JEV_CPU_STATUS_V1`, `status: saved`, matching request/owner, actual child PID/process-start, retained state and exact marker witness when present, no unresolved model calls. Validate against Step 8's child acknowledgment protocol; an exit code alone is insufficient. |

No helper path deletes the marker or releases the booking/claim. A running model call
retains its reply before cooperative save; an unresolved call is waiting, not saved.
Saved is continuation evidence, never scientific or day completion.

Use the existing lane knowledge boundary before Jev selection, including recovery of any
pending existing lane-sync request. After a validated `deliveries.json`/receipt shows
completed publication, execute the existing knowledge boundary even when comparison
disposition keeps Jev waiting. Retain/recover that boundary's existing intent instead of
inventing another provider dispatch; a pending sync remains pending and must not erase
the completed local inference/science/delivery evidence.

Peer Jev knowledge is now automatically selected from the existing synced knowledge roots.
The helper writes `brain/jev-peer/<day>-<stamp>/own-entry.json` and `teacher-lesson.json`,
then an immutable `JEV_PEER_KNOWLEDGE_V1` manifest LAST. The narrow `lane_state.snapshot`
extension transports those typed files through existing owner-version snapshots. Generic
Frankie entry globs exclude the namespace, keeping raw Jev claims outside his corpus.
Jev explicitly selects that audience, applies checked corrections, freezes exact pins,
and deduplicates `(kind, sha256)` mirror/local copies while retaining differing claims.
No private comparison is admitted. No additional peer transport or scheduler is required.

Both immediate local consumer deliveries are explicit: Jev's actual lesson reader
readbacks the scientific lesson, and Frankie's existing `jev-tested` publication is
checked for the same exact lesson. These witnesses show available knowledge, not a new
model response or native learning cycle. Preserve that distinction in parent reports.

No runtime, model, scientific, data, AWS, installation or E2E operation was performed by
this source task. CCode's caller integration and real supplied configuration are still
necessary; subsequent E2E authorization and staged one-day/three-day inspection remain
separate from this source handoff.
