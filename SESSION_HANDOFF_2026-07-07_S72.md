# SESSION HANDOFF — S72 (2026-07-07)

# ══════════════════════════════════════════════════════════════════════════════
# ⛔ DROP-IN BOX — S73 (read this first)
# ══════════════════════════════════════════════════════════════════════════════
READ, IN ORDER: `STRATEGY_INVENTORY.md` (OPERATING CONTRACT + ✅ LIVE + the S72 **SHAPE STRATEGY** block at
line ~217 + standing principle #0d NO-AVERAGING) → this handoff → `SIGNAL_SHAPE_DIRECTION_S71.md` (+ its S72
no-averaging correction) → `research/exit_s72/PEAK_VALLEY_FINDINGS_S72.md`.

BRANCH: this session = `claude/shape-arc-capacity-s72-wkf5sj` (canonical; it is the S71 tip + all S72 work).
If S72 files are missing, reconcile: `git reset --hard origin/claude/shape-arc-capacity-s72-wkf5sj`.

**⭐ WHERE WE LANDED (S72):** Greg walked the shape graphs and the WHOLE-BALLGAME picture crystallized —
ONE live curve gives direction (peak/valley, locked) + entry-quality (fire/skip) + duration + exit. Recorded
as **THE SHAPE STRATEGY** (the intended build; needs refinement first). Two decisive tests ran: (1) exit
CLIPPING confirmed (winner tops mostly past +120s), (2) the **peak-to-valley "exhaustion marks the price
turn" test = NULL** on the sparse Kraken trade-flow. The entry-shape edge (S71, AUC 0.60–0.70) is untouched.

**⭐ NEXT (S73):** decide the fork on the exit/turn read — either (a) get a DENSER trade tape (aggregated
cross-venue) or a BOOK-DEPTH-pressure proxy so the exhaustion read isn't saturated, or (b) set the exit
thread aside and BUILD + validate the confirmed ENTRY-QUALITY classifier (ascent algebra + peak height →
fire/skip, per-cell OOS through the live executor) — that's the real, ready prize. Greg to steer.

**⭐ GREG'S S72 CLOSING REFRAME (load-bearing simplification):** the entry gate does DOUBLE DUTY — selection
AND loss-avoidance — so **DEEP-BAIL is DEMOTED** (we don't fire the losers it was there to cap; keep it only
as a THIN BACKSTOP since the gate is ~0.60–0.70 AUC, not perfect). And the whole exit hunt was ONLY ever about
exiting **WINNERS at their top** (optimization — capture more of a correctly-entered ride), NOT survival — so
the exhaustion-top NULL costs us little: worst case ride the winner and exit on the current running logic
(detector's next flow turn / cover-grace). The ballgame collapses to: DIRECTION (peak/valley, locked) → ENTRY
(fire only predicted-winner shapes = the prize, also kills loss-mgmt exits) → EXIT (winner-optimization only;
current logic is the fine default; exhaustion-top needs denser tape / book-depth to improve).

# ══════════════════════════════════════════════════════════════════════════════

## What S72 did — the SHAPE thread, walked and pressure-tested

### 1. The WHOLE-BALLGAME reframe crystallized (Greg, walking the graphs)
Read every decision off ONE live curve (the individual trade's flow shape). Recorded in
`STRATEGY_INVENTORY.md` as **THE SHAPE STRATEGY** (line ~217; the intended build, NOT deploy-ready):
- **DIRECTION** = peak→SELL / valley→BUY (the lean/zigzag turn type; not a prediction; LOCKED, Greg-only).
- **ENTRY QUALITY (fire/skip)** = the pre-onset ASCENSION shape. WINNER = starts on-side (≥0), climbs early,
  **HOCKEY-STICK** (flat handle → steep LATE blade), tops HIGH. LOSER = dips below zero first, gradual rounded
  rise, low peak. **Rate-of-ascent (the blade) is the headline pre-fire tell.** Skip predicted losers = the
  biggest prize. This is the QUALITY axis (NOT direction — "direction is dead" does not apply to it).
- **DURATION (short/long ride)** = ascent morphology.
- **EXIT** = the exhaustion limb (the FLATTEN / velocity→0, "no more movement" — stronger than the loose
  zero-CROSSING). ← this is the piece S72 pressure-tested and it did NOT hold on Kraken trade-flow (see §4).
- **2×2 archetypes = duration × outcome**; same shape, own NUMBERS per cell (doge = same shape, own scale).

### 2. Standing rule sharpened (Greg, S72) — NO AVERAGING, INDIVIDUAL TRADE SHAPES ONLY
The signal is EACH individual trade's shape. The `quad_means` archetype arcs are a PICTURE of the archetype
ONLY — never the signal, never the grader. Averaging destroys the per-trade shape and washes the edge; a flat
pooled scalar is the averaging error, not a null. Validation = classify each trade on its OWN shape and TALLY
per-trade decisions (that is counting, not averaging curves). Folded into `SIGNAL_SHAPE_DIRECTION_S71.md` top.

### 3. The +20 arc "jump" — RESOLVED as a smoothing artifact (not a turn)
The step at +20s in the archetype arcs moves EXACTLY with the smoothing window (SMOOTH_SEC 10→+10 / 20→+20 /
30→+30). It's the onset volume CLIMAX (a real event, the turn's volume) falling out of the trailing smoother
at exactly SMOOTH_SEC seconds — the ENTRY climax echoed forward, NOT a second turn at +20. Informational only,
dropped as an exit marker.

### 4. Two decisive exit tests (agent, `research/exit_s72/`)
- **EXIT CLIPPING — confirmed (Greg was right).** With an honest long horizon (600s), **65–69% of winner price
  tops land past +120s** (median top 242–262s, was mis-read as 35–68s at the 120s cap). The +120s window cost
  a median **+4.6 (btc) … +11.3 (doge) bps**, p90 up to 34 (scales with vol). `exhaustion_price_exit.py`.
  ⚠ the "ideal exit" is a perfect-hindsight oracle over a long look-ahead (argmax bias); the clean, real result
  is the *clipping*, not a deployable "hold to 250s" rule.
- **PEAK-TO-VALLEY "exhaustion marks the price turn" — NULL** (`peak_valley_exhaustion.py`,
  `PEAK_VALLEY_FINDINGS_S72.md`). Segmented the tape by the PRICE's own zigzag peaks/valleys (θ 10/20/40bp),
  signed flow by swing direction, 4 swing-groups, per-leg, plus correlation/precision. Result across ALL cells/
  θ/groups: P(exhaustion spent | turn) ≈ 45–60% (coin flip); flow flip LAGS the turn (negative lead); not
  specific (flips 1300–1800× vs tens–hundreds of turns → fires everywhere); per-swing corr(flow,price) ≈ +0.1
  (weakly WITH-trend, not rolling back); 4 groups do NOT separate; only asymmetry = a peak buy-flow baseline
  (retail bias). **ROOT CAUSE:** Kraken trades are SPARSE (~1.7% btc → 0.2% doge of 0.1s cells) so
  rolling_imb(20s) SATURATES to a ±1 square wave — no coherent exhaustion arc over multi-minute price swings.
  So it's a data-resolution limit, not "exhaustion is meaningless."

### 5. Scoping the null (honest, load-bearing)
- Does NOT contradict the S71 ENTRY finding — that's a different object (the flow-ONSET legs, short horizon at
  the trade climax where flow HAS structure). **Pre-onset shape → winner/loser AUC 0.60–0.70 all 5 cells stands.**
- DOES say: "catch the price top/bottom via 20s trade-flow exhaustion" is not supported on this sparse book.
- Untested alternatives for the price-turn/exit read: a DENSER/aggregated cross-venue trade tape (unsaturate
  the imbalance), or a BOOK-DEPTH-pressure proxy (resting bid/ask imbalance) instead of sparse trade-imbalance.

## Artifacts (all committed on the branch; PNGs gitignored, regen from scripts)
- `STRATEGY_INVENTORY.md` — the S72 SHAPE STRATEGY block (line ~217).
- `SIGNAL_SHAPE_DIRECTION_S71.md` — + S72 no-averaging correction banner.
- `research/shape_s71/` — arcs, `quad_means.npz`, `doge_only.py`.
- `research/exit_s72/` — `exhaustion_price_exit.py` (clipping), `eyeball_trades.py` + `eyeball_grouped.py`
  (individual-trade views), `peak_valley_exhaustion.py` + `PEAK_VALLEY_FINDINGS_S72.md` (the NULL),
  `EXIT_EXHAUSTION_FINDINGS_S72.md`.
- Books materialize from `data/<coin>-kraken-book` → `/tmp/kbook/<coin>_book.jsonl`
  (`git show origin/data/<coin>-kraken-book:<coin>_kraken_book.jsonl.gz | gunzip`).

## NEXT (S73) — Greg to steer the fork
1. **THE READY PRIZE — build the ENTRY-QUALITY classifier.** Per-trade ascent ALGEBRA (slope/curvature) +
   peak height + start-above/below-zero → fire/skip, compared to the winner band with WIGGLE ROOM. Validate
   per-cell OOS + shuffle-null THROUGH the live executor (`run_kraken_cell`). This is the confirmed edge (AUC
   0.60–0.70) and does not depend on the exit null. Firing/direction stays on the lean (Greg-only).
2. **The EXIT/turn read** — only if pursued: get a denser/aggregated trade tape OR test a book-depth-pressure
   exhaustion proxy; the sparse 20s trade-imbalance is a dead end for the price turns.
3. Standing: capacity/reserve-per-rest (+9.65/hr) settled S71; 16 candidates need Greg's book-collector trigger.
