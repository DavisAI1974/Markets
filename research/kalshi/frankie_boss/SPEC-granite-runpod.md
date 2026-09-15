# Bounded Runpod Granite smoke boot

## Scope and status

Local implementation only; no Pod launch, model download, image layer download,
secret access or inference occurred. `granite_runpod.py` is a future Pod bootstrap,
not a control-plane client. Existing AWS workflow, startup verifier, prompts and
controller are unchanged. This smoke configuration is 4096 context tokens for the
previously measured 3484-token synthetic fixture; it proves no 128k capacity,
teacher acceptance or actual Frankie operation. Sunday remains held.

## Exact image and source reuse

Use `public.ecr.aws/deep-learning-containers/vllm@sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d`.
Anonymous registry metadata returned this exact existing manifest (7868 bytes) and
configuration digest `sha256:923cc8074bcbc5a31eddf86ad2c44a97e53c022b175b83beeca22146e9835d0b`
(41141 bytes), amd64, entrypoint `/usr/local/bin/sagemaker_entrypoint.sh`, no Cmd.
Its compressed layers total 8,370,421,495 bytes; expanded size remains unverified.
Only metadata was fetched. [AWS public vLLM images](https://aws.github.io/deep-learning-containers/vllm/).

Export committed LF source before packaging: four original bootstrap files
(`granite_startup.py`, `granite_run_artifacts.py`, `granite_artifacts_manifest.json`,
`granite_image_identity.json`) plus `granite_runpod.py` and
`granite_runpod_proxy.py`. Use `granite_runpod_package.package(exported_source, empty_output)` to create
`runpod_bundle.json` with schema
`GRANITE_RUNPOD_BUNDLE_V1` and each file's path, size and SHA256. Pin the exact
manifest bytes in `RUNPOD_BUNDLE_SHA256`. The helper also produces a trusted
`python3 -c` supervisor command embedding all six size/hash pins. This outer
standard-library verifier checks every bundle file before executing/importing
any bundle module; the in-module check alone would be too late. It uses explicit
conditions, not optimization-sensitive Python assertions. Never hash a Windows checkout and assume
a Linux checkout has identical bytes. Bootstrap files must be staged and read
back on the selected volume; unlike the small bundle, model files need not be
pre-staged. That external file-transfer operation is not implemented here.

## Concrete configuration

Proposed console settings: one on-demand NVIDIA L40S (48 GB VRAM), 30 GB container
disk and 50 GB network volume mounted at `/opt/ml`. Location, volume identity and
storage sufficiency must be verified before launch. Stage the seven small bundle
files at `/opt/ml/additional-model-data-sources/bootstrap/`; model files go in
`/opt/ml/model`. [Runpod storage](https://docs.runpod.io/pods/storage/types).

Keep the original image entrypoint and no Docker command override. Generate the
original environment with `granite_startup.launch_environment(max_model_len=4096,
served_model='granite42-smoke')` from the exported bundle. Set its
`SUPERVISOR_PROGRAM__APP_COMMAND` to the package helper's exact
`supervisor_command`, and `RUNPOD_SUPERVISOR_COMMAND_SHA256` to the returned hash.
The generated command verifies files then executes `granite_runpod.py`.
Keep supervisor autorestart false/startretries zero and all existing offline flags.
Set `RUNPOD_GRANITE_LIFETIME_SECONDS` only to the explicitly approved positive
process duration, `RUNPOD_BUNDLE_SHA256` to the exported manifest hash, and
`RUNPOD_GRANITE_API_KEY` through a Runpod secret reference. The key must be resolved,
32–256 URL-safe characters (`A-Z`, `a-z`, `0-9`, underscore or hyphen),
matching the proxy contract. No secret value goes in artifacts.
[Runpod startup](https://docs.runpod.io/pods/templates/create-custom-template),
[secret references](https://docs.runpod.io/pods/templates/secrets).

Expose only `8081/http` through Runpod HTTPS; do not publish 8080, SSH, Jupyter or
internal distributed ports. The separately reviewed proxy authenticates exact
`POST /v1/chat/completions` and minimal `GET /health`, forwarding only to
127.0.0.1:8080. vLLM's own API key does not protect all its routes, so it is not a
substitute for the allowlist proxy. [vLLM security](https://docs.vllm.ai/en/v0.20.2/usage/security/),
[Runpod HTTPS proxy](https://docs.runpod.io/pods/configuration/expose-ports).

## Startup, stop and evidence

Boot refuses missing lifetime/secret, wrong bundle bytes or altered startup
configuration before staging. It invokes the existing immutable public Hugging
Face URL/downloader in a separate process. The whole stage has a parent timeout,
covering stalled DNS/reads/hashing; each file gets one attempt, retaining the
existing strong-ETag partial-resume behavior and exact roster/hash checks. No
whole deployment retry occurs. The original verifier then checks every model
file, runtime version/source and single GPU in another bounded subprocess before
vLLM starts. The parent checks the small returned receipt and exact launch argv.
Thus the repeated full model hash and GPU/runtime imports cannot bypass the
parent deadline.

The original startup receipt is preserved; a separate explicit backend argv
changes only the bind address to127.0.0.1. The proxy runs on8081. Backend does not
receive the proxy secret. Both are new process groups; any child exit, exception,
interruption or lifetime expiry stops both groups, including remaining descendants.
Receipts omit the key; boot failure prints only exception class, not backend text.
SIGTERM enters the same cleanup path. No proxy restart or backend auto-recovery
is introduced. All injected environment is operator-reviewed; source consistency
does not defend against a hostile host or unapproved PYTHONPATH/LD_PRELOAD settings.

Process duration begins at bootstrap entry; paid Pod provisioning/image pull can
precede it. **Stopping these processes does not terminate the billable Pod.**
A separately reviewed external teardown/watchdog, full wall-clock duration and
total cost cap (including storage and startup) must be in the final authorization.
The funded $30 balance is not an approved cap. The supervisor must remain configured
not to restart the failed boot. Runtime source checks are consistency evidence,
not host attestation.

## Remaining work before any run

Finish/export the reviewed proxy, stage/read-back the small bundle, select/verify
volume and location, validate driver and disk capacity, provision secret reference,
and audit the effective full configuration plus independent external cleanup and
explicit budget. No Runpod controller transport exists yet: the current live
controller invokes SageMaker's protocol. A successful smoke response cannot claim
that controller integration, native context capacity, repeatability or latency.
The user requested one final audit before any run; that audit is still required.
