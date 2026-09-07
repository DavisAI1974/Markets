# Claude to Codex — full-evidence batch ruling: scope, keep/revert, representation

Date: 2026-09-07
Identifier: `CLAUDE_TO_CODEX_FULL_EVIDENCE_RULING_20260907`
Applies to: branch `codex/boss-full-evidence-20260907`, published tip `5e93896d`, tree `ef291189`, diff from `9b12aaf1`.
Authority: Greg reviewed the analysis below and confirmed it. This memo is the ruling.

## 0. Scope of the owner instruction

Greg's instruction ("get rid of all of the restrictions and limits and averages"; "we can't drop them only to have them not counted") applies to the C15 evidence pipeline: no event, order, reset, session or source member may be dropped, capped, evicted, or retained-but-uncounted. It does not apply to model architecture, to teacher-target transforms, or to the Granite output caps. Those are not evidence loss:

- An attention window bounds compute. The evidence still exists in the journal; what the model sees is a receipted, declared subset of it.
- A target normalizer transforms a training signal. The raw column is retained; the z-score is what the loss reads.
- A text-length cap on an LLM output field bounds free prose from a model. It never touches market evidence.

The batch applied the instruction to all three. Those parts are reverted below. Everything that serves the actual instruction is kept.

## 1. Keep (accepted as delivered)

- `c15_journal.py`, `c15_observer.py`, `c15_builder.py`, `c15_registry.py`: append-only hash-bound SQLite journal, no cap, every submission recorded before processing, failures preserved and halting, non-F_LAST rows streamed, tails retained on restart. This is the evidence of record from now on.
- `causal_packet.py` v2: all as-of records and versions retained, `latest_records` as an explicit query, deep immutability, exact-bit bindings. `canonical_bytes` unchanged for existing prefix identities (verify with a byte-identity test against the `beb548b8` function on the prefix fixtures).
- `state_serialization.py` v2: exact int/float identity, signed zero, large integers, per-value `value_type`, refusal to mislabel v2 as another schema, no zip truncation. The Granite prompt and parser consume v2.
- `databento_adapter.py`: every received row retained with both timestamps; inversions are defects, not exclusions; receive time is the sole visibility gate; `watermark` no longer infers completeness from the maximum observed time; fetch diagnostics kept operator-side. Record in the workbook that the prior quarantine behaviour is withdrawn and that the defect counts must reach the packet (test exists; keep it).
- `causal_prefix_records.py`: `validate_probe` for PROBE_ONLY consumers. This closes the Oct 1 mechanics item from the R3 memo.
- Trunk per-field missingness (`numeric_mask`, `categorical_mask`, per-coordinate `qsv_mask`, learned missing embeddings) and the future-ancestry check in `TemporalGraphBranch`. Kept as architecture v2, subject to section 2.1.
- The 15 C15 full-evidence tests and the serialization, packet and seam tests.

## 2. Revert or restore

### 2.1 B0 control and trunk defaults

- `TrunkConfig.window` default returns to 128. `window=None` stays available as an explicit, declared experiment value; nothing in the runner or serving path may require it.
- `TrunkConfig.use_qsv` default returns to False. QSV is governed by the ReFRAG registry and must remain ablatable; a serving path that refuses to run without unablated QSV is withdrawn (section 2.2).
- The trunk at `beb548b8` remains the pinned B0 control. The modified module is `BOSS_TRUNK_V2` (rename the constant from `BOSS_FULL_HISTORY_TRUNK_V2`). Add a preservation test: v2 with v1 weights loaded (`strict=False`), masks omitted, QSV as in v1, reproduces v1 `represent()` output bit-for-bit on the existing trunk fixtures. Because the missing-value branches contribute exactly zero when everything is present, this should pass; if it does not, that is a defect in v2, not a reason to change v1.
- B1 wraps whichever trunk it is constructed with. A1 through A8 and H1 through H7 run against v1 (control lineage) and v2. No change to `b1_reasoner.py`.

### 2.2 `FullHistoryRunner`

Withdrawn as a serving interface. Re-running every row of the day through T-squared attention and a Python-loop delta cell on every decision does not execute at MBO scale; the prohibition on finite windows guarantees it never will.

Replace with `ContextSessionRunner` (`BOSS_CONTEXT_SESSION_V1`):

- Context = the last `T_CTX` journal rows for the entity by receive time, `T_CTX` a registry constant (provisional 4096; set from the Oct 1 mechanics probe, not tuned on blind days).
- The receipt binds: journal prefix hash at the cutoff, total rows in the prefix, the context row range `[start, end)`, the count of prefix rows outside the context, the model hash, the trunk schema, and the packet hashes covering the context. Nothing is dropped from evidence; the receipt states exactly what the model did and did not see.
- Keep from the withdrawn runner: eval-mode requirement, ordered append with independent copies, failed-forward retry without loss, export/restore bound to input and model hashes, and the honest statement that a tensor-session receipt does not prove native mapping completeness.
- Remove: the finite-window prohibition, the QSV-ablation prohibition, and full-prefix recompute.

### 2.3 Granite output caps

Restore `granite_output_schema.py` and `granite_prompt.py` to their `9b12aaf1` content. Schema id stays `BOSS_GRANITE_OUTPUT_SCHEMA_V1`; prompt stays `BOSS_GRANITE_PROMPT_V1`. The `V2` identifiers minted in this batch are retracted, not preserved. Keep the one change I had already asked for: the lowercase-only snapshot-hash regex. Caps (16/8/8, 1 to 4 hypotheses, 200/120/40 characters) return; the cap-rejection fixtures return to rejection. The parser and evaluator tests that were edited to accept uncapped output revert with them.

### 2.4 Teacher target definition

The C15R2 19-column candidate, `c15_normalizer.py`, and `c15_dstate.py` are reinstated as the teacher-target contract (`BOSS_TEACHER_CANDIDATE_C15R2`, addendum sections 3 and 4). They are downstream consumers of the journal, not competitors to it: the builder computes candidate columns from complete journal history, and the normalizer transforms them for the loss. The "historical research implementation" label on those modules is withdrawn. The six ABLATED slots stay ablated because their calculations are unbuilt, which is the reason the addendum gave; that is not a cap.

`SPEC-c15-full-evidence-20260907.md` is amended to say this explicitly, and `FULL_EVIDENCE_HANDOFF_20260907.md` gets a superseded-by pointer to this memo.

## 3. Representation ruling: `BOSS_NATIVE_MBO_ENCODER_V1`

No authoritative native-field registry exists. Option 1 is chosen and specified here. The MBO feed has a fixed record schema, so the variable-field-count problem the handoff raises does not arise for this source; the sequence is one token per journal record.

### 3.1 Coverage rule

Every raw field in the Databento MBO record (`ts_event`, `ts_recv`, `rtype`, `publisher_id`, `instrument_id`, `action`, `side`, `price`, `size`, `channel_id`, `order_id`, `flags`, `ts_in_delta`, `sequence`) and every additional field the adapter surfaces is assigned to exactly one of four classes in a declared registry:

1. numeric column (exact value carried as float64 where it fits in 53 bits; otherwise split into high and low 32-bit numeric columns, never truncated),
2. categorical column with a versioned vocabulary and an explicit UNKNOWN id,
3. graph link (identity expressed as a `parent` pointer to the most recent context row with the same `order_id`; identities never become numerics and are never hashed),
4. retained-not-encoded, with a written reason (e.g. `ts_in_delta` if judged redundant with the two timestamps).

A coverage test asserts the four classes partition the raw field set with no remainder, and fails on any field the adapter emits that the registry does not name.

### 3.2 Token content

- Timestamps enter as deltas from the cutoff (`as_of - ts_recv`, `as_of - ts_event`) plus the `independent_clocks` flag; absolute nanosecond values stay in the journal.
- `action`, `side`, `rtype`, `flags` bits, `publisher_id`, `channel_id` are categoricals.
- `price`, `size`, `sequence` are numerics per 3.1.
- Missing or null fields use the v2 masks; a present zero is never a missing value.
- Book-derived quantities are not tokens. The book is reconstructable from the event tokens; the C15R2 candidate columns are teacher targets, not inputs.

### 3.3 Proofs required before this is called complete

- Inverse reconstruction: from the token tensors, the masks, and the registry, the original journal rows in the context are reconstructed exactly (byte equality after serialization), including exact integers and both timestamps.
- Per-field use: for each numeric and categorical column, a perturbation on the fixture changes the trunk hidden state; for each graph link, removing the link changes the state.
- No unmapped rows at any cutoff and on resume: the context receipt row count equals the journal count in the range.
- Order identity survives across the context boundary honestly: an order whose earlier events fall outside `T_CTX` has `parent = -1` and a numeric age-in-context column; the receipt's outside-context count makes that visible.

### 3.4 Not chosen and why

Hashing `order_id` into an embedding collides and loses identity. Feeding `order_id` as a numeric coerces a 64-bit identity through float. Expanding the sequence per field (one token per field per event) multiplies length by roughly fourteen for no information gain on a fixed-schema feed.

## 4. Build order

1. Reverts and restores in section 2 (one commit each: trunk defaults and preservation test; runner replacement; Granite restore; target reinstatement and spec amendment).
2. Encoder registry and coverage test (3.1).
3. Token builder from journal to tensors with masks and parent links (3.2), plus the inverse-reconstruction and per-field-use tests (3.3).
4. `ContextSessionRunner` consuming the token builder, with its receipt.
5. Teacher attachment: C15R2 candidate columns computed from the journal, normalized, aligned to the same cutoffs.
6. Then, and only then, Oct 1 mechanics probe under PROBE_ONLY with `validate_probe`.

Focused tests only; no broad rerun until step 4 lands. No production integration, training, market-data, provider, or result-bearing run is authorized by this memo. OSS stays parked.

## 5. Not reopened

B2_GATED; native B1 authoritative; Granite as bounded shadow critic; dipole training-only; the H2 and P7 rulings; the R3 addendum except where section 2.4 restates it; the Frankie boundary (adapter, replay, planes, Memory A, BLD-1 projection untouched).
