# S75 — SOL loser-blade gate + two book pieces (Greg's spec) — FINDINGS

Greg (S75): both SOL losers share ONE blade shape (steep, short ramp ~x≤0.15, then flatten) vs winners
(short-win ramps to ~0.32; long-win is a smooth cubic). → make the loser-blade the FIRST pre-entry skip;
KEEP the two book pieces separate (with-side depth, against-side depth — not the net ratio "sum").

Built `sol_blade_gate.py`: birth→onset normalized limb (ignition-anchored, same as `leg_imbalance.py`) →
per-trade blade features (`blade15` first-15% slope, `kink`+`hblade` grid-hockey, `treach` front-loadedness,
`convex`) + the two scale-free book pieces (`bwith{K}`/`bagn{K}` = with/against depth ÷ causal rolling total
depth) + `peak`/`climb`. Separation diagnostic per cell + gates through the LIVE `run_kraken_cell`. SOL only.
699 legs / 73.1h / base-win 62.5% / med-dur 44s. CAP=$5000/trade. matplotlib shimmed (no install).

## Verdict: the per-trade loser-blade does NOT separate on SOL — it is a MEAN-ARC artifact (like the S73 "linear vs non-linear" falsification)

### Separation diagnostic (per-trade, per cell)
**SHORT (win 232, lose 117, cat-win 66%): nothing separates.**
- `blade15` win 2.360 / lose 2.402 — no gap. `kink` 0.443/0.434 — no gap. `treach` 0.588/0.565 — no gap.
- `hblade` 1.845/2.087 (loser steeper at the MEAN, matches Greg) BUT skipping the steepest raises win% to
  67→73% — the individual steep-blade trades are WINNERS, not losers.

**LONG (win 205, lose 145, cat-win 59%): the separators are ENERGY, not blade, and blade REVERSES.**
- `hblade` win 2.046 / lose 1.719 — long-losers are GENTLER (opposite of short → no consistent loser blade).
- `climb`/`peak` lower for losers ✅ (energy, as the S74 findings already said).
- `bwith1` win 0.613 / lose 0.454 — the single strongest long separator (skip-10% → 42.9% vs 59 base).
  Only visible because the book was kept as two pieces (net `bnet5` is flat 0.020/0.001). Greg's "keep both
  pieces" surfaced a real (weak, long-only) signal.

### Gates (live legs; ungated $/hr = 5.880)
| gate | win% | $/hr | fired | winners skipped |
|---|---|---|---|---|
| UNGATED | 62.5 | **5.880** | 100% | 0 |
| ENERGY-only (peak, 4-anchor) | 63.4 | **6.170** | 96% | 13 |
| BLADE (blade15+kink) | 63.3 | 3.832 | 58% | 180 |
| BLADE+treach / kink+treach+convex | 64.5 / 64.1 | 3.69 / 3.44 | 55% | ~190 |
| BOOK-pieces only (bwith5+bagn5) | 64.9 | 4.021 | 51% | 208 |
| BLADE **and** BOOK skip | 64.2 | 5.248 | 78% | 85 |

## Why (the mean-vs-per-trade trap, again)
Fitting a hockey to the AVERAGED winner arc gives a gentler blade (kink lands late ~0.32); the AVERAGED loser
arc gives a steeper blade (kink lands early ~0.15). But per trade the kink position does NOT separate
(0.44 vs 0.43) and the blade even reverses between short and long. So a loser-blade nearest-template gate skips
~42% of legs near-randomly → $/hr collapses 5.88→3.83. Mean separates; individual curves overlap.

## What holds
- Only the conservative ENERGY (peak) gate nudges $/hr up (5.88→6.17, in-sample) — matches "SOL win/lose
  energy levels mostly overlap" (S74). Small.
- The two long-only separators (`bwith1` with-side book depth + energy) are real but weak and long-only.

## CORRECTION — the 2-NUMBER BOOK GATE, judged JOINTLY (Greg, S75)
Greg: the two book pieces must decide pass/fail TOGETHER — one decision from BOTH numbers at the same time
(joint (with-side depth, against-side depth) position → loser region vs winner region), NOT one-then-the-other
and NOT the net ratio. Corrected in `sol_blade_gate.py::main` (joint 2-D nearest-template per level K).

| gate | win% | $/hr | fired | winners skipped |
|---|---|---|---|---|
| UNGATED | 62.5 | **5.880** | 100% | 0 |
| ENERGY (reference) | 63.4 | 6.170 | 96% | 13 |
| BOOK-2 K=1 (with+agn jointly) | 63.9 | 4.100 | 40% | 258 |
| BOOK-2 K=5 (with+agn jointly) | 64.9 | 4.021 | 51% | 208 |
| BOOK-2 K=10 (with+agn jointly) | 61.7 | 3.794 | 48% | 229 |

Result: the joint 2-number book gate lifts win% a hair (62.5→~65%) but over-skips winners (208–258/437) → $/hr
5.88→~4.0. CONFIRMS the S74 finding "SOL book is FLAT (±0.03), no separation — trade imbalance is the whole
story." The two-piece decomposition surfaced only ONE weak long-only gap (`bwith1`). SOL is the wrong coin for
a book gate; BTC is where the book is the "gold" pre-fire tell (winners born book-+, losers book-−, all K).

## Next (open — Greg's call)
1. Run this diagnostic on BTC/ETH/XRP — blade likely fails there too, but their peak (BTC short +0.257/+0.024)
   and book (BTC) separate better per the S74 tables.
2. Chase the long-only separators as a LONG-cell-only skip (bwith1 + energy), accepting shorts are a wall.
3. Eyeball individual per-trade SOL curves (not means) to confirm the blade tell truly isn't there per-trade
   before dropping it.
