# News Events Schema

Last updated: 2026-05-16

`news_events.jsonl` is the raw input for testing whether news and narrative flow couple to BTC/ETH trade activity.

Each line is one timestamped item:

```json
{
  "event_id": "theblock-schwab-btc-eth-2026-05-13",
  "published_at": "2026-05-13T00:45:00-04:00",
  "source": "The Block",
  "source_quality": "TRUSTED_MEDIA",
  "url": "https://www.theblock.co/post/401069/charles-schwab-spot-btc-eth",
  "title": "Charles Schwab launches spot BTC, ETH trading to select retail clients",
  "assets": ["BTC", "ETH"],
  "category": "INSTITUTIONAL",
  "directional_bias": "BULLISH",
  "confidence": 0.75,
  "impact": 0.65,
  "summary": "Major brokerage gives select retail clients direct BTC and ETH access.",
  "dedupe_key": "schwab-spot-btc-eth-launch",
  "classifier": "keyword_v0+nlp_v1",
  "nlp_features": {
    "is_followup": false,
    "has_numeric_size": false,
    "magnitude_bps_hint": 10
  },
  "trade_starter_candidate": false,
  "starter_actions": ["START_LONG_IF_CONFIRMED"]
}
```

## Required Fields

- `published_at`: ISO timestamp. Use the earliest reliable publication timestamp.
- `source`: publisher, feed, forum, or primary source name.
- `title`: headline or short event label.
- `assets`: `["BTC"]`, `["ETH"]`, or `["BTC", "ETH"]`.
- `directional_bias`: `BULLISH`, `BEARISH`, `MIXED`, or `UNKNOWN`.

## Recommended Fields

- `source_quality`: `PRIMARY`, `EXCHANGE_PRIMARY`, `PROTOCOL_PRIMARY`, `TRUSTED_MEDIA`, `AGGREGATOR`, `SOCIAL`.
- `category`: `REGULATORY`, `ETF`, `MACRO`, `EXCHANGE`, `SECURITY`, `PROTOCOL`, `ON_CHAIN`, `DERIVATIVES`, `SOCIAL`, `STABLECOIN`, `INSTITUTIONAL`.
- `confidence`: `0.0` to `1.0`, based on source quality and confirmation.
- `impact`: `0.0` to `1.0`, expected market relevance before seeing future price action.
- `dedupe_key`: shared key for syndicated copies of the same story.
- `classifier`: classifier/enrichment version string.
- `nlp_features`: deterministic enrichment such as follow-up detection, numeric-size cues, and rough `magnitude_bps_hint`.

## Coupling Rule

The research pass treats routine news as a modifier. Shock news can be a trade starter, especially for exits and hedges. A useful new-entry coupling exists only when article direction, source quality, market response, and trade-flow response line up better than placebo timestamps.

Trade-starter candidates should be explainable and risk-capped:

- primary-source regulatory bans/enforcement
- exchange insolvency/outage
- exploit/hack/security incident
- stablecoin depeg
- ETF approval/rejection
- protocol-breaking event

Starter actions include both exits and entries:

```text
EXIT_LONGS
EXIT_SHORTS
START_LONG
START_SHORT
START_LONG_IF_CONFIRMED
START_SHORT_IF_CONFIRMED
ALLOW_HEDGE_LONG
ALLOW_HEDGE_SHORT
```
