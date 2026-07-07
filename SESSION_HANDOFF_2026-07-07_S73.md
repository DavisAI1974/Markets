# SESSION HANDOFF — S73 (2026-07-07)

# ══════════════════════════════════════════════════════════════════════════════
# ⛔ DROP-IN BOX — S74 (read this first)
# ══════════════════════════════════════════════════════════════════════════════
READ, IN ORDER: `STRATEGY_INVENTORY.md` (OPERATING CONTRACT + ✅ LIVE — the **ENTRY SHAPE GATE** block near
the top of LIVE carries the whole S73 result + the standing principles #0d/#0e/#0e-GATE) → this handoff →
`SIGNAL_SHAPE_DIRECTION_S71.md` → `research/shape_s71/` (the agent's ORIGINAL shape builder — reuse it, do
NOT build another).

BRANCH: this session = `claude/entry-curve-shape-classifier-b5neon` (= canonical S72 tip + all S73 work). If
S73 files are missing, the branch was cut from a stale parent → reconcile to canonical
(`git reset --hard origin/claude/shape-arc-capacity-s72-wkf5sj`) then re-apply, OR just
`git reset --hard origin/claude/entry-curve-shape-classifier-b5neon`.

**⭐ WHERE WE LANDED (S73):** built + validated the **ENTRY SHAPE GATE** (Job 1) — a per-trade entry-selection
overlay on the LOCKED firing that reads each trade's pre-onset CURVE SHAPE and skips the LOSER shapes. It runs
through the **LIVE** `run_kraken_cell` (agent's builder for the shape; nothing reinvented). The **shape
characteristics are validated** (on SOL the gate catches 75% of short-losers + 72% of long-losers), but a
**midpoint threshold over-skips** (71% of winners also skipped → win% only 61.7→63.3, $/hr halved) because
per-trade winner/loser shapes OVERLAP even though the MEANS separate cleanly. Characteristics right; threshold
too blunt. All the design principles were nailed down (see below).

**⭐ NEXT (S74):**
1. **FIND WHERE WINNER/LOSER DON'T OVERLAP, and gate ONLY there (Greg, load-bearing).** The shapes separate on
   the MEAN but overlap per-trade, so a midpoint threshold over-skips. The fix = characterize the NON-OVERLAP
   regions — the loser TAIL where winners essentially never land (bottom-decile peak for short-loser; deepest
   below-zero dips for long-loser; and whatever other feature has a clean separable tail) — PER COIN × PER CELL,
   and skip only there. Skip fewer trades, but the skipped ones are almost pure loser → win% lift without
   gutting volume. Re-run on the same SOL book through the live code first, then cell-by-cell.
2. **Pre-onset PRESSURE/BALANCE agent (NEUTRAL).** Spin up an agent to (a) MEASURE the buy/sell flow BALANCE
   (how balanced vs lopsided the buy-vs-sell flow is) during the pre-trade window, PER COIN × PER CELL (the 4
   cells), through the live executor's legs on recent book, and (b) find WHERE the 4 cells' distributions do
   NOT overlap (the cleanly-separable regions per feature per cell) so we can focus the gate there. Report
   whether/where the 4 cells differ. Shape/RATIO-based only (scale-free — NO absolute volume, NO price, per the
   S73 principle). **Give the agent NO expected outcome** (see "Greg's hypothesis" below — keep it OUT of the
   instructions to avoid biasing).
3. **Then cell-by-cell:** re-fit the (universal) shape thresholds for BTC/ETH/XRP (their OWN numbers) using the
   non-overlap regions, gate each; **doge on its own separate track** (doge is excluded from the 4-major rules).

**⛔ Greg's hypothesis — FOR OUR EYES ONLY, do NOT put in the S74 agent's instructions (avoid biasing the
findings):** Greg's guess is that more BALANCED buy/sells may characterize the SHORT cells (both wins and
losses) and more LOPSIDED flow the LONGER runs. Test it NEUTRALLY — the agent must not be told this.

# ══════════════════════════════════════════════════════════════════════════════

## What S73 did — Job 1, the ENTRY SHAPE GATE, built through many Greg refinements

The entry gate is a per-trade ENTRY SELECTION overlay on the LOCKED firing (Greg-only): read each forming
trade's pre-onset ascent CURVE SHAPE and DON'T FIRE on the loser shapes. Built ON the agent's original shape
builder (`research/shape_s71/arc_gate.py` + `regroup2.py` + `quad_means.npz` — reuse, never rebuild), decision
through the LIVE `run_kraken_cell`. Ran on SOL's 73h Kraken book, $5k/trade, one-sided maker, no deep-bail.

### The design principles nailed down this session (all in the LIVE ENTRY SHAPE GATE block)
- **SHAPE, not numerical values — NO volume, NO price.** Both scale per coin/regime → nothing transfers. The
  signal object is the normalized imbalance-ratio arc ([−1,1]) so the CURVE SHAPE is scale-invariant. This is
  WHY shape ≫ numbers (and why a literal slope/rate SCALAR reads backwards — go with the graph).
- **UNIVERSAL SHAPES, CELL-SPECIFIC NUMBERS** (across the 4 majors; doge separate). The 4 archetype
  CHARACTERISTICS are coin-universal (characterize once); only the THRESHOLDS re-fit per cell. This IS #0d
  (shape = fixed scaffold, thresholds = tunable numbers).
- **Grade PER CELL × PER CATEGORY, never lump the NUMBERS** — lumping averages across different thresholds →
  signal cancels → flat gate (exactly why the early general gate came out flat).
- **NO AVERAGING in the decision** (#0d/#0e-GATE); **the edge is the CURVE, not an AUC** (#0e — all AUC refs
  purged this session).

### The 4-cell characteristics (universal shapes; SOL's numbers shown)
- **SHORT-WINNER** — short run, moderate energy (peak ~0.125), clear positive peak, holds above zero.
- **SHORT-LOSER** — short run, FLAT / no energy (peak ~0.014), barely above zero, shallowest. Tell = no energy.
- **LONG-WINNER** — long run, HIGHEST energy (peak 0.348), steepest ascent, stays above zero most.
- **LONG-LOSER** — long run, lower peak (0.295), LOWER ascension rate, dips DEEPER/LONGER below zero
  (ascent-min −0.64 vs −0.56; 37% vs 33% below zero). Tell = below-zero dip.
- **Easiest discriminators:** (1) ENERGY = onset PEAK (ranks short-lose < short-win < longs, splits the short
  pair 0.125 vs 0.014), then (2) BELOW-ZERO DIP to split the long pair. Run-length = the long/short axis.
- **Ascension rate:** winner steeper in both (per the graph); a rate SCALAR on the normalized signal reads
  backwards (saturation) — use the shape/peak, not the scalar.

### The gate result (SOL, LIVE run_kraken_cell, same 73h book)
- ungated: 61.7% win / +11.26 $/hr (100% fired).
- refined 4-cell cascade (skip short-loser on low energy + long-loser on deep below-zero dip): IS 63.3% win /
  6.08 $/hr / 28% fired; OOS 62.2% / 7.32 / 28%.
- Loser detection WORKS: short-loser recall 75% (203/270), long-loser 72% (224/313).
- But WINNERS wrongly skipped 71% (670/939) → over-skip. Per-trade winner/loser shapes OVERLAP heavily even
  though the MEANS separate — a midpoint threshold catches losers AND winners alike. Characteristics validated;
  threshold too blunt → S74 loser-tail-selectivity is the fix.

## Artifacts (committed on the branch; the agent's ORIGINAL builder is reused, not rebuilt)
- `STRATEGY_INVENTORY.md` — the LIVE ENTRY SHAPE GATE block (the way forward) + #0e-GATE + all S73 principles.
- `research/shape_s71/` — the agent's ORIGINAL builder (`arc_gate.py`, `regroup2.py`, `quad_means.npz`) +
  S73 selection/analysis on top: `sol_ascent_eq.py` (ascension equation, per-cell characteristics),
  `sol_loser_gate.py` (the refined 4-cell entry gate through the live code), `sol_gate_run.py` (the
  individual-curve k-NN gate, earlier cut).
- SOL book: `git show origin/data/sol-kraken-book:sol_kraken_book.jsonl.gz | gunzip > /tmp/kbook/sol_book.jsonl`.

## RULES (standing, unchanged)
Firing LOCKED (Greg-only) · live-code-only for every test · shape not numbers (no volume/price) · universal
shapes + cell-specific numbers · per-cell × per-category · no averaging · the edge is the CURVE, never an AUC ·
the 4-major shape rules EXCLUDE doge (doge-specific pass is its own job).
