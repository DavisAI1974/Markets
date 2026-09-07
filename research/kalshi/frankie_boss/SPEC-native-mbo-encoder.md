# Native MBO encoding and context sessions

Authority: Claude full-evidence ruling (2026-09-07), approved by Greg;
Greg subsequently authorized correcting its exact identity/reconstruction gaps.
Existing inventories and the serializer contract provide no native field map.

## Correction to section 3

BOSS_NATIVE_MBO_ENCODER_V1 keeps one sequence token per event. Every declared
raw field also enters a reversible exact byte tensor using the journal's
existing pack/canonical_bytes encoding. This tensor is consumed by a learned
byte embedding with position-dependent contributions at every byte; it is not
an archive sidecar. Original field order, type, null versus absent, signed zero,
float bits, arbitrarily large integers, bytes and nested extension values survive.
The inverse uses these tensors, masks and registry, never the source journal.
Neural hidden states are learned representations, not reversible raw evidence.

Order IDs enter as exact categorical bytes and additionally select causal graph
links. They never become numeric quantities or hash buckets. Distinct unknown
categories retain distinct bytes even when the semantic vocabulary emits UNKNOWN.
No retained-not-encoded class is used. Unknown field names halt mapping until
explicitly declared as registry extensions; no automatic silent exclusion.

Numeric integer values use sign/high32/low32 float64 columns (fixed width).
Both timestamp deltas use the same exact decomposition. Missing/null use masks;
the byte tensor distinguishes them. Present zero has a present mask. Values
outside a semantic column's declared integer range remain in the byte computation
path, with a false semantic mask; they are not coerced or truncated.
Categoricals: action, side, rtype, publisher/channel, flags bits and independent
clocks. Their exact raw types/values remain in the byte computation path.
Adapter metadata and integrity diagnostics are explicitly registered and encoded,
as required by the ruling that defects reach packets. Book composition/statistics
and candidate target quantities remain teacher evidence; no hidden projection of
those quantities is substituted for the native event input.

## Model and receipts

NativeTrunk is an opt-in Trunk v2 subclass; B1 wraps it without B1 code changes.
The baseline Trunk and all Frankie/provider/replay/Memory A seams stay separate.
Default attention window 128; QSV optional/ablatable. The native numeric path is
float64 throughout: a lower-precision model is rejected, not silently cast.

ContextSessionRunner uses the last T_CTX entity event rows by receive time,
ties by source cursor; T_CTX=4096 is provisional, not probe-approved. Journal
INPUT/APPLIED audit entries are not two market events. The receipt distinguishes
audit-entry count from market-record count, binds the verified journal prefix,
context [start,end), outside-context count, exact cursor/packet membership,
registry, tensor bytes, model weights/config/code and teacher alignment.
A context receipt explicitly does not claim older rows were model-visible on
that decision. All source rows remain available for full-history teacher
computation. Graph ancestry outside context becomes -1; age-in-context starts
at first observed in-context event, not an invented order birth timestamp.

No training, market-data/provider run, OSS evaluation or Oct 1 probe is authorized.
Synthetic software checks demonstrate representation and consumption, not learning
quality, throughput at MBO scale or readiness for production deployment.

Teacher outputs obey R2 section 7: one DipoleTarget artifact per context cursor,
each binding its own cutoff, prefix and normalizer receipt. The context receipt
binds the complete ordered tuple. No multi-cutoff C14 schema is invented.
Receive-time regressions halt teacher attachment instead of stamping a target
with a time earlier than evidence already read. Raw rows remain in the journal.
Failed forwards bind the prepared input/model identities; changing context,
registry, teacher state or weights cannot silently substitute a different retry.
