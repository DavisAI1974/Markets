# Exact stacked native context V1

## Problem and scope

The first actual 3,262-record context required 929,730 input tokens in the
existing compact representation. Its native fields, DBN wire bytes, adapter
metadata, and per-record provenance hashes contain exact representational
redundancy. This codec removes that redundancy without changing any decoded
market evidence, native state, scope, clocks, graph, or receipt value.

This is a new candidate representation. It does not modify the original compact
module or claim that a model understands the new notation. Model admission and
the route wrapper remain separate. No source database, provider, or model is
called by this module.

## API and identities

`encode(value, scope_public=None, prefix_seed=None, limits=DEFAULT_LIMITS)` accepts
the exact typed dictionary returned by the compact tree decoder. It returns
`BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V1`, carrying its versioned prompt and grammar
hash. `decode(envelope)` restores the exact original value. Encoder acceptance
requires equality of `canonical_bytes(pack(decoded))` and the original bytes,
including dictionary order, sequence type, float64 bit patterns, and byte strings.

`GRAMMAR`, `PROMPT_VERSION`, and `grammar_hash()` describe and identify the
model-facing notation. `codec_code_hash()` binds this module, C15 packing,
canonical JSON, and both source-prefix formula modules, plus the required
`databento-dbn==0.62.0` wire-constructor version. A route must pin that code identity
and the grammar; the envelope does not grant itself operational authority.

## Composable reductions

1. Ordered maps become named columns when their layouts agree. Scalars,
   dictionaries, repeated values, integer deltas, integer runs, byte columns,
   and exact float64 representations retain explicit type tags. Strings that
   are exactly 64 lowercase hex characters may use reversible 32-byte base64.
2. For each applicable record, the pinned SDK `MBOMsg` constructor rebuilds the
   original DBN wire representation from its typed fields. Every encoding attempt
   compares complete bytes. Mismatches, unsupported records, and unavailable SDK
   support retain literal fallback values. Reconstruction never repairs a source
   field or changes a timestamp.
3. Thirteen adapter aliases and the derived price, snapshot flag, and last flag
   are copied/calculated from the raw record. Exceptions preserve differing
   original types and values. Paths, source hashes, clock declarations, defects,
   and other metadata remain literal evidence, optionally compressed by the
   general column/dictionary layer.
4. A packet-hash recipe is optional and conditional. Its complete scope and
   preceding seed are included inside the envelope. Every regenerated hash must
   equal the original before the literal vector can be replaced.

## Source-prefix and packet-hash requirements

The codec sorts supplied evidence by actual source cursor for chain calculation,
then restores packet hashes in the original context order. Supplied cursors must
be unique and contiguous, agree with `receipt.context_cursors`, and end at the
original source-prefix commitment. The scope genesis must match the receipt.
Every source-member assignment and source hash is checked against the scope.

At cursor zero, the supplied scope defines the genesis. For a later window the
caller must explicitly supply:

```json
{
  "next_cursor": 100,
  "previous_prefix_hash": "<trusted prefix through cursor 99>",
  "scope_genesis_hash": "<original scope genesis>"
}
```

The caller must obtain this seed from trusted original prefix evidence. The
codec does not look it up, infer it, or fabricate omitted rows. Wrong/missing
seeds, holes, omitted intervening entities, mismatched packet hashes, or a
different terminal source commitment retain the complete literal hash vector.
Encoder fallback does not mutate the caller's input.

The record-prefix calculation uses the existing
`BOSS_CAUSAL_PREFIX_V1/RECORD` domain and full `RecordInput.stable_action()`.
Only its already-defined unstable local `source_dbn_object` field is excluded
from the source-chain action; that path remains in the restored original
metadata and in each packet's exact evidence. Packet hashing uses the existing
`C15_FULL_EVIDENCE_V1` packing/hash implementation over the ordered fields
`schema`, `source_prefix`, `record`, `metadata`, and `as_of`.

## Model-facing use

The grammar explains named columns, their numerical meaning, original row
order, and reconstruction recipes. It explicitly separates market facts from
provenance hashes, dictionary indexes, and encoded lengths. This is not an opaque
compressed blob. The route must still expose the correct original native hash
and reconstruct any native views it normally validates.

Decoder resource limits reject excessive depth, expanded entries, bytes, or
input size. Rejection never means dropping rows or truncating input.

## Evidence and limits

The retained actual offline experiment reconstructed all 3,262 wire records,
all sixteen adapter fields per row, and all 3,262 original packet hashes exactly.
Its complete typed inverse passed. The experimental combined prompt measured
91,914 input tokens plus 1,200 output tokens, versus the model's 131,072 positions.
These are experimental prompt measurements, not a measurement or admission of
this production wrapper, its grammar, or a later 4,096-record context. They are
not evidence of model comprehension or successful inference.

New targeted synthetic checks cover exact type/float-bit/order preservation,
genesis and explicit later seeds, missing-seed/gap/hash fallbacks, literal wire
and adapter exceptions, and decoder expansion/duplicate-key rejection. Prior
passing suites and original model tokenization are not repeated.
