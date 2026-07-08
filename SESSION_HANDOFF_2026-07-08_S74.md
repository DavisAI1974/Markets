# SESSION HANDOFF — S74 (2026-07-08)

READ FIRST: `STRATEGY_INVENTORY.md` OPERATING CONTRACT + ✅ LIVE section — the **S74 WHOLE-LEG IMBALANCE
FINDINGS** block + the **S74 ENTRY-ENERGY GATE** block carry the whole S74 result. Then this handoff. Then
`research/shape_s71/leg_imbalance_findings.md` (the full tables + 8 equations/coin + per-cell PNGs).

BRANCH: `claude/entry-shape-classifier-s74-5lb1p5` (reconciled to the canonical S73 tip
`origin/claude/entry-curve-shape-classifier-b5neon` at session start, then all S74 work on top). Books restored
to `/tmp/kbook/{sol,btc,eth,xrp,doge}_book.jsonl` via `git show origin/data/<coin>-kraken-book:<f>.jsonl.gz | gunzip`.

## What S74 did (Job 1, entry, then the whole-leg imbalance characterization)

### 1. Entry-energy gate — tested every way through the LIVE code (`sol_loser_gate.py` / `gate3.py`)
The S73 "4 energy values as the fire gate" (onset peak, per cell): tested as train-midpoint, loser-own-number,
all-legs 4-anchor, absolute + PROPORTIONAL wiggle. Verdict: **energy is a real mean-differentiator but blunt as
a standalone absolute-level gate** — on SOL it over-skips ~40% of winners (win% 61.7→63.6 but $/hr 11.26→10.08).
**BUT the SOL failure is SOL-SPECIFIC:** the energy gate roughly DOUBLES $/hr on BTC (2.5→6.08), ETH (5.47→6.40),
XRP (2.47→5.18). On SOL a cumulative deep-hole skip (`late_integral` lowest ~5%) beats it (11.43 > ungated 11.26).
ALL IN-SAMPLE. The S73 "linear vs non-linear ascent" prime discriminator is **FALSE** — all 4 cells are convex
hockey sticks; linearity does not separate.

### 2. Whole-leg imbalance characterization (the payoff) — `leg_imbalance.py` + `_findings.md` + PNGs
Extended each of the 4 cells' legs TURN-TO-TURN (valley/birth via `ignition_idx`, lookback ≤150s → onset peak →
exhaustion at the ACTUAL close, no clip) through the LIVE `run_kraken_cell`. Two channels signed to side: TRADE
imbalance `(buy−sell)/(buy+sell)` and BOOK imbalance `(bidK−askK)/(bidK+askK)` K1/5/10. Per-cell mean arcs.
Scope: SOL 699 legs/73h, BTC 885/42h, ETH 623/67h, XRP 635/73h.

- **TRADE IMBALANCE IS THE DECIDER (Greg's hypothesis — confirmed + more):** DIRECTION = trade-imbalance POLARITY
  (born ~−0.85 against-side at the valley, flips with-side at onset; onset sign = buy/sell, gap +0.47..+0.72 all 4
  coins; BOOK does NOT decide direction). DURATION = onset PEAK HEIGHT (long ~+0.33..+0.45 vs short ~+0.13..+0.25).
- **⭐⭐ UNIVERSAL EXIT TELL (all 4 coins):** WINNER post-onset tail holds ≥0 to close (exh ≈0..+0.1, just
  de-energizes); LOSER tail decays THROUGH zero to −0.14..−0.42 — the flow reverses onto the other side, and THAT
  reversal IS the loss. Pre-fire shape = SAME family all cells (why entry win/lose is hard); win/lose lives in the
  TAIL. Exhaustion point = flow returning to balance (zero-cross); the live exit lets losers reverse to ~−0.3 first.
- **⭐⭐ BTC BOOK = PRE-FIRE WIN/LOSE FORECAST ("worth its weight in gold"), COIN-SPECIFIC:** on BTC, winners born
  book-POSITIVE and stay positive whole leg, losers born book-NEGATIVE and stay negative (K1/5/10 agree; forecasts
  win/lose AT the valley, pre-ignition). FLAT on SOL, WEAK on ETH, LONG-WIN-only on XRP. Book never flips at the
  peak (standing lean, not a turn tell — the turn tell is in the TRADE channel).
- **8 equations/coin** (pre-fire + tail per cell, split at the fire) in `_findings.md` §4. Pre-fire = convex-cubic/
  hockey family; TAIL = the distinguishing shapes (win flattens near 0; lose declines through 0 to negative).

⚠ ALL CHARACTERIZATION — mean arcs, one book window/coin. NOT a per-trade gate, NOT sizing-grade. The tail-flip must
be tested as a per-trade EXIT trigger (same overlap risk the entry energy had).

### 3. EXIT KNOB — BUILT as a per-coin TUNING KNOB; baseline wins so far → stick with baseline (Greg)
Wired an opt-in `balance_exit=(arm_hi, exit_lo)` into `odcore/swing_maker.py` (threaded through `run_stream`/
`run_kraken_cell`; default None = byte-identical, canary reproduced SOL 1522 / BTC 2395 / ETH 1459 / XRP 1518 legs
leg-for-leg; coexists with deep-bail, earliest cell wins). **This is the FINE-TUNING stage, and it's still a win —
the exit tool is built + live + per-coin tunable.** On the current window baseline still wins on all 4 majors (best
config vs baseline: SOL +8.44 vs +11.26, BTC −2.91 vs +2.49, ETH +0.31 vs +5.47, XRP +0.94 vs +2.47; full
arm×window×exit_lo grid). **RULE (Greg): tune the knob PER COIN on fresh book; adopt only where a coin's tuned config
BEATS its baseline — where baseline still wins, STICK WITH BASELINE** (current flow-turn + cover-grace exit). WHY
baseline wins so far: (1) the current flip-turn exit is already at the trade's 60s scale (subsumes the knob); (2)
**FLOW LAGS PRICE** — winners' flow returns to ~0 while their PRICE gain holds to the later price turn (exiting hands
back 15–25% winner $/hr), losers' loss already in price by the time flow rebalances. The bigger win/lose lever is
ENTRY; deep-bail caps the loser price tail. `research/shape_s71/exit_test_findings.md`.

## ⭐ NEXT (S75)
1. **⭐⭐ THE PER-CELL EQUATIONS may be the winning part (Greg):** the pre-fire + tail equations (8/coin, split at
   the fire) are in `research/shape_s71/leg_imbalance_findings.md` §4 (+ `fit_shapes.py`). Greg thinks THESE are the
   winning piece — get them into usable form and build on them. (Not urgent per Greg, but the lead to chase.)
2. **⭐⭐ THE BTC BOOK GATE ("worth its weight in gold"):** the ONE pre-fire win/lose tell we have. Build + validate
   the BTC book pre-fire lean as a BTC ENTRY gate (skip/down-weight legs BORN book-negative at the valley); confirm
   OOS / on fresh book. BTC-specific (flat on SOL, weak ETH, long-win-only XRP).
3. **Validate the ENERGY gate on BTC/ETH/XRP walk-forward** (doubles $/hr in-sample: BTC 2.5→6.08, ETH 5.47→6.40,
   XRP 2.47→5.18) — if it holds OOS it deploys; SOL uses the cumulative deep-hole (`late_integral`) skip.
4. **EXIT knob:** re-tune `balance_exit` per coin on fresh book; keep baseline where baseline wins. Entry is the
   bigger lever. doge on its own track (excluded from the 4-major rules).

## Files (all committed on the branch)
`research/shape_s71/`: `leg_imbalance.py` (whole-leg 2-channel char), `leg_imbalance_findings.md`, `leg_imbalance_{coin}.png`,
`whole_legs.py` (turn-to-turn extractor), `fit_shapes.py` (per-cell equation fitter), `sol_loser_gate.py` / `gate3.py`
(entry-energy gate), `cell_ascent_equations_findings.md` (first agent's ascension-equation run). Books local in `/tmp/kbook`.

## RULES (standing, unchanged)
Firing LOCKED (Greg-only) · live-code-only (decision via run_kraken_cell) · shape/RATIO only (no volume/price) ·
per cell × per category · the edge is the CURVE (not an AUC) · 4-major shape rules EXCLUDE doge.
