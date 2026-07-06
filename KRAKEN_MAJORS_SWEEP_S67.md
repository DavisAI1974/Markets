# Kraken Liquid-Majors Sweep — S67

**Task:** find LIQUID MAJOR coins on **Kraken** (only venue we trade) *beyond* our current 5-coin
majors sleeve that deserve their own maker mean-reversion / flip-zigzag swing cell. Research only —
nothing deployed, no cells decided, odcore/ untouched.

**Excluded by mandate (already have cells):** BTC (XXBTZUSD), ETH (XETHZUSD), SOL (SOLUSD),
XRP (XXRPZUSD), DOGE (XDGUSD).

---

## Summary

Pulled the full Kraken public REST universe and ranked every USD-quoted online pair by 24h USD
notional, then compared each candidate's **maker fee schedule field-by-field against our 5 majors**.
Headline findings:

1. **Fee viability is NOT the gate people fear.** All classic large-caps on Kraken sit on the **exact
   same maker schedule as BTC/ETH/SOL/XRP/DOGE** (`fees_maker` starts 0.25% → hits **0.0% at the $10M
   30d-volume tier**, our current tier). So they are **0bp maker for us, same as our existing sleeve —
   not fatal.** A second cohort of newer listings (HYPE, XPL, and various alts) sits on a **different
   but *better* 0.23%-start schedule that reaches 0.0% at $5M and −0.02% (a REBATE) at $10M** — i.e.
   *superior* to our majors at our tier, not a fatal kr_mk2-style 1bp schedule. **I found no liquid
   recognizable major on a fatal (never-reaches-0) maker schedule.** The stablecoin/fiat schedule
   (0.20% start, no 0-floor) is the only "different" one, and those are excluded anyway.

2. **The real gate is LIQUIDITY, and it produces a surprise:** reputational "majors" like **DOT, POL,
   ATOM, ARB, OP, FIL, ETC, UNI, ICP, HBAR, FET** are **thin on Kraken USD** (DOT only ~$363k/24h,
   ATOM ~$134k, ARB ~$97k, OP ~$75k). On Kraken the genuinely deep non-top-5 books are a *different*
   set: **HYPE, SUI, ADA, ZEC, XMR, AVAX, XLM, AAVE, LTC, NEAR, TAO, LINK, BCH, BNB, TON.** Name
   recognition ≠ Kraken depth.

**Method / provenance.** Endpoints: `GET /0/public/AssetPairs` (1507 pairs → 687 USD-quoted → 637
online with tickers) for `altname`/`wsname`/`quote`/`fees_maker`/`status`; batched
`GET /0/public/Ticker?pair=…` (100 pairs/call) for 24h base volume `v[1]`, 24h trade count `t[1]`,
last `c[0]`. 24h USD notional = `v[1] × last`. **Ticker snapshot: 2026-07-06 19:51 UTC.** Bands mirror
the S66 eligibility doc: **LARGE ≥ $1M/24h, MID $250k–$1M, SMALL $100k–$250k, THIN < $100k.** Tape
loader `backfill_kraken_trades.py --days 1` used to confirm top picks pull cleanly.

Fee-schedule column legend:
- **SAME** — byte-identical maker schedule to BTC/ETH (0.25→0.0 @ $10M). **0bp maker for us. Safe.**
- **BETTER(0.23)** — 0.23%-start schedule; 0.0 @ $5M, **−0.02 rebate @ $10M**. Even better for us.
- (No candidate below carries a fatal/elevated schedule.)

---

## Ranked candidate table (LARGE + MID bands, all viable)

| pair (altname) | wsname | coin | 24h USD vol | 24h trades | last px | fee sched vs majors | band | capacity note ($5k maker leg) |
|---|---|---|---:|---:|---:|---|---|---|
| HYPEUSD | HYPE/USD | HYPE | $12,935,199 | 10,573 | 71.56 | **BETTER(0.23)** | LARGE | $539k/hr; leg = 0.9% of hourly |
| SUIUSD | SUI/USD | SUI | $10,568,394 | 11,262 | 0.7475 | SAME | LARGE | $440k/hr; leg = 1.1% |
| ADAUSD | ADA/USD | ADA | $9,667,111 | 14,924 | 0.18378 | SAME | LARGE | $403k/hr; leg = 1.2% |
| ZECUSD | ZEC/USD | ZEC | $5,822,586 | 5,544 | 450.36 | SAME | LARGE | $243k/hr; leg = 2.1% |
| XMRUSD | XMR/USD | XMR | $5,601,436 | 11,097 | 323.11 | SAME | LARGE | $233k/hr; leg = 2.1% |
| AVAXUSD | AVAX/USD | AVAX | $3,622,878 | 4,506 | 6.97 | SAME | LARGE | $151k/hr; leg = 3.3% |
| XLMUSD | XLM/USD | XLM | $3,382,387 | 6,446 | 0.19922 | SAME | LARGE | $141k/hr; leg = 3.5% |
| AAVEUSD | AAVE/USD | AAVE | $2,965,433 | 6,545 | 96.03 | SAME | LARGE | $124k/hr; leg = 4.0% |
| LTCUSD | LTC/USD | LTC | $2,752,372 | 7,395 | 45.25 | SAME | LARGE | $115k/hr; leg = 4.4% |
| NEARUSD | NEAR/USD | NEAR | $2,294,879 | 6,012 | 2.0725 | SAME | LARGE | $96k/hr; leg = 5.2% |
| TAOUSD | TAO/USD | TAO | $2,244,070 | 5,135 | 215.64 | SAME | LARGE | $94k/hr; leg = 5.3% |
| LINKUSD | LINK/USD | LINK | $1,982,978 | 5,211 | 8.0024 | SAME | LARGE | $83k/hr; leg = 6.1% |
| BCHUSD | BCH/USD | BCH | $1,815,818 | 3,312 | 245.52 | SAME | LARGE | $76k/hr; leg = 6.6% |
| BNBUSD | BNB/USD | BNB | $1,232,676 | 2,609 | 584.39 | SAME | LARGE | $51k/hr; leg = 9.7% |
| TONUSD | TON/USD | TON | $1,214,256 | 4,633 | 1.77 | SAME | LARGE | $51k/hr; leg = 9.9% |
| XPLUSD | XPL/USD | XPL (Plasma) | $1,168,925 | 4,809 | 0.1082 | **BETTER(0.23)** | LARGE | $49k/hr; leg = 10.3% |
| CRVUSD | CRV/USD | CRV | $846,581 | 3,181 | 0.21428 | SAME | MID | $35k/hr; leg = 14.2% |
| TIAUSD | TIA/USD | TIA | $809,788 | 3,727 | 0.3846 | SAME | MID | $34k/hr; leg = 14.8% |
| TRXUSD | TRX/USD | TRX | $688,821 | 2,937 | 0.32838 | SAME | MID | $29k/hr; leg = 17.4% |
| WLDUSD | WLD/USD | WLD | $635,547 | 2,449 | 0.4136 | SAME | MID | $26k/hr; leg = 18.9% |
| PYTHUSD | PYTH/USD | PYTH | $559,844 | 5,293 | 0.04578 | SAME | MID | $23k/hr; leg = 21.4% |
| ALGOUSD | ALGO/USD | ALGO | $542,226 | 2,182 | 0.08879 | SAME | MID | $23k/hr; leg = 22.1% |
| ONDOUSD | ONDO/USD | ONDO | $535,478 | 2,386 | 0.33831 | SAME | MID | $22k/hr; leg = 22.4% |
| YFIUSD | YFI/USD | YFI | $487,128 | 2,421 | 2569.5 | SAME | MID | $20k/hr; leg = 24.6% |
| INJUSD | INJ/USD | INJ | $466,868 | 2,178 | 4.883 | SAME | MID | $19k/hr; leg = 25.7% |
| AEROUSD | AERO/USD | AERO | $455,372 | 1,964 | 0.5781 | SAME | MID | $19k/hr; leg = 26.4% |
| UNIUSD | UNI/USD | UNI | $447,523 | 1,776 | 3.1965 | SAME | MID | $19k/hr; leg = 26.8% |
| ICPUSD | ICP/USD | ICP | $412,398 | 1,569 | 2.224 | SAME | MID | $17k/hr; leg = 29.1% |
| KASUSD | KAS/USD | KAS | $407,899 | 1,866 | 0.03033 | SAME | MID | $17k/hr; leg = 29.4% |
| HBARUSD | HBAR/USD | HBAR | $394,957 | 2,410 | 0.07431 | SAME | MID | $16k/hr; leg = 30.4% |
| FETUSD | FET/USD | FET | $374,514 | 1,728 | 0.1729 | SAME | MID | $16k/hr; leg = 32.0% |
| DOTUSD | DOT/USD | DOT | $362,968 | 3,209 | 0.8892 | SAME | MID | $15k/hr; leg = 33.1% |
| ENAUSD | ENA/USD | ENA | $316,365 | 1,157 | 0.0788 | SAME | MID | $13k/hr; leg = 37.9% |
| IMXUSD | IMX/USD | IMX | $311,406 | 1,682 | 0.1415 | SAME | MID | $13k/hr; leg = 38.5% |
| JTOUSD | JTO/USD | JTO | $289,359 | 1,955 | 0.76215 | SAME | MID | $12k/hr; leg = 41.5% |
| PENDLEUSD | PENDLE/USD | PENDLE | $263,104 | 1,411 | 1.452 | SAME | MID | $11k/hr; leg = 45.6% |

*(MID also includes ONDO/AERO/PENGU/VANRY/ZRO/MINA/DYDX/DASH/DAI-excluded etc.; SMALL band $100–250k
adds MANA, FIL, GRT, POL, KSM, WIF, SEI, JUP, ARB, LDO, RENDER, ATOM, MANA — all SAME schedule but
capacity-thin, a $5k leg is 40–100%+ of hourly volume.)*

---

## TOP PICKS (3–8 coins most worth a cell)

Ranked by depth-gated fillability at 0bp/rebate maker. All confirmed to pull a clean full 24h tape.

1. **HYPE (HYPEUSD)** — $12.9M/24h, 10.6k trades. Deepest non-top-5 book on Kraken and on the
   **BETTER 0.23 schedule = −2bp maker rebate at our tier** (fees work *for* us). $5k leg is <1% of
   hourly vol. Tape verified: 10,532 trades → 4,311 1s-bins/day. **Strongest single candidate.**
2. **SUI (SUIUSD)** — $10.6M/24h, 11.3k trades, SAME schedule (0bp). Deep, high trade-count (dense
   tape = good for swing turn detection). Tape verified: 11,273 trades → 2,648 bins/day.
3. **ADA (ADAUSD)** — $9.7M/24h, **14.9k trades (highest trade count of any candidate)**, SAME
   schedule. Classic clean major, dense oscillatory tape. Tape verified: 14,929 trades → 4,579
   bins/day.
4. **XMR (XMRUSD)** — $5.6M/24h, 11.1k trades, SAME schedule. Deep + very high trade density; Monero
   mean-reverts hard, well-suited to flip-zigzag. Clean major.
5. **ZEC (ZECUSD)** — $5.8M/24h, SAME schedule. Deep book, clean privacy-coin major, high $/px so
   tick granularity is favorable for maker placement.
6. **AVAX (AVAXUSD)** — $3.6M/24h, SAME schedule. Textbook liquid L1 major, $5k leg = 3% of hourly.
7. **LTC (LTCUSD)** — $2.75M/24h, 7.4k trades, SAME schedule. Oldest liquid major after BTC; steady
   deep book.
8. **XLM / AAVE / NEAR / LINK / BCH** — the next tier of clean SAME-schedule LARGE majors
   ($1.8–3.4M/24h), all viable for a cell with $5k legs at 3–7% of hourly. Give cells as capacity
   allows.

**Practical cut:** the first ~11–15 rows (HYPE→TON, all LARGE ≥$1M/24h) are the defensible cell set —
a $5k maker leg is ≤10% of hourly volume, book-fillable. Below ~$1M/24h (MID band) the same $5k leg
becomes 15–45% of hourly volume; those are cell-able only at reduced size and should be treated as
"capacity-thin, size down," not primary.

---

## REJECTED / FLAGGED

- **Our 5 (excluded by mandate):** XBTUSD, ETHUSD, SOLUSD, XRPUSD, XDGUSD — already have cells.
- **Stablecoins / fiat (top of the volume list but not tradeable majors):** USDT ($169M), USDC
  ($38M), EUR ($20.8M), USDE, USDG, GBP, AUD, EURC, DAI, PYUSD. On the **stablecoin fee schedule
  (0.20% start, no 0-floor)** and have no swing edge — excluded.
- **PAXG (PAXGUSD, $750k)** — tokenized gold commodity, not a crypto major. Flagged/excluded.
- **Memecoins with high notional but not "clean majors":** FARTCOIN ($2.2M), PUMP ($1.2M), BONK
  ($990k), PEPE ($760k), SPX, TLM, ZEUS, USELESS, PENGU, WIF. Deep enough to fill, but meme
  microstructure (event-driven jumps, not oscillatory) is a poor fit for a mean-reversion swing —
  flagged, not recommended. (Note: several sit on the BETTER 0.23 rebate schedule, so revisit only
  if a meme-specific strategy is ever built.)
- **Newer thin/obscure BETTER-schedule listings** (SYN, CAP, MON, SLX, CC, NIGHT, BILL, NES, ARX, AI,
  PLAY) — rebate-eligible fee-wise but low recognition and/or MID-to-thin depth; not clean majors.
- **Reputational majors that are TOO THIN on Kraken USD (the surprise):** POL ($234k), DOT ($363k),
  ATOM ($134k), FIL ($149k), ARB ($97k), OP ($75k), APT ($76k), ETC ($31k), STX, XTZ, EGLD, FLOW,
  RUNE, 1INCH. All on the SAME (0bp) schedule — **fee is fine, liquidity is not.** A $5k maker leg is
  30–100%+ of hourly volume; these would be capacity-starved cells. MATIC/FTM/MKR/THETA/EOS **have no
  USD pair on Kraken** (MATIC migrated to POL). Do not prioritize on name recognition.

---

## Data caveats

- **Ticker is a single 24h snapshot (2026-07-06 19:51 UTC).** 24h volumes swing hard day-to-day
  (news, regime); a coin near a band boundary can move bands. Re-pull before committing capital, and
  ideally average a few days.
- **Fee tier is account-wide by trailing 30d USD volume**, not per-pair. This report assumes our
  current tier is the **$10M tier** (the only tier at which the major schedule yields the stated 0bp
  maker on BTC/ETH). If our real 30d volume is *below* $10M, then majors would be >0bp maker (fatal),
  and the BETTER(0.23) coins would also not yet be at rebate — **verify the actual account tier
  before treating any of these as 0bp.** The relative ranking (which coins are deep, which schedule
  each is on) is tier-independent; the absolute bp is not.
- Notional = `24h base volume × last`; a fast-moving `last` slightly skews notional but not banding.
- Capacity note uses flat `24h_notional / 24` for hourly; real intraday volume is U-shaped, so the
  overnight fraction is worse than the average shown. Treat the % as a floor on how chunky a leg is.
- Depth here is inferred from *traded* volume, not order-book snapshot. Before sizing a cell, confirm
  actual top-of-book / L2 depth (a separate Depth-endpoint pull) — traded volume is a proxy for
  fillability, not a guarantee.
