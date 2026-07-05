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
