# Frankie / NOVA SEAL evaluation docket — 2026-08-20

Status: **RESEARCH COMPLETE; DO NOT INTEGRATE.** This docket covers the complete
25-page arXiv v2 paper, the official NeurIPS 2025 version, all appendices, the
released repository/results, and later primary-source scope corrections. It does
not authorize a Frankie runtime change, a NOVA adapter, training, V4, or promotion.

Primary sources:

- Zweiger et al., [Self-Adapting Language Models (SEAL), arXiv:2506.10943v2](https://arxiv.org/abs/2506.10943)
- [Official NeurIPS 2025 record and conference paper](https://papers.nips.cc/paper_files/paper/2025/hash/6b41e04c41726e2a60e456d0a2b961ab-Abstract-Conference.html)
- [Official MIT-licensed research repository](https://github.com/Continual-Intelligence/SEAL)

## Adjudication

SEAL is a credible but narrow meta-learning experiment. It is not a safe general
self-improving agent and it does not solve COG10's consolidation, retention,
rollback, evaluator-independence, or promotion problems.

Do not wire SEAL or NOVA into Frankie now. The default is the current frozen
Frankie plus deterministic external memory/retrieval. A NOVA/SEAL arm remains
eligible only as a disposable SHADOW challenger after it beats fixed rewrite,
long-implications, self-QA, random-search, and ordinary NOVA controls at matched
tokens, calls, trainable parameters, optimizer work, seeds, latency, and cost.

## What the method actually does

For a context and downstream task, the current model generates a textual
self-edit. A cloned model is supervised-fine-tuned on that edit, the clone is
evaluated, and the post-update score trains the original model to emit better
future edits. The reward environment changes with the model weights; old
trajectories are stale. PPO and GRPO were unstable, so the paper uses ReST-EM:
sample candidates on-policy, evaluate every candidate after an inner update,
keep the best/successful candidates, and behavior-clone them.

This needs a trusted labeled downstream task for every context. It is not
autonomous learning from unlabeled experience. The public selector ranks
absolute adapted accuracy and can retain the least harmful edit even when every
candidate is worse than the unadapted model.

## Exact evidence

### Knowledge incorporation

- Base model: Qwen2.5-7B; SQuAD v1.1.
- Each outer round: 50 contexts × 5 edits × 3 update seeds = 750 inner
  fine-tune/evaluation loops; two rounds; about six hours per round on 2×H100.
- Single passage accuracy: frozen base 32.7, raw passage 33.5, base-model
  synthetic data 39.7, GPT-4.1 synthetic data 46.3, SEAL 47.0.
- Continued pretraining over 200 passages: 32.7 / 36.0 / 50.6 / 59.4 / 58.2.
- Continued pretraining over 2,067 passages: 29.0 / 31.2 / 43.4 / 49.2 / 46.4.

SEAL exceeds GPT-4.1 by only 0.7 points in the single-passage column and loses at
both larger scales. A paired audit of the released single-passage artifacts gives
a passage-level difference of 0.68 points with an approximate 95% interval of
[-3.53, +4.88]. The edge is not supported statistically. On the released
500-question continued-pretraining arrays, exact paired tests also do not support
a difference at either scale.

Fixed prompt ablations are a stronger warning. Before reinforcement learning,
the long-implications and rewrite prompts score 49.3 and 49.4, already above the
canonical 47.0 result. After learning they reach 54.4 and 55.6. Prompt arms were
not matched for generated training-token count. A GPT-4.1 proxy reward reaches
45.6 in about five minutes versus 47.0 in about six hours for the full reward.

Figure 6 demonstrates catastrophic forgetting: passage 0 falls from about .38
after its update to .19 after eight sequential edits. That alone fails Frankie's
zero-protected-regression COG10 rule.

### Few-shot ARC

- Base model: Llama-3.2-1B-Instruct.
- Eleven manually curated training tasks and eight evaluation tasks, both
  filtered for solvability by a hand-tuned oracle test-time-training setup.
- Five configurations for each of eight evaluation tasks: 40 correlated
  configuration trials, not 40 independent tasks.
- ICL 0%, untrained self-edit 20%, SEAL 72.5%, oracle 100%.

The 72.5% is 29 successful configurations among 40 trials on eight
oracle-filtered tasks. It is not 72.5% of ARC tasks solved. The selected spectrum,
pseudoreplication, tiny task count, and absence of intervals make this unsuitable
as evidence of broad self-adaptation.

## Released-artifact audit

The repository is a valuable MIT-licensed research artifact, but not a production
dependency: nine commits, no release, CI, or test suite, and hardware/SLURM
assumptions. Material discrepancies include:

1. Table 2 result files cap both continued-pretraining evaluations at 500
   questions, while the paper says the 200-passage model uses all 974 questions.
2. Released full-fine-tuning uses learning rate `7e-5`, outside the paper's stated
   multi-passage search grid.
3. The public newline-splitting command sets `1` while the script checks for
   `"true"`.
4. Inner seeds derive from wall-clock microseconds.
5. ARC files contain 12 train and 10 evaluation tasks, while the paper reports
   11 and 8 and README commands use several inconsistent counts.
6. No human validation of the GPT-4.1 QA judge is reported; the same model family
   supplies both the comparison synthetic data and the judge.

The official NeurIPS checklist explicitly reports no suitable significance or
error-bar evidence for the main experiments.

## Frankie, GPT-5.6 Sol, AWS, and NOVA

GPT-5.6 Sol's [official model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
lists a 1.05M context window, tool/structured-output support, and **no fine-tuning
support**. SEAL therefore cannot update Sol's weights. A client running in AWS
changes orchestration, IAM, storage, alarms, latency, and rollback—not Sol's
reasoning or the statistical validity of an experiment.

For Frankie, the only lawful analogue is an external, versioned proposal: a
typed memory candidate, prompt/procedure patch, retrieval policy, or training set
for a separate model. Immutable evidence, evaluator, permissions, outcome wall,
rollback, and promotion stay outside the learner.

NOVA is trainable, so adapter-based SEAL is technically possible. It is not yet
justified. Current NOVA is a small conventional decoder without the demonstrated
1B–7B edit-generation capacity, LoRA/SEAL loop, clean corpus, repeated-seed
evidence, or retention system. SEAL may propose data during COG10's disposable
"progress" phase; it supplies no safe "compress" mechanism.

## Required control ladder

Any future test must preserve this order and stop as soon as a simpler arm wins:

1. frozen Frankie/current NOVA;
2. raw external evidence memory;
3. fixed long implications;
4. fixed rewrite;
5. fixed self-QA;
6. random update-directive search;
7. ordinary base-model self-edit without learning;
8. learned ReST-style selector;
9. proxy-reward selector;
10. structured pairs/triples with equal generation count.

All arms receive the same source checkpoint, causal data, synthetic-token count,
original-evidence tokens, trainable parameter count, optimizer steps/FLOPs,
candidate/update-seed count, evaluation calls, and total cost. Candidate judging
and outer training count against the intervention budget. Use distinct
chronological training, reward-development, hyperparameter-development, and
untouched-forward partitions with at least five outer-loop seeds.

Promotion requires a repeated-seed paired interval excluding zero against both
fixed rewrite and random search; no protected or old-regime regression; no
reward/test reuse; no calibration, provenance, abstention, unsupported-claim, or
general-reasoning regression; and exact adapter removal/rollback. Any future
leakage, unsupported synthetic claim, evaluator ownership, forgetting, proxy/true
reward divergence, or benefit that disappears after equal-token/equal-FLOP
matching ends the experiment.

## Decision

**No Frankie↔NOVA wiring and no SEAL implementation now.** Preserve SEAL as a
documented SHADOW research candidate only. The linked paper improves the design
of a falsification experiment; it has not demonstrated an upgrade to Frankie or
NOVA.
