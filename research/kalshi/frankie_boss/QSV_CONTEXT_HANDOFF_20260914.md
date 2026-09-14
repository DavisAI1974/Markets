# Governed QSV attachment

The native runner accepts `QSVContext` plus an independently trusted
`expected_qsv_hash`. Each immutable row carries the exact registry-ordered
float64 vector, Boolean coordinate mask, entity, source cursor, receive-time
availability and source prefix. Every selected context row must have a matching
artifact row. Missing coordinates are explicit masks; present zero is distinct.
No QSV values are guessed from MBO fields or filled for an absent artifact.

The selected tensors and producer binding enter the input identity. B1's
recurrence packet hash also binds that identity when QSV is attached. Retry and
checkpoint restore reject changed QSV. Later artifact suffixes leave earlier
selected input identities unchanged. Disabled/event-only paths retain their
existing behavior; explicit QSV ablation remains available.

This is the artifact-to-model boundary, not a new QSV producer or proof of
producer correctness. The caller must obtain the trusted artifact digest from
the governed producer. Production producer wiring and conformance remain open.
Attachment currently hashes/indexes the whole artifact per decision; throughput
has not been accepted. No model/data/provider/training/OSS operational run occurred.

Validation on Python 3.13 / torch 2.9.1 CPU:
- 64 focused checks passed: QSV attachment, context session and protected seam.
- Review found B1's recurrence packet identity omitted QSV; corrected and the
  updated 11-test QSV suite passed. This rerun overlaps the 64 checks.
- Original Frankie, adapter, replay, trunk, B1 and ReFRAG registry files unchanged.

## Newly confirmed integration dependency

`TypedHeads` emits `p_up`, `size`, `regime_logits`, `contradiction`, `sigma` and
`evidence_scores`. None is a substitute for the four `InternalBLD1Heads` values:
session net USD, overnight gap USD, endogenous P50 session path and the governed
confidence label. The README explicitly retains those existing heads internally
and forbids inventing a confidence threshold in the projector.

Enabled Frankie forecasts therefore need a specified forecast-head and confidence
contract. The owner has been asked whether to provide an existing specification
or have this build design it. Until resolved, a transport wrapper alone must not
be labeled completed production integration. Original protected BLD-1 remains
unchanged. All other production and experiment gates remain open as in the workbook.
