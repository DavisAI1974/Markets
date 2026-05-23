# Daily News Trade Context

Last updated: 2026-05-16

This is the contract for using daily BTC/ETH news analysis inside the markets platform. Routine news changes trade criteria and risk posture. High-confidence primary/regulatory/security shocks can start trades directly: exits, fresh directional entries, hedges, reduced exposure, or paused entries.

## Purpose

The daily news job should answer:

- What changed for BTC, ETH, or broad crypto today?
- Is the item confirmed by a primary source, trusted media, or only social chatter?
- Is price, volume, open interest, funding, basis, liquidation flow, or ETH/BTC relative strength confirming the story?
- Which auto-trade strategies are allowed, reduced, disabled, or moved to manual review?

## Output File

The daily news job writes `daily_news_context.json` at repo root. The backend and the morning present-strength reanalysis read this file.

Required shape:

```json
{
  "generated_at": "2026-05-16T03:33:07-04:00",
  "max_age_hours": 36,
  "global_blockers": [],
  "assets": {
    "BTC": {
      "narrative_bias": "BULLISH | BEARISH | MIXED | UNKNOWN",
      "market_confirmation": "STRONG | MEDIUM | WEAK | UNKNOWN",
      "crowding_risk": "LOW | NORMAL | HIGH | EXTREME | UNKNOWN",
      "volatility_regime": "LOW | NORMAL | ELEVATED | CRISIS | UNKNOWN",
      "trade_posture": "short human-readable posture",
      "risk_multiplier": 0.5,
      "max_leverage": 2,
      "requires_confirmation": true,
      "auto_trade_mode": "ALLOW | PAUSE | MANUAL_REVIEW | BLOCK",
      "allowed_strategies": ["MOMENTUM"],
      "disabled_strategies": ["HIGH_LEVERAGE_SCALP"],
      "summary": "One sentence for trader-facing reason codes.",
      "blockers": [],
      "starter_actions": ["EXIT_LONGS", "ALLOW_HEDGE_SHORT"],
      "starter_reason": "High-confidence bearish regulatory shock.",
      "starter_urgency": "HIGH",
      "starter_valid_until": "2026-05-16T06:03:07-04:00",
      "starter_category": "REGULATORY",
      "starter_horizon_min": 60,
      "policy": {
        "category": "REGULATORY",
        "directional_bias": "BEARISH",
        "horizon_min": 60,
        "signed_bps_edge_vs_placebo": 6.2,
        "hit_rate": 65.0,
        "risk_multiplier": 0.5,
        "requires_confirmation": false
      },
      "source_count": 0
    }
  }
}
```

## Auto-Trade Rules

- Routine news alone should usually adjust criteria before opening a new position.
- Shock news may start both defensive and fresh directional actions: exit longs, exit shorts, start longs, start shorts, reduce gross exposure, pause new entries, or enable a hedge playbook.
- Examples of shock news: primary-source ban/regulatory enforcement, exchange insolvency/outage, exploit/hack, stablecoin depeg, ETF approval/rejection, or protocol-breaking event.
- If `auto_trade_mode` is `PAUSE`, `MANUAL_REVIEW`, or `BLOCK`, auto-trade must not open new positions for that asset.
- If the file is stale, auto-trade must require manual review.
- If `requires_confirmation` is true and `market_confirmation` is `WEAK`, `LOW`, or `UNKNOWN`, auto-trade must not open new positions.
- If news bias conflicts with the setup side and confirmation is not `STRONG`, auto-trade must not open new positions.
- `risk_multiplier` scales the trade option notional. Use `0.0` to block, `0.25` for probe-only, `0.5` for reduced size, and `1.0` for normal size.
- Policy-derived edge and recent news dipole can nudge `trade_present_score`, but only as a bounded modifier.
- `starter_valid_until` controls shock action expiry. After expiry, starter actions are context only.

Starter action vocabulary:

```text
EXIT_LONGS
EXIT_SHORTS
EXIT_LONGS_IF_UNCONFIRMED
EXIT_SHORTS_IF_UNCONFIRMED
START_LONG
START_SHORT
START_LONG_IF_CONFIRMED
START_SHORT_IF_CONFIRMED
REDUCE_GROSS_EXPOSURE
PAUSE_NEW_ENTRIES
PAUSE_CONFLICTING_ENTRIES
ALLOW_HEDGE_SHORT
ALLOW_HEDGE_LONG
```

Example: if China announces a primary-source crypto/mining ban, BTC/ETH news context should mark `BEARISH`, `starter_urgency=HIGH`, include `EXIT_LONGS`, `START_SHORT`, `ALLOW_HEDGE_SHORT`, and `PAUSE_NEW_ENTRIES`. The starter can execute under the shock-news playbook with capped size, tight invalidation, and aggressive slippage checks.

## Daily Sources

Start with:

- Primary/regulatory: SEC EDGAR, ETF issuer updates, exchange announcements.
- Crypto news: CoinDesk, The Block, Blockworks, Decrypt, DL News.
- Macro: Fed/FOMC, CPI, jobs data, rates, DXY, Treasury yields.
- ETH protocol: Ethereum Magicians, ethresear.ch, client releases.
- Market confirmation: price, spot/perp volume, funding, OI, basis, liquidations, Coinbase premium, ETH/BTC relative strength.
- Social only after spam filtering: X, Reddit, Farcaster, TradingView, Bitcointalk.

## Daily Scrape Job

Run the RSS ingest before the morning analysis:

```powershell
python news_ingest_rss.py --output news_events.jsonl --raw-output news_raw_ingest.jsonl --lookback-hours 36
python news_coupling_research.py --data-dir . --events news_events.jsonl --output-dir pass23_news_coupling_out
python build_news_policy_from_coupling.py --coupling-results pass23_news_coupling_out/news_coupling_results.json --output news_policy.json
python build_daily_news_context.py --events news_events.jsonl --policy news_policy.json --output daily_news_context.json --max-age-hours 36
```

The first command appends deduped BTC/ETH news items into the event schema. The second tests article-level and bucketed news-dipole coupling against market activity. The third derives machine-readable policy from coupling. The fourth turns latest news plus policy into auto-trade criteria.

## Product Principle

The daily brief should answer:

- What market state are we in?
- Which strategies are allowed today?
- How much risk is appropriate?
- What conditions must confirm before auto-trade can act?
- When should the system refuse to trade?
