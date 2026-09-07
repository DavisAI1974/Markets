# Claude to Codex — parallel R3 batch review memo

Date: 2026-09-07
Applies to: package `Frankie_BOSS_H2_P7_Claude_Package_20260907` (branch `codex/boss-h2-p7-rulings-20260907`, tip `c0716cc7`, base `beb548b8`), patches 0001 through 0010.
Supersedes: the "full code review follows" note in `CLAUDE_TO_CODEX_H2_P7_RULINGS_20260907.md`.
Status: review complete. Two required corrections before push, both small. No architecture, contract, or ruling is reopened.

## 0. What was reviewed and how

All ten patches were read against the pinned base, using the four reference files (`trunk.py`, `causal_packet.py`, `state_serialization.py`, `frankie_contract.py`) at `beb548b8`. Package checksums in `BATCH_MANIFEST.json` all verify. The rulings copy inside the package is byte-identical to the issued ruling.

Every accepted patch adds new files only. No existing Frankie module is touched by any patch; the reference files are unchanged at the final tip. The Frankie boundary holds.

This was a static review. Torch was not available in my review environment, so the 47/126/46 focused results are Codex's evidence, not independently reproduced here. Nothing below depends on rerunning them.

## 1. Verdicts by slice

| Slice | Patches | Verdict |
|---|---|---|
| Prefix (patch 0005 plus three review fixes) | 0001 | Accept. The three fixes (immutable action mapping, restore fail-closed on impossible histories, strict 64-hex) are correct and complete. |
| Normalizer | 0002 | Accept. Contract sections 3.2 through 3.7 are implemented as written; floor table matches section 3.4 column by column. |
| D-state | 0003 | Accept. Section 4.1 rules 4/5/6 and the T-D trace are reproduced exactly. One integration decision flagged in section 4 below. |
| Granite schema and parser | 0004, 0008 | Accept. `evidence_verdict` rename applied; reward ladder matches plan section 2; `training_score is runtime_score` holds. |
| Granite evaluator | 0005, 0008 | Accept. L4 denominator applied per ruling; `sample_count` sits beside the model metrics. |
| Docs and contracts | 0006, 0010 | Accept. |
| B1 recurrence and halting | 0007 | Accept with one required test addition (R1). Code matches sections 1 and 2 and the H2 ruling. |
| Granite prompt builder | 0009 | Accept with one required fix (R2). The answer wall is currently over-broad and will reject legitimate states. |

## 2. Required corrections (before push)

### R1 — H2c is exercised only at the two trivial extremes

`test_h2b_h2c_convergence_batch_independence` runs `conv_tau` in {1e-3, 10.0}. At 10.0 every example converges at step 1; at 1e-3 on a freshly initialised cell every example runs to `k_max`. The review-regression test uses the default 1e-3 with `k_max=2`, so it also lands on MAX_DEPTH. No fixture stops at an intermediate depth, which is the only place batch composition could plausibly move `depth_used`.

Add one fixture where the batch-one example converges at an interior step: run the batch-one forward once with `conv_tau=0` and `k_max=8` to obtain `r_trace`, pick two consecutive ratios `r_j > r_{j+1}` from the interior, set `conv_tau` to their geometric mean, and assert the existing `assert_h2_agreement` at batch 32. The 1 percent margin assertion already in `assert_h2_agreement` guards the knife edge; if the chosen trace has no interior pair with sufficient separation, the fixture fails loudly rather than silently degenerating.

While there: lines 167 and 168 of `test_b1_reasoner.py` (`h0`, `h0_single`) are dead assignments left from the old failure demonstration. Remove them.

### R2 — P7 wall uses substring matching and rejects innocent states

`granite_prompt.build_prompt` checks `name in value.lower()` for every `BLD1_FIELD_NAMES` entry against the whole prompt text and every decoded state string. Two of those names are common English substrings: `date` matches `update`, `updated`, `consolidated`, `validated`; `group` matches `group_count`, `n_groups`, `groups_log`. A serialized state whose numeric field is named `book_update_count`, or whose `source_versions` carries a key like `consolidated_feed`, is rejected today. The C15 candidate slots `unresolved_age_groups_log` and `step_duration_groups_log` also contain `group`; they are training-only and should never reach a prompt, but the rule as written would misreport that as a BLD-1 leak rather than a scope violation.

The ruling said P6 and P7 stand with no exception list. Exact-name matching is not an exception; it is what "no BLD-1 field name" means. Replace the substring test with:

- Tokenise the lowercased text into identifiers with `[a-z0-9_]+`.
- For a BLD-1 name containing no underscore (`specialist`, `group`, `date`, `reasoning`, `confidence`, `disposition`): reject on exact identifier equality.
- For a BLD-1 name containing an underscore (`guessed_net_usd`, `overnight_gap_usd`, `path_p50_curve`, `plays_fired`, `plays_stood_down`, `state_defects_and_gaps_reported`): keep substring matching; these are specific enough that over-breadth is not a concern and it catches prefixed or suffixed variants.

Apply the same rule to `prompt.text` and to the decoded source strings, as now. The existing `test_p7_no_exception_for_any_bld1_name_anywhere` (all twelve names in three locations) and the line-25 assertion in `test_p7_exact_state_bytes_hash_and_fixed_system_instruction` continue to pass unchanged. Add two regressions: a numeric field named `book_update_count` and a `source_versions` key `consolidated_feed` both build successfully; a numeric field named `date` still fails.

The separate `target/label/outcome` check already tokenises on `[a-z]+` and is fine as is.

## 3. Non-blocking corrections (fold into the next touch of each file)

- **B1 `forward_decision`, eval-mode guard.** A3/H5 determinism is stated for eval mode. The trunk has no dropout today, so nothing breaks, but `if self.training: raise ValueError("audited decision requires eval mode")` makes the serving contract self-enforcing at zero cost. Add it with a one-line test.
- **Schema hash case.** `granite_output_schema` accepts `[0-9a-fA-F]{64}` for `snapshot_hash`; `b1_reasoner` (`packet_hash`), `granite_evaluation` (training hashes), and `SerializedState.hash` itself are all lowercase-only. An uppercase echo can never be L4, so this only moves an output from L2 to L3. Change the schema regex to `[0-9a-f]{64}` for consistency across the batch.
- **`ModelMetrics.schema_valid_count` is identical to `l4_count`.** Under the ruling the content denominator is the L4 count, so the field is redundant and its name suggests a looser set than it holds. Either drop it or rename it `content_denominator_count`. The ruling's intent (denominator shown next to total) is already satisfied by `l4_count` and `sample_count`.
- **Parser cost under GRPO.** `score()` re-parses and re-serialises the snapshot on every call and rebuilds the row/field map. In training that is eight calls per prompt per step. When the GRPO runner (plan step 4) lands, add a `SnapshotIndex` built once per prompt (canonical check plus field map) and let `score` accept either a `SerializedState` or the index. Do not change the ladder.
- **Normalizer transform cost.** `statistics.median` copies and sorts the 4096-value window twice per `transform`. At Oct 1 scale (13 active columns times instruments times cutoffs) this may be minutes, not seconds. Measure on the first mechanics pass before touching it; a sorted-container window or `numpy.partition` is the fix if it matters.
- **D-state D3 degenerate branch.** `m_prev == 0` cannot occur: `m_last = x - E` with `x > E` strictly, so `m_prev` is always positive. The INVALID `DEGENERATE_STEP` branch is dead. Harmless; leave it or delete it when the file is next edited.

## 4. Integration boundary items (decisions, not defects)

- **D-state receipt consumer is RESULT_BEARING-only.** `ReceiptDChain.advance` calls `RecordPrefixChain.validate_result_bearing`, which rejects any PROBE_ONLY scope. The Oct 1 mechanics phase is PROBE_ONLY (section 3.5), and that is where the floor-binding fractions and D-column availability get reported before lock. As delivered, Oct 1 must run through `advance_synthetic` with no receipt binding. When L-INT opens, give `ReceiptDChain` a PROBE_ONLY consumer that binds the PROBE_ONLY reference chain's receipt from `causal_prefix.py`, so the mechanics probe carries prefix identity too. Not part of this batch; record it against C15 in the workbook.
- **Valid-token mask reaches halting only.** `valid_mask` gates the convergence norm but not the reasoning cell's attention, matching the trunk, which also attends over padded positions. Consistent with sections 1 and 2 as written. The production input builder (C06) owns padding semantics; note it there so nobody later reads B1 as masking padding.
- **Prefix hex normalisation.** `_require_sha256_hex` accepts uppercase and returns lowercase. All comparisons happen after normalisation, so no verification is weakened. Acceptable; noting it so the "exactly 64 ASCII hexadecimal characters" wording in the review memo is read as case-insensitive.

## 5. Confirmed as correct (for the record)

- B1: transition matches section 1.3 line for line; `TemporalGraphBranch` applied once; `GatedDeltaCell` state local per step; no detach or no_grad in the loop; `n_params_core` includes the trunk per rev-1 A2 and is independent of `k_max`; `e_step` is exactly `k_max x d_model`; frozen rows are masked after the batched cell per section 2.4; `stop_reason` semantics and `r_trace` per section 2.6; `convergence_halt` signature per H6; `forward_decision` rejects any tensor with leading dimension other than 1, including broadcast metadata; A3/H5 tested at batch size 1 per the ruling.
- H2a, H2b, H2c implemented as ruled: exact zero cross-example gradient via `autograd.grad`; 1e-4 float32 bound on `z_K` and every head; margin check on both traces before comparing depth and stop reason; the three original fixtures retained; no skips or xfails.
- Granite: seven required keys, `evidence_verdict` enum, caps 16/8/8/1-4, per-ref row and field resolution against metadata plus numeric plus categorical names; duplicate keys, non-finite numbers, boolean row indices, and wrapped JSON rejected; `SCHEMA_VERSION` unchanged at `BOSS_GRANITE_OUTPUT_SCHEMA_V1` per the ruling; P8 signature check present; prompt includes the exact serialised bytes and the snapshot hash; system prompt hash exposed for G16.
- Evaluator: exactly 200 unique identities, declared training-hash disjointness, equal positive token budgets, finite positive decode times; gates 1 through 4 implemented with inclusive integer boundaries; unverified echoes reported separately from mismatches.
- Normalizer: exclusive window, 256-PRESENT warmup per (instrument, column), floors per section 3.4, six ABLATED slots hold no state, FROZEN skips update, restore verifies config, mode, window counts, float64/hex agreement, and the caller-supplied state hash; `normalizer_id` carries the state hash only when FROZEN.
- D-state: exact rational tick arithmetic; undefined anchor freezes; tick-unknown and book-integrity failures do not mutate geometry; source-member and session boundaries reset; ordinals must advance by one; receipt binding checks scope, instrument, publisher, and last-receipt identity.

## 6. Disposition

Apply R1 and R2, rerun the two affected focused files (`test_b1_reasoner.py`, `test_granite_prompt.py`), and the batch is cleared to push as `codex/boss-parallel-r3-20260907` or whatever name Greg prefers. No broad rerun is requested. Non-blocking items go in the workbook against their components and get picked up on the next touch.

Not reopened: architecture, Granite promotion assumption, OSS (parked), the H2 and P7 rulings, and every other addendum decision.
