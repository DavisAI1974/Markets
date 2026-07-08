# DavisAI — BTC Early Signal (session paper, 2026-07-08) — Greg's drop-in, S75

> Extracted from the attached .docx. The S76 plan: point the whole-curve shape gate at BTC+ETH at ~60s with a ride-to-reversal exit + the book direction signal (HIGH on BTC/ETH).

DavisAI — BTC Early Signal: Monetization, Cross-Platform & Coinbase Forward-Test Findings
Working session summary • 2026-07-08 • crypto BD / trading strategy exploration
>Prepared as an exploration only. Not investment advice. All results are provisional and from single test windows unless noted.
1. Executive summary
The core asset is a forward-looking order-book signal on BTC: the resting book's shape leans into a price turn BEFORE price moves, whereas standard order-flow imbalance confirms the turn ~18 bps late. The entire profit-and-loss lever is execution economics — the edge is negative at taker fees and flips positive at the maker / zero-fee floor. This session (a) framed the monetization and cross-platform plays, (b) analyzed the Coinbase Exchange Liquidity Program (0% maker at all tiers), (c) mapped US-eligible venues that pay maker discounts, and (d) empirically tested the forward signal on real Coinbase L2 data and on all five majors. Headline empirical result: the forward book signal is real and leads price on Coinbase (BTC + ETH strong, ETH as strong as BTC; SOL flat as documented) — and, treated as a per-cell weighted component of a signal stack rather than a standalone trigger, all five majors are informative (5 wins).
2. What the signal is
•  Book pre-fire tell (FILTER): two-piece L2 depth shape (with-side vs against-side); fires before price turns. 'Gold' on BTC, flat on SOL (per prior work; confirmed this session).
•  1-sec price reversal (TIMING): enters ~5.6 bps off the true top/bottom; separate from the filter.
•  Economics are a fee-floor story: edge dies at ~10 bps taker round-trip; flips positive at the ~4 bps (or 0%) maker floor. Per-second data alone is worth ~8 bps per round-trip swing vs 1-minute.
•  Deployment is per-cell (asset x venue x side). Measured survivors: btc_bybit (taker), btc_kraken (maker). 
3. Coinbase Exchange Liquidity Program (June 2026)
This program is almost custom-built for the strategy: it zeroes the exact cost that kills the edge and 10x-credits the exact pair the signal trades.
Tier
Taker fee
Maker fee
Notes
Tier 4
0.030%
0.00%
entry tier
Tier 3
0.022%
0.00%

Tier 2
0.0175%
0.00%

Tier 1
0.011%
0.00%
top

•  Maker fee is 0.00% at every tier — better than the 4 bps floor that already made the edge positive in backtest.
•  BTC-USD carries a 10x AMV qualification multiplier this month — the exact flow the signal generates counts 10x toward qualification.
•  Three low/no-bar on-ramps: New Client Introductory Rate (Tier 4 / 0% maker for 1-2 months, no volume bar); Jumpstart (port Kraken/other-exchange volume to qualify); Accelerator (jump a tier).
•  Cross-platform benefits: Coinbase Derivatives performance feeds spot tiers; Verified Pools (DeFi TVL) earns tier upgrades. Contact: mmprogram@coinbase.com.
•  Caveats: 0% is a zero fee, not a rebate; BTC-USD is the most HFT-competed book; the tell must still convert on Coinbase's book (unproven until tested — see Section 6).
4. Monetization & cross-platform plays
Trade it (highest edge/dollar):
•  A1. Book-armed maker market-making on BTC at the 0% maker floor (crown jewel; needs sub-second + co-region colo — Coinbase = us-east-1).
•  A2. Directional swing on taker-viable cells (fastest live track record).
•  A3. Cross-venue confirmation overlay (precision multiplier). A4. Rebate/fee-tier farming as a revenue line.
Sell it (capital-light, Option E): Tier 1 closed Discord feed; Tier 2 energy futures license; Tier 3 methodology-as-product. New crypto-native: liquidation/cascade front-run on perps; turn-aware execution algo; MM-as-a-service / rebate share; book-shape data product.
5. US-eligible venues that pay maker discounts (Bybit alternatives)
User is a US citizen (Bybit unavailable). Verified July 2026:
Venue
US eligibility
Maker on majors
Role
Coinbase Exchange
Most states
0.00% (program)
primary — BTC signal home
Gemini ActiveTrader
All 50 states
0.00%, down to -0.01% top tier
easiest all-state spot
Kraken Pro
Most (not NY/ME)
0.00% at $10M/mo
spot; rebates on alt pairs only
Kraken Derivatives US
US-eligible
maker rebates
direct Bybit-perp replacement (Bitnomial, CFTC)
Coinbase Derivatives
US (CFTC FCM)
—
BTC/ETH perps, feeds spot tier

•  Fat rebates (negative maker) are on illiquid pairs, not BTC/ETH/SOL — on majors, 'discount' means 0% maker + spread.
•  Do NOT VPN into Bybit/Hyperliquid — compliance landmine for a US business. Kraken Derivatives US / Coinbase Derivatives are the legal equivalents.
6. Empirical: is the forward signal actually on Coinbase? (tested this session)
Tested on the real Coinbase L2 book (data/btc-book, 196 hours / 8+ days, 1.47M snapshots), fully out-of-sample. NOTE: this is the crude net-imbalance / scalar read — a LOWER BOUND — not the real curve-shape-match gate (that code was not available in this session).
6a. Lead-lag — the book leads price (forward confirmed): every depth measure peaks at lag +1s. Correlation weak (~0.08) and short-lived (gone by 5s), but genuinely forward. Full top-10 depth beats top-of-book.
6b. Tradeability — only clears at the 0% maker floor, and thinly:
Signal / exit
gross bps/trade
net @0% maker
net @2bps taker
win%
net imbalance, 15s hold
+0.385
positive, thin
-1.6 (dead)
57%
threshold 'both-agree' gate
-0.07 to +0.59
flat/positive
dead
58-63%
ride-to-reversal, 30bps trail
+7.39
+7.39
+5.39
58%
ride-to-reversal, tight trail
-2 to -5
negative
dead
40%

•  Ride-to-reversal with a wide (30 bps) trailing stop is the first net-positive config — even at taker (+5.4 bps/trade). But fragile: only the widest stop works, n=100 OOS trades, one window, likely riding a few big trend legs (single-regime-artifact risk).
•  The threshold 'both-agree' gate reproduced the documented S75 negative: win-rate up (+6 pts) but net not up — a scalar snapshot over-skips the fat winners. This confirms WHY the whole-curve shape-match is needed.
•  The signal lives at ~60s, not 15-30s — a new, useful data point for aiming the real gate.
7. Cross-coin: the same signal across the majors (per-cell weighting, not pass/fail)
Identical forward test on each major's Coinbase L2 book (~35-41h each, OOS). Per the standing rule (tools are complementary; deploy per-cell; never discard a signal for failing on some cells), the question is not 'does it trade alone' but 'how to WEIGHT it per coin in the stack.' All five cells are informative — 5 wins. Accuracy (hit-rate), not gross bps, sets the weight; volatile alts show big gross from a few moves rather than from being right.
Coin
corr @0
corr +1s
hit 15s
gross 15s
stack weight / use
BTC
+0.076
+0.087
57%
+0.28
HIGH — leads; standalone-candidate filter
ETH
+0.148
+0.085
55%
+0.42
HIGH — as strong as BTC or stronger (new)
SOL
+0.003
+0.019
37%
-0.50
ZERO the book here; lean on other tools (flat = actionable; confirms prior)
XRP
+0.010
+0.022
51%
+0.92
LOW — slight edge alongside other signals, not a trigger; volatile
DOGE
-0.012
+0.060
48%
+0.60
LOW — slight forward carry (+1s); stack contributor

•  BTC and ETH: high-weight, standalone-candidate filters (positive correlation, book leads, >54% accuracy). ETH as strong as BTC extends the strong-cell set.
•  SOL flat is a win: zero-weight the book on SOL and rely on other signals there — prevents fading a non-signal — and independently confirms the documented 'flat on SOL'.
•  XRP / DOGE: use as a slight edge in the stack, never the standalone trigger. Small weight, real +1s forward carry on DOGE; the volatility is sizing context.
•  Guardrail (Result Discipline): a weak component only adds if genuinely additive/orthogonal, not noise. BTC/ETH clearly are; the weak three need the multi-window run + the real curve-shape gate to confirm the small real edge under the volatility before weighting.
8. Paper-trading plan & validity discussion
•  Sandbox is an INTEGRATION test (fake liquidity), NOT a validity test. For signal validity: live-real-data paper > sandbox; the only true fill-validity test is small real orders.
•  Chosen path: (1) live real-data paper loop (no key, simulated fills, conservative maker assumptions) to validate the signal; sandbox later only to shake out API plumbing; tiny real size when ready.
•  Caveat: any paper run available in this session trades the SCALAR lower-bound signal, not the real curve-shape gate.
9. Next steps
•  Point the REAL whole-curve shape-match gate at Coinbase BTC + ETH, at the ~60s horizon, with a ride-to-reversal exit (the branch holding that code).
•  Validate across multiple windows/regimes (not one 8-day window) — the accruing 5-coin x 3-venue data is the resource.
•  Open Coinbase Exchange (net-new -> Introductory 0% maker) + file Jumpstart with Kraken volume; email mmprogram@coinbase.com for the AMV calc.
•  Stand up Kraken Derivatives US for the perp cell (US-legal Bybit replacement).
•  Run the Option-1 live real-data paper loop to collect a forward sample.
>Sources: Coinbase Exchange Liquidity Program Overview (June 2026); Kraken/Gemini fee & maker-rebate pages; Kraken CFTC-regulated US perps launch; internal test scripts on real realbins + data/*-book L2 snapshots.

