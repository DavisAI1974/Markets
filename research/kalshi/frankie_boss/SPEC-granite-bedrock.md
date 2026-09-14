# Bedrock Granite critic service

Add an opt-in service factory with a real lazy boto3 `bedrock-runtime.converse`
execution path. Disabled service returns without credential discovery/client
construction. No deployment or real inference is performed by software tests.

Explicit configuration requires region, deployed model ID/ARN, caller-confirmed
Converse text/system support, connect/read/caller timeouts and frozen Granite
identity. This adapter supports non-thinking text output only; it does not guess
Granite-specific InvokeModel payloads or claim Granite 4.2 availability. Prompt
management ARNs and prompt routers are unsupported because their extra prompt or
routing behavior would violate the frozen request. SDK retries are disabled.

The service preserves the exact shadow prompt as one user text block, with no
additional system or conversation content. Configuration identity hashes region,
endpoint model, transport mode/timeouts and SDK versions. A call envelope binds
that identity to shadow request hash; both are included in requestMetadata and
returned receipt. Response hashes are locally asserted routing bindings, never
provider attestations of weights. Raw provider JSON, including response metadata,
usage and stop reason, is retained for completed calls. Only a single text block
with assistant role and end_turn is accepted; truncation, tools and thinking reject.

One daemon worker per service at a time; a timeout never releases its capacity
until the underlying SDK call actually ends. Repeated calls fail busy instead of
accumulating threads. Finite socket timeouts are configured, but remote cancellation
and exact overall network duration are not claimed. Late output is discarded and
cannot affect Frankie decisions. The service exposes critique(snapshot, request_id)
for controller use; no inference call happens automatically on construction.

Offline boto3 Stubber and injected clients validate real SDK arguments, metadata,
disabled route, failure isolation, pin/config binding and timeout capacity.
Runtime model/region/credential availability and deployed model compatibility
remain production acceptance prerequisites.

## Explicit live integration harness

After obtaining the deployed model's identity and confirming compatibility,
provide a JSON object with exactly `config` (BedrockConfig fields) and `identity`
(GraniteIdentity fields), plus a canonical synthetic SerializedState JSON file.
Credentials are supplied through the normal AWS SDK chain, never the JSON file.
Run `python -m research.kalshi.frankie_boss.granite_bedrock --live --config CONFIG
--snapshot STATE --request-id ID --receipt NEW_FILE` as one command. It performs
one real configured Converse call and writes its complete diagnostic receipt to
a new file; rejected model output exits 1. Existing receipts are never overwritten.
This is explicit integration execution, not a default unit test or trading path.
The owner authorized real Bedrock integration testing later in this task; no call
can proceed until usable credentials, region, deployment and true pins exist.

Sources checked 2026-09-14:
- https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
- https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-marketplace-model-reference.html
- https://docs.aws.amazon.com/botocore/latest/reference/config.html
