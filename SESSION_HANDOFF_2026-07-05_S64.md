# SESSION HANDOFF — S64 (2026-07-05) — fee/rebate reality + the eligible-pair BASKET + the ANTI-CIRCLING inventory

Branch reconciled to canonical `5c5vg9` at open (designated `claude/s64-markets-kickoff-gee6os` was cut
from an S59-era parent AGAIN — reset --hard; docs committed + pushed there). **READ `STRATEGY_INVENTORY.md`
FIRST** (new S64 anti-amnesia doc — all our live strategies/tools/cells + the TRIED-&-DEAD ledger).

## ⭐ THE PROCESS FIX (Greg, load-bearing — we waste days/weeks reinventing the wheel)
New standing rules in CLAUDE.md: (1) `STRATEGY_INVENTORY.md` = canonical list of EVERYTHING; read at start;
(2) **UPDATE IT AS YOU GO, not at session end** (esp. the TRIED-&-DEAD ledger); (3) **VENUE IN FILE NAMES**
for deployables (`kraken`); (4) PER-COIN LAW — ditch per coin, keep where it works, never global-kill.
Root cause this session: a whole benchmark ran on BARE flow-lean, ignoring the deployed stack + the E300 family.

## WHAT WE LEARNED (in order)
1. **Job 1 still DATA-gated:** the Kraken book is still the same ~30h LOW-EDGE window (ETH ideal-fill −2.04,
   BTC −1.11); can't grade fill viability on it. Tardis.dev has Kraken L2 book (depth-1000; June-1/July-1 free;
   full 27d = ~1mo paid Spot sub) — the fast unblock for a normal-edge multi-day book.
2. **Edge is REAL but the raw lean is marginal-by-construction (benchmark):** 0.5–1 bp gross < ~0.8 bp
   adverse-selection fill cost. Naive-MM Sharpe −109; our filter/timing rescues it. The lever the literature
   says makes MM work = **maker REBATES**. lean_lab markout independently confirmed ETH/BTC (z+4–9, band-wide).
3. **Kraken side-convention CORRECT** (contemp flow→price +0.11, same sign as Coinbase +0.33) → SOL's reversal
   is genuine microstructure, not wiring. (Uploaded `kraken_sol_loader.py` would sign-flip our tape — use --aggressor-side.)
4. **FEE/REBATE REALITY (nailed):** Kraken maker 0.25%→**0.00% at $10M/30d**→neg only at $500M (majors).
   30d volume is **AGGREGATE across all pairs** (majors count toward the tier). **Rebate −2bp = LOW-LIQ pairs
   ONLY** (BTC/ETH/SOL/XRP/DOGE excluded), $10M+/30d. **US-legal rebate = Kraken alts only** (Bybit/OKX US-out).
   Eligible set churns ~monthly (liquidity-driven); detect live via AssetPairs negative-maker-tier signature.
5. **IDLE finding (Greg's Q):** under honest maker fills the majors sit **~57% IDLE** (fill ~40%, forced-taker
   ~58%) — the fill leak is ALSO a capital-utilization problem. Fill-the-gaps = **maker DIVERSIFICATION** (per-pair
   edges ~0-correlated, ETH↔BTC −0.03 → √N Sharpe), NOT taker-entry.
6. **Taker-entry DEAD** (tested): fee (11bp) > captured edge (1–7bp avg); ORACLE (+11 ETH) works but no
   entry-time swing-SIZE predictor exists (vol AUC 0.567≈chance). Same dead-direction wall.
7. **THE ELIGIBLE SWEEP:** 720 eligible pairs (AssetPairs neg-maker signature) → pulled top ~30 by vol → gated.
   ⚠ raw markout gate is TREND-contaminated (SLX −52%/NEX +48% "pass" = trending, not edge). **Per-coin TUNED
   gate (window is the key lever) + per-week stability →** ~6 confirmed: **APE, RE (fwd); XDC, SHX, AIOZ, ARPA
   (rev)**. SHX/AIOZ only pass at **W2400** (tune window per coin!). HYPE ($9.3M, most liquid) = null (efficiency
   gradient: liquid=weak edge, thin=strong). 7-day pairs (SYN/GWEI/NIGHT/HYPE) need longer pulls for per-week.
8. **STACKING (Greg — don't treat lean as the only tool):** deployed majors = lean + **early-arm** (the lift:
   ETH −0.83→+3.44 on realbins) + deep-bail + cover-grace. **E300 death-cut ON the lean ride is PER-COIN (Greg):
   KEEP on BTC (+0.20, helps marginally), DROP on ETH (−0.41)** — do NOT pool to "neutral"/global-kill (per-coin
   law). E300 ALSO runs as its own SLEEVE (family B). Window flag: early-arm HURT BTC on realbins (opposite of
   S63 REST tape) — point estimates window-fragile; confirm 2nd window before sizing.

## THE ARCHITECTURE (where it's heading)
Two-sleeve (+basket) Kraken book: **majors sleeve** (lean+early-arm+deep-bail+cover-grace; unlocks the $10M
tier via deep volume, 0bp) + **eligible-basket sleeve** (per-coin tuned lean, earns −2bp rebate once at tier) +
**E300 sleeve** (family B, uncorrelated). All ~0-correlated → √N Sharpe + fills the majors' 57% idle. The
rebate is capped by eligible-pair volume (thin), and the ramp to $10M costs fees — real but bounded.

## KRAKEN LIVE WIRING (design done, S64): WS v2 public (book/trade)→incremental RollingFlow→executor→auth WS
(add_order post_only / amend_order re-quote / cancel / executions). Token via REST GetWebSocketsToken. NO spot
testnet → validate with tiny real size. Decision core (platform.run_stream) done; need the `KrakenLiveAdapter`
+ safety (staleness kill-switch, reconciliation, rate limits). Sequence: prove basket edge → adapter → tiny size.

## NEXT (S65)
1. **Build the multi-sleeve basket simulator** (name `*_kraken_*`) through the REAL executor (early-arm+deep-bail
   +cover-grace), with tier/rebate/honest-fill wired — put an honest $/hr + Sharpe on the two-sleeve+basket book.
2. Full per-week+reversed re-gate on the ~6-pair shortlist + longer pulls on SYN/GWEI/NIGHT/HYPE (pull running).
3. E300 as its own sleeve (correlation vs lean sleeve).
4. (Greg) Tardis paid month for a normal-edge multi-day Kraken book → finally grade Job 1 fill for real.
Files (scratchpad, ephemeral — re-derive from inventory): leanlab_kraken/rebate_gate/tuned_gate/basket_map2/
idle_and_corr/taker_entry/swingsize/stack_e300. Eligible ranked list: /tmp/rebate_tape/eligible_ranked.json.
