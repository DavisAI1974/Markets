# S74 — Per-cell ascension equations, clean discriminators, and the energy-gate fine-tune

> ⛔⛔ S75 CORRECTION (Greg) — THIS DOC IS THE WRONG FRAME; KEPT AS A RECORD. It treats the equations as sources of
> SCALAR "features" (peak / equation-derived numbers) and grades non-overlap of those scalars. That is a SNAPSHOT,
> not a shape. The equations are EQUATIONS OF CURVES — 8 distinctive shapes/coin, kept SEPARATE, NEVER summed. The
> gate MATCHES CURVE SHAPES (enter + exit), whole-curve via the sampled arcs or the 8 split pieces — never a
> scalar/sum. See STRATEGY_INVENTORY #0f + CLAUDE.md S75. The scalar "clean discriminator / energy-gate" findings
> below are IN-SAMPLE scalar results and are NOT the method going forward.

Scope: BTC/ETH/SOL/XRP (majors). DOGE excluded. All trade decisions come through the LIVE
`run_kraken_cell` via `sol_ascent_eq.extract()` / the `arc_gate.py` builder — nothing in the executor,
fills, or fees was reimplemented. The signal object is the normalized signed imbalance-ratio arc in [-1,1]
(NO raw volume, NO price). Averaging is used ONLY to draw the archetype pictures (mean arcs); every gate
decision is per-trade.

Scripts (all in `research/shape_s71/`): `archetype_fit.py`, `per_trade_shape.py`, `sep_diag.py`,
`natural_extent.py`, `gate3.py`, `gate_final.py`, `archetype_plot.py` (fig `archetype_ascension.png`).

Window/clip discipline: every entry feature is computed strictly on the pre-onset limb (t<=0); nothing uses
the post-onset tail, so the fixed +60s POST clip in `quad_means.npz`/`regroup2.py` does NOT touch any result
here. (That clip WILL matter for the future EXIT/decay equation — flagged at the end.)

---

## HEADLINE (result-disciplined)

Greg's intuition was that because the 4 archetype graphs look visibly distinct, a per-trade equation on the
ascension shape should separate the cells cleanly and could REPLACE the energy signal. What the data actually
says:

1. **The 4 archetype MEANS are genuinely distinct, and each cell has a unique, fittable ascension equation**
   (below). The graphs are real.
2. **But per-trade, winner vs loser distributions OVERLAP heavily on EVERY scale-free shape/equation feature
   we could build** — ascent rate, curvature, hockey blade/handle, convexity, integrated/cumulative flow,
   dip depth, below-zero fraction, ignition timing, time-extent, and the normalized-shape fingerprint. This
   is true for energy (`peak`) AND for every equation-derived feature. The visible distinctness is a property
   of the MEANS between OUTCOME-defined cells, not of the pre-trade-decidable per-trade distributions.
3. Therefore an equation cannot CLEANLY REPLACE energy in the strong sense (no single feature gives
   non-overlap). **However**, the equation IS the better tool on SOL specifically — the one coin where the
   energy gate fails — and every discriminator that shows any edge measures the SAME thing:
   **losers ignite LATE from a DEEP/LONG below-zero hole; winners are born earlier and top out higher.**
4. New, measured fact (Greg's "missing entry data"): the old 45s window was **clipping a large fraction of
   ascension heads** — ~40-54% of ETH/SOL/XRP legs are born earlier than -45s. Recovering the full head
   modestly sharpens separation on ETH shorts, but does not manufacture clean non-overlap anywhere.

Net recommendation: KEEP the energy gate on BTC/ETH/XRP (it works there); on SOL, REPLACE the energy skip
with a light **cumulative-flow "deep-hole" skip** (`late_integral`), which recovers the winners energy was
wrongly skipping. Details and numbers below.

---

## (a) The 4 per-cell ascension equations

### Universal functional form (same shape, cell-specific numbers)
Every cell's mean pre-onset ascension limb is a **convex hockey stick**: a near-flat/low "handle" then a
steeper "blade" into onset. Two equivalent fits both work on the mean arc:

- Quadratic:  `flow(t) = a + b·t + c·t²`, t in seconds (-45..0). `c > 0` (convex) in ALL 16 cells.
- Piecewise hockey:  flat handle for `t <= t_break`, steep blade for `t > t_break`.

The hockey fit wins on R² for the means (e.g. SOL long-winner R²=0.992, long-loser 0.987). "Winners hockey /
losers linear" is FALSE as stated — both winners and losers are hockey-shaped (both convex, c>0). What
differs per cell are the NUMBERS: peak energy, how deep/long the handle sits below zero, and blade timing.

### Per-cell coefficients (from the mean arcs; `archetype_fit.py`)
Quadratic `b` (linear rate), `c` (convexity), `peak`=flow at onset, `below0`=% of limb below zero:

| coin | cell | start | peak | min | below0 | b | c |
|---|---|---|---|---|---|---|---|
| SOL | short-loser  | -0.116 | **+0.010** | -0.132 | 19% | 0.0179 | 0.00018 |
| SOL | short-winner | -0.095 | +0.127 | -0.095 | 32% | 0.0221 | 0.00026 |
| SOL | long-winner  | -0.227 | **+0.347** | -0.230 | 47% | 0.0284 | 0.00027 |
| SOL | long-loser   | -0.259 | +0.299 | -0.267 | **63%** | 0.0304 | 0.00034 |
| BTC | short-loser  | -0.128 | **+0.042** | -0.130 | 66% | 0.0107 | 0.00020 |
| BTC | short-winner | -0.097 | +0.179 | -0.097 | 7% | 0.0146 | 0.00024 |
| BTC | long-winner  | -0.288 | **+0.365** | -0.290 | 69% | 0.0315 | 0.00039 |
| BTC | long-loser   | -0.292 | +0.287 | -0.322 | **79%** | 0.0340 | 0.00046 |
| ETH | short-loser  | -0.096 | **+0.016** | -0.096 | 13% | 0.0165 | 0.00024 |
| ETH | short-winner | -0.056 | +0.169 | -0.056 | 4% | 0.0231 | 0.00037 |
| ETH | long-winner  | -0.181 | **+0.341** | -0.200 | 67% | 0.0339 | 0.00046 |
| ETH | long-loser   | -0.247 | +0.285 | -0.289 | 66% | 0.0313 | 0.00037 |
| XRP | short-loser  | -0.068 | +0.131 | -0.107 | 34% | 0.0342 | 0.00060 |
| XRP | short-winner | -0.063 | +0.167 | -0.063 | 30% | 0.0236 | 0.00040 |
| XRP | long-winner  | -0.252 | **+0.453** | -0.262 | 53% | 0.0377 | 0.00045 |
| XRP | long-loser   | -0.255 | +0.316 | -0.255 | **62%** | 0.0358 | 0.00049 |

Universal cell characteristics (hold across the 4 majors; only numbers re-fit per coin):
- **SHORT-LOSER** = the failed-ignition short: peak barely above zero (SOL +0.01, BTC +0.04, ETH +0.02;
  XRP is the exception at +0.13, its shorts barely differ). It never builds energy.
- **SHORT-WINNER** = short that builds moderate energy (peak +0.13..+0.18).
- **LONG-WINNER** = deep start, tops HIGHEST (peak +0.34..+0.45), rises earliest/steadily.
- **LONG-LOSER** = same deep start as long-winner but tops LOWER (peak +0.29..+0.32), and spends MORE of the
  limb below zero (below0: SOL 63 vs 47, BTC 79 vs 69, XRP 62 vs 53; ETH is the one near-tie 66 vs 67) with a
  deeper dip. It is the **late ignition from a deeper hole that tops out weaker.**

### Time-extent equation (the per-cell NUMBER on the time axis; `natural_extent.py`)
Not clipping at 45s and detecting each leg's birth (bottom of the final hole) gives a per-cell TIME-EXTENT.
LONG signals genuinely live longer than SHORT, and within a class winners are born a bit earlier than losers.
Median argmin-birth extent (s), and fraction of legs born before -45s:

| coin | SHORT-WIN | SHORT-LOSE | LONG-WIN | LONG-LOSE | born<-45s (S/L) |
|---|---|---|---|---|---|
| BTC | 22.1 | 16.8 | 31.9 | 30.7 | 23% / 34-36% |
| ETH | 47.0 | 31.8 | 50.4 | 38.5 | 41-50% / 46-54% |
| SOL | 36.4 | 35.3 | 43.0 | 44.0 | 42-46% / 47-48% |
| XRP | 37.0 | 33.5 | 49.2 | 42.2 | 40-44% / 48-51% |

So the ascension time-extent IS a per-cell signature: short≈long-duration axis, and winners > losers extent
(born earlier) on ETH/XRP/BTC. **The 45s clip was hiding roughly half of ETH/SOL/XRP legs' heads** — Greg's
"missing vital entry data", confirmed. (Bound honesty: even a 150s look-back hit the prior-leg-close/book
boundary on 29-34% of legs, so a minority of births are still truncated; those are aligned at the boundary.)

---

## (b) Clean discriminators — where distributions do and DON'T separate

Method: per cell x category, take the loser-tail of a feature (the k% most loser-like) and read the win-rate
IN that tail. If it stays near the category base win% → NO separation. Depression far below base → a
loser-enriched skip zone. (`sep_diag.py` fixed-45s; `natural_extent.py` full-head + 45s-truncated.)

**The honest verdict: NO feature — energy or equation — produces clean non-overlap.** The best any single
feature does is depress a 10% loser-tail win-rate by ~10-20 points (a loser-ENRICHED tail, not a pure-loser
zone). Result per coin:

- **SOL**: essentially NOTHING separates in the 45s window (best tails 53-56% vs 59-64% base). Energy `peak`
  does not separate per-trade either (the documented failure). Natural-extent does not rescue it.
- **BTC**: weak everywhere (base 66-73%, tails hold 58-65%).
- **ETH**: the strongest separator, and it SHARPENS with the full head. ETH-SHORT natural-extent flags
  `extent`, `t_infl`, `rise_last3`, `below0`, `dip`, `peak` (loser-tail win% ~40-44 vs 56 base) where the
  45s-truncated version flagged only `peak`. ETH-LONG: `net_area_ratio`, `cum_final`, `min_asc` flag
  (loser-tail ~38-44 vs 52 base).
- **XRP**: `b_blade` (SHORT, 37% vs 52) and the dip/`late_integral` group (LONG, ~42% vs 51) flag modestly.

**Every feature that shows an edge measures ONE physical thing** — losers spent more of the pre-onset limb
DEEP and LONG below zero and ignited LATE. These are correlated views of the same "deep-hole / late-blade"
tell:
- integrated/cumulative flow (Greg's suggestion, and the cleanest single group):
  `late_integral` (time-weighted ∫arc), `cum_final` (∫arc), `net_area_ratio` (signed area above vs below 0),
- hole depth: `min_asc`, `dip`;   time in hole: `below0`, `frac_late_neg`, `t_last_neg`;
- born-early: `extent` (winners born earlier);   `b_blade` (late-blade sign).

Concrete cleanest single discriminator = **`late_integral`** (integrate the pre-onset arc, weighting toward
onset). The deepest-hole tail (lowest `late_integral`) is loser-enriched AND net-negative on 3 of 4 coins:

| coin | lowest-5% late_integral win% (base) | net_bps sum of that 5% | separates? |
|---|---|---|---|
| SOL | 55% (62) | **-26** | yes, net-negative |
| BTC | 61% (69) | **-65** | yes, net-negative |
| XRP | 43% (52) | **-142** | yes, strongest |
| ETH | 56% (54) | +48 | NO — not loser-enriched on ETH |

Representation note (Greg): the **cumulative/integrated** arc separates the deep-hole loser better than the
raw arc-level features on the long cells (it is exactly what aggregates "how long/deep below zero"). The
normalized-time shape fingerprint (q25/q50/q75, conv_n, t_infl) does NOT separate better than the integrated
form — hockey-ness per se is not the discriminator; time-and-depth-in-the-hole is.

---

## (c) + (d) The three gate candidates, run through the LIVE path

`gate3.py` (complete leg set from the live `run_kraken_cell`, ungated SOL $/hr=11.258 = the known baseline;
CAP=$5000). Decision is duration-agnostic at entry. Anchors/thresholds fit in-sample on labels (matches the
baseline gate's convention).

| coin | UNGATED $/hr | (A) ENERGY $/hr | (B) best EQUATION $/hr | which wins |
|---|---|---|---|---|
| SOL | 11.258 (win 61.7%) | 10.079 (win 63.6%) | **11.432** — `late_integral` skip 5% (win 62.0%) | **B (equation)** |
| BTC | 2.506 | **6.081** | 4.973 — `t_last_neg` skip 30% | A (energy) |
| ETH | 5.471 | 6.396 | 6.504 — `b_blade` skip 10% (≈ energy) | A≈B |
| XRP | 2.469 | **5.177** | 5.043 — `t_last_neg` skip 30% | A (energy) |

Read-out:
- **The "energy gate hurts" problem is SOL-SPECIFIC.** On BTC/ETH/XRP the energy gate roughly doubles $/hr
  (it skips genuinely expensive loser cells). On SOL it cuts $/hr 11.26→10.08 because SOL winner/loser energy
  levels overlap so it over-skips winners (WIN-skip 376/939).
- **On SOL, the equation REPLACES energy.** Skipping only the deepest-hole 5% by `late_integral` gives
  $/hr **11.43 > ungated 11.26 > energy 10.08**, lifts win% to 62.0, and drags only 42 winners (vs energy's
  376) while catching 13 short-losers + 21 long-losers. It recovers exactly what energy wrongly skipped.
- **The STACK (C) = energy AND equation is NOT needed** — it never beats the better of A/B on any coin.

### Concrete fine-tune recommendation (per cell x category)
1. **BTC / ETH / XRP: keep the existing 4-anchor energy gate.** It is strongly $/hr-positive there; do not
   replace it. (ETH may optionally add a tiny `b_blade`/`net_area_ratio` deepest-hole skip — neutral-to-slightly
   positive, ~ties energy.)
2. **SOL: replace the energy-anchor skip with a light "deep-hole" cumulative skip.**
   Rule: `late_integral = Σ_t (arc(t) · w(t))·0.1` over the pre-onset limb, `w` ramping 0→1 to onset; **skip a
   forming trade only if its `late_integral` is in SOL's lowest ~5%** (SOL p5 ≈ **-16.3**; equivalently
   `net_area_ratio <= -0.97`). This is the single cleanest stand-alone equation discriminator and it turns
   SOL's gate from $/hr-negative to $/hr-positive. Re-fit the p5 threshold per coin (universal shape, coin
   number): BTC p5≈-18.1, ETH -17.2, XRP -17.5.
3. Do NOT expect a large win — even the best equation skip is a modest, in-sample, ~1-2% $/hr gain on SOL. It
   is a fine-tune, not a step change. There is no clean non-overlap to exploit for more.

### Honest non-results (reported as carefully as the wins)
- The "winners hockey / losers linear" hypothesis is FALSE: both are convex hockey sticks; linear-fit R² does
  not separate winner from loser.
- Per-trade energy (`peak`) does NOT separate winner from loser within a category — confirming the premise.
- No equation feature gives clean non-overlap on ANY coin; the equation cannot fully replace energy as Greg
  hoped, only out-perform it on SOL where energy is actively harmful.
- The natural-extent gate $/hr numbers in `gate_final.py` are on a ~half-size leg SUBSET (the prior-leg-close
  bounding drops back-to-back legs), so they are NOT comparable to the complete-set baseline — natural-extent
  is used here only for separation/extent characterization; all gate money numbers come from the complete set.

### Forward note for the EXIT read
The exit/decay equation (same hockey curve, post-onset) WILL need the full post tail to each leg's actual
`close_idx` (variable length), not the fixed +60s in `quad_means.npz`, and the same natural-extent /
normalized-time treatment. The +60s clip truncates long-leg exhaustion tails and must be replaced by
close-aligned extraction there.
