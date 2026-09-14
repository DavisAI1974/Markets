# Pinned Granite AWS integration run

Status: proposed for root review; specification only. No resource creation,
permission changes, downloads of weights, or model inference have been performed
by this task. Governing record is commit
`9006b633829cc2d7d34df269d6645d1ec4ddee54`,
`frankie_boss_live_stack/05_PERSONAL_AUTOMATED_EXECUTION_AND_LICENSING.md`:
self-hosted AWS Granite with a bounded initial GPU run. This run uses synthetic
market evidence and actual Granite weights. It establishes operational wiring,
not forecast quality, production capacity, execution authorization, or training.

## Reuse and smallest harness

Use the existing `SageMakerShadowService` with its real boto3 client, existing
`FrankieForecastController`, `NativeForecastRefresh`, `ContextSessionRunner`,
native mapper, parser, forecast book and controller journal. Preserve their
authority and bytes. An additive operator harness orchestrates these components;
it must not imitate their forecasts, invent a successful critic response, or
replace production classes with test doubles.

Proposed additive pieces after review:

- `granite_run_artifacts.py`: exact manifest verification, resumable shard staging,
  tokenizer capacity receipt, and private deployment plan generation. No inference.
- `granite_live_run.py`: explicit deploy/run/inspect/cleanup commands with a durable
  run ledger and injected AWS clients for synthetic lifecycle tests. Real mode uses
  real SDK clients and the configured service. CLI import/default mode is inert.
- A small pinned startup verifier/entrypoint, only if the selected official image
  cannot verify mounted artifacts and report runtime identity before readiness.
  Any derived image needs its own reviewed source and immutable ECR digest.

Keep one explicit private run configuration outside Git: account, region,
execution role, bucket/prefix, resource names, instance type, GPU count, quota and
rate evidence, maximum spend, absolute deadline, startup/request limits, supervising operator, CI cleanup job, and retention policy. Do not print credentials or copy account IDs/ARNs
into the repository. Public manifests can refer to private configuration hashes.

## Artifact verification and staging

The only initial model is `ibm-granite/granite-4.2-8b`, revision
`f8de16cdcdbc6c779ca517604e050d82cc119e44`. Copy the exact filename/hash table from
`SPEC-granite-sagemaker.md` into a machine-readable reviewed manifest. Its four
BF16 shards total 17,583,228,032 bytes. HF LFS hashes are expected values, not proof
that the local or deployed bytes match.

Download only immutable revision URLs, with bounded streaming into a task-owned
partial file. Verify each final file's byte length and SHA256 before accepting it.
Resumes must establish unchanged remote identity and rehash the complete result;
an interrupted file never becomes a verified artifact. Reject unexpected files,
symlinks, path traversal, duplicate paths and safetensors index references outside
the exact shard set. Verify the index, configuration, tokenizer files, chat
template and generation configuration as well as weights. Keep original bytes.
Do not execute the optional thinking parser: this run disables thinking and
does not require remote model code. Record explicitly whether unused repository
files are retained or excluded from the runtime file set.

Upload verified files individually under a fresh manifest-addressed S3 prefix.
Use SageMaker `ModelDataSource.S3DataSource` with `S3DataType=S3Prefix` and
`CompressionType=None`; this avoids a second 17.6 GB tarball. Process one shard
at a time when local space is limited. Retain it until its uploaded object has
been read back and streaming-hashed, then release only that task-owned file.
S3 ETags and multipart composite checksums are not substitutes for the expected
whole-file SHA256. Record exact object size/version and verified digest; list
the prefix and reject missing or extra keys before model creation. Place receipts
outside the model prefix. SageMaker downloads current prefix objects, so S3
version IDs alone do not bind the mounted files: require startup verification
against the same manifest and prohibit writes during deployment/inference.

The startup verifier rehashes all mounted files before model loading/readiness,
rejects missing/extra artifacts, and emits the verified manifest digest. This
provides a retained operational check under the trusted runtime; it is not remote
hardware attestation. Do not claim immutable S3 storage unless policy actually
enforces it. Uncompressed deployment is an AWS-supported model-data route.
[AWS uncompressed model deployment](https://docs.aws.amazon.com/sagemaker/latest/dg/large-model-inference-uncompressed.html),
[S3ModelDataSource](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_S3ModelDataSource.html).

## Runtime and identity

Resolve the documented candidate vLLM image tag
`0.20.2-gpu-py312-cu130-ubuntu22.04-sagemaker` in the approved region. Retain its
registry response, manifest and resolved platform digest, then deploy by digest.
A tag string is not a runtime pin. Inspect the selected image's actual entrypoint
and supported environment variables before generating its complete launch plan.
Set local model/tokenizer paths to verified `/opt/ml/model` data; no floating HF
download is allowed at startup. Disable remote code, quantization, adapters,
speculative decoding, tools and thinking. Set tensor parallelism and concurrent
sequences to one, with one endpoint instance containing exactly one GPU.
Use the existing exact chat request contract, including served model name,
temperature zero and explicit maximum output tokens. Record defaults affecting
generation instead of assuming them from another image's documentation.
[AWS vLLM endpoint example](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints-openai-compatible.html).

Canonical JSON manifests use UTF-8, sorted keys, compact separators and finite
values, with an explicit schema and SHA256 of those exact bytes. Define:

- Base manifest: repository/revision, complete runtime weight/config file set,
  filenames, verified sizes/hashes, and index relationship. Its digest becomes
  `GraniteIdentity.base_checkpoint_sha`; the 40-character HF revision does not.
- Tokenizer manifest: verified tokenizer/config/template/supporting vocabulary
  hashes, tokenizer implementation/version, and exact chat-template invocation.
  Its digest becomes `tokenizer_sha`.
- Runtime manifest: actual deployed image/platform digest, startup-verifier hash,
  Python/PyTorch/Transformers/tokenizers/vLLM/CUDA versions, GPU/driver, complete
  effective launch arguments and generation settings, model/tokenizer manifest
  digests, and startup verification receipt. Canonical JSON is the explicit
  `runtime_versions` value (including the runtime manifest schema).

For this unmodified base-model run set `weights_sha=None` and
`tune_receipt_hash=None`: those paired fields denote tuned weights in the existing
contract. Use `quantization='none'`. Derive the real prompt/parser/schema pins
from the selected approved context route. Never reuse the dummy repeated hashes
or synthetic runtime labels in tests. Verify DescribeModel/EndpointConfig/Endpoint
and retained startup evidence before constructing the enabled service.

## Exact context admission

Freeze and hash a purpose-built synthetic fixture before provisioning, constructed
with real native classes and deterministic saved model/head state. Derive source,
session, configuration and artifact hashes from their actual bytes; do not copy
the test fixture's placeholder H values into runtime identity claims. Start with
one full evidence row and three native horizons: this is a complete small source
fixture, not a truncated larger window. Save fixture code/state/manifests and all
exact input, packet, snapshot and prompt hashes.

Apply the pinned tokenizer's actual chat template to exactly the service's single
user message with thinking disabled and the proper generation suffix. Count the
complete rendered input and reserve the declared output token budget. Record the
token IDs or their digest and implementation versions. Confirm against actual
server tokenizer behavior. Admit only when input plus output fits the model's
verified positional limit and the explicitly measured/configured runtime limit.
Choose runtime context length from this measured fixture requirement and hardware
capacity; do not silently select a small arbitrary limit, truncate, summarize,
discard masked values, or claim the model's nominal limit is a GPU capacity test.

Native V1's existing measurements show the need for admission checks: the 32-row
QSV fixture used 122,335 chat tokens, and the 128-row version used 483,555. These
are local synthetic measurements, not tested endpoint capacities. The exact compact
codec is separately specified in `SPEC-granite-context-compact.md`; use it only
after explicit mapper/service/controller routing approval and exact inverse tests.
It is not a hidden V1 substitution. Neither a one-row success nor repeated-vector
compression proves full-window production feasibility. Oversized fixtures stop
before endpoint creation or inference.

## Bounded deployment and failure recovery

Resolve quota, available one-GPU instance, current hourly rate and storage costs
before deployment. BF16 shard size alone does not establish GPU fit: account for
runtime workspace and KV cache. Do not automatically enlarge instance count,
change precision, lower context, switch model or extend time after failure.
The private reviewed plan must contain numerical startup timeout, request timeout,
absolute deletion deadline and maximum spend. No unspecified defaults authorize
a chargeable operation. Persist exact resource names and creation intent before
each AWS mutation; describe/reconcile uncertain creates, never mint replacement
names on restart. Reject names/configurations belonging to another run.

Use one instance, one variant and no autoscaling. The first test is supervised:
run it in an explicitly bounded CI job with an always/finally cleanup step, a
named operator watching its absolute deadline, and retained resource names and
cleanup commands accessible independently of the runner. Verify deletion and
report cleanup failure immediately. The operator takes over cleanup if CI stops,
loses credentials or cannot confirm endpoint absence. Before starting, confirm
that this supervision and the scoped deletion access are available.

This arrangement is a supervised time budget, not an absolute billing cap or a
guarantee of cleanup after simultaneous runner/operator failure. Endpoint charges
can continue past the deadline until deletion completes. A GPU process exit,
request timeout or local alarm does not terminate SageMaker billing. Independent
cloud scheduling can strengthen later unattended operation but is not a resource
or IAM prerequisite for this first supervised test.

CI and the operator invoke cleanup on success, exception, timeout and cancellation.
On restart inspect the durable ledger and AWS state before any new work. An expired
or uncertain run enters cleanup-only mode. Delete the exact owned endpoint, poll
until absence, then delete its owned endpoint configuration/model. Preserve roles
until AWS cleanup completes. Retain deletion request IDs, descriptions and final
absence receipts. S3 versions/logs are separate retention costs and need explicit
retention/cleanup policy; do not erase verification or provider evidence. A missed
deadline is an operational failure and alert, never a successful bounded run.
[AWS endpoint deletion](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DeleteEndpoint.html).

## Real-model integration acceptance

After deployment verification, run one frozen fixture through the actual
controller with the configured `build_sagemaker_service` and default real client.
This single call tests native publication, real Granite invocation and the combined
receipt together; a second standalone model call is unnecessary. Count native
forwards and provider calls: three native horizons share one critic request when
their validated context is identical. Do not perform an extra native forward to
prepare Granite input. Granite never changes the native forecast record.

Retain source journal/count/head, native state/decoder artifacts, native publication
ledger and checkpoints, exact source/input/packet/context/prompt/tokenization
receipts, manifests, SDK versions, endpoint descriptors, provider request/body
hashes, complete raw response bytes and SDK metadata through `provider_json`,
parser outcome, controller result and cleanup evidence. Keep private identifiers
in access-controlled run artifacts; publish only a redacted summary in Git.

Require the real response to satisfy the existing strict schema/parser and
identity/snapshot bindings; no response repair, forced success, prose stripping or
invented evidence references. If the actual model emits malformed JSON or reaches
its output limit, retain that failure and mark integration incomplete. Tuning a
prompt or increasing an approved budget is a separate receipted attempt, not a
silent retry. Timeout leaves an uncertain attempt under existing controller rules.
On a successful attempt, reopen with trusted checkpoints and repeat the same
request: require identical recorded output with zero additional forward/provider
calls. Verify category-free consumer outputs and unchanged native artifact hashes.

## Tests and current blockers

Before live mode, synthetic tests must cover shard corruption/resume, incomplete
uploads, extra S3 keys, startup manifest mismatch, image/config drift, exact
token admission, absent limits, one-GPU enforcement, failed/uncertain create,
restart recovery, expired-run cleanup, deletion acknowledgement loss, cleanup
failure reporting and complete evidence retention. These tests establish harness
behavior only; existing transport/controller tests already cover their semantics.

Current blockers: SageMaker/quota/pricing/ECR access is denied under the last
inventory; execution role and storage access are proposed rather than validated;
weights have not been downloaded and verified; actual image digest and startup
verification path are unbound; GPU fit/rate/quota, numeric run budget/deadline and
verified CI cleanup and operator supervision remain unresolved. Compact context routing and
production-sized context capacity remain separate unfinished work. Resolve these
through the owner/root-reviewed setup, then execute the smallest admitted real
fixture. This specification creates no cloud resources or additional authority.
