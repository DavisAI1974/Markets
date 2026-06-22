# SESSION HANDOFF — 2026-06-07 — Session 22 (Markets: chem-dipole construction resolved + core ported)

WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR.
Commits this session: `d129c19` (code) + the docs/master commit that follows.
Master context: `CLAUDE (5).md` (now canonical through S22). All Operating Rules + Result
Discipline in force. Zero synthetic data.

## Headline
S22 priority #1 (the chem dipole) is RESOLVED and the verbatim-safe core is ported + pushed.
Prior sessions assumed the originals lived in `DavisAI1974/Basic_equations` while access-denied
and never verified it. They are NOT in `Basic_equations` (Greg checked) and NOT in the Markets git
history (searched all 15 refs). The verbatim original is a LOCAL untracked file at
`E:\Markets\_markets_algebraic_dipole.py`. It settles the "what are H_a/H_b" question:

    H_a_i = <c_i, c_win_centroid> / ||c_win_centroid||     # c_i = per-trade operator-coefficient vector
    H_b_i = <c_i, c_lose_centroid> / ||c_lose_centroid||
    fit   H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2          # per pair + pooled

So H_a/H_b are NORMALIZED PROJECTIONS of a per-trade operator-coefficient vector onto in-sample
win/lose centroids -- NOT windowed Vasicek entropy of buy/sell volume. The odcore reconstruction
used the latter, which is the entire reason the quadratic coefficient collapsed to c~=0 (near-
symmetric buy/sell window entropies -> H_a ~= H_b -> H_a*H_b collinear with H_a^2 -> gamma
unidentified). Epistemic rule #4 (S19) confirmed: tool-wrong, not signal-absent.

Greg's steer: the two other "missing" files (`s12_coupling_decomposition.py`,
`s13_chemistry_residual.py`) are ALREADY reimplemented in `odcore/null_extract.py` (the current
5-step coupling model), so they need no port. Only `dipole_predictor.py` was reconstructed wrong.

## What was built + pushed (commit d129c19)
- `odcore/dipole_predictor.py` REWRITTEN to the verbatim construction:
  `build_centroids(C, labels)` / `project(c, c_win, c_lose)` / `algebraic_dipole_over_trades(C, labels)`.
  Legacy window-based `fit_algebraic_dipole(M)` KEPT (coupling_scanner imports it) as a descriptive
  operator-matrix fit, clearly marked not-the-predictor. Numeric self-check under `__main__`.
- `odcore/dipole_trade.py` NEW: wires the dipole onto the current 5-step coupling model.
  - `trade_coupling_vector(a, b)`: runs `analyze_coupling` + `fit_algebraic_dipole` + `detect_leadlag`
    on a trade's pre-entry window -> 15-feature c_i (decision #1, Greg-approved).
  - per-feature `Standardizer` (deviation from the homogeneous-128-dim original; documented + justified
    -- heterogeneous features need standardizing before centroid projection).
  - `fit_trade_dipole(trades)` (IN-SAMPLE; reproduces the original report) + `predict(model, a, b)`.
  - Portable: takes `(a, b, label)` tuples; NO platform-shell imports (S21 portability rule).

## Decisions (Greg-approved this session)
- #1 c_i = the 5-step coupling model's per-trade feature vector (15 dims); labels from
  backtest / paper trade outcomes.
- Per-feature standardization before centroid projection (heterogeneous features; necessary).
- Hybrid delivery: land the verbatim-safe core now; finish/validate the plumbing in the run env.

## Environment gotcha (IMPORTANT for next session)
`E:\Markets\.claude` is HARD-LOCKED on this Windows box (exFAT, open handle): git could not
stat / checkout / rename / delete it, so an in-place branch switch was impossible. WORKAROUND USED:
worked entirely from git refs (`git show ref:path`) and committed via git plumbing (temp
`GIT_INDEX_FILE` + read-tree / hash-object / update-index / write-tree / commit-tree / push) with NO
working-tree checkout. Do not fight the lock; either work-from-refs + plumbing, or use the container.
Also: avoid `Remove-Item` while cwd is `E:\Markets` (a sandbox guard blocks it).

## HONEST STATUS (Result Discipline) -- edge unchanged
Reproducing the algebraic R^2 is a STRUCTURAL "markets = 5th science" check, NOT a net-of-cost edge
(in-sample centroids are self-referential; H_a^2 vs H_a*H_b hugs a low-D curve by construction). The
directional / combined predictor must clear `odcore/validation.py`: net>0 after real fees+slip,
beat baseline + buy-hold under embargoed walk-forward, tautology z>>2-3, small random-vs-WF gap.
S20/S21 showed the unblocked OD signals LOSE net-of-cost. Nothing here changes that until validated.

## What is NOT done (S23 priority 1)
- A runner (scripts/) that pulls labeled win/lose trades + each trade's aligned pre-entry channel
  arrays from the executor / `adaptive_backtester` trade store (data shapes not yet mapped), feeds
  them to `dipole_trade.fit_trade_dipole` / `predict` with WALK-FORWARD centroids, and validates via
  `odcore/validation.py`.
- Then, only if it clears the gate, the WIRE step (flow od_* fields through /api/signals + /api/stream).

## Pointers
- Next kickoff: `KICKOFF_2026-06-07_S23.md`
- Session CLAUDE note: `CLAUDE_session_note_2026-06-07_S22.md` (fold into `CLAUDE (5).md`, bump header)
- Verbatim original: `E:\Markets\_markets_algebraic_dipole.py` (local, untracked)
- Prior: `SESSION_HANDOFF_2026-06-05_S21.md`, `KICKOFF_2026-06-05_S22.md`

## Branch
WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets)
