# CLAUDE.md — DavisAI Markets / Kalshi (Updated 2026-07-13, Session 86)

**One-line state:** the futures→Kalshi LAG is the live edge thread — **NYMEX is the CANARY, Kalshi the
delayed follower.** S86 produced a **MODEL, not just features: `research/kalshi/EVENT_STATE_DESIGN_S86.md`**
— Greg's driver model that reads each energy release CONDITIONED on prior + anticipated state (events STACK;
three pillars = news/storage/market-capacity; storage = the physical confirmation node; shared drivers with
per-market/per-period weights, "same scaffold, different values"; the human/emotion factor shows as the herd
run = order-flow footprint). S86 also BUILT three leakage-gated reads on the 24 MBP-10 windows (~$0.42):
depth run-length (NG −0.17 / CL +0.52), the EIA seasonal-proxy surprise split, and the **pre-release VOLUME
primed/coiled detector** (NG: quieter pre-release → bigger move, consistent across cells; the first build off
the model, needs no external feeds). All provisional (n=12, Apr-Jul only, logged WITHOUT mechanism). **NEXT =
P3 lag join** (Kalshi echo net-of-fee vs the futures move = realized-EV; scoped, needs a `kalshi_history.py`
pull of the 24 settled events; gates the $130 full-year pull). Weather = scoreboard only, forecaster is
Greg's spec. Detail: `SESSION_HANDOFF_2026-07-13_S86.md`.

**READ THIS FIRST, in order — do NOT read this whole file for detail, it points you at the detail:**
1. The latest `SESSION_HANDOFF_*.md` (highest S-number) — the actual current state.
2. The latest `KICKOFF_*.md` — the priorities for this session.
3. `KALSHI_TRADING.md` — the file index: every Kalshi file, what it does, current vs old.
4. Then `git log --oneline -1` — confirm you are NOT on the stale tip (see Branch discipline).

---

## What this project is

DavisAI Markets. The live product is **Kalshi prediction-market trading** (weather / macro / energy /
electricity event contracts). Crypto (the OD "info-dipole" / order-flow toolkit) was the proving ground
and is now history — the session-by-session record + the earlier OD/physics research lives in
`CLAUDE_ARCHIVE_OD.md` (nothing deleted; see Archive pointer). The operator toolkit that came out of it
is LIVE and documented below (see "OD toolkit") — it is the engine the Kalshi lag / signal work runs on,
and we regularly reach back into it for pieces.

Team: **Greg Davis** (founder, sets direction, owns the weather forecaster spec) + Claude (engineer).

---

## The trading rules (load-bearing — Greg, S80-S82)

- **EACH TRADE INDIVIDUALLY, never average.** No pooled hit-rate, no mean signed-bps, no averaged
  coefficient — every aggregate blurs away the per-trade fingerprint that IS the predictive content.
  Characterize the DISTRIBUTION + the per-trade fingerprint; never lead with the mean.
- **Per-cell always, never pool.** Cells = moneyness × side × velocity/lag-class × release (for
  level-hits); regime × city × season × bucket × swing-dir (for weather). A signal that survives on a
  SUBSET of cells is KEPT and used on those cells — partial coverage is not failure. Report "works on
  {X}, not {Y}", never "X failed."
- **The merged signal architecture:** catalyst (release/news) = trigger + coarse size; book imbalance +
  flow + exhaustion = direction + magnitude; herd breadth = continuation, whale = scalp-only.
- **NYMEX is the CANARY; Kalshi is the delayed follower (Greg, S84).** The move happens on NYMEX/ICE
  first and reprices onto Kalshi seconds-to-a-minute later (futures lead, Kalshi never leads). Gather
  NYMEX as the leading signal, measure the lag, fire on Kalshi. Resolution: 1-min is USELESS (NYMEX
  moves fast); 1-sec is the historical floor and STILL undersamples — every 1-sec NYMEX readout is a
  LOWER BOUND, never the full tape. Data reality: Pyth has WTI (historical works) but NO natural gas
  and Brent-historical 404s; NG/Brent need Yahoo/other. See `research/kalshi/NYMEX_CANARY_NOTES_S84.md`.
- **Exclude the settle window** (the daily-settle exclusion / `SETTLE_UTC` guard) from every backtest.
- **Leakage gate before ANY backtest** (`odcore/leakage.py`) — pre-entry context must be invariant to
  future trades. This is mandatory and non-negotiable.
- **Zero synthetic trading data.** Ever.
- **Provisional until live.** A backtest edge is a hypothesis; nothing is "real" until it clears live.
- **Weather = Greg's spec, HANDS OFF.** The forecaster itself is Greg's own work; we only build the
  scoreboard/bridge (`kalshi_score.py`, the `(value,sigma)` bridge) and score PER REGIME vs the baseline.
- **`--events` on `news_coupling_research.py` is a BASENAME** joined onto `--data-dir`, not a path.
- **Keep `KALSHI_TRADING.md` current** — add new files to the top section, move superseded ones down.

---

## Operating discipline (cross-cutting)

- **Falsification-first / Result Discipline.** Every claim needs a falsifiable test. Every result is ONE
  data point — map alternatives (incl. the deflationary reading) before promoting to a claim. Catalog
  MISSES with the same care as hits; a negative that sharpens the program (like the S82 level-hit result)
  is a real deliverable.
- **No tent-widening on outliers.** When something lands outside the pattern, find the specific reason —
  don't loosen the test or wave it off as transient.
- **Incremental validation.** Canary run (short) before any long/compute-heavy run; break long runs into
  chunks with stop gates.
- **git is the source of truth.** Commit + push working code/docs regularly. Large data stays LOCAL /
  gitignored (see Branch & data). Better, stronger, faster, cheaper.
- **No emojis / special symbols** in docs, commits, or anything pushed.

---

## Branch & data discipline (READ — recurring trap)

- **The stale-tip trap:** the harness often cuts a fresh session branch from a stale old tip (the known
  bad one is **S70 `3c70ff5`**). ALWAYS run `git log --oneline -1` first. If the tip is old, you are NOT
  on the real work.
- **Canonical trunk = `claude/kalshi-s79-kickoff-ij8t9o`.** The GitHub Actions collectors auto-push data
  commits here, so it is the live rolling branch — develop and push here (pull/rebase first, the
  collectors commit too). Do not strand work on a fresh harness-assigned branch.
- **Durable data accrues on branches, code does not:** `data/kalshi-bins` (live bins + consensus),
  `data/pyth-ticks` (Pyth futures ticks), `data/*-book` / `data/*-bins` (crypto history). Fetch + gunzip
  the relevant branch at session start; VERIFY it actually accrued before trusting it.
- **Local/gitignored data stores:** `data/kalshi_hist_trades/`, `data/pyth_ticks/`, `data/kalshi/`,
  `data/level_hits_*.json`. Too big for git; re-pullable.
- **Workflows (kept, on the trunk):** `.github/workflows/kalshi_collectors_durable.yml` (6h),
  `pyth_collector_durable.yml` (6h). If a run sits `queued` and never executes, it is an account-level
  Actions issue (billing/minutes/runner cap), not the workflow. My token cannot click "Run workflow" —
  Greg dispatches manually.

---

## Where things live (see `KALSHI_TRADING.md` for the full index)

- **`research/kalshi/`** — all Kalshi code: collectors (`kalshi_collector.py`, `kalshi_history.py`,
  `pyth_collector.py`, `consensus_poll.py`), the lag thread (`futures_kalshi_lag.py`,
  `lag_exploit_backtest.py`), the level-hit thread (`level_hit_dataset.py`), release/scoring/weather
  (`release_book_signal.py`, `kalshi_score.py`, `kalshi_weather_forecast.py`), findings `*.md`.
- **`KALSHI_BUILD_SCOPE.md`** — the build scope / thesis.
- **`odcore/`** — the OD toolkit (below).
- **`.claude/skills/`** — session rituals: `kalshi-session-start` (branch/data/accrual checks),
  `kalshi-backtest` (the mandatory evaluation discipline), `kalshi-roll` (Pyth front-month roll).
- Shared: `news_ingest_rss.py`, `news_coupling_research.py`, `regime_classifier.py`.

---

## OD toolkit (live — we reach back into this; provenance in `CLAUDE_ARCHIVE_OD.md`)

The operator tools built in the crypto era (S20–S37) that the Kalshi pipeline runs on, plus the pieces
we periodically pull back out. All portable numpy; validated per-cell.

- **`odcore/leakage.py`** — the MANDATORY pre-backtest leakage gate (catches look-ahead 40/40). Nothing
  gets backtested without passing it.
- **`odcore/leadlag.py`** — raw cross-covariance-over-lag lead-lag + time-slide null (the S19 "right
  tool"; what `futures_kalshi_lag.py` is built on).
- **`odcore/info_dipole.py`** — signed order-flow features + `divergence()`: the 2-factor
  DIVERGENCE (flow opposes price → ~65% reversal) + EXHAUSTION (imbalance collapsing toward 0.5 =
  leader weakening) read. The FILTER in the filter/timing split. Also provisional `cell_signal`/`DEPLOY`
  — **`DEPLOY_VALIDATED=False`, never trade the directional map** (S36 robustness: trend artifacts).
- **`odcore/incremental.py`** — `RollingFlow`, O(1)/tick bit-faithful incremental operator (1.7µs/tick)
  for hot-path use.
- **`odcore/fingerprint.py`** — per-cell fingerprint encoder (verbatim ports of the live micro-feature
  math + chunker recipe; flow features stacked per cell).
- **`odcore/dipole_predictor.py`** — the 128-dim centroid-projection algebraic dipole
  (`build_centroids`/`project`; H_a/H_b = projections on win/lose centroids — centroid-based, NOT bins).
- **`odcore/null_extract.py` / `coupling_scanner.py` / `symbolic.py` (PySR) / `validation.py` /
  `sizing.py` / `stacking.py` / `generators.py`** — coupling discriminator, tautology-killing
  circular-shift null, symbolic regression, the walk-forward net-of-cost promotion gate, OD-native
  sizing, stacking.
- **Crypto data history** (for reaching back): `data/*-bins`, `data/*-book`, `data/*-kraken-book`,
  `data/perp-history` branches — 5 coins × 3 venues 1s bins + L2 books. Collector workflows were
  deleted from the trunk end-S82 (runner hog); the code is recoverable via git history if collection
  ever needs to restart.

The research findings behind these tools are the next section — the dipole research stays LIVE here,
not just in the archive.

---

## Dipole research (standing — the findings, kept live)

The information dipole (davisai.ai/dipole) is our directional/flow tool; Greg: the trend-following /
flow read may be one of our biggest edges, usable across the WHOLE platform — which is why this stays
in the live doc. Full detail: `S36_NETCOST_BACKTEST_FINDINGS.md`, `SESSION_HANDOFF_2026-06-22_S36.md` /
`_S36b` / `_S37`, and `CLAUDE_ARCHIVE_OD.md`.

- **The core read (S36, 2 factors, stack monotonically):** markets are follow-the-leader (a trend = a
  flow) until the leader exhausts → new leader, usually opposite; the edge is detecting the changeover.
  (1) **DIVERGENCE** — `aligned_flow = imb_level × sign(price_drift)`; strong divergence (≤ −0.20) →
  ~65% reversal, temporally stable, consistent 6/7 cells. (2) **EXHAUSTION** — the dipole COLLAPSING
  toward 0.5 (leader weakening; the MOVE toward balance, NOT the discrete crossing, which is a coin
  flip). Combined: oppose+exhaust 64% reversal > oppose+strengthen 58% > with-trend+exhaust 52% >
  with-trend+strengthen 49% (healthiest trend).
- **Discipline (load-bearing):** the signed flow is NOT a direct direction predictor — apparent
  directional lifts were trend/base-rate artifacts (Simpson's on a trending window) and died under
  window/forward sweep + temporal OOS + detrended targets. `DEPLOY_VALIDATED=False`; never trade the
  directional `cell_signal` map. The DIVERGENCE/FLIP read is the robust edge; static `imb_level` is
  the detector (differential flows are not).
- **Net-of-cost (S36b, per cell):** the 64% does NOT clear a 10bps round-trip pooled; the flow gate
  adds ~+3bps/trade over blind trend-following and clears walk-forward-robustly only on specific cells
  (btc_bybit sell/buy). Direction is the easy part — the edge is SIZE-vs-FEE (the same finding Kalshi
  S81/S82 reproduced on a different market).
- **The architecture split:** DIPOLE = the FILTER (which turns are real) + fine-resolution
  PRICE-REVERSAL = the TIMING (1-sec enters ~5–6bps off the true turn vs ~9–11 at 1-min). Fee-floor
  rule: never trade a swing smaller than round-trip fee + 2× entry slippage (taker floor ~22bps;
  resting a maker limit at the predicted turn drops it to ~4bps, with fill-risk). Per-cell regime
  master-gate rescues bleeder cells; leave winning cells un-gated.
- **The gated-swing stack (S37, `_info_dipole_gated_swing.py`):** timing (1-sec price-reversal) +
  filter (dipole divergence) + regime gate + maker floor, leakage-gated (PASS 6/6); PROVISIONAL 4/6
  cells clear on the single window — never size off one window.
- **The centroid-dipole lineage (S33–S35):** the real markets dipole is CENTROID-based, not bins —
  H_a/H_b = projections of a trade's 128-dim OD `operator_coefficients` on win/lose centroids; per-cell
  exact coeffs + the distinctive-fingerprint program (`bucket-distinctiveness-is-the-goal`: predict
  winners by their per-cell fingerprint, never by class-separation statistics).
- **Standing meta-rules:** tools are COMPLEMENTARY, not competing — evaluate by STACKING, never
  head-to-head ("even a 5% net edge is huge"). Per-cell always. On Kalshi today the dipole exhaustion
  read is live inside `release_book_signal.py` (direction = book-imbalance sign, magnitude/fade =
  imbalance + dipole exhaustion) and the level-hit context features.

---

## Current state & priorities

Detail is in the latest handoff + kickoff — this is the pointer, not the record.

Recent arc (compressed; full detail in each `SESSION_HANDOFF_*.md`):
- **S81** — lag made tradeable-or-not: direction predictable (sharpens with move size), edge is
  size-vs-fee, real but rare at 1-min → sub-minute pivot to Pyth ticks.
- **S82** — per-trade level-hit dataset (200k events): level-hits mean-revert at 1¢, NO cell pays at
  maker fees, internal flow is a weak predictor → **the edge is EXTERNAL (futures lag)**. Pyth feed
  unstuck. Weather scoreboard characterized.
- **S83** — meta session: CLAUDE.md audit/split (this lean doc + `CLAUDE_ARCHIVE_OD.md`, dipole
  research + OD toolkit kept live); the three ritual skills (`kalshi-session-start`, `kalshi-backtest`,
  `kalshi-roll`). No research ran; `data/pyth-ticks` still absent at close.
- **S84** — Data reckoning + weather. NYMEX-canary principle set. Found Pyth has NO natgas (bogus `NGDQ6`
  id) → Databento = primary historical (true-tick CL+NG, `databento_backfill.py`). KXNATGASD = daily
  NG-futures market; KXPOWERKWH = monthly macro stat. Weather per-day fingerprint. Killed respawning
  crypto collectors. Detail: `SESSION_HANDOFF_2026-07-15_S84.md`.
- **S86** — Produced the **event-state MODEL** (`EVENT_STATE_DESIGN_S86.md`, Greg's driver model — see
  one-line state) + three leakage-gated builds on the 24 MBP-10 windows (~$0.42), all provisional/n=12/
  Apr-Jul/logged-without-mechanism: (1) MBP-10 depth run-length (push-book one-sidedness vs run length NG
  −0.17 / CL +0.52); (2) EIA seasonal-proxy surprise split (`eia_surprise.py`, 12/12; opposite-signed
  surprise/move NG vs CL); (3) pre-release VOLUME primed/coiled detector (`pre_release_volume`; NG quieter
  pre-release → bigger move, consistent across cells — first build off the model, no external feeds).
  Eyeball-validated (06-17 CL big move = the 2026 Hormuz crisis). NEXT = P3 lag join (needs a Kalshi
  historical pull; gates the $130 full-year MBP-10). Detail: `SESSION_HANDOFF_2026-07-13_S86.md`,
  `DEPTH_RUNLENGTH_FINDINGS_S86.md`, `EVENT_SURPRISE_FINDINGS_S86.md`, `PREVOL_FINDINGS_S86.md`.
- **S85** — Databento LIVE (key set, `pip install databento` 0.81). `event_move_baseline.py` BUILT + run
  on 12 NG + 12 CL real release windows (leakage PASS, `definition`-schema $10/tick): per-contract
  HOLD-TIME map (NG 60s=66% of move front-loaded; CL slower, 60s=27%, longer hold gets the rest — both
  kept, EV-net-of-fee is the gate). Futures move = the ceiling; lag join next. `databento_backfill.py`
  hardened (defs mode + point-in-time tick store, volume roll `.v.0`, retry/backoff). Schema decision =
  MBP-10 (depth, ~$130/yr both, ~$5 over credit; MBO off). Tape persisted on `data/nymex-ticks`
  (session-start restores it). Detail: `SESSION_HANDOFF_2026-07-12_S85.md`, `EVENT_MOVE_FINDINGS_S85.md`.

S86 priorities (see `KICKOFF_2026-07-12_S86.md`): (1) extend writer+baseline to consume MBP-10 DEPTH
(run-length/exhaustion read), then batch the full-year MBP-10 (watch disk); (2) historical surprise join
(EIA actuals + consensus) for the surprise-cell split; (3) the lag join = Kalshi echo net-of-fee vs the
futures move (realized-EV); (4) standing: NGDQ6 fix, weather forecaster scoring, Pyth live lag.

---

## Archive pointer

The full OD / info-dipole crypto research (S20–S37) and the earlier Information-Layer / four-forces /
gravity-time physics research (S3–S25, the INFO-0xx ledger, capability demos) live VERBATIM in
`CLAUDE_ARCHIVE_OD.md`. Nothing was deleted — it was moved out of the always-loaded context because it
is history, not the live Kalshi operating surface. Consult it only if a question reaches back into the
OD toolkit's provenance.

---

## Keeping this file lean (session-note workflow)

This file stays SHORT and CURRENT. Per session: write full detail to a `SESSION_HANDOFF_*.md`, update the
one-line state + header date/session at the top, fold only the new headline into the "Recent arc" list
(drop the oldest if it grows past ~6 entries), keep `KALSHI_TRADING.md` current, commit + push. Do NOT
paste session detail into this file — that is what the handoffs are for. The failure mode this structure
prevents: a bloated master a cheaper model silently half-ignores.
