# C15 D-chain isolated implementation

Authority: R2 target-semantics proposal §5 and corrected
`CLAUDE_BOSS_CONTRACT_ADDENDUM_R3_20260907-1.md` §4.1.
Base: reviewed record-prefix foundation `17e4b46a`.

## Implemented surface

`c15_dstate.py` computes the six unnormalized D columns for one instrument,
one completed group at a time. Tick size is declared at construction; rational
raw-price/tick comparisons preserve exact threshold comparisons. Pullback and
break constants remain 1 and 3 ticks. The machine never chooses the anchor,
reconstructs a book, averages a path, or reads a future group.

- A break retains the extreme, clears completed-step history, disarms, and
  remains broken until a strictly new extreme. The restarting extreme is
  extension zero; its preceding break pullback is not credited.
- Undefined anchors and invalid book observations freeze geometry. A later
  defined reversal resets it. Source-member/session changes reset geometry,
  including when their first observation is undefined.
- Every supplied instrument group advances its ordinal. Frozen observations
  leave `age` frozen under the explicit freeze rule. Completed duration uses
  group ordinals, so it includes those intervening groups.
- `duration_last` is captured when an extension completes, following the
  explicit R2 §5.4 last-completed-step tuple. Subsequent unarmed advances do
  not rewrite the completed step's duration. This interpretation was surfaced
  to the coordinator and confirmed before review.
- Immutable outputs carry PRESENT/MISSING/INVALID strings matching C14 state
  names; missing/invalid values are exactly zero. C14 tensor conversion and
  float32 emission belong to the later builder. This module emits raw float64
  log transforms and does not normalize them.

## Authority boundary

`DChain.advance_synthetic` is an explicit mechanics seam with no claim of
source authority. `ReceiptDChain` is a separate, explicit consumer bound at
construction to a `RecordPrefixChain` and a publisher/instrument. It verifies
the actual chain's result-bearing context, then requires gapless per-instrument
group ordinals. Other instruments can interleave without invalidating the
current instrument's receipt.

The emitted receipt binds the input record receipt hash, terminal prefix,
module git-blob SHA supplied by the verified constructing caller, canonical
config hash, observation, and six output columns. Hashing uses only
`causal_packet.canonical_bytes` and domain-separated SHA-256. This binds the
declared code identity; the pure module does not read its own source file.

Receipt binding is not a proof that the caller derived the anchor, session,
integrity flag, or far-side price correctly from that prefix. That proof
remains with the authorized observer/builder integration. No automatic hook or
production call site is installed here.

## Deferred scope

C1 lifecycle implementation remains blocked under addendum §7. Section 4.2
clarifies partial cancellation and identity termination but does not override
that block; its lifecycle acceptance tests D5-D9 are deferred with C1.
The 19-column builder, observer, checkpoint/resume slice, normalizer, registry
promotion, market probes, training, provider calls, and Frankie changes are
not implemented by this lane. C15 remains partial.

## Verification

Before implementation: the two prefix modules' existing test suites passed
70 tests with exit 0. The new D-chain tests first failed collection because
`c15_dstate` did not exist (exit 2), then the first 21 tests passed after the
implementation (exit 0).

The tests pin T-A, T-B, T-C and T-D; same-group arm/break precedence; sustained
broken state; freeze/reset behavior; mirrored BID/ASK direction; completed
duration retention; exact tick thresholds; suffix and immutable-output
invariance; malformed inputs; source regressions; and real receipt authority,
including rejection of probe and stale receipts. Final regression evidence
and independent review disposition are recorded in the review package.
