# STRATEGY & TOOL INVENTORY — DavisAI Markets (living doc; started S64 2026-07-05)

# ══════════════════════════════════════════════════════════════════════════════════════════
# ⛔ OPERATING CONTRACT — READ THIS FIRST, EVERY SESSION. THESE ARE LOCKED. (Greg, S70)
# ══════════════════════════════════════════════════════════════════════════════════════════
# This is not history — it is the binding contract. Everything below this box is reference/log.
# If anything below (a drop-in Job, an old S-block) contradicts this box, THIS BOX WINS.
#
#  1. FIRING IS FIXED. Each coin's detector stack (direction/side, REV, eps, deep-bail, cover-grace —
#     the LIVE section firing table = odcore/platform.py::KRAKEN) is LOCKED. Never re-adjudicate, sweep, reverse, or "compare"
#     a coin's firing. It changes ONLY when Greg explicitly says to change a specific coin (and,
#     once live, via the evolution review loop — never ad-hoc mid-session).
#  2. GREEDY IS ALREADY LIVE (odcore/allocator.py mode="greedy" + platform.run_portfolio, canary-clean).
#     Do NOT rebuild it. The ONLY work is ADJUSTING HOW GREEDY FILLS THE $5k.
#  3. LIVE CODE ONLY. Every test/backtest runs its DECISION through the live executor
#     (run_stream/run_kraken_cell → swing_maker) + the live allocator. NO tape proxy, NO
#     reimplementation, NO bolt-on. (capacity.py-on-TAPE is RETIRED as a capacity source — S69.)
#  4. ALWAYS FRONT-OF-LINE. We post the best bid/offer (enticing close) so we are first in line.
#     "queue"/back-of-line is NOT an operating mode — never a choice, at most a worst-case footnote.
#  5. BOOK = FILLS. TAPE = PLUMBING/STRUCTURE ONLY. Price/tune the fill on RECENT book (recent book =
#     current conditions = the right surface; we do NOT wait weeks). Never grade/price a coin on tape.
#  6. THE CAPITAL MODEL: ONE $5k bank, kept ~100% deployed as a MAKER, front-of-line. Fill the BEST
#     performer ($/hr per $) first, up to what its BOOK can absorb / capital allows; the remainder
#     cascades to the next-best LIVE coin, and so on to $5k. Breadth (majors + minors) is what keeps
#     the bank full — no idle, no queue-waiting (if a coin is tapped, move to the next coin in line).
#     Never DROP a coin (all coins stay seated). "Never fund negative edge" is a WRONG rule (Greg, S70) —
#     average edge does NOT predict a trade; we keep the $5k deployed, we do NOT idle it or exclude a coin.
#
# THE ONE JOB, ALWAYS: adjust how the live greedy allocator fills the $5k from the live BOOK,
# front-of-line — firing untouched. That is the entire session surface unless Greg says otherwise.
# ══════════════════════════════════════════════════════════════════════════════════════════

> **WHY THIS EXISTS (Greg, S64):** we keep re-deriving from one tool and forgetting the rest of our
> own toolkit (S64: a whole benchmark got run on *bare* flow-lean, ignoring the deployed stack + the
> E300 family). This is the canonical list of EVERYTHING we have live/built so no session misses it.
> **Rule: read this at session start; update it whenever a strategy/tool/cell is added, tuned, or retired.**
> Keep it in sync with `odcore/platform.py::DEPLOYED` and the per-session handoff/kickoff.

---

## ⭐ STANDING RULE (Greg, S65) — SIM = LIVE CODE + NEW PIECES (things must MATCH)
Every simulation / backtest / probe MUST run its DECISION through the LIVE code
(`odcore/platform.py::run_cell`/`run_stream` → `odcore/swing_maker.py`), never a reimplementation. A sim
only ADDS pieces the live path doesn't own yet: a data loader for a venue with no live loader, new signal
COMPOSITION, portfolio/sleeve orchestration, parameter sweeps. It does NOT rewrite the executor, fill
model, sizing, or fees. **New mechanics go INTO `odcore/` (live) FIRST, then the sim uses them** — e.g. the
S65 enticing close is `swing_maker.close_improve_bps`, threaded through `run_stream`, then used by
`basket_sim_kraken.py`. This RESTATES the standing no-rewrite-of-existing-files rule (Greg: "please make a
note to not rewrite sim code in place of our actual code"). **MAKER NUMBERS ARE FRONT-OF-LINE** by default
(`fill_model="front"` — the deployed S46 premise "have the best bid/offer"); back-of-line/`queue` is a
pessimistic REFERENCE only. WHY THIS RULE: S65 caught the basket sim using `queue`/back-of-line while live
uses `front` — the numbers didn't match. That mismatch is exactly the failure this rule prevents.

> **⭐⭐ RE-STATED, LOUDER (Greg, S69): ALWAYS RUN THE LIVE CODE FOR EVERY TEST. NO EXCEPTIONS.**
> Never estimate fills/capacity/edge with a tape PROXY, a hand-rolled reimplementation, or a bolt-on
> ( `capacity.py`-on-tape, a scratch script that recomputes eligibility, etc.). Every fill/capacity/$hr
> test MUST go through the actual executor (`run_stream`/`run_kraken_cell` → `swing_maker`) on the REAL
> data — and the honest FILL comes from the L2 **BOOK** via `fill_model="queue"` + real `best_bid_sz`/
> `best_ask_sz` (`scripts/basket_sim_kraken.py::load_book` already does this), **not** tape flow. If you
> catch yourself reimplementing what the executor already does, STOP and call the live code. (S69 burned
> a whole session estimating capacity from the tape — nonsense $25 "caps" — when the live queue-fill on
> the real Kraken book was the answer the whole time: BTC fills ~34% queue / ~90% front of the $5k.)

---

## ⛔⛔ STANDING RULE #0b (Greg, S70) — DO NOT TOUCH HOW COINS FIRE. FILL-LAYER ONLY.
**The per-coin FIRE strategy is FIXED and LOCKED.** Direction/side, REV threshold, early-arm eps, deep-bail,
cover-grace — the entire per-coin detector stack in the LIVE section firing table (= odcore/platform.py::KRAKEN) — is DONE. Every session
**RUNS what the strategy doc says, verbatim, through the live path.** You do NOT re-adjudicate direction,
sweep REV/eps, "explore" alternative signals, or bracket strategy variants for a coin — that work is closed.
- **The ONLY thing we tune is HOW CAPITAL GETS FILLED across the stack** — the fill model (front/queue), the
  shared-$5k allocation / capital layer, capacity. NOT how a coin fires.
- **NEVER change how a coin fires except when Greg EXPLICITLY says to change a specific coin.** No exceptions,
  no "quick check," no re-running a coin reversed "to compare."
- **New coins get the GENERAL per-coin strategy applied as-is;** the only tuning is the FILL, on a couple days
  of the most RECENT book (recent book = current trading conditions = the right tuning surface — we do NOT
  need weeks to accrue). An `evolution` step will SUGGEST config updates for review — suggestions are never
  self-applied, and even then a coin's firing changes only on Greg's explicit say-so.

## ⛔⛔ STANDING RULE #0c (Greg, S70) — LIVE CODE ONLY FOR TESTS. ZERO TOLERANCE. TIGHTEN UP.
Restates the SIM=LIVE rule with no exceptions: **we do NOT write testing programs that don't run the live
version.** Every test/backtest/probe's DECISION goes through the live executor (`run_stream` /
`run_kraken_cell` → `swing_maker`); a script may ONLY add I/O (a venue book loader) + orchestration
(param loop, portfolio layer, reporting) AROUND the live calls. No scratch reimplementation of the
executor/fill/fees/sizing, no tape proxy, no bolt-on. If a test isn't calling the live code, it doesn't run.

## ⭐ STANDING PRINCIPLE #0d (Greg, S71) — STRUCTURE IS SCAFFOLDING; ONLY THE NUMBERS ARE TUNABLE
Our STRUCTURE is good — treat it as fixed **scaffolding**. STOP changing the architecture session to session;
the thing that adapts to conditions is the **numeric values**, not the structure.
- **SCAFFOLDING (fixed):** the flow-lean zigzag detector, `swing_maker` executor, `run_portfolio` +
  reserve-per-rest, the signal DEFINITIONS (the exhaustion/onset arc, dipole/divergence), the pipeline shape.
- **TUNABLE (the only thing that moves):** per-cell params (`rev/eps/grace/bail/improve`), window/smoothing
  sizes (incl. the ~60s/5s shape windows), capacity caps, ranking weights, signal thresholds (`DIVERGE_STRONG`,
  …) — fitted to CURRENT conditions.
- Generalizes #0b (firing locked) + #0c (live-code-only) + the no-rewrite rule into one: **scaffold + knobs.**
  It is exactly the architecture the continuous re-tuner needs (tune numbers on a fixed structure, never rewrite
  the structure) and mirrors the shape thesis (structure/shape invariant; numbers regime-dependent — "same
  shape, same conditions, different numbers"). Firing stays Greg-only regardless.
- **WHY (Greg, S71 — the reading-rule):** long-window AVERAGES rarely fit, because conditions are always
  changing — averaging blends conditions that shouldn't be blended, so the real-time edge cancels in the mean.
  The long window gives the SCAFFOLD (general shape/baseline); **you trade the REAL-TIME CORRECTION to it**, not
  the average. Corollary for every backtest: a flat long-window average does NOT falsify a live signal — the
  edge lives in the real-time deviation, so judge signals on the correction, not the mean. (This is the OD
  adaptive-operator / energy-trader instinct: re-fit the numbers to CURRENT data continuously.)
- **CHURN COROLLARY (Greg, S71):** don't throw churn away blindly. Churn is NEUTRAL, bounded only by the FEE
  FLOOR — profitable churn (each trade clears its cost) is MORE money; only SUB-FEE churn bleeds. Do NOT
  optimize for fewer trades; optimize for PROFITABLE trades, let the count be whatever the market gives. The
  S71 "preemption thrashes" / "aggressive open-fee on churn" verdicts were the SAME averaging error — those
  specific trades were sub-fee in ONE low-edge window, NOT proof churn is bad; where each ride clears the fee,
  that churn is money.
- **DIPOLE = REAL-TIME TREND-FOLLOWER, averaged out (Greg, S71):** we already established the dipole is a great
  trend-follower (flow = trend; ride the flow = ride the trend, S36). We were AVERAGING OUT THE TREND — pooling
  over long windows flattened exactly the trend it tracks (the flat conviction ladder). The onset→exhaustion
  ARC (S71 shape work) IS that trend in real time: flow builds (ignition) → ride → exhausts (trend dies) →
  flip. Read/trade it in real time; never average it. The arc SHAPE is the profitable-churn filter (ride the
  trends whose ignition arc predicts a fee-clearing move; skip the rest).

## ⛔⛔ STANDING PRINCIPLE #0e (Greg, S72 — EMPHATIC, STOP RE-LITIGATING) — WE READ THE CURVE SHAPE, NOT A SNAPSHOT/AUC SCALAR
The entry-quality edge **IS the individual trade's ASCENT CURVE SHAPE** — its morphology, read PER TRADE: rate of
ascent (the hockey-stick blade), peak height, start above/below zero — matched to the archetype shapes with WIGGLE
ROOM. It is **NOT a snapshot AUC or any single scalar.** Any AUC ever quoted (e.g. the S71 ~0.60–0.70) was ONLY a
rough one-off check that shape carries information — it is **NOT the signal, NOT the validation metric, and NOT how
we deploy.** We validate and deploy on the per-trade **SHAPE MATCH**, never on a collapsed scalar. Do NOT re-describe
this edge as "an AUC classifier" — that is the same snapshot/averaging error #0d forbids, applied to the OUTPUT
instead of the input. When you write about this edge, write "the curve shape read per trade," not "the AUC." This
battle is CLOSED — the object is the CURVE.

> ⛔⛔ #0e-GATE (Greg, S73 — DO NOT AVERAGE THE ARCHETYPES INTO THE GATE). The 4 archetypes (short/long ×
> winner/loser) are FOUR SEPARATE SETS OF INDIVIDUAL CURVES — never collapse a set into one mean/centroid and
> match to that. A centroid gate IS averaging (the winner-mean ≈ loser-mean when the arcs saturate, so it can't
> separate — proven on SOL S73). The gate matches each forming trade to the EXACT individual curve shapes
> (nearest actual curves / per-trade template match), keeping all 4 buckets as distinct reference sets, and
> outputs trade / don't-trade. NO averaging ANYWHERE in the gate — not of the input arc, not of the archetype
> references. "Pick the exact curve shapes and use those as trade-or-not" (Greg verbatim, S73).

## ⛔⛔ STANDING PRINCIPLE #0f (Greg, S75 — EMPHATIC) — WE MATCH CURVE SHAPES; WE DO NOT SOLVE EQUATIONS FOR NUMBERS
The per-cell equations (`leg_imbalance_findings.md` §4) are **EQUATIONS OF CURVES — algebraic descriptions of a
CURVE'S SHAPE**, i.e. simply how a curve is written down. **We do NOT solve them for a scalar. We do NOT collapse a
curve to a peak / blade-number / energy / any single value. We do NOT sum anything.** "That's not how you show the
shape of a curve" (Greg, S75). The gate = **match each forming trade's WHOLE curve to the archetype curve-SHAPES,
with wiggle room** — fire on a winner-shape match, skip on a loser-shape match.
- **THE 8 PIECES ARE 8 DISTINCTIVE CURVE SHAPES — ALWAYS KEPT SEPARATE, NEVER SUMMED (Greg, S75).** Per coin there
  are 8 curve-shape descriptions (4 cells × 2 limbs = short/long × win/lose × pre-fire/tail). Each is its OWN
  distinctive shape; they are never added, averaged, or collapsed together.
- **WHAT IS THE CURVE vs WHAT IS A DERIVED SCALAR (Greg, S75 — the transcription fix):** in a line like
  `short-win y=−0.875+2.117x (x≤0.32, blade +0.963) — −0.903 → +0.123`, the CURVE is `y=−0.875+2.117x` **+ its
  domain `x≤0.32`** (the kink; for the cubic long-win `y=−0.834+2.197x−2.292x²+1.543x³` there is no kink). The
  `blade +0.963` and the `−0.903 → +0.123` (start → peak) are **DERIVED SCALARS — NOT the curve** (the peak is the
  "energy" scalar). Write the equations as `y=f(x)` + domain ONLY; drop blade and start→peak. **Clean SOL ENTER
  shapes (Greg, S75):** short-win `y=−0.875+2.117x, x≤0.32 (then flat)` · short-lose `y=−0.883+2.372x, x≤0.15` ·
  long-win `y=−0.834+2.197x−2.292x²+1.543x³` (cubic) · long-lose `y=−0.883+2.203x, x≤0.15`.
- **⛔ IT DOESN'T MATTER IF THE EQUATION "REACHES" A VALUE — THE SHAPE IS WHAT MATTERS (Greg, S75).** A hockey that
  plateaus below the observed peak still describes the correct SHAPE (steep rise → kink → flat). We match SHAPE;
  the absolute level/endpoint the curve arrives at is NOT the object and is never checked.
- **⭐ TWO WAYS TO MATCH — TEST BOTH (Greg, S75; whole-curve "probably cleaner"):** (1) WHOLE-CURVE = match each
  forming trade's full leg curve (valley→onset→close) to the 4 archetype WHOLE-curves; (2) SPLIT = match the 8
  pre-fire/tail pieces separately. Keep the 4 buckets as distinct reference sets (#0e-GATE, no centroid).
- **⭐ USE BOTH REPRESENTATIONS — THE EQUATIONS AND THE SAMPLED ARCS (Greg, S75).** The archetype curve exists two
  ways: the clean **EQUATION** (`y=f(x)`+domain — the idealized intended shape) and the **SAMPLED ARC**
  (`leg_imbalance_arcs_{coin}.npz` — the true empirical shape as points). **Use BOTH** — if combining them makes the
  gate better, do so; at minimum use one as a CROSS-CHECK on the other (the equation guards against a noisy arc; the
  arc guards against a lossy equation) so the shape is never built incorrectly. Neither is "solved for a number" —
  both are matched as SHAPES.
- **ENTER and EXIT are BOTH shape reads.** Pre-fire (ascension) shape = the entry read; post-fire (tail) shape = the
  exit read. Both matched as SHAPES.
- **⛔ FORBIDDEN (the S75 wrong-frame, do not repeat):** extracting scalar features (peak, blade15, kink, convexity,
  energy) and gating by nearest-anchor / thresholds / z-distance / any "sum" of numbers. That is a SNAPSHOT, not a
  shape (proven wrong on SOL S75: scalar/book-piece nearest-template gates all over-skip winners and lose $/hr).
  Also FORBIDDEN: summing the two book pieces into a net ratio — they are a joint SHAPE read, both must agree.
- Generalizes #0e/#0e-GATE to the mechanism: the signal object is the CURVE, on enter and on exit, matched
  shape-to-shape. CLOSED — do not re-frame the edge as a scalar/AUC/sum again.

## ⭐ EVOLUTION (Greg, S70) — REVIVE `research/strategy_evolution/` (structure good, needs updating)
The hindsight missed-winner audit loop = the "evolution that suggests updates." Structure: replay what the
live system DID (opened/skipped + actual PnL) → oracle = best favorable exit WITHIN each trade's real horizon
→ classify (`missed_entry` / `exit_missed_or_fee_leak` / `not_a_hindsight_winner`) → aggregate the leaks.
UPDATE it to: run through the CURRENT live Kraken executor on RECENT BOOK data; under the locked-firing rule
its ACTIONABLE output is the FILL/exit-leak side (`exit_missed_or_fee_leak` = the capital/fill layer we tune),
while `missed_entry` is REPORT-ONLY for Greg. It SUGGESTS fill/capital-config updates for review — never
self-applies, never changes firing. (Old machinery was Coinbase live-mock on E:; only one doc survived in git.)

---

# ══════════════════════════════════════════════════════════════════════════════════════════
# ✅ LIVE — THE AGREED CURRENT STACK  (authoritative; EVERY change lands HERE immediately)
# ══════════════════════════════════════════════════════════════════════════════════════════
> This section is what is actually running / agreed. **When a strategy is replaced, the OLD line moves to
> the SCRAP HEAP below and the NEW line lands here — immediately, same edit.** Source of truth for firing =
> `odcore/platform.py::KRAKEN` (live code wins). Nothing is "live" unless it is in this section.

**VENUE / FEES:** Kraken US spot. `kr_mk0` = **0bp maker** ($10M/30d tier, treated as real); taker ~5bp fallback.

**FIRING — FIXED per coin** (= `odcore/platform.py::KRAKEN`; detector = flow-lean zigzag `flip_detector.py`
WFLIP=600 / ARM0 natural cadence + early-arm `retime` where eps set. DO NOT touch except on Greg's explicit say-so):

| coin | side | rev | early-arm eps | deep-bail | cover-grace | improve | note |
|---|---|---|---|---|---|---|---|
| eth | +1 fwd | 0.10 | 10 | −100 | 300 | 0.5 | |
| btc | +1 fwd | 0.10 | 5 | −80 | 300 | 0.5 | K=10 |
| sol | +1 | 0.10 | — | — | 300 | 0.5 | ⚠ registry=fwd; tape deploy map=reversed — UNRESOLVED, Greg decides (do not self-change) |
| doge | +1 | 0.30 | — | — | 600 | 0.5 | |
| xrp | +1 | 0.13 | — | — | 300 | 0.5 | |

**⭐⭐ THE ENTRY SHAPE GATE — THE WAY FORWARD (Greg, S73; LIVE direction, TUNING STILL TO DO).** On top of the
LOCKED firing above sits a per-trade ENTRY SELECTION overlay: read each forming trade's PRE-TRADE exhaustion
CURVE SHAPE (the onset ignition arc, per trade, live) and **DON'T FIRE ON THE LOSER SHAPES.** Firing/direction
is untouched (Greg-only) — the gate only decides, for each fire the lean already produced, TAKE or SKIP.
- **The object:** each INDIVIDUAL trade's pre-onset flow-shape arc (signed to side), read PER TRADE. NO
  AVERAGING anywhere (#0d / #0e-GATE), NO AUC/snapshot scalar (#0e) — we match the CURVE.
- **The 4 archetypes** (short/long × winner/loser) are FOUR SEPARATE SETS OF INDIVIDUAL CURVES (never a
  centroid/mean). Match each forming trade to the exact individual curves with WIGGLE ROOM; SKIP if it matches
  a LOSER shape (short-loser AND long-loser), FIRE $5k on the winner shapes.
- **Winners vs losers have VISIBLY different pre-trade shapes** (Greg — "you can just see it"; the regrouped
  arcs `research/shape_s71/regroup2.py` → `kraken_types_regrouped.png` are the reference curves). WINNER =
  starts on-side/above zero, steep rate-of-ascent (hockey-stick BLADE), HIGH onset peak. LOSER = **DIPS BELOW
  ZERO first**, shallower/later ascent, LOW peak.
- **⭐ THE DIFFERENTIATOR = ENERGY GOING INTO THE TRADE (Greg, S73, from the graphs).** The WINNER always
  carries MORE ENERGY into onset — a higher onset PEAK / bigger RISE (peak−start) / a steeper climb to a
  higher level — for BOTH short-wins AND long-wins. The LOSER has less energy (lower peak/rise). SOL measured:
  peak short-win 0.125 vs short-lose 0.014, long-win 0.348 vs long-lose 0.295; rise (energy) 0.217/0.127 short,
  0.577/0.556 long (big gap on shorts, tighter on longs). The SHORT-loser additionally **DIPS BELOW ZERO**
  before the upswing while the short-winner stays above. ⚠ do NOT use the terminal-15s "blade slope" as the
  energy measure — a winner that reaches a HIGHER peak saturates/flattens near onset, so blade-slope reads
  LOWER for the winner (an artifact); use PEAK / RISE, not terminal slope.
- **⛔ SHAPE, NOT NUMERICAL VALUES — NO VOLUME, NO PRICE (Greg, S73 — foundational):** we deliberately do NOT
  use raw volume or price, because both SCALE differently per coin and per regime → constant re-scaling, nothing
  transfers between cells. The signal object is the **normalized imbalance-ratio arc ([−1,1])**, so the CURVE
  SHAPE is scale-invariant and comparable across coins even when absolute activity differs wildly. This is WHY
  shape ≫ numbers. Corollary (the slope conflict): a literal slope/rate SCALAR on the normalized signal reads
  BACKWARDS (loser "steeper") — the "steeper winner ascension" the GRAPH shows IS the winner reaching a HIGHER
  PEAK (a shape/energy property, captured by peak). Read the SHAPE, trust the graph; do not chase a rate scalar.
- **⭐ UNIVERSAL SHAPES, CELL-SPECIFIC NUMBERS (Greg, S73 — the clean architecture, across the 4 majors, NOT
  doge):** the 4 archetype CHARACTERISTICS are COIN-UNIVERSAL — a short-loser is the flat/no-energy/near-zero-
  peak/dips-below-zero one, a long-winner is the highest-energy/steepest/stays-above-zero one, etc., on BTC,
  ETH, SOL, XRP alike. We characterize the 4 cells ONCE. Only the THRESHOLDS are cell-specific: SOL's short-
  loser peak ~0.014 is not BTC's number, but BTC's short-loser is still the flattest/lowest-energy/below-zero
  one of ITS four. Re-fit the numbers per coin; do NOT re-discover the shapes. This is #0d exactly — the shape
  CHARACTERISTICS are the fixed SCAFFOLD (universal), the THRESHOLDS are the TUNABLE numbers (per cell).
- **⛔ WHY PER-CELL (NUMBERS) NEVER LUMPED (Greg, S73 — load-bearing):** the dominant tell's THRESHOLD differs
  by cell AND category (SOL-short split by energy/peak; SOL-long by below-zero dip; each major its OWN numbers).
  LUMP the NUMBERS and you average across different thresholds → signal CANCELS → flat gate (exactly why the
  earlier general/bunched gate came out flat). The SHAPES transfer; the NUMBERS are graded per cell × category.
- **⭐⭐ WHERE WINNER/LOSER DON'T OVERLAP — THE TWO UNIVERSAL WINNER SIGNATURES (Greg, S73 — VERY IMPORTANT,
  load-bearing).** The S73 gate over-skipped because winner/loser shapes OVERLAP in ABSOLUTE level. The
  separation — where they do NOT overlap — is in TWO scale-free signatures that hold in BOTH categories:
  1. **RELATIVE ENERGY:** the winner ALWAYS has MORE ENERGY than its PAIRED loser (short-win > short-lose,
     long-win > long-lose). The within-pair winner>loser energy rule never flips — even though absolute peak
     levels overlap across short/long, the PAIRED comparison separates cleanly.
     **⭐ SOL JUMPING-OFF VALUES (the archetype energy anchors — cell-specific NUMBERS to start from):
     SHORT-WIN 0.125 vs SHORT-LOSE 0.014 (EXTREMELY DISTINCT — ~9×, zero archetype overlap, you know right away
     which is which); LONG-WIN 0.348 vs LONG-LOSE 0.295.** These are SOL's numbers; each other major re-fits its
     OWN (universal shapes, cell-specific numbers). Jump off from these.
  2. **LINEAR vs NON-LINEAR ASCENT:** the winner's ascent is NON-LINEAR / hockey-stick; the loser's is LINEAR
     (straight/flat). Measure via linear-fit R² / convexity vs the start→peak chord (NOT the terminal blade
     slope, which saturates and reads backwards — the S73 miss).
  Gate on THESE (the non-overlap signatures), NOT on an absolute-level midpoint threshold (the overlapping
  middle is exactly what a blunt threshold fails on). This is the S74 build.
- **⭐ CELL-SPECIFIC + CATEGORY-SPECIFIC + SEQUENTIAL (Greg, S73).** Not general rules — each CELL (coin) has
  its OWN characteristics with its OWN thresholds, and each CATEGORY (short/long) its own. The loser gate is a
  SEQUENTIAL cascade: check each characteristic ONE AT A TIME; if the trade's shape shows a loser trait (fails
  a check), SKIP it — it must pass every check to fire. Build the shape in REAL TIME (the causal pre-onset
  limb) for the live comparison. ⭐ SCOPE: these shape rules apply to the **4 MAJORS (BTC/ETH/SOL/XRP)**; **DOGE
  is its OWN thing — EXCLUDED for now**, gets a doge-specific pass next.
- **⭐ RUN LENGTH = the LONG/SHORT axis (Greg, S73).** Both long-winner AND long-loser have LONGER pre-trade
  runs than their short counterparts — more momentum → longer run → bigger ascent (long peaks/rises ~0.3 vs
  short ~0.02–0.12). That's the duration axis; the winner/loser split lives WITHIN each duration.
- **⭐ THE TELLS ARE PER-CATEGORY (Greg, S73 — each pair has its own dominant tell):** SOL measured —
  SHORT-win vs SHORT-lose: the ENERGY/PEAK gap is HUGE (0.125 vs 0.014) and carries it; below-zero barely
  separates. LONG-win vs LONG-lose: the energy gap is TIGHTER (peak 0.348 vs 0.295) but the BELOW-ZERO DIP
  does the separating — the long-loser dips LOWER and spends MORE of its run below zero (ascent-min −0.64 vs
  −0.56; 37% vs 33% below zero), and starts lower (−0.261 vs −0.229). So the LONG-loser IS entry-catchable
  (its own rule: less energy + more below-zero dip) — NOT "entry-invisible" (my earlier call was wrong).
- **⚠ NOT YET TUNED (the work that remains):** per-cell + per-category thresholds and wiggle-room for the tells
  (short-loser: low energy/peak; long-loser: below-zero dip + lower energy), plus the exit/turn read. TUNE
  LATER (Greg) — do NOT get bogged down now.
- **⭐ SHAPE BUILDER = THE ORIGINAL AGENT'S, for LIVE code (Greg, S73 — do NOT build another; his is PERFECT):**
  the live shape is built by the agent's original `research/shape_s71/arc_gate.py` + `regroup2.py` (the
  onset→exhaustion arc extraction + the regrouped reference curves + `quad_means.npz`). Do NOT write a new
  shape builder — REUSE these. The entry gate / selection logic sits ON TOP of that builder.
- **Status (S73, DONE — validated, not yet selective enough):** refined 4-cell cascade run through the LIVE
  `run_kraken_cell` on SOL ($5k/trade, no deep-bail). Loser detection WORKS off the shape (short-loser recall
  75%, long-loser 72%) BUT a midpoint threshold OVER-SKIPS (71% of winners too) because per-trade shapes
  OVERLAP even though the MEANS separate → win% only 61.7→63.3 (OOS 60.8→62.2), $/hr halved, 28% fired.
  Characteristics validated; threshold too blunt. `research/shape_s71/sol_ascent_eq.py` + `sol_loser_gate.py`.
- **⭐ NEXT (S74) — FIND WHERE WINNER/LOSER DON'T OVERLAP, gate ONLY there (Greg):** the shapes separate on the
  MEAN but overlap per-trade, so characterize the NON-OVERLAP regions (loser TAILS where winners never land —
  bottom-decile peak for short-loser, deepest below-zero dips for long-loser, etc.) PER COIN × PER CELL and skip
  only there (fewer skips, near-pure loser → win% lift, keep volume). Plus a NEUTRAL agent to measure pre-onset
  buy/sell BALANCE + the non-overlap regions per coin × per cell (ratio/shape only, no volume/price; NO expected
  outcome passed — a hypothesis is parked in the S73 handoff, keep it OUT of the instructions). Then cell-by-cell
  BTC/ETH/XRP; **doge on its own separate track.** See `SESSION_HANDOFF_2026-07-07_S73.md`.
- **Deep-bail DEMOTES to a thin backstop** once the gate skips the losers (the entry gate does selection +
  loss-avoidance). EXIT = winner-optimization only; the flow-based exit is BUILT as a per-coin TUNING KNOB
  (`balance_exit`, opt-in) — baseline still wins on all 4 majors on the current window, so the current flow-turn +
  cover-grace exit STAYS the default; **re-tune the knob per coin on fresh book and adopt only where it beats that
  coin's baseline** (else stick with baseline). Deep-bail caps the loser price tail. Detailed research record: the
  S72 SHAPE STRATEGY block below.

**⭐⭐ S74 WHOLE-LEG IMBALANCE FINDINGS (2026-07-08) — TRADE IMBALANCE IS THE DECIDER + a UNIVERSAL EXIT TELL +
the BTC BOOK GOLD.** Characterized the 4 cells over WHOLE legs (extended TURN-TO-TURN: valley/birth → onset peak
→ exhaustion at the ACTUAL close, not the −45/+60 clip) through the LIVE `run_kraken_cell`, tracking TWO channels
signed to side — **TRADE imbalance** `(buy−sell)/(buy+sell)` and **BOOK imbalance** `(bidK−askK)/(bidK+askK)`
K1/5/10. Per-cell mean arcs (archetype pictures; Greg-approved for the characterization). Files:
`research/shape_s71/leg_imbalance.py` + `leg_imbalance_findings.md` + `leg_imbalance_{coin}.png` + `fit_shapes.py`
(8 equations/coin). ⚠ CHARACTERIZATION — mean arcs, one book window/coin, NOT yet a per-trade gate / sizing-grade.
- **⭐ TRADE IMBALANCE IS THE DECIDER (Greg's hypothesis — CONFIRMED, and it does MORE):**
  - **DIRECTION** = the trade-imbalance POLARITY. Born maximally AGAINST-side at the valley (~−0.85), FLIPS
    with-side at onset; the SIGN at onset is the buy/sell call (gap **+0.47..+0.72 all 4 coins**). BOOK does NOT
    decide direction (±0.02..0.06).
  - **DURATION** (short vs long) = the onset **PEAK HEIGHT** (long fires from ~+0.33..+0.45 vs short ~+0.13..+0.25,
    all 4 coins). The valley and the pre-fire MEAN carry NO duration/win-lose info.
- **⭐⭐ THE UNIVERSAL EXIT TELL (all 4 coins) — win/lose lives in the TAIL, NOT the entry:** post-onset the
  **WINNER** trade tail decays gently and HOLDS ≥0 to close (exh ≈ 0..+0.1 — the ride de-energizes, flow never
  flips); the **LOSER** tail decays THROUGH zero into strong negative (exh **−0.14..−0.42**) — the flow REVERSES
  onto the other side mid-tail, and THAT reversal IS the loss. Each of the 4 cells has its OWN DISTINCT pre-fire and
  tail curve shape (the §4 equation + the sampled arc); we match each forming leg's curve to those per-cell
  signifiers on enter and exit. **⭐ S74 EXIT KNOB — `balance_exit` is a per-coin TUNING KNOB, opt-in
  (default OFF, canary bit-identical; `research/shape_s71/exit_test_findings.md` + `exit_balance_grid.py`).** The exit
  tool (close at the flow zero-cross / return-to-balance) is BUILT + wired LIVE and TUNES PER COIN — **this is the
  fine-tuning stage, still a win, NOT a dead end.** On the CURRENT window baseline still wins on all 4 majors (best
  config vs baseline: SOL +8.44 vs +11.26, BTC −2.91 vs +2.49, ETH +0.31 vs +5.47, XRP +0.94 vs +2.47; full
  arm{0.05–0.40}×window{20/40/60s}×exit_lo{+0.10..−0.20} grid). **RULE: tune the knob PER COIN on fresh book; adopt it
  only where a coin's tuned config BEATS its baseline — where baseline still wins, STICK WITH BASELINE** (current
  flow-turn + cover-grace exit). WHY baseline wins so far: (1) the flip-turn exit is already at the trade's 60s WFLIP
  scale (subsumes the knob); (2) **FLOW LAGS PRICE** — winners' flow returns to ~0 while their PRICE gain holds to
  the later price turn (exiting hands back 15–25% winner $/hr), losers' loss already booked in price by the time flow
  rebalances. The bigger win/lose lever is ENTRY; deep-bail caps the loser PRICE tail. **⭐ Greg: the per-cell
  EQUATIONS (pre-fire + tail, `leg_imbalance_findings.md` §4) may be the winning part — pursue next.**
- **⭐⭐ BTC BOOK = A PRE-FIRE WIN/LOSE FORECAST (Greg: "could be worth its weight in gold") — COIN-SPECIFIC:** on
  **BTC** the BOOK imbalance forecasts win/lose BEFORE the leg fires — winners born book-POSITIVE (with-side) and
  stay positive valley→peak→close (short-win peak +0.13, long-win +0.20), losers born book-NEGATIVE and stay
  negative the whole leg (short-lose −0.25/−0.39, long-lose −0.10/−0.19); K1/5/10 all agree, and the born-book sign
  already forecasts win/lose AT the valley (pre-ignition). This is a genuine **PRE-FIRE ENTRY tell on BTC** — a
  second, book-based signifier stacked on the per-cell pre-fire curve-shape match. ⚠ **NOT universal:** FLAT on
  SOL (±0.03 — book carries nothing, TRADE is the whole story there), WEAK on ETH, LONG-WIN-only on XRP. Book NEVER
  FLIPS at the peak on any coin — it is a standing LEAN (context), not a turn-timed signal; the turn tell lives in
  the TRADE channel. **NEXT (BTC): build + validate the BTC book pre-fire lean as a BTC entry gate, confirm OOS / on
  fresh book.**
- **Endpoint map:** TRADE valley NEVER separates (universal birth ~−0.85..−0.91); TRADE **exhaustion (close)** is
  the cleanest universal win/lose separator; TRADE **peak** = duration. 8 distinct equations/coin (pre-fire + tail
  per cell, split at the fire) in `leg_imbalance_findings.md` §4 — each cell's pre-fire and TAIL curve is its own
  distinct shape (win tail flattens near 0; lose tail declines through 0 to negative).
- **⛔ CORRECTION to S73:** the S73 "LINEAR vs NON-LINEAR ascent" prime discriminator is **FALSE** — all 4 cells are
  convex hockey sticks; linearity does not separate winner from loser. The real per-trade edge is NOT in the entry
  shape at all — it is in the TAIL (exit) + (BTC only) the book pre-fire lean.

**⭐ S74 ENTRY-ENERGY GATE (2026-07-08) — energy gate is GOOD on BTC/ETH/XRP, the SOL failure was SOL-SPECIFIC.**
Tested the 4 cell ENERGY (onset peak) values as a standalone entry gate through the LIVE code (4 anchors, wiggle):
it roughly **DOUBLES $/hr on BTC (2.5→6.08), ETH (5.47→6.40), XRP (2.47→5.18)** but HURTS SOL (11.26→10.08 — SOL
winner/loser energy LEVELS overlap so it over-skips ~40% of winners). On SOL a cumulative deep-hole skip
(`late_integral` lowest ~5%) beats it (11.43 > ungated 11.26 > energy 10.08). All IN-SAMPLE. Files
`research/shape_s71/sol_loser_gate.py` / `gate3.py`. Reconciles the S73 "energy over-skips" result: it over-skips
only on SOL; on the other 3 majors the energy gate is strongly $/hr-positive and should be kept.

**⭐⭐ S74 → S75: THE WHOLE-CURVE SHAPE-MATCH GATE (Greg: "if they're distinct, that's the gate") — the #1 UNTESTED
test. SHAPE MATCH, not equation-solving (#0f).** We have 8 distinctive per-cell CURVE SHAPES (pre-fire + tail;
`leg_imbalance_findings.md` §4) — kept SEPARATE, NEVER summed. The gate = **match each forming trade's WHOLE curve
to the archetype curve-SHAPES** (nearest actual curve = the SAMPLED ARC `leg_imbalance_arcs_{coin}.npz`, NO centroid
= #0e-GATE), fire winner-shape / skip loser-shape, through LIVE `run_kraken_cell`. **TEST BOTH WAYS (Greg, S75):**
(1) WHOLE-CURVE (full leg valley→onset→close vs the 4 archetype whole-curves — "probably cleaner"); (2) SPLIT (the
8 pre-fire/tail pieces separately). We tested ENERGY + single scalar features alone (overlap, WRONG frame #0f) but
NEVER the whole-curve SHAPE match — the untested piece. ⚠ honest note: enter = the pre-fire shape, exit = the tail
shape; the tail shapes are the more distinct ones. Reference = the sampled ARCS (curve-as-points), not the lossy
hand-written equations. Grade vs ungated + vs energy.

**⛔⛔ S75 RESULT — THE SHAPE GATE WAS RUN ON SOL; IT HIT THE DIRECTION WALL. SOL IS DONE. (2026-07-08/09; full
detail `SESSION_HANDOFF_2026-07-09_S75.md`; code `research/shape_s71/sol_gate_run.py`.)** The whole-curve shape gate
was BUILT + run LIVE on SOL (raw curve, NO normalize/average/smooth; arcs + equations; opt-in `entry_gate` socket
added to `run_stream`/`run_kraken_cell`, bit-identical default). **Every entry variant lands at ~62% win / below
ungated $/hr** (arc 59.6/$6.68 · eq 59.6/$6.68 · eqpeak 49.0/$2.95 · ungated 61.7/$11.26). **WHY (load-bearing,
reproduces S62): WIN/LOSE IS DIRECTION.** The `flip` test — reverse the side of SOL's losers — turns **82% of
long-losers / 87% of short-losers into WINNERS** ($/hr 11.26 → 41.88 reverse-all HINDSIGHT ceiling). So a winner and
its "loser" twin have the **IDENTICAL entry** → no entry feature (shape/peak/dipole/book) can separate them → **~62%
is the detector's direction hit-rate, a HARD CEILING on entry filtering.** Direction is un-callable at entry (SOL
book FLAT; dipole ~chance, all classes ~61%) AND mid-trade (flow-turn flip is a WASH — breaks ~as many winners as it
rescues = winners-invisible) AND un-flip-on-distance (SOL barely moves: only 34/1522 legs reach 15 bps adverse, ZERO
reach 30). **SOL is a small-band, mean-reverting, SPREAD-CAPTURE coin** (mid-price ride is −5.2/hr; the +11.26 edge is
spread). ⭐ **SOL VERDICT: capped at ~62% / +11.26 $/hr, near its ceiling — the edge is the deployed spread capture;
STOP fighting SOL.** (⚠ `losscap` mode is BUGGY — bail identical across depths; fix before use.)

**⭐⭐ S75 THE REAL EDGE — THE BOOK EARLY-SIGNAL (direction; Greg drop-in `early_signal.py` + `early_signal_kraken.py`).**
Proximity-weighted top-K book depth imbalance → MAGNITUDE (entry filter) + SIGN (direction); `fit_direction_sign()`
fits the sign per venue×cell. Fit on OUR Kraken books (100ms→1s, horizon 60s, min_conv 0.5): **BTC sign +1, 71.4%
directional hit at 60s on strong leans (n=83k) = HIGH ⭐; ETH +1 ~55% HIGH-ish; XRP +1 ~56% LOW; SOL FLAT (n=27=noise);
DOGE −1 flat.** Confirms Greg's ranking (BTC/ETH biggest, SOL smallest). **The book gives DIRECTION on BTC/ETH that
SOL never had — the piece that breaks the 62% wall on those coins.** Re-fit `direction_sign` per venue×cell.

**⭐ S76 NEXT — BTC + ETH TOGETHER (Greg): shape gate WITH FALLBACKS + the book direction stack + ride-to-reversal
exit, ~60s horizon.** REBUILD the per-cell archetypes on BTC/ETH (SOL's were the wrong coin). Stack the book
`direction_sign` (HIGH on BTC/ETH). Exit = wide (~30 bps) trailing ride-to-reversal (the paper's first net-positive
config). Validate multi-window (0% maker floor — Kraken $10M tier / Coinbase Liquidity Program). Full plan:
`BTC_SIGNAL_SESSION_2026-07-08.md` (Greg's paper) + `SESSION_HANDOFF_2026-07-09_S75.md`.

**⭐ THE LEVER STACK (Greg, S74 — LARGELY INDEPENDENT levers → they COMPOUND; validate each, then STACK; S64
"tools are complementary, not competing").** ENTRY selection: whole-curve equation gate + ENERGY gate (doubles $/hr
BTC/ETH/XRP, SOL=deep-hole) + BTC BOOK pre-fire tell. RISK control: long-duration cap / deep-bail (the worst-loser
bleed is LONG legs — `worst_losers_S74.md`; SOL has NO deep-bail). EXIT tuning: `balance_exit` per coin where it
beats baseline. FOUNDATION: TRADE imbalance = the real-time direction+duration decider. ⚠ several are in-sample/
untested — each needs its own validation FIRST, then they stack → "a lot of improvement" (Greg).

**⭐ THE GREEDY CAPITAL STRATEGY — LOCKED (Greg, S70; stop rehashing — this is settled).** In plain words,
this is exactly what `odcore/allocator.py` (`mode="greedy"`) + `odcore/platform.py::run_portfolio` do (LIVE,
canary-clean). Do NOT re-derive or re-litigate it; only IMPLEMENT/tune the inputs it names.

1. **ONE $5k bank = the entire stack** (not per-coin, not per-sleeve). The goal is to keep that $5k **in play
   as close to 100% of the time as possible.**
2. **Fund the BEST performer FIRST.** "Best" = highest **edge per dollar** ($/hr per $ deployed). Rank all
   seated coins by it every allocation.
3. **Give the best coin as much as it can take** — bounded by TWO things: (a) our **free capital** in the $5k,
   and (b) that coin's **counterparty capacity** = how much its book actually absorbs our front-of-line maker
   order (i.e. how much the counter actually trades against us). If the best coin can absorb the full $5k
   (e.g. BTC can), it **gets the full $5k — concentration on the best is FINE. We do NOT force-spread.**
4. **Cascade the leftover.** Whatever the best coin can't take (capital it couldn't absorb / we still have free)
   goes to the **next-best performer**, then the next, and so on **until the $5k is deployed.** Example (Greg):
   we have $2500 to place and the counter on that coin only trades $1000 worth → we fill $1000 there and the
   remaining $1500 cascades to the next coin.
5. **Positions are per-coin and INDEPENDENT, mixed direction.** We can be **short BTC and long SOL at the same
   time** — nothing forces the whole book to one side. Multiple concurrent positions is the NORMAL state; that
   is how the $5k stays full.
6. **Never DROP a coin** — every coin stays seated and available. **"Never fund negative edge" is a WRONG rule
   (Greg, S70; tested repeatedly).** Average edge is backward-looking and does NOT predict a trade's win/lose
   (direction is unpredictable — closed 4 ways), so it does NOT gate a coin out and we do NOT idle capital to
   dodge a negative-average coin. Edge sets the funding ORDER (best first); it never excludes. Keep the $5k
   deployed to stay ~100% in play.
7. **Always FRONT-OF-LINE maker** (`fill_model="front"` + enticing close `swing_maker.close_improve_bps`=0.5/coin):
   post the best bid/offer so we are first in line.
8. **Breadth is the fuel.** More seated coins (majors + the 16 minors + the small-cap sleeve) = more concurrent
   fill opportunities = the $5k stays deployed. Thin books each take small size; that is why we need many coins.

**The ONLY tuning surface on this** = the INPUTS greedy consumes: per-coin **counterparty capacity** (from the
live BOOK DEPTH — the resting bid/ask sizes, NOT trade volume) and the **edge-per-$ ranking** (order only, never
a gate). Firing is untouched. ⚠ the allocator CODE currently skips non-positive edge — that must be removed
(fund to keep the $5k deployed), the concrete code change for the greedy test.

**EXECUTOR / PLATFORM (the live decision path — ALL tests run through this):**
- `odcore/swing_maker.py` — the one executor (maker-at-the-turn, cover_grace, exit_spec deep-bail, front fill, fees).
- `odcore/platform.py` — `run_kraken_cell` / `run_stream` / `run_portfolio`; `KRAKEN` registry.
- `odcore/flip_detector.py` (signal) · `odcore/incremental.py` RollingFlow (hot path) · `odcore/leakage.py` +
  `odcore/validation.py` (MANDATORY gates).

**DATA (book = fills, tape = plumbing only):**
- Book collectors LIVE: 5 majors (`data/{btc,eth,sol,xrp,doge}-kraken-book`, 6h cron) + 16 candidate minors
  accruing (`kraken_candidate_book_collectors_durable.yml`, S70). Price/tune the fill on RECENT book.
- `backfill_kraken_trades.py` (tape) = structure/plumbing ONLY — never a pricing/capacity source.

**MINORS / SMALL-CAPS (capacity breadth for the $5k):**
- 16 LARGE candidates (HYPE·SUI·ADA·ZEC·XMR·AVAX·XLM·AAVE·LTC·NEAR·TAO·LINK·BCH·BNB·TON·XPL) — SEATED, books
  accruing; grade **on BOOK** when deep, then apply the GENERAL stack. Never graded on tape.
- ~116 THIN-OK −2bp small-cap sleeve — future capacity.

**EVOLUTION (the adjustment mechanism — revive `research/strategy_evolution/`):** hindsight missed-winner audit
through the live executor on recent book → surfaces `exit_missed_or_fee_leak` (the fill layer) → SUGGESTS
fill/capital-config updates for Greg's review. Never self-applies; never changes firing.

---

# ══════════════════════════════════════════════════════════════════════════════════════════
# 🗑️ SCRAP HEAP — NOT LIVE  (dead / parked / replaced / research + the full session history)
# ══════════════════════════════════════════════════════════════════════════════════════════
> **NOTHING below this line runs.** It is the archive: retired strategies, parked venues, research threads,
> and the session-by-session log. Kept so we never re-run a dead experiment or re-derive a solved thing.
> See the LIVE section ABOVE for what is actually running. When something here gets promoted, it moves UP to
> LIVE (and whatever it replaces moves down here) — in the same edit.
>
> Explicitly in the scrap heap (not live, do not reach for): `queue`/back-of-line fill (we are always
> front-of-line) · `capacity.py`-on-TAPE as a capacity source (S69 dead end) · tape-grading as a pricing
> path · Coinbase (parked) · Bybit/MEXC (banned) · every family/tool tagged dead/parked/research below.

## ⭐⭐ S72 — THE SHAPE STRATEGY (Greg: "this SHOULD be the build" — RECORD IT; NEEDS REFINEMENT FIRST, do NOT deploy yet)
> Greg, S72: this is the direction. Read the **INDIVIDUAL trade's flow SHAPE** (the onset→exhaustion arc), never an
> averaged scalar. The **whole ballgame reads off ONE live curve.** Recorded here as THE intended build; it needs
> refinement (per-cell OOS validation + the exit turn-definition + the ascent algebra) BEFORE it goes live. Direction/
> firing stays LOCKED (Greg-only) — the shape is the **selection + exit OVERLAY**, i.e. the tunable surface, not a
> firing change. Artifacts: `research/shape_s71/` (arcs, `quad_means.npz`, doge_only), `research/exit_s72/`
> (`exhaustion_price_exit.py`, `EXIT_EXHAUSTION_FINDINGS_S72.md`), `SIGNAL_SHAPE_DIRECTION_S71.md` (+ S72 no-averaging correction).

- **THE OBJECT — individual trade flow shape, NO averaging.** Each trade's with-trade flow arc (`imb_signed×side`
  over the pre-onset→exhaustion window). We read/classify EACH trade's own curve. The `quad_means` archetype arcs
  (all-coin, doge-separate) are a PICTURE of the archetype ONLY — never the signal, never the grader. Averaging
  destroys the per-trade shape; a flat pooled scalar is the averaging error, not a null. (S72 hard rule, Greg.)
- **THE 2×2 ARCHETYPES = duration × outcome.** short/long (TIME the trade lasts) × winner/loser. 4 shapes, same
  landmarks, different NUMBERS per cell (doge = same shape, own scale → same detector, own thresholds). DIRECTION is
  NOT in these (it's normalized out by signing to the trade's side).
- **WHOLE BALLGAME off the one curve:**
  - **DIRECTION** = peak→SELL / valley→BUY (the lean/zigzag turn type; not a prediction; LOCKED/unchanged). Doesn't
    collide with "direction is dead" — we react to a peak/valley, we don't guess price.
  - **ENTRY QUALITY (fire / skip)** = the pre-onset ASCENSION shape. WINNER = starts on-side (≥0), climbs early,
    **HOCKEY-STICK** (flat handle → steep LATE blade), tops HIGH. LOSER = **dips below zero first**, gradual rounded
    rise, low peak. **Rate-of-ascent (the blade) is the headline pre-fire tell**; peak height + start-above/below-zero
    corroborate. Skip predicted losers = **the biggest prize** (this is the QUALITY axis, NOT direction — the
    closed-4-ways rule does not apply to it).
  - **DURATION (short/long ride)** = ascent morphology (extended accelerating build → long ride; abrupt spike → short).
  - **EXIT** = the exhaustion limb — the exhaustion **FLATTEN** (velocity→0, "no more movement") / price-turn-aligned;
    get off before the crowd. (Zero-CROSSING is only a loose clock — the FLATTEN is the stronger candidate.)
- **ENTRY CLASSIFIER (to build):** per-trade fit the ascension to an **algebraic ascent equation** (slope/curvature —
  dipole-style algebra) + **peak height**; fire only if inside the **WINNER BAND** = archetype mean ± **WIGGLE ROOM**.
  Build per-cell reference shape-graphs; match each forming pre-trade shape with tolerance. Validate per-cell OOS +
  shuffle-null THROUGH the live executor before wiring.
- **EXIT (in refinement):** align on each trade's ACTUAL price peak/valley (first real price REVERSAL ≥θ, duration-
  invariant — NOT a max-over-window), read the exhaustion signature THERE; find the consistent exhaustion value/flatten
  that marks the turn across duration buckets.
- **S72 EVIDENCE so far:** the pre-onset **CURVE SHAPE separates winners from losers per trade** on all 5 cells
  (S71; a rough one-off logistic check scored OOS ~0.60–0.70 with shuffle-z 1.8–2.6 — that scalar is ONLY a
  "shape-carries-information" sanity check per #0e, NOT the signal/metric/deploy basis; the edge is the CURVE). Exit **clipping confirmed** — 65–69% of winner tops land past +120s; the +120s window cost a median
  **+4.6 (btc)…+11.3 (doge) bps**, p90 up to 34 (600s captures them). The **+20 arc jump = a smoothing-window artifact**
  of the onset volume climax (it moves 10→+10 / 20→+20 / 30→+30 with `SMOOTH_SEC`), NOT a turn — informational only.
  Flow-exhaustion (~60s) vs the 600s-argmax "top" (~250s): the argmax is the WRONG turn (catches later swings).
  **EXIT/TURN read = NULL on the sparse Kraken trade-flow (S72):** the peak-to-valley test (segment by the price's
  own zigzag peaks/valleys; `peak_valley_exhaustion.py`) shows the 20s trade-imbalance exhaustion does NOT mark,
  lead, or predict the price turns — P(spent|turn)≈coin-flip, flow-flip LAGS, not specific, corr≈+0.1, 4 groups
  don't separate — ROOT CAUSE: Kraken trades too sparse (~1.7%→0.2% of cells) so `rolling_imb(20s)` saturates to
  a ±1 square wave (data-resolution limit, not "exhaustion is meaningless"). ⇒ the ENTRY-QUALITY half is the
  ready prize; the EXIT/turn read needs a DENSER/aggregated tape or a BOOK-DEPTH-pressure proxy (both UNTESTED).
- **⚠ REFINEMENT REQUIRED before deploy (Greg — this is the build, but not yet):** (1) per-cell OOS + shuffle-null of
  the ascent-algebra entry classifier through the LIVE executor; (2) direction stays on the lean, firing Greg-only;
  (3) NO averaging anywhere in the live path; (4) per-cell numbers (same shape, own thresholds, own wiggle room).
- **⭐ GREG'S S72 CLOSING REFRAME (simplification):** the entry gate does DOUBLE DUTY — **selection AND loss-avoidance**
  — so **DEEP-BAIL is DEMOTED to a thin backstop** (we don't fire the losers it was there to cap; keep it only because
  the shape gate is not perfect — some predicted-winner curves still turn out losers). The exit hunt was ONLY ever **exiting WINNERS at their top** (optimization,
  not survival), so the S72 exhaustion-top NULL costs little — worst case ride the winner and exit on the CURRENT
  running logic (detector's next flow turn / cover-grace). Net ballgame: DIRECTION (peak/valley, locked) → ENTRY
  (fire only predicted-winner shapes = the prize, also kills loss-mgmt exits) → EXIT (winner-optimization only; current
  logic is the fine default; the exhaustion-top read needs a DENSER tape / BOOK-DEPTH proxy to improve — both untested).

## ⭐ S67 IN-PROGRESS (2026-07-06, live) — THE CAPITAL MODEL (v1 built, canary PASS) + overlooked-majors sweep
> Greg's S67 landing (S66): keep the per-coin EDGE; make capacity a VARIABLE SIZE cap (not $5k/trade);
> build the shared-POOL allocator on the LIVE path. Design LOCKED (Greg): MAJORS-FIRST (5 + agent's LARGE
> candidates as ungraded seats; thin sleeve stays a parallel data track); POOL=$5k shared; capacity
> granularity = PER-COIN position cap (an explicit JUMP-OFF scaffold — swappable `caps` dict migrates to
> per-LEG later w/o touching the allocator; the cap is a SIZE scale, NEVER an inclusion gate — a thin-cap
> coin gets small size, never dropped); fee = the $10M tier treated as REAL (majors 0bp, carried as the
> per-cell maker_fee param so a pre-$10M adjustment is a value change, not a rewrite).
- **Branch reconciled** (recurring wrong-parent bug): designated `claude/davisai-s67-capital-model-0mhh4j`
  was cut from a stale S59 parent; `reset --hard` to canonical S67 tip `0e688fb`. Dropped only a superseded
  `book_collector_btc.yml`; all Kraken collectors + paper cron intact on canonical.
- **⭐ CAPITAL MODEL BUILT (v1) — 3 additive pieces, existing live path byte-untouched:**
  - `odcore/allocator.py` (NEW): `allocate(demands,caps,pool,weights,clusters,cluster_caps)` = weighted
    WATER-FILL under 3 caps in priority (per-key capacity → cluster/correlation → pool). Proportional by
    return-on-capacity so best edge-per-$ funds first when the pool binds, but NOBODY is excluded (Greg's
    rule). + `pnl_correlation`/`cluster_by_corr` (union-find) promoted from basket_sim's ad-hoc corrcoef.
    6/6 sanity tests pass (unconstrained, cap-binds-thin-not-excluded, pool-binds-weighted-proportional,
    cluster-cap, corr-cluster, equal-weight fallback).
  - `odcore/platform.py::run_portfolio` (NEW, additive — run_cell/run_stream/run_kraken_cell untouched):
    event-driven shared-pool replay OVER per-cell legs (never re-decides a trade; sim=live). Closes free
    capital before opens at each cell; a batch opening competes for REMAINING pool via `allocate`; a held
    leg isn't resized mid-hold nor preempted (realistic; v1 simplification). Leg PnL realizes on the
    notional it held: `net_bps/1e4 * alloc`. Returns `PortfolioResult` (POOL RETURN, per-coin funded%/
    realized, pool Sharpe, utilization/idle).
  - `scripts/portfolio_sim_kraken.py` (NEW sim; only adds tape I/O + cap/weight/cluster construction):
    loads realbins Kraken tape, LIVE `run_kraken_cell` → legs, `capacity.py` per-coin caps (S66 whole-hold
    + price-eligible), return-on-capacity weights, corr clusters, `run_portfolio` over $5k. Reports POOL
    RETURN vs the acknowledged-WRONG sum-@-$5k-each framing.
- **⭐ CANARY PASS (load-bearing):** `--canary` proves `run_portfolio(pool=inf, cap=$5k/coin)` reproduces
  basket_sim's sum-of-cells **bit-for-bit** (|diff|=0.00e+00; eth +5744.24 / btc +5374.06 / total
  +11118.3043) → the capital model sits ON the proven per-cell path; "allocator off" == today's numbers.
- **FIRST NUMBER (BTC+ETH Kraken tape, 677h/27.7d, front-of-line, $10M-tier 0bp — PROVISIONAL 2-coin):**
  one **$5k shared pool** capacity-capped (ETH cap ~$1.3k, BTC ~$4.0k) earns **+8.11 $/hr = +0.162%/hr**,
  pool util mean 89%/peak 100%/idle 1%, Sharpe/bucket +0.48, BTC/ETH PnL-corr just 0.10. Contrast the
  WRONG framing (sum @ $5k each = +16.4 $/hr but on $10k of capital, crediting $5k fills BTC's ~$4k book
  can't absorb). Per-$ rate nearly identical (0.162 vs 0.164 %/hr) because near-zero corr + idle capacity
  → $5k shared ≈ as efficient as $10k split (the anti-resting/diversification benefit, architect §1.5).
- **⭐ OVERLOOKED-MAJORS SWEEP DONE** (`KRAKEN_MAJORS_SWEEP_S67.md`, agent): fee gate is a NON-ISSUE (all
  liquid majors share the majors' 0bp-at-$10M schedule; HYPE/XPL better at −2bp). Real gate = LIQUIDITY,
  and name≠Kraken depth (DOT/ATOM/ARB/OP thin; MATIC/MKR no USD pair). LARGE-band candidate cells:
  HYPE·SUI·ADA·ZEC·XMR·AVAX·XLM·AAVE·LTC·NEAR·TAO·LINK·BCH·BNB·TON(+XPL). ⚠ liquidity ≠ edge (HYPE was the
  S64 NULL) — each needs a per-cell grade before it's a cell. ⚠ 0bp assumes we HOLD the $10M/30d tier.
- **⭐ FULL ROSTER RUN + CANDIDATE GRADES (S67, 14d Kraken tape):** pulled sol/xrp/doge/ada/sui/ltc/avax
  Kraken tape (`backfill_kraken_trades.py --days 14`; majors 28d already on box). New grading harness
  `scripts/grade_coin_kraken.py` = per-cell S54 gate for a NEW coin (forward-vs-reversed + circular-shift
  NULL floor + per-window sign consistency + REV sweep; LIVE run_stream, front-of-line, kr_mk0). Grades
  of the agent's 4 candidate majors (deep book ≠ edge — the per-cell law):
  **LTC=SEAT** (rev-side, REV0.30, +3.33 $/hr, 86% windows, clears floor) · **AVAX=MARGINAL** (+3.37 but
  57% windows, barely over floor) · **ADA=MARGINAL** (+1.88, BELOW its own null floor +2.41) · **SUI=REJECT**
  (−2.30, 43% windows — 2nd-deepest book, no mean-reversion edge). Registries added (additive):
  `platform.KRAKEN_CANDIDATES` (LTC) + `KRAKEN_CANDIDATES_MARGINAL` (AVAX/ADA); `portfolio_sim_kraken
  --seats {majors,graded,all}`. CANARY still PASS on the 6-cell roster.
- **⭐⭐ THE POOL-BOUND FINDING (load-bearing — reframes "backup capacity"):** at a FIXED $5k pool the 5
  majors ALREADY SATURATE it (98% util, 0% idle) → adding coins DILUTES the strong ones, LOWERING pool
  return: majors +5.98 → +LTC +5.40 → +LTC/AVAX/ADA +5.11 $/hr (backups cannibalize BTC/ETH allocation +
  XRP is a drag −0.68/hr, negative-edge on 14d tape, echoing S63 "XRP aside on tape"). Backup capacity
  pays ONLY when the POOL GROWS to match: at $10k, +LTC ADDS (+11.04 vs +10.86 majors). Per-$ return is
  ~flat 0.11%/hr until over-provisioned (all@$15k → 0.079%/hr, 73% util). **⇒ backup coins buy POOL
  HEADROOM (capacity to deploy MORE), not per-$ edge; best per-$ config is majors-only; XRP tape-grade is
  a review flag.** (⚠ 14d window, tape-proxy capacity, front-of-line — structure not sizing-grade.)
- **⭐ GREG'S REFRAME (load-bearing, end of S67):** the **$5k is the ENTIRE stack**, not per-sleeve — the
  per-coin $5k slice was always the temp tuning artifact. The job = **best deployment of ONE $5k for max
  profit/hr**. Rules: (a) **fill the best edge-per-$ coin FIRST** (greedy, not spread); (b) **never DROP a
  coin — idle costs nothing**, every coin stays seated & available, the allocator just doesn't fund it when
  its edge is negative or better coins fill the pool; (c) don't fund negative-edge (idle > a losing trade).
- **⭐ XRP REFIGURED (Greg was right):** −0.68 was a **book-overfit CONFIG**, not a bad coin. `grade_coin_kraken`
  on 14d tape: XRP wants **REVERSED, REV0.20 → +2.61 $/hr** (registry had FORWARD; that's the S63 "XRP aside/
  reversed on tape" signal; last night's +16 was the 30h book). Applied as a sim-only `GRADED_OVERRIDE`
  (live registry untouched). Re-grade of all 5 majors on 14d tape: BTC FWD0.10 +5.10 SEAT · ETH FWD0.13
  +5.89 SEAT · SOL/XRP/DOGE MARGINAL (positive with right config, below null floor on this window).
- **⭐ GREEDY ALLOCATOR built** (`allocator.allocate(mode="greedy")`, now DEFAULT; `run_portfolio(mode=)`):
  ranks seated coins by edge-per-$, fills the best to its cap first, then next, until $5k spent; **skips
  non-positive edge (idle beats a loser); never drops a coin**. `portfolio_sim_kraken --seats all --mode
  greedy` = 9 coins seated (5 majors + LTC + AVAX/ADA/SUI backups), XRP fixed. CANARY still PASS bit-for-bit.
  ⚠ **OPEN (the real "best deployment" work, next session):** per-batch greedy funds THINNER coins during
  BTC/ETH's idle windows and some lose on this 14d window (no preemption; idle-vs-deploy threshold unset) →
  pool +5.37/hr @ $5k, ~flat vs proportional. Tuning the idle-vs-deploy / preemption / per-coin exposure cap
  is the next lever. Numbers PROVISIONAL (14d tape-proxy capacity, front-of-line; not sizing-grade).
- **✅ $10M-TIER VOLUME (Greg's Q, answered):** based on the 5 majors' tape, our capacity-capped $5k pool
  trades **~$49M notional over 13.8d** (12,295 funded legs, open+close) = ~$3.5M/day → **~$106M/30d, crosses
  $10M in ~2.8 days**. The 0bp/−2bp tier is SELF-SUSTAINING once running (churn ≈ 10× the threshold even at
  $5k); the only cost is the pre-$10M RAMP (~first 3d at higher maker fee) = Greg's deferred "pre-10M" adjust.
- **⭐ NEXT (S68):** (0) **TUNE ALL 4 CANDIDATE MAJORS** (Greg — ADA/SUI/AVAX/LTC: don't accept the base grade;
  finer REV grid + eps/bail + side re-confirm via grade_coin_kraken before final seating); (1) **TUNE THE BEST
  $5k DEPLOYMENT** — idle-vs-deploy threshold (don't fund thin coins
  just because majors are between legs unless edge clears a bar), optional preemption / per-coin exposure cap,
  edge-weight source (tape vs book); confirm LTC + the marginal configs on a longer window; (2) **SMALL-CAP
  STRATEGY** (Greg's 3rd ask — the ~116 THIN-OK −2bp sleeve: rebate economics, queue-honest fill, per-cell
  grade via `grade_coin_kraken`; architect S1–S3 thin proof); (3) later: per-LEG cap swap; pin capacity on the
  Kraken BOOK; wire run_portfolio to the paper cron. Restart eligible-alt collection (thin track).

---

## ⭐ S66 IN-PROGRESS (2026-07-06, live) — the pre-capital-model gating work + the BIG small-cap data pull
> Greg's S66 reorder (load-bearing): the capital model is BLOCKED — we CANNOT build it until (a) all the
> proposed improvement tests are run per-cell on **majors AND small caps** (E300, bigline, S42 direction,
> divergence-filter, etc.), and (b) the **small-cap coins are actually figured out** (we've only ever worked
> the majors sleeve). So S66 = complete the per-cell test matrix + build out the small-cap sleeve FIRST.
- **Branch reconciled:** `claude/davisai-s66-kickoff-4kjp87` was cut from a stale S59-infra parent; reset --hard
  to canonical S65 tip `5a2b537` (the recurring wrong-parent bug). Origin matches. Dropped only a stale
  `book_collector_btc.yml` infra variant (superseded on canonical).
- **⚠ MISSING agent reads (S65):** only TWO coverage audits landed (`PIECES_TEST_execution_kraken.md`,
  `PIECES_TEST_dipole.md`). The **dipole-EXPERT deep read** and the **ARCHITECT read** never landed — TODO.
- **E300 death-selector on DOGE/XRP (Greg's directive):** RUN. Runs on Binance-vision 30d bins (`/tmp/backfill`,
  the S62 substrate) — **Binance preview:** DOGE AUC **0.685**, base +0.63 → 3piece +1.32 (**Δ+0.69**, 4/5 wk+);
  XRP AUC **0.768**, base +1.10 → 3piece +3.08 (**Δ+1.98**, 4/5 wk+). Matches S62's 0.69–0.77. Driver:
  `scripts/_s66_e300_run.py {binance|kraken}` (drives `_s62_e300_3piece` unmodified — sim=live rule). **Kraken
  re-run in progress** (waits on the XDG/XRP tape) — that is the deploy-grade number.
- **⭐ BINANCE ≠ KRAKEN for deploy (the answer to Greg's Q):** Binance is a fast SIGNAL-EXISTENCE proxy for
  MAJORS only (prices arb'd, lag-0 synchrony) — good for "does depth@300 predict death (AUC)". It is NOT the
  deploy $/hr (fee kr_mk0=0bp, fill, spread, liquidity are Kraken-specific → grade on Kraken tape). For SMALL
  CAPS Binance is useless: most eligibles (XDC/SHX/AIOZ/GWEI/NIGHT/HYPE) are **404 on Binance** and the edge is
  Kraken low-liq microstructure. **⇒ all deploy-grade tests must run on Kraken tape.**
- **⭐ DATA REALITY fixed (no 30d wait):** Kraken REST `Trades` gives HISTORICAL 30–120d NOW.
  - Majors: BTC+ETH already have **27.7d** Kraken tape on box (`realbins/{btc,eth}_kraken_bins.json`,
    2026-06-08→07-06). SOL/XRP/DOGE 30d pulling (`/tmp/ktape`, higher volume ~20–40min).
  - **Small caps are SECONDS each** (XDCUSD 30d = 34k trades = 4s) → deep history is cheap.
  - **⭐ THE ELIGIBLE UNIVERSE IS 352, NOT 6:** Kraken has **352 rebate-eligible (maker_deep = −2bp) USD alt
    pairs** (`/tmp/eligible_pairs.txt`), not the S64 shortlist of ~6. Greg: "bigger sample of them."
  - **⭐ LIQUIDITY-BANDED (Greg: "some of the small caps are actually large"; `KRAKEN_ELIGIBLE_LIQUIDITY_S66.md`,
    24h Ticker):** eligible ≠ small — the 352 span the whole range. Bands: **LARGE >$1M/24h = 5** (HYPE $8.8M
    = S64 NULL, SYN, CAP, SLX, AI → expect WEAK per S64 efficiency gradient) · **THIN-OK $10k–1M = 116** (the
    edge sweet-spot; `/tmp/thinok_pairs.txt`) · TOO-THIN <$10k = 231 (median $3,856/24h) · **DEAD $0 = ~30
    (untradeable)**. So the real target sleeve = the ~116 THIN-OK, and liquidity is a first-class gating axis
    (edge strong on thin, weak on liquid). Collect all 352 (cheap) but GATE/BUILD on THIN-OK.
  - **"RE"** = probably a TYPO in the S64 notes (Greg), not a real intended pair — drop it (REUSD exists but ignore).
- **⭐ OVERNIGHT DURABLE COLLECTION (running while Greg away):** `scripts/_s66_overnight_collect.sh` pulls all
  352 eligible alts @ **120d** Kraken tape (par=4, self-throttling), gzips + commits every 20 pairs to the orphan
  branch **`data/kraken-smallcap-tape`** (survives container recycle; resumable — skips committed pairs). Absorbs
  the SOL/XRP/DOGE majors at the end. 120d = ~17 weeks for the per-week+reversed gate (vs 5 on 30d).
- **⚠ Ambiguity to resolve (Greg):** S64 "**RE**" isn't a bare Kraken pair — candidates `RED/REKT/RENDER/REN USD`.
- **⭐ ORDER (Greg S66):** dipole-EXPERT + ARCHITECT reads DONE (`DIPOLE_EXPERT_READ_S66.md`,
  `ARCHITECT_READ_S66.md` — converged: capacity FIRST, capital model LAST, risk-axis changes). Kraken E300 DOGE/XRP
  + 5 majors DONE (AUC 0.64–0.72 venue-robust; ⚠ on the DEPRECATED 3-piece harness — not deployed-stack numbers).
- **⭐ CAPACITY BUILT + the reframe (S66 landing):** `odcore/capacity.py` (per-leg $ fill-cap, canary PASS). The
  fill-model saga (see handoff): STATIC cap = too pessimistic (−13, winners "unfillable"); PIVOT patch = LEAKAGE
  (retracted, agent caught it); **DYNAMIC following-maker** (`_s66_dynamic_fill_kraken.py`, Greg's re-quote-to-
  follow mechanic) = the honest middle (fills 100%, ETH +0.45/BTC +1.35). **GREG'S CALL: don't chase fill-quality —
  keep last night's per-coin EDGE, make capacity a VARIABLE SIZE cap, PIVOT to the capital model.** Per-coin $/hr =
  edge × capacity; the pool is SHARED ($2k/$2k/$1k across coins), capacity-capped, correlation-aware. Variable
  capacity REORDERS last night (BTC ~+5.2, XRP ~+7.4, SOL ~+2.8, ETH ~+1.8, DOGE ~+0.4 — thin books shrink hard).
- **⭐ NEXT SESSION:** (1) restart the eligible-alt collection (`_s66_overnight_collect.sh`, resumes; ⚠ in-container
  bg dies on idle); (2) **BUILD THE CAPITAL MODEL** — variable capacity + shared-pool allocator on the LIVE path
  (`odcore/allocator.py` + `platform.run_portfolio`, architect spec; sim=live); settle capacity-granularity
  (per-leg vs per-coin position) + pool size; (3) Kraken agent for **overlooked MAJORS** (LINK/ADA/AVAX/LTC — liquid
  majors beyond our 5, NOT thin eligibles); (4) re-grade eligibles + BTC/ETH with the DYNAMIC fill (static kill
  superseded) + pin on the ~30h book.

---

## 1. DEPLOYED CELLS (`odcore/platform.py::DEPLOYED`) — the production registry
Per-cell law: each cell = asset × venue × side, validated + deployed independently.
- **⭐ WE ARE ON KRAKEN (Greg). `KRAKEN` registry (S65) = the ACTIVE live stack** (`odcore/platform.py::KRAKEN`
  + `run_kraken_cell`): per-coin STACK (direction / early-arm eps / deep-bail / cover-grace / **enticing close** /
  REV), FRONT-OF-LINE fill, kr_mk0. `scripts/basket_sim_kraken.py` DECIDES through `run_kraken_cell` (sim = live
  code — S65 rule). CellConfig gained `side/rev/eps/bail/improve`. ⚠ BOOK-PROVISIONAL (one 30h window): direction
  re-adjudication (SOL/XRP/DOGE fwd) + the REV pick are NOT a live-capital decision until a 30d-tape confirm.
- `DEPLOYED = [sol, doge(grace=600), xrp, eth, btc(K=10)]` — **LEGACY Coinbase cells (venue PARKED, S63).** The
  paper_trade cron still runs these (a parked-venue ledger). **S66 open: replace the paper/live path with the
  KRAKEN registry** (needs a live Kraken book loader wired into a `run_cell`-style path + the paper cron repointed).
- **Fee frame (S63 pivot): KRAKEN kr_mk0 = 0 bp maker** (needs $10M/30d volume tier; Coinbase parked/legacy).
- `SANDBOX = []` (emptied S57 when Bybit was struck).

## 2. STRATEGY FAMILIES (we have MORE THAN ONE — do not treat lean as the only tool)

### A. Kraken flow-lean ZIGZAG — the mean-reversion RIDE  ⭐ primary
- **Signal:** `odcore/flip_detector.py` — causal taker-FLOW-lean flip detector (WFLIP=600, REV=0.1, ARM0).
  Zigzags on the taker-flow LEAN, not price (price at a turn is ~99.6% symmetric).
- **The STACK (this is a stack, not bare lean):**
  - `+ early-arm entry` (`retime_flips`, S47) — fire at first price reversal near the extreme. **~doubles it**
    (ETH bare +4.86 → +9.50; BTC +4.22 → +8.64 @ $5k, kr_mk0 paper). eps per-coin (ETH 10, BTC 5).
  - `+ deep bail` (BTC −80 / ETH −100) — FREE tail-cap (at big depth WIN%~0 = dead loss). Taker flatten.
  - `+ cover_grace` (rest cover past the turn, S48) — recovers the maker fill (ETH taker 55%→12%).
  - `+ swing floor` (coarser REV) — fill-vs-edge knob (fewer/bigger swings for real-fill deployment).
- **Per-coin verdict (`KRAKEN_DEPLOY_MAP_S63.md`):** ETH/BTC **forward** · SOL **reversed** · DOGE = fade-8h
  (different tool) · XRP = stand aside. **Per-coin window TUNING matters** (S64: SHX/AIOZ only pass at W2400).
- **Tools:** all `scripts/_s63_kraken_*.py` (20): retime, deepstop, covergrace, swingfloor, flipzz, winloss,
  makerfill, zigzag(+null), bail/widebail/flipbail/bailshort, winners/smallwinners, dipole_agent, etc.
- **DEAD levers (don't re-chase):** any entry/direction signal; flip/re-short at depth; shallow stop;
  take-profit trail; taker-entry (fee > captured edge — S64).

#### ⭐ FINAL PER-COIN CONFIG — the authoritative deployed set (reconciled S65 from CODE + docs; cite this)
> **Provenance (Greg's S65 concern — "best zigzag was the final Bybit, then per-coin fixes on Kraken; I don't
> trust we documented it right"):** the PEAK model is the deployed fine flow-lean zigzag at **NATURAL CADENCE
> (ARM0 — NO arming gates**; the S55/S56 *armed* fine-confirm variants were all killed by their own gate,
> `SESSION_HANDOFF_2026-07-03_S56.md`). On Bybit it PASSED the full S54 gate on all 5 coins (z 6.8–14.4 @ MM3
> rebate) — but Bybit's big $/hr was the **MM3 rebate volume paycheck**, not extra structure; the STRUCTURE is
> what ports. S63 carried that structure to **Kraken spot @ kr_mk0 (0bp)** with per-coin fixes below. Bybit is
> permanently banned (§6) so the config lives on Kraken now.
>
> Reconciled against BOTH the actual code constants (`scripts/_s63_kraken_*.py`: `WFLIP,REV=600,0.1`;
> `EPS`/`REVERSED`/`DEPTHS`) AND the prose (`KRAKEN_DEPLOY_MAP_S63.md`, `S63_TREND_FLIP_FINDINGS.md`,
> `SESSION_HANDOFF_2026-07-05_S64.md`). Core detector: `flip_detector.py` **WFLIP=600, REV=0.1, ARM0**, all coins.

| coin | signal | direction | early-arm eps | deep-bail | cover_grace | E300-on-ride | paper $/hr | gate |
|---|---|---|---|---|---|---|---|---|
| **ETH** | flow-lean zigzag | **forward** | **eps10** | **−100** | 300 | **DROP** (−0.41, redundant w/ deep-bail) | +9.50 | z=4.0 PASS |
| **BTC** | flow-lean zigzag (**K=10**) | **forward** | **eps5** | **−80** | 300 | **KEEP** (+0.20) | +8.64 | z=3.0 PASS |
| **SOL** | flow-lean zigzag | **REVERSED** | **none** (early-arm HURTS SOL, −0.68) | none | 300 | — | +2.33 | fwd z=−1.6 → reversed (fragile) |
| **DOGE** | **fade-8h TREND** (different tool, `_s63_kraken_fade.py`) | fade | — | — | 600 | — | +2.73 | fade p=0.016 (data-limited, 3% cov) |
| **XRP** | — nothing clears — | — | — | — | — | — | ~0 | z=0.7 → **STAND ASIDE** |

- **Fees:** kr_mk0 = 0bp maker; taker fallback ~5bp (deep-bail taker cross 11bp, flip 22bp). A 1bp maker fee is
  FATAL (kr_mk2 nets −13..−20) — the 0bp tier is the existence condition, razor-thin ~0.5bp/swing headroom.
- **Fill-mode knob (deployment vs paper):** detection **REV=0.1** = the paper edge; **swing-floor REV≈0.2 +
  cover_grace≈300** = the real-fill config (raises fill% 31%→60%; a fill-vs-edge knob). The honest-fill re-grade
  (Job 1) runs the swing-floor config, NOT bare REV=0.1.
- **⚠ S64 window-fragility flag (do NOT size off one window):** early-arm is the lift on the 30d TAPE but it
  **HURT BTC on the realbins book window** (opposite sign) — point estimates are window-fragile; confirm on a
  2nd window before sizing. Same for the E300-per-coin split (one realbins window).
- **⚠ Code-vs-deploy nuance (flagged S65):** `_s63_kraken_deepstop/bail/*.py` list `("sol", "SOLUSD", 10.0)` —
  the `10.0` is an eps used only to generate SOL's *analysis* legs; **SOL's DEPLOYED config takes NO early-arm.**
  Don't read that constant as "SOL uses eps10."
- **⭐ S65 PROVISIONAL LEAD (3 independent confirmations — basket sim + execution agent + dipole agent; ONE ~30h
  book window, NOT the tape — do NOT overturn the deploy map yet):**
  - **XRP is a clean-POSITIVE honest-fill cell** as the PLAIN base flow-lean ride (forward, NO early-arm, NO bail,
    cover_grace): +12.5 $/hr honest, fill 49%, forced-taker only 11%, win 53%, W/L 1.44. Its book fills well where
    the majors don't. The S63 "stand aside" was a 30d-TAPE direction call (z=0.7); the book-FILL picture is
    materially positive. A dipole gate does NOT help XRP — leave it un-gated. **NEXT: confirm on a 30d tape / Tardis.**
  - **The bleed on ETH/BTC/SOL is the FILL, not the signal** (`analyze_basket_kraken.py`): maker-closed legs are
    net positive/breakeven; 54–79% of ALL loss is FORCED-TAKER closes (win% 11–32% vs 49–54% maker). Fill fix
    (coarser swing-floor REV + bigger cover_grace, `_kraken_filllever.py`) mechanically lifts fill% 24→59% and
    claws ETH→~breakeven / SOL→+1.2 / BTC still −1.9 — but this LOW-EDGE window can't show the payoff (need Tardis).
  - **Dipole `divergence` as a leg-FILTER (never tried — only as a direction classifier)** lifts on 0bp-IDEAL
    (ETH 0.34→1.60/leg, SOL-rev sign-flip +1.98, opp+exh stack > opp alone) BUT on the HONEST fill it WRECKS fill%
    (the opposing-flow legs are exactly the adverse-selected worst-filling ones, S45) → net negative. Fill-idealization
    artifact; re-grade on a real-tape honest-fill window before any wire-in.
  - **Cheap coverage gaps found:** add xrp/doge to the `makerfill`/`covergrace`/`deepstop` CELLS (eth/btc/sol only);
    run S42 book-depth DIRECTION + E300 death-selector on the Kraken TAPE for XRP/DOGE (never run on Kraken).
  - **⭐ FRONT-OF-LINE vs the pessimistic bound (Greg S65 #2, `_kraken_enticing.py`):** the basket-sim "honest"
    number used `fill_model="queue" queue_frac=1.0` = BACK-of-the-best-level-queue (pessimistic). The DEPLOYED
    `run_cell` uses `fill_model="front"` = FRONT-of-line (the S46 "have the best bid/offer" premise). At front-of-line
    (queue_frac→0) EVERY cell flips positive on this window (eth +3.4 / btc +1.8 / sol +2.2 / xrp +14.0, forced-taker→0).
    So most of the ETH/BTC/SOL "bleed" was the back-of-line worst-case, not the signal.
  - **⭐ ENTICING MAKER CLOSE (Greg S65 #1 — new opt-in `swing_maker.simulate_swing_maker(close_improve_bps=)`,
    default 0 = bit-identical):** to EARN front-of-line, post a price-IMPROVED cover that CONCEDES a little half-spread
    to jump the queue → maker close instead of a taker cross. Even from the pessimistic back-of-line base, a **0.5bp
    concession converts forced-taker closes 26–47%→2–7%** and recovers ~half the bleed (eth −7.8→−3.1, sol −8.0→−3.1,
    xrp +12.5→+14.7). **Sweet spot is MINIMAL (~0.5bp)** — more concession costs more than it saves. The enticing quote
    is the mechanism that turns the back-of-line bound into the front-of-line ceiling. Re-grade on a normal-edge window.
  - **⭐ BASKET AT FRONT-OF-LINE (the corrected live-code run, `basket_sim_kraken.py` via `run_stream`):** all 4 active
    cells POSITIVE — eth +6.77 / btc +6.66 / sol +4.79 / xrp +14.02 $/hr; aggregate **+32.24/hr @ $5k each**; correlations
    near-zero (eth-btc 0.42, rest <0.22) so **portfolio Sharpe +0.674 > best single +0.629** (diversification real). The
    enticing lever adds **+0.00 at front-of-line** (nothing to convert — front-of-line already fills maker); its value is
    the back→front recovery it SECURES (+10/+17/+10/+1.5 per coin). Keep it on (free safety net; positive where needed).
  - **⭐ THE NEW BLEED = SIGNAL-LOSS, not fill** (`analyze_basket_kraken.py` at front-of-line): forced-taker collapses to
    0–1% of loss (1–2 legs); **100% of loss is now maker-close losers = wrong-direction swings** (win 52–57%, W/L 1.05–1.40).
    Deep-bail never fired (no −80/−100 leg on this calm window). So the CHEAP bleed (fill) is FIXED; the residual is the
    irreducible direction cost (direction is DEAD, closed 4 ways). Only SOL has a fatter tail (worst-10 = 33% of loss,
    W/L 1.05) — the one maybe-cheap probe left (a SOL bail was killed on tape; re-check on book), low priority.
  - **⭐ THE 2.5× LEG EXPLOSION AT FRONT-OF-LINE IS CHURN, NOT EDGE** (Greg S65; `_kraken_newlegs.py`/`_kraken_legbleed.py`):
    front-of-line fires ~2.5× more legs (eth 194→453) but ~same $/hr — the money is ONLY in the big swings (eth ≥20bp = 23
    legs = 97% of $/hr, net/leg +17bp; btc ≥10bp ~73%; xrp ≥20bp 109%); the mid legs [2,20)bp have winners ≈ losers (pure
    churn, ±25/hr gross → +6.77 net on eth). Bleed = QUICK-REVERSAL whipsaws (87–96% of loss).
    **PER-COIN REV (`_kraken_revsweep.py`, Greg's rule — cut churn ONLY where NEGATIVE):** eth/btc/sol keep 0.10 (their
    fine churn is net-POSITIVE — coarsening LOSES money, causally); **DOGE→0.30 and XRP→0.13 ADOPTED** (negative churn cut:
    doge +6.59→+9.13 win 54→63%, xrp +14.02→+16.05, portfolio Sharpe +0.810→**+0.946**). In the KRAKEN registry.
    Fewer/bigger/spaced legs also serve the capital/anti-resting rotation. front-of-line is optimistic on sub-bp legs.
  - **⭐ DIRECTION RE-ADJUDICATION employed (agent finding; `_kraken_readjudicate.py`) — FWD wins ALL 5 on the book:**
    eth +3.42 / btc +1.80 / **sol +6.51 > rev +2.17 (CONTRADICTS deployed reversed)** / **xrp +14.02 (was stand-aside)** /
    **doge +5.46 fwd flow-lean** (deployed = fade-8h). Employed in `basket_sim_kraken.py` (SOL→fwd, DOGE activated fwd, XRP
    fwd), portfolio Sharpe → +0.810 with 5 uncorrelated cells. ⚠ ONE 30h BOOK window vs the 30d-TAPE deploy map — a
    RE-ADJUDICATION, NOT an overturn; the live deploy map (SOL reversed / XRP aside) stands until a 30d-tape/Tardis confirm.
  - **⚠ CAPITAL FRAMING (Greg S65): NO aggregate-as-sum.** $5k is the TOTAL, not per-cell; the sim's "aggregate @ $Nk"
    line is the OLD wrong framing. Real portfolio = ONE $5k pool ALLOCATED across cells with an ANTI-RESTING strategy
    (route capital to whichever uncorrelated cells are live so it's never idle — majors sit ~57% idle, small caps take
    small size → need MANY cells). The $5k-shared-pool + anti-resting rebuild is the next build (not yet done).

### B. Coinbase midband entry + E300 DEATH-SELECTOR — the mid-leg rig  ⭐ SEPARATE family
- **Entry:** `odcore/entry_coinbase.py::armed_midband_flips` (S59 promoted; `COINBASE_MIDBAND` registry).
- **The edge:** at 300 s into each leg a depth classifier (`scripts/_s62_e300_3piece.py`) predicts DEATH
  (final gross ≤ −40) at **AUC 0.69–0.77 all 5 coins** → HOLD / FLATTEN / FLIP. Independently earns
  (BTC +1.29/hr). `_s63_e300_trend.py` folds the 1h-trend as flip-direction confirm.
- **NOT yet combined with family A** (S64 open): stack E300 death-cut onto the Kraken lean ride, and/or
  run E300 as a SECOND uncorrelated sleeve (edges ~uncorrelated → √N Sharpe + fills the majors' idle).

### C. Fade-the-N-hour-TREND — direction tool for trending coins
- `scripts/_s63_kraken_fade.py` / `_s63_fade.py` — pred_side = −sign(mom over W hours). DOGE-8h clears
  (p=0.016); the market mean-reverts at multi-hour horizon. Decide side at ENTRY (no flip fee).

### D. OD dipole / divergence-exhaustion (the S36 flow read)
- `odcore/info_dipole.py` — `divergence()` (aligned_flow = imb·sign(drift)), exhaustion (dipole→0.5).
  Per-cell trend-continuation-vs-FLIP detector. Feeds gates; the S36 "biggest edge" candidate.

### E. 128-dim OD FINGERPRINT tier (the S35 distinctive-winner signature)  ⚠ heavy, mostly off-container
- `odcore/fingerprint.py`, `fingerprint_predictor.py`, `dipole_predictor.py`, `od_refrag_adapter.py` —
  deterministic OD coeff decoder + centroid dual-print (match-winner MINUS match-loser). The winner-side
  path when causal flow reads are null. **Needs the E-drive discovery archives + encoder** (not in container).

### F. QuietFloor gate — book-depth relaxation
- `odcore/quiet_floor.py` — AR(1) relaxation floor on book-depth imbalance; fires only on a shock that
  breaks the floor (gate = WHEN, level sign = DIRECTION). Cuts between-trade churn.

### G. Other executors / research strategies
- `odcore/swing_accum.py` — Greg's ACCUMULATE strategy (starter + all-in-on-confirm, layered unload).
- `odcore/swing_bigline.py` — Greg's BIG-LINE (trendline ride/break, coarse-theta swing capture).

## 3. EXECUTOR & INFRA (shared)
- `odcore/swing_maker.py` — **THE one executor** (S55 "one version: live=paper=research"). Maker-at-the-turn,
  one-sided; params: `cover_grace`, `lean_exit`, `exit_spec` (price_stop/armed_dive/casc_flip), `exit_gate`,
  `fill_mode` (maker/taker), `fill_model` (front/queue-honest), `maker_fee`(neg=rebate)/`taker_fee`. Deep-bail
  = an exit_spec/taker flatten. Defaults bit-identical when arms off.
- `odcore/platform.py` — `run_cell` (deployed cells) / `run_stream` (any flip stream, same executor);
  `DEPLOYED`/`SANDBOX`/`COINBASE_MIDBAND` registries; venue is a first-class CellConfig dim.
- `odcore/incremental.py` — `RollingFlow` O(1)/tick incremental signal (the LIVE hot-path form).
- `odcore/maker_book.py` — honest queue-ahead fill model (feeds swing_maker fill_model="queue").
- `odcore/leakage.py` (`assert_no_leakage` — MANDATORY before wiring any signal), `validation.py`
  (walk-forward + real costs + circular-shift tautology null), `sizing.py` (OD-native, `size_legs`),
  `generators.py`, `stacking.py`, `quiet_registry.py`.
- **Paper/live:** `scripts/paper_trade.py` (forward ledger cron), `paper_ledger*.jsonl`.

## 4. DATA COLLECTORS
- `backfill_kraken_trades.py` (REST tape → 1s bins; pairs XBTUSD/XDGUSD; ~1req/s, hours).
- `kraken_book_collectors_durable.yml` (all 5 coins, 6h cron → `data/<coin>-kraken-book`, L2 depth).
- Coinbase: `coinbase_book_collector.py`, `coinbase_collector.py`; alt/book durable workflows.
- Materialize book: `git show origin/data/<coin>-kraken-book:<f>.jsonl.gz | gunzip`.

## 5. FEE / VENUE REALITY (S64)
- **Kraken spot maker:** starts 0.25% (25 bp) → **0.00% at $10M/30d** → negative only at $500M+ (majors).
  30d volume is **aggregate across ALL pairs** (majors count toward the tier).
- **Maker REBATE (−2 bp):** ONLY on select LOW-LIQUIDITY pairs (majors BTC/ETH/SOL/XRP/DOGE excluded),
  and only at $10M+/30d. Eligible set = detect live via AssetPairs negative-maker-tier signature; Kraken
  re-curates it ~monthly (liquidity-driven).
- **US-legal rebate venues:** effectively only Kraken's alt-pair program. Bybit/OKX out (US-ineligible).

## 6. STANDING BANS / DEAD
- ⛔ **BYBIT** — permanently banned (US-ineligible, S57). **MEXC** dead. Coinbase parked (fee frame = Kraken).
- Dead levers: entry/direction prediction (closed 4 ways); taker-entry as blanket rule; mk0 as a default basis.

---
## 7. TRIED & DEAD — do NOT re-run these (per-coin caveats noted; kept where they work)
- **Entry/direction prediction** — closed 4 ways (S62 coeff, S62 momentum, S63 fade-flip, S63 dipole agent);
  direction ~0.50 at entry AND every mid-leg time. Depth predicts DEATH (magnitude), never direction.
- **Taker-entry as a blanket rule** (S64) — taker fee (11bp/leg) > captured edge (1-7bp/leg avg). ORACLE
  (perfect winner-pick) works (+11 ETH) but no entry-time swing-SIZE predictor exists (vol AUC 0.567≈chance).
- **E300 death-cut ON the lean ride — PER-COIN, NOT global** (S64, Greg): KEEP on **BTC** (+0.20, helps even if
  marginal), DROP on **ETH** (−0.41, redundant with deep-bail there). Do NOT pool to "neutral" — per-coin law.
  ⚠ one window (realbins); confirm 2nd window before sizing. E300 ALSO runs as its own SLEEVE (family B, +1.29/hr).
- **Flip / re-short at depth** (S63) — slide spent (confirmed-short wins ~19%); bail-flat > confirmed-short > blind.
- **Shallow stop (−15), take-profit trail** (S63) — clip recoveries / fight mean-reversion + pay taker. Deep-bail only.
- **mk0 as a default fee basis** (S57) — 0bp is the $10M/30d tier, not a given. **Bybit / MEXC** — banned/dead.
- **Grading a pair on ONE lean config** (S64) — under-calls per-coin; tune the WINDOW (SHX/AIOZ need W2400).

### S64 open threads (see handoff/kickoff)
1. ✅ Full-stack + E300-on-lean measured (early-arm = the lift; E300-on-ride neutral → E300 = separate sleeve).
2. Rebate-eligible-pair BASKET (per-coin tuned gate; ~6 confirmed: APE/RE fwd, XDC/SHX/AIOZ/ARPA rev). Needs
   the full per-week+reversed re-gate on the shortlist + longer pulls on the 7-day pairs (SYN/GWEI/NIGHT/HYPE).
3. **Multi-sleeve basket simulator** (majors unlock tier + eligible earn rebate + E300 sleeve; ~0-corr idle-fill)
   — THE next build. Name it `*_kraken_*` (deployable). Run through the real executor, not bare lean.
4. Kraken live adapter (WS v2 add/amend/cancel, executions, post_only; no spot testnet → tiny-size first).

---
## 8. PIECES — exhaustive catalog (S65, Greg's anti-amnesia audit)
> Greg (S65): "go through all the handoff versions and list all the different inventory pieces. it doesn't
> matter if they say dead or killed or whatever... I'm just not 100% we haven't missed something." Every
> distinct strategy/signal/detector/gate/executor/sizing/fill-model/dipole-read/fingerprint/cross-venue
> tool/feature/research-idea ever BUILT or seriously PROPOSED (S19→S65), regardless of dead/killed/parked
> status. Sourced from all SESSION_HANDOFF_*, KICKOFF_*, *_FINDINGS/*_NOTES, CLAUDE.md deltas, code, and
> docs/DIPOLE_PAPER_S60.md. The richest "buried but reusable" reservoirs are flagged at the bottom.

### 8.1 Signals & detectors
- **Flow-lean zigzag flip detector** (`odcore/flip_detector.py`, S36→S56) — causal taker-FLOW-lean zigzag (W600/REV0.1/ARM0); zigzags on flow lean not price. **live** — core deployed; ETH/BTC fwd, SOL rev.
- **ARM0 natural-cadence fine zigzag** (`flip_detector.py`, S56) — the PEAK model; full S54 gate all 5 (z 6.8–14.4). **live**.
- **Price-reversal zigzag (1-sec)** (S36b) — enter ~5–6bp of the true turn; the TIMING half. **live** (paired w/ dipole filter).
- **Big-line / trendline ride-break** (`odcore/swing_bigline.py`, S54) — coarse-theta swing capture. **parked** — Coinbase-1-window +$1–4/hr didn't reproduce on 30d Bybit bins (per-window, not dead).
- **Two-scale zigzag (fine executes, coarse selects)** (S54→S55) — **DEAD** — v0/v1 re-entry churn (global).
- **Fade-the-N-hour-trend** (`_s63_kraken_fade.py`/`_s63_fade.py`, S62/S63) — pred_side=−sign(mom over W hrs). **live-per-coin** — DOGE-8h clears (p=0.016), SOL-4h; XRP/ETH fragile.
- **1h-trend-fade flip** (`_s63_trend_flip.py`, S62/S63) — among big losers 1h trend predicts fwd dir 0.58–0.67; flip strongest. **research**.
- **Multi-hour big-trend oracle** (S53→S54) — 100–300bp waves, fee 2–5% of swing. **research** — proved opportunity, capture open.
- **OFI momentum / fade generators** (`odcore/generators.py`) — ofi_momentum/ofi_fade/momentum5/dipole_direction. **DEAD** — all lose net-of-cost (WF −11.8%..−188%, taut z~1); kept as diagnostics.
- **Depth-imbalance next-move predictor** (`_liquidity_dive.py`, S42) — top-K depth_imb predicts SIGNED next move (OOS +0.164, 63% hit, leads +0.1s). **research** — sub-bp, a MAKER/quoting signal.
- **buy/sell mirror leave-one-out** (`_diag_flip_states.py`, S41) — 63.5% flip-state classifier. **research/diagnostic**.
- **Freight-train anatomy** (S56/S57) — worst-10 = counter-entries into violent moves; dipole `continue` rc=0.00 flags them. **DEAD as gate** — no subgroup sums negative; content in size axis.

### 8.2 Entry timing
- **Early-arm retime (`retime_flips`)** (`flip_detector.py`, S47) — fires at first price reversal near extreme; ~doubles $/hr. **live-per-coin** — eps10 ETH/eps5 BTC; HURTS SOL (−0.68) & hurt BTC on realbins (window-fragile S64).
- **Arming rule v1 (two-stage confirm)** (`_s55_armed_zigzag_probe.py`, S55) — **DEAD** — idles 98% of month, unbounded loss (global, S56).
- **v2 extreme-anchored + trailing fallback** (`_s56_armed_gate.py`, S56) — **DEAD** — 25bp first-dip = coin flip (47% win, global).
- **ARM chop-filter family (v3-ARM)** (S56) — **DEAD** — fails as a family (global).
- **Armed mid-band entry machine** (`odcore/entry_coinbase.py::armed_midband_flips`, S58→S59) — **deployed** — `COINBASE_MIDBAND` (sol mb100/xrp mb80/doge mb100; btc gated; eth absent).
- **Theta-confirm baseline entry** (S55/S57) — **DEAD as edge** — theta-late (SOL −31bp/leg gross); the baseline to beat.
- **Fine 25bp reversal confirm (the LAG cut)** (S55 R5) — theta-confirm 151bp/54min → 26bp/1min. **research** — ~250bp/leg recoverable.
- **Bounce-back / trough-sell fallback** (S53/S56) — **DEAD** — rejected S58 R5; trough-sell fine-scale-local.
- **Confirm threshold scaling with band** (S57) — **DEAD** — "+2bp as coarse confirm" listed dead.

### 8.3 Exit & loss management
- **Deep bail (BTC −80 / ETH −100)** (`_s63_kraken_deepstop/bail/widebail.py`, S63) — at big depth WIN%~0, taker-flatten caps the −150/−200 tail FREE. **live-per-coin** — ETH/BTC (SOL none).
- **Shallow bail / stop (−15)** (S63) — **DEAD global** — BLED (clips recoveries + fights mean-reversion + taker).
- **Flip / re-short at depth** (`_s63_kraken_flipbail/bailshort/flipzz.py`, S63) — **DEAD global** — slide spent, confirmed-short wins ~19%.
- **Take-profit trail / peak harvester** (S60/S63) — **DEAD global** — winners already 68–83% of peak; toll law (giveback=c·θ) → no harvester exists.
- **cover-grace** (`swing_maker.py::cover_grace`, S48) — rest cover past turn, first opposing=maker. **live** — taker→~0% all 5; flipped DOGE losing→profitable; grace map (doge 600).
- **lean_exit / lean-collapse exit (R8)** (`swing_maker.py::lean_exit`, S55) — **parked** — INERT at fine scale (flip detector IS that exit); value at coarse, never aimed.
- **exit_gate (structure-says-out / FLAT third state)** (`swing_maker.py::exit_gate`, S55) — **research** — fixes S46 non-actionable-flip-HELD mismatch.
- **Wrong-side corrector (per-cell DIAGONAL)** (S60 Piece-2) — **research-per-coin** — SOL none / BTC plain-stop / DOGE casc-flip / XRP none.
- **Plain price-stop rider (BTC)** (`btc_coinbase_mb80_plainstop`, S60/S61) — **parked/ops-blocked** — cell stays negative; ZERO gap protection → ops bar (needs exchange-side stop + staleness kill).
- **Armed dive / armed-before uw-stop** (`exit_spec=armed_dive`, S60/S61) — **DEAD-per-coin** — fails BTC th80; SOL-only until re-shown.
- **Cascade-join flip (casc_flip)** (`exit_spec=casc_flip`, S60) — **research DOGE-only** — BUY-only +1.10/hr; fails Kraken shuffle floor (venue law).
- **Harvest-into-strength rungs (B1)** (`_s53_accum_sandbox.py`, S53) — **DEAD global** — LOSES (−$0.26), caps fat winners.
- **c_x·theta retrace exit** (S61) — **DEAD** — wealth transfer (winners −65..−73 SOL).
- **3-part exit oracle (hold/flatten/flip)** (`_s62_3piece_harness.py`, S61/S62) — **research (oracle)** — +26/hr (15×), 508/508 winners kept; NO causal mid-leg signal reaches it (winners-invisible law).
- **Big-loser flip / flip pre600<−80** (`_s62_loser_flip.py`, S61) — **research** — +2.38–6.79/hr; WEEK-FRAGILE (wk4).
- **Flip-then-manage** (S61 R13f) — flatten reversed leg on adverse / ride on favorable. **proposed** — the wk4 mitigation, unbuilt.
- **Winner flip** (`_s62_winner_flip.py`, S62) — **DEAD** — winners fade DEEPER (min −429), outnumber losers 2.5:1.

### 8.4 Gates & filters
- **Dipole divergence (aligned_flow)** (`info_dipole.py::divergence`, S36) — imb·sign(drift); strong div → ~65% reversal. **research/gate** — the S36 "biggest edge" candidate.
- **Dipole exhaustion (dipole→0.5)** (`info_dipole.py`, S36) — oppose+exhaust=64% reversal. **research** — stacks w/ divergence.
- **QuietFloor gate** (`odcore/quiet_floor.py`+`IncrementalQuietGate`, S42/S44) — AR(1) book-depth relaxation; fire only on a shock breaking the floor. **research/wired** — fires 6.9% vs 100%; on the depth channel.
- **Regime master-gate (per-cell)** (`_info_dipole_regime_gate.py`, S36b) — stand-aside; rescues bleeders. **research** — PER-CELL.
- **E300 death-selector** (`_s62_e300_3piece.py`, S62) — at 300s realized DEPTH predicts DEATH (gross≤−40) AUC 0.69–0.77 all 5. **research/Family-B** — magnitude/death not direction.
- **E300-on-the-ride death-cut** (S64) — **research-per-coin** — KEEP BTC (+0.20), DROP ETH (−0.41); one window.
- **Deep-arm variant (arm −20/−30)** (`_s62_armed_trend.py`, S62) — ETH/BTC/DOGE +1.1..+1.6. **research** — one window.
- **Climax-volume gate** (S40/S47) — **DEAD as wrong-tail gate** — removes winners, halves total; real as a fillability marker (S60).
- **Adverse-excursion STOP gate** (S47) — **DEAD** — cuts winners that reverse.
- **Dipole-exhaustion wrong-tail gate (entry_gate)** (S46) — **DEAD/marginal** — anti-predictive; off by default.
- **Confirm-budget / D-class gates** (S53) — **DEAD** — confirm-budget dud (corr −0.10).
- **Death-combo anti-print (opposing+climax w/o exhausting)** (S58) — 4×-replicated worst-entry (−31..−53bp/leg). **research (anti-print)** — avoid, not a positive gate.
- **Coeff gate / loser-coeff tier** (S62) — **DEAD in-container** — ~chance at mid-band (date/regime confound).
- **"No gates" scoring rule** (Greg S53) — judge net $/hr AND legs/hr. **standing rule**.

### 8.5 Executors & platform
- **swing_maker (THE one executor)** (`odcore/swing_maker.py`, S46→S55) — one-sided maker-at-the-turn; cover_grace/lean_exit/exit_spec/exit_gate/fill_mode/fill_model/fees. **live**.
- **platform run_cell / run_stream** (`odcore/platform.py`, S55) — deployed cells / any flip stream; venue = 1st-class dim. **live**.
- **DEPLOYED/SANDBOX/COINBASE_MIDBAND registries** (S55/S56/S59) — **live** (SANDBOX emptied S57).
- **entry_coinbase** (`odcore/entry_coinbase.py`, S59) — armed mid-band + truncation-invariance leakage gate. **deployed**.
- **swing_accum** (`odcore/swing_accum.py`, S52) — accumulate (starter + all-in-on-confirm + layered unload). **research** — +$1.3–1.6/hr SOL miniature; R&D not deploy.
- **swing_bigline** (`odcore/swing_bigline.py`, S54) — **parked** (see 8.1).
- **exit_spec socket** (`swing_maker.py`, S61) — price_stop/armed_dive/casc_flip, flat/flip, wall-clock lean_w. **research**.
- **RollingFlow incremental** (`odcore/incremental.py`, S36b) — O(1)/tick, bit-faithful, 1.70µs/tick. **live** (hot-path form).
- **paper_trade forward ledger** (`scripts/paper_trade.py`, S47) — causal executor + sizing all 5 cells, deduped accruing. **live**.
- **3-piece harness** (`_s62_3piece_harness.py`, S62) — reproduces R11 (SOL +1.77/+13.93/+26.02). **research rig**.

### 8.6 Sizing
- **Two-factor conviction sizing** (`odcore/sizing.py::size_legs`, S47/S49) — QUALITY (clmx_60) × SIZE (vol_60/volat_120/runup/dive_depth). **live** — SOL +3.6σ/DOGE +3.2σ/BTC +2.2σ; XRP/ETH null. Leakage PASS.
- **Staged-commit / accumulate sizing** (`swing_accum.py`, S52/S57) — starter → all-in on confirm (maker adds). **research/validated** — confirm adds beat random 10–14σ; NO across-trade signal.
- **Dive-depth→size (|lean@pivot|)** (S40) — predicts big moves all 4 cells. **research/live** — the first swing-SIZE signal (a SIZE axis).
- **Size cap / hi_clip tightening** (S51) — **DEAD** — FALSIFIED on forward ledger; net rises to hi_clip=4.0.
- **Scale-in / netting variants** (`_scale_in_probe.py`, S51) — **DEAD** — losers soak ~2× flow (adverse selection); REVERSED control beats it.
- **Anti-martingale / probe-across-trades** (S52/S57) — **DEAD** — P(w|prev w)==P(w|prev L) all 5.
- **Taker-entry as blanket rule** (S64) — **DEAD global** — fee 11bp > edge 1–7bp/leg; no entry-time swing-size predictor (vol AUC 0.567≈chance).

### 8.7 Fill models
- **Front-of-queue (v1)** (`_capacity_model.py`, S45/S51) — best-price priority, full half-spread. **research (optimistic bound)**.
- **Queue-honest (v2)** (`_capacity_model.py`, S51) — minus best-level size ahead. **research** — mk0 4/5 ceilings NEG; −1bp flips positive.
- **maker_book honest queue-ahead** (`odcore/maker_book.py`, S43) — fill when opposing taker vol clears the queue + adverse selection. **research** — feeds `fill_model="queue"`; binding = PRICE ELIGIBILITY.
- **Price-eligibility fill fix** (`_leg_caps` price_eligible, S52) — **live (bug fix)** — all pre-S52 mk0 $/hr were artifacts.
- **1s entry-window fill bound (FILL_W)** (S50) — **live** — Greg-caught (SOL −$204→+$19/hr).
- **Honest fill (queue + repeg-to-best)** (S61 #1) — queue clears median ~8s; repeg makes grace=0 fine. **research**.
- **Fill-size binding constraint** (S56) — median fillable $137–169/leg is the cap, not the edge. **measured**.
- **Taker-share acceptance / fill-asymmetry dollars** (S60) — **proposed (ranked archive levers)**.

### 8.8 Dipole / OD reads (D1–D8 + turn anatomy)
- **D1 flow dipole (dMI/dt)** (`info_dipole.py`, S60) — **DEAD standalone** — blind (R²<0.02, opposition is construction-generated).
- **D2 algebraic ("chem") dipole** (`dipole_predictor.py`, S60) — H_a²=a+b(H_a·H_b)+c(·)². **DEAD on order-flow entropies** — no convex c>0; convexity is a D3 (coeff-space) property.
- **D3 centroid dual-projection (markets H_a/H_b)** (`dipole_predictor.py`, S25) — coeff on win/lose centroids. **research** — real per-pair (z=+9.6) but confounded; needs same-period losers.
- **D4 trading lean dipole (the deployed one)** (`flip_detector.py`, S36+) — trailing flow lean + causal zigzag. **live** — deepest record (z 6.8–14.4).
- **D5 divergence/exhaustion** (`info_dipole.py`, S36) — see 8.4. **research/gate**.
- **D6 raw-covariance dipole (solved for time)** (`odcore/leadlag.py`/`coupling_scanner.py`, S41/S60) — raw cross-cov over lag; recovers the lag. **research (rank-A)** — the lead-lag tool; entropy transforms destroy it.
- **D7 entropy-asymmetry + C ratio** (S60) — **DEAD as signal** — units bookkeeping / MI-degeneracy.
- **D8 fingerprint-space difference (dual-print / buy-sell mirror)** (S60) — see 8.9. **research** — population-relative.
- **M1 mutual-info-in-null discriminator** (`odcore/null_extract.py`, S60) — state-dependent regime coupling. **research tool**.
- **Turn anatomy — CLIMAX / coeff-flip / QUADRATIC+accel-leads-3s** (`_turn_*`, S40) — 94–99.6% symmetric; edge = ODD remainder in FLOW (5.7%) not price (0.4%). **research findings** — climax = fillability marker.
- **Absorption / spoof wall** (`_s60_absorption_wall.py`, S60) — **DEAD (decided against)** — latency killed, wall falsified; residual SOL-only maker-frame price-discovery lead.
- **Three-offices dipole framing** (S60) — one lean, three offices (entry-confirm/wrong-side/fill-moment). **standing note**.
- **Fill-office INVERSION (dive marks THIN tape)** (S60) — dive marks ~70%-one-sided tape; with-ride climax = true fillability. **finding**.
- **coupling_scanner tautology null** (`coupling_scanner.py`, S20/S41) — 5-step coupler + circular-shift (145 decoupling events). **research tool** — load-bearing null.
- **dipole_trade 15-dim coupling vector** (`dipole_trade.py`, S22) — **DEAD as basis** — collinear (eff-rank 7.82); superseded by 128-dim.
- **3 dipole flow agents (paper/dive/s61alt)** (S62) — **DEAD as death-vs-recovery** — ~chance (0.47–0.56); orthogonal but null.
- **8 dipole-paper features F1–F8** (`dipole_paper_s62.md`, S62) — F1_lean..F8_entdipole. **research** — AUC ~0.5; F5 weak ETH, F2/F7 weak BTC.

### 8.9 Fingerprint / 128-dim OD tier
- **OD coeff deterministic decoder** (`odcore/od_refrag_adapter.py`/`fingerprint.py`, S39) — prefill+refine → 128-dim unit-L2, in-container (35s). **research**.
- **Per-cell distinctive fingerprint predictor** (`fingerprint_predictor.py`, S40) — ~91% shared shape, distinctiveness = ~9% residual; buy/sell perfect mirror (−1.0). **research**.
- **Centroid dual-print (match-winner MINUS match-loser)** (S59) — **DEAD at micros tier** — clean null; narrows to the S35 ENCODER tier.
- **Onset re-anchor (per-episode)** (`_build_episode_onsets.py`, S35b) — reconstruct true onset. **research** — entry-fingerprint canary gate.
- **6 micros feature set** (S34/S35) — mean_dipole/dipole_acl1/volume_zscore/trade_present/recent_2chunk/from_onset. **research** — stored micros were LOOK-AHEAD; coeffs CLEAN.
- **cand_sp / win_onset coeff signatures** (`markets_<cell>_win_cand_sp/`, S35) — ~1,919 per-cell signatures, hist AUC 0.72–0.84. **research (archived LOCAL on E:)** — the heavy winner-side prize; not in container.
- **HEAVY OD-coeff + centroid gate** (`_markets_gate_v2.py`, S35) — memoized, AWS-scalable. **research (validated tier)**.
- **Fingerprint encoder + canary** (`_canary_fingerprint.py`, S35) — must reproduce ONSET micros from pre-entry bars. **research (gate)** — must pass before wiring.

### 8.10 Cross-venue / coupling / lead-lag
- **Cross-venue reversion** (`od_xvenue_backtest.py`, S20/S51) — Coinbase↔Bybit lag-0 cc=0.656 z=580. **DEAD as taker edge** — real (z 3.0–3.6 @10s) but per-trade edge < cost.
- **leadlag raw cross-cov-over-lag** (`odcore/leadlag.py`, S19/S41) — a leads b 75.5%, mean +0.07s. **research tool**.
- **Cross-venue lead-lag map (D6, rank A)** (S60 menu) — Binance-spot flow leads Kraken price 1–30s. **proposed** — kill if lag-0 dominates.
- **Cross-coin dive propagation (D4+D6, rank A)** (S60) — BTC/ETH dive precedes alt dives → portfolio flatten overlay. **proposed**.
- **Implied stablecoin-basis monitor (D6+D7, rank A)** (S60) — implied USDT/USD depeg early-warning. **proposed** (novel data object).
- **Cross-coin rolling correlation regime descriptor** (F2/F3, S51/S62) — rolling 400s corr vs other major. **research feature**.
- **Book-toxicity score (VPIN analogue) / lean-conditioned inventory skew** (D4+D6, rank A, S60) — **proposed**.
- **Coupling-collapse vol overlay / dipole-class throttle / algebraic convexity cell-selector / centroid drift alarm** (D-menu rank B, S60) — **proposed (lower)**.

### 8.11 Data & infra
- **backfill_kraken_trades** (`.py`, S59) — REST tape → 1s bins, paced/resumable; 30d×5 pulled. **live**.
- **kraken_book_collectors_durable** (`.yml`, all 5, S59) — 6h cron → `data/<coin>-kraken-book` L2. **live** (the FILLS truth).
- **Coinbase book/bin collectors** (S37/S44) — **live (parked venue)**.
- **Bybit book/perp collectors** (S37/S51) — **DEAD/STRUCK** (S57 ban; 2 branches await UI delete).
- **Binance-vision / bybit backfill** (`backfill_binance_spot.py`, S39/S54) — bulk dumps → 30d×5 1-sec bins ~40min. **live** (the S54 unlock).
- **build_realbins** (`scripts/build_realbins.py`, S23) — merge daily JSONL → realbins. **live**.
- **Gzip data-branch storage + rotation guardrail** (S37/S58) — fixes 100MiB cap. **live** — off-git (S3/Render) is the durable answer.
- **OD-BOOK L2 collector + dynamics-recoverer** (`research/od_book/`, S37/S43) — **DEAD (KILL S43)** — fee-floor not signal (leg-2 FAIL); DMD operator salvaged as a feature.
- **CouplingStore + 5 OD endpoints** (`backend/odcore_store.py`, S21) — **research/diagnostic** — OD is shadow, not live source.

### 8.12 Fee / venue reality (context)
- **Real fee models** (S57) — cb_entry 40/60 .. cb_top 0/6 ceiling. **standing** — mk0 = unreached tier.
- **Kraken kr_mk0 (0bp @ $10M/30d)** (S58/S59) — verified, no application, the existence condition. **live frame** — 1bp maker FATAL.
- **Kraken alt-pair maker rebate (−2bp)** (S64) — select low-liq pairs, $10M+/30d, majors excluded. **research** — only US-legal rebate path.
- **Bybit MM (−0.1..−1.25bp)** (S51/S52) — **DEAD/BANNED** (S57 US-ineligible).
- **Fee-tier > all exit code** (S60/S61) — Greg's "2 clicks". **standing note**.

### 8.13 Multi-sleeve / basket (open builds)
- **Multi-sleeve basket simulator** (`scripts/basket_sim_kraken.py`, S65) — majors book-honest + eligible/E300 sleeves flagged; correlation + portfolio Sharpe. **BUILT v1 (S65)** — full per-coin stack via real executor; provisional on the 30h low-edge book.
- **Rebate-eligible-pair basket** (S64 #2) — ~6 confirmed (APE/RE fwd; XDC/SHX/AIOZ/ARPA rev; SHX/AIOZ @W2400). **research** — needs full per-week+reversed re-gate.
- **E300 as separate uncorrelated sleeve (Family B)** (S64) — +1.29/hr BTC, fills majors' idle. **research**.
- **Kraken live adapter (WS v2)** (S64 #4) — add/amend/cancel, post_only; no spot testnet → tiny-size. **proposed**.

### 8.14 Validation / discipline infra (gate everything)
- **assert_no_leakage** (`odcore/leakage.py`, S36b) — mandatory pre-entry; catches look-ahead 40/40. **live (mandatory)**.
- **validation (walk-forward + real costs + circular-shift null)** (`odcore/validation.py`, S20) — **live** (promotion gate).
- **S54 full gate (shuffle + reversed + per-week ×5)** (S54/S56) — **live** (deep-history gate).
- **Shuffle floor** (S56) — structure-free tape earns ~$90–106/hr/coin; premium = +$7–17 above. **standing** — never cite floor as edge.
- **quiet_registry / size_legs per-cell emit** (S44/S49) — per-cell alpha/roll + deploy flag. **live**.
- **Agent-fleet playbook** (`AGENT_PLAYBOOK_PIECES.md`, S58) — leg-dump-not-tape, falsification duty, convergence=evidence. **standing method**.
- **Leg dump (entry/exit)** (`_s58_piece1_legdump.py`, S58) — causal descriptor row at the decision cell, leakage-gated. **live method**.

### ⭐ Richest "may have missed something" reservoirs (Greg's concern → the audit agents' targets)
1. **Per-coin-DEAD exit correctors kept for another coin** (§8.3) — casc_flip DOGE-only, plain-stop BTC-only, wrong-side corrector diagonal — never swept across ALL Kraken coins per-cell.
2. **Gates alive as size/fill markers but DEAD as gates** (§8.4/8.8) — climax (fillability), death-combo (anti-print), dive (thin-tape marker) — reusable in a different office.
3. **The S60 dipole-paper rank-A/B menu** (§8.10, docs/DIPOLE_PAPER_S60.md) — ~15 fully-specified but UNBUILT cross-venue/coupling proposals (cross-coin dive propagation, book-toxicity/VPIN, lean-conditioned inventory skew, stablecoin-basis).
4. **The E-drive fingerprint archives** (§8.9) — cand_sp/win_onset coeffs (AUC 0.72–0.84), the heavy winner-side path never wired (needs E: + encoder).
