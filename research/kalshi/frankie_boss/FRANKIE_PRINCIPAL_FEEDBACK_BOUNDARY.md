# Frankie principal feedback boundary

`frankie_principal_adapter.FrankiePrincipalAdapter` connects the independently
pinned frozen `prepare_boss_attachment` subprocess to an authorized host agent
session. It never selects Claude merely because the CLI exists, calls a provider
API, computes market labels, or claims that rendering a prompt ran Frankie.

## Configuration and actual use

Construct with the frozen receiver checkout and commit, its Python executable,
a separate durable output directory, preparation CLI kwargs (underscores), and
emitter CLI kwargs (hyphens). `render['knowledge-receipt']` is mandatory: supply the
verified pre-Sunday Memory A bundle, not an automatically refreshed historical
post-Sunday bundle. `protected_files` maps memory names to `{path,bytes,sha256}`.
`section_evidence` maps all 18 IDs (`4.0`, `4.0b`, `4.1` through `4.16`) to trusted
historical principal output file witnesses. `feedback_contract` is the explicit
request/session/chronology/query policy provided by the runtime. Configurations
are pinned across recovery.

1. `prepare(handoff_directory)` runs the actual frozen receiver and prompt emitter.
   It verifies retained preparation inputs, manifest members, output witnesses,
   frozen receiver commit, prompt, memory, and preserved section files.
2. The cycle coordinator persists its principal intent, then calls
   `execute(request_id, attachment)`. The adapter also writes/fsyncs the complete
   `session-request.json` before dispatching any session executor.
3. If `session_executor(request)` is supplied, it must be the authorized host's
   actual agent-session bridge. With no callback, `PrincipalPending` exposes a
   durable outbox for the host's real agent tools. Read the outbox, invoke Frankie
   with its exact files, then call `record_session_response(response, host_attestation=...)` with the
   actual session output and the host's independent saved dispatch/output witness. Do not synthesize labels
   in the runner or use a historical session ID as proof of this new call.
4. `recover(request_id, attachment)` never calls a session. No saved adapter request
   raises `PrincipalNotDispatched` (safe for the coordinator to execute). An existing
   request without a complete response raises `PrincipalPending` and must not be
   redispatched. A saved response yields the same envelope.
5. `verify(envelope, request_id, input_hash, source_hash, learning_cutoff_ns)` checks
   against the retained session response and returns typed `FrankieFeedback`.
   The learner performs its existing full session/causality/label checks before
   gradients. The coordinator saves the envelope before the atomic update.

## Session response schema

The actual session response is a JSON object containing:

- `session_id`, `model_identity_as_reported_by_session`: actual new host session.
- `request_sha256`: `digest(session_request)` using canonical JSON.
- `sections`: all 18 section IDs mapped to their retained principal file SHA256.
  These preserve historical authorship. The session authors **new feedback** on
  the new BOSS request; it does not falsely relabel old calculations as new work.
- `feedback`: `request_id`, `input_hash`, `source_hash`, `available_ns`, `sessions`.
  Each session has `session_id`, `timing`, `gap`, `path` matching the existing
  `native_forecast_learning` label fields. Omit `principal_receipt_hash`: the host
  adds its attested receipt hash after receiving the actual session result.
- `lessons`: newly authored lessons for the coordinator's separate append-only
  store. Frozen Memory A remains unchanged.

The host receipt binds exact request and response hashes plus actual session
identity. This is host session provenance, not a provider cryptographic signature.
The adapter cannot prove that an arbitrarily fabricated callback came from an
agent; only the authorized host may supply the session executor or response.

## Redelivery of completed evidence

`rebind_delivery_receipt(original, expected_original_sha256, local_directory,
output)` streams and verifies all original plaintext witnesses and object sizes /
known hashes. It emits a **new** receipt with updated physical paths and explicit
`local_redelivery` provenance linking the untouched original receipt bytes and
original self-hash. Source pins must cite the new delivery receipt hash. This does
not rerun market calculations or rewrite the historical source manifest.

Stage the three exact plaintext ledgers, their gzip objects,
`calculation_result.json`, and `small_artifacts.tar.gz` on a host with enough disk
space. The retained Sunday delivery needs over 10 GB of plaintext. E: has ample
space; C: does not. No source-day prerequisite is introduced: this authorized run
is Sunday only. Forecast labels still need an interior causal request cutoff and
later observations within that same day; final-prefix context cannot supply its
own future observations.

## Verification scope

Seven new focused synthetic tests passed (5.16 seconds): interrupted sessions do
not redispatch, retained responses recover typed feedback, changed feedback /
request / memory / independent pins / configuration refuse, missing section
citations refuse, and redelivery preserves original evidence. These tests are new
boundary checks, not a repeated historical suite, live Frankie execution, actual
Sunday learning, or proof that full plaintext delivery has already happened.

## Retained prompt mode (current Sunday route)

The frozen receiver checkout now carries the later post-Sunday seed and Windows
Git checkout line endings differ from original receipt bytes. Do not use its
current memory seed, and do not rewrite that checkout to make a historical
knowledge receipt pass. Original committed blobs were copied with `git cat-file
blob` to `E:/Codex/Frankie-BOSS-20260915/retained-principal`, verified against the
historical `FROZEN_MANIFEST.json`. The receipt `retained-witnesses.json` pins 29
files including all 18 sections and exact extracted pre-Sunday Memory A.

Supply these `render` keys for the new path:

- `retained-prompt`, `retained-prompt-sha256`
- `knowledge-receipt`, `knowledge-receipt-sha256`
- `knowledge-bundle-sha256`

The knowledge bundle remains beside its receipt as `KNOWLEDGE_BUNDLE.md`.
`retained_knowledge` verifies its exact historical bytes, receipt self-hash,
166,700-byte pre-Sunday seed identity and the embedded seed bytes themselves.
The adapter preserves the original prompt separately as `historical-prompt.md`;
the new prompt prefixes the current one-day instructions, unchanged historical
prompt bytes, and the exact BOSS input block returned by the real frozen
`native_boss_attachment.verify_attachment` subprocess. No regenerated historical
prompt or post-Sunday memory is represented as the original input.

Two additional focused tests passed (3.74 seconds): original prompt bytes and
exact receiver block remain intact; a self-consistent post-Sunday memory receipt
is refused. Actual retained knowledge verification also passed with the original
248,922-byte bundle and receipt `6dc5825b578ac6fd3a6afa5b13c76bcd359a857d738610e64b02efb654891ea4`.
No actual BOSS attachment or principal call is claimed by these checks.

The initial source-contract agent intent is separately saved at
`E:/Codex/Frankie-BOSS-20260915/principal-source-contract/intent.json`, request
SHA256 `9d23d35f8e83129d708b375f1410014bb8bf66418656545b3f294381a37d7e08`.
The root host owns the actual session call, then continues the same Frankie
session only after receiving the actual BOSS attributed inputs. The request
preserves all 19 historical invocation cutoffs, requires own-source certified
anchors and outcome-independent timing/query conventions, and prevents training
on end-of-day outcomes before replaying earlier same-day requests.


## Review repairs and runtime conversion

`record_session_response` now requires `host_attestation`. Its schema is
`FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1`, with `mechanism=AGENT_SESSION`,
`request_sha256`, `response_sha256`, `session_id`,
`model_identity_as_reported_by_session`, and
`host_record={path,bytes,sha256}`. The host record itself must contain the same
binding fields plus a nonempty `host_authority`. It represents the host's actual
session dispatch/output observation, not a model's self-attestation. The host
must retain the record for recovery. A callback returns
`{response: ..., host_attestation: ...}`. No provider-signature claim is made.

Both renderer paths now require pinned, verified pre-Sunday memory before prompt
construction. The emitter's result/delivery paths must equal receiver preparation
paths; adapter-only hash flags are removed from its CLI arguments. An incomplete
receiver directory is preserved under a unique `receiver.partial-*` name before
new preparation, rather than deleted or left permanently wedged.

`source_contract_runtime.bind_cycle(contract_path, expected_contract_sha256,
cycle_index, prefix)` validates the entire authored 19-cycle contract and binds
only the runtime source hash to the exact authored cursor and clocks. It returns
the typed target/session roster, registry hash, learning cutoff and authored
policy/split hashes. It does no forward pass and computes no market labels.
`metadata_for_binding(binding, state_defects_and_gaps_reported=...)` creates exact
BLD metadata with explicit development units and ABSTAIN disposition; the host
must supply known defects explicitly.

`make_principal_adapter(...)` constructs per-cycle receiver pins only after a
verified controller export exists. It calls the real full-source `bind_prefix`,
uses the new physically verified local redelivery receipt, and selects pristine
historical prompt/memory/section witnesses. Required expected manifest, mapping,
source-journal checkpoint, retained-witness and delivery-file hashes come from
trusted host receipts. The coordinator must still lazily return completed cycles
before reconstructing old runtime identities.
