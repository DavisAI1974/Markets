# Frankie post-S137 residual top-10 evaluation docket — 2026-08-20

## Scope and decision rule

This list assumes every S137 COG01–COG10 scaffold passes its component gate. It asks what could
still invalidate the system-level evidence or make a composed/live Frankie unsafe. None of these
items is evidence that V4 should run, and none changes execution authority.

| Rank | Residual bottleneck | Research anchor | Frankie disposition |
|---:|---|---|---|
| 1 | Adaptive holdout/backtest-selection overfit | Dwork et al., *Reusable Holdout*; Bailey et al., PBO | P0 one-shot exposure ledger implemented; adaptive-null test still required |
| 2 | Causal/temporal leakage hidden inside preprocessing | Kaufman et al.; TensorFlow Data Validation | P0 point-in-time lineage and adversarial mutations required |
| 3 | Locked but biased evaluator | Zheng et al., MT-Bench/Chatbot Arena | P0 order/length/truth canary implemented; real canary data still required |
| 4 | Retrieval/tool prompt injection and poisoning | AgentDojo; PoisonedRAG | P0 before external tools; content is data, never authority |
| 5 | Live temporal/distribution shift | Rabanser et al., *Failing Loudly* | P1 quarantine-only sentinel; no automatic retraining |
| 6 | Correction fails to withdraw descendants | Goods; Google ML Metadata | P0 declared transitive memory withdrawal implemented; full artifact DAG remains |
| 7 | Hidden rare/catastrophic strata | Hidden Stratification; Domino | P1 discovery/confirmation split with multiplicity control |
| 8 | Uncalibrated abstention/selective release | SelectiveNet | P1 external chronological calibration; not a Sol weight change |
| 9 | Safe components compose unsafely/common-mode failure | STAMP | P1 all 45 pairs plus selected higher-order fault tests |
| 10 | Monitoring, rollback, and causal credit after deployment | ML Test Score; doubly robust evaluation | Required before live; paired shadow scoring is simpler while actions are disabled |

## What was implemented in this checkpoint

Three controls were safe to add without claiming model improvement:

1. `memory_withdrawal_closure` excludes every declared transitive descendant of a corrected memory
   while preserving unrelated branches.
2. `HoldoutExposureLedger` makes RELEASE and UNTOUCHED_FORWARD one-shot and aggregate-only, and the
   later release gate rejects a missing, tampered, or split-mismatched audit.
3. `evaluate_judge_independence_canary` revokes grading authority for order, verbosity-control, or
   objective-truth failures and explicitly grants no promotion authority.

The controls passed deterministic tests only. They have not passed planted adaptive-null,
real-evaluator, temporal-shift, hidden-stratum, interaction, or live rollback experiments.

## GPT-5.6 Sol, AWS, and NOVA

GPT-5.6 Sol can reduce ordinary generation and interface errors, but it cannot remove statistical
overfit, leakage, evaluator correlation, poisoned retrieval, or rare-stratum risk. Sol does not
support fine-tuning, so continual weight learning must stay external. AWS can enforce IAM,
append-only logs, alarms, and rollback; it hosts Frankie's control plane, not the OpenAI model.

NOVA should not be added merely to realize a paper architecture. It becomes a candidate only if a
trainable NOVA adapter beats fixed rewrite/random-search and frozen-Sol controls at matched calls,
tokens, wall time, data, and evaluator budget while also passing retention, contamination,
calibration, and rollback gates.
