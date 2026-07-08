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

- **⭐⭐ ETH is a deployment candidate: OOS +7.23 bps/trade at 0% maker AND taker-survivable (+2.23).** Reproduces the
  paper's magnitude out-of-sample on Kraken with train-selected params — not a cherry-pick.
- **BTC: OOS-positive at 0% maker (+2.09) but dead at taker** — BTC's moves are small (~1.4 bps/60s, most HFT-competed
  book), so it needs the 0% maker floor. Real edge, thinner.
- The strict, LOW-FREQUENCY entry is what recovers the fat per-trade edge (his ~0.5–1.5 trades/hr, not my first 5.8/hr).

### 3. ⚠ Tuning trap (do NOT repeat): optimizing train **$/hr @0% maker** overfits to CHURN
Adding trail/hold to the grid and picking best train $/hr@0 chose trail15/hold60 → 740 trades (45/hr), +0.7 bps/trade:
big $/hr @0 but **−90 to −97 $/hr at taker** — razor-thin, not robust. **Tune by per-trade QUALITY (bps/trade), not
$/hr (which rewards fee-fragile churn).** The robust config is the low-frequency RIDE (trail 30 / hold 600).

## ⭐ NEXT (S77) — confirm + wire, KRAKEN ONLY
1. **Multi-window confirm** — the S76 OOS is ONE ~35–40h window split 60/40 (ETH OOS n=84). Re-run the walk-forward
   as the Kraken books accrue more hours / across regimes. This is the decisive robustness test before sizing.
2. **Tune by bps/trade quality, not $/hr** (avoid the churn trap). Keep the low-frequency ride (trail 30 / hold 600).
3. **Wire the ETH book-swing as its own sandbox cell** (directional, separate from the maker zigzag) once multi-window
   holds; BTC as a 0%-maker-floor cell.
4. Firing/direction stays LOCKED (Greg-only); the book swing is a NEW directional strategy, not a change to the zigzag.

## Files (committed on the branch)
`research/shape_s71/early_signal.py` (Greg's plugin: book imbalance → magnitude+direction; `fit_direction_sign`) ·
`early_signal_kraken.py` (per-coin Kraken direction fit) · `book_direction_kraken.py` (book-vs-maker-leg test) ·
`book_swing_kraken.py` (ride-to-reversal swing + 60/40 walk-forward, drives `early_signal`).

## RULES (standing)
KRAKEN ONLY (S76) · 0% maker = the $10M tier · firing LOCKED (Greg-only) · live-code / his-plugin-as-is · tune by
per-trade QUALITY not $/hr churn · walk-forward (train 60% / test 40%) before any claim · the book swing is a SEPARATE
directional cell from the maker zigzag · SOL is done (spread-capture wall) · doge on its own track.
