# H2/P7 implementation and Claude review package

Update: read `R3_REVIEW_CORRECTIONS_20260907.md` for the completed full review,
R1/R2 corrections, and current 49 B1 / 55 prompt checks. Details below record
the original c0716cc7 review submission.

Owner: Greg Davis. Date: 2026-09-07.
Repository: DavisAI1974/Markets.
Branch: `codex/boss-h2-p7-rulings-20260907` (local; not pushed).
Starting accepted review tip: `9c80afb2ca32e0ccdfe015d78fc32c23a7e4767f`.
Original repository base: `beb548b86b777dc69bf834950b30cc28000e16ef`.

## Read order and authority

1. `parallel_r3_contracts/CLAUDE_TO_CODEX_H2_P7_RULINGS_20260907.md`.
2. The corrected rev-1 addendum and Granite structured-output plan in that
   directory, read with those later rulings applied.
3. This implementation note and the changed component files/tests.

Original contract-source bytes are preserved. The later ruling overrides H2,
adds the batch-one serving contract, renames C23's field, and fixes the content
metric denominator to L4. Old review memos describe the historical blockers;
they are not current status. Claude's separate full review memo was not supplied.

## Implemented

- `9decb7b6`: B1 recurrence/halting is now batched, including cell and heads.
  Graph executes once per forward. FIXED and zero-depth retain the original B0
  execution path. `forward_decision` rejects batches in every supplied tensor;
  ordinary `forward` remains available for training and shadow batches. Future
  audited serving must call `forward_decision`; no existing runner is rewired.
- H2a checks exact zero cross-example gradients. H2b uses only the authorized
  float32 maximum absolute bound of 1e-4. H2c asserts the actual fixture traces
  have the required 1% threshold margin before comparing depth and stop reason.
  Both convergence and maximum-depth fixtures are covered. All three original
  regression dimensions (8,1), (16,7), (32,7) are retained. No skips or xfails.
  Packet-hash determinism A3/H5 is checked at batch size one.
- `e254a96e`: C23 requires `evidence_verdict`; enum values and schema identifier
  are unchanged. The old `disposition` key is rejected. Evaluation content and
  verdict concentration count L4 outputs only. `schema_valid_count` now means
  L4 count, with `sample_count` retained beside the model metrics. Malformed and
  missing echoes remain separately reported.
- `a2f2aa60`: `granite_prompt.build_prompt(SerializedState)` adds a fixed,
  model-neutral system instruction, exact canonical state bytes, snapshot hash,
  and system-prompt hash. The full prompt has no BLD-1 vocabulary exceptions.
  Contaminated or noncanonical inputs fail closed instead of being rewritten.
  Existing `ablate_market_fields` output works without serializer changes.

## Verification and review

Final focused results, each with exit 0:

| Scope | Passed |
|---|---:|
| B1 recurrence, H2/H5 and serving guard | 47 |
| Granite parser/schema and evaluator | 126 |
| Granite prompt and answer wall | 46 |

These are separate focused results, not a full-suite claim. No repeated broad
suite, provider call, market-data run, training job, or A/B experiment ran.
Real Torch 2.5.1+cpu executed synthetic forward/backward checks. This session's
missing pytest runner was installed only in isolated scratch, with no repository
dependency changes. H2 tests first exposed the old rowwise calls and missing
serving entry. Review then reproduced metadata broadcasting past the initial
batch guard; the final guard rejects it and its regression passes.

A separate read-only reviewer approved the final changes subject to the final
B1 check; that final check passed. It ran no independent tests. Existing Frankie
inputs, calculations, planes, adapters, replay, teachers, trunk, and Memory A
artifacts are unchanged. The four requested reference files are copied directly
from the pinned repository and hash-bound in the delivery manifest:
`trunk.py`, `causal_packet.py`, `state_serialization.py`, `frankie_contract.py`.
They are reference copies, not patches.

## What remains

C19/C20's pure component implementation is complete; production attachment and
preservation proofs remain open. C23's pure parser, prompt builder, and supplied-
output evaluator are complete. Granite runtime/fusion, identity pinning, GPU
training and promotion remain unfinished. C15 stays Partial: observer, full
19-column builder, and checkpoint integration are still outside this tranche's
authorization. OSS remains parked. No live authority or production readiness is
claimed from synthetic component tests.

The prompt wall is lexical, not proof of upstream causal source selection.
The evaluator's hash inventory cannot establish chronological separation.
B1 trusts the caller's upstream packet identity. Those existing responsibilities
must be enforced at the future integration boundary.

## Reproduction and transfer

Run the three focused test files/groups using pytest with the repository root
and `research/kalshi/frankie_boss` on PYTHONPATH, and a healthy Torch runtime.
The delivered patches apply in numeric order to the original base. The Git
bundle requires that base history. The manifest records the exact final tip,
per-file SHA-256 values, and the requested reference blob identities. The
workbook records these completions while keeping integration gates open.
