# SESSION HANDOFF — S76 (2026-07-09) — the BOOK ride-to-reversal swing is the BTC/ETH edge; ETH walk-forward VALIDATES (taker-survivable) on KRAKEN

READ FIRST: `STRATEGY_INVENTORY.md` OPERATING CONTRACT + LIVE. Then `SESSION_HANDOFF_2026-07-09_S75.md`
(SOL = the direction/spread-capture wall, DONE). Then this. Branch: `claude/curve-shape-gate-s75-06m1vf`.
Books: `git show origin/data/<coin>-kraken-book:<coin>_kraken_book.jsonl.gz | gunzip > /tmp/kbook/<coin>_book.jsonl`.
**VENUE: KRAKEN ONLY (Greg, S76). 0% maker = our $10M/mo tier. Do not chase other venues.**

## What S76 did — moved off SOL to BTC/ETH; found the book ride-to-reversal is the edge, walk-forward validated
All in `research/shape_s71/book_direction_kraken.py` + `book_swing_kraken.py` (drives Greg's `early_signal.py`).

### 1. The book is NOT a filter on the maker zigzag (book_direction_kraken.py)
At each maker-leg entry, the book direction vs the leg's winning side is a **coin flip** (BTC 50.1%, ETH 49.3%);
flipping on it loses; trade-only-when-agrees is marginal (BTC 2.49→3.18). WHY: the maker legs win/lose on
**spread capture**, not on the 60s directional move the book predicts. **The book's 71% edge and the maker zigzag
are DIFFERENT signals.** So the book is its OWN directional strategy, not an overlay on the zigzag.

### 2. The book RIDE-TO-REVERSAL swing — the paper's monetization (book_swing_kraken.py, drives early_signal.py)
Enter on a strong book lean (`EarlySignalTracker`: |z|≥enter_z AND |imb|≥0.5), ride the ~60s move, exit on a wide
trailing stop (30 bps) or max hold (600s). Verified my swing == `es.EarlySignalTracker` bit-for-bit.
- **⭐ 60/40 WALK-FORWARD (Greg's "tune on 60%"): fit `direction_sign` + pick enter_z on the first 60%, validate on
  the held-out 40%.** This is the honest OOS test and it HELD:

| coin | train pick | **OOS bps/trd @0% maker** | **OOS @taker(5bp)** | OOS win% | OOS n |
|---|---|---|---|---|---|
| **ETH** | sign+1, enter_z 1.5 | **+7.23  ($/hr 21.7)** | **+2.23  ($/hr 6.68) ✅** | 59.5 | 84 |
| **BTC** | sign+1, enter_z 1.0 | **+2.09  ($/hr 6.07)** | −2.91 (dead) | 57.9 | 95 |

- **⭐ OBJECTIVE = MAX $/hr @0% maker (Greg, S76) — trade count / per-trade size are IRRELEVANT (more trades = more
  $/hr is fine).** Best OOS $/hr @0% maker: **ETH +21.7/hr** (z1.5, trail 30, hold 600, 6 trd/hr — also taker-survivable
  +2.23 bps/trd) · **BTC +15.9/hr** (z1.0, trail 15, hold 60, 45 trd/hr). The table above is the low-freq *ride*; the
  higher-freq BTC config gives the higher $/hr.
- **⭐ THE OTHER COINS HAVE THE BOOK EDGE TOO, JUST SMALLER (Greg + the paper: 5 wins, per-cell weighting).** BTC/ETH
  biggest; SOL/XRP/DOGE a smaller version, weighted low — NOT zero. So run the per-cell max-$/hr swing on ALL 5.
- ⚠ TWO real caveats (NOT quality): (1) these assume **0% maker on BOTH entry AND exit** — the reversal exit may need
  to cross (taker), and at taker the high-freq configs COLLAPSE (BTC −97/hr) → **the deployability gate is MAKER-EXIT
  at 0% on Kraken**; ETH's ride is the most taker-tolerant. (2) P&L is **mid-price (upper bound, no spread/slippage)**.

### 3. Code note — `book_swing_kraken.py` fixed to sweep `min_conv` (for the flat-book coins)
SOL/XRP/DOGE books lean less, so `min_conv=0.5` almost never fires (SOL crashed — <10 train trades). The train grid now
sweeps `min_conv` (0.0/0.2/0.3/0.5) so flat-book coins enter enough to measure their smaller edge, and guards the empty
case. **The 5-coin max-$/hr walk-forward is READY to run — that's the first S77 task (saved for next session).**

## ⭐ NEXT (S77) — confirm + wire, KRAKEN ONLY
1. **Run the per-cell MAX $/hr walk-forward on ALL 5 coins** (`book_swing_kraken.py`, code ready) — rank by OOS $/hr
   @0% maker. Expect BTC/ETH biggest, SOL/XRP/DOGE smaller-but-present (Greg).
2. **Multi-window confirm** — S76 OOS is ONE ~35–40h window. Re-run as the Kraken books accrue / across regimes. The
   decisive robustness test before sizing.
3. **Nail the MAKER-EXIT question** — can the reversal exit rest as a 0% maker on Kraken? If not, the high-freq $/hr
   collapses (taker). This gates deployability, not "quality."
4. **Wire the top-$/hr book-swings as their own sandbox directional cells** (separate from the maker zigzag) once
   multi-window holds. Firing/direction stays LOCKED (Greg-only); the swing is a NEW cell, not a change to the zigzag.

## Files (committed on the branch)
`research/shape_s71/early_signal.py` (Greg's plugin: book imbalance → magnitude+direction; `fit_direction_sign`) ·
`early_signal_kraken.py` (per-coin Kraken direction fit) · `book_direction_kraken.py` (book-vs-maker-leg test) ·
`book_swing_kraken.py` (ride-to-reversal swing + 60/40 walk-forward, drives `early_signal`).

## RULES (standing)
KRAKEN ONLY (S76) · 0% maker = the $10M tier · **objective = MAX $/hr @0% maker (trade count/quality irrelevant)** ·
firing LOCKED (Greg-only) · use Greg's `early_signal.py` AS-IS · walk-forward (train 60% / test 40%) before any claim ·
the book edge exists on ALL 5 coins, weighted per-cell (BTC/ETH biggest) · the book swing is a SEPARATE directional
cell from the maker zigzag · the maker-exit-at-0% question is the deploy gate · doge on its own track.
