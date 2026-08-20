# Frankie P0 gap closure — provisional checkpoint — 2026-08-20

Status: **PROVISIONAL SHADOW/CONTROL PLUMBING. COMPONENT CONTRACTS READY;
EMPIRICAL EVIDENCE BLOCKED. NO V4 LAUNCH, PROMOTION, AUTOMATIC APPLY, LIVE
TRAINING, OR PAPER-REPLICATION CLAIM.**

Base checkpoint: `71a71e94c08c27615b05f10165cbc88e38f2aa56`.

Implementation commit: `5501fd5f4ce50ae908b0a40b1d9939c465ab3c1a`.

The committed S137 research dockets remain the source of paper interpretation.
This addendum records what was actually added or repaired; it does not rewrite
helpers as learning algorithms or tests as performance evidence.

## Outcome

The incomplete Frankie plumbing was materially upgraded. Nine of the ten
cognitive candidates now have an explicit bounded SHADOW hook; COG01 remains a
no-behavior-change architecture/instrumentation contract because CoALA is an
organizing framework, not a prescribed learning algorithm. The registry binds
60 public call surfaces across nine P0 modules to exact source bytes and reports
`COMPONENT_CONTRACT_READY`.

That is not empirical readiness. The executed held-out, calibration,
contamination, retention, evaluator-independence, and live byte-rollback
receipts are all absent, so readiness remains
`BLOCKED_PENDING_EMPIRICAL_EVIDENCE`.

## Cognitive implementation depth

| Candidate | Implemented provisional surface | Honest remaining paper/evidence gap |
|---|---|---|
| COG01 CoALA | typed memory/action map; instrumentation coverage separated from behavior; exact behavior-projection invariance | no preferred CoALA policy or memory learner is claimed |
| COG02 ReAct | bounded decide/read-only-act/observe/replan/stop hook; transitive evidence grounding | no paper prompt/tool environment or learned action policy |
| COG03 LATS | bounded selection, expansion, simulation, value, reflection, backpropagation; tree vs one-path control | no paper prompts, learned policy/value model, or benchmark replication |
| COG04 StructGPT | iterative exact-reference reads plus runtime catalog revalidation | no paper-exact table/KG/database interfaces or trained retrieval policy |
| COG05 Faithful reasoning | source-hashed, deterministic, non-Turing typed IR | no language-to-IR model or general solver stack |
| COG06 CRITIC | immutable initial/check/critique/revise/recheck hook | no paper prompts, external tool suite, or trained critique policy |
| COG07 MemoryAgentBench | isolated chronological four-axis benchmark and descendant withdrawal receipts | no corpus replication, LLM judge, or complete runtime memory architecture |
| COG08 HippoRAG | source extraction proposals, associative graph, PPR, top-k, cited reader, flat control | no paper-exact extractor/entity linker/trained reader or benchmark replication |
| COG09 HiAgent | one-active-subgoal state, compaction, hidden history, detail retrieval | no model-generated subgoals/summaries or learned retrieval policy |
| COG10 Progress & Compress | protected-KB/active/teacher/distillation-EWC proposal/retention/rollback lifecycle | callbacks do not prove real gradients, Fisher estimation, distillation, or live consolidation |

All nine hooks are explicit opt-in calls through
`CognitiveCandidateRuntime.run_p0_component`. They are not automatically
invoked by the S135 group runner and never gain execution or apply authority.

## Market, temporal, and GDL controls added

- Causal Level-I OFI events, book guards, trailing features, observable
  depletion/refill episodes, censoring, lag-only forecast rows, and matched
  OFI/price/volume/static-imbalance baselines.
- Open-stream one-to-one event matching, false-alarm/delay scoring, exact
  first-lock movie recomputation, reveal-purged splits, calibration/selective
  risk, case-clustered repeated-seed evidence, complete retention matrices,
  planted-null contamination receipts, and non-vacuous byte rollback.
- Anytime planted-null alpha-spending audit; accumulated-gap calibration;
  delayed-label scalar ACI replay; Han–Huang–Wang-inspired current-risk windows
  over a frozen model pool with fixed/expanding/recent controls.
- Causal prefix/effective-cutoff audit, graph stability pairs, 1-WL and edgeless
  Deep-Sets controls, and declared artifact-DAG descendant withdrawal coverage.
- TGN/TGAT-inspired temporal message/memory plumbing with exact batch-size-1
  predict-before-update replay, lane isolation, invalidation replay, reset
  identity, and frozen-static/Deep-Sets/1-WL control bindings.

The temporal graph adapter is not a trained or paper-faithful TGN/TGAT.
Graph associations are never causal provenance. The current-risk helper is not
a cumulative-loss, best-fixed, switching-regret, or live-selection theorem.

## Repaired pre-existing plumbing defects

- ReAct retrieval use is transitive and every reasoning step must have an
  observation/retrieval ancestry path.
- LATS-style branch selection is ancestry closed.
- Deterministic-check receipts bind exact inputs.
- Runtime typed-read catalogs are detached immutable copies; later caller
  mutation cannot alter pending validation.
- Future invalidations no longer alter historical withdrawal hashes; creation
  chronology and descendant paths are validated.
- Memory competency scorecards require per-axis performance minima.
- Associative retrieval rejects dangling endpoints and binds graph/active/seed
  identities.
- Marginal and joint strata are predeclared and independently gated; a damaged
  joint cell cannot hide behind passing marginals.
- The paired runner requires declared marginal/joint strata and balanced arm
  ordering. Synthetic/development rows no longer claim performance evidence.
- COG01 task behavior is hash-projected separately from instrumentation gain.
- Release exposure chains are recomputed and bind the candidate, locked
  evaluator, and rollback artifacts.
- Judge canaries bind judge identity/version, canary manifest, exact cases, and
  valid tolerances.
- Evolution release audits bind evaluator and rollback artifacts.

## Evidence contract

`frankie_p0_registry.evaluate_p0_readiness` refuses labels and standalone SHA
declarations. Each of these six evidence types must embed its complete
self-hashed executed source-validator receipt, reconcile row/artifact counts,
pass its own gate, and share candidate, baseline, runner, evaluator, and plan
bindings:

1. held-out paired performance;
2. calibration and selective risk;
3. planted-null contamination;
4. complete protected retention matrix;
5. evaluator-independence canary;
6. non-vacuous byte-exact live rollback.

Even a complete bundle leaves execution, apply, and promotion false and still
requires independent review plus explicit user authorization.

## Research accounting

- Cognitive Top-10: 10/10 paper-level mechanism/evidence audits complete.
- SEAL: complete deep audit; remains “do not integrate.”
- Independent market academic Top-10: 10/10 complete.
- GDL monograph: full document audited.
- GDL bibliography: 340/340 screened, but only 25/340 have explicit paper-level
  audits. Screening is not deep research; 315/340 remain without individual
  deep mechanism/evidence audits.

SEAL/NOVA remains a disposable candidate only if it beats frozen, fixed
rewrite, self-QA, random-search, and ordinary NOVA controls at matched budget
and passes retention, contamination, calibration, evaluator, and rollback
gates. It was not integrated here.

## Verification

```text
python -B -m pytest -q research/kalshi/tests tests/test_frankie_s135_group_runner.py
329 passed

python -B research/kalshi/agent_frankie.py selftest
12/12 passed
```

Registry: 60 public surfaces; 6 benchmarks, 29 helpers, 10 runtime loops, and 15
validators. Synthetic component canary passed contracts with
`performance_evidence=false`.

No V4 source/workflow was changed or launched. No V3 monitor was created or
managed. The separate V4 decision is in
`FRANKIE_V4_UNIFIED_FRAMEWORK_AUDIT_20260820.md`.

## Remaining priority gaps

1. Produce real, untouched chronological evidence for the six-type readiness
   bundle without consuming or reusing a release holdout.
2. Supply real model/tool callbacks and matched controls for the surviving
   cognitive mechanisms; current injected callbacks are bounded plumbing and
   caller attestations.
3. Run calibration, dependence-aware paired uncertainty, poisoning/prompt
   injection, evaluator canaries, protected retention, and live rollback on
   real artifacts.
4. Decide which gap-critical GDL references merit deep audits; do not call all
   340 deeply audited.
5. Keep spectral, ReLIC, graphon, learned topology, and full trained temporal
   graph mechanisms as separately named shadow candidates until they beat
   simpler controls.
6. Do not launch V4 until the unified registry/adapter/reconciler design, exact
   candidate commit, all V4 gates, and separate user authorization are complete.
