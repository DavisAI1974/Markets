# Step 6 retained CPU meeting source slice — 2026-10-07

SOURCE-BUILT / RUNTIME-UNVERIFIED. The existing pinned Granite 4.2 3B Q4_K_M,
llama.cpp b11440 and confirmed eight runtime parameters remain unchanged. This
slice adds retained runner intake and verified return around the existing
meeting/owner importer. Step 6 still needs the exact remote owner-admission caller
described below. It does not start a host, download a model or run a meeting.

## Source completed

- `frankie_box_granite_meeting.LlamaServer` honors the explicit `cpu_only` transport
  flag with `--n-gpu-layers 0`; Granite supplies it, and the Jev CPU helper uses the
  same narrow transport capability. No meeting prompts or scientific role transfer
  to Jev. The server refuses before spawn when the resolved thread count exceeds
  its effective CPU affinity. The confirmed `threads: null = os.cpu_count()` rule
  remains intact; this is not a silent new allocation or an extra lane.
- `frankie_box_granite_runner.prepare` binds the downloaded exchange to the owner's
  SHA256 and exact dispatched commit/run/day. Resume verifies the complete archive
  SHA256, exact file inventory and each file's bytes/hash before restoring progress,
  binding, records, attempts and full evidence. No symlink, duplicate member or
  escaping path is accepted. Different retained identities refuse.
- The Granite workflow accepts `exchange_sha256`, `prior_state_get_url` and
  `prior_state_sha256`. Intake runs before setup or model work. A GitHub rerun without
  retained state refuses; continuing a failed prior dispatch requires a new dispatch
  with its complete state archive and original commit. Concurrent requests for the
  same exchange serialize. Existing local pending-call behavior preserves unknown
  replies as open items and never repeats those calls.
- Remote model setup/calls are explicitly held pending owner admission. Inputs-only
  remains available; `inputs_only: false` permits only verified completed-record
  replay. A retained incomplete archive does not authorize new calls. Local owner
  execution still uses its existing meeting lock and unchanged pinned configuration.
- The workflow seals `runner-state.zip` plus `runner-state.json` after success or
  failure whenever intake completed. The archive includes the entire output tree
  except the advisory lock; the return JSON contains the archive hash. Existing
  `return.json`, complete meeting record and optional record PUT remain. Each
  attempt has a distinct artifact name, preserving previous attempt artifacts.
- The runner helper's explicit `import` command verifies/restores the returned
  archive, then invokes the existing owner importer. That importer checks the
  retained plan, completed ROOT/exchange, source currentness and record shape before
  brain publication. It does not independently attest runtime execution or runtime
  pin verification. The new archive helper separately checks complete records'
  input/config/model/binary/parameter witnesses against their retained binding and
  committed configuration; these witness checks are not runtime attestation.
  A matching previously restored intake
  reuses its exact files; missing files from interrupted intake can finish without
  replacing differing bytes. Publication remains the existing idempotent owner path.

## Source interfaces

Workflow dispatch requires the retained exchange's SHA256 in addition to its HTTPS
GET URL. For a continuation, supply the prior `runner-state.zip` HTTPS URL and the
SHA256 in its `runner-state.json`; use the same source commit. Do not launch another
fresh dispatch of the same owner operation as a substitute for unavailable retained
state. Workflow concurrency prevents overlap, not historical deduplication across
arbitrary fresh manual dispatches. Therefore this workflow currently refuses all
remote model work, including incomplete-state continuation, until owner admission
is wired. Lost/expired state leaves the outcome unknown.

The owner-side transport can download the returned archive into its existing work
area, then invoke the following source-built command when execution is authorized:

```sh
python deploy/aws/box/frankie_box_granite_runner.py import \
  --exchange "$OWNER_EXCHANGE" --exchange-sha256 "$OWNER_EXCHANGE_SHA256" \
  --commit "$ORIGINAL_DISPATCH_COMMIT" --archive "$RETURNED_STATE_ZIP" \
  --archive-sha256 "$RETURNED_STATE_SHA256" --out "$OWNER_RETURN_INTAKE"
```

The original owner supplies these witnesses; no URL or path is fabricated. The
helper performs no download and no model call. The receipt from the existing
importer identifies actual publication. Artifact upload, a source patch and an
archive hash alone are not publication or successful runtime verification.

## Exact remaining caller contract: CCode-owned `Run.voice`

1. Retain immutable intent before dispatch, binding original exchange bytes/source,
   run/day, code/config and meeting input, owner and any complete prior-state witness.
2. Retain the original GitHub run identity after dispatch. An uncertain dispatch
   outcome must be reconciled to that intent, never resent as a fresh run.
3. Before model setup/start, the runner must receive and verify the owning lane's
   acknowledgment admitting this exact GitHub run and exact retained predecessor.
   Restore a previous incomplete attempt only after its original process is known
   stopped and its complete state is reconciled; never reuse an older archive as
   permission to repeat calls possibly completed by a newer attempt.
4. Return/reconcile complete archive and record through the existing verified owner
   importer. The owner records completion before admitting any successor attempt.

No such remote admission operation was found in the existing runner/lane interface.
This slice does not invent S3/Git locking, another scheduler, or a substitute host.

## Decisions and limits retained

The recorded host order is GitHub standard CPU first, then the existing small AWS
CPU box. The first E2E host and any installation/start still need execution
authorization. Existing setup source already stages/verifies the committed model,
archive, server and extracted-file pins; it was not run here. A restricted affinity
which cannot fit the pinned host-count policy needs a declared fitting thread
configuration before launch; no allocation was guessed.

Granite receives the same exact governed exchange source/seat material on either
host. The coordinator's existing knowledge index/findings summaries are not the
full content of indexed knowledge and do not prove that every participant has the
complete synchronized market timeline. The user's shared-picture requirement
applies while keeping answer and private-reasoning boundaries: calculations may
finish out of order, but downstream consumers must use their proper original
market ordering/as-of availability. This slice preserves those source identities;
it does not invent a missing semantic consumer or backdate completed knowledge.

Requested code tests remain `requested_not_run` until the existing scientific owner
binds and executes an authorized operation. Granite coordination cannot choose new
targets, lags, formulas, scientific outcomes or survivors. Model/meeting completion
does not establish scientific resolution. Retained complete meetings still repair
publication without replay; runtime refusals remain explicit operational states.

## Verification

Applied using-agent-skills, API/module contracts and incremental source changes.
AST parsing without project imports and whitespace/source review only. The AWS
skill retrieval call stalled pending authentication and was aborted; no AWS
operation completed and it was not retried. Existing Step 6 AWS findings informed
the owner-local retained I/O approach. No tests, synthetic exercise, benchmark,
project runtime, model call, install, dispatch or AWS account action. No measured
speedup, full workflow completion or successful E2E is claimed.
