# Rebuild the Markets signal core around Operator Discovery (OD)

## Context

`CLAUDE (5).md` (committed as the new master research log, identical to the upload) is a
19-session log of "Operator Discovery" — a domain-agnostic method that extracts governing
equations from raw data. Markets is treated as the "5th science." The current
`/home/user/Markets` platform is a mature shell (exchange collectors + durable GitHub
Actions, FastAPI backend with SSE/auth/push, React frontend, paper-only executor with risk
gates, PELT chunker, backtester, operator registry) — **but its only "dipole" is crude
order-flow imbalance** `(buy_vol - sell_vol)/(buy_vol + sell_vol)`. None of the real OD
machinery the log developed is in this repo (the original scripts live in the separate
`basic_equations`/`agent` repo, which is **not reachable from this session**).

Goal: **reuse the shell, rebuild the signal core** around the real OD discoveries, in a new
`odcore/` package — equations reconstructed from the log (line-cited below). Build BOTH the
coupling scanner AND the directional predictor on one engine, let the process discover which
channels carry the strongest signal, strip/​unwire the cruft the repo accumulated, and wire
toward live with OD-native (not textbook-Kelly) sizing and honest validation.

### Honest framing (load-bearing, per the log's own Result Discipline)
The owner wants "100% winners betting max bank." No system delivers that, and max-bank sizing
blows up a real edge on the first losing streak. The log itself says the ~0.993 dipole accuracy
is **random-CV**, which **overstates** out-of-sample on correlated series (INFO-026, line 617).
So we build the strongest signal the pieces allow, prove it with **walk-forward** validation +
a **tautology-killing null**, and size from **measured OD confidence** with circuit breakers.
That is how a real edge is kept, not thrown away.

---

## The OD parts list we are implementing (with log cites)

- **A. Windowed operator basis + centered-SVD null** — basis `[H_a, H_b, H_a², H_b², H_a·H_b, MI]`,
  window=40 / stride=10; **center (do NOT z-score)** then SVD, smallest singular vectors = the
  null; rank-3 null subspace (INFO-022, l.609; INFO-012, l.597). The `(-1,-1,+2)/√6`
  equal-entropy attractor is a **geometric artifact / baseline to project out**, not signal
  (INFO-012/036/051, l.597/1033/2009).
- **B. Coupling discriminator** (INFO-040 l.289-373; INFO-041 l.375-390) — decompose `null[0]`
  into {equal-entropy, MI, residual} axes. **MI entering the null ⇒ structured, law-like
  coupling**; the INFO-041 control proves generic correlation creates MI but it does NOT enter
  the null — so this discriminates *structured* coupling from mere correlation.
- **C. Two strength meters** — **biology** = MI-vs-H_a **slope** (`MI ≈ 0.28·H_a`, slope tracks
  coupling knob g; INFO-040 l.340). **chemistry** = **residual-fraction** of the fixed relation
  `0.54·H_a + 0.54·H_b + 0.32·H_a² − 0.55·H_b² ≈ 0`, which rises monotonically with the
  Brusselator-B knob (0.169→0.342→0.400; INFO-044 l.1495-1512).
- **D. PRIMARY signal — static algebraic (chem) dipole** `H_a² = a + b·(H_a·H_b) + c·(H_a·H_b)²`
  (chemistry coeffs `a=0.007, b=−0.093, c=1.309, R²=0.943`, l.287), with the directional
  `H_a > H_b` rule (~0.993 **random**-CV, l.244).
- **E. CRITICAL S19 finding — the entropy/flow dipole is the WRONG tool** (INFO-065/066,
  l.890-945). `dMI/dt ~ Σ c_self·H_i² + Σ c_cross·H_i·H_j` is FLAT on real data because windowed
  marginal entropies are lag-independent, so coupling/time info never enters them
  ("tool-blindness"). What DOES carry it: **(1) raw cross-covariance over lag** → recovers
  lead-lag timing (7.32 ms in LIGO; |cc| z=37 in GPS), and **(2) the static algebraic dipole**
  (D). In crypto, (1) = a **cross-venue / cross-asset lead-lag detector** (who moves first, by
  how many bars). Design AROUND this; do not build the flow dipole.
- **F. Tautology-killing null** (INFO-066 l.913) — circular-shift one channel: preserves
  smoothness + shared factor, kills only the instantaneous pairing. The rigorous proof a
  coupling/dipole excess is real (event z=2.7 genuine vs noise z≈0 tautology). Standard
  validation gate.
- **G. Per-domain functional families** (INFO-025 l.280-285) — physics `(H_b−H_a)²+c`, biology
  `0.5·exp(H_a/2)`, chemistry `linear in H_a`, geology `const`. Candidate operators to try per
  pair; data picks.
- **H. Algebraic ratio** `C = H_self/H_cross` (l.274) — a by-scale meter per pair.
- **I. Stationarity** (INFO-026, l.617) — chemistry is the **only** stationary domain → the
  **only one with positive walk-forward** (+0.4..+0.8 vs −0.5..−80). This is *why* the chem
  dipole transfers cleanly and survives honest validation. Report the **random-vs-walkforward
  gap** as a stationarity signature.
- **J. MI is the only scale-invariant quantity** (INFO-051, l.1051) — marginal-entropy asymmetry
  is a units choice. Normalize channels so MI is the physical content; don't read asymmetry as
  signal.
- **K/L. Estimator + confidence** — KSG kNN MI holds (INFO-034); **singular-gap** = null-direction
  confidence; **anti_frac ≈ 1/N_eff** = data-sufficiency flag (INFO-017/024).
- **M. "They never stacked"** (l.124) + the `_markets_dipole_chunker_stack` concept (l.246) —
  the edge is in composing pieces others used singly.
- **N. Order-flow DIVERGENCE + EXHAUSTION reversal detector (S36, `odcore/info_dipole.py`).** The raw
  order-flow dipole `(buy−sell)/(buy+sell)` used NOT as a direction predictor but as a
  trend-continuation-vs-**FLIP** detector — the per-cell signal that fills the S35b "bleed" (the
  side-AGNOSTIC 128-dim coeff cannot encode direction). Frame: markets are mostly follow-the-leader (a
  trend = a flow) until the leader exhausts → new leader, usually opposite; the edge is detecting the
  changeover. Two validated factors STACK: (1) **DIVERGENCE** `aligned_flow = imb_level·sign(price_drift)`
  (<0 = flow opposes price); strong divergence (≤−0.20) → ~65% reversal, temporally stable, 6/7 cells.
  (2) **EXHAUSTION** = the dipole COLLAPSING toward 0.5 (|late imbalance| < |early|, leader weakening —
  Greg's "dipole→0.5 = change in flow"; the MOVE toward balance, NOT the discrete crossing, which is a
  coin flip). Combined: oppose+exhaust **64% reversal** vs with-trend+strengthen **49%** (healthy trend).
  **REINFORCES Part E:** the entropy/differential flow (dMI/dt, `mi_flow`) is a TREND ARTIFACT (vanishes
  under detrend + temporal OOS) — only the raw order-flow LEVEL divergence is real, exactly E's "design
  around the raw signal, not the entropy flow." Per-cell, never pooled; deploy gated on net-of-cost.

---

## Approach: new `odcore/` package, reuse the shell

```
odcore/
  operators.py        # A,J,K: basis, KL/Vasicek marginals, KSG MI (k=4), build_operator_matrix(window=40,stride=10)
  null_extract.py     # A,L: center(not z-score)+SVD, rank-3 null, singular_gap, anti_frac, project_out_equal_entropy
  coupling.py         # B,C: decompose null -> {eqEnt,MI,residual}; structured-vs-correlation; MI-slope + residual-fraction meters
  leadlag.py          # E: raw cross-cov over lag, argmax-lag = who-moves-first, z vs time-slide null  (the S19 right tool)
  dipole_predictor.py # D: PRIMARY algebraic surface fit per (asset,venue,pair) + residual-fraction strength + H_a>H_b rule
  symbolic.py         # PySR + Julia symbolic regression: DISCOVER the dipole/coupling equation from raw
                      #   crypto operator data (Piece 1), not hardcode it; ops {+,-,*,/,square,cube,exp,log,sqrt}
  functional_families.py # G: physics/biology/chemistry/geology candidate forms; data selects
  channels.py         # channel constructors (cross-asset, cross-venue, order-flow, price/vol, exogenous); MI-preserving normalize (J)
  coupling_scanner.py # enumerate pairings; rank by structured coupling gated by tautology-null (F); emit DECOUPLING events
  stacking.py         # M: compose dipole + leadlag + strength + families into one stacked generator
  info_dipole.py      # N: order-flow divergence + exhaustion -> per-cell trend-continuation-vs-FLIP detector (S36)
  validation.py       # I,F: walk-forward/block CV + embargo; random-vs-walkforward gap; fees+slippage; tautology null; baselines
  sizing.py           # OD-native sizing (NOT Kelly): residual-fraction + live R^2 + leadlag stability, calibrated to measured edge
  generators.py       # SignalGenerator wrappers so odcore plugs into the existing AdaptiveSelector
  io.py               # single load_bars (consolidates 5 duplicate loaders)
executor/sizing.py                  # bridge odcore.sizing -> position size (replaces fixed position_size_usd)
executor/exchanges/ccxt_adapter.py  # env-gated real adapter; PaperExchange stays default
tests/  test_synthetic_coupling.py, test_dipole_predictor.py, test_leadlag.py, test_validation.py
```
Every `odcore/*` equation header marked **RECONSTRUCTED-FROM-CLAUDE.md**, naming the original
`basic_equations` script it would be a verbatim port of (so the repo can be added later and diffed).

### Plug-in points (reuse, don't rebuild)
- **MarketChunker** (`markets_adapter.py:237`): the new path uses odcore's own window=40/stride=10
  and does **not** call `chunk()`. **Keep the class, unwire it from the signal path** (per
  directive). It stays available for regime-history/exploratory segmentation only.
- **SignalGenerator / AdaptiveSelector** (`adaptive_backtester.py:51-163`): `odcore.generators`
  returns `SignalGenerator`s; they drop into the existing rolling-Sharpe selector unchanged. Extend
  the single-`MarketFeatures` `predict_fn` via a closure / thin `PairFeatures` for cross-pair
  operators; keep existing single-feature generators working.
- **OperatorRegistry** (`operator_registry.py`): unchanged schema; OD generators register under the
  same `ASSET.VENUE` keys; `preferred_for()` surfaces the winner.
- **regime_classifier**: kept as gating/context; coupling scanner adds a new `DECOUPLING` event type.
- **SSE / SignalEvent** (`backend/api_server.py:115`): extend with OD fields
  (`coupling_strength`, `dipole_r2`, `leadlag_bars`, `leadlag_z`, `structured`, `od_size_fraction`).
- **Risk gates** (`executor/risk.py:161`): add `gate_dipole_r2`, `gate_leadlag_stability`; keep
  `gate_daily_loss` / `gate_daily_trade_count` / stop-loss as guardrails. `position_size_usd`
  becomes a **cap**; actual size from `odcore.sizing`.
- **Exchange protocol** (`executor/exchanges/base.py:39`): `ccxt_adapter` implements it; loaded only
  when `MARKETS_LIVE_EXCHANGE=ccxt:<id>` is set; `PaperExchange` stays the default.

### Estimator / windowing / numerical stability
KSG MI (k=4), Vasicek/KL marginals (binning fallback for short windows); raw-cov path for leadlag
(no entropy). window=40/stride=10. **center not z-score**; jitter near-constant channels; dedup
zeros in order-flow; clamp `MI≥0`; refuse to emit when `singular_gap` < τ or `N_eff` too small;
gate on extreme marginal-entropy asymmetry (MI variance collapses there).

### Coupling scanner + lead-lag
Enumerate cross-asset / cross-venue / order-flow / price-vol / exogenous pairings (repo already
collects Coinbase/Kraken/Bybit BTC+ETH). For each: build matrix → null → decompose → strength;
**a pair is "coupled" only if it beats its circular-shift control (F)**. Decoupling → first-class
`DECOUPLING` signal. Lead-lag: raw cross-cov over a lag grid, `argmax|cc|` = leader + lag in bars,
z vs time-slide null → `LEADLAG` signals (cross-venue = latency-arb; cross-asset = momentum
transmission), sized by lead-lag stability.

### Primary generator + alternatives + stacking
Chem algebraic dipole is PRIMARY (fit per source, residual-fraction strength, `H_a>H_b` direction).
Functional families (G) are alternative `predict_fn`s; the existing `AdaptiveSelector` picks the live
winner per source ("data picks"). `stacking.py` builds the `dipole_chunker_stack` composite that
competes in the same pool.

### Symbolic-regression equation DISCOVERY — PySR + Julia (the per-session research workflow)
This is the same machinery every research session used (INFO-025 l.615; "same PySR-from-raw-data
machinery," l.472/567) — and the owner's directive. We do not just hardcode the reconstructed chem
coefficients; we **run PySR (Julia backend) on the crypto operator-basis data to DISCOVER the dipole /
coupling / MI-vs-H equation per channel-pair from raw data** (the "Piece 1: re-derive the governing
equation without assuming it" step).
- `odcore/symbolic.py` wraps PySR with the **extended operator set `{+,−,*,/,square,cube,exp,log,sqrt}`**
  (exactly INFO-025), complexity-limited (the families landed at complexity 5–6), fitting targets like
  `H_a²` and `MI` against the basis columns over the windowed ensemble.
- **Acceptance discipline from the log**: a discovered form is only promoted if it reproduces across
  **≥3 seeds with <5% coefficient variation** (INFO-025 / Result Discipline l.143) AND survives
  walk-forward + the tautology-killing null. PySR output is a *candidate*, not a claim.
- The reconstructed chem form `a=0.007,b=−0.093,c=1.309` becomes a **synthetic sanity anchor** (PySR on
  a Brusselator must recover it) — the production equation per crypto pair is whatever PySR discovers
  and validation promotes. Expect crypto pairs to land on the chemistry/algebraic family (the owner's
  "chem dipole is the biggest boost", reinforced by the INFO-026 stationarity reason).
- **Fallback**: when Julia/PySR is unavailable in an environment (it happened in the log, l.2057), fall
  back to the pure-numpy reconstructed forms so the engine still runs — but flag that discovery is
  degraded.

### SessionStart hook + reproducible toolchain (set up with the `session-start-hook` skill)
The log's sessions run a **SessionStart hook that re-bootstraps the numeric stack + PySR + Julia every
session** (l.1721-1722, 2044-2045) so symbolic regression is always available; this repo never had that
treatment (the open S9 question, l.249-258). We add it:
- A `.claude/settings.json` SessionStart hook + a guarded `scripts/session_start.sh` that installs the
  numeric stack (numpy/scipy/scikit-learn) + `pysr` + the Julia backend, **guarded so it always reaches
  completion** even if a step fails (the latent-failure guard noted at l.2042). Authored via the
  `session-start-hook` skill.
- Pin `pysr` + Julia + the numeric stack in `requirements.txt` for reproducibility (the log pins PySR
  1.5.10).
- Per-session research workflow carried over from the log: work on the session branch, write a detailed
  `SESSION_HANDOFF_*.md`, fold the headline + new ledger entries into the master context, bump the
  header date/session, commit + push (the log's "keep the header current" rule).

### Validation + OD-native sizing + live
- **PER-CELL PROMOTION (standing rule, Greg S33 — applies to EVERY tool A–M, not just the dipole).** All validation,
  promotion, and deployment is **per cell** (asset×venue×side). A tool/signal that beats the bar on a SUBSET of cells
  is PROMOTED and deployed **on those cells only** — partial coverage is NOT failure, and nothing is discarded for
  failing on some cells. Output is a per-cell deployment map ("works on {X}, not {Y}"), never "X failed." This is
  exactly what `AdaptiveSelector` ("data picks the winner per source") implements. (`deploy-signal-per-cell-not-universal`.)
- **validation.py**: walk-forward/block CV + embargo; report random-vs-walkforward gap (I); realistic
  fees + slippage via `kyle_proxy` (`markets_adapter.py:485`); tautology null (F); must beat
  buy-hold, the existing `pure_dipole_fade`/`dipole_x_volz`, rolling-corr, cointegration,
  transfer-entropy, and lead-lag — net of cost — to be promoted **per cell**.
- **sizing.py (NOT Kelly)**: `size_fraction = clip(w1·residual_fraction + w2·norm(dipole_R²) +
  w3·leadlag_stability, 0, 1) · calibration`, where `calibration` = measured walk-forward edge, so
  size tracks **realized** OD confidence. Notional = `min(size_fraction·max_position_usd,
  max_position_usd)`. Circuit breakers stay purely as guardrails.
- **ccxt_adapter.py**: env-gated; `PaperExchange` is the import default.

### Backend / frontend
New endpoints: `/api/coupling_matrix`, `/api/strength/{asset}/{venue}`, `/api/leadlag/{asset}`,
`/api/dipole_signals`, `/api/decoupling` (all behind `verify_token`); OD fields also flow through the
existing `/api/signals` + `/api/stream` to the executor. New React pages: `CouplingMatrix.jsx`
(heatmap), `StrengthOverTime.jsx`, `LeadLag.jsx`, `DecouplingFeed.jsx`; extend `SignalCard`/
`DipoleChart`; add fetchers to `api.js`.

### Housekeeping (branch + move-don't-delete + grep-prove zero callers)
- **PELT chunker**: keep in repo, unwire from signal path (above).
- Consolidate **5 duplicate `load_bars`** (`backtester.py:48`, `adaptive_backtester.py:170`,
  `phase1_5_evaluator.py`, `autoresearch_lite.py`, `api_server.py:224`) into `odcore/io.py` with
  thin shims, then drop.
- **DEMO_MODE** emitter (`api_server.py:89`): default off; strip once OD signals populate the feed.
- DeepNova mirror-comment scaffolding in `markets_adapter.py` / `coinbase_*_canary_v2.py`: strip
  stale "mirrors X exactly" framing, keep the working classes.
- **autoresearch_lite.py**: superseded by `odcore.validation`; unwire from any scheduled path, keep
  on branch as reference.

---

## Phased execution
0. **Toolchain + engine + tests-first**: author the SessionStart hook (`session-start-hook` skill) that
   installs the numeric stack + PySR + Julia (guarded); pin them in `requirements.txt`. Build
   `operators`, `null_extract`, `test_synthetic_coupling` — OU recovers `(-1,-1,+2)/√6` (cos≥0.9994);
   reproduce INFO-040 control (g=0→MI-frac~0.006, g>0→0.81-0.97 monotone slope) and INFO-041 control
   (correlation makes MI but it stays out of the null).
1. **Symbolic discovery + primary dipole + lead-lag**: `symbolic.py` runs PySR (ops
   `{+,−,*,/,square,cube,exp,log,sqrt}`) — on a synthetic Brusselator it must **rediscover**
   `a=0.007,b=−0.093,c=1.309,R²~0.943` (anchor test); on cached crypto bins it discovers the per-pair
   dipole form (≥3 seeds, <5% coeff variation to promote). `dipole_predictor` consumes the discovered
   form; known N-bar-lagged synthetic pair recovers lag + z (`leadlag`).
2. **Scanner + strength + families + stacking**: chem residual-fraction tracks a swept synthetic
   B-knob (0.169→0.342→0.400); generators wired into `AdaptiveSelector`.
3. **Validation + sizing**: backtest cached bins (`phase1_bins.json`, `kraken_bins.json`, eth_*);
   random-vs-walkforward gap small on chem-form / large on non-stationary baselines; tautology-null
   kills artifacts; OD size tracks measured edge.
4. **Backend + frontend + executor**: endpoints, SSE fields, views, new risk gates, env-gated
   `ccxt_adapter`; paper-trade smoke test `python -m executor.executor --config
   executor/config.example.json --dry-run` opens/closes OD-sized paper trades in `audit.jsonl`.
5. **Housekeeping** on the same branch; grep-prove zero callers; DEMO_MODE off.

## Verification (end-to-end acceptance)
- (a) Synthetic unit tests green: INFO-040/041 controls, OU `(-1,-1,+2)/√6` recovery, known-lag
  recovery, and **PySR rediscovers the chem coeffs** `a=0.007,b=−0.093,c=1.309` on a synthetic
  Brusselator with <5% cross-seed coefficient variation.
- (b) Walk-forward backtest on cached bins beats buy-hold + the existing dipole generators **net of
  fees+slippage**, with the tautology-null passing.
- (c) Paper-trade smoke test: OD signals → risk gates → OD-native sizing → paper fills → audit trail
  → outcome resolution in `/api/stats`.

## Open item — `basic_equations` repo
The original scripts (`_markets_algebraic_dipole.py`, `_markets_dipole_kfold.py`,
`_markets_dipole_separation.py`, `_markets_dipole_chunker_stack.py`, `s12_coupling_decomposition.py`,
`s13_chemistry_residual.py`, `s12_consolidate_per_domain.py`) are **not reachable** from this
session (scope is locked to `davisai1974/markets`; `list_repos`/`add_repo` tooling is unavailable).
The plan reconstructs every equation from the log. If that repo is added to session scope, the
engineer can port the originals verbatim and diff them against the reconstructions.

## Branch
All work on `claude/crypto-trading-platform-plan-MpqwG` (already checked out); commit + push when
each phase is complete. No PR unless requested.

---

# PART 2 — What THIS session (S20, 2026-06-03) actually built

Self-contained pickup record of the work done in this session, so another session can continue
from here. (Everything above is the original approved plan; this part is the execution state as
of this session. Zero synthetic data — Greg's call. Result Discipline in force.)

## Engine built (`odcore/`), all on REAL collector bins
Every equation RECONSTRUCTED-FROM-CLAUDE.md (the master research log). Modules:
- `operators.py` — windowed basis [H_a,H_b,H_a^2,H_b^2,H_a*H_b,MI]; Vasicek marginal entropy +
  KSG(k=4) MI; window=40/stride=10 (INFO-012); `anti_frac` sufficiency proxy.
- `null_extract.py` — centered-SVD null (NO z-score; MI is the scale-invariant, INFO-051);
  coupling decomposition {equal-entropy / MI / residual}; biology MI-slope + chemistry
  residual-fraction strength meters; `analyze_coupling()` with the INFO-041 (mere-correlation)
  and INFO-024 (collapsed-MI-variance) guards.
- `leadlag.py` — raw cross-cov-over-lag detector (the S19 right tool, INFO-066): who moves
  first, z vs a time-slide null.
- `dipole_predictor.py` — algebraic dipole `H_a^2 = a + b*(H_a*H_b) + c*(H_a*H_b)^2` fit +
  `H_a>H_b` directional rule.  NOTE (this session's version): H_a/H_b were computed as windowed
  entropies of buy/sell volume — this was a GUESS and it collapses to c~=0 because buy/sell
  window entropies are near-symmetric. The correct construction is NOT entropy of volume (see
  "Blocker" below).
- `symbolic.py` — PySR (Julia, 1.5.10) symbolic discovery of dipole/MI equations from raw
  operator data (ops {+,-,*,/,square,cube,exp,log,sqrt}, INFO-025). VERIFIED working on real
  BTC: discovered `MI ~= -0.028*H_a*exp(H_b) + 0.023` (loss 0.0013).
- `coupling_scanner.py` — score/rank pairs; tautology-killing circular-shift null (INFO-066) on
  both lead-lag and operator-structure; `rolling_coupling` + `detect_decoupling` events.
- `channels.py` — channel factory (orderflow/internal/cross-venue/cross-asset) + INFO-051
  conditioning + pair enumerator.
- `io.py` — single real-bins loader (BinSeries: gap-fill, minute resample, cadence-aware
  `align`); loads the `data/*` branch bins from gitignored `realbins/`.
- `validation.py` — walk-forward/block CV + embargo; real fees+slippage; random-vs-walkforward
  gap (INFO-026); tautology-killing signal null.
- `sizing.py` — OD-native sizing (residual-fraction + dipole R2 + leadlag stability, calibrated
  to measured edge); Kelly only as a comparison helper (NOT the gold standard — Greg).
- `stacking.py` — compose operators (weighted_sign/majority/unanimous) + coupling gate.
- `generators.py` — real-bin OD signals + bridge to `adaptive_backtester.SignalGenerator`.
- `scripts/` — `od_real_run.py`, `od_scan.py`, `od_pysr_discover.py`, `od_backtest.py`,
  `od_xvenue_backtest.py`, `session_start.sh`.
- `tests/` — `test_operator_real.py`, `test_leadlag_real.py` (run on REAL bins; 3 pass).
- `.claude/settings.json` — Bash allowlist + SessionStart hook (PySR/Julia + real-bins bootstrap).

## Real-data findings (honest, Result Discipline)
- Pipeline + PySR/Julia work end-to-end on real bins (BTC/ETH x Coinbase/Kraken/Bybit, ~10.7d).
- Equal-entropy attractor reproduces on real data: quad |cos| to (-1,-1,+2)/sqrt6 = 0.9996.
- Cross-venue coupling is real + huge z: Coinbase<>Bybit-perp lag-0 cc=0.656 z=580; spot venues
  looser. Venues synchronous at 1s (sub-second leads need tick data).
- 145 real decoupling events on Coinbase<>Bybit (the tradeable regime signal).
- HONEST NULL — no net-of-cost edge from the unblocked pieces. All simple signals lose to 3bps
  costs (flip every bar): ofi_momentum WF -178%, dipole_direction -12%, tautology-z ~1.
  Cross-venue reversion is STATISTICALLY REAL (tautology z=3.0-3.6 at 10s) but per-trade edge <
  cost. The validation harness correctly REJECTS these. Nothing fabricated.
- Chem QUADRATIC dipole did NOT reproduce on this session's reconstructed channels (buy/sell
  entropies near-symmetric -> trivial identity, c~=0). Tried 5 channel types x 3 timescales x 3
  conditionings.

## Blocker (as seen this session)
The exact chem-dipole CHANNEL CONSTRUCTION (what H_a and H_b are) was not reproducible from the
master log alone; the original `_markets_algebraic_dipole.py` lives in `DavisAI1974/Basic_equations`,
which was ACCESS-DENIED this session (scope locked to `davisai1974/markets`). Files needed from it
(priority): (1) `_markets_algebraic_dipole.py` + whatever module it imports (the H_a/H_b/MI
builder) + a sample of its input data; (2) `_markets_dipole_kfold.py`, `_markets_dipole_separation.py`,
`_markets_dipole_chunker_stack.py`; (3) `s12_coupling_decomposition.py`, `s13_chemistry_residual.py`,
`s12_consolidate_per_domain.py` + `od_per_domain_equations.json`.

## Decisions made this session (best judgment)
- Zero synthetic enforced; `odcore/synthetic.py` + synthetic tests removed; tests run on real
  bins (lead-lag injects a KNOWN lag into a REAL return series).
- New `odcore/` package; existing platform shell left intact (no destructive housekeeping).
- KSG + Vasicek estimators; global channel conditioning (INFO-051) — note this symmetrizes
  buy/sell, likely the wrong choice for the chem dipole.

## Docs produced this session
- `SESSION_HANDOFF_2026-06-03_S20.md` (full detail), `KICKOFF_2026-06-03_S21.md` (next steps),
  `BUILD_QUESTIONS.md` (decisions + open questions), this `BUILD_PLAN.md`.
- The master context `CLAUDE (5).md` header bumped to S20 with the rebuild note folded in.

## Where this build plan came from
Original plan-mode artifact (approved via ExitPlanMode): `/root/.claude/plans/i-uploaded-a-new-
sorted-donut.md` (ephemeral). Copied verbatim into this `BUILD_PLAN.md` so it survives the
container. The plan was designed by an architecture (Plan) agent that read the full `CLAUDE (5).md`
research log, then refined with Greg's directives (chem dipole primary; OD-native sizing not Kelly;
keep-but-unwire the chunker; use the basic_equations knowledge).

## Next steps (as this session saw them)
1. Unblock `Basic_equations` (or supply the files above) to get the real chem-dipole construction.
2. Then: re-run the dipole + `H_a>H_b` predictor on real bins; validate with walk-forward + the
   tautology null (both already in `odcore/validation.py`) before wiring anything live.
3. Backend endpoints (coupling matrix / strength / lead-lag / dipole / decoupling) + frontend
   views; executor wiring (OD generators + OD-native sizing + circuit breakers); keep PELT
   chunker but unwire from the signal path. Promote ONLY what beats baselines net of cost.

---

# PART 3 — S36 (2026-06-22): the order-flow DIVERGENCE/EXHAUSTION reversal edge (Part N)

Built `odcore/info_dipole.py` — the order-flow divergence + exhaustion **FLIP detector** (Part N), the
per-cell signal that fills the S35b "bleed" (the side-agnostic 128-dim coeff can't encode direction).
This is the order-flow dipole used the RIGHT way per Part E (raw level, not entropy flow).

- **VALIDATED** (per cell, pooled n=1560, on the committed `fingerprint_dataset/` test_bars): DIVERGENCE
  (flow opposing price) + EXHAUSTION (dipole collapsing toward 0.5) stack to a **64% reversal** gate;
  temporally stable (early 70% / late 62%); 6/7 cells (btc_bybit_buy inverts).
  `divergence(buy_vol, sell_vol, price_drift)` → `{imb_level, aligned_flow, confirms, opposing,
  exhausting, expect∈{reversal,flip_risk,weakening,continue}, reversal_conviction}`. Reusable in the
  pre-window stage AND stacked into `odcore/fingerprint.py` per cell.
- **DISCIPLINE / what NOT to use:** the DIRECTIONAL probe (`cell_signal`/`DEPLOY`) is a TREND/base-rate
  ARTIFACT (Simpson's paradox on a 2-day trending window) — it shows +5..+11 "lift" that VANISHES under
  a window/forward sweep + temporal OOS + a detrended target. `DEPLOY_VALIDATED=False` — **do NOT trade
  off it.** This REINFORCES Part E (the entropy dMI/dt flow is the wrong tool). The robust edge is the
  raw order-flow LEVEL divergence/flip read.
- **NEXT (decisive, per `KICKOFF_2026-06-22_S36.md`):** net-of-cost backtest of the reversal gate **per
  cell** (a 64% hit-rate is only an EDGE if the moves beat fees+slippage; walk-forward); confirm on the
  LOCAL 1-sec multi-regime history (test_bars are thin 1-min/2-day); wire `divergence()` into the regime
  classifier (flow-opposed/collapsing → reversal/transition) + sizing (`reversal_conviction`) per cell;
  investigate the 2 inverting cells; add the C ratio (H_self/H_cross) as a 3rd factor.
- **Tools (bar-free, off committed data):** `_info_dipole_trend_flip.py` (the edge),
  `_info_dipole_flow_detrend.py` (artifact-vs-real), `_info_dipole_flow_robustness.py`,
  `_info_dipole_flow_probe.py`. Full detail: `SESSION_HANDOFF_2026-06-22_S36.md`.

# PART 4 — S36 cont. (2026-06-22): net-of-cost + the SWING reframe + the TIMING edge (branch `claude/divergence-exhaustion-backtest-wj65sm`)

Ran KICKOFF #1 (net-of-cost the reversal gate per cell) and, following Greg's live reframe, turned it into
a SWING strategy with an explicit timing model. Full detail: `S36_NETCOST_BACKTEST_FINDINGS.md`. Tools:
`_info_dipole_netcost_backtest.py`, `_info_dipole_trailing_backtest.py`, `_info_dipole_swing_backtest.py`
(reads 1-min test_bars OR 1-sec `realbins/`), `_info_dipole_timing_test.py` (+ matching `*_results*.json`).

- **Net-of-cost verdict (per cell, 5 bps/side = 10 bps round-trip).** The 64% reversal rate does NOT clear
  10 bps pooled (FLOW policy −5.97 bps/trade; breakeven ≈ 4 bps round-trip). The flow gate DOES add
  +3 bps/trade over blind trend-following. Per cell it CLEARS robustly (both walk-forward halves):
  **btc_bybit_sell** (FLOW +9.1 t=3.1; fade gate +18.6 t=5.9) and **btc_bybit_buy** (fade gate +25.7 t=4.6).
  eth "clears" are walk-forward-fragile single-regime artifacts on the thin 1-min/2-day data — not deployable.
- **The SWING reframe (Greg, load-bearing).** Markets oscillate: **buy valleys, short peaks, flip at each
  turn; NO clock horizon** — the only thing that ends a position is the next turning point. Rarer straight
  runs = ride, don't fight (flow keeps confirming → no flip). Enter AT the turn, never the backside.
- **ORACLE proves the opportunity.** Perfect swing-trading (ZigZag pivots) nets thousands of bps over the
  window; swings beat the 10 bps fee 3–13× (θ=20 bps → mean swing ~42 bps, +32 net/swing). The money is real.
- **The whole game is entry TIMING at the turn — and 1-sec is a quantified edge.** Order-flow imbalance
  crossing is a MID-SWING trigger (~18 bps off the turn at ANY resolution — does NOT improve with finer
  data). The thing that fires AT the turn is **price reversing**, and that sharpens with resolution. The
  clean timing test (same real turns, same data, only the clock changes): **1-sec enters ~5.6–6.5 bps off
  the true turn vs ~9.2–11.0 at 1-min → +4.2 bps penalty PER entry (~8 bps/round-trip swing) the 1-min
  trader hands over, growing with volatility** ("not close unless the market is dead"). Per-second is required.
- **FEE-FLOOR logic (Greg — never trade sub-fee).** R (reversal confirmation) is TIMING only — how close
  you enter — and never fires a trade standalone (each fire pays the fee). The trade decision is the
  swing-size filter: **min swing > round-trip fee + entry slippage + exit slippage ≈ 10 + ~6 + ~6 ≈ 22 bps
  at 1-sec.** Tradeable zone = θ ≳ 20 bps swings (where the oracle net is fattest); sub-fee moves dropped.
- **ARCHITECTURE locked.** **DIPOLE = the FILTER** (exhaustion/divergence → "a real ≥~22 bps turn is near",
  the 64% read) decides WHICH turns to trade. **1-sec price-reversal = the TIMING** — enter within ~5–6 bps
  of the top/bottom. Earlier whipsaw failures came from using a trigger as a filter; separating the two
  roles + the fee floor is the fix.
- **NEXT:** build the gated swing strategy (dipole filter arms the tight 1-sec trigger; ≥~22 bps swing
  floor; ride to next confirmed turn; net-of-cost per cell). Confirm on the local 1-sec MULTI-REGIME onset
  history (the in-git `realbins/` 1-sec is a single later window). Maker-rebate execution to lower the cost
  floor. Investigate the inverting cells. Add the C ratio (H_self/H_cross) as a 3rd flow factor.

## Quantum/classical-merge question — RESOLVED by the Architect (S36b): precision, NOT speed
The timing test made speed a MEASURED, compounding edge (+4.2 bps/entry per resolution step, grows with
vol). Greg's serious thread was whether the DavisAI quantum/classical-merge math buys a timing edge. The
Architect pulled the Hilbert-Space-Unification math and resolved it:
- **Classical-∞-dim ML and quantum ML are the SAME mathematics on different substrates** — same Hilbert
  space, same spectral operator; the only difference is how the inner product is computed. The distinction
  is COMPUTATIONAL, not mathematical.
- Therefore the merge-math **FORBIDS a quantum-execution edge rather than enabling one**: any "step ahead
  of price" would exist on both substrates equally, so it isn't a quantum thing. **Build the operator
  OFFLINE, compile it, run it CLASSICALLY in the live path. No quantum hardware between tick and order.**
  (A turn-detector on an order-flow+price window is low-dim with cheap classical eval — it fails every
  prong of the quantum-advantage test: needs exp-large kernel space AND intractable classical eval AND
  efficient state prep.)
- **The edge is PRECISION (a better spectral operator = the dipole filter / turn-predictor), not speed.**
  Latency stays pure classical HFT physics (colo, FPGA, kernel-bypass). The math gives the operator; the
  FPGA/colo captures it. This independently CONFIRMS PART 4's split (dipole = filter; fine-res price = timing).
- ("Quantum = speed" was the wrong frame, and our own theory is the proof. Greg's "time on atomic decay"
  noted as the joke it was.)
- **SCOPE (Greg, load-bearing — do NOT over-read the closure):** this "no quantum edge" result is
  CONDITIONAL on the turn-detector being LOW-DIMENSIONAL (an order-flow+price window with cheap classical
  evaluation — that is what fails the quantum-advantage prongs). It does NOT generalize to other uses of the
  merge-math. Greg believes the edge he has in mind is **something OTHER than the dipole/OD turn-detector**;
  for THAT application the Architect's answer does not apply, and it stays an OPEN thread he is exploring
  with the Architect. Settled = "build the swing turn-detector classically." Open = the broader merge-math edge.

## Actionable edges (Architect, S36b) — ALL 4 DONE
- **DONE — per-leg ASYMMETRIC fee floor** (`_info_dipole_fee_floor.py`). The 22 bps floor is round-trip
  TAKER. Because the dipole PREDICTS the turn, you can REST a maker limit there → lower fee AND lower
  slippage (you fill at your price). Floor drops 22(taker/taker) → 13(maker-in/taker-out) → **4 bps
  (maker/maker)**, which **1.6–3.5× the oracle opportunity** (far more swings clear a lower floor). Caveat:
  maker-rest carries FILL RISK (limit only fills if price reaches it) — model per-venue before trusting.
  Model the floor PER-LEG, not as a flat 22.
- **DONE — regime master-gate** (`_info_dipole_regime_gate.py`) via ER (trend-efficiency) + the dipole C
  ratio (H_self/H_cross). NOT universal: it cuts good trades on the cells where the dipole already wins, but
  rescues the bleeders (btc_bybit_perp −173→+16, eth_kraken −1207→−170). Deploy PER CELL — fire only where it
  earns its place. Confirm the per-cell on/off on multi-regime 1-sec data (degenerate-tuning wall on one window).
- **DONE — incremental/sliding operator update** (`odcore/incremental.py` `RollingFlow` + `_canary_incremental.py`).
  O(1)-amortized rolling order-flow imbalance + exhaustion; bit-faithful to the batch operator (max err 7e-13,
  0 exhaustion mismatches) at **1.70 µs/tick**. The per-tick window recompute is out of the hot path. Same math.
- **DONE — pre-entry leakage check** (`odcore/leakage.py` `assert_no_leakage` + `_canary_leakage.py`). Model-
  agnostic: corrupt all data AFTER i, require the signal at i unchanged. Canary CLEARS the dipole (leak-free)
  and CATCHES a look-ahead control (40/40). **This is the mandatory gate** — the algebraic-dipole 0.993/FN=0
  does NOT enter the harness until it passes `assert_no_leakage`.

## Falsification harness (Architect, D) — the decisive validation, when there's a validated challenger
Do NOT run "quantum vs classical detector" — the unification thesis predicts a null there, so a null tells
you nothing. The real test: **OD-recovered operator vs a strong CLASSICAL champion** (order-flow imbalance +
tuned reversal filter), BOTH running classically, on frozen fine-resolution data. Metric = **bps-to-turn +
FN-rate at matched FP, net of the per-leg fee floor, out-of-sample.** The OD challenger enters only AFTER it
clears the mandatory pre-entry-window validation (no validated challenger → no test yet). Architect's soft
prediction: OD shows as an edge on turn FILTERING (which reversals are real), NOT on turn TIMING
(fine-resolution price already pins the turn near the fee floor). The frozen-data test decides it.

## LIVE EXECUTION — latency & placement (TODO before going live; record so we don't forget)
The timing edge (+4.2 bps/turn at 1-sec, market-making is inherently sub-second) is captured by REACTION
latency + placement, NOT by CPU count. Vertical-scaling AWS cores does NOT make us faster to the turn —
it only adds research/parallel throughput. What actually buys live speed, in order of leverage:
1. **REGION/PLACEMENT (the big, near-free win):** run the live box in the SAME AWS region/AZ as each
   exchange's matching engine. **Coinbase runs on AWS us-east-1** → co-region is single-digit ms vs
   50–100 ms cross-region. Find where **Kraken** and **Bybit** host and match each. For crypto this alone
   beats every retail/1-min trader — no physical colo/FPGA/microwave needed to beat the slow guys.
   ACTION: confirm each venue's (Coinbase/Kraken/Bybit) hosting region/AZ; place a live box per venue region.
2. **Warm connections + kernel-bypass networking:** keep websocket/FIX sessions hot (no reconnects), good NIC.
3. **Higher-CLOCK, not more-CORES, for the hot path:** compute-optimized / high-frequency instances
   (c-series, z1d) beat big many-core boxes for per-message latency. More cores only = more cells in parallel.
4. **Incremental/sliding operator update** (Architect): move per-tick recompute out of the hot path
   (recursive rolling state). Cheapest latency win, pure software.
More CPUs DO help the offline RESEARCH workload (operator discovery / PySR / the harness over multi-regime
1-sec data is embarrassingly parallel across cells) — bucket that as "research speed", not "live edge".

## Regime master-gate — PER-CELL (deploy where it earns its place; `deploy-signal-per-cell-not-universal`)
The regime gate is NOT a universal improvement and must NOT be applied everywhere. On the harness (1-sec,
OOS, maker floor) it HURTS the cells where the un-gated dipole already wins (btc_kraken +466 → +151 — it
cuts good trades) but HELPS the cells where the dipole bleeds: btc_bybit_perp flips −173 → +16 (with 13
real trades, not no-trade), eth_kraken cuts −1207 → −170. So KEEP the regime gate as a PER-CELL option —
fire it only on the cells/instances where it earns its place (the bleeders), leave the winning cells
un-gated. Confirm the per-cell on/off on the multi-regime 1-sec history before deploying; do not tune off
the single window. (Things don't have to work on all cells all the time — that's the whole per-cell rule.)
