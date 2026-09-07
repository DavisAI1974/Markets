# Parallel BOSS foundations — 2026-09-07

## Current owner correction — complete evidence

Greg superseded the C15R2 reduction choices after this batch's clearance:
no silent data loss, no history caps, top-three selection, normalization,
clipping, averages/smoothing, warmup suppression or truncated geometry in the
new C15 path. Preserving an archive without delivering/using the evidence is
not sufficient. See `SPEC-c15-full-evidence-20260907.md` and the full-evidence
handoff/audit for current acceptance and remaining model-consumption work.

The 19-column C15R2 builder direction, normalizer and D-summary below are
historical research contracts, not the current integration plan. The original
Claude documents remain intact as provenance. No Frankie input, calculation,
adapter or replay implementation was changed by this correction. OSS remains
deferred until the end of the build.

Base: `beb548b86b777dc69bf834950b30cc28000e16ef`.
Contract: `parallel_r3_contracts/CLAUDE_BOSS_CONTRACT_ADDENDUM_R3_20260907.md`, rev 1.

The user authorized concurrent implementation after Claude resolved the shared
contracts. Each lane owns new files in a separate worktree. No existing Frankie
input, calculation, plane, adapter, replay, Memory A artifact, or last-run
behavior may change. No provider, market-data, training, or AWS run is part of
this tranche. Unit tests use synthetic examples and real Torch where needed.

The repository's older `tasks/plan.md` concerns other unfinished work and is
preserved. This scoped plan records this tranche only.

## Lanes and acceptance

- [x] Prefix: apply Claude patch 0005 to the four preserved additive files;
  reproduce tests, close fresh adversarial findings, and commit before L-D.
  Commit `17e4b46a`; independent review approved. 70 prefix tests; complete
  BOSS suite 309 passed and one existing CUDA skip across two fresh processes.
- [x] L-B1: completed under Claude H2 ruling (2026-09-07). Batched execution,
  exact cross-example gradient independence, 1e-4 float32 bound, and explicit
  margin/depth agreement. All three original fixtures retained. 49 passed;
  single-packet audited decision entry rejects metadata batch broadcasting.
  Verify A1-A8 and H1-H7,
  actual gradients, unchanged B0, graph once, frozen examples, and receipts.
  Own `b1_reasoner.py`, `tests/test_b1_reasoner.py`.
- [x] L-NORM: exclusive-window median/MAD normalizer and tests. N1-N8 passed;
  60 new tests, independent review approved, lane commit `26ad8529`. Verify
  explicit freeze, strict restore, immutable frozen statistics, bounded state.
  Own `c15_normalizer.py`, `tests/test_c15_normalizer.py`.
- [x] L-D: after prefix commit, D1-D6 pure state machine and tests. 37 new
  tests, independent review approved. Verified
  T-A through T-D, causal receipt consumption, reset/freeze/break semantics.
  Own `c15_dstate.py`, `tests/test_c15_dstate.py`. C1 implementation deferred.
- [x] Review each new lane independently, fix required findings, commit accepted
  slices locally, and assemble separately reviewable patches for Claude.

## Added by the owner's Granite plan during this tranche

- [x] L-GRANITE parser: exact output schema, deterministic L0-L4 reward, one
  runtime/training scoring authority, and snapshot-reference validation.
- [x] L-GRANITE evaluator: pure paired-output pass/fail metrics under the
  supplied fixed format/content/latency gates. No generation or training.
- [x] Prompt builder completed under Claude P7 ruling: output field renamed
  to `evidence_verdict`; no BLD-1 exception list. Canonical state text is included
  byte-for-byte. 55 focused checks pass. Parser/evaluator: 126 pass with L4-only
  content and verdict denominators, valid and total counts both reported.
  A matching snapshot hash binds output to a snapshot; it does not itself
  prove the input snapshot excludes answer/outcome content.

## Deferred boundary

Observer, replay wiring, full 19-column builder, and checkpoint integration
remain outside this tranche. Granite runtime/fusion and experiment
orchestration are not implemented. Pure parser/evaluator additions come only
from the separately supplied Granite plan. C15 remains Partial;
component tests do not establish production integration or market benefit.
No push is authorized by this tranche's supplied review instructions.

## Verification environment

The old scratch Torch installation had a truncated `libtorch_cpu.so`
(340676608 bytes, expected 433155401). A separate intact official
`torch==2.5.1+cpu` installation restored real execution without modifying
repository files or the old environment. The known checkpoint test asserts
Torch is absent from `sys.modules`; run its entire file in a fresh process
apart from Torch-dependent tests. Do not skip or rewrite that check.

## Review findings already closed

Patch 0005's initially green tests missed mutable normalized action payloads,
impossible restored cursor/member/receipt histories, and signed/whitespace SHA
strings. Ten new regression cases failed before fixes. The foundation now
owns immutable validated action mappings, strict ASCII hex validation, and
cross-checked restart state. An unkeyed state hash is an integrity check;
authenticity still belongs to the existing outer trusted checkpoint envelope.

## Final component review and execution direction

Granite parser (86 new checks) and evaluator (39 new checks) independently
passed with 20 serializer checks: 145 passed. Both approved and committed.
B1 H2 and prompt P7 are resolved in CLAUDE_TO_CODEX_H2_P7_RULINGS_20260907.md
and implemented in the follow-up branch. OSS remains deferred.
Greg directs urgency: use targeted regression checks, avoid unnecessary broad
reruns and A/B experiments, and prioritize the working model. No additional
full-suite run is required merely to package these reviewed component bytes.

Claude full review R1/R2 completed: interior-depth fixture, precise identifier
wall, and eval-mode serving guard. See R3_REVIEW_CORRECTIONS_20260907.md; only
the two affected files rerun, 104 passed. Full review clears the corrected
branch for push; the earlier no-push status above is historical.
