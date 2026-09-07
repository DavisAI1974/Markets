# C15 complete evidence — owner's replacement contract

Authority: Greg's instructions in this session supersede C15R2's reduction
choices: "Get rid of all of the restrictions and limits and averages" and
"once that is done, check the rest of the boss."

## Objective and scope

Replace the unfinished C15 builder/observer/registry, not Frankie's existing
inputs or calculations. C15_FULL_EVIDENCE_V1 preserves individual evidence.
It is not the old 19-column C15R2 candidate and does not claim that six
unimplemented calculations have become available by relabeling their masks.

No 64/1,024-group selection, no 4,096-observation eviction, no warmup
suppression, no clipping, no normalization, no averages, no smoothing, no
top-three selection, no two-step geometry summary, and no ablated target
slots in the replacement path. It records both sides without flow thresholds.

The old pure C15R2 modules are historical research implementations. The new
builder does not import or use them. Their contracts must not be represented
as current build authority. Existing neural model arithmetic is audited
separately after this correction; it is not silently rewritten here.

## Storage and interface

- c15_journal.py: append-only SQLite evidence journal with hash-bound entries;
  no pruning, time-to-live, or row cap. Iteration streams all requested history
  without requiring all history in RAM. Every submitted raw mapping is saved
  before normalization; rejected processing is recorded and stops the builder.
- c15_observer.py: lossless reads of all authoritative resting orders, FIFO
  level membership, raw clocks/prices/sizes, and existing apply effects.
  No private parallel book and no invented origin times. Existing adapter
  frames are preserved as original outputs, including its existing statistics.
- c15_builder.py: original adapter's public normalize/book.apply calculations,
  exact per-record prefix, every group receipt, and complete observations.
- c15_registry.py: replacement evidence schema and exact code identities.

Completed-order evidence is retained even after the exchange removes an order
from the current resting book. Reset, source-member and session transitions
are records, not deletion commands. All integrity diagnostics are retained.
Missing original birth history is not filled with an invented timestamp. The
journal exposes the full recorded history for recovery and analysis.

The immutable input member is still bound by its source hash/count. Prefix
cutoffs and source integrity checks enforce evidence identity and causality;
they do not evict prior evidence or discard malformed submissions silently.

Each checkpoint binds the full journal prefix, adapter state, prefix state and
code identity. A journal tail after the checkpoint is retained and reported,
never truncated to make resume pass. Every input and output is committed;
disk/write errors stop processing. No claim of unlimited physical disk space.

## Verification and coding conventions

Python standard library and the existing V4 adapter; direct/package import
fallback follows existing BOSS tests. Use explicit data records and iteration,
not aggregate replacement values. No new dependencies, market reads or runs.

Command (with this checkout and existing test runtime on PYTHONPATH):
`python -m pytest -q research/kalshi/frankie_boss/tests/test_c15_full_evidence.py --tb=short`

Verify synthetic history beyond 4,096 entries; deep FIFO orders; snapshot-born
IDs; partial/full cancels, fills and reset history; exact float preservation;
interleaved F_LAST groups; malformed submissions retained with failure details;
continuous/resumed identity; altered/missing/extra journal history rejected;
original adapter frames/legacy rows/state unchanged. Review the rest of BOSS
only after these corrections are complete.

Teacher tensor packing and deployment remain incomplete. The replacement
does not silently pretend that an uncapped evidence stream fits the retired
fixed-width target schema. No OSS evaluation until the end of the build.

Owner clarification: "We can't not drop them only to have them not counted."
Every successful record is returned in AppliedEvidence.evidence and emitted
by evidence_stream, with complete raw fields, applied effects and diagnostics.
The stream includes non-F_LAST and incomplete records. A failed builder cannot
serve a supposedly complete consumer stream. Storage/stream proofs do not
prove use in neural computation; model attachment and per-field use remain
explicit completion requirements, not satisfied by merely archiving data.

## Rest-of-BOSS correction scope (owner: "Fix all of that")

Correct the audited reduction and visibility defects before further build
work. State serialization v2 must round-trip complete integer values and
finite float precision, including signed zero, and deliver them in readable
decimal text. Granite output/prompt v2 removes evidence-list and text-length
caps; exact keys, reference validity and answer-wall rules remain evidence
integrity requirements. Prior cap-rejection fixtures become preservation
acceptance fixtures rather than disappearing from the test inventory.

Model history access, QSV delivery, packet defect propagation and complete
model-input wiring require separate executable corrections and proofs. A
storage fix or a report listing them does not close these tasks. Neural
arithmetic and Frankie's governed output boundary must not be mistaken for
source retention; changes must preserve the protected existing Frankie path.

## Implemented rest-of-BOSS correction, still blocked at native mapping

See FULL_EVIDENCE_HANDOFF_20260907.md for exact scope and acceptance. Packet v2
retains all versions and immutable exact evidence. Independent-clock rows are
bound to the Databento adapter and remain received evidence with defects;
missing authoritative watermarks degrade explicitly. Trunk v2 uses full causal
attention/QSV by default and field-level missingness. FullHistoryRunner binds
all submitted tensor rows, their packet membership and the actual model, with
model/input-bound restart. It does not certify upstream native mapping.

The production native-field encoder/registry is absent. A lossless typed-field
representation or an existing authoritative mapping must be settled and
implemented before this task can be called complete. Do not advance to results,
deployment or OSS evaluation on the strength of storage or tensor-session tests.
