# Option E — Product spec: closed signal feed with two-tier scaling

**Date**: 2026-05-04
**Branch**: `davisai1974/markets @ claude/new-session-o3vnm`
**Status**: Direction confirmed. Build follows Phase 1 → Phase 1.5 → Option E build, with ICE port deferred until Phase 1.5 gates G + H + I pass on crypto.

## Scope

Option E is the chosen product direction from the five drafted on 2026-05-04 (see conversation log). The remaining four options (signal feed only / arb LLC / white-glove personal bots / GP-LP fund) are documented as "future possibilities" PDFs to share when scaling beyond the closed group makes sense.

This spec covers Option E only. Refined into a **two-tier scaling structure**: crypto for validation and a permanent retail-prosumer service, ICE energy futures as the scaling path to institutional revenue. Both tiers share the same backend.

## What the product is

A regime-classified, actor-aware **playbook signal** with two delivery modes:

1. **Closed signal feed** (Discord / Telegram / private channel) — posts when the classifier fires a high-confidence regime alert. Each alert names the actor type (whale up/down, herd up/down, organic, wash) and the corresponding playbook. Friends decide whether to act.
2. **Open-source executor** — a reference Python implementation friends can run on their own exchange / broker accounts. Reads from the signal feed, applies their personal risk parameters, places orders. Capital and keys stay with the friend.

The product is NOT:
- A buy/sell signal generator
- An asset-management service
- A custody / capital-pooling service
- A public newsletter

## Two service tiers

### Tier 1 — Crypto (closed group; validation venue and permanent service)

- **Audience**: Greg's closed friends group (5–20 people). Retail-to-prosumer skill level.
- **Markets**: Coinbase BTC-USD primary; Kraken BTC/USD as cross-venue confirmation; expand to ETH, SOL, BTC perps after BTC validates.
- **Data cost**: zero (public WS feeds).
- **Pricing**: probably free at launch among friends. Token monthly fee ($25–$100) once stable. Profits stay with each member.
- **Regulatory shape**: closed-list private subscription, no managed assets, no performance fees → no SEC/CFTC registration burden. Investment-newsletter precedent applies.
- **Failure mode**: when a signal misfires, friends blame the system anyway. Need clear "research, not advice" framing in the channel rules.
- **Edge longevity**: best of any tier — signal stays unpublished, N independent execution paths leave no concentrated trail.
- **MVP timeline**: ~2–3 weeks after Phase 1.5 produces gates G + H + I.

### Tier 2 — ICE energy futures (institutional scaling path)

- **Audience**: energy desks at utilities, refineries, prop shops, hedge funds, single-strategy commodities funds. B2B.
- **Markets**: ICE Futures U.S. + ICE Futures Europe energy complex (NG, Brent, WTI, power, refined products).
- **Data cost**: $$ — Databento self-service API (~$125 free credits, then usage-based) is the recommended starting point. Eventually direct ICE membership ($250 app + $400/user/month + per-product market data + $350/mo energy minimum) for production.
- **Pricing**: $500–$5,000/mo per seat. Multi-seat enterprise discounts.
- **Regulatory shape**: heavier. Data redistribution licensing required if we resell signals derived from ICE data. CFTC-aware on any wash-trade or manipulation claims. Need real legal review before sales.
- **Failure mode**: institutional sales cycles are 3–9 months; not a fast-revenue channel.
- **Edge longevity**: structurally good — energy markets have predictable regime transitions (expiry, weather/storage reports, OPEC) that the regime classifier should align to naturally. HFT competition exists at the tick scale but our minute-to-hour regime signal sidesteps it.
- **Customer-acquisition asset**: Greg's prior energy-trading career is the wedge. He knows what desks need, which actors typically dictate the market, and what the typical pre-event vs post-event regime patterns look like.
- **MVP timeline**: ~6–10 weeks after Tier 1 demonstrates revenue or signal stability on crypto.

The two tiers are **independent services** sharing infrastructure. Crypto stays running even after ICE launches.

### Tier 3 — Cross-domain macro expansion (institutional / "big boys")

The deeper truth about the architecture: **PELT chunking, dipole, regime classifier, cross-venue agreement — none of these are crypto-specific.** They detect operator structure on any pair of coupled markets. Once Tiers 1 + 2 validate the methodology, the same machinery ports to any asset class with paired-market microstructure.

- **Audience**: macro hedge funds (Bridgewater, Brevan Howard tier and below), multi-strategy desks at prop shops, family offices with macro arms, fixed-income/FX trading desks at investment banks, single-strategy commodities funds expanding cross-asset.
- **Markets** (each is its own coupled-pair test bed):
  - **FX** — EUR/USD ⊥ DXY ⊥ Treasury futures (Greg's "EUR vs 30Y mortgage" inverse relationship is the canonical example: US 10Y yield drives both ends; mortgages move with rates, EUR moves opposite to rate differential)
  - **Rates** — 2Y ⊥ 10Y ⊥ 30Y (yield curve regime detection; inversion alerts)
  - **Commodities** — WTI ⊥ Brent ⊥ USD; NG ⊥ power ⊥ weather; metals via LME
  - **Equity index** — ES ⊥ NQ ⊥ RTY (intraday rotation detection)
  - **Cross-asset** — BTC ⊥ DXY ⊥ ES (risk-on/off regime)
  - **Mortgage MBS** — MBS spread ⊥ 10Y ⊥ EUR (the original Smith Barney CBOT-style trade, modernized)
- **Data cost**: paid feeds. CME via Databento or direct membership; FX via OANDA/EBS or paid retail platforms; equities via Polygon/IBKR. ~$500-5,000/mo per asset class for production-grade.
- **Pricing**: $5K-$50K/mo per seat for individual analysts/PMs; multi-seat enterprise contracts $50K-$500K/mo for desk-wide deployment. The big-boys end of this range supports a real sales / customer-success team.
- **Regulatory shape**: heaviest of all tiers. Cross-jurisdictional data licensing (CME/ICE/LSE/etc. each have separate redistribution terms). If we manage assets or take performance fees we hit RIA territory; if we sell signals only, investment-newsletter precedent still applies but the institutional sales surface raises the SEC scrutiny threshold. Real legal team before first paid customer.
- **Edge longevity**: structurally best of all three tiers. Macro cross-asset lead-lag at minute scale is *less* heavily HFT'd than crypto microstructure (HFT competition is brutal at the tick on each individual asset, but cross-asset coupling at minute-to-hour scales has been studied less and arb'd less because the data infrastructure is harder to assemble). The methodology's domain-agnostic detection of regime transitions and actor classes is novel even in mature markets.
- **Customer-acquisition asset**: Greg's energy-trading career + cyber-DARPA operator-discovery pedigree + cross-domain market intuition spans the credibility surface that institutional buyers actually care about. The pitch isn't "we built a crypto signal feed." It's "we built a methodology for finding operator structure in any coupled-market system, validated across crypto + energy + cyber attack telemetry, ready to run on your asset class with your data." That's a different conversation than competing on signal performance against existing quant shops.
- **Failure mode**: institutional sales cycles are 6-18 months; cannot be the first revenue tier. Requires Tier 1 (live signal feed) + Tier 2 (paying ICE customer) as proof points before serious institutional sales make sense. **Plan for Tier 3 to take 12-24 months from Tier 1 launch.**
- **MVP timeline**: ~6 months after Tier 2 demonstrates a paying institutional customer. The first Tier 3 deal probably comes from a warm intro through Tier 2 — an energy desk's parent fund or a former colleague at a macro shop.

The crucial framing throughout: **the methodology is the moat, not the asset class.** Tier 1 (crypto) and Tier 2 (ICE) are *proof of methodology*. Tier 3 is where the methodology is sold as a methodology. Pricing supports it because Tier 3 customers are buying institutional-grade alpha-discovery infrastructure, not a signal feed.

## Shared architecture

Same Python backend serves both tiers. Differences are confined to the **collector** and the **regime baseline calibration**.

```
                +------- coinbase_btcusd_collector.py    \
                +------- kraken_btcusd_collector.py       \
                +------- (future) coinbase_eth.py          >--+
                +------- (future) binance_perp.py          /   |
                                                          /    |
Tier 2:                                                  /     |
                +------- databento_ice_ng.py     \      /      |
                +------- databento_ice_brent.py   >----+       |
                +------- databento_ice_wti.py    /             |
                                                                v
                                                  markets_adapter.py
                                                  (PELT chunker, encoder,
                                                   FeatureScaler, decoder)
                                                                |
                                                                v
                                                  regime_classifier.py
                                                  (6-class actor classifier)
                                                                |
                                                                v
                                                  signal_publisher.py
                                                  (Discord/Telegram per tier)
                                                                |
                                                                v
                                            +-------+-----------+----------+
                                            |       |           |          |
                                          friend  friend      energy     energy
                                          1       2           desk A     desk B
                                          (own keys, own capital, own risk parameters)
```

Per-asset baselines (realized vol, range, Kyle's lambda, baseline burstiness) computed offline and refreshed daily. Each asset gets its own baseline file.

## Sequencing

1. **Phase 1** (running now) — 4-hour Coinbase trajectory + cumulative checkpoints. Validate baseline dipole signal exists and the contamination filter behaves on real data.
2. **Phase 1.5** — add 6 new encoder features (dipole autocorr, dipole spectral peak, Kyle's lambda proxy, trade-size multimodality, inter-trade burstiness, cross-venue lead-lag). Implement rule-based 6-class classifier. Re-run analysis on Phase 1's collected bins. Evaluate gates G + H + I.
3. **Phase 2** — autoresearch operator discovery if Phase 1 gates A + B pass. Validates whether the dipole is the right operator or if data-driven discovery picks something better. Independent of Option E build but informs feature engineering.
4. **Option E Tier 1 build** — closed signal feed for crypto. Starts when Phase 1.5 gates G + H + I pass.
   - Discord/Telegram bot scaffold (signal_publisher.py)
   - Open-source executor template (executor_template.py)
   - Closed-group documentation (channel rules, risk disclaimer, executor setup guide)
   - Onboard 1–3 trusted friends as alpha users; expand to full 5–20 once stable
5. **Option E Tier 2 build** — ICE energy port. Starts after Tier 1 demonstrates ≥ 1 month of stable signal output and ≥ 1 friend trading on it.
   - Databento adapter (databento_ice_collector.py)
   - ICE-specific baseline calibration (energy markets have different microstructure)
   - Data licensing review with Databento
   - Identify 1–2 friendly energy desks for design-partner phase
   - Pricing/contract structure with first paying customer

## Open questions

1. **Discord vs Telegram vs private GitHub repo** for Tier 1 distribution. Discord is most casual and threads well; Telegram is what crypto traders are already on; private GitHub repo is most auditable but has a clunkier signal experience. Probably Discord. Greg to confirm.
2. **Pricing model for Tier 1 friends**: free indefinitely / token monthly fee / profit-share / nominal subscription? Affects regulatory positioning slightly (nominal subscription is cleanest).
3. **Tier 2 data licensing** — Databento allows derived-signal redistribution under their standard license, but we should review the specific clauses before any paid Tier 2 customer onboards. Need 1 hour of legal review with Databento support before scaling.
4. **Energy market hours** — ICE energy futures trade nearly 24/5 but with low overnight liquidity. Phase-1-style trajectory analysis should target the peak hours (US daytime for WTI/HH NG, London hours for Brent). Encoder baselines must be computed per session.
5. **Whether to expose 12D regime embeddings** as a separate paid data product (not signals — just embeddings). Could be a high-margin add-on for desks that already have their own quant teams. Defer until Tier 2 launch.
6. **OKX integration** as an additional crypto venue — ICE invested in OKX in March 2026 (per [FinTech Weekly](https://www.fintechweekly.com/news/intercontinental-exchange-polymarket-financial-data-infrastructure-2026)). If the ICE-OKX bridge produces unified data feeds, that becomes the natural "third venue" for crypto cross-venue replication, with the same data plumbing as the eventual ICE energy port. Worth tracking.

## Save locations

- `E:\information_layer\markets\OPTION_E_PRODUCT_SPEC.md`
- `F:\Factory\knowledge\information_layer\markets\OPTION_E_PRODUCT_SPEC.md`
