# Markets Watch Trade Logic

Last updated: 2026-05-16

This document is the working contract for how the platform turns market reads into trade options. It should be updated whenever we change the trading policy.

## Core Principle

Historical analysis calibrates shape and timing. It should not veto a strong current setup just because the same type of move often flattens over a long window.

The trading question is present tense:

- Is pressure strong now?
- Where are we in the life of the setup?
- Has the move already paid too much?
- Are spread, volume, and blockers acceptable?
- What is the short trade window, not the two-week story?

## Trader Vocabulary

Keep trader-facing language simple:

- Whale
- Herd
- Equilibrium
- Pressure forming
- Early probe
- Confirmed setup
- Continuation probe

Do not show internal terms such as `dipole` to traders.

## Signal Distribution

Signal delivery is tier-inclusive, not cohort-rotated.

- A tier accepts every signal at its tier and every safer tier above it.
- `tier_1` receives only tier 1.
- `tier_3` receives tiers 1, 2, and 3.
- `tier_5` receives tiers 1 through 5 and therefore gets the most signals.
- No subscriber/friend-group rotation is applied in the POC.

## Present-Tense Score

The backend computes a `trade_present_score` from:

- adjusted classifier confidence
- Whale/Herd/Nascent/pressure-watch state
- internal pressure magnitude
- volume confirmation
- move from setup onset
- current chunk movement
- setup age
- recent-window decay

Score bands:

- `85_100`: very hot; can be real, but must pass chase checks
- `70_84`: strong
- `55_69`: tradeable only with the right stage/context
- `40_54`: watch
- `0_39`: no trade

## Stage

Each same-side setup is tracked by age:

- `onset`: age 0-1 chunks
- `early_follow`: age 2-3 chunks
- `mature`: age 4-8 chunks
- `late`: age 9+ chunks

Pass-22 showed stage matters more than raw score alone. In that run:

- `70_84 + early_follow` had useful short-window follow-through.
- `55_69 + mature` was surprisingly useful as a continuation/probe bucket.
- `85_100 + onset` was not automatically best and can represent chase/exhaustion.

## Trade Options

## Strategy Switcher

Every trade option now receives an explicit strategy family before mock/live auto-trade can open it:

- `NEWS_SHOCK_EXIT_OR_HEDGE`
- `NEWS_CONFIRMED_DIRECTIONAL`
- `NEWS_BREAKOUT`
- `LIQUIDITY_SQUEEZE`
- `LIQUIDATION_SWEEP_FADE`
- `BREAKOUT_PULLBACK`
- `MEAN_REVERSION_CHOP`
- `NO_TRADE`

The switcher uses present-tense market context: side, stage, present score, pressure state, regime, market dipole, recent follow-through, volume, and daily/news dipole context. Dipole is a selector and confirmation layer, not a standalone entry rule.

The selected strategy is stored on statuses, signal events, live/mock practice trades, and replay trades as `trade_strategy_id`, `trade_strategy_label`, confidence, reasons, blockers, and strategy stop/target hints.

Practice/autoresearch mode may instantiate strategy families that have not earned product exposure yet. Product mode still obeys daily health, bucket health, venue health, and daily loss limits. This separation is intentional: the system can learn broadly while only surfacing earned, high-selectivity trades.

## Refrag Strategy Memory

Refrag belongs inside the strategy loop as the system's memory and invention layer. It should help the platform answer:

- Which prior families/rules looked similar to this market context?
- Which buckets won or failed when market, news, on-chain, and family dipoles aligned?
- What candidate variations should practice/autoresearch try next?
- Which ideas should be retired because daily health repeatedly killed them?

Refrag may propose new strategy candidates, parameter variants, feature combinations, or bucket splits, but it must not directly create product trades. Proposed ideas flow through the same evidence path:

1. Refrag proposes a candidate family or variant with rationale and citations to prior evidence.
2. The candidate is registered as practice/autoresearch only.
3. Replay/live practice records outcomes with family, bucket, venue, on-chain regime, and dipole-coupling context.
4. Daily health promotes, demotes, kills, or keeps it learning.
5. Product exposure is allowed only for `ok` families and buckets.

The loop should be self-evolving, not isolated. A family that touches a BTC/ETH signal and proves to be a poor fit should leave a structured handoff for the next candidate rather than simply disappearing. That handoff should say:

- what it saw in the signal/context
- why its own rule shape did not fit
- which features looked useful
- which features were missing or misleading
- what the next family should try differently

Example: a first family may report, "BTC had pressure, but continuation failed because follow-through was absent, exchange flow was distribution-like, and the move was stretched." The next family can then evolve toward a better fit, such as a liquidity-squeeze fade, mean-reversion variant, or on-chain-aware breakout block. Refrag's job is to preserve and route those observations so later families inherit the scars and the clues.

This makes strategy evolution evidence-driven instead of vibes-driven. Refrag can be imaginative; daily health is the judge.

Implementation hook:

- Replay writes `refrag_relay` into `mock_replay_results.json`.
- Autoresearch writes `refrag_relay` into `market_strategy_autoresearch_*_results.json`.
- The relay schema is built by `strategy_refrag_relay.py`.
- Reports include a **Refrag Relay** section summarizing each family handoff.
- `strategy_family_evolution.py` writes per-family JSON memory cards into each run's `evolved_families/` directory and the shared `research/strategy_evolution/` library.

## High-Conviction Tickets

The product-facing layer is `high_conviction_ticket.py`. It wraps the current trade option and strategy decision into a shared ticket object for backend/frontend/Discord/executor surfaces.

Ticket states:

- `GO`: eligible high-conviction ticket. Requires strategy-class history to meet configured trade-count, win-rate, and Sharpe floors.
- `WATCH`: interesting but below tier score.
- `BLOCK`: blocked by missing evidence, news conflict, trade blockers, or strategy-specific confirmation failure.

By default, missing historical strategy-class metrics block `GO`. This prevents the product layer from marketing an 80-85% class before enough replay/live evidence exists.

Replay can filter strategy families with:

```powershell
python mock_trade_replay.py --allowed-strategies MEAN_REVERSION_CHOP,NEWS_BREAKOUT,LIQUIDITY_SQUEEZE
python mock_trade_replay.py --disabled-strategies MEAN_REVERSION_CHOP
```

`confirmed_follow`

- Requires Whale/Herd confirmation.
- Prefers `onset` or `early_follow`.
- Requires readiness around 70+.
- Normal size if risk gates pass.

`early_probe`

- Allows pressure-forming or mature continuation setups.
- Requires readiness around 55+.
- Probe size by default.
- Mature continuation probe can size slightly larger than a pure early probe.

`watch`

- Used when score is below threshold, stage is late, spread is too wide, volume is missing, the move is already extended, or pressure is not clean.

## Auto Trade Policy

Auto trade is practice-first. Live full auto remains blocked unless the server is explicitly started with:

```powershell
$env:MARKETS_WATCH_ALLOW_LIVE_AUTO_TRADE = "1"
```

Tolerance presets:

- `conservative`: confirmed-follow only, 75+ readiness, 1 open auto trade
- `balanced`: early probes and confirmed follows, 65+ readiness, 3 open auto trades
- `aggressive`: early probes and confirmed follows, 55+ readiness, 6 open auto trades

Auto exits when:

- pressure flips against the position
- opposite Whale/Herd appears
- the setup degrades to watch
- the stage becomes late
- present score degrades below tradeable range
- blockers appear
- max hold window elapses

## Daily News Criteria Layer

Daily BTC/ETH news analysis writes `daily_news_context.json`. Routine news is a trade-criteria and risk layer: it can adjust present score, reduce size, require confirmation, disable strategies, or force manual review.

High-confidence shock news is different. Primary/regulatory/security/exchange shocks can start defensive action directly: exit longs, exit shorts, reduce gross exposure, pause new entries, or allow a hedge playbook. Fresh directional entries from news still need either an explicit shock playbook or market confirmation.

The backend applies this layer to `trade_option_blockers`, so auto-trade refuses new positions when the daily context says:

- the news context is stale
- auto-trade mode is `PAUSE`, `MANUAL_REVIEW`, or `BLOCK`
- market confirmation is weak while confirmation is required
- news bias conflicts with the setup side
- the daily brief supplies an explicit asset or global blocker

The same layer also scales `trade_option_notional_scale` by the asset's `risk_multiplier`. Use `0.0` to block, `0.25` for tiny probes, `0.5` for reduced size, and `1.0` for normal size.

The same layer can adjust `trade_present_score` by a bounded modifier using the resolved policy edge and recent news dipole. This keeps routine news from overpowering market structure while still letting aligned, historically coupled news improve confidence.

News-only action is limited to the shock-news path. Starter actions are time-bound with `starter_valid_until`; after expiry they remain context only.

## Mock Forward POC

Mock forward trading uses real market data and simulated execution. It can run on live realtime data or on a historical replay timeline.

Historical replay is allowed only if it is event-driven:

- At replay step `t`, the strategy can only see bars/chunks up to `t`.
- Entries fill against the bid/ask available at `t`.
- Exits are evaluated only as later replay steps arrive.
- No future outcome, final path, or future label can be used for entry decisions.

Initial mock scenarios are tested as eight variants: each base scenario has `rotation_off` and `rotation_on`.

- `pressure_scout_rotation_off` / `pressure_scout_rotation_on`: immediate trade on pressure building, around 5% of bank/reserve.
- `early_low_band_rotation_off` / `early_low_band_rotation_on`: bottom of early-but-not-reckless, score 55-69.
- `next_tier_low_band_rotation_off` / `next_tier_low_band_rotation_on`: bottom of next tier, score 70-89.
- `almost_sure_thing_rotation_off` / `almost_sure_thing_rotation_on`: 90+ score, but still blocked by chase/stage rules.

Winner rotation is optional per scenario variant. When enabled, if exposure is full and a meaningfully stronger setup appears, the scenario may close its weakest/degrading open trade at market and reallocate to the stronger one. The close reason is `rotation_to_better_performer`.

Replay guardrails added after the first day-one smoke test:

- Scenario-level cooldowns reduce repeated scout entries on every chunk.
- Mock POC fees are configurable separately from manual practice fees; default mock replay fee is 5 bps per fill.
- Open trades can exit before max hold on score drop, stop-loss bps, take-profit bps, pressure flip, stage degradation, or setup blockers.
- Historical bars with no bid/ask use a synthetic crossed spread so replay still pays realistic entry/exit spread without looking ahead.

Mock bankroll/exposure rules:

- Starting mock equity is `$10,000`.
- Bank/reserve is never displayed above `$10,000`.
- If mock equity is `$20,000+`, max open exposure is `$10,000`.
- If mock equity is `$10,000-$20,000`, max open exposure is 50% of equity.
- If mock equity is `$5,000-$10,000`, max open exposure is `$5,000`.
- If mock equity is below `$5,000`, max open exposure can use all remaining equity.
- There is no hard stop at zero; the POC can deplete the account.

## Analysis Cadence

The present-tense strength reanalysis runs daily at 2:00 AM ET and writes:

- `pass22_present_signal_strength_out/present_signal_strength_report.md`
- `pass22_present_signal_strength_out/present_signal_strength_results.json`

Use those outputs to revise thresholds, but keep production changes conservative until live forward-paper outcomes confirm the adjustment.
