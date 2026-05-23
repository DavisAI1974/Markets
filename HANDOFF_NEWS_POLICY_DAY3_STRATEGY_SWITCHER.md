# Markets Handoff: News Policy, Day 3 Replay, Strategy Switcher

Last updated: 2026-05-16

## Current Goal

We are improving the BTC/ETH markets platform so daily/intraday news can inform auto-trade decisions without letting weak headlines blindly open trades.

Working doctrine:

- Routine news modifies score, risk, allowed strategies, and blockers.
- Shock news can start defensive actions: exit longs, exit shorts, reduce exposure, pause new entries, allow hedges.
- Fresh news-started directional entries should be gated by shock policy, market confirmation, or a strategy-specific playbook.
- News dipole is useful, but not sufficient alone.

The next chat will receive a Perplexity-generated trade strategies section with a backtest simulator and automated strategy-switching mechanism.

## Files Changed Or Added

Core news/policy:

- `news_ingest_rss.py`
  - Added simple deterministic NLP enrichment:
    - `is_followup`
    - `has_numeric_size`
    - `magnitude_bps_hint`
  - Classifier version is now `keyword_v0+nlp_v1`.
  - Ethereum Foundation feed is now `PROTOCOL_PRIMARY`.

- `news_coupling_research.py`
  - Expanded `SOURCE_WEIGHTS`:
    - `PRIMARY`: 1.0
    - `EXCHANGE_PRIMARY`: 0.95
    - `PROTOCOL_PRIMARY`: 0.9
    - `TRUSTED_MEDIA`: 0.8
    - `AGGREGATOR`: 0.6
    - `SOCIAL`: 0.35

- `build_news_policy_from_coupling.py`
  - New script.
  - Reads `news_coupling_results.json`.
  - Writes `news_policy.json`.
  - Derives per category/bias/horizon policy entries:
    - edge vs placebo
    - hit rate
    - volume ratio
    - risk multiplier
    - confirmation requirement
    - shock starter actions
  - Production thresholds are intentionally conservative.

- `build_daily_news_context.py`
  - Now accepts `--policy news_policy.json`.
  - Embeds selected policy entry into each asset context.
  - Adds:
    - `starter_valid_until`
    - `starter_category`
    - `starter_horizon_min`
    - `policy`
    - `news_dipole`

- `daily_news_context.py`
  - Added policy/starter fields to `AssetNewsContext`.
  - Added `adjust_present_score_with_news(...)`.
  - Routine news now adds a bounded score modifier.
  - Expired starter actions are treated as context only.

Backend / reports:

- `backend/api_server.py`
  - Trade option generation now applies `adjust_present_score_with_news(...)` before option selection.
  - Still applies blockers and risk scaling through `news_adjusted_trade_option(...)`.

- `present_signal_strength_reanalysis.py`
  - Latest snapshot now shows:
    - base market score
    - news-adjusted score
  - This makes it visible whether news raised, lowered, or blocked a setup.

- `scripts/run_present_signal_strength_update.ps1`
  - Morning workflow order is now:
    1. ingest news
    2. run coupling research
    3. build `news_policy.json`
    4. build `daily_news_context.json`
    5. run present-strength reanalysis

Replay:

- `news_dipole_replay.py`
  - Standalone news-dipole selector.
  - Useful for research, not live trading by itself.

- `mock_trade_replay.py`
  - Added safer replay controls:
    - `--block-kraken-buys`
    - `--buy-score-premium`
    - `--require-news-alignment`
    - `--news-alignment-min-abs-dipole`
    - `--early-loss-bps`
    - `--early-loss-after-minutes`
  - Fixed exit ordering so degradation/early-loss checks happen before max-hold expiry.
  - Mock trade records now preserve `daily_news_context` and `daily_news_status`.

Docs:

- `TRADE_LOGIC.md`
- `DAILY_NEWS_TRADE_CONTEXT.md`
- `NEWS_EVENTS_SCHEMA.md`

## Generated Artifacts

- `news_policy.json`
  - Strict production policy.
  - Current result: 0 enabled rules because sample size is too small.

- `news_policy_replay_lenient.json`
  - Research-only lenient policy.
  - Current result: 1 enabled low-sample rule.
  - Do not use as live policy.

- `daily_news_context.json`
  - Strict daily context generated from current events/policy.

- `daily_news_context_auto_replay.json`
  - Replay-only context that allows auto-trade so historical behavior can be inspected.

- `daily_news_context_replay_lenient.json`
  - Research-only daily context from lenient policy.

## Validation Completed

Compile passed:

```powershell
python -m py_compile mock_trade_replay.py daily_news_context.py build_daily_news_context.py build_news_policy_from_coupling.py news_ingest_rss.py present_signal_strength_reanalysis.py backend\api_server.py
```

Full news workflow smoke passed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_present_signal_strength_update.ps1 -OutputDir pass24_news_policy_smoke_out -NewsCouplingOutputDir pass24_news_coupling_smoke_out -NoMultiSignalPelt
```

Smoke results:

- News events: 29
- News dipole buckets: 17
- Coupling observations: 64
- Placebo observations: 8381
- Strict enabled policy rules: 0

## News Dipole Research Result

Standalone news dipole was tested.

Day 2 specific window:

- 0 trades because no news buckets aligned with that replay window.

Overlapping market/news window:

- 14 trades
- 50.0% win rate
- P&L: `-$17.97`
- Bearish/news-short dipoles: 7/7 winners, `+$1.38`
- Bullish/news-long dipoles: 0/7 winners, `-$19.34`

Read:

- News dipole alone is not a strategy.
- Bearish news was more useful than bullish news in the current tiny sample.
- Negative shock/news should be a stronger exit/hedge/short starter than bullish news is a long starter.

## Day 3 Replay Results

Baseline refined day 3 first 6 hours:

Command shape:

```powershell
$env:MARKETS_WATCH_DAILY_NEWS_CONTEXT='E:\Markets\daily_news_context_auto_replay.json'
python mock_trade_replay.py --data-dir . --output-dir mock_replay_refined_day3_first6_out --start-hour 48 --hours 6 --stride-minutes 15 --checkpoint-hours 0 --disable-pressure-scout --block-watch --min-score-floor 55
```

Result:

- 26 closed scenario trades
- Total P&L: `-$135.03`
- Buys: 18 trades, `-$111.88`
- Sells: 8 trades, `-$23.16`
- Worst pattern: ETH Kraken buys held to max hold.

Remaining 18 hours:

```powershell
$env:MARKETS_WATCH_DAILY_NEWS_CONTEXT='E:\Markets\daily_news_context_auto_replay.json'
python mock_trade_replay.py --data-dir . --output-dir mock_replay_refined_day3_remaining18_out --start-hour 54 --hours 18 --stride-minutes 15 --checkpoint-hours 0 --disable-pressure-scout --block-watch --min-score-floor 55
```

Result:

- 88 closed scenario trades
- Total P&L: `-$136.58`
- Buys: 72 trades, `-$125.75`
- Sells: 16 trades, `-$10.83`
- Main loss source: Kraken buys, especially ETH Kraken.

Safer v2 first 6 hours:

```powershell
$env:MARKETS_WATCH_DAILY_NEWS_CONTEXT='E:\Markets\daily_news_context_auto_replay.json'
python mock_trade_replay.py --data-dir . --output-dir mock_replay_refined_day3_first6_safer_v2_out --start-hour 48 --hours 6 --stride-minutes 15 --checkpoint-hours 0 --disable-pressure-scout --block-watch --min-score-floor 55 --block-kraken-buys --buy-score-premium 10 --require-news-alignment --news-alignment-min-abs-dipole 0.25 --early-loss-bps 6 --early-loss-after-minutes 3
```

Result:

- 10 closed scenario trades
- Total P&L: `-$49.91`
- Wins: 2
- Sides:
  - Sells: 8
  - Buys: 2
- Venue P&L:
  - Kraken: `+$0.99`
  - Coinbase: `-$50.90`
- Close reason after exit-order fix:
  - `present_score_degraded`: 10

Read:

- The safer controls reduced damage from `-$135.03` to `-$49.91`.
- Blocking Kraken buys helped.
- News alignment helped by eliminating many bad longs.
- Still not profitable. Strategy identity is the missing layer.

## Why Trades Are Bad Beyond Long Holds

1. Weak directional quality.
   The system detects pressure, but pressure is not automatically tradeable edge after fees, spread, and chop.

2. Long bias was bad.
   Buys dominated losses on day 3.

3. Venue-specific failure.
   Kraken buys were especially bad before blocking. This likely reflects microstructure, data behavior, or venue-specific flow.

4. Score bands are not calibrated enough.
   `70+` did not guarantee good trades. Some high-score setups were exhausted or wrong-regime.

5. News alignment is useful but not sufficient.
   News helped filter bad trades, but did not create standalone edge.

6. No explicit strategy identity yet.
   Current logic mixes:
   - momentum follow
   - mean reversion
   - shock-news defensive action
   - liquidity sweep/fade
   - pressure continuation
   - no-trade chop

   These need different entries, exits, holds, stop logic, and size rules.

## Recommended Next Step

Drop in the Perplexity strategy-switcher/backtest simulator section and map platform signals into explicit strategy families.

Suggested strategy families:

- `PRESSURE_CONTINUATION`
- `NEWS_SHOCK_EXIT_OR_HEDGE`
- `NEWS_CONFIRMED_DIRECTIONAL`
- `LIQUIDATION_SWEEP_FADE`
- `BREAKOUT_PULLBACK`
- `MEAN_REVERSION_CHOP`
- `NO_TRADE`

Each strategy should define:

- allowed sides
- allowed venues
- entry trigger
- confirmation requirements
- max hold
- early invalidation
- stop/take-profit
- news policy interaction
- score/risk multiplier

Important next experiments:

1. Run day 3 safer v2 for the remaining 18 hours.
2. Compare safer v2 versus baseline:
   - all trades
   - side
   - venue
   - asset
   - strategy once available
3. Test strategy-switcher on day 1, day 2, day 3 one day at a time.
4. Keep strict production `news_policy.json` conservative until sample size improves.

