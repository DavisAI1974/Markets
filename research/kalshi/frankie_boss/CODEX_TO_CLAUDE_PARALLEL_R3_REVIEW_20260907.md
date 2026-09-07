# Codex to Claude — parallel R3 foundation review batch

Date: 2026-09-07. Base: `beb548b86b777dc69bf834950b30cc28000e16ef`.
Contract: `BOSS_CONTRACT_ADDENDUM_R3_20260907`, corrected rev 1 supplied by Greg.

## Outcome and requested review

Five isolated components are independently reviewed and committed locally:
the per-record causal prefix, C15 normalizer, D1-D6 geometry machine, Granite
schema/parser, and Granite evaluator.
B1 recurrence/halting is implemented as an **uncommitted review draft** with
an ordinary failing acceptance regression. Please review the separate patches
as a batch and return the two narrow contract rulings below. The agreed model
architecture is not being reopened.

All changes are additive. No existing Frankie input, calculation, plane,
adapter, replay, trunk, teacher, Memory A artifact, or last-run behavior was
changed. No provider, market-data, training job, AWS workflow, or reveal ran.
Synthetic unit tests did execute real Torch forward/backward operations.
No branch was pushed. The review aggregation branch combines new components
for delivery and tests only; it is not production integration.

## Included slices

| Slice | Files under research/kalshi/frankie_boss | Status / lane commit |
|---|---|---|
| Prefix | causal_prefix.py, causal_prefix_records.py, their two test files | Approved; `17e4b46a` |
| Normalizer | c15_normalizer.py, tests/test_c15_normalizer.py | Approved; `26ad8529` (original lane) |
| D-state | c15_dstate.py, tests/test_c15_dstate.py, C15_DSTATE_R3_IMPLEMENTATION.md | Approved; `08763740d596f847daa29167ed1dfc2645b8cf16` (original lane) |
| Granite parser | granite_output_schema.py, granite_parser.py, tests/test_granite_parser.py | Approved; `af18053116073b56a91ff5da840ebb6d30735667` (original lane) |
| Granite evaluator | granite_evaluation.py, tests/test_granite_evaluation.py | Approved; `78d7325fb0941582c0dab90fcb278817d40020f3` (original lane) |
| B1 / halt | b1_reasoner.py, tests/test_b1_reasoner.py | Draft; H2 blocked; no accepted commit |

The accepted patches apply in numbered order to the exact base. Normalizer
is independent of prefix; D-state depends on prefix. B1 draft can be reviewed
against the same base but is intentionally absent from the accepted branch.
The package contains exact code, tests, contract sources, patch files, and a
Git bundle of the accepted local review branch. See BATCH_MANIFEST.json for
full commit identities, blob hashes, and file checksums.

## Prefix: Claude patch 0005 plus required review fixes

Reproduced the prior 93-test baseline before applying patch 0005. Claude's
patch passed 135 relevant checks. Fresh review then reproduced three defects:

1. RecordInput was frozen but its action mapping remained mutable after
   validation; malformed values could be chained. The mapping is now a
   detached immutable scalar mapping.
2. Restore accepted structurally impossible histories, including a genesis
   state with an advanced cursor, mismatched terminal receipt context, and
   inconsistent per-instrument/global ordinals. These now fail closed.
3. SHA validation via int(value,16) accepted signs/whitespace. It now requires
   exactly 64 ASCII hexadecimal characters.

Ten new regression cases failed before the fixes. Independent rereview
approved the result. No prefix preimage/schema change was needed for honest
records. Self-hashes remain integrity checks, not proof of external authority;
the existing trusted outer checkpoint envelope still owns authenticity.

## Normalizer

Implements the exclusive prior-value window, exact 256-PRESENT warmup,
per-instrument/column floors, 4096-value bound, explicit freeze, strict restore,
float64 compute/float32 emission, and all six blocked slots without state.

Freeze is explicit: restore matching UPDATING state, freeze unchanged Oct-1
statistics, export FROZEN state, and bind that resulting state hash. Future
frozen phases restore that exact FROZEN export; no permissive mode mismatch.

Fresh review reproduced and fixed:

- config hash missing its DOMAIN + NUL separator;
- canonical_bytes' 12-significant-digit float policy allowing distinct
  float64 windows to share a hash despite different float32 outputs;
- finite subtraction overflow producing an incorrect clipped z score.

Numeric export values are retained. Exact float.hex companions bind window
and configurable float values through the same canonical_bytes authority;
restore cross-checks both. No second JSON serializer was introduced.

## D-state

Implements only pure D1-D6 geometry and an explicit existing-prefix receipt
consumer. T-A through T-D, break/restart, undefined-anchor freeze, reversal,
source/session reset, and last-completed-step duration are tested. Duration is
captured when an extension completes, matching R2's duration_last family
tuple; a later unarmed extreme cannot rewrite the completed step.

The consumer checks receipt authority, instrument, and ordinal progression.
It does not prove that caller-supplied anchor/book values were derived from
that prefix: the future observer/input builder owns that proof. C1 lifecycle
implementation remains deferred, despite clarified semantics in the addendum.
No D-state checkpoint integration or full target builder was added.

## B1: one required ruling, no weakened tests

The draft implements the specified shared recurrent core, separate K_MAX by
d_model embedding count, h0 reinjection, graph once, step-local temporal
memory, full backpropagation, fixed/convergence policies, and receipts.

Initial H2 fixtures passed after evaluating the shared cell and unchanged
heads row by row in CONVERGENCE mode, eliminating their batched-kernel rounding
differences. FIXED and zero-depth use the original B0 execution path.
Broader independent fixtures showed the unchanged trunk itself can produce
different h0 bits for the same example in batch 1 versus batch 32. Rowwise
recurrence/heads cannot remove that upstream difference.

Current B1 focused result: **37 passed, 3 failed, exit 1**. The three ordinary
regressions cover (d_model,T)=(8,1),(16,7),(32,7); observed h0 differences are
approximately 1.19e-7 to 4.77e-7. No skip, xfail, rounding, dtype substitution,
global backend change, trunk edit, or relaxed assertion hides this failure.
The independent reviewer also reproduced the issue at larger model widths.

Please resolve the numerical execution contract, not the agreed architecture:

- Suggested ruling: allow CONVERGENCE to evaluate the whole native path per
  example, and define graph-once as once per example's representation rather
  than once per batched forward. Preserve the original FIXED/zero-depth B0
  path. This changes invocation granularity, not graph weights or authority,
  but must be approved because current A5 explicitly requires one invocation.
- If instead numerical tolerance is intended, specify it and the required
  halting-depth behavior near conv_tau; Codex will not choose a tolerance or
  silently relax H2.

All other reviewed B1 requirements had no required finding. That is not an
approval of the B1 slice; H2 remains a commit blocker.

## Granite: implemented components and one prompt ruling

The supplied Granite structured-output plan now has a strict closed schema,
L0-L4 parser/reward authority, and a pure evaluator for supplied paired outputs.
Training and runtime scorer names refer to the same function; runtime accepts
only L4. Hash checks use the exact SerializedState identity, and nested field
references must resolve against that snapshot. Duplicate keys, nonfinite
numbers, boolean row indices, unknown keys, caps, and wrapped JSON fail closed.

The evaluator implements the supplied format/content/latency gates using 200
unique paired snapshot identities and equal token budgets. It runs no models
or A/B experiments. Content/diversity and disposition metrics use schema-valid
outputs; Claude should confirm this documented denominator (disposition is
stricter than an all-prompts denominator). Unparseable or missing hash echoes
are reported separately: zero observed mismatches does not mean every echo was
verified. Declared disjoint training hashes do not prove chronological separation.

Prompt-builder P7 needs a narrow ruling: the mandatory output schema contains
`disposition`, but P7 bans every BLD1_FIELD_NAMES name anywhere in prompt text,
and that set includes `disposition`. Suggested ruling: apply the BLD-1 ban to
source/input prediction and outcome payloads while explicitly permitting the
required output-schema vocabulary. Do not silently weaken the answer wall.
Matching snapshot hashes establish identity, not absence of answer leakage.

No prompt builder, provider adapter, training runner, model download, GPU run,
or production integration is included. OSS remains undecided and outside this
batch; its added value will be considered later, per Greg's direction.

## Owner's execution direction

Prioritize reaching a working model. Use targeted checks for concrete regression
risks and proceed with improvements that have credible benefit without adverse
effects. Avoid further discovery, repeated broad suites, or unnecessary A/B
experiments. The evaluator is available for later use, not a new requirement
to run experiments before each implementation step. Preserve the existing
Frankie boundary and resolve the two actual contract conflicts promptly.

## Verification evidence

Healthy runtime: Python 3.12, official Torch 2.5.1+cpu in an isolated scratch
installation. Old Torch libtorch_cpu.so was truncated (340676608 bytes versus
433155401 expected), causing SIGBUS. Existing environments were not changed.

| Slice | Actual test evidence |
|---|---|
| Prefix | 70 prefix tests independently pass; full package at prefix commit: 298 passed + 1 existing CUDA skip, plus 11 checkpoint tests in a separate process |
| Normalizer | 60 new + 51 unchanged packet/decision tests = 111 passed; independent 60-test rerun approved |
| D-state | 37 new independently pass; lane full package: 346 passed + 1 existing CUDA skip across two processes |
| B1 draft | 37 passed, 3 failed; wider H2 failure retained |
| Granite parser/evaluator | 86 new parser + 39 new evaluator + 20 unchanged serializer = 145 independently passed |

Before adding Granite, the combined accepted prefix/normalizer/D branch passed
406 tests with one existing CUDA skip across two processes. Granite then passed
its focused independent checks above. No new combined full-suite total is claimed;
no broad rerun was performed after Greg requested targeted checks and urgency.

The checkpoint file asserts Torch is absent from sys.modules. Combining it
with Torch test collection in one process produces an existing isolation
failure. The complete checkpoint file runs in a fresh process; none was
deleted/deselected. The only skip is the existing CUDA-only control test.

Reproduction from `research/kalshi/frankie_boss/tests`, with pytest and real
Torch installed and the parent directory on PYTHONPATH:

```
python -m pytest -q --ignore=test_benchmark_checkpoint.py --tb=short
python test_benchmark_checkpoint.py
```

For the B1 draft after deliberate application: run
`python -m pytest -q test_b1_reasoner.py --tb=short` and expect the three H2
failures until Claude's ruling is implemented.

## Readiness and next boundary

C14 schema and C17/C18 repairs already existed at the base; C13 mask plumbing
also exists and its preservation checks ran with healthy Torch. They were not
rebuilt. Workbook reconciliation must retain pending production proofs.

C15 remains Partial. B1/C20 remain Partial with the H2 blocker. Observer,
full 19-column builder, checkpoint integration, Granite prompt/runtime/fusion,
experiment orchestration, and all market/promotional runs remain unfinished.
Existing BOSS-off identity and answer-wall integration gates stay OPEN.

Please review these slices together, return any required corrections and the
H2 and P7 rulings, and preserve the current Frankie boundary throughout.
