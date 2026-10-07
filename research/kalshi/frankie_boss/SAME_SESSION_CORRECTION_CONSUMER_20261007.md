# Original-session checked correction consumer — 2026-10-07

Source-built / runtime-unverified. This implements a bounded analytical reader after
the retained correction scope ledger. It does not complete native learner training
or prove that every kind of retained knowledge reaches a supported predicate.

## Implemented boundary

`frankie_principal_adapter.prepare_knowledge_correction` adds an optional
`learner_consumer` to new requests. It pins this adapter and the existing
`frankie_box_classroom_code.py` reader by their exact source hashes. The additional
field changes the content-addressed request identity only for a genuinely new
correction intent. Preparation first finds an existing identical intent, comparing
all request fields except this additive consumer pin. It verifies each retained
request against its content-addressed directory and reuses the unique original
body/hash; ambiguous matches refuse. An old pending dispatch cannot become a new
request merely because the reader was added or its source changed. An earlier
immutable request or response is not overwritten or silently upgraded. A pinned
old reader can require explicit recovery rather than replacement. Earlier V1 follow-ups remain
recoverable with their exact original receipt shape; `learner_consumption` is
omitted for those earlier responses, preserving retained proof comparisons.

`Session.knowledge_correction` still binds the original request, initial response,
session, reported model and host authority. For new requests it now:

1. Retains the existing checked scope ledger as `scope-comparison.json` in the
   correction's existing content-addressed outbox.
2. Reads that file back and compares it to the complete checked ledger.
3. Calls `consume_knowledge_correction` with this readback and the unchanged
   original request.
4. Returns the analytical output as `learner_consumption` in the response. The
   existing response hash and independent host attestation bind that output.

The reader replaces only whole selected documents with their checked successors,
following the carried correction chain. It preserves unaffected selected documents.
The existing `REVIEW.require_current` rejects selected derived containers still
depending on superseded source hashes; it also checks the original visible evidence
for known replaced dependencies. This code does not edit old source pointers to
make an uncorrected derived result appear current.

The actual analytical consumer is the existing
`classroom_code.stage_knowledge_reproduction`. It receives complete effective
knowledge documents and only `classroom.visible_of(original_request)`. Existing
pair/component predicates perform the computation; no new predicate, numerical
method, target, label, lag or validation criterion is selected. The output carries
the complete effective selection, original request/response digests, checked-overlay
digest, original visible-evidence digest and the existing reader's full result.

Host recording/recovery computes the expected analytical response from the same
original request and checked ledger before accepting the response attestation.
The original pending-feedback object is checked against the initial response;
the original request ID and complete feedback contract are checked unchanged.

## Meaning and limits

- This is same-session **code-level analytical consumption/reproduction**. It
  is not a new forecast, a classroom answer rerun, a replacement model session,
  a native checkpoint update or independent scientific confirmation.
- Existing `checks`, `listed`, `not_measurable`, `full_claim_tested: false` and
  other unsupported-predicate dispositions stay unchanged. The consumption object
  explicitly says `all_knowledge_consumed: false`,
  `native_learning_performed: false` and
  `independent_scientific_verification: false`.
- No original model-visible classroom means refusal. SOCRATIC/VERIFY require the
  learner-owned evidence already present in that original visible package; this
  path never fetches a new snapshot, reads the host answer key or initiates a walk.
- A corrected embedded source still needs an explicit checked containing-document
  successor before that container can be used. School/meeting owner recovery is a
  separate workstream. A retained original classroom evidence dependency that is
  known to be superseded similarly refuses; no replacement observation is guessed.
- Full BOSS/native representation, targets, masks, controls, training lineage and
  unsupported scientific claim predicates remain outside this consumer. Their
  unsettled choices are not resolved by the analytical receipt.
- Transport uses the existing response/host-attestation files. The checked overlay
  remains in the owning Session outbox. Dispatch integration must distinguish an
  older ledger-only receipt (no `learner_consumption`) from this bounded consumer,
  and must not interpret either as full native learning completion.

## Review and efficiency

Applied using-agent-skills, context-engineering, API and Interface Design, and
code-review-and-quality. Reused the documented AWS/source-only constraints, the
existing whole-file witness cache, existing correction/currentness rules and the
existing evidence/predicate reader. No new service, cache, worker pool, validator
framework or claimed measured speedup. Repeated GUIDED evidence access uses the
reader's existing process-local evidence cache; host verification still recomputes
the analytical result rather than trusting a completion flag.

Both changed Python modules passed AST parsing without imports and scoped
`git diff --check`. Source/interface review traced preparation, retained readback,
predicate invocation, host recording and recovery. No tests, data/model runs,
project imports, AWS calls, installations or runtime verification occurred.

Owned changes: `deploy/aws/box/frankie_box_boss_session.py`,
`research/kalshi/frankie_boss/frankie_principal_adapter.py`, and this document.
