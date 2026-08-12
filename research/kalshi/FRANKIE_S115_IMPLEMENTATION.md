# Frankie S115 Implementation

This is the implementation record for `FRANKIE_BUILD_BRIEF_S115.md`. The registry remains truth;
this document distinguishes **built contract** from **measured evidence** so an implemented gate is
never mistaken for a passed experiment.

## Sequence now enforced

1. M-16 / A-61 / A-50
2. A-66 ownership
3. A-59 / A-68 / A-62
4. A-65
5. A-67 arm 1 / A-69
6. A-67 arm 2 / A-42
7. later only: A-5 + A-63 + A-60

A-63/A-60 are deliberately NOT pulled forward. The S115 brief says they are one later build and
require A-5's library index first.

## Built

### M-16 guarded Databento entry

`databento_backfill_s115.py`

- resolves all S115 destinations from the repository root, never the caller's cwd;
- defaults NG trades to `data/nymex_cont_n0`, MBP-10 to `data/nymex_mbp10`, L1 to `data/ng_l1`;
- defaults the S115 NG continuous roll to `n` rather than silently selecting `v`;
- rebinds the historical writer globals before decoding, which closes the legacy trades writer's
  ignored-`out_dir` path for guarded runs;
- snapshots destination byte sizes before and after the pull;
- hard-fails if rows are reported and no destination bytes grow;
- prints the ACTUAL verified destination, never merely the requested one.

The historical `databento_backfill.py` remains untouched for reproducibility. S115+ operational pulls
must use the guarded entry point. This is deliberate rather than pretending an unreviewed rewrite of
that long-lived decoder is safer.

### A-61 pinned verification snapshot

`frankie_s115.pin_snapshot()` / `verify_snapshot()` hash the exact files a verification reads and
hard-fail if one changes beneath the verifier.

### A-50 narrative leak adjunct

`assert_no_narrative_leak()` is a deterministic deny gate for known outcome language in automatically
loaded narrative files. It supplements, and does not replace, the existing `brain_view` leak wall.
A-67 also carries a `narrative_locked_until_both_complete` seal.

### A-66 ownership

`frankie_s115.OWNERSHIP` encodes PART ownership, not coarse layer ownership:

- D8 merge -> `memory/content_store`
- A-62 -> `memory/derived_track_record_index`
- A-65 -> `memory/serving_policy`
- A-68 -> `memory/within_run_lens_journal`
- A-59 -> `scaffold/render_and_typed_contract`
- A-64 -> `control_logic/candidate_branching`

Sharing a layer is legal. Same-part ownership is a hard failure. Protocol/arbitration is not invented
until a true same-part overlap survives finer decomposition.

### A-59 NOOA render target and typed write

`frankie_render_s115.py`

`FrankieAgentObject` holds explicit state and renders directly from the existing canonical
`spawn.templates()` and `spawn.slots()` machinery. The substitution rule intentionally matches
`spawn.py`: only known slots are replaced; conditional braces remain literal.

`assert_byte_identical()` compares Frankie's render bytes with the canonical render semantics.

`TypedPosterior.from_mapping()` rejects malformed/underspecified writes and any attempt to enable
execution before a coordinator can consume the output.

`frankie_forecaster_s115.py` composes that with the S115 attachments while leaving the canonical
prompt bytes unchanged.

### A-68 lens book

Each specialist gets an append-only JSONL book. Entries are written at that lens's decision point.
`causal_lens_view()` serves only STRICTLY EARLIER days. Current/future rows are absent, not hidden by
instruction. The book records this lens's own carried state and actions; it is not general doctrine
and does not write the brain.

### A-62 specialist track records

`build_specialist_track_records()` creates a GENERATED index from posteriors + actuals. It records
failure mechanism and correction mechanism, not score alone. The payload marks `generated=true` and
`authored=false`; authored priors are refused.

### A-65 validated compaction

`validate_compaction()` compares same-cell full-view and changed-view posteriors on the registered
load-bearing fields: direction, magnitude, fired set and stood-down set.

- any movement -> `REJECT_VIEW_CHANGE`
- no movement on an independently believed lossy change -> `TEST_INSENSITIVE`
- otherwise -> `VALIDATED_FOR_THIS_CELL_ONLY`

There is no global compaction blessing.

### A-67 architecture A/B contract

`frankie_validation_s115.py`

The common staged substrate can be sealed before either arm. Namespaces must differ and must be
non-canonical. Metrics are fixed in the seal before the run:

- per-event absolute error;
- the three registered benchmarks: zero-change, seasonal-naive, persistence;
- emission ratio;
- band coverage;
- stand-down honesty;
- derived-vs-fitted quantity provenance.

`compare_arms()` refuses differing event sets/cells and returns no pooled scalar.

### A-69 self-training and A-42/FJ-1

`TrainingSplit.validate()` requires the blind wall up and strict train/head disjointness.

`grade_fj1()` validates edge + fault side + mode against `failure_localization.py`'s frozen paper
modes plus declared local extensions. Frankie cannot invent a self-serving category.

`training_release_gate()` reports corpus and held-out results together. A corpus gain without a
held-out gain is explicitly `SCRAP_RECALL_OR_OVERFIT`.

## Not claimed as passed

The following are experiments/data operations, not code-completion claims:

1. M-16 still requires the real EC2/data-plane repair action: move or free re-decode the already-paid
   head/L1 Databento jobs into the verified root destinations, then run the guarded landing check.
2. g6-g16 actuals still require a measured rebuild where absent, using the basis each STATE was built
   on. Do not silently normalize all old blocks to one continuous basis.
3. A-67 arm 1 has NOT been run on the held-out head by this branch.
4. A-69 has NOT been trained/scored on the reconstructed walked corpus by this branch.
5. A-67 arm 2 retention has NOT run across three sequential held-out blocks.
6. A-42's adapter is wired, but the first production FJ-1 grading run remains evidence to collect.

## Commands

```bash
# status without pretending missing evidence is ready
python research/kalshi/frankie_s115_status.py

# S115+ Databento pull: cwd-independent, landing asserted
python research/kalshi/databento_backfill_s115.py pull \
  --symbol NG --roll n --schema trades --start YYYY-MM-DD --end YYYY-MM-DD

# prepare a specialist object while proving canonical render-byte identity
cd research/kalshi
python frankie_forecaster_s115.py prepare-day BLD-1 g24 20260720 B

# after the blind decision, validate + record posterior and append this lens's causal book
python frankie_forecaster_s115.py record-day posterior.json --carried-state carried_state.json
```

## Core invariants preserved

- `spawn.py` remains untouched and pinned by Frankie CI.
- the blind engine remains the core predictor; Frankie extends it.
- no direct brain edits;
- no pooled above/below metrics;
- future information is absent from causal views;
- absence must announce itself;
- no general lesson enters the blind through the lens book;
- no execution authority exists in Frankie;
- no A-63/A-60 fitted-sigma shortcut is introduced.
