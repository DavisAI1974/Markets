# BOSS full-evidence corrections — 2026-09-07

Status: correction batch implemented and reviewed; **native model-input mapping
is still a build blocker. Do not advance to results, deployment or OSS evaluation.**

Owner authority: Greg explicitly rejected silent/arbitrary data loss, history
caps, raw normalization/averaging/smoothing, and retaining evidence without
counting it. Those instructions supersede the old C15R2 reduction choices and
Claude's clearance of the earlier 9b12aaf1 batch. This is a separate branch:
`codex/boss-full-evidence-20260907`. Old review documents are historical evidence,
not clearance of these changes.

## Corrected

- C15 uses an append-only, hash-verified journal. Every submitted raw mapping is
  recorded before processing. Successful records each return and stream their
  raw fields, effects and diagnostics, including non-F_LAST events. Failure
  preserves the submission and stops processing. No history or output cap.
- All order IDs, completed-order histories, resets, sessions, source members,
  FIFO positions and price levels remain available. No guessed order birth
  timestamp. Missing-reference events remain explicit evidence. No 1,024-group
  window, 4,096-observation eviction, warmup suppression, clipping, averaging,
  normalization, smoothing or six ablated slots in the replacement C15 path.
- Exact IEEE-754 float bits (including NaN payloads and signed zero), bytes,
  integer digits and raw additional fields survive journal round trips. Restart
  verifies the complete journal and retains unexpected tails rather than
  truncating them. Canonically equivalent byte tampering is rejected.
- Causal packet v2 retains all as-of records and all known versions. Features
  see full histories; current-fact resolution is an explicit `latest_records`
  query. Packet evidence and feature outputs are deeply immutable. New exact
  bindings prevent the old 12-digit canonicalizer from hiding payload changes.
  Legacy canonical_bytes remains unchanged for existing prefix identities.
- `values` keeps one slot per row and exact numeric types. `field_entries`
  distinguishes absent, explicit null and present zero with original identity.
- Databento retains every received row, including clock inversions. Both
  timestamps are preserved. Independent clock treatment requires a named
  contract bound to the actual adapter; generic sources cannot bypass checks.
  Receive time still prevents future evidence leakage. Defects reach packets.
  Missing authoritative completeness is explicitly degraded, never inferred
  from maximum observed time. Operator fetch history is retained separately;
  future-row counts cannot leak into an earlier model packet.
- Trunk v2 defaults to complete causal attention and enabled QSV. Numeric,
  categorical and QSV missingness are per field. Available coordinates retain
  their computation paths; missingness is represented separately from zero.
  Extra categorical columns fail explicitly. Future/invalid ancestry fails.
- `FullHistoryRunner` processes every submitted tensor row on each decision,
  across appends. It forbids finite attention windows and QSV ablation. It
  returns one evidence score per row, retains failed inputs for retry, binds
  row-to-packet ranges and actual weights/config/code/QSV registry, and checks
  trusted input and model identities on restart. Its receipt is explicitly an
  **ordered tensor-session receipt**, not proof of native-field completeness.
- State serialization v2 preserves exact int/float identity, all finite float
  round-trip digits, large integers and signed zero; it rejects underflow,
  extra QSV entries and mislabeled old schema IDs. Independent-clock rows can
  retain both timestamps. Missing data cannot silently carry discarded values.
- Granite schema/prompt v2 removes evidence list counts and text length caps.
  Empty hypotheses are valid. Types, references, exact keys, the answer wall
  and closed verdict vocabulary remain integrity controls.

## What remains unresolved

**The repository has no authoritative complete native-field-to-tensor mapping.**
The inspected `research` tree has Trunk/B1 implementations and synthetic test
inputs, but no production instantiation connecting all C15 evidence to model
columns/tokens. The existing serializer spec explicitly declined to invent
names for anonymous tensor columns. The old 19-column target is both incomplete
and superseded by Greg's instruction.

The tensor-session fixes do not solve this: a missing order ID can still be
absent upstream of its tensor boundary. Source causality and one-to-one coverage
must be established by the missing mapping. Do not claim an archive, callback,
row receipt, evidence score, or changed random-model output alone proves every
native field was mapped or meaningfully learned.

A concrete representation decision is needed before that last correction:

1. **Lossless typed field/event tokens (proposed):** preserve source field paths,
   exact scalar type/value, explicit absence, order/event identity and causal
   receipt links. Variable field/order counts expand the sequence rather than
   dropping columns or hashing IDs into collisions. Integer identity cannot be
   coerced through float32/float64. This is a new encoder contract and requires
   its own schema, inverse reconstruction and per-field coverage/use proofs.
2. **An existing authoritative field registry, if Greg has one:** use its exact
   field names, units, encodings and causal mappings. It must account for every
   raw/native field, including partial records and unknown IDs, without the old
   reductions. The current anonymous numeric/categorical defaults are not such
   a registry.

Neither alternative has been silently implemented as a new scientific model.
After the representation is settled, implement the source-to-model mapping,
prove no unmapped fields/rows at every cutoff and on resume, and prove available
coordinates in partial records affect computation. Then attach the corrected
teacher/native path and continue the rest of the planned build. OSS evaluation
stays last.

## Boundaries deliberately preserved

Frankie's existing adapter, replay, planes, Memory A, calculations and BLD-1
projection were not changed. That protected adapter still calculates its own
activity windows/statistics and compact frames; C15 separately preserves the
complete raw history/all-order state so those summaries do not replace evidence.
There is no claim that all historical reductions have vanished from the repo.

Historical C15 normalizer/D-summary modules and experimental ablation helpers
remain for provenance/reproduction. The replacement C15 builder does not import
or use them. Finite attention remains an explicit historical experiment option;
the new full-history serving interface rejects it. B1 finite reasoning depth,
causal/source-identity checks, decision abstention and the narrow Frankie output
boundary are not source-retention limits. Neural LayerNorm, softmax and learned
memory arithmetic were not removed. Evaluation/teacher aggregate metrics remain
in their parked research harnesses; they are not substituted for raw input.
These distinctions need to remain visible, rather than claiming “all averages
and limits removed everywhere.”

No market-data replay was executed by the abandoned capped C15 draft, and no
real-data journal has been created by this correction. Therefore this work did
not restore a previously pruned live dataset. Restoration of an independently
existing dataset would require its original source members and prior receipts.

## Validation and review

- 340 focused tests passed across `test_boss_full_history`, `test_causal_packet`,
  `test_seam`, `test_b1_reasoner`, `test_boss_precision_and_output`,
  `test_state_serialization`, `test_granite_prompt`, `test_granite_parser`, and
  `test_granite_evaluation` (11.07 seconds).
- 15 C15 full-evidence tests passed, including 4,200 events, deep books,
  missing-reference IDs, exact bits, nonterminal rows, failures and resume.
- A separate test_trunk run passed its 17 non-training tests. Its existing
  end-to-end synthetic training smoke was blocked at optimizer construction by
  the scratch runtime's missing `sympy`; it was not deleted or disabled.
- A second-model read-only review found and then cleared numeric type loss,
  journal NaN/canonical-byte issues, mutable packet evidence, packet membership,
  model provenance, clock authorization and false watermark completeness.
  It agrees that native mapping remains a blocker.
- No market/provider/AWS/result-bearing run or deployment was performed. These
  are synthetic software checks, not predictive or trading evidence.

The review package includes the complete BOSS source/tests/docs at the branch
snapshot, a diff from 9b12aaf1, a file hash manifest, the updated workbook and the
four requested files: trunk.py, causal_packet.py, state_serialization.py and
frankie_contract.py. The latter remains unchanged.
