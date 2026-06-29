# OD-BOOK — Order-Book Dynamics Operator (S36b, markets timing line)

Thread 1 of the Architect's "OD as dynamics-recoverer, not just detector" vision
(`EXP_book_dynamics_operator_1.md`). Falsification-first, pre-registered KILL gate
(`KILL_GATE.md`). Threads 2 (regime operator) and 3 (cross-asset transfer) are
built ONLY if thread 1 clears its gate.

**Question:** Does OD recover a *governing operator* for short-horizon order-book
evolution that out-predicts a strong classical forecaster (VAR/ridge) out-of-sample
— or does it KILL? Per the standing pattern (OD recoverable in physics/chem/geology
but NOT where a strong linear model already absorbs the signal), a KILL is a live,
expected outcome. That is the framework working.

## Data

L2 order-book snapshots from `coinbase_btcusd_book_collector.py` — top-10/side
resting-size depth + spread + signed trade flow, on a regular **100 ms** grid,
gzipped JSONL. Collected on GitHub Actions (`book_collector_btc.yml`) to the
`data/btc-book` branch. This captures the *resting-size book state* the existing
trade-bin collectors discard (they keep only `{buy,sell,mid,high,low,n_trades}`).

> Activation note: GitHub fires `schedule:`/cron only from the **default** branch.
> While the workflow lives on the feature branch it runs via `workflow_dispatch`;
> recurring cron collection needs it enabled on the default branch.

## Pipeline (status)

| Module | Purpose | Status |
|--------|---------|--------|
| `coinbase_btcusd_book_collector.py` (repo root) | L2 capture, top-K grid snapshots | **built + live-validated** |
| `book_collector_btc.yml` (workflow) | durable GHA collection → `data/btc-book` | **built** (dispatch-ready) |
| `book_state.py` | load snapshots → compact x(t) state matrix | **built + tested on real sample** |
| `splits.py` | walk-forward, time-ordered split discipline | **built** |
| `KILL_GATE.md` | pre-registered metrics + pass/fail bar | **frozen** |
| `champion.py` | VAR(p) + ridge one-step baseline | **built** |
| `challenger_od.py` | OD operator recovery (exact-DMD + spectrum) | **built** |
| `metrics.py` | OOS R² + turn-as-consequence (net 22 bps) + spectrum stability | **built** |
| `run_experiment.py` | §6 sequencing, one-shot-guarded T_test | **built** |
| `test_smoke.py` | single-window plumbing/early-read (NOT the gated test) | **built** |

### Early read (single 18.8-min local window — NOT the gated T_test)
Plumbing validated end-to-end on real BTC book data. On this one window the DMD
operator **ties the VAR/ridge** (mid_price R² 0.076 vs 0.078 at 100ms; champion
ahead at 500ms/1s), and the net-of-22bps swing PnL is deeply negative for *both*
(fee floor dominates at 100ms–1s, ~200 flips/window). This is the spec's
anticipated KILL-modes #1 (linear model absorbs the dynamics) and #2 (no edge
after fees) showing early. **Not a verdict** — the gated decision runs ONCE on the
multi-day `data/btc-book` dataset via `run_experiment.py --commit-ttest`.

### GATED VERDICT (S43, 2026-06-29) — **KILL** (one-shot pass committed; sentinel frozen)
Single T_test pass on the multi-day `data/btc-book` dataset (1,259,450 states, 45
dims, 0 dropped, **46.7 h** = 2803.5 min, 100 ms grid; data_hash `7d69fda097989dc9`,
sha `bb1b394`). Result in `od_book_result.json`; sentinel `.ttest_committed.json`
locks the pre-registration (a second pass is refused).

| KILL-gate leg | result | test detail |
|---|---|---|
| 1. forecast skill (mid R², ≥1 horizon) | **PASS** | OD challenger (DMD r43) BEATS the VAR(3)/ridge champion at all 3 horizons OOS: chal +0.0120/+0.0049/−0.0043 vs champ −0.0045/−0.0086/−0.0168. The strong linear champion overfit val → negative OOS; the rank-truncated operator generalized. |
| 2. turn net-of-22 bps fee | **FAIL** | both net **−39.6 bps**; sub-bp moves never clear the fee floor (deadband 5 bps lets 2 flips through, both lose). KILL *for trading*. |
| 3. operator stable (no wander) | **PASS** | top-k spectral drift 0.040 ≪ 0.15; radius ≈ 0.961 ± 0.008 across 6 walk-forward windows. |

**Verdict: KILL** (miss any one leg). This is anticipated **KILL-mode #2** (prettier
forecast, no tradeable edge after fees) — explicitly NOT mode #1: OD did not merely
tie the linear model, it out-forecast it OOS and recovered a *stable* operator.
**Salvage (reusable, not discarded):** the DMD operator wins `mid_price` at all 3
horizons + `spread` at h10 and is stable enough to serve as a feature/gate/
spread-adjuster in the wider architecture. Per the gate, the dynamics-recoverer
thesis for the book is KILLED as a standalone strategy; the validated dipole
*detector* stands; **threads 2 (regime operator) and 3 (cross-asset transfer) are
NOT built.** Caveat: single venue/coin (btc_coinbase), ~2 days — a multi-venue
re-confirm is the only thing that would revisit this, and it would still need to
clear the same frozen gate.

## x(t) state vector (45-dim default, K=10)

`mid_ret, spread, tob_imb, depth_imb, flow` + per-level `bid_sz_k / ask_sz_k /
bid_off_k / ask_off_k`. Absolute `mid` kept separate (non-stationary) for
reconstructing the predicted price trajectory in the turn metric. Small + explicit
by design — dimensionality is the enemy of clean operator recovery.

## Sequencing (spec §6)

1. ✅ x(t) extractor + walk-forward splitter; freeze splits.
2. ✅ Fit champion (VAR + ridge). Record OOS skill = the bar.
3. ✅ OD recovery on T_train, tune on T_val; inspect operator spectrum.
4. ✅ Freeze metrics + KILL gate in writing (`KILL_GATE.md`).
5. ✅ Single T_test pass. Both competitors. Score. → **KILL** (S43; `od_book_result.json`).
6. ✅ Logged in-repo (`od_book_result.json` + this README; no E:\ `MASTER_DISCOVERIES.json` in cloud).
7. ⛔ Does NOT pass → threads 2 / 3 NOT built (gate held).
