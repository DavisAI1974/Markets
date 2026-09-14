# Frankie native forecast and required Granite controller

Status: implemented additive software wiring with synthetic integration checks.
This connects the implemented authoritative native forecast, exact native-context
Granite critic and approved category-free consumer. It does not submit orders,
send messages, fit models, alter original Frankie/S121, or write Memory A.

## Existing authority and APIs

- `ForecastSession` in `forecast_session.py` is the explicit session/unit/causal
  observation manifest, not a running service. `validate_for_publication()` already
  enforces prior-close certification and the declared tick grid. Do not duplicate it.
- `NativeForecastRefresh(context, decoder, book, targets, policy).update(sessions=,
  expected_sessions_hash=, arm_hash=, as_of=, source_as_of=, source_hash=,
  material=False, through_cursor=None)` validates the complete active target list,
  prepares exact native tensors, performs same-forward B1 production per due target,
  and writes through `ForecastRefreshLoop`. Reuse this complete implementation.
- `ForecastRefreshLoop` already records whole-refresh intent before production and
  preserves per-target commits across partial failure. A retry does not regenerate
  committed revisions. An empty return means no due/new completed targets; do not
  relabel an earlier `book.latest()` publication as refreshed at the current cutoff.
- `RollingForecastBook.publication(hash)` verifies a specific retained publication;
  `.checkpoint()` exposes trusted count/head state for reopen. Selection already
  publishes the sole valid candidate or highest-ranked comparable candidate without
  a minimum score cutoff. The controller must not add another selector.
- `consume_forecast(legacy=, enabled=True, book=, publication_hash=, metadata=)`
  verifies native artifact/computation bindings and yields `CategoryFreeRecord`.
  Its twelve fields, null confidence, fatal-only defects and reproduction status
  are authoritative. `to_json()` retains caller-metadata provenance explicitly.
- `ContextSessionRunner._prepare(as_of, cursor)` returns `(tokens, info, input_hash,
  teacher, context)` without running the model. This existing private seam is the
  minimum additive way to reconstruct exact published input; isolate its use in
  one controller helper and bind its code hash. Do not call `.run()` for the critic:
  that would perform an unnecessary second model forward.
- `granite_shadow.serve_native_shadow()` uses the exact new mapper/prompt/parser
  contract; the older `serve_shadow()` remains a separate control.
  `map_native_context`, `build_native_prompt` and `score_native` implement the
  additive native schema and named-field L0-L4 validation.
- `build_bedrock_service(enabled=True, config=BedrockConfig(...),
  identity=GraniteIdentity(...))` already supplies real, lazy Bedrock Converse I/O,
  pinned SDK/config identity, one in-flight underlying call, explicit timeouts,
  provider response evidence, and no implicit retries. `build_sagemaker_service`
  provides the explicit self-hosted AWS endpoint route for exact Granite 4.2.
  The controller uses their shared configured native-context service protocol.

## Required behavior and boundaries

The enabled operational controller requires both a configured native B1/decoder
and a configured native-context Granite service. Missing or disabled critic
configuration rejects before native generation or AWS credential discovery.
The top-level disabled path calls the supplied legacy callable directly, before
reading journals or validating enabled-only configuration; preserve disabled
identity behavior. A CLI live run is explicit and separate from synthetic tests.

B1 retains forecast authority. Granite receives the exact causally available
native input with named graph/QSV/raw evidence, never teacher targets, forecasts,
future outcomes or decoder output. A valid Granite disagreement is durable critic
evidence; it never edits the selected native artifact, price path, selection,
publication revision or category-free metadata. No low/medium/high categories or
confidence cutoff are introduced. The critic assesses input evidence; one accepted
critic response may be linked to multiple horizons sharing the identical context,
packet, mapper, prompt, parser and frozen service identities. It is not described
as a separate forecast-specific critique of each horizon's price path.

Every enabled due refresh must reach a durable critic result before an integrated
success is returned. A timeout, rejected/malformed response, binding mismatch or
transport failure yields an explicit incomplete controller result, preserving the
native publication and unmodified Frankie record for inspection. It must never be
reported as successful operational B2_GATED completion. This is operational status,
not a new gate that changes B1 publication authority. A valid L4 disagreement is a
successful critic execution, not an infrastructure failure or a forecast veto.
No-refresh-due is a durable idle result and does not require a redundant critic call.

## Smallest controller contract

Add `FrankieForecastController` and `ControllerJournal` in additive modules. The
controller owns a single-writer scope and rejects overlapping runs; no distributed
leader-election claim. Its explicit async `refresh` request carries:

- unique request ID, exact frozen session registry/hash and arm hash;
- receive/event cutoffs, source prefix, explicit through-cursor and material flag;
- per-target complete existing eight-field metadata, in active-target registry order;
- independently trusted native model/execution/decoder, context-registry and
  Granite deployment/identity/config pins supplied at controller construction.

Preflight deep-copy/validate metadata and all pins before native work. Freeze the
canonical request bytes, policy/target registry, controller code, context-mapper
code, native-context prompt/parser identities, and both model configurations.
The controller configuration also binds the shared `granite_shadow.py` runtime,
so changing transport waiting, request construction or response validation cannot
silently reuse a completed request under unchanged service-module bytes.
Changes to these inputs require a new declared model/configuration generation;
ordinary source-prefix updates retain unchanged model identities. Never resolve a
human model label to whatever endpoint happens to be available.

1. Append controller intent before invoking the existing native refresh. Preserve
   the forecast ledger's own authoritative intent and recovery rules unchanged.
2. Invoke `NativeForecastRefresh.update` with the exact preflighted request. Record
   each returned publication identity, revision, target and forecast checkpoint.
   On partial failure, retain a pending controller operation and let the existing
   native refresh retry finish only missing targets under the same locked request.
3. Read each publication through `book.publication`, decode its artifact with the
   expected digest, and obtain its context/recurrence binding. Reconstruct tensors
   at the locked cursor using `_prepare`; compare source/input/model/packet identities
   to each artifact, including teacher/QSV binding and actual execution settings.
   Verify journal/model identities remain unchanged across preparation and refresh.
4. Build the exact new native-context Granite snapshot from those tensors and
   receipt, with independently obtained expected input/packet hashes. Reject any
   whole-request size limit explicitly; never truncate evidence. The mapper and
   native parser remain the sole authority for their new schema.
5. Append critic intent containing exact snapshot/prompt text, schema/model/config
   hashes, deterministic critic request ID and timeout before provider invocation.
   Invoke the configured native-context Granite service once. Append its complete accepted or
   failed receipt, raw response evidence and explicit status before exposing it.
6. For every returned publication call `consume_forecast`, retain its exact stamped
   JSON/digest and link it to the native publication and critic receipt. Commit the
   combined result before returning it. Never inject critic text into the twelve
   existing fields; store it in the separate combined receipt.

## Durable combined evidence and retry

Use a separate `EvidenceJournal` with an explicit new schema and trusted count/head
restore checkpoint. Do not place forecast/critic rows in C15. Record immutable
canonical payloads for `INTENT`, `NATIVE_COMPLETE`, `CRITIC_INTENT`, `CRITIC_RESULT`,
and `RESULT`; validate their legal transition order and cross-hashes on replay.
Combined result includes request/config hashes, exact source/cutoff/cursor,
native/context/recurrence identities, target publication/revision/artifact hashes,
critic snapshot/request/response/status/verdict/config identities, and exact
category-free record bytes/digests. Preserve prior attempts and revisions.

A completed request replay returns the stored result with zero native forwards
and zero provider calls. Reusing a request ID with changed metadata, pins, source
or cutoffs fails before side effects. A controller append whose commit is uncertain
stops the instance; reopen only against a trusted journal checkpoint. Reconcile
forecast checkpoints by verified prefix extension, never by truncating either
journal or assuming the two journals committed atomically.

An unmatched `CRITIC_INTENT` means external completion is unknown. Do not blindly
reinvoke on restart and do not claim exactly-once remote inference. Require an
explicit recovery attempt with a new attempt ID linked to the prior unknown call;
preserve the prior record. The existing service retains its busy guard after a
timeout until the underlying call ends; late responses cannot become accepted
current results. A durable known failure may be inspected without reinvocation.

## Verification and delivery increments

Test the additive native-context service paths with
the real installed SDK shapes plus fake provider responses, including complete
prompt preservation, new parser bindings, timeouts and late-result isolation.
The controller depends on a configured native-context Granite service protocol,
not a Bedrock-specific class. Exact Granite 4.2 operational deployment requires
the explicitly pinned supported serving route, including SageMaker where Bedrock
does not provide that exact model. The protocol exposes enabled, identity,
request_timeout and current config_hash properties and async critique_native(snapshot, request_id=).
Then implement controller orchestration and journal replay together, using actual
synthetic C15/B1/decoder/rolling-book fixtures and that service with a fake SDK.
Do not replace the integration with wrapper-only tests or hand-made publications.

Required proofs: disabled legacy identity; all active horizons; full native-context
mapping and required critic invocation; same-forward artifacts without an extra B1
forward; unchanged Frankie bytes on critic disagreement; malformed/timeout/busy
status isolation; zero-call completed replay; partial native commit recovery;
unknown external completion; changed-source/config/request rejection; immutable
history; journal mutation/unknown-write failure; exact restore; no order/client or
Memory A side effects. Existing forecast/Granite/Frankie controls must stay green.

Live acceptance is a separate explicit harness using owner-supplied deployed model
ID, endpoint capabilities, actual model/tokenizer/runtime pins and authorized
source/session manifests. Inventory availability alone does not attest deployed
weights. Do not fabricate missing checkpoint hashes or claim empirical accuracy,
production throughput or production B2_GATED completion from synthetic software.
