# A-memory Member-First Native-MBO Recalculation Specification

## Objective

Recalculate the useful book-state focus of the completed A-memory diagnostic RT
replay without reducing individual F_LAST-closed groups to daily averages. Keep
the original daily summaries as coequal context, then discover exact native
families, subfamilies, pairings, recurrence structures, and causal chains that
explain when similar aggregate values arise from different market mechanics.

This is a read-only retrospective derivation over the preserved A-memory native
ledger and verified checkpoints. It does not invoke Frankie, resume A-clean
Forecaster, create a lock/freeze, or cross the Step-1/reveal wall.

The derivation may use only evidence actually present in that initial diagnostic
run. It must not add a corrected packet, supplemental/enriched feature source,
newly recovered data, rerun-only context, or any information that should have
been supplied but was omitted the first time. Those additions belong only to the
later corrected reruns. Deterministically reconstructing per-group book/FIFO
state from the initial run's own preserved raw actions is recalculation of the
same evidence, not enrichment.

This is an output-oriented A-memory improvement pass, not a clean-versus-memory
test. Scientific interpretation may use the verified prior A-memory package and
positive same-arm knowledge already derived from this initial run, including new
same-arm findings promoted during the retrospective. Those materials guide what
relationships to inspect but cannot alter native measurements or supply missing
market evidence. A-clean output is not evidence for this derivation; the A-clean
arm remains necessary later for the corrected comparative reruns.

This initial diagnostic used a degraded information surface because material
that should have been available was omitted. Therefore this pass may promote
mechanically supported positive findings, refinements, and confirmations, but it
must not promote a negative or null research conclusion whose apparent absence
could be caused by that omitted information. The exact member calculations and
all unmatched/open-world structures remain preserved. This is a one-time
missing-input exception, not a general positive-only rule: every later corrected
full-data run must retain negative, null, contradictory, and falsifying evidence
alongside positive findings.

## Inputs and identity

- A-memory run: `frankie-a-memory-rt-c7da7d257fda-1`.
- Native ledger:
  `/workspace/scratch/da00127ac123/a-memory-runtime-c7da7d2/native-evidence-groups.jsonl.gz`.
- Required ledger SHA-256:
  `bc0788b51a719d39f5024f10007f4c74e96ff3361a21b66d662d9fadf1a67d8f`.
- Required population: 5,667,689 native records and 4,256,603 F_LAST-closed
  groups across the four hash-bound source days.
- October 1 and 3 are warmup/development; October 4 and 5 are held-out
  discovery. No cross-day population average is permitted.

## Exact-member contract

Emit one record per F_LAST-closed group containing:

- group index/hash, source, source role, native record cursors, and instrument;
- event, first-component receive, F_LAST availability, and formation clocks;
- exact action string, side string, ordered actions, prices, sizes, and order IDs;
- the original eight post-group measurements: spread, full-depth imbalance,
  bid/ask depth, bid/ask order count, and bid/ask price-level count;
- the same eight pre-group measurements when a lawful prior closed state exists;
- exact before/after deltas;
- action/side quantities, fill multiplicity, distinct prices/order IDs, and
  same-ID post-fill disposition; and
- deterministic family, subfamily, mirrored-side, adjacency/run, same-order
  lifecycle, and session-phase linkage fields when supported.

Every member remains recoverable. Rare and singleton structures remain explicit;
they are never discarded as noise.

## Family and pairing hierarchy

1. Exact member.
2. Exact action-family plus exact side-sequence stratum.
3. Mechanical subfamily: multiplicity, price span, order continuity, terminal
   disposition, replenishment/withdrawal/resizing, priority, and touch response.
4. State-transition subgroup based on the joint exact before/after values and
   deltas of the original eight measurements.
5. Causal relationships: mirrored-side pairs, prior/next group edges, maximal
   runs, same-order lifecycles, session withdrawal/restart chains, and candidate
   precursor/birth/recognition/completion runways.

The established structural seeds are
`P=persistent_exhaustion`, `O=collapsed_opposite_flow_reversal`,
`S=collapsed_same_flow_reload`, and `X=collapsed_sparse_indeterminate`;
transition orientation remains separately `SAME` or `FLIP` (historical post-pipe
`S`/`F`). They are not hardcoded output classes. The recalculation must expose
the exact native characteristics needed to reproduce, split, or extend them and
must issue deterministic candidate IDs for unmatched structures. There is no
maximum family count.

No centroid or global clustering operation may merge different days, families,
subfamilies, sides, sessions, phases, clocks, or existing cluster identities.
Numerical density clustering, if later warranted, occurs only inside one fully
identified structural stratum and cannot erase its exact member roster.

## Coequal averaged companions

Preserve the first replay's per-day `first`, `last`, `min`, `max`, and arithmetic
`mean` for the original eight measurements. For each valuable exact family,
subfamily, pairing, run, or lifecycle, an arithmetic companion may be calculated
only within one identical source-day, side, session, phase, and clock stratum.
Every companion names its denominator and member roster. Differences caused by
scope or granularity are `COMPLEMENTARY_SCOPE_DIFFERENCE`.

## Exhaustion and timing interpretation

The recalculation supplies exact native candidates to the full RT mission; it
does not mechanically declare exhaustion from a book-state cluster. Candidate
runways must preserve lawful precursor, birth/onset, first durable prediction,
recognition, persistence, inflection, recurrence, completion/reversal, dipole,
and direction evidence.

Prediction timing is continuous: `PRIOR` with exact lead when a durable call is
lawful before birth, `T0` at birth, otherwise first lawful `H+N`. D0-D5 denote
successive exhaustion-chain depth, not quality; deeper open-world lineages remain
eligible. Future realized depth, duration, descendants, and path shape are
forbidden at earlier cutoffs.

## Implementation and commands

- Pure grouping logic:
  `research/kalshi/frankie_raw_mbo_benchmark/a_memory_member_first_recalculation_20260828.py`.
- Unit tests:
  `research/kalshi/frankie_raw_mbo_benchmark/tests/test_a_memory_member_first_recalculation.py`.
- Focused test:
  `python -m unittest research.kalshi.frankie_raw_mbo_benchmark.tests.test_a_memory_member_first_recalculation -v`.
- Full benchmark test suite:
  `python -m unittest discover -s research/kalshi/frankie_raw_mbo_benchmark/tests -v`.
- Full calculation uses an explicit input ledger and output directory; it must
  fail closed on any identity, count, clock, F_LAST, or arm-scope mismatch.

## Outputs

The output directory contains hash-bound, deterministic artifacts:

- compressed exact-member ledger;
- exact family/subfamily index and member counts;
- directed adjacency and maximal-run ledger;
- same-order lifecycle ledger;
- mirrored-side pairing index;
- narrowly stratified averaged companions;
- run receipt with input/output hashes, counts, invariants, and limitations; and
- positive scientific findings report separating observed facts from hypotheses.

## Acceptance criteria

1. Every A-memory F_LAST group appears exactly once and reconciles to the native
   record denominator.
2. All eight original measurements are emitted per member after lawful book
   reconstruction; before/after/delta views reconcile sequentially.
3. Exact structural families and sides reproduce established counts independently.
4. Family, side, source day, session/phase, and clock boundaries cannot be pooled.
5. Pairings and chains retain exact members, clocks, and relationship evidence.
6. Unknown action paths, state transitions, and structural candidates remain
   counted and addressable; no allowlist or historical family-count ceiling can
   reject them.
7. Daily averaged values reproduce the diagnostic replay while all additional
   averages declare their exact strata and denominators.
8. No Step-1, reveal, Forecaster, other-arm, or reduced-surface evidence is read.
9. No principal model call, lock, freeze, scoring, or execution claim is made.
10. No supplemental, corrected, enriched, or rerun-only input is read.
11. Interpretive carry-forward is limited to verified prior A-memory knowledge
    and positive same-arm findings; it cannot change the exact calculations.
12. Focused and full tests pass, the full calculation completes, and output hashes
   verify before any finding is registered or promoted.
