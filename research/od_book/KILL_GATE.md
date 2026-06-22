# OD-BOOK — PRE-REGISTERED KILL GATE (frozen before T_test)

**Experiment:** Order-Book Dynamics Operator (OD-BOOK), thread 1 of the Architect's
OD-in-markets vision. Branch S36b (markets timing line).

**One-line question:** Does OD recover a *governing operator* for short-horizon
order-book evolution that out-predicts a strong classical forecaster out-of-sample
— or does it KILL?

This file is written and committed **before T_test is ever touched.** Metrics and
the pass/fail bar are frozen here. No quiet metric-swapping after seeing T_test; no
re-running until it passes. A clean KILL is a successful outcome of the framework.

---

## Competitors (both run classically, same frozen windows, scored identically)

- **CHAMPION (classical, must be genuinely strong):** VAR(p) on x(t), order p
  selected on T_val; plus a ridge one-step linear predictor (alpha on T_val).
- **CHALLENGER (OD):** operator-recovery of A mapping x(t) -> x(t+Δ) (exact-DMD
  with rank truncation chosen on T_val; piecewise/regime-segmented variant as the
  "piecewise Liouvillian" analogue). Report A's spectrum and dominant modes — OD's
  value is an *interpretable* operator. If A is just the VAR matrix in disguise,
  that is itself an informative result (OD found nothing the linear model didn't).

Only the predictor varies. Same x(t), same targets, same frozen splits.

## Horizons (map to 100ms grid)

- 1 step = 100 ms
- 5 steps ≈ 500 ms
- (intermediate) ≈ 100–500 ms

## Metrics (frozen)

**Primary**
1. **Multi-step forecast skill:** out-of-sample R² of x(t+Δ), per component, with
   emphasis on `mid` (via integrated `mid_ret`), `spread`, and `tob_imb` /
   `depth_imb`. Challenger vs champion, at each horizon.
2. **Turn-as-consequence (the only money metric):** derive the turn signal from
   each forecaster's predicted mid trajectory; score bps-to-true-turn and FN-rate
   at matched FP, **net of the 22 bps round-trip fee floor.** A forecast that is
   prettier (higher R²) but no closer to the turn after fees is a KILL *for trading*.

**Secondary / diagnostic**
3. Operator spectrum stability across walk-forward windows (does the same A keep
   getting recovered, or does it wander?). A wandering operator = no stable
   dynamics = KILL.
4. Which component OD wins/loses on, if it splits.

## KILL GATE (the bar)

OD-BOOK is **KILLED** unless, out-of-sample on T_test, the challenger:

1. **exceeds** the champion on multi-step forecast skill at **≥1 horizon**, AND
2. that edge **translates to a turn-timing or FN improvement that survives the
   22 bps fee floor**, AND
3. is **stable across walk-forward windows** (operator does not wander).

**Miss any one of the three → KILL** the dynamics-recoverer thesis for the book.
Keep the validated dipole *detector*; stop here. Threads 2 (regime operator) and
3 (cross-asset transfer) are built ONLY if this passes.

## Anticipated KILL modes (so we recognize them fast)

- OD ties the VAR everywhere → the linear model already absorbs the dynamics
  (expected per the standing pattern: OD recoverable in physics/chem/geology but
  NOT where a strong linear model already absorbs the signal). Clean KILL.
- OD wins on R² but not after fees → prettier forecast, no tradeable edge. KILL for
  trading.
- Operator wanders across windows → no stable governing dynamics in the book. KILL.

## Discipline

- Walk-forward, time-ordered, no shuffling across the boundary (`splits.py` asserts
  this). Random shuffle is the leakage mode that produced the unvalidated
  0.993/FN=0 dipole.
- T_test touched exactly once, after this gate is committed.
- Every discovery → MASTER_DISCOVERIES.json immediately, KILL or not.
- CPU-scale only. Any proposed GPU spend before the gate clears = scope creep.
- Save to E:\Markets\ and mirror to F:\Factory\knowledge\.

---

*Status: frozen at scaffold time. Champion/challenger/metrics implementations land
next, then a single T_test pass once enough real book data has accrued. Pre-entry
leakage discipline applies to any downstream signal, same as the algebraic dipole.*
