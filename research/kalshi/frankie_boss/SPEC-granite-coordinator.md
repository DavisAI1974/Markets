# Hosted Granite coordinator

`granite_coordinator.py` joins the existing pinned staging, tokenizer admission,
resource lifecycle and real SageMaker controller. It runs from the committed Linux
checkout: the same bytes generate bootstrap staging and source/runtime expectations.
No protected prompt changes, fitting, order submission or Frankie calculation
launcher are introduced. The small retained synthetic connectivity fixture is not
Frankie's production context and does not establish forecast/calibration acceptance.

The coordinator rehashes all staged model objects, verifies/stages the four exact
bootstrap objects, downloads the eight exact tokenizer files, measures the complete
chat input with the image's tokenizer versions and retains token IDs. It checks
fresh endpoint inventory, quota, price and registry manifest before creating the
one planned ml.g6e.2xlarge endpoint. Plan and mutation intents are saved first.

Before inference it validates the complete startup receipt: mounted roster/bytes,
manifest/verifier/bootstrap hashes, image, exact argv/environment/generation policy,
all package/source identities, one L40S GPU, GPU memory, CUDA and Python versions.
Driver version is measured and retained, not guessed. Actual resource descriptors
must match the plan. It then invokes the existing controller/service exactly once
and verifies actual input-token usage and trusted retry behavior. Incomplete output
is retained and reported as failure, never repaired or relabeled as acceptance.

Cleanup runs in Python finally and an independent CI always step. Endpoint absence
precedes configuration/model removal; failures remain recorded. The 45-minute
deletion and 60-minute cleanup deadlines are unchanged. The CI run step has a
40-minute limit; independent cleanup has 20 minutes. Credentials are exposed only
to the operational run and cleanup steps; private artifacts remain outside Git.

The workflow runs only when its own file is pushed to the integration branch, so
routine source commits do not automatically launch additional endpoints. A new
actual attempt requires a deliberate reviewed workflow edit. Concurrency is one
hosted job with cancellation disabled. No silent automatic retry or budget extension.

Official interfaces: [SageMaker CreateModel](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateModel.html),
[InvokeEndpoint](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html),
[GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).

Operational exposure for the eventual actual Frankie run is **attributed_input**,
explicitly selected by the user on September 14. Authentic source mapping remains
separate from this connectivity test. Preserve that attribution in the actual
emitted prompt and evidence receipts.

Verification before the first hosted attempt: 106 combined coordinator/live-helper/lifecycle/startup/artifact checks passed locally. Independent reviewer reran all 28 coordinator checks and approved the bounded workflow. These are software checks; actual hosted acceptance is recorded separately.

Run 34905678210 verified all staged model bytes and bootstrap, then failed before
resource creation: Transformers 5.8.0 returns BatchEncoding by default. Admission
now explicitly requests a flat token-ID list, no padding or truncation, and records
those invocation settings. Local verification with all eight hash-verified real
tokenizer files and the retained Linux prompt reproduced the default return and
confirmed the explicit list contains the identical 2,284 IDs. The 106 regression
checks pass. This is tokenizer verification, not hosted model acceptance.
The independent cleanup step now records no_creation_intent even when admission
fails before a deployment ledger exists. A deliberate workflow change schedules
the corrected bounded attempt; the first attempt created no GPU resources.

Corrected run 34906771361 (frozen source 3e0a01ed) passed the real Linux tokenizer
admission, then timed out waiting for endpoint startup after 20 minutes. No startup
receipt, provider response or controller inference was obtained. Container log
collection reported ResourceNotFoundException for the log group; this does not
establish the underlying provisioning cause. Both Python finally and independent
CI cleanup confirmed endpoint/configuration/model absence with status deleted.
The ledger retains 119 transient DeleteEndpoint ValidationExceptions before
confirmed removal. This is a failed hosted attempt with successful cleanup, not
model acceptance. Retain/read better provisioning diagnostics before another run.

## Startup diagnostics continuation

Every startup poll now retains a numbered, timestamped endpoint descriptor before
status/configuration validation, including Creating and Failed states and the
service FailureReason. Polling errors retain SDK Error and ResponseMetadata.
Cleanup deletion errors retain full sanitized service messages/request IDs in the
ledger. CloudWatch page errors are retained individually, including a missing log
group; successful pages are sanitized copies and runtime admission still consumes
the original response. Coordinator exception files include sanitized tracebacks.
Diagnostic redaction covers credential field names, bearer tokens, private keys,
AWS access-key IDs and common credential assignments. These private diagnostic
artifacts are not a blanket guarantee that arbitrary provider prose has no private
data, and should remain in the existing private artifact channel.

No polling interval, startup deadline, budget, creation policy or inference gate
changes. No new hosted attempt is authorized by this diagnostics change. Existing
34906771361 artifacts cannot reconstruct discarded periodic descriptors or full
transient deletion messages; provisioning cause remains unknown.
