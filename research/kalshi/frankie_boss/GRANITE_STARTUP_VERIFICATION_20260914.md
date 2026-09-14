# Granite verified startup route

This startup slice uses the existing selected AWS vLLM image and its documented
standard-supervisor override. No derived image, separate calculation launcher,
model-download-at-startup, or prompt/schema changes are introduced.

## Evidence for the selected image

The private ECR inventory's exact digest is also served by AWS's official public
ECR repository. The retrieved Docker manifest bytes hashed to
`sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d`.
Its config bytes hashed to
`sha256:923cc8074bcbc5a31eddf86ad2c44a97e53c022b175b83beeca22146e9835d0b`
and identify amd64 with `/usr/local/bin/sagemaker_entrypoint.sh`.
The complete 856-byte entrypoint layer and 3,461,257,375-byte dependency layer
were streamed and SHA256-verified against the image manifest before accepting
extracted sources. No archive paths were extracted directly to the filesystem.

The actual entrypoint execs `standard-supervisor python3 -m
vllm.entrypoints.openai.api_server ...`. The installed package metadata reports
model-hosting-container-standards 0.1.15. Its real environment parser and config
generator were executed locally: `SUPERVISOR_PROGRAM__APP_COMMAND` correctly
replaces the app command; autorestart=false and startretries=0 survive generation.
`granite_image_identity.json` retains source hashes and layer/config identity.
Startup checks the installed source/version against those hashes, so an uninspected
later image-layer override cannot silently pass. Real runtime execution is still
required before claiming a deployed model.

## Startup and evidence

`granite_startup.launch_environment(max_model_len=..., served_model=...)` produces
the explicit reviewed environment. The caller must derive the context size from
the admitted complete fixture and reserve output before provisioning. Tests' 4096
is synthetic and is not a chosen real runtime capacity. The environment keeps
PROCESS_AUTO_RECOVERY=true so the supervisor override is used, but explicitly
sets its app autorestart=false/startretries=0. Dependency auto-install and HF
network lookup are disabled.

Four reviewed bootstrap files are staged under their own content-addressed
`models/bootstrap/<bootstrap-manifest-digest>/` S3 prefix. A CreateModel
`AdditionalModelDataSources` channel named `bootstrap` mounts them separately at
`/opt/ml/additional-model-data-sources/bootstrap/`; the primary model prefix stays
exactly the 13 reviewed model files. The supervisor runs `python3` with the mounted
`granite_startup.py`. The bootstrap checks its own/verifier/image-manifest/model
manifest hashes and rejects additional controlled environment overrides. It
rehashes every mounted model file before runtime inspection or server startup,
checks exactly one GPU and the installed vLLM/supervisor source/version identities,
then records real Python/package/CUDA/GPU/driver facts and exact launch arguments.
It execs the existing real vLLM API server with explicit local model and tokenizer,
BF16, one tensor/pipeline/data parallel worker, max-num-seqs=1, declared runtime
context size, gpu-memory-utilization=0.9 and generation-config=vllm. The service's
request still supplies temperature=0, thinking=false and explicit max_tokens.

Before launch, `/tmp/granite-startup-receipt.json` and a CloudWatch log line
`GRANITE_STARTUP_RECEIPT <canonical JSON>` preserve schema
GRANITE_STARTUP_RUNTIME_V1 with mount bytes/hashes, runtime facts, image and code
identity, exact argv/environment and generation policy. This is an operational
receipt under the trusted runtime, not hardware attestation. DescribeModel,
EndpointConfig and Endpoint validation must match the approved plan separately.
The integrated service can use the entire canonical receipt as runtime_versions,
and mount.manifest_sha256 as base_checkpoint_sha. The tokenizer manifest must
also bind its verified files, actual implementation versions and template call.

## Validation and unresolved run work

48 focused synthetic tests pass across artifact/staging and startup, including
startup byte/identity/GPU/source mismatch rejection and bootstrap nonoverwrite,
whole-object readback and verify-existing-before-writes behavior. These tests make
no GPU, inference or endpoint-readiness claims. The separate bootstrap workflow
creates no GPU resources and validates tests before exposing scoped credentials.

The first reviewed live plan is one ml.g6e.2xlarge, deletion deadline 45 minutes
from creation intent, 20-minute startup wait, and 60-minute CI job including final
cleanup. At the freshly verified rate USD2.8026/hour, 45 minutes is USD2.10195 in
compute, plus storage/requests and possible deletion lag. This is a supervised
time budget, not a hard billing cap. Deployment must write exact resource intent
first, always/finally delete the exact endpoint, wait for absence, then delete its
configuration/model. Startup evidence and the real controller/model fixture are
required before the enabled service is admitted.

Primary references:
- https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_AdditionalModelDataSource.html
- https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ContainerDefinition.html
- https://github.com/aws/model-hosting-container-standards/blob/main/python/model_hosting_container_standards/supervisor/README.md
- https://github.com/aws/model-hosting-container-standards/blob/main/python/model_hosting_container_standards/supervisor/models.py
- https://github.com/aws/model-hosting-container-standards/blob/main/python/model_hosting_container_standards/supervisor/generator.py
