# Frankie general cognitive-architecture academic top-10 evaluation docket - 2026-08-20

Status: **CANDIDATE EVALUATION ONLY.** This is an additional whole-Frankie
research track. It supplements, and does not replace, the chain/POX-specific
`FRANKIE_ACADEMIC_TOP10_EVALUATION_DOCKET_20260820.md` or the GDL bibliography
audit in `FRANKIE_GDL_REFERENCE_EVALUATION_DOCKET_20260820.md`.

This docket covers Frankie's overall reasoning, planning, working memory,
long-term memory, evidence use, verification, learning, and evaluation. It does
not authorize implementation, V4 launch or resumption, permanent Frankie
mutation, a canonical paper-manifest addition, trading, or play promotion.

## Research and adjudication method

Three independent research passes considered: (1) reasoning and planning,
(2) memory and learning, and (3) evaluation, safety, and promotion controls. The
final ranking was adjudicated across those passes rather than formed by vote or
simple aggregation. Every selected paper is peer-reviewed and linked to an
official conference, journal, or proceedings record.

The ranking favors papers that cover a distinct Frankie cognitive function,
produce an isolated and falsifiable candidate experiment, preserve Frankie's
causal and authority walls, and can be compared under equal model, tool, token,
storage, and latency budgets. A paper's result in QA, coding, web navigation,
games, or continual-learning benchmarks is motivation for a Frankie test, not
evidence of market or forecasting validity.

## Ranked candidates

### 1. Cognitive Architectures for Language Agents (CoALA)

Sumers et al., [TMLR 2024](https://openreview.net/pdf?id=1i6ZCvflQJ).

What it says: language agents can be described through modular working,
episodic, semantic, and procedural memory; structured internal and external
actions; and a decision cycle that selects among those actions. It is primarily
an organizing framework, not a claim that one implementation is best.

Frankie transfer: use CoALA as a typed architecture map for the existing
collector, causal-scientist, trading-mechanics, adjudication, evidence, outcome,
critic, and proposal surfaces. Make every read, write, retrieve, reason, verify,
propose, and external action explicit, attributable, and permissioned.

First gate: produce a no-behavior-change shadow map and replay representative
Frankie tasks. Require complete provenance for every retrieved memory and tool
result, no new authority, and exact decision invariance before testing any new
cognitive component.

Boundary: CoALA is a vocabulary and design frame. It does not justify merging
Frankie's independent lanes, letting the LLM execute, or letting a learner edit
permanent state.

### 2. ReAct: Synergizing Reasoning and Acting in Language Models

Yao et al., [ICLR 2023](https://arxiv.org/pdf/2210.03629).

What it says: interleaving reasoning traces with task-specific actions allows
observations from the environment to update plans instead of separating a long
reasoning pass from all evidence gathering.

Frankie transfer: test a typed research loop of hypothesis, permitted evidence
request, immutable observation, update, and stop or abstain. This is relevant to
both causal-scientist and trading-mechanics research, but each lane must retain
its own evidence and conclusion.

First gate: compare the present workflow with a bounded ReAct-style shadow loop
on sealed tasks at the same model calls, retrieved tokens, tool queries, and wall
clock. Report evidence completeness, unsupported claims, conclusion flips,
abstention quality, and fail-to-pass versus pass-to-fail cases.

Boundary: actions are typed read-only research operations. ReAct never gains
execution, code-change, promotion, or trading authority, and a reasoning trace
is not evidence.

### 3. Language Agent Tree Search (LATS)

Zhou et al., [ICML 2024](https://proceedings.mlr.press/v235/zhou24r.html).

What it says: reasoning, acting, planning, environment feedback, value
estimation, and reflection can be combined in a tree-search framework so an
agent explores multiple candidate paths instead of committing to one linear
trajectory.

Frankie transfer: test bounded search over alternative causal mechanisms,
evidence plans, or research decompositions before adjudication. Distinct
hypotheses should remain visible rather than being compressed into an early
story.

First gate: compare one-path planning with a small fixed-width, fixed-depth tree
under the same total call and token budget. Require improved executable-grader
success and failure localization without worse latency, hallucinated evidence,
calibration, abstention, or protected-case regressions.

Boundary: branch scores are search heuristics, not probabilities or promotion
votes. Search cannot inspect unrevealed outcomes, expand permissions, or use
Frankie's final judgment as its own ground truth.

### 4. StructGPT: A General Framework for Large Language Model to Reason over Structured Data

Jiang et al., [EMNLP 2023](https://aclanthology.org/2023.emnlp-main.574/).

What it says: specialized interfaces can retrieve relevant portions of
structured data while the language model performs iterative reading and
reasoning over the returned evidence. The model need not ingest or invent a
linearized copy of the entire data store.

Frankie transfer: expose event records, evidence nodes, outcomes, lens books,
plays, and provenance through narrow typed read interfaces. The LLM asks for a
specific lawful view and receives a deterministic, attributable result.

First gate: compare current retrieval with typed interfaces on sealed
multi-source questions at equal returned-token and query budgets. Require higher
evidence recall and citation correctness with no increase in forbidden-field,
future-data, cross-lane, or unauthorized-write access.

Boundary: a typed call is not semantic safety by itself. Access policy,
availability time, provenance, and result validation remain deterministic and
outside the model.

### 5. Faithful Chain-of-Thought Reasoning

Lyu et al., [IJCNLP-AACL 2023](https://aclanthology.org/2023.ijcnlp-main.20/).

What it says: for suitable tasks, a model can translate a problem into a formal
representation that is executed by a deterministic solver, tying the answer to
an inspectable computation instead of relying on a free-form rationale alone.

Frankie transfer: move checkable portions of reasoning - temporal eligibility,
arithmetic, contract rules, evidence joins, thresholds, set membership, and
consistency checks - into typed intermediate representations and deterministic
execution.

First gate: select a preregistered set of presently free-form but checkable
steps. Require exact executable validity, lower silent-error and unsupported-step
rates, and unchanged or better end-task performance at the same model budget.

Boundary: the deterministic executor validates only the encoded proposition. It
does not make a false premise true, and qualitative causal judgment remains
explicitly separate from mechanical proof.

### 6. CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing

Gou et al., [ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/fef126561bbf9d4467dbb8d27334b8fe-Abstract-Conference.html).

What it says: models can verify and revise outputs using external tools, while
the paper's evidence also shows that feedback-free self-correction is unreliable
and can degrade results.

Frankie transfer: test a bounded verify-then-revise pass using deterministic
schema, citation, arithmetic, timestamp, and contradiction tools before a
candidate reaches the existing independent adjudicator.

First gate: compare one-pass output, introspective self-critique, and
tool-grounded critique under matched budgets. Report corrected failures,
introduced failures, unsupported revisions, tool-evidence use, and every
protected-case regression.

Boundary: Frankie may revise a disposable candidate, never immutable evidence
or a resolved outcome. The same model's confidence or critique is not an
independent judge, and revision cannot bypass adjudication.

### 7. Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions

Hu, Wang, and McAuley, [ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/fd1eff9dd295df50a41f2521942fa31d-Abstract-Conference.html).

What it says: MemoryAgentBench evaluates four separate competencies - accurate
retrieval, test-time learning, long-range understanding, and selective
forgetting - in incremental multi-turn histories. Its evaluations show that
current memory agents do not master all four.

Frankie transfer: define the memory scorecard before selecting a memory design.
It directly tests recall of evidence and lessons, incorporation of causally
revealed outcomes, cross-session reasoning, and rejection of stale or corrected
material.

First gate: build sealed chronological Frankie histories containing long-range
dependencies, corrections, conflicts, and invalidations. Compare the frozen
baseline with one candidate wrapper, scoring each competency plus provenance,
unsupported recall, obsolete-memory use, latency, and downstream decision
quality.

Boundary: aggregate forecasting gain cannot compensate for failure on selective
forgetting, provenance, or unauthorized memory. Forgetting means excluding stale
material from serving, never deleting historical evidence.

### 8. HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models

Gutierrez et al., [NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/6ddc001d07ca4f319af96a3024f6dbd1-Abstract-Conference.html).

What it says: a knowledge graph plus Personalized PageRank can support
associative, multi-hop retrieval over newly accumulated information, providing
an alternative to flat or purely vector-based retrieval.

Frankie transfer: retrieve connected evidence spanning events, mechanisms,
prior failures, corrections, instruments, regimes, and market structures while
preserving a path back to immutable source nodes.

First gate: compare current retrieval with graph/PPR retrieval on sealed
multi-hop reasoning and failure-localization tasks. Hold storage, top-k returned
tokens, reader calls, and latency ceilings fixed; measure answer quality,
provenance, obsolete-node use, and downstream decisions.

Boundary: graph proximity is association, not causality. Generated links and
indexes are disposable derived views; they may not rewrite evidence, timestamps,
decisions, or outcomes.

### 9. HiAgent: Hierarchical Working Memory Management for Solving Long-Horizon Agent Tasks

Hu et al., [ACL 2025](https://aclanthology.org/2025.acl-long.1575/).

What it says: long agent histories can be organized into subgoals, with
completed subgoals summarized while detailed action-observation history is
retained for the active subgoal. This targets in-trial working memory rather
than cross-trial learning.

Frankie transfer: structure long research and forecasting runs around explicit
causal, data, retrieval, adjudication, and grading subgoals instead of an
ever-growing undifferentiated prompt.

First gate: compare full-history context with hierarchical subgoal context under
the same prompt-token, call, tool, and time ceilings. Score task completion,
decision invariance, omitted evidence, provenance, recovery after interruption,
and pass-to-fail cases caused by compaction.

Boundary: summaries are disposable working views. Any lost source link or change
to direction, magnitude, fired or stood-down sets, uncertainty, or safety state
caused by compaction rejects the candidate.

### 10. Progress & Compress: A Scalable Framework for Continual Learning

Schwarz et al., [ICML 2018](https://proceedings.mlr.press/v80/schwarz18a.html).

What it says: a separate active component learns a current task, after which new
competence may be consolidated into a protected knowledge base while preserving
older skills. The paper demonstrates the concept in classification and
reinforcement-learning domains, not language-agent forecasting.

Frankie transfer: the separation matches Frankie's intended shadow learner,
replay and critic, and deliberate consolidation path. Permanent Frankie stays
frozen while a disposable candidate learns from resolved outcomes.

First gate: compare frozen Frankie with an equal-compute shadow candidate across
sequential regimes. Report new-regime gain, every old-cohort regression,
calibration, forgetting, provenance, and rollback fidelity; do not summarize
these into one average.

Boundary: no automatic compression into permanent Frankie. Consolidation
requires untouched-forward evidence, zero protected regression, independent
criticism, reproducible lineage, rollback, and explicit human approval.

## Cross-cutting governance spine

These are not extra cognitive features and therefore are not ranked in the ten,
but they should shape every experiment:

- [AgentBoard](https://proceedings.neurips.cc/paper_files/paper/2024/hash/877b40688e330a0e2a3fc24084208dfa-Abstract-Datasets_and_Benchmarks_Track.html)
  supports trajectory-level rather than final-answer-only evaluation.
- [JudgeBench](https://openreview.net/forum?id=G0dksFayVq) warns that an LLM
  judge needs calibration against executable and human-labeled evidence.
- [AgentDojo](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html)
  supports adversarial testing of tool-using agents and untrusted content.
- [AI Control](https://proceedings.mlr.press/v235/greenblatt24a.html) supports
  treating monitoring and limited authority as independent control problems.
- [The ML Test Score](https://doi.org/10.1109/BigData.2017.8258038) and
  [Datasheets for Datasets](https://doi.org/10.1145/3458723) support production
  tests, provenance, and explicit dataset lineage.

The evaluator, permissions, immutable evidence, release split, rollback, and
promotion gate remain outside any candidate that can learn or modify itself.

## High-value watchlist

- [Reflexion](https://proceedings.neurips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html):
  post-feedback episodic lessons, but only after resolved external evidence.
- [ReasoningBank](https://proceedings.iclr.cc/paper_files/paper/2026/hash/980ea04d23d1f6908964eba2a74afe45-Abstract-Conference.html):
  compact strategy memories from trajectories, with self-judgment replaced by
  Frankie's resolved outcomes and independent criticism.
- [A-Mem](https://proceedings.neurips.cc/paper_files/paper/2025/hash/19909c36f51abc4856b4560aff3d36d6-Abstract-Conference.html):
  linked note-style memory, with dynamic changes limited to derived indexes.
- [Agent Workflow Memory](https://proceedings.mlr.press/v267/wang25bx.html):
  reusable procedural memory, kept in SHADOW until independently validated.
- [Teaching Models to Express Their Uncertainty in Words](https://openreview.net/forum?id=8s8K2UZGTZ):
  explicit uncertainty reporting and calibration.
- [Large Language Models Cannot Self-Correct Reasoning Yet](https://proceedings.iclr.cc/paper_files/paper/2024/hash/8b4add8b0aa8749d80a34ca5d941c355-Abstract-Conference.html):
  a direct challenge to feedback-free introspective correction.
- [Generative Agents](https://dl.acm.org/doi/10.1145/3586183.3606763),
  [Toolformer](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract-Conference.html),
  and [Reasoning with Language Model is Planning with World Model](https://aclanthology.org/2023.emnlp-main.507/):
  useful secondary designs for memory reflection, tool use, and planning.

The preprint-only papers already present in `frankie_paper_manifest.json` remain
research leads, not automatically canonical evidence. A recent preprint should
not displace stronger peer-reviewed work merely because it is newer.

## Common experimental contract

Every candidate experiment must:

1. freeze the current Frankie baseline, task set, graders, budgets, seeds,
   chronological splits, and protected cases before evaluation;
2. change one cognitive component at a time and preserve both independent
   reasoning lanes rather than allowing voting or averaging;
3. use the same model and backend where possible, with matched model calls,
   retrieved tokens, tool queries, storage, latency, and wall-clock ceilings;
4. permit learning only after the relevant outcome is causally revealed and
   preserve immutable raw evidence, decisions, and resolved outcomes;
5. prefer executable graders, calibrate any LLM judge, and record full
   trajectories rather than final answers alone;
6. report fail-to-pass and pass-to-fail cases by task, dependency depth, regime,
   safety state, uncertainty, and provenance, without hiding rare catastrophic
   regressions in an average;
7. keep candidate, development, release, untouched-forward, and adversarial sets
   separate to prevent repeated holdout adaptation;
8. preserve complete lineage from source evidence through retrieval, reasoning,
   revision, decision, outcome, lesson, and candidate build; and
9. keep all candidates disposable and reversible. No candidate may edit its own
   evaluator, permissions, gates, promotion rules, rollback, or permanent
   Frankie state.

## Suggested evaluation order

Start with the no-behavior-change CoALA map and the memory/evaluation scorecard.
Then test lower-authority components: typed structured reads, executable checks,
tool-grounded verification, and hierarchical working memory. Only after those
gates are reliable should Frankie test associative long-term retrieval,
multi-branch planning, or continual-learning candidates.

V4 should remain paused or unlaunched during this research phase. Research
completion does not itself authorize resumption; resumption requires a separately
reviewed experiment contract and explicit human decision.
