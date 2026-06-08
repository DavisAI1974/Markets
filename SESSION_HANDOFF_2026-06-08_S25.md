# SESSION HANDOFF — 2026-06-08 — Session 25 (Markets: PySR/Julia toolchain FIXED; dipole VALIDATED real on the 128-dim per-pair basis; PySR discovery run)

WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR.
**WRITTEN-IN-STONE GUIDE: `BUILD_PLAN.md`** (commit `da9dc63`) — the approved OD / PySR-Julia rebuild plan.
Follow it to a T; any deviation cleared with Greg first ([[follow-canonical-plan-rule]]). Zero synthetic data;
Result Discipline in force.

## Headline
Cleared the S24 blocker (PySR/Julia now loads), then executed kickoff §0–§2 on the RIGHT basis. The markets
algebraic dipole is **REAL per pair on the original 128-dim `operator_coefficients`** — categorically
different from the S24 collapse, which was an artifact of the off-plan 15-dim pooled basis. Concretely:
reproduced the algebraic surface per pair, **validated the win/lose classifier honestly (z = +9.6 vs a
label-permutation null, on PRE-ENTRY no-look-ahead coefficients, all 12/12 pairs)**, and ran PySR per-pair
symbolic discovery. No code shipped to the repo yet; this was a fix-reproduce-validate-discover session.

## 1. Toolchain fix (durable) — the S24 "PySR hangs" blocker
Root cause: juliacall/juliapkg's first-run auto-download of Julia from `julialang-s3.julialang.org` STALLS —
the S3 mirror resets connections (curl itself died at 22 MB). Not a Python bug; it is `SETUP_julia_pysr.md`
failure-mode #4 (network policy / S3). Fix (LOCAL Windows machine — this session ran locally, not in a web
container):
- Pre-downloaded Julia 1.11.9 with a `curl -C -` resume loop (completed in 4 chunks), extracted to
  `C:\Users\A\.julia\juliabin\julia-1.11.9\`.
- Set user env `PYTHON_JULIAPKG_EXE = C:\Users\A\.julia\juliabin\julia-1.11.9\bin\julia.exe` (setx) → juliapkg
  uses this binary and SKIPS the broken download. SymbolicRegression.jl + 95 deps precompiled & cached in
  `C:\Users\A\.julia\`.
- VERIFIED: `import pysr` (1.5.10) + Julia 1.11.9, tiny fit recovers `2x0²+0.5x1` (loss 1e-14); cached import ~12s.
- Memory: [[pysr-julia-local-toolchain]]. Note the local hook is `scripts/session_start.sh` (always-on), NOT
  the web-only `.claude/hooks/session-start.sh` in `SETUP_julia_pysr.md`. Container/cloud path still unsolved
  (a fresh container would re-hit the S3 block unless Julia is pre-baked) — but local-vs-cloud "makes no
  difference" to Greg (S25).

## 2. STEP 1 — algebraic dipole reproduces per pair on real 128-dim coefficients
Ran the VERBATIM originals (on disk at `E:\Markets`): `_markets_algebraic_dipole.py` and `_markets_dipole_kfold.py`.
They read `E:\refrag\discoveries\operator_discoveries\<pair>_<win|lose>[_suffix]\*.json` → `result.operator_coefficients`
(confirmed **128-dim**), build win/lose centroids, project `Ha=<c,c_win>/||c_win||`, `Hb=<c,c_lose>/||c_lose||`,
fit `Ha² = a + b(Ha·Hb) + c(Ha·Hb)²`. Default (post-hoc) set, per-pair R²_quad: btc_bybit_sell 0.975,
eth_coinbase_sell 0.956, btc_kraken_buy 0.951, btc_kraken_sell 0.946, btc_coinbase_sell 0.925, eth_kraken_buy
0.910 (6/11 ≥ 0.91, convex +γ). **POOLED collapses to 0.493** → per-pair right, pooling wrong (this is exactly
the S24 failure mode). Quad beats linear on every strong pair → genuine structure, not the degenerate Hb=−Ha
tautology.

## 3. HONEST validation — the key result (real, not a D≫N artifact)
Added the two tests the kfold original lacked: a **label-permutation null** and a run on **pre-entry**
(no-look-ahead) coefficients. Harness: `C:\Users\A\AppData\Local\Temp\od_honest_val.py` (numpy-vectorized
nearest-centroid `Ha−Hb>0`, 5-fold, 200-perm null). On `_preentry_cs100` (100 win / 100 lose per pair):
- mean classifier accuracy **0.947**, AUC ~0.99–1.0, Cohen's d OOF +3.2..+5.9.
- label-permutation null collapses to **0.50 ± 0.045** → real-vs-null **z = +6..+11.6 on all 12/12 pairs**
  (mean +9.6, empirical p=0.000).
So the win/lose separation is genuine PREDICTIVE signal in the PRE-ENTRY operator coefficients — not a
high-dimension geometric artifact. (Random k-fold pooled was 0.976 = the old ~0.993 claim; that overstates,
BUILD_PLAN signal I — but the permutation null is what makes this trustworthy.)
Memory: [[dipole-real-on-128dim-per-pair]].

## 4. PySR per-pair discovery (kickoff §2 — discover, don't hardcode)
Harness: `C:\Users\A\AppData\Local\Temp\od_pysr_discover.py` (ops {+,−,*,/,square,cube,exp,log,sqrt}, 3 seeds
[11,22,33], target Ha² on x0=Ha·Hb, `_preentry_cs100`). Finding: PySR confirms the surface is real and
reproducible, but the crypto data prefers a **CUBIC** surface, not the hardcoded quadratic. 5 pairs land on an
IDENTICAL form across all 3 seeds (promote-able): btc_coinbase_buy `(x0+0.087)³` R²0.905; btc_coinbase_sell
`(x0+0.088)³` R²0.857; eth_bybit_buy `1.818·x0³` R²0.701; eth_coinbase_buy `1.456·x0³` R²0.725;
eth_coinbase_sell `1.376·x0³` R²0.687. The other 7 have high R² but seed-unstable forms (exp/sqrt/high powers =
overfitting). NOTE: the script's "convex&<5%" gate reads the x0² coefficient, so it mislabels the cubic pairs
"fail" — that is a gate-READOUT bug to fix (gate on the discovered dominant term), not a discovery failure.

## 5. The correct construction is ALREADY in the repo
`odcore/dipole_predictor.py` already carries the verbatim 128-dim construction (`build_centroids`, `project`,
`algebraic_dipole_over_trades`). S24's error lived in `odcore/dipole_trade.py` + `scripts/od_trade_dipole_run.py`,
which fed a **15-dim hand-built `c_i` + per-feature standardizer** (see its own docstring) instead of the raw
128-dim coefficients. The fix is a DATA-PATH change: feed `result.operator_coefficients` per pair, do NOT pool,
do NOT standardize.

## Data map (where everything lives)
- 128-dim coeffs: `E:\refrag\discoveries\operator_discoveries\<pair>_<win|lose>[_suffix]\*.json` → `result.operator_coefficients`.
  Suffixes: default (post-hoc, both sides), `_preentry` (20/20), `_preentry_cs100` (100/100 balanced — the HONEST
  set), `_preentry_cs100_v2` (WIN-ONLY, no losers). 12 pairs = btc/eth × bybit/coinbase/kraken × buy/sell.
- `E:\Markets\_full_pipeline_winners_preentry_cs100_v2\summary.json` = 1054 trades with `net_bps` (PnL label),
  asset/venue/side/horizon, but only `operator_coefficients_head` (TRUNCATED — full 128-dim is in the dir JSONs).
- JSONs carry NO trade timestamp (only processing wall_time_ms) → strict time-ordered walk-forward not yet possible
  from these files.

## HONEST STATUS (Result Discipline)
Strong, validated separability on the right basis — but still owed before any edge claim: (1) walk-forward / non-random
split (need a time/grouping key); (2) net-of-cost PnL backtest (BUILD_PLAN acceptance-b); (3) the larger trade-set run.
Outliers kept, not sanded: eth_bybit buy/sell are CONCAVE (−γ) surfaces vs the other 10 convex.

## What is NOT done → S26 (see `KICKOFF_2026-06-09_S26.md`)
- Run the LARGER trade set on the 128-dim per-pair basis (Greg's "run the larger set we did earlier").
- Walk-forward / grouped split + net-of-cost validation; fix the PySR promotion-gate readout; lock per-pair forms.
- Wire the corrected 128-dim construction into `odcore` generators (replace the 15-dim `dipole_trade` path).

## Pointers
- Plan: `BUILD_PLAN.md`. Next: `KICKOFF_2026-06-09_S26.md`. Prior: `SESSION_HANDOFF_2026-06-08_S24.md`.
- Temp harnesses (local, not in repo): `od_honest_val.py`, `od_pysr_discover.py`, `pysr_bootstrap.py` under
  `C:\Users\A\AppData\Local\Temp\`.
- Memory written this session: [[pysr-julia-local-toolchain]], [[dipole-real-on-128dim-per-pair]].

## Branch
WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets)
