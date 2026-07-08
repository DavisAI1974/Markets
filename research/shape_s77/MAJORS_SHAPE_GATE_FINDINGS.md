# S77 — MAJORS SHAPE-FOLLOW ENTRY GATE (BTC / ETH / XRP / DOGE) — FINDINGS

**Question (Greg / S76 plan):** point the S75 whole-curve shape-match gate at the MAJORS (S75 built it on SOL —
the wrong coin, and SOL has no direction so it capped ~62%). Rebuild the 4 archetype shapes **per major**, fire on
WINNER shapes / skip LOSER shapes, ride-to-reversal (non-patient) exit, and measure whether shape-following **lifts
$/hr vs ungated** — walk-forward, 0% maker.

**Verdict: NO. The shape-follow gate does not lift the majors' $/hr.** It reproduces SOL's wall on BTC/ETH/XRP/DOGE.
No coin × wiggle setting clears random-skip noise (all |z| ≲ 1.6 OOS). The reason is now *measured on the majors*:
win/lose is **direction**, and direction is not written in the pre-fire shape.

Driver: `research/shape_s77/majors_shape_gate.py` (results JSON alongside). Reuses the S75 machinery verbatim —
executor entries (`run_kraken_cell`, firing Greg-locked), the leg_imbalance causal birth→onset ignition arc, the
`fit_shapes` nearest-archetype whole-curve gate, and the `book_swing_kraken` ride-to-reversal exit. **No
normalize/average/smooth** on the per-leg curve (raw amplitude is the edge); shape/RATIO only; 4 buckets kept
separate; leakage-free (curve uses only data ≤ onset; archetypes built on first 60%, tested on held-out 40%).

## Setup
- **Entry universe:** the executor's flip legs (forming trades) — firing untouched. The gate only FILTERS.
- **Pre-fire curve:** with-side TRADE imbalance ratio ∈ [-1,1], causal birth→onset (ignition-anchored), native
  amplitude, resampled to 100 pts. Exactly the S74 `leg_imbalance.py` construction.
- **Archetypes:** per-cell MEAN pre-fire arc, 4 distinct buckets = duration (executor-leg median split) × outcome
  (ride net>0). Built on TRAIN 60% only.
- **Gate:** nearest-archetype L2 over the whole raw curve → fire if nearest ∈ {short-win, long-win}. Two variants:
  `wiggle=0` (strict nearest, `fit_shapes` style) and `wiggle=0.15` (a winner within 15% of the nearest loser still
  fires, `sol_gate` style).
- **Exit:** wide ride-to-reversal — ride the favorable mid excursion, exit when it retraces `trail=30bp` from its
  best or at `maxhold=600s`. NON-patient (majors, per Greg). Reported at 0% maker (headline) and taker.

## Result (walk-forward OOS, held-out last 40%, 0% maker)

| coin | OOS n / h | ungated win% / $hr | **gate (nearest)** win% / $hr / fire% | gate (wiggle .15) | random-skip z (nearest) |
|---|---|---|---|---|---|
| **BTC** | 354 / 16.8 | 50.6 / **+3.98** | 51.3 / +4.58 / 89% | 50.6 / +3.26 | **+0.87** (ns) |
| **ETH** | 250 / 27.0 | 47.6 / **+7.44** | 47.2 / +1.33 / **21%** | 45.9 / +7.35 | **−0.04** (ns) |
| **XRP** | 254 / 29.3 | 50.4 / **−1.26** | 48.3 / −3.75 / 46% | 50.4 / −1.03 | **−1.56** (ns) |
| **DOGE** | 94 / 24.7 | 37.2 / **−2.41** | 34.4 / −3.28 / 34% | 41.7 / −0.41 | **−1.15** (ns) |

*(ns = not significant vs skipping the same number of legs at random, 200 draws.)*

- **No lift anywhere.** Best nominal case is BTC-nearest (+0.6 $/hr), which is z=+0.87 — indistinguishable from
  random skipping. The strict-nearest gate on ETH **over-skips catastrophically** (fires 21%, drops fat winners
  with the losers → +7.44 collapses to +1.33), the classic S75 failure mode. XRP/DOGE it actively hurts.
- **The `wiggle=0.15` variant fires ~everything (97–98%) and just reproduces ungated** — it doesn't select, it
  passes through. So the gate is either anti-selective (nearest) or a no-op (wiggle). There is no middle setting
  that trims losers.
- **Gated win% never rises.** BTC 50.6→51.3, ETH 47.6→47.2, XRP 50.4→48.3, DOGE 37.2→34.4. This is the single
  cleanest proof: if the shape could see winners, gated win% would climb; it doesn't.
- **Fees:** every cell is deeply negative at taker (−40 to −100 $/hr). The edge exists **only at 0% maker**, and
  even there it's single-digit $/hr — matching Greg's BTC paper (dead at taker, positive at 0% maker).

## The 4 archetype shapes DID rebuild cleanly per major (the shape describes ENERGY/DURATION, not direction)
The universal ordering from the inventory holds on every major: **long-winner = highest-energy (highest onset
peak)**, short-loser = lowest/flattest.

| coin | SW peak | SL peak | LW peak | LL peak |
|---|---|---|---|---|
| BTC | +0.259 | +0.215 | **+0.380** | +0.223 |
| ETH | +0.102 | +0.227 | **+0.367** | +0.223 |
| XRP | +0.374 | +0.205 | **+0.483** | +0.462 |
| DOGE | +0.104 | +0.067 | **+0.368** | +0.236 |

So the archetypes are real and coin-universal in *shape ordering* — but they separate **duration/energy**, not
outcome. The gate's discriminating pairs (same duration, opposite outcome: SW–SL, LW–LL) have **small L2
separation** relative to the duration axis (SW–LW):

| coin | SW–SL | LW–LL | SW–LW (duration) |
|---|---|---|---|
| BTC | 0.96 | 1.21 | 1.66 |
| ETH | 0.97 | 0.98 | 1.84 |
| XRP | 0.79 | 0.56 | 0.85 |
| DOGE | 1.24 | 1.42 | 1.68 |

Winner-vs-loser shapes (at fixed duration) are less separated than short-vs-long — i.e. **a trade's outcome is not
in its entry shape.**

## Root cause — the DIRECTION wall, now measured on the majors (identical to SOL)
Reverse the side of each OOS loser (opposite trade over the same window ≈ −gross):

| coin | % of OOS losers that flip to winners | reverse-all-losers $/hr@0 (hindsight ceiling) vs ungated |
|---|---|---|
| BTC | **94%** | +69.6 vs +3.98 |
| ETH | **100%** | +68.1 vs +7.44 |
| XRP | **100%** | +63.6 vs −1.26 |
| DOGE | **98%** | +31.3 vs −2.41 |

The losers ARE winners entered backwards — 94–100% of them. A winner and its loser twin share the **same entry
shape** (that's why SW–SL / LW–LL barely separate), so no entry-shape gate can tell them apart. This is exactly the
S75 finding: **~62% / the win/lose axis is DIRECTION, and direction is un-callable from the pre-fire shape.** It is
NOT a SOL peculiarity — BTC/ETH/XRP/DOGE all show it. The enormous headroom (ceiling 60–70 $/hr) is the *direction*
lever, which the SHAPE does not carry.

## Exit sensitivity (why the ride matters little here)
The 30bp/600s ride **saturates at maxhold** on these calm 42–73h windows (mean ride-hold 498–595s ≈ the 600s cap),
so it is effectively "hold ~10 min", not a true ride-to-reversal — the trail rarely bites. Sweeping the trail
(10/15/20/30/50 bp) wanders in single-digit $/hr @0% maker and stays deeply negative at taker on every coin. No exit
width rescues a shape edge; there isn't one to rescue.

## Honest caveats
- **One window per coin** (BTC 42h, ETH 67h, XRP 73h, DOGE 61h), small OOS n (94–354 legs; DOGE especially thin).
  Don't size on any single number.
- **Low-vol windows** — the ride saturates at maxhold, so the non-patient exit didn't get a real workout. A trendier
  window could move the $/hr level, but would not change the structural result (shape ⊥ direction) unless the
  winner/loser shapes started to separate, which they don't here.
- **Firing was locked** (Greg-only) — this measures only the entry-shape FILTER, as specified.

## Takeaway for S76/S77
The whole-curve shape-follow gate is a good **energy/duration** descriptor but a **null direction filter** on the
majors, same as on SOL. To lift the majors you need the piece the shape can't provide: **DIRECTION** — the S75 book
EARLY-SIGNAL (71% BTC / 55% ETH at 60s on strong leans) is the lever, not the entry shape. Recommendation: don't
gate on shape alone; stack the book direction signal (S76 plan step 2) and use the shape/energy read only for
sizing/duration, not for the fire/skip decision.
