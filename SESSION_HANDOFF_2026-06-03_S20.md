# SESSION HANDOFF — 2026-06-03 — Session 20 (Markets: OD signal-core rebuild)

Branch: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR.
Scope: rebuild the crypto trading platform's SIGNAL CORE around the Operator-Discovery
(OD) discoveries in the master context (`CLAUDE (5).md`), on REAL collector data. All
Operating Rules + Result Discipline in force. Zero synthetic data (Greg's call).

## Headline
Built a new `odcore/` package that brings the real OD machinery into the Markets repo
(which previously had only a crude order-flow-imbalance "dipole"). The full pipeline runs
end-to-end on REAL bins, and PySR symbolic regression (Julia backend) discovers equations
from real market data. Honest Result-Discipline outcome: the OD coupling structure is REAL
and significant, but the signals buildable from the UNBLOCKED pieces have NO net-of-cost
edge yet — the directional chem dipole, whose exact construction lives in the access-blocked
`Basic_equations` repo, is the missing piece. Nothing fabricated; nulls reported.

## What was built (all committed + pushed)
`odcore/` (every equation RECONSTRUCTED-FROM-CLAUDE.md; originals would port from
`Basic_equations`):
- `operators.py` — windowed basis [H_a,H_b,H_a^2,H_b^2,H_a*H_b,MI]; Vasicek marginal
  entropy + KSG(k=4) MI; window=40/stride=10 (INFO-012). anti_frac sufficiency proxy.
- `null_extract.py` — centered-SVD null (no z-score; MI scale-invariant, INFO-051);
  coupling decomposition {equal-entropy / MI / residual}; biology MI-slope + chemistry
  residual-fraction strength meters; `analyze_coupling()` with INFO-041/INFO-024 guards.
- `leadlag.py` — raw cross-cov-over-lag detector (the S19 right tool, INFO-066): who moves
  first, z vs time-slide null.
- `dipole_predictor.py` — algebraic (chem) dipole `H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2`
  least-squares fit + directional `H_a>H_b` rule.
- `symbolic.py` — PySR (Julia) discovery of dipole/MI equations from raw operator data
  (ops {+,-,*,/,square,cube,exp,log,sqrt}; INFO-025). VERIFIED working on real bins.
- `coupling_scanner.py` — score/rank pairs; tautology-killing circular-shift null (INFO-066)
  on lead-lag AND operator-structure; `rolling_coupling` + `detect_decoupling` events.
- `channels.py` — channel factory (orderflow/internal/cross-venue/cross-asset) + INFO-051
  conditioning + pair enumerator.
- `io.py` — single real-bins loader (BinSeries, gap-fill, minute resample, cadence-aware
  `align`). Loads the data/* branch bins from gitignored `realbins/`.
- `validation.py` — walk-forward/block CV + embargo; real fees+slippage; random-vs-
  walkforward gap (INFO-026); tautology-killing signal null.
- `sizing.py` — OD-native sizing (residual-fraction + dipole R2 + leadlag stability,
  calibrated to measured edge); Kelly only as a comparison helper (Greg: not gold standard).
- `stacking.py` — compose operators (weighted_sign/majority/unanimous) + coupling gate
  ("they never stacked", l.124).
- `generators.py` — real-bin OD signals + bridge to `adaptive_backtester.SignalGenerator`.
- `scripts/` — `od_real_run.py`, `od_scan.py`, `od_pysr_discover.py`, `od_backtest.py`,
  `od_xvenue_backtest.py`, `session_start.sh`.
- `tests/` — `test_operator_real.py`, `test_leadlag_real.py` on REAL bins (3 pass).
- `.claude/settings.json` — Bash allowlist + SessionStart hook (PySR/Julia + real-bins
  bootstrap, guarded).

## Real-data findings (Result Discipline)
- **Pipeline + PySR/Julia work end-to-end on real bins.** PySR (1.5.10, the log's pin)
  discovered, from real BTC order-flow, `MI ~= -0.028*H_a*exp(H_b) + 0.023` (loss 0.0013).
- **Equal-entropy attractor reproduces on real data**: quad |cos| to (-1,-1,+2)/sqrt6 =
  0.9996 (the log's >=0.9994). INFO-041 control holds.
- **Cross-venue coupling is real + huge z**: Coinbase<>Bybit-perp lag-0 cc=0.656 z=580;
  spot venues looser (cc~0.24). Venues synchronous at 1s (sub-second leads need tick data).
- **145 real decoupling events** on Coinbase<>Bybit (coupling mean 0.57, collapsing at
  dislocations) — the tradeable regime signal.
- **HONEST NULL — no net-of-cost edge from unblocked pieces.** All simple signals lose to
  3bps costs (flip every bar): ofi_momentum WF -178%, dipole_direction -12%, tautology-z ~1.
  Cross-venue reversion is STATISTICALLY REAL (tautology z=3.0-3.6 at 10s) but per-trade
  edge < cost -> net negative. The harness correctly REJECTS these. This is why the chem
  dipole matters.
- **Chem QUADRATIC dipole does NOT reproduce on reconstructed channels.** Real buy/sell
  entropies are near-symmetric (H_a~=H_b) -> trivial identity H_a^2~=H_a*H_b, c~=0; nothing
  scores "structured". Tried 5 channel types x 3 timescales x 3 conditionings. Either a
  channel/preprocessing mismatch vs the original `_markets_algebraic_dipole.py`, or a genuine
  construction-not-nature result. NOT fabricated.

## BLOCKER (needs Greg)
`DavisAI1974/Basic_equations` ("Dipole equations for 4 life sciences") is ACCESS-DENIED this
session (scope locked to `davisai1974/markets`). It holds `_markets_algebraic_dipole.py`,
`s13_chemistry_residual.py`, `s12_coupling_decomposition.py` — the exact chem-dipole recipe.
ACTION: add `Basic_equations` (and maybe `od-engine`, `evolution`) to the session's allowed
repos, then the originals port verbatim and run on the real bins.

## Decisions made (best judgment; in BUILD_QUESTIONS.md)
- Zero synthetic enforced; synthetic.py + synthetic tests removed; tests run on real bins
  (lead-lag uses a known lag INJECTED into a real return series).
- New `odcore/` package; existing platform shell untouched (no destructive housekeeping
  while unattended).
- KSG + Vasicek estimators; global channel conditioning (INFO-051) — note this symmetrizes
  buy/sell, possibly the wrong choice for the chem dipole (pending the blocked recipe).

## Open questions for Greg (see BUILD_QUESTIONS.md)
1. Add `Basic_equations` to scope (top priority).
2. Maker-fee/rebate venue or tick data? The cross-venue signal is real (z=3) but cost-bound;
   cheaper execution could flip it positive.
3. Want a single labeled known-law fixture to prove PySR rediscovers a governing equation?
   (Would be the only synthetic; currently omitted per zero-synthetic.)
