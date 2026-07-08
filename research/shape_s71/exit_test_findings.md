# S75 BALANCE-EXIT test — findings (SOL / BTC / ETH / XRP)

**First real test of the exit/turn read through the LIVE executor.** VERDICT up front:
**the balance exit does NOT beat the current exit on any of the 4 majors.** It cuts WINNERS
without rescuing LOSERS, so every configuration that materially fires loses money vs baseline.
Result-disciplined negative. Details + the mechanism below.

## What was built (LIVE code, opt-in, canary bit-identical)
The finding this test rests on (S74): post-onset the WINNER's signed trade-imbalance tail holds
`>= 0` to close (flow de-energizes, never flips); the LOSER's tail decays THROUGH zero into strong
negative (`exh ~ -0.2..-0.4`) — the flow reverses onto the other side mid-tail, and THAT reversal
is the loss. Hypothesis: exit each leg EARLIER, when its with-ride flow-lean decays back to balance
(`<= exit_lo`), to catch the loser's flip at the zero-cross while keeping winners (who end `~= 0`).

An existing socket already implemented this shape: `swing_maker.lean_exit` (S55 R8) — arm when the
with-ride lean is strongly positive, close on the first collapse to `exit_lo`, via maker-preferred
cover machinery. But it is mutually exclusive with `exit_spec` (the deep-bail that BTC/ETH use) and
`run_kraken_cell` never wired it. So a minimal **opt-in `balance_exit=(arm_hi, exit_lo)`** was added
to `odcore/swing_maker.py` and threaded through `odcore/platform.py::run_stream / run_kraken_cell`:

- Walks the with-ride flow-lean `side*lean[t]` per open leg (the SAME imbalance the flip detector
  runs on — no new signal type). Arms at `arm_hi` (so it can't fire at the low-lean entry), then the
  first decay to `<= exit_lo` closes via the **unchanged** maker-preferred cover machinery
  (cover-grace + front-of-line + taker fallback). Only the CLOSE TRIGGER is new.
- **Coexists with the deep-bail**: both triggers are walked in ONE per-leg scan, EARLIEST cell wins,
  so the protective price_stop is preserved exactly (BTC/ETH). Mutually exclusive with `lean_exit`.
- Lean window is configurable (`bal_lean_w`): tested **200 cells (20s, the S74 characterization
  window)** and **600 cells (60s, the executor's own WFLIP flip-lean)**.
- Legs closed this way carry `SwingLeg.bal_exit=True`. Default `balance_exit=None` → byte-identical.

**CANARY (bit-identical, all 4 coins):** with `balance_exit=None`, `simulate_swing_maker` reproduces
the pre-S75 executor leg-for-leg (side/open/close/net/close_maker/stop_exit) — SOL 1522, BTC 2395
(deep-bail price_stop intact), ETH 1459 (deep-bail intact), XRP 1518. Firing is untouched.
Test script: `research/shape_s71/exit_balance_test.py` (+ `exit_balance_grid.py`). Not committed.

Run scope (one book window/coin, in-sample PROVISIONAL): SOL 1522 legs/73.1h, BTC 2395/41.9h,
ETH 1459/67.3h, XRP 1518/73.1h. CAP = $5000/leg. Exit-flow measured with the 20s lens (matches S74).

---

## The money: BASELINE vs balance-exit thresholds (per coin, $/hr @ $5k)

`arm_hi=0.15`. `dVS` = $/hr delta vs baseline. `losFlow` = mean with-ride imbalance (20s) of LOSER
legs at close (the "does the loser exit nearer 0?" test). `win$/hr` / `los$/hr` split the $/hr.

### 20s lean window (the responsive, S74-characterization window)
| coin | config | $/hr | dVS base | win% | nBal | loser-exitflow | win-$/hr | los-$/hr |
|------|--------|------|---------|------|------|----------------|----------|----------|
| **SOL** | BASELINE | **+11.26** | — | 61.7 | — | −0.227 | +29.90 | −18.64 |
| SOL | exit_lo +0.10 | +7.16 | −4.10 | 60.3 | 788 | −0.223 | +25.70 | −18.54 |
| SOL | exit_lo −0.10 | +8.44 | −2.82 | 61.2 | 681 | −0.253 | +26.92 | −18.49 |
| **BTC** | BASELINE | **+2.49** | — | 69.4 | — | −0.344 | +25.95 | −23.46 |
| BTC | exit_lo +0.10 | −3.74 | −6.23 | 69.6 | 1130 | −0.343 | +20.51 | −24.24 |
| BTC | exit_lo −0.10 | −2.91 | −5.41 | 69.7 | 1021 | −0.364 | +21.17 | −24.08 |
| **ETH** | BASELINE | **+5.47** | — | 53.5 | — | −0.187 | +26.16 | −20.69 |
| ETH | exit_lo +0.10 | −1.24 | −6.71 | 50.9 | 732 | −0.214 | +19.17 | −20.42 |
| ETH | exit_lo −0.10 | +0.31 | −5.16 | 51.7 | 637 | −0.222 | +20.30 | −19.99 |
| **XRP** | BASELINE | **+2.47** | — | 51.5 | — | −0.201 | +28.11 | −25.64 |
| XRP | exit_lo +0.10 | +0.50 | −1.97 | 52.2 | 835 | −0.178 | +23.05 | −22.55 |
| XRP | exit_lo −0.10 | +0.94 | −1.53 | 52.3 | 745 | −0.217 | +24.24 | −23.30 |

**Every firing config at every threshold loses vs baseline** (dVS −1.5 to −6.7). The `win-$/hr`
column drops on all 4 coins (winners cut 15–25%). The `los-$/hr` column does NOT systematically
improve (BTC/ETH worse; SOL flat; XRP improves +3 but is swamped by the −5 winner cut).

### 60s lean window (the executor's OWN WFLIP flip-lean)
Barely fires — **nBal = 0–10 legs** across all thresholds, all 4 coins → $/hr `~=` baseline
(deltas +0.00 to +0.17, all from < 11 legs = noise). **Reason (load-bearing): the current
flip-turn exit ALREADY IS a lean-collapse exit at the 60s scale** — the flip detector zigzags on
the WFLIP=600 lean, so a "turn" is declared exactly when the 60s lean reverses. A 60s balance exit
is therefore redundant: the price turn has already closed the leg before the 60s lean decays to the
threshold. So the balance exit only adds anything at a FASTER window (20s/40s), and there it loses.

### Robustness grid (SOL, load-once): no config beats baseline
arm_hi ∈ {0.05, 0.10, 0.20, 0.30, 0.40} × window ∈ {20s, 40s, 60s} × exit_lo ∈ {+0.05 … −0.20}:
- 20s: dVS −2.8 to −4.3 (fires 640–790). 40s: dVS −1.9 to −2.7 (fires 360–430). 60s: 0 (subsumed).
- **Low arm_hi (0.05/0.10) — so weak-onset LOSERS arm and could be caught earlier — still loses**
  (dVS −2.0 to −2.9): winners cut 29.90→26.8–28.5, losers unchanged ~−18.4 to −19.4. There is no
  corner of the grid where the balance exit beats the current exit.

---

## Loser rescue? NO. Winner integrity? CUT. (the two diagnostic questions)

**Loser rescue — does the loser exit-flow move from ~−0.3 toward 0?** No. With the balance exit ON,
the surviving losers still close at strongly-negative flow (SOL −0.227→−0.226; BTC −0.344→−0.345;
ETH/XRP unchanged-to-more-negative). Loser net_bps and los-$/hr do not systematically improve.
**Why the premise fails:** a loser is a mislabeled wrong-side entry (S63/S74). By the time its FLOW
returns to balance, the adverse PRICE move is already realized — the flow-flip LAGS the price loss,
so "catch the flip at the zero-cross" catches it too late to cut the loss. Worse, the losers we'd
most want to rescue have a WEAK onset surge (S74: short-lose peak ~+0.14 vs long-win ~+0.37), so
they often never arm — the exit can't touch them. The legs it DOES fire on are the energized rides.

**Winner integrity — are winners kept?** No, they are cut. `win-$/hr` falls on every coin
(SOL 29.90→25.7–26.9, BTC 25.95→20.5–21.2, ETH 26.16→19.2–20.3, XRP 28.11→23.0–24.2). **Why:** a
winner's FLOW de-energizes back to ~0 while its PRICE gain HOLDS and keeps running to the actual
price turn (exactly the S74 "winner holds >= 0 to close"). Exiting when the flow hits balance is
EARLIER than the price turn, so it hands back the winner's residual upside. The hypothesis assumed
"winners end ~= 0 anyway so a zero-cross exit captures them" — but the executor already rides them
to the price turn (the next flip), which is LATER and richer than the flow-balance point.

**Net:** winners are cut MORE than losers are saved → negative on all 4 coins, all firing configs.

---

## Best threshold per coin + verdict

| coin | best FIRING config (20s/40s) | vs baseline | best OVERALL |
|------|------------------------------|-------------|--------------|
| SOL | 20s, exit_lo −0.10: +8.44 | **−2.82 (worse)** | 60s (subsumed) = baseline +11.26 |
| BTC | 20s, exit_lo −0.10: −2.91 | **−5.41 (worse)** | 60s (subsumed) = baseline +2.49 |
| ETH | 20s, exit_lo −0.10: +0.31 | **−5.16 (worse)** | 60s (subsumed) = baseline +5.47 |
| XRP | 20s, exit_lo −0.10: +0.94 | **−1.53 (worse)** | 60s (subsumed) = baseline +2.47 |

The only non-negative deltas are the 60s-window configs that fire on < 11 legs (noise, +0.00 to
+0.17) and do NOT survive the train(60%)/test(40%) split as a real effect (e.g. BTC "best" test
$/hr −0.34 vs baseline −0.12 — worse OOS). There is no threshold that beats the current exit.

## VERDICT
**Exiting at the flow-return-to-balance does NOT beat the current exit, on any of the 4 majors.**
It cuts winners without rescuing losers. Two clean reasons:
1. **The current exit already captures the balance-exit idea at the trade's own scale** — the
   flip-turn IS a 60s flow-lean collapse. The balance exit only differs at a faster window, where
   it fires prematurely.
2. **The S74 asymmetry is real but not tradeable as an early exit** — winners' flow returning to 0
   is NOT a signal to leave (their price gain holds to the later price turn), and losers' flow
   returning to 0 is too LATE (the loss is already in the price). The flow-flip lags the price, so
   catching it early cuts good rides and misses the bad ones.

The right place to act on the S74 loser/winner asymmetry is at ENTRY (winners vs losers are a
direction/side question — S63/S74 "winners are invisible to causal flow reads at exit"), not by an
earlier flow-based CLOSE. The deep-bail already caps the loser TAIL at the price level (−80/−100bp),
which the price lens handles better than the flow lens. `balance_exit` stays OPT-IN, default OFF,
adopted nowhere.

## Files
- `odcore/swing_maker.py` — opt-in `balance_exit` param + `SwingLeg.bal_exit` + unified deep-bail/
  balance walker (default None = byte-identical; canary PASS all 4 coins). NOT committed.
- `odcore/platform.py` — `run_stream` / `run_kraken_cell` route `balance_exit` + `bal_lean_w`.
- `research/shape_s71/exit_balance_test.py` (baseline vs sweep + canary + train/test),
  `research/shape_s71/exit_balance_grid.py` (robustness grid).
