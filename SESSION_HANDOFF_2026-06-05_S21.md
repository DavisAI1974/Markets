# SESSION HANDOFF — 2026-06-05 — Session 21 (Markets: OD layer wired into platform)

Branch: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR.
Scope: continue the S20 OD signal-core rebuild — surface + wire the OD machinery through the
platform (backend API, frontend, executor) and do the safe housekeeping. All Operating Rules +
Result Discipline in force. Zero synthetic data. The chem-dipole port (S21 priority #1) stayed
BLOCKED this session (Greg is fetching the `Basic_equations` files); everything below is the
unblocked Section-2 build from `KICKOFF_2026-06-03_S21.md`.

## Headline
The OD coupling layer is now plumbed end-to-end through the running platform: a backend store
computes the coupling matrix / lead-lag / dipole / strength / decoupling from the REAL bins and
serves them on 5 new API endpoints; a new frontend "Coupling" tab renders them; the executor
now wires the OD generators, OD-native sizing, and a circuit-breaker. Housekeeping: 5 duplicate
bar loaders consolidated to one; DEMO_MODE defaulted off. HONEST STATUS UNCHANGED: re-ran the
promotion gate on real BTC this session — every unblocked OD signal still LOSES net-of-cost
(dipole_direction walk-forward -11.8%, tautology z=1.2; ofi/momentum far worse). The OD layer is
DIAGNOSTIC/shadow, NOT the live signal source yet. Nothing fabricated; nulls reported.

## What was built (all committed + pushed)
- `backend/odcore_store.py` — `CouplingStore`: loads realbins, computes the OD layer, caches a
  snapshot, refreshed off the polling loop ON A THREAD (compute ~84s, self-gated to 600s,
  lock-guarded against overlap). Functions: coupling matrix (lag-0 |cc| + structured verdict),
  cross-venue lead-lag (z vs time-slide null), per-source algebraic dipole (a,b,c,R2 + H_a>H_b
  dir), rolling strength meters (MI-slope / chem-residual), decoupling events.
- `backend/api_server.py` — 5 new authed endpoints reading the cached snapshot:
  `/api/coupling_matrix`, `/api/leadlag/{asset}`, `/api/dipole_signals`,
  `/api/strength/{asset}/{venue}`, `/api/decoupling`; OD status added to `/api/health`; OD
  refresh wired into `_polling_loop` via `asyncio.to_thread`.
- `frontend/` — new "Coupling" tab: `components/CouplingMatrix.jsx` (heatmap, structured pairs
  ringed), `LeadLag.jsx`, `StrengthOverTime.jsx` (recharts), `DecouplingFeed.jsx`,
  `pages/Coupling.jsx` (composes them; dipole table drives strength selection), api.js client
  fns + App nav/route. `npm run build` passes.
- `adaptive_backtester.py` — `build_generators()` now appends
  `odcore.generators.make_od_generators()` so the OD operators compete in the rolling-Sharpe pool.
- `executor/risk.py` — `gate_circuit_breaker` (trips after `max_consecutive_losses` trailing
  closed losers on a source; 0 disables) + config fields `od_sizing`, `position_floor_usd`,
  `max_consecutive_losses`.
- `executor/executor.py` — `_size_notional`: OD-native sizing (`odcore.sizing`) when
  `cfg.od_sizing` and the signal carries `od_*` confidence inputs; else fixed size. Sized-out
  signals skipped + audited. PaperExchange stays default (no live-exchange change).
- Housekeeping: `markets_adapter.load_minute_bars` is now the SINGLE minute-bar loader; the 5
  duplicate copies (adaptive_backtester / backtester / autoresearch_lite / phase1_5_evaluator /
  backend SignalStore) all delegate. Housed in markets_adapter (not odcore/io.py) to keep odcore
  free of platform-shell imports so it stays portable to Basic_equations; `odcore.io.load_bins`
  remains the separate 1s BinSeries loader. `MARKETS_WATCH_DEMO_MODE` now defaults "0".

## Real-data findings (Result Discipline) — re-verified this session on realbins
- CouplingStore smoke run (6 sources, minute bars): ETH Coinbase<>Kraken lag-0 cc0=0.92;
  BTC Coinbase<>Kraken structured (mi_frac=0.92); Bybit-perp leads spot by 1 bar (60s) at minute
  cadence; chem quadratic c~=0 on the reconstructed channels (as S20 found); 68 decoupling events.
- HONEST PROMOTION GATE re-run (`scripts/od_backtest.py --source btc_coinbase --fee 2 --slip 1`,
  15,396 minute bars, buy-hold -4.52% over window): ofi_momentum WF -177.9% (taut z 1.9),
  ofi_fade -188.2%, momentum5 -91.8%, dipole_direction -11.8% (taut z 1.2). NOTHING clears the
  bar. Confirms the S20 null on fresh re-run.

## Greg's question this session: "what do we have to do to make OD the source?"
Two separate things — EARNING it (validation) and WIRING it (plumbing). Wiring is easy; earning
is the real work and is NOT done. The promotion bar (already coded in `odcore/validation.py`):
net_return > 0 after real fees+slippage, beats baselines under walk-forward (embargoed OOS),
survives the tautology null (z >> 2-3), small random-vs-walkforward gap. Current OD signals fail
all of these. The two candidate paths to an actual edge: (1) the chem QUADRATIC dipole (the `c`
term) with the EXACT channel construction from `Basic_equations` — c~=0 on reconstructed channels,
so the real recipe is the prime candidate (BLOCKED, files incoming); (2) cheaper execution /
maker-rebate venue or tick data — cross-venue reversion is statistically real (tautology z 3.0-3.6)
but cost-bound. Full plan in `KICKOFF_2026-06-05_S22.md`.

## Decisions made (best judgment)
- OD layer kept ADDITIVE/diagnostic; did NOT make it the live signal source (no net edge — would
  ship a losing signal). Regime classifier remains the source.
- Shared loader housed in `markets_adapter` (not odcore/io.py as the kickoff literally said) to
  preserve odcore's independence from the platform shell. Recorded here as a deviation.
- OD-native sizing and circuit breaker are OPT-IN (off by default) so live behavior is unchanged
  until configured.
- The session's master-context "fold" was already done by S20 on this branch; only added the
  ALREADY-FOLDED-IN guard (per Greg "make a note so next session doesn't redo this"). The stale
  `claude/session-upload-handoff-cy7wQ` branch (a redundant fold on a base missing odcore/) should
  be deleted — remote delete kept failing with a git-proxy network error this session.

## BLOCKER (still needs Greg) — unchanged from S20
Add `DavisAI1974/Basic_equations` to session scope so `_markets_algebraic_dipole.py`,
`s13_chemistry_residual.py`, `s12_coupling_decomposition.py` port verbatim and the chem dipole
(Piece 1, the prime edge candidate) can be reproduced on the real bins. Greg is fetching these.

## Open decision carried to S22 (asked Greg, answer pending action)
"Unwire PELT from the signal path" (S21 housekeeping): flipping the live backend chunker
hybrid->fixed changes the regime-classifier signal path (still the actual source). Greg's reply
was the question above ("what to make OD the source"). DECISION: defer the PELT unwire until OD is
validated as the source — they are paired for exactly that reason. See kickoff.
