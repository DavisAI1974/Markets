# NYMEX ENERGY PRODUCT SURVEY — fit-ranking + test plan for the sub-second-reversal + dipole system (S91)

**Deliverable:** a RANKED FIT ANALYSIS + TEST PLAN. Not executed backtests — data testing is BLOCKED
(the raw MBP-10 year corpus is being re-pulled to S3, S90). This is the product/cell/gate plan to run
the moment the tape is back. Per-cell always, distributions never pooled means, net-of-fee at maker AND
taker, leakage-gated. External specs cited inline; all figures are point-in-time (mid-2026) and should be
re-verified against the live CME contract-spec / volume pages before sizing.

---

## 0. What we are fitting products TO (verified against CLAUDE.md + S85/S86/S90)

The edge (S36/S37 crypto → S90 NG canary): a **native-tick / ms-resolution PRICE-REVERSAL timing signal**
(enter within a few bps/ticks of the true turn) **STACKED** with the information-dipole **DIVERGENCE**
(taker flow opposes price → reversal, `odcore/info_dipole.py` `signed_flow_features`/`divergence`) +
**EXHAUSTION** (10-level book imbalance collapsing toward 0.5 = the leader is spent — the *robust half* of
the S36 finding, and the one that showed the only right-signed pulse in the S90 NG canary). Direction from
the `(H_a−H_b)` order-flow imbalance; the S19 raw cross-cov lead-lag (`odcore/leadlag.py`) is the
cross-venue/cross-contract companion.

The audience is **latency / microstructure (big + HFT)**, hunting a ms-to-µs edge. That flips the Kalshi
capacity constraint on its head:

| Kalshi weather books (thin) | NYMEX futures (this survey) |
|---|---|
| tiny size, fee-bound, few lines/day | HIGH volume, DEEP 10-level book, continuous 2-sided |
| edge shows in aggregate of many small bets | edge = ms-resolution turn timing, many turns/day |
| fee is the binding constraint | **tick-granularity + book depth** are the binding constraints; fee is secondary but still gated |

So the ideal product is: **highest continuous 2-sided volume, deepest resting 10-level book, finest usable
tick relative to volatility, lowest fee-per-tick, and a raw MBP-10 tape on GLBX.MDP3.** We already OWN the
CL + NG MBP-10 tape (nanosecond `ts_event`/`ts_recv`, every message, all 10 levels — S86/S88/S90). Any
other product requires a fresh Databento GLBX.MDP3 pull.

---

## 1. Product catalog survey (CME Group GLBX.MDP3 energy complex)

All figures point-in-time mid-2026; volumes are order-of-magnitude ADV (contracts/day, futures only).
**Every product below is on GLBX.MDP3 and therefore a raw MBP-10 (10-level, nanosecond) tape EXISTS** —
the only question is whether we've pulled it (we have CL+NG; everything else is a new pull).

| Product | Sym | Size | Tick | Tick $ | Notional* | ~ADV (fut) | ~OI | Fee/side† | GLBX MBP-10 | On our tape? |
|---|---|---|---|---|---|---|---|---|---|---|
| WTI Light Sweet Crude | **CL** | 1,000 bbl | $0.01 | **$10** | ~$67k | **>1.0M** | ~4M | ~$1.50 | yes | **YES** |
| Henry Hub Natural Gas | **NG** | 10,000 MMBtu | $0.001 | **$10** | ~$34k | **~400–500k** | ~1.3–1.7M | ~$1.60 | yes | **YES** |
| NY Harbor ULSD (Heating Oil) | **HO** | 42,000 gal | $0.0001 | **$4.20** | ~$99k | ~130–180k | ~250–350k | ~$1.50 | yes | no (pull) |
| RBOB Gasoline | **RB** | 42,000 gal | $0.0001 | **$4.20** | ~$90k | ~120–160k | ~250–350k | ~$1.50 | yes | no (pull) |
| Brent Last-Day Financial | **BZ** | 1,000 bbl | $0.01 | **$10** | ~$70k | ~36k | ~36k | ~$1.50 | yes | no (pull) |
| Micro WTI Crude | MCL | 100 bbl | $0.01 | $1.00 | ~$6.7k | ~30–80k | small | ~$0.50 | yes | no (pull) |
| Micro Henry Hub NG | MNG | 1,000 MMBtu | $0.001 | $1.00 | ~$3.4k | low | small | ~$0.35 | yes | no (pull) |
| Micro ULSD / RBOB | MHO/MRB | 4,200 gal | $0.0001 | $0.42 | ~$10k | thin | small | ~$0.60 | yes | no (pull) |
| E-mini Crude | QM | 500 bbl | $0.025 | $12.50 | ~$34k | thin/declining | small | ~$1.00 | yes | no (pull) |
| E-mini Natural Gas | QG | 2,500 MMBtu | $0.005 | $12.50 | ~$8.5k | thin/declining | small | ~$0.85 | yes | no (pull) |
| CL / NG calendar spreads | CL-CL, NG-NG | native spread | $0.01 / $0.001 | $10 | — | deep (implied) | — | ~$1.50 ea leg | yes | derivable |
| Weekly / serial options | LO, ON, etc. | on 1 fut | varies | varies | — | active but quote-driven | — | ~$1.50 | yes (MBP-10 per strike) | no |

\* Notional at representative mid-2026 prices (CL ~$67, NG ~$3.40, HO ~$2.35/gal, RB ~$2.15/gal, BZ ~$70).
† Non-member all-in exchange+clearing per side (TradeStation schedule). CME energy has **symmetric
maker/taker fees — there is NO maker rebate** (see §2). Member/seat-lease pricing roughly halves these
(~$0.79–0.85/side). Add exchange market-data + reg (NFA ~$0.02) on top.

Sources: [CME WTI specs](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.html),
[CME WTI volume](https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.volume.html),
[CME Henry Hub NG specs](https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.contractSpecs.html),
[CME NY Harbor ULSD](https://www.cmegroup.com/markets/energy/refined-products/heating-oil.html),
[CME RBOB Gasoline volume](https://www.cmegroup.com/markets/energy/refined-products/rbob-gasoline.volume.html),
[CME Brent Last-Day Financial specs](https://www.cmegroup.com/markets/energy/crude-oil/brent-crude-oil-last-day.contractSpecs.html),
[CME Micro WTI specs](https://www.cmegroup.com/markets/energy/crude-oil/micro-wti-crude-oil.contractSpecs.html),
[CME Micro Henry Hub fact card](https://www.cmegroup.com/markets/energy/files/micro-henry-hub-natural-gas-fact-card.pdf),
[CME E-mini Crude specs](https://www.cmegroup.com/markets/energy/crude-oil/emini-crude-oil.contractSpecs.html),
[TradeStation exchange+clearing fees](https://www.tradestation.com/pricing/exchange-execution-and-clearing-fees/),
[CME clearing-fee schedule](https://www.cmegroup.com/company/clearing-fees.html),
[Databento GLBX.MDP3 dataset](https://databento.com/datasets/GLBX.MDP3),
[Databento MBP-10 schema](https://databento.com/docs/schemas-and-data-formats/mbp-10).

---

## 2. The fee-floor analysis (the crux — and it points two ways)

Our S36b fee-floor rule: **min tradeable swing > round-trip fee + 2× entry slippage.** For a tick-timing
edge you must read the floor in BOTH natural units, because they rank the complex differently.

**Critical structural fact:** CME energy is a central limit order book with **symmetric fees — no maker
rebate.** So "maker" here does NOT cut the fee. Maker = **rest a limit at the predicted turn → capture the
~1-tick spread instead of paying it** (these are all ~1-tick-wide markets at top of book). The maker edge is
spread capture + zero taker slippage; the fee (~$1.50/side) is paid either way. This is exactly the S36b
per-leg asymmetric-floor logic re-expressed for a rebate-free venue.

| Product | tick in **bps** | RT fee in **ticks** | RT fee in **bps** | reading |
|---|---|---|---|---|
| **NG** | **2.94** (coarsest) | 0.32 | **0.94** (most expensive) | chunky book, few price levels → cleanest discrete turn structure; but swings must clear ~0.9 bps |
| **CL** | 1.49 | 0.30 | 0.45 | balanced; deepest book → best maker-fill probability |
| **BZ** | 1.43 | 0.30 | 0.43 | CL-like economics, but see depth caveat §4 |
| **HO** | **0.43** (finest) | 0.71 | **0.30** (cheapest bps) | finest microstructure = most ms-resolution; cheapest bps fee, but flat fee = 0.71 tick so swings must be multi-tick |
| **RB** | 0.47 | 0.71 | 0.33 | HO's sibling, slightly coarser/more volatile |
| MCL | 1.49 | 1.00 | 1.49 | fee = a whole tick RT → poor floor; micro book is shallow |
| MNG | 2.94 | 0.70 | 2.06 | worst bps floor; shallow book |

**The tension, stated honestly:**
- **Tick-value axis (matters for a tick-counting maker-limit strategy):** CL / NG / BZ win — the $10 tick
  makes the fee only ~0.3 tick RT, so a 1–2-tick reversal already clears it. HO/RB/micros pay 0.7–1.0 tick RT.
- **Tick-granularity axis (matters for ms-resolution turn *detection*):** HO / RB win — a 0.43 bps tick is
  3–7× finer than CL/NG, i.e. the book has many more price levels per unit move, which is precisely the
  resolution the "enter within a few bps of the turn" edge feeds on. And HO/RB's fee in **bps** is actually
  the *lowest* of the complex.
- **Depth/volume axis (matters for capacity + maker-fill + clean flow reads):** CL ≫ NG ≫ HO ≈ RB ≫ BZ ≫ micros.

No single product maximizes all three. The ranking (§3) weights **depth/volume + data-in-hand** highest
(they gate whether the test is even runnable and whether the flow read is clean), then tick economics.

---

## 3. RANKED FIT — all surveyed products, scored on the 5 axes

Axes (from the brief): (a) tick/microstructure resolution the edge needs; (b) book depth & continuous
2-sided liquidity; (c) volume/frequency (turns/day); (d) fee floor vs expected per-turn move; (e) data
availability on our tape. Score 1–5 (5 = best fit), FIT = judgment-weighted (b,c,e weighted up).

| Rank | Product | (a) tick res | (b) depth | (c) freq | (d) fee floor | (e) data | FIT | one-line |
|---|---|---|---|---|---|---|---|---|
| **1** | **NG** | 4 | 4 | 5 | 4 (tick) / 3 (bps) | **5 own** | **★★★★★** | Fastest, most front-loaded reactor; chunky clean book; own tape; exhaustion already flickered right-signed (S90). |
| **2** | **CL** | 4 | **5** | 5 | 5 (tick) / 4 (bps) | **5 own** | **★★★★★** | Deepest, most liquid oil book on earth; capacity + maker-fill anchor; own tape; slower turns = longer holds. |
| **3** | **HO** | **5** | 3 | 3 | 3 (tick) / 5 (bps) | 2 pull | **★★★★** | Finest tick = best ms-resolution playground + cheapest bps fee; deep-enough refined-products book. Needs a pull. |
| **4** | **RB** | **5** | 3 | 3 | 3 (tick) / 5 (bps) | 2 pull | **★★★★** | HO's more-volatile sibling (driving-season vol) → more turns/day; complementary cells. Needs a pull. |
| **5** | **BZ** | 4 | 2 | 2 | 5 (tick) / 4 (bps) | 2 pull | **★★☆** | CL-like tick economics BUT thin on GLBX (~36k/day); the deep Brent book is ICE (off our tape). Marginal — see §4. |
| 6 | CL/NG calendar spreads | 3 | 4 (implied) | 3 | 4 | derive | ★★☆ | Deep + mean-reverting = natural reversal surface, but tape is implied/spreader-dominated → muddy flow read. Research aside. |
| 7 | MCL | 4 | 2 | 3 | 1 | 2 pull | ★★ | Same tape shape as CL at 1/10 size but shallow book + 1.0-tick RT fee. Sizing tool, not an edge venue. |
| 8 | QM / QG e-minis | 3 | 1 | 1 | 2 | 2 pull | ★ | Declining liquidity, thin book — fails depth/freq. Avoid. |
| 9 | MNG / MHO / MRB | 4 | 1 | 2 | 1–2 | 2 pull | ★ | Shallow micro books; worst bps floor (NG-micro 2.06 bps RT). Avoid for this edge. |
| 10 | Weekly/serial options | n/a | 2 | 2 | 2 | pull | ★ | Quote-driven, MM-dominated, discrete strikes, wide spreads — wrong microstructure for a price-reversal futures edge. Exclude. |

**Top 5 = NG, CL, HO, RB, BZ.** (BZ is the honest marginal pick; §4 explains why and names the alternative.)

---

## 4. Why BZ is #5-with-an-asterisk (and the alternative)

BZ on **NYMEX/GLBX.MDP3** is the *Brent Last-Day Financial* cash-settled contract: ~36k ADV / ~36k OI, a
thin book that fails our deep-book + continuous-2-sided requirement. The genuinely liquid Brent order book
is **ICE Brent (product B)**, which is NOT on GLBX.MDP3 — it lives on a different Databento venue
(ICE Futures Europe, `IFEU.IMPACT`). So on OUR tape, BZ is a weak fit.

**Two honest options for slot #5:**
- **Keep BZ** as a low-priority pull to *empirically confirm* the book is too thin (cheap to check; ~$0.05).
- **Better:** spend the #5 slot on **more CL/NG sub-cells** (front-month vs 2nd-month outrights; US-pit-open
  vs London-overlap time cells; EIA-day vs non-event days) — same deep tape we already own, more regime
  coverage, zero new data. If a 5th *distinct product* is required for the test matrix, **HO+RB together**
  already cover the refined-products microstructure; BZ adds little the CL tape doesn't.

Recommendation: **run the top-4 (NG, CL, HO, RB) as the real matrix; treat BZ as a $0.05 depth-confirmation
probe, not a full test.** If it surprises with depth, promote it.

---

## 5. TOP-5 TEST PLANS (per-cell, native-tick, maker AND taker gate)

**Common harness for all five** (do not re-implement per product — extend the live files, FILE DISCIPLINE):
- **Source:** raw MBP-10 S3 tape via `event_move_baseline.load_cont_day(root, day, source="s3")` +
  `normalize_mbp10_row` (S90). Work at **native message/event time (`ts_event`), NOT 1-sec bins** — the S90
  resolution lesson: 1-sec binning threw away exactly the ms-resolution the edge lives at.
- **Leakage gate FIRST** (`odcore/leakage.py`) — pre-entry context invariant to future messages. Mandatory,
  non-negotiable. No plan below runs until its cell-assignment passes the gate.
- **Exclude the daily settle window** (`SETTLE_UTC` guard) from every cell.
- **Signal stack:** (1) native-tick PRICE-REVERSAL trigger = top-of-book mid reverses after a run of N
  same-direction ticks; (2) DIPOLE FILTER = `signed_flow_features`/`divergence` on the pre-turn taker
  buy/sell flow window (flow opposing price = real turn); (3) EXHAUSTION = 10-level aligned book-imbalance
  collapsing toward 0.5 into the push (`event_move_baseline --depth` `aligned_imb_push`/`exhaustion`). The S90
  canary says exhaustion is the load-bearing factor, static imbalance is not — weight accordingly.
- **Cells (never pool):** `time-of-day-bucket × regime × volatility-bucket`, where TOD = {pre-open, US-pit-open
  9:00 ET, EIA/DOE-release window, midday, London-overlap, pre-settle}; regime = curve state from
  `forward_curve.py` (backwardation/contango) × trend-vs-range; vol = realized-vol tercile. Event-day vs
  non-event-day is its own split. Report the forward-turn-amplitude **distribution** per cell, `$/tick` and
  bps, never a pooled mean.
- **Two gates, per cell (the S36b per-leg floor):**
  - **MAKER gate** (rest a limit at the predicted turn): net = `swing_ticks×tick$ + spread_captured(≈1 tick×tick$)
    − 2×fee`, discounted by an explicit **fill-probability** (queue-position model — a maker limit at the turn
    may not fill; this is the binding risk, not the fee). Report net-of-fee AND net-of-fee×P(fill).
  - **TAKER gate**: net = `swing_ticks×tick$ − 2×fee − 2×slippage(≥0.5 tick/side)`. This is the hard floor;
    if the median cell swing doesn't clear the taker gate it only trades maker-if-filled.
- **Capacity** = min(resting size available at the turn price levels from MBP-10, a fraction of ADV). Deep book
  = you can size; thin book = capacity-capped regardless of edge.

### 5.1 NG (Henry Hub) — #1, OWN TAPE, run first
- **Why first:** fastest/most front-loaded reactor (S85: 106 bps median 60s move, peaked in 1s on 06-11);
  exhaustion showed the only right-signed pulse in the S90 canary; coarse 2.94 bps tick = a chunky, few-level
  book where discrete turns are cleanest to time. Data already on S3.
- **Cells:** EIA-storage-Thursday 14:30 UTC window (the fast reactor) vs non-Thursday daily-settle turns;
  × summer-contango vs winter-backwardation (from `forward_curve.py`, which already ran the year: NG
  summer-contango → winter-premium hump → backwardation); × vol tercile; × temp-regime tag (`nws_temp_feed`
  HDD/CDD bucket) as a conditioning axis.
- **Entry:** run of ≥K same-dir ticks into a one-sided 10-level book, dipole flow flips to *oppose* price AND
  aligned book-imbalance collapses toward 0.5 (exhaustion) → enter the reversal at native tick.
- **Gate:** fee floor 0.32 tick / 0.94 bps RT. NG swings are large in bps, so the taker gate should clear on
  the bigger turns; maker gate (rest at the turn, capture the chunky ~2.94-bps spread) is the fat-EV path —
  but NG's coarse book means fewer resting levels → model fill-prob carefully.
- **Capacity:** high (deep book, ~400–500k ADV). **Data needed: NONE — own tape.**

### 5.2 CL (WTI) — #2, OWN TAPE, run second
- **Why:** the deepest, most liquid oil book on the planet (>1M ADV, ~4M OI) = the capacity anchor + best
  maker-fill probability + cleanest continuous 2-sided flow read. S85: slower, less front-loaded (60s captures
  27%, the $2,640/17-min day) → the reversal edge here is a **longer-hold** turn, and CL's +0.52
  `aligned_imb_push`↔sustain sign (S86, opposite NG) means the exhaustion read is *inverted vs NG* — test it
  as its own cell, do not carry NG's sign over.
- **Cells:** US-pit-open vs EIA-Wednesday 14:30 UTC window vs London-overlap; × backwardation (CL ran 311/312
  days backwardated in the year — Hormuz-tight) so regime is nearly constant → lean the split on TOD × vol ×
  event; × Hormuz/geopolitical-regime tag.
- **Entry / gate:** same stack; fee floor 0.30 tick / 0.45 bps RT (the best tick floor in the complex). Fine-ish
  1.49-bps tick + deepest book = highest maker-fill probability → the maker gate is where CL's EV concentrates.
- **Capacity:** highest of all. **Data needed: NONE — own tape.**

### 5.3 HO (NY Harbor ULSD) — #3, NEEDS A PULL
- **Why:** finest tick in the complex (0.43 bps) = the most ms-resolution for the turn-timing edge, AND the
  cheapest fee in bps (0.30 bps RT). This is the product that most directly tests the "the edge lives in tick
  granularity" thesis. Refined-products book is deep enough (~150k ADV, ~300k OI) for a real test, though ~1/7
  of CL.
- **Cells:** DOE weekly petroleum-status Wednesday 10:30 ET window (HO reacts to distillate stocks) vs pit-open
  vs midday; × heating-season (winter demand) vs shoulder; × crack-spread regime (HO–CL) as a conditioning tag;
  × vol tercile.
- **Entry:** same stack, but expect **multi-tick** reversal targets — the fee is 0.71 tick RT, so a 1-tick turn
  does NOT clear the taker gate; the cell must show median swings ≳ 2 ticks (≈0.9 bps) to trade taker; maker
  (capture the fine spread, pay 0.71 tick fee) needs the swing > ~1 tick net. The fine tick means most real
  turns ARE multi-tick, so the granularity works FOR the gate here.
- **Capacity:** medium (book ~1/7 CL). **Data needed: pull HO MBP-10 for the test window(s) from GLBX.MDP3.**

### 5.4 RB (RBOB Gasoline) — #4, NEEDS A PULL
- **Why:** HO's sibling with the same fine tick (0.47 bps) but higher seasonal volatility (summer driving
  season, RVP-spec transitions) → **more turns/day** = more reversal opportunities; complements HO on the cell
  map (different demand driver, different seasonal). Same DOE-Wednesday catalyst.
- **Cells:** DOE-Wednesday window vs pit-open vs midday; × driving-season (Mar–Sep) vs off-season; ×
  spec-transition weeks (winter↔summer RVP) as a high-vol tag; × vol tercile.
- **Entry / gate:** identical to HO (0.71 tick / 0.33 bps RT floor, multi-tick targets). RB's extra vol should
  fatten the swing distribution vs HO → likely a better taker gate, slightly thinner book → tighter capacity.
- **Capacity:** medium (~130k ADV). **Data needed: pull RB MBP-10 from GLBX.MDP3.**

### 5.5 BZ (Brent Last-Day Financial) — #5, NEEDS A PULL, run as a $0.05 DEPTH PROBE only
- **Why marginal:** CL-like tick economics (0.30 tick / 0.43 bps RT) but ~36k ADV and a thin GLBX book; the
  deep Brent liquidity is on ICE (`IFEU.IMPACT`), NOT on our GLBX.MDP3 tape (§4).
- **Plan:** pull ONE representative BZ MBP-10 day, run `event_move_baseline --depth` purely to **measure resting
  10-level book depth + top-of-book continuity**. Decision gate: if median resting size at the top 3 levels is
  comparable to HO/RB → promote BZ to a full test; if it's a sparse, gappy book (expected) → **stop, do not
  pull more, redirect the slot to CL/NG sub-cells** (§4).
- **Data needed: 1 BZ MBP-10 day from GLBX.MDP3 (~$0.05).** Do not pull the year until the depth probe passes.

---

## 6. Data-pull requirements summary (what a top-5 test needs beyond CL+NG)

| Product | Own it? | Pull needed | Est. cost | Priority |
|---|---|---|---|---|
| NG | **YES** | none | — | run now |
| CL | **YES** | none | — | run now |
| HO | no | MBP-10, test windows then year | ~$0.02–0.05/window; ~$60–70/yr | high (after CL/NG pass) |
| RB | no | MBP-10, test windows then year | ~$0.02–0.05/window; ~$60–70/yr | high (with HO) |
| BZ | no | **1 day only**, depth probe | ~$0.05 | low (gate before any more) |

(Cost model from S85/S86: MBP-10 windows ran ~$0.02–0.05 each; the CL+NG full year was ~$130 total. HO/RB
year pulls should be similar per-product. Gate on `metadata.get_cost` before every pull.) All pulls use the
existing `databento_backfill.py --schema mbp-10` / `pull_year_mbp10.py --dest s3://…` machinery — zero-filter,
raw, gzipped to the bucket. **No new collector code needed; only new symbols + `metadata.get_cost` gating.**

---

## 7. Load-bearing caveats

1. **Testing is BLOCKED (S90):** the raw MBP-10 year is being re-pulled to S3. This is the ranking + plan,
   not results. Every number is provisional-until-live.
2. **CME has NO maker rebate** — the maker edge is spread-capture + zero taker-slippage, not a fee cut; the
   ~$1.50/side fee is paid on both legs. Fill-probability of a resting limit at the turn is the binding maker
   risk and MUST be modeled (queue position), not assumed.
3. **The S90 NG canary is not a green light:** static divergence did NOT transfer (lift ~0 to −0.04); only the
   EXHAUSTION factor showed a faint right-signed pulse, on ONE trending EIA-Thursday, binned to 1-sec (too
   coarse). The real test is native-tick/ms-resolution across the per-cell year. Weight exhaustion > static
   imbalance, and expect per-cell (and per-contract) sign differences (S86: NG −0.17 vs CL +0.52 — opposite).
4. **Seasonality confound:** the S85/S86 reads are Apr–Jul 2026 only (n=12/contract). No per-contract property
   generalizes across seasons until the full-year tape confirms it. `forward_curve.py` regime tags + the vol
   terciles are the anti-lock-in cell axes.
5. **Volumes/OI are point-in-time** order-of-magnitude figures from CME/Barchart; re-verify on the live CME
   volume pages before sizing. Fees are the non-member schedule; member/seat-lease ~halves them and materially
   improves every fee-floor number.
6. **BZ off-tape depth:** the liquid Brent book is ICE (`IFEU.IMPACT`), a different Databento venue not in our
   GLBX corpus. Do not assume BZ depth from NYMEX GLBX data.

---

## 8. Bottom line

Run the matrix **NG → CL → HO → RB**, with BZ demoted to a $0.05 one-day depth probe. NG and CL are the
immediate, zero-new-data tests (we own the tape) and split the microstructure cleanly: NG = fast, chunky,
front-loaded turns; CL = deep, slow, longer-hold turns with an inverted exhaustion sign. HO and RB are the
fine-tick refined-products pulls that most directly stress the "ms-granularity turn-timing" thesis and carry
the cheapest bps fee. Everything else (micros, e-minis, calendar spreads, options) fails the depth/volume or
microstructure requirement for THIS edge and is out of the top 5. Per-cell, distributions, leakage-gated,
net-of-fee at maker AND taker — always.
