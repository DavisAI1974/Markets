# S72 — Order-Flow Exhaustion vs. Price Exit, per individual trade (Kraken 5 majors)

**Descriptive research.** Changes no strategy/firing code. Legs come from the **LIVE** executor
`odcore.platform.run_kraken_cell` (SIM = LIVE); flow is the book collector's own `buy/sell` fields
on a 0.1s grid via `_liquidity_dive.build_channels`; with-trade flow = rolling `imb_signed * side`
(SMOOTH_SEC=20), exactly the S71 `shape_arc.py` pattern. **Book-only** (`/tmp/kbook/<coin>_book.jsonl`,
~42h each); no tape/backfill used.

> **REVISION (S72 lead):** the first pass used a **+120s** ride horizon, which **clipped long-runner
> winners** and biased the "don't extend the window" conclusion. This version uses a **+600s (10 min)**
> post-entry horizon and **requires the full 600s window to exist per leg** (legs too close to the end of
> the book are dropped — 12/2395 on btc, ≤4 elsewhere). It re-measures where the favorable price extremum
> actually lands and explicitly counts what the old 120s window clipped. Edge-pin at 600s is **<1% on
> every cell**, so 600s is a sufficient horizon (the tops are captured, not cut off).

**Discipline:** every quantity is measured **per individual trade first**, then tallied into
distributions (medians / p50 / p75 / p90 / p95 / counts). **No averaged shapes / no mean-and-read.** No
rule about what "marks" the exit is assumed. Reporting is split **WINNERS (net_bps > 0)** vs
**LOSERS (net_bps ≤ 0)**, winners as the headline.

Definitions (per trade, seconds since entry unless noted):
- **price-ext** = time of the ride's favorable price extremum over the **full 600s** window (the oracle best mid exit).
- **fav@ext / fav@close** = favorable mid move (bps) `side*(mid[t]−mid[open])/mid[open]*1e4` at the extremum / at the actual close.
- **extra-beyond-120** = `fav@ext(600s) − fav@ext(first 120s)` = favorable mid the old window could not see (≥0).
- **tail** = `fav@ext − fav@close` (bps between the oracle top and the actual close).
- **flow-zero** = time the with-trade flow first returns to balance (≤0) after its post-entry peak.

Script: `research/exit_s72/exhaustion_price_exit.py`. Per-cell raw stats: `results_<coin>.json`.
Per-cell plots (gitignored PNGs, in `/tmp/kbook/`): `<coin>_kraken_winners_longride.png` —
individual winner rides (price panel: faint per-trade fav paths + a black dot at each trade's own top;
flow panel: 40 per-trade flow envelopes, 60s display-smoothed, `|` at each trade's own return-to-balance).

---

## Were we clipping long runners at +120s? — YES, on every cell

The old +120s window missed the majority of winners' price tops. With the honest 600s window:

| cell | winners n (win%) | **% of winners whose top is PAST +120s** | price-ext median [p75 / p90 / p95] (s) | edge-pinned at 600s |
|------|------------------|------------------------------------------|----------------------------------------|---------------------|
| btc  | 1655 (69%) | **65%** (1082/1655) | **242** [466 / 564 / 587] | 5/1655 (0%) |
| eth  | 776 (54%)  | **69%** (534/776)   | **251** [481 / 571 / 590] | 0/776 (0%) |
| sol  | 935 (62%)  | **68%** (632/935)   | **257** [463 / 562 / 587] | 1/935 (0%) |
| xrp  | 780 (52%)  | **69%** (541/780)   | **262** [485 / 568 / 589] | 4/780 (1%) |
| doge | 203 (53%)  | **67%** (135/203)   | **244** [439 / 542 / 582] | 0/203 (0%) |

The +120s median top was 35–68s; the true median top is **242–262s** — roughly **7×** later. The extremum
distribution is broad (p10 ≈ 0s: ~10–25% of winners top almost immediately; p95 ≈ 580–590s: a minority run
the whole window), but the mass sits well past 120s. **Edge-pin < 1% everywhere → 600s captures the tops;
no need to push the window further.**

### How much favorable move did the +120s clip cost? (extra bps beyond 120s)

| cell | extra-beyond-120, median over **all** winners | median over the **clipped** winners | p75 / p90 / p95 (all winners) |
|------|-----------------------------------------------|-------------------------------------|-------------------------------|
| btc  | +2.2 | **+4.6** | +6.7 / +12.0 / +15.5 |
| eth  | +4.0 | **+8.0** | +12 / +21 / +28 |
| sol  | +4.3 | **+9.2** | +12 / +22 / +32 |
| xrp  | +6.1 | **+11.1** | +16 / +28 / +39 |
| doge | +5.4 | **+11.3** | +15 / +34 / +51 |

So on the ~65–69% of winners that kept running, the price rose a further **median ~4.6–11.3 bps** (p90
12–34) *after* the old 120s cutoff, in mid terms. The clip cost scales with volatility (btc smallest,
xrp/doge largest). Full-window fav@ext medians roughly doubled vs the 120s window: btc +5.2, eth +11.3,
sol +12.3, xrp +15.8, doge +16.2 bps.

## LOSERS (alongside) — same clipping direction

| cell | losers n | med net | % top past +120s | price-ext med (s) | extra-beyond-120 med (clipped) | fav@ext med |
|------|----------|---------|------------------|-------------------|-------------------------------|-------------|
| btc  | 728 | -2.0 | 57% | 220 | +1.0 (+5.1) | +2.7 |
| eth  | 672 | -3.1 | 65% | 261 | +3.3 (+7.6) | +6.2 |
| sol  | 580 | -3.6 | 65% | 259 | +4.3 (+9.1) | +7.9 |
| xrp  | 734 | -3.8 | 62% | 253 | +4.1 (+10.9)| +9.4 |
| doge | 180 | -6.0 | 61% | 192 | +2.0 (+10.9)| +8.2 |

Losers also usually have a later favorable "top" than +120s, but a smaller one; they still end negative at
the actual close (fav@close median −1.1 to −3.1).

---

## Revised extend-vs-tail verdict

**The +120s "roughly balanced, small tail" reading was an artifact of the short window and is withdrawn.**
With the honest 600s window the executor closes **long before** the oracle price top:

| cell | winners close BEFORE the top | close AFTER the top | actual close median (s) |
|------|------------------------------|---------------------|--------------------------|
| btc  | **77%** | 21% | 32 |
| eth  | **83%** | 16% | 41 |
| sol  | **80%** | 19% | 41 |
| xrp  | **84%** | 15% | 43 |
| doge | **79%** | 21% | 69 |

The executor's median close is 32–69s in, while the oracle top is 242–262s in. So relative to a 10-minute
horizon the dominant pattern is **closing early and leaving mid upside on the table on persistent runners**
(the median tail given back, fav@ext − fav@close, is +4.6 btc / +7–9 eth·sol / +11 xrp / +5 doge bps; p90
14–34) — the *opposite* bias from what the clipped 120s window implied. In mid terms the executor captures
almost none of the eventual favorable extremum (winner capture-fraction fav@close/fav@ext ≈ 0 median;
fav@close median 0.0–2.1 vs fav@ext 5–16 bps).

**Load-bearing caveat (do not over-read the "ideal exit at ~250s"):**
1. This is an **oracle** best-exit with perfect hindsight over a 10-min look-ahead; a causal strategy cannot
   realize the full tail, and holding to ~250s carries reversal risk the oracle ignores.
2. Taking a **max over a long window mechanically pushes the argmax later and higher** even for a
   driftless walk — part of "median top at ~250s (≈40% of the 600s window)" is that statistic, not a
   structural top at 250s. What is *not* an artifact and *is* the headline: **65–69% of tops lie past 120s
   and carry real extra bps** — the old window genuinely clipped them.
3. net_bps is already positive (the maker fill/half-spread capture is not in the mid-move number); "tail"
   is the additional *mid* move a later exit would capture, not evidence the trades are unprofitable. It
   sizes the exit-timing opportunity, largest on xrp/doge/sol, smallest on btc.

## Flow exhaustion vs. the price top on the long ride

With the full window, **order-flow exhaustion is an EARLY event and does NOT mark the price top**:

| cell | flow returns to balance (median, % of trades) | flow-zero − price-ext (median) | flow-zero − actual-close (median) |
|------|-----------------------------------------------|--------------------------------|-----------------------------------|
| btc  | 66s (100%) | **−152s** | +31s |
| eth  | 62s (100%) | **−174s** | +20s |
| sol  | 57s (100%) | **−186s** | +20s |
| xrp  | 61s (100%) | **−162s** | +20s |
| doge | 66s (100%) | **−156s** | +20s |

The with-trade flow returns to balance at a **median 57–66s** — then the favorable price keeps running for
**~2.5–3 more minutes** to its eventual top (~245–260s). So flow-zero **precedes** the oracle price top by
a median ~150–190s. (This reverses the earlier 120s-window reading, where the truncated price top appeared
to arrive around/before flow-zero — another symptom of the clip.) Flow return-to-balance is now observed in
**100%** of trades within the 600s window (vs 91–95% in 120s), confirming it as a near-universal but
**early** event. Relative to the executor's actual close, flow-zero still lands a median **+20–31s later**
(unchanged from the first pass), with wide per-trade spread (btc winners p10 −27s, p90 +157s) — so the flow
zero-crossing is **not a tight per-trade marker** of either the close or the price top; it is a central
tendency only. The measured median ordering on winners is **flow-peak (~44–55s) → flow-zero (~57–66s) →
close (~32–69s, often before flow-zero) → price top (~245–262s)**.

---

## Plain-language summary (what the data says, corrected)

1. **We WERE clipping.** At +120s, 65–69% of winners' price tops were cut off. Extending to +600s (which is
   sufficient — <1% of tops hit the 600s edge) recovers a median **~4.6–11.3 extra bps** of favorable mid
   move on those clipped winners (p90 12–34 bps), scaling with volatility (btc smallest → xrp/doge largest).

2. **The executor exits well before the eventual price top** (77–84% of winners close before their oracle
   top; median close 32–69s vs median top 242–262s). Relative to a long horizon it is leaving mid upside on
   persistent runners, not giving back tail past a top. **Caveat:** this is a perfect-hindsight oracle over
   a 10-min look-ahead, mechanically biased late; a causal exit cannot capture the full tail and faces
   reversal risk. The real, un-caveated result is the *clipping* (point 1).

3. **Order-flow exhaustion is early and does not mark the price top.** Flow returns to balance at a median
   57–66s (100% of trades) while the favorable price keeps trending for ~2.5–3 more minutes. On the full
   ride, flow-zero *precedes* the oracle top by a median ~150–190s and lags the executor's close by a median
   ~20–31s, with wide per-trade spread — a central tendency, not a per-trade trigger.

4. **Losers** reach a later but smaller favorable top (median 192–261s, fav@ext 2.7–9.4 bps) and still close
   negative; same clipping direction as winners.

### Per-cell honest notes
- **btc:** smallest tail/extra-bps of any cell (clipped-winner median +4.6, p90 +12) and fav@close median
  0.0 — its edge lives in the maker spread, not the mid path; the weakest cell for an exit-extension gain.
- **eth / sol / xrp:** largest, most consistent clipping gains (clipped-winner median +8 to +11 bps, p90
  21–28); the exit-timing opportunity is biggest here.
- **doge:** smallest sample (n=383; grace=600 → fewer, longer trades) and highest per-trade variance
  (extra-beyond-120 p95 +51 bps); read its distributions with the low n in mind. Its losers hold longest
  (median close 81s).
- **All cells:** the "ideal exit ~250s" is an oracle statistic with a known late-bias from the long
  look-ahead; do NOT read it as a deployable exit time. The deployable facts are (a) 120s clips the majority
  of winner tops, and (b) flow exhaustion is an early, non-marking event relative to the price top.

n per cell (full-600s ride window; W / L): btc 2383 (1655 / 728), eth 1448 (776 / 672),
sol 1515 (935 / 580), xrp 1514 (780 / 734), doge 383 (203 / 180).
