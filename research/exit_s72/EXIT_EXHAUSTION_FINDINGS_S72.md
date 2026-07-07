# S72 — Order-Flow Exhaustion vs. Price Exit, per individual trade (Kraken 5 majors)

**Descriptive research.** Changes no strategy/firing code. Legs come from the **LIVE** executor
`odcore.platform.run_kraken_cell` (SIM = LIVE); flow is the book collector's own `buy/sell` fields
on a 0.1s grid via `_liquidity_dive.build_channels`; with-trade flow = rolling `imb_signed * side`
(SMOOTH_SEC=20), exactly the S71 `shape_arc.py` pattern. **Book-only** (`/tmp/kbook/<coin>_book.jsonl`);
no tape/backfill used. Ride horizon = a **generous +120s** forward from `open_idx` (bounded by data),
chosen so it does *not* pre-decide the extend-vs-tail question.

**Discipline:** every quantity is measured **per individual trade first**, then tallied into
distributions (medians / p10 / p25 / p50 / p75 / p90 / counts). **No averaged shapes.** No rule about
what "marks" the exit is assumed — we report where the favorable **price extremum** (max of
`side*(mid[t]-mid[open])/mid[open]*1e4` bps over the ride) falls relative to the measured **flow**
features (post-entry flow peak; first return-to-balance i.e. flow ≤ 0 after its peak; half-peak decay).
All reporting is split **WINNERS (net_bps > 0)** vs **LOSERS (net_bps ≤ 0)**, winners as the headline.

Script: `research/exit_s72/exhaustion_price_exit.py`. Per-cell raw stats: `results_<coin>.json`.

Definitions used below (all per trade, seconds since entry unless noted):
- **price-ext** = time of the ride's favorable price extremum (the best mid-based exit).
- **close** = the LIVE executor's actual close time.
- **fav@ext / fav@close** = favorable mid move (bps) at the extremum / at the actual close.
- **tail** = `fav@ext − fav@close` (bps given back between the price top and the actual close; ≥0).
- **flow-zero** = time the with-trade flow first returns to balance (≤0) after its post-entry peak.

---

## Headline — WINNERS, per cell

| cell | n (win%) | med net bps | price-ext med [p10..p90] | close med [p10..p90] | fav@ext med (p90) | fav@close med | **tail** med (p75 / p90) | flow-zero med (%ret) |
|------|----------|-------------|--------------------------|----------------------|-------------------|---------------|--------------------------|----------------------|
| btc  | 1663 (69%) | +0.1 | **35s** [0..111] | 32s [8..80]  | +1.4 (7)  | +0.0 | **+1.0** (3.0 / 5.7)  | 54s (93%) |
| eth  | 781 (54%)  | +2.7 | **53s** [0..113] | 41s [12..100]| +5.3 (16) | +1.0 | **+3.6** (7.0 / 11.0) | 56s (94%) |
| sol  | 939 (62%)  | +3.0 | **51s** [0..113] | 41s [12..86] | +5.5 (15) | +0.6 | **+4.3** (7.4 / 12.1) | 52s (95%) |
| xrp  | 782 (52%)  | +3.4 | **60s** [5..114] | 43s [12..98] | +7.2 (19) | +1.4 | **+5.1** (9.3 / 14.4) | 52s (94%) |
| doge | 205 (53%)  | +5.8 | **68s** [4..117] | 69s [24..122]| +7.9 (27) | +2.1 | **+5.4** (9.9 / 18.0) | 51s (94%) |

## LOSERS, per cell (reported alongside)

| cell | n | med net bps | price-ext med | close med | fav@ext med | fav@close med | tail med (p90) | flow-zero med (%ret) |
|------|---|-------------|---------------|-----------|-------------|---------------|----------------|----------------------|
| btc  | 732 | -2.0 | **0s**  | 38s | +0.0 | -1.1 | +2.4 (6.4)  | 57s (92%) |
| eth  | 678 | -3.2 | 22s | 44s | +1.3 | -2.1 | +4.6 (12.1) | 54s (91%) |
| sol  | 583 | -3.6 | 18s | 45s | +1.9 | -2.5 | +6.1 (13.0) | 54s (92%) |
| xrp  | 736 | -3.8 | 28s | 44s | +2.4 | -2.6 | +6.6 (17.1) | 55s (92%) |
| doge | 180 | -6.0 | 25s | 81s | +2.6 | -3.1 | +6.6 (18.9) | 42s (93%) |

---

## Q1 — Where does price turn/flatten relative to the flow trajectory?

**Winners:** the favorable price extremum lands at a **median 35–68s** post-entry (btc earliest, doge
latest), with a wide per-trade spread (p10 ≈ 0–5s, p90 ≈ 111–117s). The measured ordering on the
median is **flow-peak (~37–41s) → price-top → flow-return-to-balance (~51–56s)**: the price tends to
top out while flow is **past its peak and declining but not yet back at balance**. Concretely, the
per-trade offset `price-ext − flow-zero` has median **−20s (btc), −9s (eth), −6s (sol), +2s (xrp),
+4s (doge)** — i.e. the price top generally precedes the full flow return-to-balance by a median ~0–20s,
shrinking to roughly coincident on xrp/doge.

**Losers:** the "extremum" is early and tiny — median price-ext **0s (btc), 18–28s (others)** with
fav@ext median 0.0–2.6 bps. Losers barely go favorable at all before turning adverse.

**Honest caveat (load-bearing):** the ordering above is a **median tendency, not a per-trade law**.
The `price-ext − flow-zero` distribution is very wide (btc winners p10=−78s, p90=+59s; similar on all
cells). On any single trade the price top can lead or lag the flow zero-crossing by ~a minute either
way. So "price turns as flow exhausts" is a soft central tendency, not a tight per-trade coincidence.

## Q2 — Window calibration: extend the ride, or are we giving back tail?

**Do NOT extend the window.** The ideal price exit is comfortably inside 120s: the extremum is pinned
at the 120s horizon edge for only **0–3%** of trades on every cell, and 89–98% of trades close within
120s. Ideal-exit medians are 35–68s. A generous but finite window already captures the best exit; no
evidence we need to look further out.

**Are we holding past the top (tail) or closing early?** Roughly a coin-flip, per trade — the executor
closes **near** the ideal top on the median, not systematically past it:

| cell | winners close AFTER top | close BEFORE top | close ≈ AT top (±0.5s) |
|------|-------------------------|------------------|------------------------|
| btc  | 49% | 47% | 5% |
| eth  | 45% | 54% | 1% |
| sol  | 43% | 53% | 0% |
| xrp  | 40% | 58% | 1% |
| doge | 47% | 51% | 2% |

On the median the actual close lands a few seconds **before** the ideal top for eth/sol/xrp (close 41–43s
vs top 51–60s → leaving a little upside) and essentially **at** the top for btc/doge (32 vs 35s; 69 vs 68s).

**But there is real recoverable tail on the ~40–49% of winners that close after the top**, and it grows
with volatility: winner **tail** median **+1.0 bps (btc) → +3.6 (eth) → +4.3 (sol) → +5.1 (xrp) → +5.4
(doge)**, with p90 of **5.7 / 11 / 12 / 14 / 18 bps** respectively. In mid-price terms winners capture
only a small fraction of the ride's peak favorable move (median capture-fraction ≈ 0.0–0.3; fav@close
median 0.0–2.1 vs fav@ext median 1.4–7.9). *Note:* net_bps is already positive because the maker
fill/half-spread mechanics are not in the mid-move number — this study measures the **mid** favorable
path, so "tail" is the extra mid move that exiting nearer the price top would have captured, not a claim
that the trades are unprofitable. The tail is the size of the exit-timing opportunity, and it is largest
on xrp/doge/sol (the higher-vol majors) and smallest on btc.

**Losers hold past their brief top.** 57–71% of losers close after their (early, small) price extremum
(btc 66%, doge 71%), turning a ~0–2.6 bps favorable blip into a −1.1 to −3.1 bps mid loss at close.

## Q3 — Is there a consistent lead/lag between flow and the price extremum?

**A consistent MEDIAN offset exists; a tight per-trade lead/lag does not.**

- **Flow-zero vs. actual close** (the coordinator's specific ask — does the flow return-to-balance line
  up with the trade end?): median **flow-zero − close = +20s** for btc/eth/sol winners and losers,
  **+15s** xrp winners, **+1s** doge winners (doge's longer trades let the flow finish near close),
  **−45s** doge losers (doge losers hold far past the flow-zero). So on the median the flow generally has
  **not** yet returned to balance when the trade closes — it exhausts ~15–20s **later** — except on doge.
  **However the per-trade spread is huge** (e.g. btc winners `flow-zero − close` p10=−35s, p90=+71s).
  **Conclusion: the flow zero-crossing does NOT reliably mark the trade's end on individual trades.** It
  is a wide distribution centered ~20s after the close; treat "flow-zero ≈ close" as false at the
  per-trade level.

- **Flow-zero vs. price extremum:** median `flow-zero − price-ext = +20s (btc), +9 (eth), +6 (sol),
  −2 (xrp), −4 (doge)` for winners — flow returns to balance around/after the price top on the median,
  again with a wide per-trade spread (~±60s). Losers: flow-zero lands +9 to +26s after their early price
  top.

- **Flow return happens** for 91–95% of trades within the 120s window on every cell — so the
  return-to-balance itself is a robust, near-universal feature; only its *timing relative to price/close*
  is loose per trade.

---

## Plain-language summary (what the data says)

1. **Winners' price top lands ~35–68s in and is well captured by a 120s window — no need to extend.** The
   best-exit time has a wide per-trade spread but essentially never sits at the horizon edge.

2. **The executor already closes winners near their price top on the median** (a few seconds early for
   eth/sol/xrp, ~at the top for btc/doge). It is *not* systematically bleeding the tail — but on the
   ~40–49% of winners that do close after the top there is **recoverable mid tail** of median 1–5 bps
   (p90 6–18 bps), scaling up with volatility (btc smallest, doge/xrp/sol largest). That is the size of
   the per-cell exit-timing prize if the exit could be pulled toward the price extremum on those trades.

3. **Order-flow exhaustion (return to balance) is a real, near-universal event (91–95% of trades) but a
   LOOSE per-trade clock.** On the median it lands ~15–20s *after* both the price top and the trade close
   (doge excepted, where it lands ~at close). Per trade it scatters by roughly ±a minute, so **the flow
   zero-crossing does not mark the price turn or the trade end on any individual trade** — it is a
   central tendency, not a trigger. The median ordering is *flow-peak → price-top → flow-zero*, i.e.
   price tends to turn while flow is decaying but before it fully exhausts.

4. **Losers look different and consistently so:** they barely go favorable (median fav@ext 0–2.6 bps),
   their price "top" is very early (0–28s), and they **hold past it 57–71% of the time**, ending negative.
   The exhaustion signal fires late relative to these fast adverse turns.

### Per-cell honest nulls / caveats
- **btc:** smallest tail of any cell (winner tail median +1.0, p90 +5.7 bps) and close lands ~at the top
  → the exit-timing opportunity here is marginal; btc winners' fav@close median is 0.0 bps (edge is in the
  maker spread, not the mid path). Weakest cell for an exit-tail edge.
- **doge:** smallest sample (n=385; grace=600 → fewer, longer trades) and the one cell where flow-zero ≈
  close for winners; its losers are the extreme "hold-past-the-top" case (81s close vs 25s top). Read doge
  distributions with the low n in mind.
- **eth / xrp:** lowest win-fractions (54% / 52%) but the largest winner tails (median 3.6 / 5.1, p90 11 /
  14 bps) → the exit-timing prize is biggest on these two plus sol.
- **All cells:** the price-ext ↔ flow relationship is a median tendency with wide per-trade dispersion; do
  not deploy the flow zero-crossing as a standalone per-trade exit marker on this evidence.

n per cell (individual trades, 120s ride window): btc 2395 (W1663/L732), eth 1459 (781/678),
sol 1522 (939/583), xrp 1518 (782/736), doge 385 (205/180).
