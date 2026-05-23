# Handoff: Daily Health, Strategy Families, On-Chain, Dipole Coupling

Date: 2026-05-16

## Current Goal

Build the platform into a high-selectivity crypto trading copilot. The key principle is:

- Strategy families can run in practice/autoresearch freely.
- Product exposure is allowed only when daily health says the family, bucket, venue, and daily loss state are acceptable.
- Continuation-style trading is removed from the active strategy universe.

## Core Architecture State

The platform now has these layers:

1. Families generate hypotheses.
2. Practice/autoresearch records outcomes.
3. Daily health report summarizes evidence.
4. Ticket/product layer obeys the report.
5. Dipole should become a coupling layer across market/news/on-chain/families, not a standalone entry trigger.
6. Refrag should become the strategy memory/invention layer that proposes new candidates for practice, never product exposure directly.

## Important Files Added

- `E:\Markets\daily_health_loader.py`
  - Loads `reports/daily_health_report_YYYYMMDD.json`.
  - Provides lookups for family, bucket, venue, and daily limit state.

- `E:\Markets\build_daily_health_report.py`
  - Builds daily health JSON/MD from replay result files and flat JSONL trade logs.
  - Supports:
    - `--input` replay result file or directory.
    - `--trade-log` flat JSONL practice/live/executor logs.
  - Computes family, bucket, venue, execution quality, and daily limit state.
  - Ignores open/pending trades from JSONL logs.

- `E:\Markets\daily_limits.py`
  - Tracks family and bucket daily PnL in R.
  - Classifies daily limit blockers.

- `E:\Markets\strategy_bucket_stats.py`
  - Bucket stats and health.
  - Venue stats and venue weights.

- `E:\Markets\onchain_features.py`
  - Canonical on-chain feature schema.
  - `classify_onchain_regime(...)`.
  - `onchain_allows_side(...)`.
  - Current labels:
    - `onchain_accumulation`
    - `onchain_distribution`
    - `onchain_rotation`
    - `onchain_stress`
    - `onchain_neutral`

- Strategy specs in `E:\Markets\research\strategy_specs\`
  - `news_breakout_btc_eth_v1.json`
  - `liquidity_squeeze_btc_eth_v1.json`
  - `vol_breakout_btc_eth_v1.json`
  - `basis_dislocation_btc_eth_v1.json`
  - `relative_strength_btc_eth_v1.json`
  - `session_structure_btc_eth_v1.json`

## Important Files Modified

- `E:\Markets\strategy_switcher.py`
  - Added explicit non-continuation families.
  - Added:
    - `strategy_family_health(...)`
    - `continuation_regime_ok(...)`
  - `MEAN_REVERSION_CHOP` can invert/fade the pressure side through side override.

- `E:\Markets\high_conviction_ticket.py`
  - Ticket generation now prefers the persisted daily health report when present.
  - Falls back to direct bucket/venue/daily-limit calculations when no report exists.
  - Ticket includes:
    - family health
    - bucket health
    - venue health
    - daily limit state
    - base go score and venue-adjusted go score.

- `E:\Markets\mock_trade_replay.py`
  - Added product-style gates:
    - `--enforce-bucket-health`
    - `--enforce-daily-limits`
  - Replay now writes:
    - `*_strategy_bucket_stats.json`
    - `*_strategy_venue_stats.json`
  - Trade records include bucket/session/profit-R and high-conviction ticket metadata.

- Configs:
  - `E:\Markets\bucket_thresholds.json`
  - `E:\Markets\daily_limits.json`
  - `E:\Markets\venue_prefs.json`

## Generated Reports / Smoke Outputs

- `E:\Markets\reports\daily_health_report_20260516.json`
  - Built from mixed replay + flat practice log.
  - Confirmed JSONL trade-log path works and open trades are ignored.

- `E:\Markets\mock_replay_switcher_invariant_smoke_out`
  - Smoke replay with bucket + daily limits enforced.
  - Result: zero product-eligible trades, which is expected when evidence gates are not satisfied.

## Validation Already Run

Python compile checks passed for the relevant modules:

```powershell
python -m py_compile build_daily_health_report.py onchain_features.py daily_health_loader.py high_conviction_ticket.py strategy_switcher.py strategy_bucket_stats.py daily_limits.py mock_trade_replay.py backend\api_server.py
```

JSON validation passed for:

```powershell
bucket_thresholds.json
daily_limits.json
venue_prefs.json
research\strategy_specs\*.json
```

## Key Interpretation

These changes improve product safety and evidence flow, but they do not prove better PnL yet.

What improved:

- Bad continuation buckets no longer contaminate product performance because the family is outside the active universe.
- Product layer has a single source of truth through daily health.
- More strategy families can enter practice without being promoted prematurely.
- Venue/execution quality is now part of daily health.
- On-chain can now be added as a feature/regime block.

What is not proven yet:

- A better active family has not been validated.
- `MEAN_REVERSION_CHOP`, `NEWS_BREAKOUT`, `LIQUIDITY_SQUEEZE`, etc. need autoresearch/practice runs.
- Product may correctly emit no trades until families earn `ok`.

## Dipole Direction

User strongly believes dipole should help combine families and find on-chain possibilities. Good design:

```text
market_dipole   = price/orderflow pressure
news_dipole     = narrative polarity/shock
onchain_dipole  = accumulation vs distribution / flow imbalance
family_dipole   = weighted vote across strategy families
coupling_score  = agreement among the independent dipoles
```

Use dipole as a coupling/alignment layer:

- Boost when independent sources align.
- Reduce size or block when they conflict.
- Track daily-health outcomes by dipole regime.

Do not make dipole a standalone entry strategy.

## Refrag Direction

Refrag belongs in the trade-strategy loop as memory plus controlled invention:

- Retrieve similar prior families, bucket outcomes, and contexts.
- Explain why a bucket/family won or failed.
- Propose candidate variants: new family ideas, parameter grids, feature combinations, or bucket splits.
- Feed those candidates into practice/autoresearch only.
- Let daily health decide promotion, demotion, kill, or continued learning.

Make this a self-evolving relay. When one family touches a BTC/ETH signal and is not a good match, it should leave a structured report for the next family:

- what market/news/on-chain context it saw
- why its rule shape did not fit
- which features had signal
- which features were missing or misleading
- what the next family should try differently

The next candidate should use that handoff to evolve toward the better fit instead of starting from scratch. For example, failed continuation evidence can become instructions for a liquidity-squeeze fade, a mean-reversion chop variant, or an on-chain-aware breakout block. Refrag preserves the relay memory; daily health judges the result.

Hard rule: Refrag is allowed to suggest experiments, not product trades. Product exposure still requires daily health `ok` status for family and bucket.

Implementation hook added:

- `E:\Markets\strategy_refrag_relay.py`
  - Builds `refrag_strategy_relay_v1`.
  - Produces family reports, poor-fit reasons, useful features, missing/misleading features, and next-family handoff messages.
- `E:\Markets\mock_trade_replay.py`
  - Writes `refrag_relay` into replay JSON.
  - Adds a **Refrag Relay** table to replay Markdown reports.
- `E:\Markets\market_strategy_autoresearch.py`
  - Writes `refrag_relay` with top autoresearch rule findings.
- `E:\Markets\strategy_family_evolution.py`
  - Writes per-family evolved-memory JSONs for self-training.
  - Stores run-local copies under `evolved_families\`.
  - Updates shared memory under `research\strategy_evolution\`.

## Suggested Next Steps

1. Add `dipole_coupling.py`
   - Compute `market_dipole`, `news_dipole`, `onchain_dipole`, `family_dipole`, `coupling_score`.
   - Include conflict flags such as `news_vs_onchain_conflict`.

2. Extend daily health report
   - Add `trades_by_onchain_regime`.
   - Add `trades_by_coupling_state`.
   - Add PnL/win rate by family + on-chain regime + coupling state.

3. Wire on-chain as a gate first
   - `NEWS_BREAKOUT` long blocked during `onchain_distribution`.
   - `NEWS_BREAKOUT` short blocked during `onchain_accumulation`.
   - `BASIS_DISLOCATION` uses on-chain accumulation/distribution as a crowding sanity check.
   - `LIQUIDITY_SQUEEZE` avoids fading too early during `onchain_stress`.

4. Run family practice/autoresearch
   - Start with `LIQUIDITY_SQUEEZE` because it directly tests failed continuation as a separate family.
   - Then `BASIS_DISLOCATION`.
   - Then `NEWS_BREAKOUT`.

5. Keep product exposure strict
   - Only families/buckets marked `ok` in daily health should surface as product trades.
   - Learning/deallocated/killed stays practice-only or hidden.

## Notes For Next Chat

- Do not touch the original `E:\od_autoresearch`; a clone exists at `E:\Markets\research\od_autoresearch_original`.
- The Perplexity/Nemotron toy strategy file was copied to `E:\Markets\research\perplexity_trade_strategies.py`; it is not production-integrated.
- Current repo has many pre-existing dirty/untracked files. Do not revert unrelated changes.
- Use `apply_patch` for edits.

## 2026-05-16 Continuation Update

The on-chain provider work is now partially scaffolded:

- `E:\Markets\onchain_features.py`
  - Added `OnchainProvider` protocol.
  - Added `build_onchain_features(...)` and normalized builder helpers.
  - Kept existing dict schema and `labels.onchain_regime` behavior.
  - Added optional future blocks:
    - `dex_cex_flows`
    - `perp_protocol`
    - `stables_health`

- `E:\Markets\onchain_providers\`
  - Added provider factory in `__init__.py`.
  - Added `nansen.py` and `amberdata.py` skeleton providers.
  - API endpoint paths and exact raw field names are still placeholders by design; replace from vendor docs before live use.

- `E:\Markets\feature_store.py`
  - Added append-only JSONL plus in-memory latest lookup for on-chain features.

- `E:\Markets\onchain_daemon.py`
  - Added CLI daemon loop:
    - `--provider nansen|amberdata`
    - `--assets BTC,ETH`
    - `--interval-seconds`
    - `--window-minutes`
    - `--once`

Dipole coupling was added as a coupling layer, not an entry signal:

- `E:\Markets\dipole_coupling.py`
  - Computes:
    - `market_dipole`
    - `news_dipole`
    - `onchain_dipole`
    - `family_dipole`
    - `coupling_score`
    - `coupling_state`: `aligned | neutral | conflicting`
  - Emits conflict flags such as `market_vs_onchain_conflict`.

- Daily health now includes:
  - `context.trades_by_onchain_regime`
  - `context.trades_by_coupling_state`
  - `context.trades_by_family_onchain_coupling`

- Replay/live practice trade records now persist:
  - `mean_dipole`
  - `dipole_coupling`
  - `high_conviction_ticket`
  - `onchain_features` when available through the latest feature store.

Validation run:

```powershell
python -m py_compile onchain_features.py dipole_coupling.py feature_store.py onchain_daemon.py onchain_providers\__init__.py onchain_providers\nansen.py onchain_providers\amberdata.py build_daily_health_report.py high_conviction_ticket.py mock_trade_replay.py backend\api_server.py
python build_daily_health_report.py --day 2026-05-16 --input mock_replay_switcher_invariant_smoke_out --trade-log backend_practice_trades.jsonl --reports-dir tmp_onchain_coupling_report_smoke --write-md
```
