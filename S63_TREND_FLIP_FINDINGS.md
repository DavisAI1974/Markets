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
