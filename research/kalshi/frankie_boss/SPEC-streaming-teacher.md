# Bounded C15R3 teacher attachment

The full prefix is consumed once in strict cursor order. The R2 and six-column R3
raw iterators receive the same exact row in lockstep. Each emits one raw result
before the next source row can arrive; an explicit one-row source avoids even
the implementation-dependent block buffering of `itertools.tee`.

Every completed group updates the R3 normalizer chronologically, including rows
outside the selected context. Non-F_LAST rows keep their original masks and do
not update normalizer windows. Only selected context rows create targets, raw
return values and receipts. No unused full-prefix R2 targets are constructed.

R3 hashes each complete original evidence row before creating a temporary
equation-specific history view. The existing 1025-group horizon retains all
action/effect/order/rank/source fields used by the equations. At closed groups it
retains both three-level FIFO cohorts with every constituent order and its full
fields, plus level and integrity information. Full-depth observations remain
unchanged in the original journal and in the evidence-content hash. This view
changes temporary feature memory only; no source records or model inputs are
discarded and no cohort members are sampled.

Raw values, masks, timestamp alignment and exclusive-prefix normalizer state
match a saved pre-change varied reference. Code-bound candidate, builder and
attachment identities change explicitly; old and new attachment hashes are not
claimed to be identical. Source builder/extraction/journal identity modules are
unchanged, so the already-running source recovery remains valid.

New regressions exercise varied fills/modifications/cancellations/unknown sides,
an unselected future suffix, bounded retention of large unused row/observation
payloads, and complete FIFO membership in both three-level cohorts.
