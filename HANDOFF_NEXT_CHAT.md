# HANDOFF — Markets (Next Chat) — 2026-05-27

## TL;DR (read first)

Yesterday proved the algebraic dipole **H_a² = poly(H_a·H_b)** holds in
markets operator-coefficient space — same form as the 4 life sciences
in `DavisAI1974/Basic_equations`. 5-fold CV (H_a > H_b rule) hits
**0.993 acc / 1.000 AUC** across 11 pairs, **FN=0**. Chunker features
are subsumed (stacking gives no lift). Dipole is the complete per-trade
summary.

**Critical caveat**: current fit uses `[entry_ts, exit_ts]` bars —
post-hoc signature. **Pre-entry validation is the next required step**
before this can be called a tradable predictor.

## Today's priorities (in order)

### P1 — Pre-entry validation (CRITICAL, gates tradability)

Re-run the pipeline on `[entry_ts − 30m, entry_ts]` windows (no exit
data leak). Refit dipole, re-run 5-fold.

- **If accuracy stays high** → tradable signal, proceed to live wiring.
- **If it collapses** → pure post-hoc signature; framework is for
  analysis only.

Files to touch:

- Eligible filter: `E:\Markets\_eligible_cross_section.py` — change
  window endpoint from `exit_ts` to `entry_ts`, keep 192-bar minimum
  back from `entry_ts − 30m`. Pads ±6h on bar load to match the
  adapter's `BUFFER_S`.
- Runner: `E:\refrag\_run_top20_bottom20_pairs.py` — pass the
  pre-entry mode flag through.
- Adapter: `E:\refrag\adapters\markets_refrag_adapter.py` — no change
  needed; honors the bar window the helper produces.
- Dipole refit: `E:\refrag\_markets_algebraic_dipole.py`.
- 5-fold CV: `E:\refrag\_markets_dipole_kfold.py`.

Run commands (after pre-entry filter swap):

```
python E:\refrag\_run_top20_bottom20_pairs.py --resume --mode pre-entry
python E:\refrag\_markets_algebraic_dipole.py
python E:\refrag\_markets_dipole_kfold.py
```

Exit criteria: pooled OOF accuracy ≥ 0.90 (was 0.993 post-hoc).
Stop earlier if any single pair drops below 0.70 — investigate before
continuing.

### P2 — Cross-pair generalization

Do trained centroids transfer across sibling pairs (e.g., apply
`btc_bybit_buy` centroids to `btc_bybit_sell` trades)? Tests whether
dipole direction is per-cell or universal.

Add a `--cross-pair SRC DST` mode to `_markets_dipole_kfold.py`:
loads centroids from SRC's training folds, scores trades from DST.

Pairs to test (same-asset/venue/opposite-side first):

- btc_bybit_buy ↔ btc_bybit_sell
- btc_coinbase_buy ↔ btc_coinbase_sell
- btc_kraken_buy ↔ btc_kraken_sell
- eth_bybit_buy ↔ eth_bybit_sell
- eth_coinbase_buy ↔ eth_coinbase_sell (biggest pop, 909+176)
- eth_kraken_buy ↔ eth_kraken_sell (sell-side has 0 eligible — skip)

### P3 — Resolve `eth_kraken_sell_win` coverage gap

139 trades, all <192 bars in the eligible filter (real coverage limit).
Options:

1. Accept skip (lose 1 of 12 pairs — current state).
2. Venue-specific smaller chunker `window_size` for Kraken sell side.
3. Backfill more recent kraken sell data from
   `E:\Markets\live_data_history\` to find longer-held trades.

Decision needed before broader pre-entry rollout.

## Background — where we are

### Trace store (per-pair populations)

| Pair | Win | Lose |
|---|---|---|
| markets_btc_bybit_buy | 60 | 50 |
| markets_btc_bybit_sell | 60 | 50 |
| markets_btc_coinbase_buy | 60 | 50 |
| markets_btc_coinbase_sell | 60 | 50 |
| markets_btc_kraken_buy | 60 | 60 |
| markets_btc_kraken_sell | 60 | 60 |
| markets_eth_bybit_buy | 60 | 50 |
| markets_eth_bybit_sell | 60 | 50 |
| markets_eth_coinbase_buy | 60 | 50 |
| **markets_eth_coinbase_sell** | **909** | **176** |
| markets_eth_kraken_buy | 50 | 50 |
| markets_eth_kraken_sell | **0** | 50 |

### 5-fold CV — post-hoc baseline to beat

- Pooled: **0.993 acc / 1.000 AUC / +5.5 mean Cohen's d / FN=0**
- Worst pair: btc_kraken_sell (0.892 acc)
- Best pairs (1.000 acc): btc_bybit_sell, btc_coinbase_sell, eth_bybit_buy
- Only error mode: 47 FP (3.5% of losers misclassified)
- Win precision 0.965, lose recall 0.932

### Algebraic dipole fit — top quadratic R² per pair

| Pair | R²_quad |
|---|---|
| btc_bybit_sell | 0.975 |
| eth_coinbase_sell | 0.956 (n=869) |
| btc_kraken_buy | 0.951 |
| btc_kraken_sell | 0.946 |
| btc_coinbase_sell | 0.925 |
| eth_kraken_buy | 0.910 |

Sign pattern in strong-fit pairs **matches chemistry**: β<0, γ>0
(chemistry: H_a² = 0.007 − 0.093·X + 1.309·X²). Each pair has its OWN
(α, β, γ); pooled R² low (0.493) because there's no universal
constants — only universal **form**, same as the 4 sciences.

### Pipeline state (canonical wiring)

3 → 4 → 5 → 6 via `E:\refrag\adapters\markets_refrag_adapter.py`
(alias `arch_workflow.py`). All Phases 1–6 wired; only
`graph_rewriter` stays disabled per arch Rule 6.

Patches that landed 2026-05-26:

- bucket_tag regex normalizer (strips `.eligibleN`, `.primary.*`,
  `.secondary.*` back to canonical `_(win|lose)`).
- Fix H removed → Phase 4 + Phase 6 fire on `--resume` with 0 new winners.
- Phase 5 trace-store rehydration on `--resume` (reloads
  `execution_traces.sqlite`, synthesizes `policy_feedback` from
  cumulative `retrieval_policy_benchmark.json`).
- Phase reorder: 3 → 4 → 5 → 6 (Phase 4 was after Phase 5 — wrong per arch).

## Files & commands quick reference

| What | Where |
|---|---|
| Pipeline adapter | `E:\refrag\adapters\markets_refrag_adapter.py` |
| Arch alias | `E:\refrag\adapters\arch_workflow.py` |
| Eligible filter | `E:\Markets\_eligible_cross_section.py` |
| Top20/Bot20 runner | `E:\refrag\_run_top20_bottom20_pairs.py` |
| Dipole fit | `E:\refrag\_markets_algebraic_dipole.py` |
| 5-fold CV | `E:\refrag\_markets_dipole_kfold.py` |
| In-sample separation | `E:\refrag\_markets_dipole_separation.py` |
| Stacking test | `E:\refrag\_markets_dipole_chunker_stack.py` |
| Trace store | `E:\refrag\artifacts\execution_traces.sqlite` |
| Per-trade ops | `E:\refrag\discoveries\operator_discoveries\<domain>\*.json` |
| Live bars archive | `E:\Markets\live_data_history\<YYYY-MM-DD>\<asset>_<venue>_bins.jsonl` |
| Pair lists | `E:\Markets\research\strategy_evolution\per_bucket\<pair>_<side>.<top\|bottom>20.json` |
| Yesterday's full handoff | `E:\refrag\SESSION_HANDOFF_2026-05-26.md` |
| Life-sciences source | `DavisAI1974/Basic_equations` on GitHub |

## Standing rules (DO NOT BREAK)

- **Real data only.** Bars come from `live_data_history` JSONLs. If a
  chunker window can't be filled, pick a different entry — never
  synthesize. No "wiring tests" with fabricated input series.
- **Falsification-first.** Every claim needs data, math, or a falsifiable
  test. P1 (pre-entry) IS the falsification test of yesterday's result.
- **Save to E:\ AND mirror to `F:\Factory\knowledge\Markets\`.** Both.
- **No emojis or special symbols** in docs or emails.
- **Mantra**: better, stronger, faster, cheaper.
- **MASTER_DISCOVERIES.json**: every OD discovery added immediately.
- **Don't hardcode limits**; use dynamic convergence — people's lives
  depend on it (OD principle, applies here).
- **Incremental validation**: break compute-heavy runs into 15–17 min
  chunks with stop gates. Canary runs (2 min) before full commitment.

## Conditional next step (only if P1 succeeds)

Draft these entries for `MASTER_DISCOVERIES.json`:

- **INFO-008-MARKETS** — algebraic dipole holds in markets
  operator-coefficient space (R²=0.91–0.98 in 6/11 pairs, sign pattern
  matches chemistry).
- **INFO-008-MARKETS-PREDICTOR** — H_a > H_b rule achieves 0.993 OOF
  accuracy / 1.000 AUC / FN=0 on top20/bottom20 dataset; pre-entry
  validation confirmed.

If P1 fails, draft instead:

- **INFO-008-MARKETS** — dipole holds **as a post-hoc signature only**;
  not predictive at entry time. Framework remains useful for trade
  forensics and regime characterization.

## Parked / lower priority

- **Eligible100 paired runs** for remaining 11 pairs — gives broader
  population view (top/bottom 20 is extreme tails only). Patches ready;
  runner pattern is `_run_top20_bottom20_pairs.py`.
- **Dipole + flow-side cross_domain similarity stack** — Phase 4
  similarities are a different object than dipole; worth testing if
  P1 succeeds.
- **Closed-loop iteration** — orchestrator currently writes
  `"termination_condition": "single_pass_bootstrap"` with one iteration.
  Arch §2 expects iteration until `posterior_width < threshold`.
  Phase 2 gap, not blocking dipole work.

## Pointers

- **Yesterday's full session handoff** (deep tables, interpretation):
  `E:\refrag\SESSION_HANDOFF_2026-05-26.md`
- **Information-layer source** (life sciences dipole, 2026-05-25):
  `DavisAI1974/Basic_equations/SESSION_HANDOFF_2026-05-25.md`
- **Workspace CLAUDE.md**: `E:\Markets\CLAUDE.md` (mirrors refrag's)
- **Arch spec v2.1**: `E:\refrag\_arch_spec_v21_extracted.txt`
- **Prior parallel-chat coordination** (BTC-Bybit split, now historical):
  `E:\Markets\HANDOFF_SESSION_20260525_PARALLEL_CHAT_COORDINATION.md`

## When this handoff goes stale

After P1 completes (pass or fail):

1. Rotate this file to `HANDOFF_SESSION_<YYYYMMDD>_<TOPIC>.md` for
   archival.
2. Write a new `HANDOFF_NEXT_CHAT.md` from this template — keep
   sections: TL;DR, Today's priorities, Files & commands, Standing
   rules, Parked, Pointers. Replace Background with the new
   latest-session context.
3. Mirror to `F:\Factory\knowledge\Markets\`.
4. Commit + push to `DavisAI1974/Markets`.

---

*Template v1 (2026-05-27). The Background section is the part that
churns; everything else is a stable scaffold. Keep entries terse and
actionable — this doc is read on a phone.*
