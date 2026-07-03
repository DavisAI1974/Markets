# S57 VENUE FINDINGS (2026-07-03) — the fee-group correction, the rebased anchor cells,
# the venue sweep, and the MEXC kill

## 1. THE BYBIT FEE-GROUP CORRECTION (verified, load-bearing — supersedes the S52-S56 -1.25bp)

Bybit's MM rebate is FEE-GROUP TIERED (verified: bybit-exchange.github.io/docs/v5/market/
fee-group-info + Nov 2025 maker-rebate adjustment announcement). At MM3:

| Group | members (ours) | MM3 maker | share weighting |
|---|---|---|---|
| G1 majors | BTC, ETH, XRP, SOL | **-0.4bp** | 1x |
| G2 high-growth | DOGE (+ HYPE, NEAR, TIA, ONDO, 1000PEPE, ADA, WLD, AVAX, LTC) | **-0.4bp** | 5x |
| G3 | FIL, DOT, SEI... | -0.75bp | 8x |
| G4 (106 syms) | **ZEC** (verified in-list) | **-1.0bp** | 15x |
| G5 long-tail (266 syms) | CFX, SNX, CHZ... (thin books) | -1.25bp | 20x |

The -1.25bp booked S52-S56 for sol/eth was the G5 rate. ALL FIVE of our coins are -0.4bp.
SANDBOX cells re-based + sandbox ledger reseeded at true fees (commit 44939a2). The
weighting column matters for the MM application: G2+ maker volume counts 5-20x toward the
0.03% weighted maker-share qualification.

## 2. REBASED ANCHOR CELLS (19.5h bybit books, queue-honest, $5k flat)

| cell | net/leg | v2 honest | v1 front-of-queue | verdict |
|---|---|---|---|---|
| sol_bybit @-0.4 | +2.56bp | +$1.89/hr | +$16.57/hr | survives — 0.62bp half-spread = real capture |
| eth_bybit @-0.4 | +1.22bp | **-$2.20/hr** | +$7.11/hr | marginal — 0.03bp spread = was ~all rebate |

ETH's S56 "lead on the honest metric" was an artifact of the wrong rebate. KEY MECHANIC:
our executor is price-improvement (front-of-queue, S45 spec) — that needs ROOM INSIDE THE
SPREAD. SOL has it; ETH does not (tick-floor book -> stuck at back-of-queue economics).
**Pick cells by half-spread width, not tape size.** Like-for-like SOL venue check (same
machine, $5k full-fill): sol_bybit +2.56bp/leg, ~$185/hr vs sol_coinbase +1.93bp/leg,
~$142/hr (41.0h ledger) — and the Coinbase number assumes mk0, a tier Coinbase does not
give us (S49: retail 25-60bp, no rebate exists, 0.00 floor at $250M/30d tier only).
OPEN: Coinbase "fee-upgrade program" (S49: >=$500k/mo proof -> as low as 0.0 maker) —
unverified in current terms; our cadence generates ~$25-30M/mo notional even at today's
fills, so if the program is real it reopens sol_coinbase at genuine mk0 as a US-legal
second venue. Verify before citing.

## 3. THE VENUE SWEEP (S57 research agent; fees from venue-owned pages)

Reachable maker rebate for a small institutional applicant: **Bybit MM program ONLY**
(application on weighted maker share >=0.03%, not a volume wall). Everything else:
Binance LP ($100M/30d to apply), Kraken (-0.3 at $250M/30d), KuCoin (-0.7 at ~$30M/30d
proof), Bitget LIP (entry easy, rebate competition-gated monthly), OKX (application viable
~$200k assets, MM terms contract-private), Hyperliquid (+1.5bp base maker = fatal; rebate
needs 0.5-3% venue share), Gate (+2.0bp standard — the old "-1bp standard" belief was
WRONG), Coinbase (0.0 floor, never negative; INTX LP needs 1% venue share, excludes US
persons), Lighter DEX (0/0 no threshold — unmeasured books, collector-worthy someday),
dYdX (0 at $25M/30d, thin books).

## 4. MEXC = DEAD VENUE (hard research, 5 threads, primary sources; do not revisit)

1. **FEES:** the advertised 0% maker is web/app MANUAL trading only. API futures trading
   (= our executor) has a separate OVERRIDING schedule: opened Mar 31 2026 at 1/5bp,
   raised May 1 to 4/6, raised **Jun 1 2026 to +6bp maker / +8bp taker** ("takes
   precedence over any rates or promotional offers"). 0-fee campaigns explicitly exclude
   "institutional accounts, market makers, project teams, and API users."
2. **ToS:** MEXC explicitly restricts unauthorized bots, HFT, and API algo trading —
   the strategy is a ToS violation on its face.
3. **COUNTERPARTY:** unlicensed everywhere that matters — Seychelles FSA enforcement
   May 2026 (operating without VASP license; "cannot assist in recovery of user funds"),
   exiting EU under MiCA Jul 2026, FCA warning list, OSC/Japan/HK warnings, US-blocked
   (accounts frozen on US-nexus detection). Clawbacks codified in their own risk-control
   guideline. Recourse = HKIAC arbitration from a dissolved-at-home entity.
4. **BEHAVIORAL:** verified recurring pattern of freezing PROFITABLE/fast/automated
   accounts (White Whale $3.15M frozen Jul-Nov 2025 for "two orders within the same
   second" — our machine does 130-170 RT/hr; exchange-admitted wrongful; hundreds of
   parallel reports; Trustpilot ~1.6/5 dominated by cash-out freezes).
5. **VOLUME:** headline volume substantially non-organic per every independent assessor
   (Cong et al. Benford failures; Kaiko bot-signature clustering + exclusion from its
   liquidity ranking; CCData grade C; Forbes 2022 grouping). CoinGecko 9/10 does not
   audit futures volume (self-reported).

## 5. STANDING OPEN ITEMS OUT OF S57 VENUE WORK

- **US-person/entity question on Bybit (blocking for LIVE):** Bybit does not onboard US
  persons. The MM application path needs a legal answer (entity/jurisdiction) before any
  live dollar on the lead cells. GREG.
- ZEC: G4 verified (-1.0bp), $119M/day tape, 0.61bp half-spread; 30d bins pulled
  (/tmp/backfill/ZECUSDT_30d_bins.json), collector added to the cron (first book window
  starts on Greg's manual dispatch or the 00:00 UTC cron). Gate + capacity = the cheap
  decisive test. Volume may be event-elevated — persistence unproven.
- Collector matrix now: sol/eth/doge/xrp/btc/zec on bybit + 5-coin Coinbase books.
- Coinbase fee-upgrade program verification (see §2).
