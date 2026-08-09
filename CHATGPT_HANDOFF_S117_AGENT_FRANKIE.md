# ChatGPT Handoff — S117 Agent Frankie

**Branch:** `chatgpt/agent-frankie-s117`  
**Base:** `chatgpt/novel-edge-lab-s116`  
**Entry point:** `research/kalshi/agent_frankie.py`  
**S115 conformance:** `research/kalshi/FRANKIE_S115_IMPLEMENTATION.md`

## Status

Frankie is now aligned to Claude's registered S115 build brief rather than the earlier generic hybrid-agent plan.

Specification source used for conformance:

```text
branch: claude/kalshi-agents-coordinator-guard-sg0n15
path:   research/kalshi/FRANKIE_BUILD_BRIEF_S115.md
blob:   6cddd0c8aad6ddf75304220250193371301bf18f
```

The registry remains truth if a later registry revision disagrees with this handoff.

**CI:** GitHub Actions run `31288931300` passed the full pre-S115/supplemental suite after fixing a deterministic hash bug in the evolution layer. The next branch head retains those fixes. `spawn.py` remains unchanged.

## What Frankie is

Frankie extends the existing blind/refine machine; he does not replace it.

Existing machine remains responsible for:

- mission brief;
- canonical reasoning order;
- output contract;
- field inventory;
- specialist engine and gold-vault discipline.

Frankie adds:

- toolbox catalogue;
- explicit typed agent/render object;
- this lens's causal append-only book;
- generated specialist track record;
- grading duty after actuals become available;
- architecture A/B and held-out self-training gates;
- bounded cross-market/Novel reasoning and AWS orchestration.

Availability is additive and consultation is selective: whole plays remain available; the agent chooses what to consult rather than shrinking the toolbox.

## S115 build sequence

Implemented in the registered order:

```text
0  M-16 + A-61 + A-50
1  A-66 ownership table
2  A-59 + A-68 + A-62
3  A-65
4  A-67 arm 1 + A-69
5  A-67 arm 2 + A-42/FJ-1
LATER: A-5 -> A-63 + A-60 as one build
```

A-63/A-60 were deliberately NOT pulled into the first architecture test. The later band must be the empirical spread of the matched cohort, not a fitted-sigma shortcut.

## S115 implementation

### M-16 data-plane guard

`research/kalshi/databento_backfill_s115.py`

- repository-root absolute destinations, independent of cwd;
- guarded NG default is `.n.0`;
- rebinds the legacy writer destination before decoding;
- asserts physical destination byte growth;
- reports the actual destination, not merely the requested one.

The historical decoder remains untouched for reproducibility. Use the S115 wrapper for new operational pulls/redecodes.

### A-61 verification snapshot

`frankie_s115.pin_snapshot()` / `verify_snapshot()` pin the exact file hashes read by a verifier and fail if the tree changes underneath it.

### A-50 leak guard

Known outcome language in automatically loaded narrative files can hard-stop the run. A-67 also seals the experiment so neither arm's outcome may be narrated until both are complete.

### A-66 ownership

Ownership is at PART resolution:

| owner | part |
|---|---|
| D8 merge | canonical content store |
| A-62 | generated track-record index |
| A-65 | serving policy |
| A-68 | within-run lens journal |
| A-59 | render + typed contract |
| A-64 | candidate branching/control |

Sharing a layer is fine. Same-part ownership is not. Split the part more finely before inventing arbitration.

### A-59 NOOA structural layer

`research/kalshi/frankie_render_s115.py`

- explicit agent object/state;
- render through the existing `spawn.templates()` and `spawn.slots()` machinery;
- byte-identity assertion against canonical render semantics;
- malformed or under-specified posterior fails at the write boundary;
- execution can never be enabled by a posterior.

`research/kalshi/frankie_forecaster_s115.py` adds the toolbox, causal book, track-record attachment and grading duty without replacing the canonical predictor.

### A-68 lens book

Append-only JSONL per lens. An entry is visible only to strictly later days. Current/future rows are absent, not discouraged by prose. The book records this lens's own carried state/actions; it is not doctrine and cannot directly edit the brain.

`frankie_effects_s115.retention_falsifier()` explicitly declares one-session retention inert when matched same-lens events show no improvement.

### A-62 specialist track record

Generated from posteriors + actuals, never authored. It carries the named failure mechanism and what corrected it, not merely a score.

`specialist_prior_falsifier()` returns `INERT_CUT` when matched events show neither improvement in the named failure nor emission behavior.

### A-65 validated compaction

Same specialist/day full view versus changed view. Direction, magnitude, fired set and stood-down set are load-bearing. Movement rejects the view change. A supposedly lossy change with no posterior movement marks the test insensitive rather than blessing the compaction.

### A-67 architecture experiment contract

Both arms must be blind, share the same staged/pinned substrate, use separate noncanonical namespaces, and fix metrics before either arm runs.

Per-event outputs include:

- absolute error;
- zero-change, seasonal-naive and persistence benchmarks;
- emission ratio;
- band coverage;
- stand-down honesty;
- derived-vs-fitted provenance.

No pooled above/below scalar is emitted.

### A-69 self-training + A-42/FJ-1

- blind wall remains up during walked-corpus forecasts;
- walked and head event IDs must be disjoint;
- corpus and held-out results are always reported together;
- corpus-only improvement -> `SCRAP_RECALL_OR_OVERFIT`;
- FJ-1 labels must exist in `failure_localization.py`'s frozen paper/local-extension table;
- root-cause doctrine remains earliest unrecovered failure, not loudest final symptom.

## Research layer

`research/kalshi/frankie_paper_manifest.json` is now `READY` with nine reviewed papers:

- NOOA — arXiv:2607.20709
- ACM long horizon — 2607.23809
- Kernel Forge — 2607.24762
- ACM lifecycle/architecture — 2607.21503
- Self-Improvement Survey — 2607.13104
- Adaptive Auto-Harness — 2606.01770
- RSEA held-out selection — 2606.28374
- MOSS — 2605.22794
- AgentDevel — 2601.04620

The supplemental evolution layer keeps explicit strategy/skills/playbook state, requires isolated trials for source-affecting candidates, rejects pass->fail regressions, requires a precommitted held-out improvement, and cannot apply its own source changes.

## AWS runtime

Retained from the original S117 build:

- SQS long-poll worker with SNS-envelope support;
- 15-minute visibility lease;
- first-writer event-hash idempotency;
- local + optional S3 evidence;
- Bedrock lane + optional independent OpenAI critic;
- hardened systemd worker;
- disabled-by-default reflection timer;
- least-privilege IAM template;
- no order/execution route.

## What is NOT complete evidence yet

Do not mark these DONE merely because their harness/gate exists:

1. **M-16 physical repair** — move or free-redecode the already-paid head trades/L1 jobs into the canonical root data plane and verify actual landing.
2. **g6-g16 actual rebuild** — rebuild missing actuals on the basis each original STATE used; do not silently mix `.v.0` and `.n.0`.
3. **A-67 arm 1** — actual blind vs Frankie run on untouched head not yet executed by this branch.
4. **A-69** — actual self-training/grading on reconstructed walked corpus not yet executed.
5. **A-67 arm 2** — three sequential retention blocks not yet executed.
6. **A-42** — production FJ-1 run not yet executed; adapter/validation is wired.

Use:

```bash
python research/kalshi/frankie_s115_status.py
```

to report readiness without promoting missing evidence.

## Key commands

```bash
cd research/kalshi
python agent_frankie.py health
python agent_frankie.py selftest
python frankie_s115_status.py
python frankie_forecaster_s115.py prepare-day BLD-1 g24 20260720 B
python databento_backfill_s115.py pull --symbol NG --roll n --schema trades --start YYYY-MM-DD --end YYYY-MM-DD
```

## Permanent safety boundaries

- original `spawn.py` untouched and pinned;
- no direct brain edit;
- no venue create/amend/cancel client;
- no Kalshi/tastytrade execution credentials;
- no automatic Git mutation or production promotion;
- no fitted threshold/weight/coefficient introduced by Frankie evolution;
- no LLM in the market-data hot path;
- every Frankie decision/evolution artifact carries `execution_enabled=false`.
