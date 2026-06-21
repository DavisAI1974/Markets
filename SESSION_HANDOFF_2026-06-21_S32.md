# SESSION HANDOFF — S32 (2026-06-21) — BUILD_PLAN crypto signal-core: Phase 0 + Phase 1(a) DONE; next = Phase 1(b)

**Open the new chat in the worktree `E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6`**
(branch `claude/crypto-trading-platform-plan-MpqwG`). `CLAUDE.md` now auto-loads there (renamed
from `CLAUDE (5).md` this session). Read order: `CLAUDE.md` (S32 delta at top) → this file → `BUILD_PLAN.md`.
Memories auto-load.

## SCOPE (Greg, S32 — hard)
Work ONLY on the **crypto trading platform** per `BUILD_PLAN.md` (the OD/PySR-Julia 5-step signal-core
rebuild). The **quote service** (`QUOTE_SERVICE_PLAN.md`, mm_passive/maker-rebate) is **OUT of scope** —
do not build it. "crypto trading platform" != "quote service". **Zero-synthetic** = no synthetic *trading*
data (signals/backtests/edge must be real bins); tool-validation synthetic anchors (a Brusselator to check
PySR recovers a known equation) ARE allowed. Memories: `scope-crypto-platform-only`, `zero-synthetic-scope`.
**Follow the plan step by step** (Greg).

## DONE THIS SESSION
- **Phase 0 — COMPLETE.** Engine (`odcore/operators.py`, `null_extract.py`, `leadlag.py`) was already built;
  the 3 real-bin acceptance tests pass (`tests/test_operator_real.py`: equal-entropy `(-1,-1,+2)/√6` recovery,
  known-lag lead-lag, tautology-null). The one missing deliverable — **`requirements.txt`** pinning the toolchain
  — was added (PySR **1.5.10** + numpy/scipy/scikit-learn/pytest); `scripts/session_start.sh` now installs from it.
  Commit `10646ce`.
- **Phase 1(a) — COMPLETE.** New `tests/test_symbolic_anchor.py` (2 passed). The discovery engine recovers the
  **convex chem dipole FAMILY two independent ways** on a Brusselator (tool-validation anchor):
  - algebraic fit (`fit_algebraic_dipole`): `c≈0.68`, `R²≈0.99`, **<2% cross-seed** (3 sim seeds).
  - PySR (Julia): rediscovers `square(H_a·H_b · 0.825)` → `c≈0.68`, identical across 3 seeds, loss 6e-6.
  - The reference `a=0.007, b=−0.093, c=1.309 (R²=0.943)` is a **PRIOR** from the original `basic_equations`
    ensemble construction (unreachable — BUILD_PLAN's documented open item). The `c≈0.68` delta is a **DATA POINT,
    not a failure** (Greg + Result Discipline). The anchor asserts the *form + reproducibility*, not the exact number.

## NEXT — Phase 1(b)/(c), then Phase 2 (per BUILD_PLAN "Phased execution" §1–2)
1. **Phase 1(b):** run PySR per-pair symbolic discovery on the **real cached bins** (`realbins/`, present in this
   worktree: btc/eth/doge/link × Coinbase/Kraken/Bybit) — discover the per-pair dipole form, promote a form only on
   **≥3 seeds, <5% coeff variation** (Result Discipline). S25 already saw a convex per-pair surface (data prefers a cubic).
2. **Phase 1(c):** confirm `dipole_predictor` consumes the discovered form. Lead-lag known-lag recovery is already
   covered (Phase 0 test).
3. **Phase 2:** scanner + strength meters + functional families + stacking wired into `AdaptiveSelector`.
   (Downstream, the real gate is Phase 3's net-of-cost acceptance — every OD signal has lost net-of-cost through S30;
   that's the eventual frontier, not Phase 1's concern.)

## ENV / TOOLCHAIN
PySR **1.5.10** imports; `PYTHON_JULIAPKG_EXE = C:\Users\A\.julia\juliabin\julia-1.11.9\bin\julia.exe` (Julia precompiles
on first fit). `realbins/` materialized in this worktree. **Fragile 4-CPU box** — keep PySR runs modest
(serial parallelism, moderate niterations); a 3-seed discover takes ~2 min.

## BRANCH NOTE (divergence — flag, don't silently reconcile)
This branch (`crypto-trading-platform-plan-MpqwG`) carries the master **body frozen at S25** (`CLAUDE (5).md`,
renamed → `CLAUDE.md` this session for auto-load). The fuller S26–S31 history lives on the **S30 line**
(`beautiful-shaw`/`lucid-dubinsky`/`suspicious-payne` @ `30c2d37`). **The S25-body dipole headline `z=+9.6` is
SUPERSEDED:** S29/S30 corrected it to a degenerate artifact → **real-but-weak gate piece, NO net-of-cost edge**
(`dipole-real-on-128dim-per-pair`, `markets-win-lose-pool-provenance-confound`). Do **not** cite `+9.6`.
If the two master lines need merging, that's a separate task to raise with Greg.

## ARTIFACTS / COMMITS (branch `claude/crypto-trading-platform-plan-MpqwG`)
- `requirements.txt` (new) + `scripts/session_start.sh` (reads it) — Phase 0 commit `10646ce`.
- `tests/test_symbolic_anchor.py` (new) — Phase 1(a).
- `CLAUDE.md` (renamed from `CLAUDE (5).md`, S32 delta + header bump) + this handoff.
- Scratch probes (`_anchor_probe.py`, `_anchor_pysr.py`) removed (folded into the test).
