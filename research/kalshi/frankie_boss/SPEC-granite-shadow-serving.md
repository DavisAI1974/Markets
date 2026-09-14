# Frozen Granite shadow boundary

Software-only, additive opt-in call; no model download, inference connector,
training, decision fusion, forecast publication or empirical promotion.

Caller supplies an immutable identity containing base checkpoint, adapter or
merged weights (nullable for base), tokenizer, quantization, runtime versions,
thinking mode, deterministic inference temperature zero and token budget,
system prompt/schema/parser hashes and optional tune receipt. Tuned identities
require a tune receipt. These are caller assertions, not weight attestations.
Local prompt, schema and parser pins are checked before transport invocation.

Each request binds caller request id, identity, exact canonical state bytes,
full prompt bytes and explicit positive timeout. Response echoes request hash
and identity hash. Raw final text is retained; existing runtime_score alone
decides L4 acceptance after echoes match. Thinking extraction belongs to the
pinned transport; this layer never repairs, strips or rewrites output.

Timeout, transport exception, malformed response and identity/state mismatch
produce isolated shadow receipts. Evidence disagreement remains diagnostic;
no native forecast, Frankie decision, B0/B1, replay or Memory A is an argument
or mutation target. Receipts are immutable in-memory values, not durable logs.

Transport must be trusted cooperative async I/O. The boundary limits caller
waiting, requests cancellation and discards late output without waiting for
cancellation acknowledgement. It cannot stop remote work or event-loop-blocking
transport code. Caller cancellation propagates and requests transport cleanup.

Acceptance: synthetic fake transports prove pin checks before side effects,
exact request identity, successful and rejected parser receipts, failures,
bounded timeout including cancellation-resistant transport, and unchanged
snapshot. Existing parser/prompt tests remain passing. Production runtime pins,
timeout choice, transport, cancellation and throughput acceptance stay open.
