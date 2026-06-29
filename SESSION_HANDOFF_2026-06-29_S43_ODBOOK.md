# SESSION HANDOFF — S43 (2026-06-29) — OD-BOOK gated T_test = KILL

Branch `claude/crypto-liquidity-signals-5c5vg9` (canonical S43 tip; harness landed me on the
stale S37 branch `2txotq` — switched to canonical per the S43 drop-in, dev/push here).

## What ran
NEXT #5 from the S43 kickoff: the **pre-registered, one-shot OD-BOOK T_test**
(`research/od_book/run_experiment.py --commit-ttest`), now that the book is multi-day.

- Data: `data/btc-book` → `btc_coinbase_book.jsonl.gz`, extracted to `/tmp/od_book.jsonl.gz`
  (`git show <ref>:btc_coinbase_book.jsonl.gz`). **1,259,450 states, 45 dims, 0 dropped,
  46.7 h (2803.5 min), 100 ms grid.** data_hash `7d69fda097989dc9`, sha `bb1b394`.
  (Book grew ~4× from S42's 11.67 h — the GHA has been accruing.)
- Discipline honored: KILL gate frozen (`KILL_GATE.md`) before the run; VAL-only pass first to
  validate plumbing (T_test untouched); single committed pass; sentinel `.ttest_committed.json`
  now refuses any second pass. Time-ordered splits with leakage asserts; train-only
  standardization; persistence-of-price R² baseline; turn metric net of 22 bps.

## VERDICT: **KILL** (anticipated KILL-mode #2 — prettier forecast, no edge after fees)

| leg | result | test detail |
|---|---|---|
| 1 forecast skill (mid R², ≥1 horizon) | **PASS** | OD (DMD r43) > VAR(3)/ridge at all 3 horizons OOS: chal +0.0120/+0.0049/−0.0043 vs champ −0.0045/−0.0086/−0.0168. Champion overfit val → negative OOS; rank-truncated operator generalized. |
| 2 turn net-of-22 bps | **FAIL** | both **−39.6 bps**; sub-bp moves never clear the fee floor. KILL for trading. |
| 3 operator stable | **PASS** | top-k drift 0.040 ≪ 0.15; radius ≈ 0.961 ± 0.008 over 6 walk-forward windows — no wander. |

Miss any one leg → KILL. Notable: this is **not** mode #1 (OD did not tie the linear model — it
beat it OOS and recovered a *stable* operator); it dies purely at the fee floor.

**Salvage (kept, not discarded):** the DMD operator wins `mid_price` (all 3 horizons) + `spread`
(h10) and is stable enough to serve as a **feature/gate/spread-adjuster** in the wider
architecture. Consistent with the standing pattern + S42: the book's tradeable content is a
MAKER/quoting signal below the active fee floor, not a taker strategy.

## Consequences (gate held)
- Dynamics-recoverer thesis for the book = **KILLED as a standalone strategy.** The validated
  dipole/imbalance **detector** stands.
- **Threads 2 (regime operator) and 3 (cross-asset transfer) are NOT built** (only on a PASS).
- The result could only be revisited by a **multi-venue** re-confirm (collector is btc_coinbase
  only) — and it would still have to clear this same frozen gate. Single venue/coin, ~2 days is
  the honest caveat on the KILL.

## Artifacts (committed)
- `research/od_book/od_book_result.json` — full scores, spectrum, gate, salvage.
- `research/od_book/.ttest_committed.json` — one-shot sentinel (KILL @ 2026-06-29T10:54:03Z).
- `research/od_book/README.md` — gated verdict section + §6 sequencing closed.

## LEG-2 POST-MORTEM (why turn-net-of-fee failed; `_leg2_diagnosis.py` / `_leg2_diagnosis.json`)
Greg: "not going to kill it yet — dive into why leg 2 failed." Diagnostic only; the frozen KILL
verdict (taker dynamics-recoverer) is unchanged — this dissects the *mechanism* on the TEST block.

**The leg-2 metric scores a TAKER swing** (flip on the forecaster's predicted next-cell sign, pay
22 bps round-trip per flip). It fails for one reason, three ways:
1. **Edge is ~140× below the taker fee.** Predicted forward move p99 = 0.11–0.16 bps at h=1; the
   round-trip taker fee is 22 bps. The signal predicts the *direction of 100ms wiggles*, not 22-bp
   swings.
2. **Gross is positive but tiny per flip** (+0.14 bps/flip champion, +0.30 bps/flip challenger at
   deadband 0; ~+4600 bps gross over the block — real captured direction). The taker fee swamps it:
   15k–33k flips × 22 bps = −330k to −713k net. Pure fee churn.
3. **No taker deadband rescues it.** Raising the deadband to cut churn just stops trading
   (predicted moves never exceed ~0.16 bps): db=5 → 2 residual flips → **−39.6 bps, exactly the
   committed gate number.** There is no taker operating point — the edge lives entirely below the
   fee floor.

**Execution-model counterfactual (the live lead).** Same positions, fee=0 → net = gross = **+~4600
bps** over 18.7h; both models flip positive. The challenger (DMD) is also materially **less churny**
than the champion (VAR): same gross with ~half the flips (15k vs 33k) → 2× gross/flip. So the
operator buys something on execution economics even though both fail the taker gate. **CAVEAT
(load-bearing):** fee=0 is an *optimistic upper bound* — it assumes fills at mid with zero adverse
selection / queue cost / 100% fill. A maker right about micro-direction gets *adversely selected*.
So +4600 is NOT deployable; it is the ceiling that justifies building the queue/adverse-selection
fill model (NEXT #3), not a result. Conclusion: **leg 2's failure is an execution-model artifact
(taker fee floor), not absence of signal** — exactly S42's "this is a maker/quoting signal, not a
taker strategy." The maker thread is NOT falsified; it needs the honest fill model.

**Bug found + fixed (`metrics.label_turns`).** `direction=0` made both `>=0`/`<=0` branches fire,
so the running extreme chased price both ways and it returned **0 turns** on real data. Fixed to
independent hi/lo tracking → **12 swings ≥22 bps over 18.7h, median amplitude 49 bps** (matches
S42's ~42 bps / θ≈20 bps and confirms the test window has real tradeable swings, range 141 bps,
6190 bps cumulative travel). The bug touched only the turn-timing/FN *diagnostic* fields; the gate
leg 2 scores swing PnL and never called it → **frozen verdict unaffected.**

## Other NEXT items (unchanged, still open)
1. More book data / **more venues+coins** = the bottleneck (needs Greg's manual GHA trigger).
2. Re-run `_liquidity_dive.py` + fit `QuietFloor` per cell once multi-cell book exists.
3. Maker-fill / queue-position model to monetize the sub-bp depth_imb predictor net-of-rebate.
4. Wire the QuietFloor gate into the live dipole.
