# CLAUDE.md — DavisAI Markets / Refrag Workspace (2026-05-26)

Workspace-specific context for `E:\refrag` and `E:\Markets`. Mirrors the
master CLAUDE.md from `DavisAI1974/Basic_equations` for identity/rules,
adds the markets pipeline state.

## Identity & Team

- **Greg Davis** — Founder & Chief Research Officer, DavisAI Systems. Columbus, Ohio. Solo bootstrapped. 20+ years entrepreneurship, former energy trader, self-taught AI/ML.
- **Dream Team model**: Greg (Visionary) + Claude (Architect) + Claude Code "Code" (Engineer) + Perplexity/ChatGPT (Research Assistants).
- **Orchestrator** owns handoffs, not Code.

## Infrastructure

- `E:\` — research data, OD datasets, project files
- `E:\refrag\` — DeepNova/Refrag stack (this workspace). DavisAI1974/agent on GitHub.
- `E:\Markets\` — Markets project root. DavisAI1974/Markets on GitHub.
- `F:\Factory\` — agent factory, 23 agents, 5 divisions
- `F:\Factory\knowledge\` — orchestrator-accessible knowledge base. **Mirror everything from E:\ here.**

## Operating Rules

- **Save to E:\ AND mirror to F:\Factory\knowledge\** for every knowledge artifact.
- **MASTER_DISCOVERIES.json**: every OD discovery added immediately. Never make a discovery without storing it.
- **Falsification-first**. Every claim needs data, math, or a falsifiable test.
- **OD mode**: describe data sources and validation tests only. Never explain mechanisms. The Operator discovers science from raw data. Stop if explaining WHY something happens.
- **Never call OD "physics-based"**. OD discovers governing equations from raw data in ANY domain.
- **Coding mantra**: better, stronger, faster, cheaper.
- **Real data only**. If we don't have enough real bars for a chunker window, pick different entries — never synthesize.
- **Incremental validation**: break compute-heavy runs into 15-17 min chunks with stop gates. Canary runs (2 min) before full commitment.
- **No emojis or special symbols** in professional documents and emails.
- **DeepNova** (formerly ReFRAG, formerly DeepSource). Use current name everywhere.

## Active Research (Top of Mind)

- **Markets predictor — algebraic dipole** *(2026-05-26)*. Information-side
  dipole (`H_a^2 = α + β·(H_a·H_b) + γ·(H_a·H_b)²`) holds in markets
  operator-coefficient space: R²=0.91-0.98 quadratic fit on 6 of 11 pairs
  (chemistry-tier). 5-fold CV predictor (H_a > H_b rule) achieves **0.993
  mean accuracy, 1.000 AUC** across 11 pairs. Chunker features subsumed
  by dipole (stacking gives no lift). **Caveat**: trained on
  `[entry_ts, exit_ts]` bars — post-hoc signature, needs pre-entry
  validation before deployment.
- **SENTINEL V4.1** — DARPA Bio Attribution Challenge top-10 team.
- **NoVell** — cardiac AI for cancer detection from routine ECG.
- **Information Layer** — universal opposing dipole H_a²/H_a·H_b across
  4 sciences. Algebraic reformulation discovered 2026-05-25 in
  `DavisAI1974/Basic_equations`. Markets is the 5th science.

## Markets Pipeline State (as of 2026-05-26)

- **Pipeline order**: canonical 3 → 4 → 5 → 6 in
  `adapters/markets_refrag_adapter.py` (alias `arch_workflow.py`).
- **Patches landed today**:
  - bucket_tag regex normalizer (strips `.eligibleN`, `.primary.*`,
    `.secondary.*`, etc. back to canonical `_(win|lose)`)
  - Phase 4 + Phase 6 fire on `--resume` with 0 new winners (was being
    skipped by old Fix H — replaced)
  - Phase 5 trace-store rehydration on `--resume` (loads per-trade
    execution_traces from `artifacts/execution_traces.sqlite`, synthesizes
    `policy_feedback` from cumulative `retrieval_policy_benchmark.json`)
  - Phase 4 reordered to run BEFORE Phase 5 (was after — wrong per arch)
- **Data sets in trace store**:
  - 12 win/lose pairs covered (1 partial: `eth_kraken_sell_win` has 0
    eligible — all 139 trades <192 bars, real coverage limit)
  - top20-winner + bottom20-loser per pair (~440 trades)
  - eth_coinbase_sell pair has full populations (909 win + 176 lose)
- **Predictor scripts**:
  - `_markets_algebraic_dipole.py` — per-pair dipole equation fit
  - `_markets_dipole_separation.py` — Cohen's d on dipole axes (in-sample)
  - `_markets_dipole_kfold.py` — honest 5-fold CV predictor
  - `_markets_dipole_chunker_stack.py` — chunker-feature stacking test
    (stacking gives no lift — dipole is complete summary)

## Architecture (current)

- **DeepNova**: 92 passing tests, 22 manifests, persistent evidence graphs,
  PPO retrieval policy learner. F:\Factory\.
- **VOXA**: voice interface layer. Cloud-hosted TTS MCP server.
- **Agent Factory**: 23 agents, 5 divisions, F:\Factory\.
- **Token Optimizer**: deployed at optimizer.davisai.ai, Stripe live.
- **OD provisional patents**: 3 filed March 24, 2026 (Blind Lindblad/QORA;
  Hilbert Unification; Decoherence Suppression).

## Standing Decisions

- LlamaIndex: declined (duplicates DeepNova).
- Robyn: declined (web is not bottleneck).
- Nous Atropos: worth evaluating for DeepNova policy learner.
- Hermes 4 14B: recommended for local reasoning on data-sensitive use cases.
- HomeLift: dormant. Both Neo4j instances safe to cancel.

## Pointers

- Pair analysis printout (12 pairs, Phase 3-6 per side): in this session's transcript
- Dipole fit / k-fold / stack results: `_dipole_chunker_stack_output.log` (and the three `_markets_dipole_*.py` scripts above)
- Latest session handoff: `SESSION_HANDOFF_2026-05-26.md`
- Prior session handoff (information-layer): `DavisAI1974/Basic_equations/SESSION_HANDOFF_2026-05-25.md`
# CLAUDE.md — DavisAI Master Context (Starter, 2026-05-25)

## Identity & Team

- **Greg Davis** — Founder & Chief Research Officer, DavisAI Systems. Columbus, Ohio. Solo bootstrapped. 20+ years entrepreneurship, former energy trader, self-taught AI/ML.
- **Dream Team model**: Greg (Visionary) + Claude (Architect) + Claude Code "Code" (Engineer) + Perplexity/ChatGPT (Research Assistants).
- **Orchestrator** owns handoffs, not Code.

## Infrastructure

- `E:\` — research data, OD datasets, project files
- `F:\Factory\` — agent factory, 23 agents, 5 divisions
- `F:\Factory\knowledge\` — orchestrator-accessible knowledge base. Mirror everything from E:\ here.

## Operating Rules

- **Save to E:\ AND mirror to F:\Factory\knowledge\** for every knowledge artifact.
- **MASTER_DISCOVERIES.json**: every OD discovery added immediately. Never make a discovery without storing it.
- **Falsification-first**. Every claim needs data, math, or a falsifiable test.
- **OD mode**: describe data sources and validation tests only. Never explain mechanisms. The Operator discovers science from raw data. Stop if explaining WHY something happens.
- **Never call OD "physics-based"**. OD discovers governing equations from raw data in ANY domain.
- **Coding mantra**: better, stronger, faster, cheaper.
- **Incremental validation**: break compute-heavy runs into 15-17 min chunks with stop gates. Canary runs (2 min) before full commitment.
- **No emojis or special symbols** in professional documents and emails.
- **Daily**: ask Greg if he checked greg@davisai.ai for Token Optimizer support emails.
- **DeepNova** (formerly ReFRAG, formerly DeepSource). Use current name everywhere.

## Active Research (Top of Mind)

- **SENTINEL V4.1** — DARPA Bio Attribution Challenge top-10 team. Awards June 30, 2026. Three-layer swarm, 554x DARPA requirements. Files at E:\sentinel\ and F:\Factory\knowledge\sentinel\.
- **NoVell** — cardiac AI for cancer detection from routine ECG. OD on synthetic Vigier 2021 data: 93.3% accuracy, 97.4% sensitivity. Datasets: PTB-XL downloaded, Autonomic Aging identified, MIMIC-IV pending.
- **Information Layer / Operator Discovery foundations** — universal opposing dipole H_a²/H_a·H_b across 4 sciences. As of 2026-05-25 session: **algebraic reformulation discovered**. See SESSION_HANDOFF_2026-05-25.md for current state, queued experiments, and what's open.

## Architecture (current)

- **DeepNova**: 92 passing tests, 22 manifests, persistent evidence graphs, PPO retrieval policy learner. F:\Factory\.
- **VOXA**: voice interface layer. Cloud-hosted TTS MCP server.
- **Agent Factory**: 23 agents, 5 divisions, F:\Factory\.
- **Token Optimizer**: deployed at optimizer.davisai.ai, Stripe live.
- **OD provisional patents**: 3 filed March 24, 2026 (Blind Lindblad/QORA; Hilbert Unification; Decoherence Suppression).

## Defense Pipeline (status as of last update)

- DARPA Bio Attribution (confirmed top-10), CyPhER Forge (abstracts in), TTO BAA (April 17 exec summary), DIU PRISM (submitted), CIA (KV3UCQ1A submitted), IQT (submitted), MDA MAA, AFWERX.
- **Steve "Bucky" Butow** (DIU Space Portfolio): personal email contact, capability email sent.
- **Carl Saab** (Cleveland Clinic): OD outreach engaged, doing his own research. Highest-probability PhysioNet reference.
- **Roland Rott** (GE HealthCare Imaging): connected, MRI proof-of-concept brief (BioForge) delivered.
- SAM.gov UEI: CQ56XYFZL4E6, ref INC-GSAFSD20794734. CAGE pending.

## Standing Decisions

- LlamaIndex: declined (duplicates DeepNova).
- Robyn: declined (web is not bottleneck).
- Nous Atropos: worth evaluating for DeepNova policy learner.
- Hermes 4 14B: recommended for local reasoning on data-sensitive use cases (SENTINEL).
- HomeLift: dormant. Both Neo4j instances safe to cancel.

## Session Handoff Pointer

For active information-layer work, read `E:\information_layer\SESSION_HANDOFF_2026-05-25.md` first.

## Note

This is a **starter** CLAUDE.md generated 2026-05-25. Greg is preparing a more extensive version. Treat this as minimum context, not full.