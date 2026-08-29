# Frankie A-Arm Pre-Launch State

Date: 2026-08-29 UTC
Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`
Status: **BUILD COMPLETE — NOTHING LAUNCHED — DECISIONS OPEN**

Nothing has been dispatched. No workflow run, no provider call, no lock, no freeze, no
handoff. This document is the agenda for the pre-launch review.

## 1. What was built

### The calculation layer — 16 of 16 contract sections

| Section | Module | Tests |
|---|---|---|
| §3 parallel-view rule (spine) | `native_stratum.py` | 26 + 13 sub |
| 4.5 formation, serialization, observation clocks | `native_clocks.py` | 26 |
| 4.6 queue position, priority, order survival | `native_queue.py` | 23 |
| 4.7 replenishment and liquidity resilience | `native_replenishment.py` | 25 |
| 4.8 absorption, withdrawal, delivered pressure | `native_absorption.py` | 22 |
| 4.9 price-ladder topology | `native_ladder.py` | 28 |
| 4.10 exhaustion state, birth, persistence | `native_exhaustion.py` | 24 |
| 4.11 prebirth prediction and H+N recognition | `native_recognition.py` | 17 |
| 4.12 dipole and opposing-pressure runway | `native_dipole.py` | 25 |
| 4.13 chain families and D-depth lineages | `native_lineage.py` | 18 |
| 4.14 recurrence, bursts, transition graphs | `native_recurrence.py` | 22 |
| 4.15 open-world cluster discovery | `native_discovery.py` | 22 + 9 sub |
| 4.16 fixed causal future-response table | `native_response.py` | 20 |
| §5 artifact layers + §6 acceptance gates | `native_calculation_runner.py` | 26 |

Sections 4.1–4.4 were already implemented in
`a_memory_member_first_recalculation_20260828.py`, which ran the full roster
(5,667,689 records → 4,256,603 F_LAST-closed groups, 4,758 candidate families, 2,985s)
with `daily_averaged_companion_verification: EXACT_MATCH`.

### Durability

| | |
|---|---|
| `periodic_checkpointer.py` | Save points on a record or wall-clock interval, pushed to durable storage as written, refused inside an open event group. 18 tests. |
| Workflow timeouts | 60 → 350 minutes on both A-arm launch jobs; 45/120 → 350 on the fullstack jobs. |
| Progress meter | `progress_percent` emitted on whole-percent advance, independent of save points. |

**402 tests passing, 24 subtests, no regressions.**

## 2. Design decisions worth your review

These are the calls I made that a reasonable person could have made differently.

**Streaming, forward-only, with deferred emission.** Nothing holds a forward window.
Sections 4.7 and 4.16 park pending episodes and emit only when the horizon has elapsed in
stream time. A batch pass would compute complete outcomes for structures near the end of
the data — outcomes a live system could never have had — so never-restored stays distinct
from not-yet-observed, and each horizon carries its own at-risk denominator.

**Rules enforced as structure, not as discipline.** `StratumKey` makes pooling a key
collision rather than an oversight. `completed_duration_ns` raises before completion.
`RecognitionLabel` has no `supersedes` field. There is no method returning a bare
detection-time mean, and a test asserts none exists. Forbidden discovery features raise at
schema construction, before any data is seen.

**Two self-checking invariants in 4.6.** FIFO admits new orders only behind resting ones,
and every departure from ahead is a fill or a cancel. `cancels_ahead` is the residual of
that identity, declared as a residual, with both invariants asserted — so a non-FIFO event
surfaces as a recorded violation rather than a plausible number.

**Judgment calls with a defensible alternative:**

- Channel and component count live in `subfamily_id` rather than as new `StratumKey`
  fields. Keeps the shared identity type stable; costs some readability.
- Multi-channel groups are attributed to *each* channel they span rather than to a
  synthetic combined stratum. The alternative double-counts differently.
- Quantiles fall back to a bounded reservoir past a cap, declared in the row.
  `n`, `sum`, `min` and `max` are never approximated.
- 4.8 disposition order checks sparsity first, then withdrawal, then price movement.
  A different order would classify mixed runways differently.

## 3. Open decisions — these are yours

### D1. A-clean is not clean (Critical 1 from the review findings)

`A_CLEAN_POSITIVE_KNOWLEDGE_20260828.md` is `ALWAYS_LOAD` and contains derived results
about the held-out days: a cross-day imbalance comparison (0.221155 vs 0.121056),
per-held-out-day cancel-linked share (82.652%/82.495%), order `786260864394` with its
full lifecycle and 20,400 ns gap. Delivered at cutoff zero.

- **Option A** — strip the capsule to arm-invariant method rules (findings 1 and 6
  survive; 2–5 do not), re-hash, re-register. Keeps the experiment, loses the knowledge.
- **Option B** — rename the arms (`A_PRIOR_POSITIVE` vs `A_PRIOR_FULL_CHAIN`) and rewrite
  the Goal doc's contrast. Keeps the knowledge, changes the claim.

### D2. The arms differ in three ways, not one (Critical 2)

A-memory uniquely holds `a_memory_member_first_positive_findings` and
`a_memory_member_first_recalculation_receipt` — calculation outputs over the same four
files, not prior-run lessons. A-clean uniquely holds `a_clean_extraction_opportunities`
and `a_clean_positive_family_inventory`.

Proposed fix: define the retrieval catalog by **slot**, not by file; any slot one arm
cannot fill is empty in both.

### D3. The boss allowlist (Critical 4)

`EXPECTED_MODEL = "gpt-5.6-sol"` is a single-value constant enforced in three places, with
one OpenAI route. The Sol→Granite example in the Goal doc requires the source edit both
papers forbid. Needs `ALLOWED_BOSSES` before the boss-only-mutable design is real.

### D4. The stale execution gate (Critical 3)

`corrected_a_arm_execution_gate_20260828.py` pins 24 surfaces against the registry's 97
concrete layers, in a disjoint vocabulary, referenced by nothing but its own test.
Proposed: generate `SURFACE_IDS` from the registry, derive the mandatory set from the
`CAUSAL_STREAM_REQUIRED` policy, add a test asserting they cannot diverge, and wire the
gate into the launcher.

Counts, for the record: **93 inventory bullet layers + 4 helper roles = 97 concrete
layers; + 8 arm/control bindings = 105 registry entries; 90 is the declared floor.**

### D5. Clustering mode (4.15)

Built as an explicit declared parameter rather than a silent default. `mode` is
`INCREMENTAL` or `RETROSPECTIVE`, part of the hash-bound schema, travelling on every
assignment and summary row. **Which mode the A-arms run is still undecided.**

### D6. Session and phase boundaries

`session_phase` is still a caller-supplied string. Nothing in the tree defines RTH/ETH/
reopen for these October 2021 CME sessions, and §2 says session boundaries start new
continuity segments. Something must own that definition before a real run.

### D7. Provider invocation cadence

Still genuinely open, and the one item that cannot be closed from the repository. The
registry's `EACH_F_LAST_CUTOFF` is a policy on evidence *availability*, not an invocation
schedule.

### D8. Prior-memory package hash (Required 5)

The claimed package SHA-256 `0a5cddb…` does not reproduce from the committed files. Swept
45 tar/gzip variants; none match. `a_memory_prepare_20260828.py` hard-fails at line 93, so
**A-memory cannot be prepared as committed**. Either pin the packaging toolchain and
re-derive, or replace the tar digest with a toolchain-independent manifest-of-member-hashes.

## 4. Wiring not yet done

The calculation modules are built and tested but not yet connected to the replay driver.
Specifically:

1. A driver that walks `replay_dbn_files` and feeds each section from `V4MboAdapter` state.
2. `session_phase` and continuity-segment derivation (blocked on D6).
3. The `periodic_checkpointer` wired into that driver and into the launch workflows.
4. The execution gate re-pointed and wired (D4).

None of this is hard, and all of it depends on decisions above, which is why it stopped
here.

## 5. What the runner does not do, stated plainly

The eighth acceptance gate always passes and exists to record this: these artifacts are
calculation evidence. The runner performs no principal-model invocation, lock, freeze,
one-way handoff, reconciliation, or score, and claims none.
