# SESSION HANDOFF — S33 (2026-06-21) — channel construction UNBLOCKED; dipole is centroid-based (not bins); decision = Path C (de-confound)

**Open the new chat in the worktree `E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6`**
(branch `claude/crypto-trading-platform-plan-MpqwG`). `CLAUDE.md` auto-loads. Read order: `CLAUDE.md`
(S33 delta at top) → this file → `BUILD_PLAN.md`. Memories auto-load (esp. `markets-dipole-construction-is-centroid-based`).

## SCOPE (unchanged, hard)
Crypto trading platform per `BUILD_PLAN.md` only. Quote service OUT. Zero-synthetic = no synthetic *trading*
data; tool-validation synthetic anchors OK. Follow the plan; clear deviations with Greg.

## HEADLINE — the S20 "unreachable basic_equations" blocker is RESOLVED, and it changes Phase 1(b)
1. **The `_markets_*` scripts were never truly unreachable** — they are **local (untracked)** in `E:\Markets`
   (`_markets_algebraic_dipole.py`, `_markets_dipole_kfold.py`, `_markets_dipole_separation.py`,
   `_markets_dipole_chunker_stack.py`, `_markets_dipole_crosspair.py`, `_markets_dipole_residual_kfold.py`,
   `_markets_dipole_export_centroids*.py`, `_markets_combined_info_flow_kfold.py`, `_markets_flow_features_sep.py`,
   `_markets_gate_v2.py`). The S20 "blocked" note was a sandbox artifact. `DavisAI1974/Basic_equations` (cloned to
   `E:\basic_equations_src`, now public) holds **only the four-sciences chem construction** (`static_dipole_test.py`,
   `pysr_symbolic_per_domain.py`), NOT the `_markets_*` files — its own docs say markets lives in `agent`+`Markets`.
2. **The real markets dipole is CENTROID-based, not bin-based.** From `_markets_algebraic_dipole.py`: each trade has a
   **128-dim OD `operator_coefficients` vector** (per-pair, stored in `E:\refrag\discoveries\operator_discoveries\<pair>_<win|lose>[suffix]\*.json`
   — **present locally, 148 dirs**). Per trade: `H_a = <c, c_win_centroid>/||c_win_centroid||`,
   `H_b = <c, c_lose_centroid>/||c_lose_centroid||`. Fit `H_a² = α + β(H_a·H_b) + γ(H_a·H_b)²`. 12 pairs =
   btc/eth × bybit/coinbase/kraken × buy/sell.
3. **=> odcore's BUILD_PLAN Phase 1(b) reconstructed a DIFFERENT object** (operator basis from windowed entropies of
   price **bins**). That is why the S33 bin-based canary gave **c≈0** (btc cross-venue: numpy c=0.0004, PySR landed
   LINEAR; MI weakly ~ −0.10·H_b). Sweeping more bin-channels will NOT recover the original — the original never used
   bins for the dipole. The bin track is a clean but *separate* (and so far null) construction.

## CHRONOLOGY INVESTIGATION (Greg's recollection, scored on evidence)
- **"chem dipole first, then OD, OD newest" — CONFIRMED.** Universal chem algebraic dipole validated first (S22–S25,
  ~06-07/08; the `z=+9.6` headline). OD-coefficient line is newest: regeneration + honest re-validation S26–S30
  (06-09…06-13); cleanest data `*_preentry_cs2000_clean` dated **2026-06-11**.
- **"different dipoles per coin" — directionally right, mis-attributed.** All 12 pairs used the SAME universal form
  (no per-coin *equation* discovered), but each pair has its own 128-dim coeffs → own centroids → own dipole
  *direction*. Cross-pair transfer (run this session, cached, on `preentry_cs2000_clean`) shows the direction is
  **hierarchically shared**, AUC (imbalance-robust; accuracy is junk here — winners are 3–20% of each pair):
  - SELF (in-sample ceiling): AUC ~0.71–0.83 (pooled acc 0.683)
  - SIBLING buy↔sell: **AUC 0.716** (best)
  - CROSS-ASSET btc↔eth (the per-coin test): **AUC 0.673** (mostly holds, no collapse)
  - CROSS-VENUE: **AUC 0.609** (weakest; **kraken is the outlier venue** — AUC 0.30–0.58)
  => non-universality is **per-VENUE (kraken)**, not per-coin. Side ≈ asset > venue.
- **The clean data is STILL provenance-confounded.** `_preentry_cs2000_clean` win pool = 05-23/24 (chunkhash
  missed-winners), lose pool = 05-04/11 (backtest slices) — disjoint in time AND pipeline. So the `_clean` suffix did
  NOT fix the same-period confound; the transfer structure above is of the *confounded* direction, NOT proof of real
  coupling. (See `markets-win-lose-pool-provenance-confound`, `dipole-real-on-128dim-per-pair`.)

## DECISION — Path C (Greg): de-confound, then test if the dipole is real coupling
Build the centroid dipole with **winners AND losers from the SAME same-period universe** (the documented fix:
discover same-period losers within the 05-23/24 winner universe, not 05-04/11 slices). Then:
1. **Construct same-period win/lose pools** (same dates, same pipeline) → generate/locate matching OD 128-dim coeffs.
2. **Re-run the centroid dipole** (`_markets_algebraic_dipole.py` form) + per-pair AUC with a within-period
   permutation null. Real separation that survives same-period = evidence of genuine coupling, not a date detector.
3. **Re-run cross-pair transfer** on the de-confounded pools → settle universal-vs-per-coin honestly (expect to keep
   kraken-as-outlier or not). Decide whether Path-C fits ONE shared form, per-asset, or per-venue (kraken-separate).
4. Promote nothing without the same-period null passing AND net-of-cost (the S30 frontier).
**PER-CELL, NOT UNIVERSAL (Greg, S33 — `deploy-signal-per-cell-not-universal`):** report results PER asset×venue×side and
DEPLOY on the cells that survive — partial coverage is NOT failure, and a signal is never thrown away for failing on
some cells. Output is a deployment map ("works on {X}, not {Y}"), never "the dipole failed." This is what the
`AdaptiveSelector` ("data picks the winner per source") already implies.
NOTE: `_markets_*` scripts + `operator_discoveries` data live under **main `E:\Markets` / `E:\refrag`** (absolute paths
in the scripts), NOT in this worktree. The Path-C tooling should be authored as tracked files on this branch but reads
those absolute paths. Decide early whether to copy the relevant `_markets_*` scripts into `odcore/` as the Path-C base.

## STATE / ENV
- **Git recovery done this session:** main `E:\Markets` was accidentally branch-switched (dialog) to
  `xenodochial-montalcini-f21fb6` with a stash; reverted cleanly back to `claude/run-pass-14-classifier-nTViL`
  (307 files restored from `627abef`), junk `stash@{0}` dropped. Do NOT branch-switch the shared `E:\Markets` folder
  (4+ sessions share it) — work Path C in this worktree or via absolute paths.
- Worktree clean on `390280c` (Phase 0 + 1a done). PySR 1.5.10 + Julia 1.11.9 work (preflight green this session).
- **Lightsail** (deferred): free-tier too small (burstable, throttles); Greg has **$100 credits**. If a full sweep is
  needed, 4–8 vCPU bundle (~cents for a 1–2 hr run); the real setup cost is the guarded Julia+PySR bootstrap (S24
  mirror-hang risk). For Path C (pure numpy dot-products on local JSON) NO remote needed — runs locally in seconds.
- Scratch this session (untracked, cleanable): `_phase1b_canary_btc_xvenue.log`, `outputs/` (PySR), `_xpair_cached_tmp.py`
  in this worktree / `E:\Markets`; `E:\basic_equations_src` clone.

## ARTIFACTS
- Bin-based canary (Phase 1b attempt): `scripts/od_pysr_discover.py` works; result = no convex dipole on bins (c≈0).
- Cached cross-pair transfer: `E:\Markets\_xpair_cached_tmp.py` (numbers above).
- Memory written: `markets-dipole-construction-is-centroid-based`.
