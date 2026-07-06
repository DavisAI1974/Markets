# S66 — CAPACITY build + the first finding (the fill-side is the wall) — 2026-07-06

Built `odcore/capacity.py` (the architect read's #1 missing mechanic) and ran it on the real majors Kraken tape.
Canary PASS bit-for-bit vs the proven S50/S51 `_capacity_model._leg_caps` (`scripts/_s66_canary_capacity.py`).

## What capacity.py does
Bounds a leg's realized maker fill by the REAL opposing taker $ that trades through our fixed limit:
`realized = min(desired, cap)`, `cap = Σ price-eligible opposing coin-vol over the leg · px`. Flow-bound on TAPE,
queue-honest (minus best-level size ahead) when a BOOK is present. This is the cap the allocator needs — deployable
capital = Σ per-cell caps over simultaneously-live cells, NOT the $5k slice.

## ⚠ Finding 0 — the capacity number is ASSUMPTION-SENSITIVE (pin it before trusting any $/hr)
On ETH the median per-leg cap swings **$6 → $7,593** purely by the fill-window choice:
- `FILL_W=10` default = a 100ms-BOOK param (=1s); on 1s TAPE it's a 10s window → understates ~100× (Kraken tape is
  bursty: median **$0/s**, mean $447/s).
- Deployed executor RESTS the quote the whole leg (median ~155s) → correct model = **whole-hold + price-eligible**
  (`window=None, price_eligible=True`; eligibility already excludes flow after price left the limit — the S50 concern).
This alone proves the architect's point: **no honest per-cell $/hr exists until the capacity/fill model is pinned.**

## Per-cell capacity (deployed whole-hold + price-eligible, Kraken 30d tape)
| coin | legs | med hold | median cap $ | p75 | p90 | fill% @ $5k |
|---|---|---|---|---|---|---|
| ETH | 8674 | 155s | 1,283 | 8,557 | 39,941 | 44% |
| BTC | 7670 | 151s | 3,853 | 31,006 | 150,636 | 56% |
| SOL | 10577 | 156s | 2,304 | 12,180 | 41,396 | 51% |
| XRP | 9007 | 195s | 2,252 | 12,969 | 41,472 | 51% |
| DOGE | 4242 | 469s | 227 | 2,972 | 18,945 | 30% |
Even the MAJORS are capacity-bound at $5k (fill 30–56%). Deployable per-leg is ~$1–4k on majors, ~$227 on DOGE.

## ⭐ Finding 1 (load-bearing) — WINNERS are nearly unfillable; LOSERS fill in full (adverse selection in $)
`corr(cap, net_bps) < 0` on all 5 (−0.16..−0.32). Median fill split, winners vs losers:
| coin | winner fill | loser fill | ratio | % losers |
|---|---|---|---|---|
| ETH | $15 | $5,393 | 360× | 50% |
| BTC | $128 | $16,217 | 127× | 49% |
| SOL | $104 | $7,390 | 71× | 58% |
| XRP | $103 | $9,115 | 88× | 54% |
| DOGE | $2 | $1,652 | 800× | 52% |
Mechanism (S45/S52/S56, now on Kraken): a resting bid fills when sellers keep pressing it (price falling → catching
the knife → LOSER); it barely fills when price bounces your way (WINNER runs away before you're on at size). So the
S65 front-of-line **+$6–16/hr @ $5k was fiction in SIGN, not just magnitude** — it credited winner fills that don't
happen at size. Capacity-capped, the fine-zigzag legs are dominated by loser fills.

## ⭐ Finding 2 (Greg's code-fix instinct — CORRECT) — "winners unfillable" was largely a MODELING ARTIFACT
The Finding-1 catastrophe used the OPEN-anchored window (count flow forward from open_idx). But a maker-at-the-turn
(S45) fills from the capitulation CLIMAX at the PIVOT (S40 ~2x volume as price bottoms/turns), not from flow forward
of open (which is the post-turn regime where a winner's price has already reverted away → price-ineligible → fake $0).
Anchoring the window on the PIVOT ([flip−W, flip+W], `capacity.anchor="pivot"`, new S66) fixes it:
| coin | corr(cap,net) open→pivot | winner:loser fill (pivot) | capacity-capped $/hr @$5k (pivot) |
|---|---|---|---|
| BTC | −0.32 → **−0.09** | ~2× (was 127×) | **+1.4 … +3.8** (best cell) |
| ETH | −0.16 → **−0.00** | ~2× (was 360×) | **+0.4 … +0.7** |
| SOL | −0.26 → −0.04 | ~2× | −2 … −7.6 (tape edge already weak) |
| XRP | −0.29 → −0.05 | ~2× | −2.4 … −5.3 |
| DOGE | −0.26 → −0.03 | ~1× (thin) | −0.2 … −1.3 |
CORRECTED READ: capacity is a **real but NOT catastrophic** haircut (ETH +8.4→~+0.5, BTC +7.9→~+2-3.8 @$5k), NOT a
winner-unfillable wall. WINNERS FILL at the turn. **BTC + ETH survive capacity-capped positive; SOL/XRP/DOGE do not**
on this tape (their tape edge is already weak/negative — the fine SOL/XRP legs). Robust in SIGN across W∈{15,30,60}.
The Finding-1 open-anchored numbers are SUPERSEDED for winner-fill (kept as the artifact record + the window lesson).

## Caveats (do NOT over-read the exact capped $/hr)
- The PIVOT window ±W (climax duration) is a proxy that needs BOOK calibration to pin the magnitude (tape has no
  depth; ±W symmetric double-counts pre/post-turn). SIGN (BTC/ETH+, SOL/XRP/DOGE−) is robust; magnitude is not.
- TAPE price-eligibility is a proxy for the executor's real entry-fill mechanics (definitive grade needs the BOOK +
  the executor's own open-fill accounting; we have ~30h Kraken book). The DIRECTION (winners unfillable / losers
  fill / capacity-capped ≪ front-of-line) is robust and matches S45/S52/S56 across venues.
- This does NOT by itself kill the stack; it says the deployable size and the winner-fill problem must be solved.

## What this implies for next steps (candidates, not conclusions)
1. **Size to winner-capacity, not $5k** — the deployable per-leg is the WINNER cap ($2–128 median), brutal.
2. **Bigger swings may fill better** — connect to S65 "money is only in ≥20bp swings"; test capacity vs swing size
   (do big-swing winners have real fillable capacity, unlike the churn legs?).
3. **The −2bp rebate is paid on loser fills too** — on the THIN-OK sleeve the rebate directly subsidizes the exact
   fills adverse selection forces on us; the thin sleeve's economics may survive where the majors' don't.
4. **Grade the thin-cap sleeve capacity-capped + queue-honest + per-week from the start** — never front-of-line.

Files: `odcore/capacity.py`, `scripts/_s66_canary_capacity.py`, `scripts/_s66_capacity_demo_kraken.py`.
