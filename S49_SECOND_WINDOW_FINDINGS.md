# S49 FINDINGS — the 2nd-window gate PASSES: the maker-at-the-turn + cover-grace + two-factor-sizing edge reproduces out-of-sample on all 5 cells

Branch `claude/crypto-liquidity-signals-s49-rqtcfk` (reset onto canonical `5c5vg9` — the harness landed on a
stale S37-era branch with only a redundant `paper_trade.yml` commit, byte-identical to 5c5vg9's, so 0 work lost).
This is the gate the thread has been blocked on since S46 ("never tune off one window"). **It is now cleared.**

## The data finally rolled forward (the unblock)
The book cron advanced the alt branches to **2026-06-30 17:01Z** — the alt book now spans **06-29 11:49 → 06-30
17:01 = 29.2h** (was the single 11.7h S46/S47 window ending 06-29 23:29). The `paper_trade.yml` cron on the
default branch has ALSO been firing: `paper_ledger.jsonl` already carried forward trades to 06-30 11:10 before
this session. Running `scripts/paper_trade.py` here accrued **+3463** more (ledger total **22,702** trades).
btc spans an 8-day book (06-22 → 06-30, 196h).

## The test (out-of-sample, FIXED parameters)
`scripts/_s49_window_confirm.py` segments the deduped forward ledger at the end of the original window:
- **W1** = in-sample `[book start .. 2026-06-29 23:29Z]` (the S46/S47/S48 window everything was built on)
- **W2** = **fresh / out-of-sample** `[23:29Z .. now]`

The strategy parameters (WFLIP=600, REV=0.10, per-cell GRACE, alpha=1.0, roll=200, K) were all fixed on W1 and
applied UNCHANGED to W2 — so W2 is a genuine out-of-sample test of the deployed executor, not a refit.

## Result — REPRODUCES on all 5 cells
| cell | W1 net/leg | **W2 net/leg (OOS)** | W1→W2 sized/leg | W2 win% | W2 taker% | W2 sizing lift/leg |
|------|-----------|----------------------|-----------------|---------|-----------|--------------------|
| sol  | +1.94 | **+1.59** | +2.55 → +1.74 | 63% | 0% | +0.15 |
| doge | +1.42 | **+1.28** | +2.06 → +2.10 | 58% | 7% | +0.82 |
| xrp  | +1.33 | **+1.02** | +1.47 → +1.21 | 61% | 1% | +0.19 |
| eth  | +0.69 | **+0.46** | +0.89 → +0.61 | 52% | 0% | +0.15 |
| btc  | +0.55 | **+0.34** | +0.71 → +0.57 | 59% | 0% | +0.23 |

The three load-bearing claims from S47/S48 ALL hold out-of-sample:
1. **Net-of-fee stays POSITIVE on every cell** in the fresh window (mk0/tk5). Sign and per-cell ranking
   (sol > doge ≈ xrp > eth ≈ btc) preserved.
2. **Cover-grace holds the taker rate near 0%** out-of-sample (doge 7%, others 0–1%) — the S48 execution fix
   is structural, not window-fitted. DOGE stays profitable (the S47 "47% taker kills it" cell).
3. **Two-factor conviction sizing adds positive lift on all 5 cells** out-of-sample (+0.15 to +0.82/leg);
   doge gets the biggest lift (+0.82), consistent with S47's "the size axis activates doge."

W2 net/leg sits modestly below W1 (e.g. sol +1.94→+1.59, eth +0.69→+0.46) — a real regime softening, not a
collapse; the edge is thinner but intact and the same shape.

## Honesty / what is still NOT proven
- The fill model is still OPTIMISTIC (any opposing trade lifts the fixed maker limit; same model both windows,
  so the RELATIVE reproduction is fair, but absolute bps are an upper bound). A price-level-aware venue queue
  converts fewer covers — the true edge sits below these numbers.
- Everything is GROSS of the real exchange fee schedule beyond the modeled mk0/tk5. **The whole edge requires
  maker fee ≤ 0** (S47: even a 1 bp maker fee is fatal at 2–4 bps mean swing). Confirming Coinbase's actual
  maker fee/rebate for these cells is the next hard gate (job #2) and is a business fact, not a backtest.
- Two windows is two, not many. The forward ledger now accrues automatically (the cron is live) so the
  out-of-sample record keeps growing — keep watching it.

## Leakage gate (mandatory, before any sizing-for-real)
`scripts/_s49_conviction_leakage.py` runs `odcore.leakage.assert_no_leakage` on BOTH conviction factors
(clmx_60 quality axis + the size_score axis) at the decision cells, per cell — the Architect's mandatory
pre-wiring discipline. **RESULT: PASS on all 5 cells** (sol/doge/xrp/eth/btc, both axes, 120 sampled flip
cells/cell × 3 corruption reps). The conviction signal at the flip cell is invariant to all data after it —
no look-ahead. The pivot used in dive_depth is causal (forward ZigZag, depends only on lean[0..i]).

## What got wired (S49)
- `odcore/swing_maker.py`: `SwingLeg.size` field + **`size_legs(legs, quality, size_axis, *, alpha, roll)`** —
  the two-factor conviction sizing (causal rolling rank+z, `clip(1+α·z)`) extracted from `paper_trade.py`
  into the executor module so the script AND the per-cell emit path share ONE leakage-clean implementation.
  Verified **bit-identical** to the prior inline pass (max |Δsize| = 0.0 on a 500-leg synthetic check).
- `scripts/paper_trade.py`: now calls `size_legs` instead of its inline pass (no behavior change).
- `scripts/_s49_window_confirm.py`, `scripts/_s49_conviction_leakage.py`: the two S49 gates.

## Job #2 — maker fee ≤ 0 on Coinbase — ANSWERED (the binding deploy gate)
Checked Coinbase Advanced Trade's published fee schedule (2026):
- **Maker fee floor is 0.00% (ZERO), never negative.** Reached only at the TOP volume tier (**$250M+/30d**),
  or via the fee-upgrade program (proof of **≥ $500K/mo** volume on another venue → fast-track to as low as
  **0.0% maker**). Retail/low tiers are **0.25%–0.60% maker = 25–60 bps**, i.e. ~10–30× the 2–4 bps mean swing
  → categorically fatal (consistent with S47's mk1 = fatal).
- **A true maker REBATE (negative fee) does NOT exist on Coinbase.** So S47's "mkRebate-0.5 rescues XRP/ETH /
  fattens SOL/BTC" scenario is **NOT achievable on Coinbase** — it requires a different venue (a rebate-paying
  book). The OD-BOOK collection is Coinbase-only today.
- **The deployable scenario is mk0/tk5 (zero maker).** The cover-grace executor clears it net-positive on all 5
  cells OOS (this session) — but **mk0 on Coinbase requires the top VIP tier (or the fee-upgrade program).**
  Below that tier the strategy is NOT deployable on Coinbase as-is.
- **DECISION for Greg (S50):** deploy is gated on EITHER (a) qualifying for Coinbase's zero-maker tier
  (top VIP / fee-upgrade with ≥$500K/mo proof), OR (b) standing up book collection + execution on a venue that
  pays a maker rebate (then S47's rebate column — which rescues XRP/ETH and fattens SOL/BTC — comes back).

## NEXT (still gated)
1. **Pick the deploy venue path** per the job-#2 decision above (Coinbase zero-maker tier vs a rebate venue).
   Until a maker ≤ 0 venue is secured, the deploy set is provisional.
2. Wire `size_legs` into the per-cell **emit path** (a sizing analogue of `odcore/quiet_registry.py`:
   per-cell alpha/roll + deploy flag) once #1 confirms a venue that pays maker ≤ 0.
3. Keep watching the auto-accruing forward ledger — a 3rd, 4th window strengthens the OOS record further.
DEAD (don't re-chase): entry-timing retiming, wrong-tail entry-gates, spread/dive as timing.
