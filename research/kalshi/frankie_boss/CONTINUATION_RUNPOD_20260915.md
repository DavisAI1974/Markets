# Runpod preparation closeout — 2026-09-15

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
