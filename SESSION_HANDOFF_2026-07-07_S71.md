# SESSION HANDOFF — S71 (2026-07-07)

# ══════════════════════════════════════════════════════════════════════════════
# ⛔ DROP-IN BOX — S72 (read this first)
# ══════════════════════════════════════════════════════════════════════════════
READ, IN ORDER: `STRATEGY_INVENTORY.md` (OPERATING CONTRACT + ✅ LIVE + standing principles #0b/#0c/#0d —
#0d + its reading-rule/churn/dipole/whole-ballgame corollaries are NEW and load-bearing) → this handoff →
`SIGNAL_SHAPE_DIRECTION_S71.md`.

**⭐ AFTER YOU FINISH READING THE DOCS: STOP and have GREG EXPLAIN THE NEW GRAPHS before doing anything.**
The graphs are in `research/shape_s71/*.png` (print them for Greg): `kraken_types_regrouped.png` (the 4 types,
all coins), `kraken_two_shapes.png` (per-cell {duration×outcome} arcs), `kraken_winner_loser_arcs.png`,
`btc_false_start_arcs.png`, `btc_kraken_arc_matched.png`. Greg wants to walk you through what they show — do
NOT interpret them yourself first. The saved arc values are in `research/shape_s71/quad_means.npz` (load them,
do NOT recompute — recompute is slow; Greg was firm on this).

BRANCH: reconcile to canonical FIRST (recurring wrong-parent bug). This session = `claude/davisai-s71-
counterparty-capacity-sf1168`. If S71 files below are missing, the branch was cut from a stale parent →
`git reset --hard origin/<newest davisai-sXX tip>`.

# ══════════════════════════════════════════════════════════════════════════════

## What S71 did

### 1. The capital/allocation question — SETTLED (reserve-per-rest wins)
Ran the greedy $5k pool on the real 42h Kraken book through the live path (`scripts/pool_book_kraken.py`,
`scripts/pool_capacity_honest.py`, `scripts/pool_aggressive_margin.py` — all committed, additive, baseline
byte-identical).
- **Real per-leg reachable capacity BINDS** = min(near-touch depth, taker flow); coins can't fill $5k on
  47–84% of legs (xrp real cap ~$4,291). The old "+14.5/hr" over-credited unreachable full-depth.
- **Honest number on $5k ≈ +9.65/hr** with **reserve-per-rest** (reserve the primary's cap, cascade the
  genuine leftover to backups — additive, never dilutive; Greg's thesis confirmed). Beats naive-cascade
  (+7.1, starves the primary) and A-with-idle-leftover (+9.51).
- **Aggressive/margin is NOT the direction:** deploying all coins to capacity runs the book at ~4.6x
  leverage *continuously* (5 coins live 92% of the time), and the margin OPEN FEE on high-churn turnover
  (~$14/hr over ~2000 fast legs) eats the leverage uplift → net +8.66 < +9.65. Revisit only if Kraken margin
  is balance-based not per-open. (Double-book is rare: XRP enters ~7.6/hr, true same-second collisions
  ~10/42h ≈ 0.24/hr; code reaction <1µs — the binding number is exchange RTT, a live measurement.)

### 2. The 16 Kraken candidates — fresh-tape SCREEN done (`KRAKEN_CANDIDATE_GRADES_S71.md`)
All 16 pulled + graded on fresh 14d tape via the live S54 gate. SEATs: **LTC** (confirmed, reproduced S67)
+ **BCH** (new, thin tape) + **TON/XPL** (⚠ thin-tape front-of-line magnitude artifacts — signal real,
capacity unknown, book-gate before sizing). 7 MARGINAL, 5 REJECT. No S67 verdict flipped. **Deploy gate =
on-book**, which needs Greg's manual "Run workflow" on the candidate book collector (session token 403s;
workflow has run 0 times — it's Greg's click) + days of accrual.

### 3. ⭐ THE SHAPE THREAD (the session's real discovery) — `SIGNAL_SHAPE_DIRECTION_S71.md`
Greg's reframe: stop reading signals as averaged scalars; read the **real-time CURVE** (the onset→exhaustion
ARC) — the trend in real time (the dipole is a trend-follower we'd been averaging the trend out of). Findings
(artifacts in `research/shape_s71/`):
- **The arc rhymes:** shape-matched btc trades correlate 0.97 vs 0.03/0.20 controls; the event-study mean
  over 2,394 legs is a textbook onset-force→exhaustion arc (flow builds pre-onset, peaks AT the turn, exhausts
  after; volume crests a few s later).
- **Two shapes (short-loser vs long-winner) are real** on all 5 cells (between-partition shape-distance ≫
  within). Long-winner = "took and rode" (tall onset peak, sustained plateau); short-loser = "tried and died"
  (low peak, immediate collapse). ⚠ this run was LED (Greg's prediction hardcoded) — the NEUTRAL unsupervised
  run was in-flight at close (see below).
- **The tradeable part (can't be led — OOS + shuffle-null):** the PRE-ONSET limb foretells the class
  out-of-sample, AUC **0.60–0.70 on all 5 cells**, shuffle-null z 1.8–2.6. The tell = onset-force **peak
  height** (taller → longer AND winning). Duration sets where the exhaustion collapse lands (mechanical).
- **Money (per-cell, stand-aside-on-predicted-short-losers = "bail the short shape"):** lifts doge
  (+61% $/hr, 75% legs kept), cuts the bleed on btc/xrp windows; on already-profitable eth/sol it trims good
  churn (leave un-gated). Per-cell, per the platform rule.
- **The false-start/spring** (small uptick → pushback → real launch): morphology is REAL and Greg's
  "averaging hides it" is confirmed (smears in the onset-aligned mean, sharpens when aligned on its own
  pushback time) — but it does not out-predict the smooth arc as a standalone profit filter.
- **Regrouped-by-type graph** (`kraken_types_regrouped.png`): the 4 types each on their own graph, all coins
  overlaid — the "does each type hold its shape across coins" view Greg asked for.

### 4. Standing principles added to `STRATEGY_INVENTORY.md` (Greg, S71) — load-bearing
- **#0d STRUCTURE IS SCAFFOLDING; ONLY NUMBERS ARE TUNABLE.** Fixed architecture, tune the numeric values to
  current conditions. + **reading-rule:** long-window averages give the scaffold; you trade the REAL-TIME
  CORRECTION; a flat long-window average never falsifies a live signal. + **churn corollary:** churn is neutral,
  fee-floor-bounded — profitable churn is more money, don't minimize trades. + **dipole = real-time
  trend-follower we averaged out.** + **the whole-ballgame decision surface:** direction × {entry, exit,
  quality, churn}, all read off ONE live curve. (Note: earlier "preemption thrashes / aggressive churn cost"
  verdicts were the averaging error — those trades were sub-fee in one low-edge window, not proof churn is bad.)
- **EPISTEMIC (Greg):** nothing "fails" — we listen to what the data tells us. Don't hardcode predictions into
  probes (let the data show it). Look at SHAPE, not per-cell averages. Neutral language.

### 5. Big idea logged — the AWS continuous re-tuner
A persistent agent continuously re-fitting the TUNABLE numbers (fill/capacity/ranking/timing thresholds) to
the LATEST book — regime-adaptive, persistence-gated, firing locked. It's the natural home of everything above
(one curve, tune thresholds on it). Blocked on: no authed AWS/Render workspace yet.

## Docs written this session (all committed)
`STRATEGY_INVENTORY.md` (#0d + corollaries), `SIGNAL_SHAPE_DIRECTION_S71.md`, `KRAKEN_CANDIDATE_GRADES_S71.md`,
`NEXT_WINDOW_WATCH_S71.md` (slight-edge persistence-watch), this handoff, + `research/shape_s71/` (scripts +
`quad_means.npz` + PNGs).

## In-flight at close / NEXT
- **IN-FLIGHT:** a NEUTRAL unsupervised shape-discovery + ROC-grid + regroup agent run was going at close (told
  nothing about what shapes to find — the clean test of whether short/long self-emerge). Its outputs land in
  scratchpad (ephemeral); re-run `research/shape_s71/shape_arc.py`/`two_shapes.py` logic on the book if not
  captured. The `quad_means.npz` values are saved — reuse, don't recompute.
- **NEXT (after Greg explains the graphs):** (1) the two remaining whole-ballgame legs — **EXIT-timing** (read
  the exhaustion/collapse limb LIVE → bail the short shape, ride the long one) and **direction-conditioning**;
  (2) a SECOND Kraken-book window to test the `NEXT_WINDOW_WATCH` candidates + confirm the pre-onset AUC
  persists; (3) Greg to trigger the candidate book collector so the 16 get their on-book grade; (4) scope the
  AWS re-tuner once cloud auth exists.
