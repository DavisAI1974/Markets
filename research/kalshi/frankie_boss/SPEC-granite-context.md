# Granite full native-context mapping

Additive schema `BOSS_GRANITE_NATIVE_CONTEXT_V1` and prompt
`BOSS_GRANITE_NATIVE_PROMPT_V1`. Existing state serialization V2, Granite V1
prompt/parser and original controls remain unchanged. The new schema is explicit
because native per-row QSV and typed payloads cannot fit the old global-QSV shape.

## Authority and exact mapping

Input is a prepared native context from ContextSessionRunner: exact tensors,
ContextReceipt, entity pair and native registry. First validate token inverse
reconstruction via `reconstruct_payloads`. Recompute the native input hash from
receipt info, entity, exact tensor identity and explicit QSV binding, using the
existing context_session conventions. The caller supplies an independently trusted
expected input hash and recurrence packet hash. Compare them before constructing
any critic prompt. Do not run a new model forward.

One critic row is one native context row, in the same order. Each contains:
- all original registered record fields and exact adapter/source-context/defect
  metadata, represented with canonical `c15_journal.pack` typed encoding;
- named raw/adapter field paths and declared scalar types/values for inspection;
- the exact native graph parent index;
- per-row QSV values and masks with QSV_FEATURE_REGISTRY coordinate names.

Exact packed evidence is visible model input, not a hash-only sidecar. No raw
value, signed-zero bit pattern, bytes, nested extension, defect, null, missing
key, graph edge or QSV mask may be reduced, averaged, truncated or repaired.
Registered nested fields retain their original member names. Numeric units are
only asserted where defined by native names (timestamps ns, price_raw raw integer
units); other fields retain explicit original source representation.

No unrestricted extras: raw keys must match NativeRegistry; metadata must match
the exact ContextSessionRunner.record_metadata shape. Reject teacher arrays,
forecast outputs, future/outcome material and unregistered fields. The existing
lexical answer-wall vocabulary is checked on original decoded keys/string values
before packing so escapes/byte conversion cannot conceal prohibited content.
This is defense in depth, not a proof that a named source contains no answers.

## New references and output contract

Retain Granite output V1's seven keys, bounded text/list sizes and
evidence_verdict enum. Each evidence reference is still `{row, field}`; `field`
must equal a canonical named path present in that row, using JSON Pointer escaping
(`/record/price`, `/metadata/adapter/ts_event_ns`, `/qsv/FEATURE_NAME`). Container
paths and leaves are addressable; types distinguish scalar, null, bytes, sequence
and mapping. Never alias numeric column positions to invented market meanings.
An additive native-context parser applies the same L0-L4 ladder and schema
validator; L3 checks exact native snapshot hash and named-path membership. It
never calls the old V2 parser on V3 data or changes existing model contracts.

## Inverse and operational tests

Canonical parsing must reproduce identical bytes and restore every packed raw
record/metadata payload, graph parent and named QSV value/mask. Snapshot identity
binds exact native input, source prefix, registry, scope, clocks and packet receipt.
Tests mutate raw values, row order, masks, QSV binding, source/cutoffs and pins;
each mismatch rejects before critic invocation. Tests cover nested registered
fields, bytes, signed zero, null versus absent, masked QSV and forward parents.
Prompt includes the complete canonical context. No local token estimate claims
provider capacity; any configured byte ceiling is explicit and rejects the whole
request, never truncates. Deployment token limits remain provider-enforced.

## Scope of this slice

Owned files: granite_context.py, tests/test_granite_context.py, this spec. Build
mapping, prompt and native-context parser only. Root subsequently adds the service
transport path and durable combined controller evidence. No actual provider calls,
native forecasts, trading, teacher training or outcome reads in this slice.

## Concrete API and verification

`map_native_context` requires keyword arguments `tokens`, `receipt`, `entity`,
`registry`, independent `expected_input_hash` and `expected_packet_hash`, and
`source_as_of`. `expected_qsv_binding` is additionally mandatory whenever QSV is
present. It returns immutable `NativeContext.text/hash`; its `reconstruct()`
recreates every native tensor through the unchanged encoder. `payloads()` and
`fields(row)` return owned evidence and exact reference paths.

`parse_native_context(text, expected_hash=...)` rebuilds and byte-compares the
whole canonical body, including scalar displays and graph. The expected snapshot
hash must come from trusted receipt storage when reading persisted artifacts.
`build_native_prompt` returns `.text`, `.snapshot_hash`, `.system_prompt_hash`.
`score_native` returns the existing reward/Verdict ladder; runtime and training
are aliases of that exact function. `native_parser_code_hash()` binds this module
and its parser/schema/native encoding/receipt hashing dependencies.

Run with repository root and package directory on PYTHONPATH:
`python -m pytest research/kalshi/frankie_boss/tests/test_granite_context.py -q`.
No actual Bedrock or native forward is required for these mapping checks.
