# SageMaker Granite shadow transport V1

Opt-in real boto3 sagemaker-runtime InvokeEndpoint transport for a deployed vLLM
chat-compatible endpoint. No deployment, credential discovery or inference occurs
at construction; disabled calls return None. Read-only enabled/identity/config_hash
properties support independent controller pin checks. SDK/config drift rejects.

Both critique(SerializedState) and critique_native(NativeContext) delegate to the
shared shadow boundaries and their distinct prompt/parser pins. Send exactly one
user message containing the complete frozen prompt, with explicit served model,
temperature=0, max_tokens from GraniteIdentity, stream=false, and
chat_template_kwargs.enable_thinking=false. No truncation, response repair,
additional system instruction, session routing, tools or implicit sampling policy.
The approved zero-temperature contract is retained despite IBM's recommendation
of temperature=1/top_p=.95. Compatibility must be confirmed by deployment tests.

InvokeEndpoint CustomAttributes binds request/config hashes; InferenceId binds the
call hash. These are local routing assertions, not AWS weight attestations. Raw
response body bytes (base64) and SDK response metadata are retained in provider_json,
including malformed outputs. Response stream is always closed. Accept only one
choice with index 0, matching served-model name, assistant text, finish_reason stop,
and no nonempty reasoning/refusal/tool/function/audio/annotation output. Strict
JSON rejects duplicate keys and nonfinite constants. Shared parser alone grants L4.

Single daemon worker per service; timeout/cancellation retains capacity until the
underlying SDK call and body read finish. Later calls fail busy. No SDK retries.
Finite socket/caller deadlines bound waiting; no remote-cancellation guarantee.
No cloud mutations occur in tests. Synthetic boto3 Stubber validates actual SDK
arguments, binary-body handling, failure evidence, drift, deadlines and both seams.

## Verified exact IBM artifact metadata (2026-09-14)

Official repository: ibm-granite/granite-4.2-8b
Immutable revision: f8de16cdcdbc6c779ca517604e050d82cc119e44
Architecture GraniteForCausalLM, BF16, metadata transformers_version 4.57.1.
IBM documents vLLM >=0.20 for its optional custom thinking parser. AWS documents
vLLM 0.20.2-gpu-py312-cu130-ubuntu22.04-sagemaker; actual image digest and installed
runtime remain deployment pins, not established by this software transport.

SHA256 values below were read from the official HF revision. Small-file content
hashes were computed locally; large-shard hashes are HF LFS declarations and still
require verification after download. Four shards total 17,583,228,032 bytes.

| File | SHA256 |
| --- | --- |
| model-00001-of-00004.safetensors | baed4f3128d1f2e3792ad896ac5621124929bb4f658722f132e614108751e96c |
| model-00002-of-00004.safetensors | 69e7a59b810f4c029339b7a208b4dac0c1eee6b88a66e830e74882cbd191803c |
| model-00003-of-00004.safetensors | c2c52fd2baa6ec5003d3ac9842bfd782c0a5a80fc9a1b406a007cae6af008a89 |
| model-00004-of-00004.safetensors | 0dfcc074193c1cb81270fd6e99cace27d4b0461e8739691c2a347b657c030ffc |
| config.json | 85611f4e34633d4e148e6a5f64bc2d3a23ebbc2b014bc87fbda764eecf261cd9 |
| model.safetensors.index.json | d37ecbd9468d7925034dc40e9633509ef746f54d52ac6050e2ffc3e365e31504 |
| tokenizer.json | 883975314d58743726347caaf2c32ac89afd5ad57222cffbc4f052f2ab27b2d7 |
| tokenizer_config.json | 2007f26df166ed10a2d6fa881c1c8f3cdd151e451469f59b274897f14449835f |
| chat_template.jinja | f0ba43f79b3cabca5e5a7584c77aec92f49feae45cdf7779c87d9fc54cd90258 |
| generation_config.json | 1b9baf0a7959d31d7fb58ff6b506c27d09a73d395cadccc7e6dd1d4b7e43fd9d |
| special_tokens_map.json | e9435fefd6d838fd9fcbbc44b97a8e3ff322be7f6dfb7e4fd2468586574bb52b |
| vocab.json | a1be0c1e0a89b5bacda6af6f8b63df09668cb8d1f656229ee9123140c9507810 |
| merges.txt | b6fe424e334903f7fb84d3a106d9730455f4744b9fe3c21ee136d97a00e72502 |
| granite_thinking_parser.py | cd5eef99f559f33dc402e0475174a97dcb43724d7e810149c702e9bbc473048a |

The 40-character HF revision is not a 64-character checkpoint hash. Production
GraniteIdentity must bind complete verified weight/tokenizer manifests and actual
container/runtime identity. Endpoint availability, quota, cost and cleanup are
separate deployment prerequisites; no production acceptance is implied here.

## Primary references

- https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html
- https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints-openai-compatible.html
- https://raw.githubusercontent.com/vllm-project/vllm/v0.20.2/vllm/entrypoints/sagemaker/api_router.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.20.2/vllm/entrypoints/openai/generate/factories.py
- https://raw.githubusercontent.com/vllm-project/vllm/v0.20.2/vllm/entrypoints/openai/chat_completion/protocol.py
- https://huggingface.co/ibm-granite/granite-4.2-8b/tree/f8de16cdcdbc6c779ca517604e050d82cc119e44
- https://huggingface.co/api/models/ibm-granite/granite-4.2-8b?blobs=true
