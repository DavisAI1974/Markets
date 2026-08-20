# Frankie cognitive top-10 implementation and test handoff - 2026-08-20

Status: **PRE-V4 SHADOW SCAFFOLDS AND CONTRACTS IMPLEMENTED; NO HELD-OUT PERFORMANCE CLAIM.**

The additional cognitive top ten is represented as ten separate test candidates. Most entries are
bounded validators, schemas, or pure helpers rather than implementations of the papers' full agent
methods. No paper,
component test, aggregate score, or model-written critique can edit permanent Frankie or authorize
V4. Each candidate has a frozen-current-Frankie control, an isolated intervention, matched resource
budgets, protected strata, explicit falsifiers, pass-to-fail accounting, and an untouched-forward
next gate.

## Implemented shared safety and evaluation layer

- Frankie output schema is `1.1`; agent version is `frankie-s137.0`.
- Every reasoning step now has a typed action, claim, exact evidence refs, prior-step dependencies,
  and support status.
- Every lane must report explicit uncertainty drivers. A probability is optional and has no
  authority.
- Evidence catalogs separate WORKING, EPISODIC, SEMANTIC, and PROCEDURAL memory classes.
- Evidence reads are hash-bound and read-only. Unknown or future evidence refs fail closed.
- Declared memory influence edges now support transitive withdrawal: invalidating a source also
  prevents its summaries, derived procedures, and other recorded descendants from being served.
- `frankie_s137_cognitive_runtime.py` wraps the frozen S135 CURRENT FRANKIE runtime one candidate at
  a time, attaches the selected experiment contract, and validates its evidence-bound output before
  the canonical S135 freeze/reveal/score state machine continues.
- `frankie_s137_cognitive_experiment_runner.py` derives both arms from one frozen S135 information
  set, alternates arm order when requested, requires exact six-dimension metering, freezes and hashes
  both outputs before revealing the target, then passes only externally graded rows to the locked
  evaluator.
- Immutable decision provenance records the cognitive-contract version, evidence-catalog hash, and
  independent trace hashes.
- Source provenance with `knowable_at > observed_at` is rejected before reasoning.
- The protected `spawn.py` Git-blob check now handles Windows CRLF checkout normalization without
  weakening the stored blob pin.
- Candidate release evaluation requires task/regime/safety/provenance strata, a locked evaluator,
  locked permissions, verified rollback, a fresh release split, and completed untouched-forward
  shadow evidence.
- A catastrophic result, protected-case regression, ordinary pass-to-fail regression, reused
  release split, or mutable evaluator/permissions/rollback rejects release.
- Release and untouched-forward splits have a one-shot exposure ledger: a locked evaluator may
  disclose one aggregate final score, while row-level examples and a second query fail closed.
- A separate judge canary revokes grading authority after answer-order, verbosity-control, or
  objective-truth bias; passing it grants no promotion authority.

## Ten isolated candidate arms

| Rank | Candidate | Implemented bounded surface | Important missing paper behavior |
|---:|---|---|---|
| 1 | `COG01_COALA_ARCHITECTURE_MAP` | Typed map plus generic context contract | decision-cycle policy and memory learning |
| 2 | `COG02_REACT_EVIDENCE_LOOP` | Validator for a supplied evidence trace | closed-loop tool retrieval and replanning |
| 3 | `COG03_LATS_BOUNDED_PLAN_SEARCH` | Pure selector for pre-made externally scored branches | generation, rollout, value search, reflection |
| 4 | `COG04_STRUCTGPT_TYPED_READS` | Pure hash-bound exact-reference store | iterative model-directed structured retrieval |
| 5 | `COG05_FAITHFUL_EXECUTABLE_REASONING` | Four allowlisted deterministic predicates | language-to-symbolic translation and general solver |
| 6 | `COG06_CRITIC_TOOL_VERIFICATION` | Narrow deterministic-check validator | tool-interactive critique and revision loop |
| 7 | `COG07_MEMORY_AGENT_BENCH` | Pure scorecard plus memory-selection helpers | incremental histories and runtime memory system |
| 8 | `COG08_HIPPORAG_ASSOCIATIVE_RETRIEVAL` | Pure deterministic graph-ranking helper | entity graph construction and reader pipeline |
| 9 | `COG09_HIAGENT_WORKING_MEMORY` | Working-memory object validator | subgoal generation, compaction, context serving |
| 10 | `COG10_PROGRESS_COMPRESS_SHADOW_LEARNING` | Release/consolidation gate only | active learner, consolidation, weight updates |

The authoritative machine-readable registry is
`FRANKIE_COGNITIVE_TOP10_EXPERIMENT_MANIFEST_20260820.json`.
The deterministic ten-arm contract run is recorded in
`FRANKIE_COGNITIVE_TOP10_COMPONENT_CANARY_20260820.json`; that artifact explicitly declares
`performance_evidence: false`.
The paired execution contract is frozen in
`FRANKIE_COGNITIVE_TOP10_PAIRED_RUNNER_MANIFEST_20260820.json`.

## Test contract

Every held-out row must contain:

- unique `case_id`;
- frozen-baseline and candidate pass states;
- candidate catastrophic/protected flags;
- `task`, `regime`, `safety`, and `provenance` strata;
- baseline and candidate budgets for model calls, input/output tokens, tool queries, storage bytes,
  and wall clock;
- the paper-specific metric vector.

The component gate requires:

1. zero pass-to-fail and protected-case regressions;
2. at least 30 cases, five fail-to-pass corrections, and five examples in every observed stratum;
3. zero catastrophic failures;
4. no candidate resource budget above the preregistered tolerance;
5. the primary metric improves by its declared minimum;
6. every guardrail stays within its declared non-regression tolerance; and
7. complete stratum accounting rather than a pooled average alone.

Passing produces only `COMPONENT_GATE_PASSED` and the next state
`UNTOUCHED_FORWARD_SHADOW`. It never produces permanent promotion.

## Validation completed in this implementation pass

```text
python -m pytest -q research/kalshi/tests tests/test_frankie_s135_group_runner.py
212 passed

python research/kalshi/agent_frankie.py selftest
12/12 passed
```

The new test modules run legal and adversarial component canaries for all ten candidates, including
unknown evidence, future provenance, execution requests, self-owned plan scores, stale memories,
transitive descendant withdrawal, multiple active subgoals, budget overruns, pass-to-fail flips,
catastrophic cases, holdout reuse, one-shot exposure enforcement, evaluator-bias revocation,
unlocked evaluator/permission/rollback gates, candidate/control information-set drift, and target
reveal before both arms are frozen.

These are implementation and contract tests. They do **not** claim that any candidate improves
forecasting, market reasoning, or live decision quality.

## Held-out run sequence before V4

1. Freeze the current Frankie tasks, outputs, graders, budgets, seeds, protected cases, and
   chronological partitions.
2. Materialize one experiment-row package per candidate without using the release partition during
   candidate generation.
3. Run the frozen baseline and exactly one candidate arm from the same S135 packet with the same
   model/backend and matched resource ceiling. SHA-freeze both outputs before target reveal.
4. Record exact model-call, input/output-token, tool-query, storage, and wall-clock usage; then
   evaluate with `frankie_cognitive_experiments.py evaluate` and retain full per-case trajectories.
5. Reject or revise candidates that fail their component gate. Do not combine weak candidates to
   hide individual regressions.
6. Run passing candidates on an untouched-forward SHADOW partition.
7. Use the strengthened `frankie_evolution.evaluate_release` gate with locked evaluator,
   permissions, rollback, and zero release-split reuse.
8. Present any surviving component for explicit human review. Permanent integration remains a
   separate decision.

V4 remains blocked during these cognitive experiments. SEAL/NOVA self-editing was not integrated:
the published SEAL gains do not beat simpler fixed rewrite controls consistently, the released
evidence has reproducibility mismatches, and GPT-5.6 Sol does not support weight fine-tuning. The
existing chain/POX academic docket, GDL docket, and canonical paper manifest were not replaced or
mutated by this implementation.
