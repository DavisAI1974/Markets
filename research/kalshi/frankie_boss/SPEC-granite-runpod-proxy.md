# Granite Runpod access proxy

## Boundary and acceptance

Standalone `python3 granite_runpod_proxy.py` requires `RUNPOD_GRANITE_API_KEY`
(32–256 URL-safe ASCII characters) before listening on 0.0.0.0:8081. Only this
port may be published through Runpod HTTPS; port8080 must remain unpublished.
`GRANITE_SERVED_MODEL` is also required before binding and must match the backend.
The fixed backend is127.0.0.1:8080. No CLI upstream override, dependencies,
credentials files, model operations or provisioning are included.

Exact authenticated GET `/health` returns only backend liveness, and exact POST
`/v1/chat/completions` accepts nonstreaming text-only JSON. Authentication uses
constant-time comparison. No caller headers are forwarded, including auth and
Forwarded/X-Forwarded-* (Runpod itself may supply those headers). Requests with
ambiguous framing, encoding, duplicate JSON keys, streaming, media content,
unknown routes or oversized bodies fail closed before backend I/O.

The chat object permits only model, messages, max_tokens, temperature, top_p,
seed, stream and chat_template_kwargs. Require matching model, 1–1200 integer
max_tokens, temperature0, exact `chat_template_kwargs={"enable_thinking":false}`;
stream is absent or false. Optional seed is an integer in [0,2^63), top_p finite
in (0,1]. Messages are 1–256 objects containing only role(system/user/assistant)
and string content. These match the current deterministic smoke contract, not
the complete OpenAI API. No media URLs or tools can trigger secondary fetching.

The single-request HTTP server bounds concurrency to one. Client idle timeout5s
and whole connection deadline90s; backend idle/whole deadline80s, clamped to the
remaining client deadline before connect and transmit. Request limit
1MiB, response limit4MiB. Require exact Content-Length, no transfer encoding;
close each connection. Header size is capped16KiB after the standard library's
bounded HTTP parser (at most100 header lines, each at most64KiB); the bounded
accept backlog is5 and there are no worker threads or unbounded request queues.
Backend redirects/errors/malformed or short bodies become
generic502, with no upstream headers or error bytes disclosed. Health failure503.
No request, credential, prompt, backend error or access logs. This bounds memory
and duration, not volumetric denial of service; network-level rate limiting and
independent Pod teardown remain deployment prerequisites. TLS terminates at Runpod.
Closing the upstream socket is not proof the model engine canceled generation.
This proxy does not prevent authenticated replay: a single smoke request and
independent duration/billing teardown must be enforced by the host orchestrator.
Literal known-secret response echoes are suppressed as defense in depth; this
is not universal semantic redaction. The request credential never reaches vLLM.

Acceptance tests run real local HTTP with a fake backend: auth/route/framing/body
refusals cause zero backend calls; valid chat bytes survive without forwarded
credentials; health is minimal; backend errors, redirects, oversize, malformed or
short output are sanitized; timeouts close slow peers. No model is loaded.

The pinned [vLLM0.20.2 security documentation](https://docs.vllm.ai/en/v0.20.2/usage/security/)
states API-key coverage excludes non-v1 endpoints and recommends restricted proxy
exposure. This proxy's health response is liveness only, not startup identity or
model acceptance. Sunday remains held.
Actual pinned-vLLM Content-Length/nonstream response compatibility remains a
bounded runtime acceptance check; local fake-backend tests do not establish it.
