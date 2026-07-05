# S63 FINDINGS — the 1-HOUR TREND read is REAL, but the ENTRY flip does not clear

Branch reconciled to canonical `5c5vg9` at open (designated branch was cut from an S37-era parent
again — reset --hard). Bins re-pulled: Binance-spot 30d, all 5 coins (`/tmp/backfill`, ephemeral).
Fee frame = Coinbase; tests fee=0; FLIP = 22bp taker cross. Tools: `scripts/_s63_trend_flip.py`
(the flip + shuffle-null grader), `scripts/_s63_trend_diag.py` (the direction diagnostic).

## 1. THE DIRECTION DIAGNOSTIC — reproduces + STRENGTHENS the S62-close claim
`_s63_trend_diag.py`: for each machine leg, does `sign(mom over W)` at entry equal `sign(fwd move)`
(the winning direction)? P(trend points the winning way), by population:

| coin | ALL @1h | BIG-LOSER @1h | DEATH @1h | WINNER @1h | ALL @600s | WINNER @600s |
|---|---|---|---|---|---|---|
| sol | 0.422 | **0.692** | 0.596 | 0.390 | 0.470 | 0.653 |
| eth | 0.434 | **0.729** | 0.619 | 0.402 | 0.482 | 0.598 |
| btc | 0.445 | **0.717** | 0.653 | 0.443 | 0.478 | 0.725 |
| xrp | 0.452 | **0.713** | 0.656 | 0.425 | 0.460 | 0.627 |
| doge| 0.435 | **0.697** | 0.571 | 0.409 | 0.482 | 0.730 |

Reads (all 5 coins agree):
- **The 1h trend is a REAL direction axis conditional on being a big loser: 0.69–0.73** (handoff
  said 0.58–0.67 — even stronger on this window). Deaths 0.57–0.66.
- **The market mean-reverts at the machine's 600s scale** (ALL @1h = 0.42–0.45 < 0.5) — the
  machine's own edge. Winners @600s = 0.60–0.73 (they ride the short move) but @1h = 0.39–0.44
  (they go AGAINST the 1h trend and win by mean-reversion).
- **This is exactly why the entry flip is a SELECTION problem:** WINNERS fade the 1h trend too
  (@1h 0.40 = winner side is against the 1h trend 60% of the time). So "strong 1h fade" does NOT
  separate the big losers from the winners at entry — both fade it. The big-loser 0.69 read is
  only usable *once you already know it's a big loser*, which you can't at entry.

## 2. THE ENTRY FLIP — does NOT clear (per-cell, all sweeps)
`_s63_trend_flip.py` — signal `-side*mom(W)`, flip the top-`cut`% fades at entry, `flip pnl =
-gross - 22`. Graded per-week + a **shuffle-null floor** (permute WHICH legs are flipped, N=500):

- **SOL / BTC / XRP: fail hard.** Negative lift, shuffle z ≤ ~0.9 (inside the null), big10-flip
  low. BTC/XRP baselines are already negative; flipping makes them worse.
- **ETH / DOGE: marginal.** The shuffle z is consistently *positive* (ETH +1.7…+2.6, p 0.008–0.05)
  — i.e. the fade DOES select worse-than-random legs to flip (the direction signal is real) — but
  the absolute lift is only ~0 to +0.3 $/hr (ETH 1h/cut90 = +0.31, p=0.008, wk+ 3/5; DOGE
  1h/cut85 = +0.12, p=0.036). Winner-destruction + the 22bp cross eat the edge.
- **No knife-edge survives the band test** (README discipline): nothing is robustly positive across
  a band of (W, cut) and per-week. Best cases sit at a single corner (1h, cut90).

**Verdict:** the raw `-side*mom1h` entry flip is NOT the prize. It confirms the 1h direction read
is real (shuffle z>0 on ETH/DOGE + the diagnostic) but the entry SELECTION wall (winners fade too)
holds — consistent with the whole S62 finding that big-losers aren't separable at entry.

## 3. WHERE THE EDGE IS — mid-leg, and the 1h read is the DIRECTION confirm
The separation that entry lacks exists MID-LEG: the E300 depth classifier already earns
(`_s62_e300_3piece.py`: BTC +1.29/hr, 4/5wk) by separating death-vs-winner via realized depth.
The diagnostic says the 1h trend is the right DIRECTION for the flip once a death is identified
(0.69). So the synthesis is: **E300 depth = the death SELECTOR, 1h trend = the flip-DIRECTION
confirm.** That is the next build (Job 2/3 converging) — NOT more entry-flip tuning.

## 4. Kraken books (Greg's note) — the SEPARATE (parked) thread
All 5 `data/<coin>-kraken-book` branches live, ~18h of L2 depth each so far (SOL 630k rows,
17.6h; not yet "a couple days" — one live segment per coin, no rotation yet). Schema = ts/mid/
spread/bids/asks levels = the D6 book-imbalance input (Lean Lab `coinbase_book_l2` / OD-BOOK
`research/od_book`). Kraken is PARKED for trading (fee frame = Coinbase), so this feeds the D6 /
order-book-dynamics line, not the 1h-trend lead (which runs on Binance-spot trade bins). Keep
accruing; revisit for the OD-BOOK thread-1 T_test when it's multi-day deep.

## 5. THE SYNTHESIS — 1h trend folded into the E300 rig (`_s63_e300_trend.py`)
Depth = death SELECTOR (the workhorse), 1h trend tested two ways: as classifier FEATURES and as a
flip-DIRECTION GATE. Graded per-week; the stable metric is **Δ over baseline** (absolute $/hr
wanders window-to-window — BTC E300 = +0.13 here vs the S62 drop-in's +1.29 on a slightly different
30d window; "never tune off one window").

| coin | base | E300 (repro) | E300+feat | +feat+gate | feat Δ over E300 |
|---|---|---|---|---|---|
| eth | +2.73 | +2.65 | +2.67 | +2.74 | +0.02 |
| btc | −0.46 | −0.01 | **+0.28** | +0.29 | **+0.29** (4/5 wk +) |
| sol | +2.86 | +2.69 | **+3.32** | +3.16 | **+0.63** |
| xrp | +1.63 | +2.58 | **+2.88** | +2.61 | **+0.30** |
| doge| +1.06 | +2.02 | +1.84 | +1.82 | −0.18 |

Reads:
- **The E300 depth rig is the workhorse** — lifts btc/xrp/doge well over baseline; eth/sol already
  high, E300 ~neutral there.
- **1h trend as FEATURES adds a modest lift on btc/sol/xrp** (3/5) — the depth classifier absorbs
  the real 1h direction info (AUC barely moves, 0.73→0.74 btc, 0.756→0.762 xrp; the gain is in the
  action, not the AUC). Neutral eth, slight negative doge.
- **The explicit flip-direction GATE is redundant and slightly hurts** — a predicted death IS a
  continued adverse move, so depth already encodes the 1h direction; gating on it just flattens
  some good flips. Clean negative: don't add the gate.

**Net S63 verdict:** the 1h trend is a real direction axis (diagnostic) that (a) does NOT support a
standalone entry flip (selection wall) but (b) adds a small, honest lift as a FEATURE to the working
E300 mid-leg rig on btc/sol/xrp. Needs a 2nd-window confirm (same caveat as the base E300 rig). The
depth-based E300 rig remains the deployable earner; the 1h feature is a cheap add-on, the gate is not.

## 6. THE BUY/SELL ANSWER (Greg's correction: entry is fine, only the SIDE is wrong)
`_s63_direction.py` + `_s63_fade.py`. Reframed to the ONLY question: given the machine's (correct)
entry, was the right side BUY or SELL? Graded as a DIRECTION-AT-ENTRY decision (pnl = pred_side*fwd,
NO flip fee — the side is chosen once at entry, not a mid-position reversal).

**The sign structure (all 5 coins, `_s63_direction.py`):** the machine's own side ≈ a coin flip
(dir-acc 0.50–0.53). FOLLOWING the multi-hour trend (+sign mom) is systematically WRONG (0.43–0.49);
FADING it (−sign mom) is RIGHT (0.52–0.57). That is precisely "reading the move correctly but
trading the opposite side" — the fix is a SIGN FLIP: fade the N-hour trend.

**Fade-horizon sweep (`_s63_fade.py`, pred_side = −sign(mom W); direct $/hr, per-week, sign-shuffle null):**

| coin | machine base | machine acc | best W | acc | direct $/hr | Δbase | z_null (p) | weeks+ |
|---|---|---|---|---|---|---|---|---|
| doge | +0.28 | 0.500 | **8h** | 0.542 | **+2.72** | +2.44 | +2.06 (0.018) | **5/5** |
| sol  | +1.06 | 0.517 | **4h** | 0.563 | **+2.95** | +1.89 | +2.11 (0.018) | 4/5 |
| btc  | −0.91 | 0.511 | 6–8h | 0.55–0.56 | +1.2…+1.6 | +2.1…+2.5 | +1.5 (~0.06) | 4/5 |
| xrp  | −0.63 | 0.496 | 8h | 0.532 | +2.01 | +2.65 | +1.70 (0.046) | 3/5 (lumpy) |
| eth  | +0.90 | 0.527 | 6h | 0.535 | +1.92 | +1.02 | +1.60 (0.058) | 2/5 (fragile) |

Reads:
- **YES — the side is readable, and it's a sign flip: FADE the multi-hour trend, don't follow it.**
  Fade beats the machine's direction accuracy by **+3 to +5 points** on every coin (consistent, not
  $/hr noise).
- **Best horizon is PER-COIN** (per-cell deploy rule): DOGE 8h and SOL 4h CLEAR the null (p=0.018)
  at 4–5/5 weeks = deploy candidates. BTC 6–8h rescues a NEGATIVE machine baseline (−0.91→+1.6)
  across a clean band, but z~1.5 is marginal. XRP/ETH weak/fragile (one horizon, lumpy weeks).
- **Deeper horizons (4–8h) beat 1–2h** for the whole-population side decision — the 1h that the
  handoff flagged is the big-loser *conditional* read; for choosing every leg's side, fading a
  4–8h trend is stronger.
- **Fee frame is decisive:** positive only in the direct (decide-at-entry) frame; the 22bp mid-
  position flip fee erases it. Greg's "decide buy/sell at entry" = the correct, monetizable frame.

CAVEATS (load-bearing): (1) ONE 30d window — the per-coin best-horizon MUST get a 2nd-window
confirm before sizing ("never tune off one window"). (2) The sign-shuffle null only proves "beat
random side"; a stronger circular-shift (tautology) null is owed — a fade rule flatters a range-
bound month. (3) Mechanism = longer-horizon mean-reversion; it lifts average accuracy but may not
specifically fix the trend-continuation fat tail. Next: 2nd-window confirm + circular-shift null on
the DOGE-8h / SOL-4h / BTC-6-8h deploy candidates.

## 7. KRAKEN PIVOT (Greg): park Coinbase, kr_mk0 = 0bp maker is where the money is
Ran the fade SIDE rule and a plain causal ZIGZAG on KRAKEN'S OWN tape. BTC/ETH from realbins
(~26.7d ≈June, an independent cross-venue+cross-window check); SOL/DOGE/XRP from the REST pull
(`backfill_kraken_trades.py`, rate-limited ~1req/s, partial as of writing). Tools:
`scripts/_s63_kraken_fade.py`, `scripts/_s63_kraken_zigzag.py`.

**Key economics:** the fade rule trades the SAME legs as the machine (only the side differs) so the
fee CANCELS in the comparison — Kraken's value is the ABSOLUTE net: at kr_mk0 net==gross (positive),
vs net-negative at Coinbase taker. The zigzag is a standalone strategy where the 0bp fee is the
whole ballgame.

**Fade on Kraken (partial):** DOGE (30d) fade-6h +3.81/hr Δ+2.63 z=1.99 (p=0.028) — echoes the
Binance DOGE-8h across venue. ETH (26.7d) fade-4h +1.73 z=1.47 (marginal). SOL/XRP too thin yet.

**ZIGZAG on Kraken (causal, no look-ahead), net $/hr @ $5k:**
| coin (data) | θ band | kr_mk0 (0bp) | kr_mk2 (2bp) | taker (11bp) | per-week |
|---|---|---|---|---|---|
| btc (26.7d) | 20–50b | +1.4…+2.7 | +0.2…+0.9 | negative | small +, one −75 blowup wk at θ10 |
| eth (26.7d) | 10–30b | +2.7…+8.3 | −4.7…+0.3 | negative | +13/+4/+6/+11 (steady at θ10) |
| sol/doge/xrp | — | mixed | mostly neg | very neg | data too thin/sparse to trust yet |

Reads (honest):
- **Confirmed: at kr_mk0 (0bp) the zigzag is net-POSITIVE** on the coins with real data (BTC/ETH) —
  Kraken's tape has real short-horizon mean-reversion (a random walk would net ~0). Greg's instinct
  (no fee floor → zigzag works) holds.
- **It lives or dies on the maker fill.** At just kr_mk2 (2bp/flip) most of the edge evaporates
  (BTC θ10 +6.7→−0.8; only θ≥30 survives ~+0.7); at taker it's deeply negative. So the whole thing
  hinges on actually getting **0bp maker fills at the turns** — exactly what the Kraken BOOKS
  (accruing, ~18h) must validate. This is the load-bearing unknown.
- **θ sweet spot ≈ 20–50bp:** tighter θ (10b) has higher gross but is fee-fragile and has blowup
  weeks (BTC −75); wider θ is steadier and survives small fees.
- **DATA CAVEATS:** Kraken tape is thin — BTC/ETH 11–16% second-coverage (mid forward-filled),
  DOGE only 3% (sparse → zigzag turns detected on stale prices overstate capturable swings; DOGE/
  SOL/XRP numbers unreliable until the full 30d REST pull + a coverage filter).

**Owed before sizing:** (1) a shuffled/phase-random null on the zigzag (real mean-reversion vs
sparse-tape artifact); (2) full 30d Kraken tape for all 5 (pull in progress); (3) the maker-fill
model from the books (the decisive gate). Fee frame going forward = Kraken kr_mk0.

## 8. ZIGZAG NULL VERDICT — the edge is REAL on BTC/ETH (not a sparse-tape artifact)
`_s63_kraken_zigzag_null.py` (θ=30bp, 100 return-shuffled nulls, kr_mk0):

| coin | data | real $/hr | null μ | z | p | verdict |
|---|---|---|---|---|---|---|
| btc | 26.7d 16%cov | +2.0 | −0.1 | +3.0 | 0.010 | **REAL** |
| eth | 26.7d 11%cov | +2.7 | −0.2 | +2.6 | 0.020 | **REAL** |
| doge | 30d 3%cov | −1.0 | 0.0 | −0.8 | 0.74 | ~null (too sparse) |
| sol | 24.4d 12%cov | +1.5 | −0.2 | +1.0 | 0.18 | not significant |
| xrp | 23.2d 13%cov | −0.0 | −0.1 | +0.1 | 0.55 | ~null |

- The return-shuffle null lands at ~0 (μ ≈ −0.1) — the harness manufactures no edge — and **BTC/ETH
  beat it at z=3.0/2.6 (p≈0.01)**. So the kr_mk0 zigzag edge on the two coins with real, complete
  data is **genuine short-horizon mean-reversion**, not a forward-fill/sparse artifact.
- SOL/DOGE/XRP do NOT confirm: DOGE is 3% coverage (unusable), SOL/XRP came from the still-running
  REST pull; re-run the null on their full clean 30d tape before any verdict.

**S63 KRAKEN BOTTOM LINE:** at kr_mk0 (0bp maker) a plain causal zigzag has a REAL edge on BTC/ETH
(+2.0/+2.7 $/hr, p≈0.01), θ 20–50bp. It is entirely fee/fill-bound — dies at 2bp/flip — so the ONE
decisive remaining gate is the **maker fill** (can we rest at the turns and get filled at 0bp?),
which the accruing Kraken BOOKS answer. Coinbase parked. Next: (1) full 30d tape for SOL/XRP → re-run
null; (2) maker-fill model from the books; (3) does the fade-direction SIDE rule stack on top of the
zigzag.

## 9. FULL-TAPE RE-READ — XRP/SOL do NOT hold (thin-sample artifact); BTC/ETH zigzag + DOGE fade do
The REST pull completed to ~full 30d for SOL/XRP (BTC-tape still partial; realbins BTC/ETH are the
complete BTC/ETH windows). Re-ran the zigzag null + fade on the full tape. Result discipline — the
earlier XRP/SOL strength was a THIN-SAMPLE artifact (2.3–3d), and it dissolves on the full month:

Zigzag null (θ=30bp, kr_mk0), FULL tape:
| coin | span | real $/hr | z | p | verdict |
|---|---|---|---|---|---|
| btc | 26.7d | +2.0 | +3.0 | 0.010 | **REAL** |
| eth | 26.7d | +2.7 | +2.6 | 0.020 | **REAL** |
| sol | 30.0d | +0.4 | +0.2 | 0.39 | ~null (was +8 on 3d = artifact) |
| xrp | 30.0d | +0.4 | +0.3 | 0.38 | ~null (was +11/+16 on 2.3d = artifact) |
| doge | 30.0d 3%cov | −1.0 | −0.8 | 0.74 | ~null (unusable coverage) |

Fade (full tape): DOGE-8h +2.73 Δ+0.69 z=2.19 p=0.016 (3/5wk) — clears, cross-confirms Binance
DOGE. XRP fade-8h +1.89 z=1.55 p=0.064 — marginal, lumpy per-week (−7.6/−10.2 weeks). SOL fade thin.

**CONSOLIDATED S63 KRAKEN VERDICT (full data, per-cell deploy):**
- **ZIGZAG @ kr_mk0: real edge on BTC (+2.0, p=0.01) and ETH (+2.7, p=0.02) ONLY.** θ 20–50bp.
- **FADE-direction: real on DOGE-8h (p=0.016)** (Binance-confirmed); marginal elsewhere.
- **XRP, SOL: do NOT confirm on full data** — earlier positives were thin-sample. Do not deploy.
- The whole thing remains **fill-bound** (dies at 2bp) → maker-fill via the books is the gate.
Per the platform rule: deploy where it survives (btc/eth zigzag, doge fade), stand aside on xrp/sol.

## 10. THE REAL BYBIT MODEL ON KRAKEN — flow-lean flip detector + win/loss anatomy
Greg: run the deployed bybit zigzag (NOT the price toy) on Kraken. That model = the CAUSAL FLOW-LEAN
flip detector `odcore/flip_detector.py` (WFLIP=600, REV=0.1, ARM0 no gates); it zigzags on the taker-
flow LEAN, not price (S40: price at a turn is ~99.6% symmetric). Tools: `_s63_kraken_flipzz.py`
(S54 gate: shuffle + reversed), `_s63_kraken_winloss.py`.

**Gate (kr_mk0, 0bp, pure structure — Bybit's big $ was the MM3 rebate volume paycheck, absent here):**
| coin | net $/hr | z vs shuffle | reversed | gate |
|---|---|---|---|---|
| eth | +4.86 | +4.0 (p=0.01) | −4.86 | **PASS** |
| btc | +3.29..+4.45 | +3.0 (p=0.01) | −3.29 | **PASS** |
| doge | +2.12 | +1.5 (p=0.07) | −2.12 | marginal (3% cov) |
| xrp | +0.96 | +0.7 | −0.96 | not sig |
| sol | −2.33 | −1.6 | +2.33 | FAIL (anti-predictive) |

So the bybit flow-lean model DOES port to Kraken spot on BTC/ETH (real structure, reversed loses),
NOT on SOL (anti-predictive — its edge on bybit was likely perp-microstructure + the rebate). Both
the flow-lean detector AND the price zigzag independently flag BTC/ETH as the real Kraken cells.

**WIN/LOSS anatomy (kr_mk0):** win% 41–47% (BELOW 50 on every coin) but avg WIN > avg LOSS
(W/L 1.14–1.24). So:
- **NOT hemorrhaging on loss size** — losses are already SMALLER than wins everywhere; loss control fine.
- **The lever is HIT RATE + WIN SIZE.** Net is a thin residual between ~+$44/hr wins and −$40/hr losses.
  SOL loses only because 41% hit rate can't clear its 1.18 win-size edge.
- **Razor-thin fee headroom (~0.5 bp/swing on ETH/BTC)** at ~17.5 swings/hr → mandates a true 0bp
  maker fill; a 1bp fee is fatal (kr_mk2 nets −13..−20). Quantifies the fill dependency.
- **"Push wins up" lever = entry TIMING:** entries lag the true turn by 3.9–6.7 bp (the `lag`).
  `retime_flips` (S47 early-arm price-reversal) enters nearer the extreme → adds to every win,
  shrinks every loss, widens headroom. Next test.

## 11. PUSH WINS UP — early-arm entry timing (retime_flips) roughly DOUBLES BTC/ETH
`_s63_kraken_retime.py`: keep the flow lean as FILTER, fire entry at the first fast PRICE reversal
(eps bp from the regime extreme) instead of at the late lean-confirm. Kraken kr_mk0:

| coin | base net $/h | best retime | win% | W/L | BE fee base→retime |
|---|---|---|---|---|---|
| eth | +4.86 | +9.50 (eps10) | 47.6 | 1.18→1.31 | 0.54 → 1.06 bp |
| btc | +4.22 | +8.57 (eps5) | 46→49 | 1.25→1.28 | 0.49 → 0.99 bp |
| xrp | +0.96 | +2.87 (eps10) | 45.4 | 1.15→1.24 | 0.11 → 0.33 bp |
| doge| +2.12 | ~+2.2 | flat | — | flat (3% cov) |
| sol | −2.33 | anti-predictive (timing can't fix wrong direction) | | | |

- **Early-arm ~DOUBLES net AND fee headroom on BTC/ETH** — pure win-SIZE lever (win% barely moves):
  bigger avg win, smaller avg loss, W/L up. Per-cell sweet spot (BTC eps5, ETH eps10).
- **BE fee headroom ~1.0 bp/swing** now — BTC/ETH no longer need a LITERAL 0bp fill; they absorb
  ~1bp of maker fee/slippage and stay positive. Materially eases the fill dependency (still the gate).
- SOL stays anti-predictive (timing can't fix a wrong-direction filter); DOGE flat (sparse tape).

**S63 KRAKEN SUMMARY (deployable read, per-cell):** the deployed flow-lean flip detector ports to
Kraken spot on BTC/ETH (S54 gate PASS, z 3-4, reversed loses), and early-arm timing pushes them to
~+8.5-9.5 $/hr @ $5k with ~1 bp/swing fee headroom at kr_mk0. NOT on SOL (anti-predictive) or
XRP/DOGE (thin/marginal). Remaining gate = real maker fills from the Kraken books.

## 12. FLIP-OR-BAIL loss management — a clean NEGATIVE (ride the zigzag instead)
`_s63_kraken_flipbail.py`: at -arm underwater, FLIP if a multi-hour trend is against us (mom_W),
else BAIL; retime entries; honest Kraken taker on the managed legs (flip 22bp, bail 11bp). vs the
ride-all (retime, maker-only) baseline:
| coin | ride-all | best managed | 0-fee ceiling |
|---|---|---|---|
| eth | +9.50 | +3.60 | +8.7 |
| btc | +8.64 | +5.60 | +9.2 |
| sol rev | −0.68 | −14 (≈1900 flips) | ~0 |

- **Even at 0 fee, flip/bail does NOT beat ride-all.** The detector is already a zigzag; its own
  next-flow-turn exit BEATS a fixed-depth stop because most −arm touches are DIPS THAT RECOVER above
  the stop by the next turn — bail/flip clips them.
- **Honest taker fees on the managed legs make it badly negative** (intervening = a taker cross the
  maker ride avoids; SOL churns to ruin).
- **The 10-loser "bail saves −1465bp" was a SELECTION ILLUSION** — only the 10 biggest, at 0 fee.
  Across ALL trades, dips-that-recover vastly outnumber true trend-runovers. The trend gate fired
  269–679×, far more than the few real runovers ("momentum against you at −arm" is trivially common
  when you're underwater) → we CANNOT isolate the rare runover at the arm point (winners-invisible wall).
- **CONCLUSION: drop mechanical loss-management.** Best exit = the plain early-arm zigzag riding each
  swing to the next flow-turn (+9.50 ETH / +8.64 BTC at kr_mk0). The surviving edge is ENTRY TIMING +
  the kr_mk0 MAKER venue → the decisive gate is the maker-fill model (can we get the 0bp fills the
  ride depends on).

## 13. JOB 2 — the DIPOLE/TREND agent as a buy/sell signal: ~CHANCE, does NOT flip big losers
`_s63_dipole_agent.py`: S36 divergence + dipole (imb_level/aligned_flow/exhausting/ent_dipole/mi_flow
at 1h) + multi-horizon momentum -> per-week-OOS direction classifier, on the full Kraken tape.

| coin | agent dir-acc | AUC | big-loser flip % | agent $/hr |
|---|---|---|---|---|
| eth | 0.514 | 0.514 | 41% | +0.05 |
| btc | 0.504 | 0.491 | 41% | −1.16 |
| sol | 0.531 | 0.510 | 53% | −0.07 |
| xrp | 0.500 | 0.488 | 53% | +0.12 |
| doge | 0.535 | 0.499 | 46% | −1.25 |

- Direction accuracy 0.50–0.53 (chance); big-loser flip rate 41–53% (coin flip); $/hr ~0.
- **The dipole/trend agent does NOT turn big losers into winners at entry.** The 0.69 big-loser read
  from §1 was POST-HOC survivorship (conditional on already being a big loser); EX-ANTE the direction
  is unpredictable — you can't select the big losers at entry to apply it.
- **Entry-direction is now closed 4 ways** (S62 coeff, S62 momentum, S63 fade, S63 dipole agent).
- README on trending = a caution (lucky trends fool the naive baseline; trust the shuffle null) +
  the office rule (grade as precursor/confirmer/timing). Not a trend recipe.

**GAMEPLAN LOCK:** stop hunting entry signals. Deployable = ride the early-arm zigzag per-cell
(BTC/ETH forward eps5/10, SOL reversed) + a WIDE bail (−50..−80) for tail-cap + kr_mk0 maker fills.
The only remaining thing that changes the answer is the MAKER-FILL MODEL (do we get the 0bp fills).

## 14. WHEN does the agent know direction? — NEVER (direction unpredictable at every time)
`_s63_kraken_direction_timing.py` (Greg: "it doesn't have to be at 0"): predict the REMAINING move's
direction at t = 0/60/120/300/600s into each leg, per-week OOS, Kraken tape.

| coin | t=0 | t=60 | t=120 | t=300 | t=600 |
|---|---|---|---|---|---|
| eth | 0.518 | 0.518 | 0.513 | 0.505 | 0.504 |
| btc | 0.493 | 0.522 | 0.494 | 0.504 | 0.507 |
| sol | 0.499 | 0.505 | 0.499 | 0.513 | 0.456 |
big-loser side-known% bounces 40–53% (coin flip) at every t.

- **Direction is flat ~0.50 at EVERY time** — not hidden-at-entry-then-revealed; unpredictable the whole
  way through.
- **Reconciles E300:** E300 DEPTH predicts DEATH (magnitude/outcome, AUC 0.69 — winners don't go deep),
  but DIRECTION of the next move is ~chance always. A deep loser is ~as likely to keep falling as bounce
  (the ~40% recover from §11). Depth ≠ direction. This is WHY flip/bail can't win: even knowing a trade
  is risky (deep), the next-move direction is a coin flip.
- **DIRECTION is the fundamentally unpredictable axis** — at entry AND mid-leg, across every signal
  (momentum/coeff/dipole/E300-timed).

**FINAL S63 GAMEPLAN:** stop all direction/entry-signal hunting. Deployable = harvest the mean-reversion
by RIDING the per-cell early-arm zigzag (BTC/ETH forward, SOL reversed) + WIDE bail (−50..−80) for tail
cap. The only remaining lever that changes the answer is the MAKER-FILL model (do we get the 0bp fills).

## 15. FIRE ONLY AT BIG DEPTH (Greg, correct) — deep bail = free tail-control
`_s63_kraken_deepstop.py`. Greg: the biggest losers drop big & keep going; at big depth it's a dead
loss — fire only at BIG negative depth, not all depths. Conditional outcome of trades reaching -D:
| depth | ETH cont%/WIN% | ETH bail | BTC cont%/WIN% | BTC bail | (ride: ETH+9.50 BTC+8.64) |
|---|---|---|---|---|---|
| -40 | 57/13% | +7.15 | 56/6% | +7.73 | |
| -60 | 60/5% | +8.88 | 46/1% | +8.30 | |
| -80 | 58/2% | +9.16 | 62/0% | **+8.74** | |
| -100 | 52/0% | +9.36 | 69/0% | +8.67 | |
| -120 | 58/0% | +9.50 | 78/0% | +8.69 | |

- **Greg RIGHT: WIN% (recover to PROFIT) -> ~0% by -80** on both coins → a DEEP bail clips essentially
  NO winners. The earlier "bail clips recoveries" was a SHALLOW-stop (-15) artifact; does NOT apply at
  big depth. Firing ONLY at big depth is the correct design.
- Net ~neutral-to-marginal (deep events RARE — 55 hit -80/ETH in 30d; ~40% of -80s recover to a
  smaller LOSS so not pure save). ETH -100 +9.36≈ride; **BTC -80 +8.74 > ride +8.64.**
- **FLIP ≈ BAIL at deep** (cont% only ~58%, doesn't pay the 22bp flip over the 11bp bail) → prefer BAIL.
- SOL churns → negative (no deep bail for SOL).
- **CORRECTION to §12/§14:** depth DOES carry a usable signal at BIG depth — not fine direction, but
  "this is a dead loss, won't recover to a win" (WIN%~0). Deep bail earns its place as ~free TAIL-CONTROL.

**DEPLOY UPDATE (per-cell):** add a deep bail — BTC −80, ETH −100 — as free tail-cap on top of the
ride. SOL none. Still gated by maker fills for the ride entries; the bail is an honest taker exit.

## 16. "reset + fire short to catch the rest of the slide" (Greg) — tested, DON'T (slide is spent)
`_s63_kraken_bailshort.py`: after a deep bail, reset and fire a short — blind, or ONLY when the flow
lean confirms the down-continuation ("fire correctly"). vs bail-flat:
| ETH depth | flat | blind short | conf short | conf# | conf WIN% |
|---|---|---|---|---|---|
| -60 | +8.88 | +8.26 | +8.50 | 75 | 19% |
| -80 | +9.16 | +8.82 | +8.90 | 42 | 19% |
| -100 | +9.36 | +9.21 | +9.25 | 21 | 19% |
(BTC/SOL same shape: flat >= conf >= blind.)

- **conf WIN% ≈ 19%** — even a flow-CONFIRMED short at −80 wins only ~1 in 5. There's little slide left:
  by the time a move is deep enough to confirm, it's near EXHAUSTION — entering short then catches the
  BOUNCE, not more downslide (the same mean-reversion that makes riding profitable, against us here).
- **bail-flat > confirmed-short > blind-flip** on all coins → at big depth, FLATTEN. Don't chase the slide.
- Settles the deep-loss playbook: deep = dead loss (WIN%~0, §15) → flatten for a free tail-cap; do NOT
  flip or re-short (slide spent, §16). Direction/continuation stays unpredictable-to-adverse everywhere.

## 17. MAKER-FILL GATE (real Kraken L2 book) + the cover_grace squeeze
`_s63_kraken_makerfill.py` / `_makerfill_losers.py` / `_covergrace.py` on data/*-kraken-book (~18-23h).
Honest queue fill (must trade through the displayed best-level size) vs ideal front-fill:

Maker gate (grace=0): fill ~38-42%, taker-close 55-67%, honest net -13..-19 $/hr (ideal -2..+3.7).
Post-fill win/loss: win% collapses 47%(paper)->23-33%; 64-77% of ALL losses are FORCED-TAKER closes
-> the leak is the FILL, not the signal.

cover_grace squeeze (rest the cover past the turn, S48) — honest vs IDEAL on the SAME window (the true
fill cost):
| coin | ideal | honest G=0 | honest G=600 | taker% 0->600 | fill cost (G=600 vs ideal) |
|---|---|---|---|---|---|
| eth | -2.05 | -12.87 | -2.97 | 55%->12% | ~-0.9/hr |
| btc | -1.01 | -14.60 | -6.90 | 57%->37% | ~-5.9/hr |
| sol*| +3.71 | -19.19 | -8.30 | 67%->30% | ~-12/hr |

Reads (per-cell):
- **cover_grace nearly CLOSES the fill gap on ETH** (taker 55%->12%, cost ~0.9/hr vs ideal) → ETH's
  maker fill essentially WORKS. BTC/SOL still bleed on fills even with grace (BTC 0.01bp spread + deep
  book; SOL worst).
- **The book window is LOW-EDGE** — ideal (perfect-fill) net already NEGATIVE on eth/btc (-2/-1), so the
  negative honest numbers are mostly the WINDOW, not the fill. This ~1-day book is NOT the +8-9/hr tape
  regime; viability can't be graded on it.
- **Implication:** on a NORMAL-edge window, ETH honest ≈ tape-edge(+8) − fill(~1) ≈ +7/hr; BTC/SOL fills
  too lossy as-is. Blocker is DATA (multi-day book on a normal-edge window), not method. Collectors running.

**S63 CLOSE:** direction unpredictable everywhere (rides the mean-reversion); deep bail = free tail-cap;
maker fill = viable on ETH with cover_grace (~1/hr cost), lossy on BTC/SOL; grade for real once multi-day
Kraken book accrues on a normal-edge window.

## 18. PUSH THE WINNERS UP — already well-captured; no trail helps
`_s63_kraken_winners.py` (30d tape): winners give back ~30% of peak but a mechanical peak-trail TP can't
harvest it.
| coin | winners | peak | exit | giveback | %peak captured | best trail vs ride |
|---|---|---|---|---|---|---|
| eth | 6159 | +16.3 | +11.1 | +5.2 | 68% | −1.37 (worse) |
| btc | 6174 | +12.1 | +8.3 | +3.7 | 69% | −0.46 (worse) |
| sol*| 6544 | +14.3 | +11.8 | +2.5 | 83% | −2.36 (worse) |

- Winners already capture 68–83% of peak; the ~2.5–5.2bp giveback is real but EVERY peak-trail TP nets
  BELOW ride-all (exits winners early on noisy retraces + taker cross) — same wall as the stop.
- **Symmetric conclusion: the flow-turn ENTRY (early-arm) and EXIT are both near-optimal.** Mechanical
  overlays (stop / take-profit / flip) all fight the mean-reversion + pay taker → hurt. The only lever
  that pushed winners up is the early-arm ENTRY (already deployed).

**S63 FULLY CLOSED (both sides):** ride the per-cell early-arm flow-lean zigzag (harvest the mean-
reversion), deep bail for a free tail-cap, cover_grace for the maker fill (ETH viable ~1/hr, BTC/SOL
lossy). No entry/mid-leg direction edge; no profitable stop or take-profit overlay. Remaining gate =
multi-day Kraken book on a normal-edge window to grade ETH fill-viability for real.

## 19. 10 SMALLEST winners — the fill-fragile churn tail (points to a swing floor)
`_s63_kraken_smallwinners.py` (30d tape). Winner-size distribution is a power law:
| bucket bp | ETH #/$ | BTC #/$ | SOL #/$ |
|---|---|---|---|
| 0-2 | 19%/2% | 23%/2% | 11%/1% |
| 2-5 | 23%/7% | 25%/10% | 20%/6% |
| 5-10 | 22%/15% | 24%/21% | 26%/17% |
| 10-20 | 19%/25% | 18%/30% | 31%/34% |
| 20+ | 16%/52% | 10%/37% | 13%/42% |

- ~40-48% of winners are TINY (<5bp) contributing only ~7-12% of winner $; top 10-16% carry ~40-52%.
- **These tiny winners flip to LOSERS under real fills** (a 3bp winner forced to a taker exit at -5bp = a
  -2bp loss) — a big part of why the fill-realistic win% collapsed 47%->29% (§17). They are fill-fragile
  churn, each costing a full round-trip fill for ~nothing.
- **SQUEEZE = a SWING FLOOR** (coarser detector REV / min-swing gate): skip the tiny turns → give up ~10%
  of winner $ but cut ~45% of trades → far fewer fills needed, each swing well above the fee/fill floor.
  Should help the FILL-realistic net most (the S36b fee-floor logic). NEXT: sweep REV / swing floor on
  the maker-fill model.

## 20. SWING FLOOR (coarser REV) + "exiting too early?" — the fill-vs-edge knob; exits are well-timed
`_s63_kraken_swingfloor.py`.
PART A (tape, 0bp): coarser REV HURTS — fewer trades, bigger swings, lower net (ETH 0.10 +9.50 -> 0.30
+5.15). At 0bp the tiny trades are pure profit, so cutting them loses edge.
PART B (real book, honest maker fill, cover_grace=300): coarser REV HELPS the fill-realistic net —
| coin | REV0.10 -> 0.30 | fill% | honest $/hr |
| eth  | | 31%->63% | -7.62 -> -3.17 |
| btc  | | 31%->49% | -11.48 -> -6.40 |
| sol* | | 28%->60% | -9.43 -> -2.57 |
Bigger swings = far better maker fills + less taker bleed. So REV is a FILL-vs-EDGE knob: coarser
(~0.2-0.3) for real-fill deployment, fine as-is at 0bp. (Still negative on this LOW-edge book window.)
PART C (exiting too early?): NO. Post-exit 120s favorable move is NEGATIVE on all coins (ETH -0.62,
BTC -0.58, SOL -0.03; only 46-47% kept going) -> price REVERTS after the flow-turn exit, the exit is
well-timed (flip right as the move reverses = the next leg's mean-reversion win). Small winners peak
~5-6bp mid-leg, exit ~2-3bp (gave back ~half WITHIN the leg, not harvestable per §18; peaks are small =
genuinely small moves). Nothing more to squeeze from small winners via exit timing; the only lever is
NOT taking them (the swing floor), a fill-side win.
