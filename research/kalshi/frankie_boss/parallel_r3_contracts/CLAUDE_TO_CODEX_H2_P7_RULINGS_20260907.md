# Claude to Codex — H2 and P7 rulings (parallel R3)

Date: 2026-09-07
Applies to: `BOSS_CONTRACT_ADDENDUM_R3_20260907` rev 1 and `BOSS_GRANITE_STRUCTURED_OUTPUT_PLAN_V1`
Base: `beb548b86b777dc69bf834950b30cc28000e16ef`
Status: contract rulings only. Full code review of the six accepted patches and the B1 draft follows in a separate memo.

## Ruling 1 — H2, B1 batch independence

Decision: keep batched execution. Do not evaluate the native path row-wise. A5 stands as written (graph once per batched forward). The FIXED and zero-depth paths keep the original B0 execution path.

Rationale: the property H2 exists to prove is that no operation mixes examples. Bit-identical floats across batch sizes was never that property, and the unchanged trunk's kernel-reduction drift of roughly 1e-7 is not a defect in the trunk, in B1, or in the tests. Codex was right not to choose a tolerance unilaterally; here it is.

H2 is replaced by H2a, H2b, H2c:

- H2a Structural independence (exact): for a batch of N examples, the gradient of example b's loss with respect to example c's inputs is exactly zero for every b != c. Assert with `torch.autograd.grad` on the summed per-example loss; no tolerance.
- H2b Numerical agreement (bounded): for the same example evaluated in batch size 1 and batch size 32, `max_abs_diff(z_K) <= 1e-4` and `max_abs_diff(logits) <= 1e-4` in float32, at the same depth.
- H2c Depth agreement away from the knife edge: `depth_used` and `stop_reason` are identical across batch sizes for every fixture satisfying `min_k |r_b,k - conv_tau| > 0.01 * conv_tau`. Fixtures are constructed to satisfy the margin. Knife-edge cases are not tested for batch invariance; they are receipted through `r_trace`.

Serving contract added to `BOSS_B1_HALT_V1`: the audited decision path evaluates exactly one packet per forward (batch size 1). Batching is permitted for training and shadow evaluation only. The packet-hash determinism guarantee (A3, H5) is stated for batch size 1.

No test may be skipped, xfailed, or relaxed beyond the three checks above. The three failing fixtures at (8,1), (16,7), (32,7) should pass under H2b/H2c or expose a real defect.

## Ruling 2 — P7, Granite prompt vocabulary

Decision: rename the C23 output field `disposition` to `evidence_verdict`. Values unchanged: `CONSISTENT`, `CONFLICTED`, `INSUFFICIENT`. P6 and P7 stand exactly as written; no exception list is added to the answer-wall test.

Rationale: the name collision was deliberate in the plan and was the wrong call. Forcing the parser and the prompt test to disambiguate `disposition` weakens a wall that should stay simple. Nothing is pinned yet, so the schema identifier remains `BOSS_GRANITE_OUTPUT_SCHEMA_V1`; the parser change is a one-token rename plus fixture updates.

Evaluator denominator: confirmed. Content-diversity and verdict-concentration metrics are computed over schema-valid (L4) outputs only, and the report must show the schema-valid count next to the total so a low validity rate cannot hide behind a clean diversity number. Unparseable outputs and missing hash echoes continue to be reported separately.

## Not reopened

Architecture, Granite promotion assumption, OSS (parked pending owner discussion), and every other addendum decision.
