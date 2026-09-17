# Runpod preparation closeout — 2026-09-15

> **Correction (Greg, 2026-09-16): the 4,096-token Granite service context is RETIRED.** The only Granite context is
> 131,072 with output budget = remaining context and the incomplete-output alert. Every statement below that gives
> 4096 as the current or accepted service context, or a 1,200-token output ceiling tied to it, is historical. The code
> removal is recorded in `CLAUDE_RECONCILIATION_20260916.md`.

## Later host-control completion

Tested code `934ef5b7549c3e98c5eef7ae3e733054333d055f` adds a frozen-request tokenizer
admission helper and a durable one-attempt host probe. **43 focused integrated
tests passed in 5.71s**, separate from the earlier 640-test baseline below.
Independent review approved both helpers and the standalone import regression.

The actual saved tokenizer files and pinned versions measured 19 input tokens plus
16 output allowance: 35 total within context 4096. The receipt SHA256 is
`3af163e3732cc0fc586164a4f5981870dfdbadb0616393d64506fe5557b5ef7c`. No download or
model inference occurred. A real-admission/fake-HTTP composition checked independent
SQLite readback before POST and refusal of a second attempt without further I/O.
This closes local tokenizer admission, not hosted-runtime equivalence or inference.

The probe uses only an approved Pod's HTTPS proxy, bounds requests/responses, and
commits a unique per-Pod attempt before inference. It preserves ambiguous outcomes
and exposes no reset API. The operator must preserve the same journal and enforce
actual resource identity. DNS/filesystem calls are not a hard process-return bound.

Cleanup discovery: [Runpod PR 330](https://github.com/runpod/runpodctl/pull/330)
removed stop-after/terminate-after because accepted deadlines were not enforced.
The restoration PR 331 remained draft on inspection. The public REST v2 schema
supports explicit termination, but no future scheduling field. An independent
authorized watchdog and separate volume disposition remain required. No timer
flag or application lifetime is a verified provider billing cutoff.

After the user toggled the Runpod connection, a fresh runtime again loaded its
list-Pods tool but failed with the same required-approval/policy-never error. The
desktop still lacked the tool surface. Full desktop restart is the next activation
step; resolving task approvals remains separate. No configuration policy changed,
resource was created or hosted request was sent. Sunday remains held.

The Pod bootstrap package below is unchanged. Host-control evidence is in the
current task's outputs/runpod-granite-host-controls-20260915 directory.

## Earlier Pod software preparation

The existing SageMaker bootstrap now has a separately reviewed Runpod wrapper and
authenticated allowlist proxy. The wrapper retains the pinned public image, model
revision and file hashes, bounds staging and preparation in child processes, and
stops its process groups on deadline, signal or child failure. The proxy exposes
only authenticated health and bounded text-only chat routes to a fixed loopback
backend. The package helper verifies committed LF bootstrap bytes before import.

Tested code: `06446a50d522057df3f359d6eafafd298bc744e1`.
All `test_granite*.py` under this directory's tests: **640 passed in 87.36s**.
Independent source review covered both runtime and proxy changes. Local tests
include pre-import tamper refusal, process cleanup and real local HTTP deadlines.
They do not establish Linux/GPU runtime or hosted inference acceptance.

The review-only delivery was exported from that exact commit. Its bundle SHA256
is `32312f5334efa8f002df30482fd1823d9b2b49ae0484f9ccf2798de37378b24c`;
ZIP SHA256 is `8fa7ee109f89ab0b341f95c82cd52ad658a88636046999d098f45c62b5a8ce7f`.
It contains no credentials or weights. The draft selects one L40S, a 4096-token
context and one non-market request; unresolved operational fields prevent launch.

## Readiness

- Runpod plugin 1.2.0 is installed and enabled, and OAuth completed. A fresh
  runtime's read-only list-Pods call was blocked because tool approval is required
  while client approval policy is never. No approval policy was changed.
- Launch remains blocked pending approved control-plane access, concrete resource
  and volume binding, verified remote staging, private secret binding, measured
  disk sufficiency, host token admission/one-probe control, provider termination
  and cleanup, and numerical duration/spend authorization.
- Process lifetime is not a provider billing cutoff. Single proxy concurrency is
  not a one-use request restriction. The host must enforce both external controls.
- Full Runpod transport for the existing Granite controller is not implemented.
  One OpenAI-compatible smoke response cannot substitute for that acceptance.
- Genuine Frankie paper trading remains unready: fitted artifacts and D0–D5
  acceptance, authentic source/session metadata, hosted model qualification and
  explicit paper-only routing remain open. A paper policy label alone does not
  integrate the legacy simulator with the newer BOSS controller/ledger.
- Sunday remains held. C3/C4/O7/O9 remain deferred. No new hosted run, training,
  market-data acquisition, venue request or paper session occurred in this setup.

The final audit and delivery live under the current task's outputs directory:
`FRANKIE_PRE_RUN_AUDIT_20260915.md` and `runpod-granite-setup-20260915/`.
The prior round-two execution evidence remains 401 passing tests; this change
does not alter execution files, receiver history or hosted workflow triggers.
