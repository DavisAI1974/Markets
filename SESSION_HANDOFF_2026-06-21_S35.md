# SESSION HANDOFF — S35 (2026-06-21) — REFRAME: predict winning trades by their DISTINCTIVE FINGERPRINT (stacked toolkit), as early+accurate as possible; Direction-2 discovery DONE

Worktree `E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6` (branch
`claude/crypto-trading-platform-plan-MpqwG`). Read order: `CLAUDE.md` (S35 delta top) → this file →
`KICKOFF_2026-06-21_S35.md` → `BUILD_PLAN.md`. Memories auto-load: `bucket-distinctiveness-is-the-goal`,
`markets-dipole-deconfound-verdict-s34`, `tools-are-complementary-not-competing`,
`deploy-signal-per-cell-not-universal`, `markets-deploy-feature-parity-gap`,
`refrag-parallel-discovery-race-fix`.

## THE REFRAME (Greg, S35, load-bearing — this is the whole frame)
**The goal is to PREDICT WINNING TRADES by their DISTINCTIVE FINGERPRINT, as EARLY and as ACCURATE as
possible.** Each winning trade has a distinctive fingerprint built by STACKING the whole complementary
toolkit — the **dipole** (per-bucket 128-dim OD coeff signature), the **6 micros** (mean_dipole,
dipole_acl1, volume_zscore, trade_present_score, trade_recent_2chunk_bps, trade_from_onset_bps),
**refrag** (the OD discovery pipeline), and **any other BUILD_PLAN tool**. Extracting these distinctive
traits (already mapped) is a capability no one else in the world has — it is the moat.

**What is NOT the method (Greg, said repeatedly):** the strength of the dipole alone does NOT matter; do
NOT balance win/lose classes, do NOT average coeffs into win/lose centroids, do NOT grade by win-vs-lose
SEPARATION (AUC / perm-null z). Those operations blur away the per-bucket distinctiveness that IS the
predictive fingerprint. The STACK of tools itself stays — it IS the fingerprint; only grading it by class
separation is dropped. Evaluate + deploy PER CELL by distinctive fingerprint, never by separation stats.
Greg's words: "we want to predict winning trades based on their distinctive traits which we have already
mapped … that's what we're doing now is getting the distinctive traits"; "along with the dipole we have
the 6 micros, and any other tool like refrag to fingerprint these trades as early and as accurate as
possible"; "it doesn't matter about the strength of the dipole, it's that each bucket is very distinctive."

**WHY the buckets (cells = asset × venue × side):** coins behave differently ACROSS VENUES (same coin,
different platform), different COINS behave differently, and BUY vs SELL look different → they must NEVER
be pooled; each cell is its own category. Within a cell, WINNERS vs LOSERS differ in HEAD vs TAIL pressure
(order-flow & price pressure at the trade's onset/head vs its recent/tail) — the distinctive trait the
fingerprint must capture (head ≈ `trade_from_onset_bps`, tail ≈ `trade_recent_2chunk_bps`; ensure order-flow
PRESSURE is captured, not just price bps). That winner/loser head-vs-tail-pressure difference is WHY winners
are fingerprintable.

## STATE (S35)
- **Direction-2 discovery DONE.** Ran as a DETACHED Windows scheduled task `markets_cand_disc` (4 workers,
  ~52min), enabled by fixing the WinError 5 race (retry `os.replace` in shared refrag
  `…\control_plane\storage.py::save_json`; index.json race cosmetic — `refrag-parallel-discovery-race-fix`).
  **~1,919 DISTINCTIVE cand_sp coeff signatures** landed across all 12 isolated
  `E:\refrag\discoveries\operator_discoveries\markets_<pair>_win_cand_sp\` domains; every cell now has its
  own distinctive coeffs (buy cells ~6-10 → 150+; eth_kraken_sell 25→79). Task is `Ready` (finished);
  `schtasks /delete /tn markets_cand_disc /f` to clean up when convenient. **The distinctiveness IS the
  deliverable** — discovery did its job.
- **`_balanced_rerun.py` ran** (2909 merged coeffs). Under the OLD separation lens: dipole 0/12 survive the
  within-period perm null (best btc_coinbase_sell z=+2.88); several S34 micro AUCs deflated with balanced
  classes (btc_kraken_sell 0.723→0.546). **Per the reframe this is the WRONG lens** — separation was never
  the goal. Recorded in `_balanced_rerun_results.json`; do not read it as success/failure of the asset.

## DEPLOYMENT = RECOVER + PORT (verified this session; `markets-deploy-feature-parity-gap`)
To fingerprint live, the platform must compute the tools live. Mapped end-to-end:
- **HEAVY tier already live + validated:** `_markets_gate_v2.py` `GateV2.recompute_coefs` does the 128-dim
  OD-coeff live recompute (pre-entry 30m slice → refrag pipeline window=192/stride=16, **memoized per
  (pair, decision-second)**, returns `latency_s`) + the centroid projection `info_score`. Canary-validated
  reproducible (determinism 1.0, cosine 0.995). AWS-scalable (Greg: can turn CPUs up; a "tick slow" entry
  is acceptable) — this matters because the OD coeff is the heavy part of the fingerprint.
- **6-micro computations: stripped in the S20+ rebuild, RECOVERABLE from git** (not lost). They are in
  `mock_trade_replay.py:884-890` @ commit `c486d3b` inside `current_status_from_visible`:
  `trade_from_onset_bps/current_chunk_bps/recent_2chunk_bps = _signed_bps(<chunk price>→close, side)`;
  `trade_present_score = _present_trade_score(...)`; `dipole_acl1 = feat.dipole_autocorr_lag1`. The live-tail
  wrapper `live_mock_trade_replay.py` (commit `1a92179`, `claude/run-pass-14-classifier` branch) already
  wired gate_v2 in SHADOW mode (`_gate_v2_shadow_score`, ~line 1559). `mean_dipole`/`volume_zscore`/
  `dipole_autocorr_lag1` already exist in the current `MarketFeatures` (markets_adapter.py:122).
- **Wiring path verified:** `SignalGenerator` (adaptive_backtester.py:52) via `make_od_generators`
  (odcore/generators.py:68); OD-native sizing `od_size_fraction` (odcore/sizing.py:29).
- **A port investigate→design workflow ran** (`port-feature-encoder-investigate`, run id wf_1c7fbfb9-f59;
  script under `…\workflows\scripts\`) to extract the exact git formulas + current integration points +
  ground-truth bucket values for a faithfulness canary. (NOTE: it was scoped around the 6-micro stack; the
  reframe makes the fingerprint = ALL tools stacked, so treat its output as the micro/coeff-port spec.)

## STEP 1 RECOVERED — the exact port spec (verbatim from git) + a box lesson
The feature math stripped in the rebuild was recovered VERBATIM from git c486d3b (analysis-by-direct-read,
after a Workflow wedged — see box lesson below):
- `backend/api_server.py:932-994` @ c486d3b (stripped from current platform):
  - `_signed_bps(entry, exit, side) = sign(side) * math.log(exit/entry) * 1e4` (signed log-return bps; 0 if either price <=0 or side unknown).
  - `_trade_score_band(score)` — simple 0-100 banding.
  - `_present_trade_score(status, inputs)` — a 0-100 COMPOSITE: adjusted_confidence (x35 cap 35) + regime/
    pressure bonuses (STRONG_PRESSURE_REGIMES +25, WHALE_NASCENT +18, forming/high_priority +12, internal +6)
    + |mean_dipole| bonuses + volume_zscore bonuses + trade_from_onset_bps/2.5 + trade_current_chunk_bps/2.0
    + age penalties + onset/recent-2chunk penalty. **NUANCE: this folds in regime/pressure + dipole + volume,
    so faithful live reproduction needs the regime/pressure pipeline to match the bucket-gen values — the one
    feature with a reproduction risk; the canary must check it.**
- `mock_trade_replay.py:873-890, 973-975` @ c486d3b — the assembly inside `current_status_from_visible`:
  `start_price = chunk.bars[0].close`, `close_price = chunk.bars[-1].close`,
  `recent_start = chunks[-2].bars[0].close` (else start_price), `onset_price` tracked per-trade (fresh=start).
  `trade_current_chunk_bps=_signed_bps(start,close,side)`; `trade_recent_2chunk_bps=_signed_bps(recent_start,close,side)`;
  `trade_from_onset_bps=_signed_bps(onset,close,side)`. Chunks/feats from `MarketChunker`/`MarketChunkEncoder`
  (window CHUNK_MAX_SIZE/min CHUNK_MIN_SEGMENT) — **both classes exist in the current `markets_adapter.py`**.
  `dipole_acl1=feat.dipole_autocorr_lag1` (already a current MarketFeatures field).
- HEAD = onset (`trade_from_onset_bps`), TAIL = current/recent-2-chunk (`trade_current_chunk_bps`,
  `trade_recent_2chunk_bps`). These are PRICE bps; capturing order-flow PRESSURE (head/tail imbalance) is a
  separate enhancement on top of faithful reproduction.

**BOX LESSON (`markets-box-workflow-constraint`):** the investigate→design Workflow WEDGED on this 4-CPU box
(concurrency cap = min(16, cpu-2) = 2; ~23min no progress, only 1/4 agents returned, runtime untrackable). For
live-path/precision tasks here, prefer DIRECT extraction + a canary as the deterministic check; keep any
Workflow small.

## STEP 2 RESULT — encoder + canary BUILT; canary caught a reproduction gap (did its job)
Built `odcore/fingerprint.py` (the live encoder: verbatim `signed_bps`/`trade_score_band`/
`present_trade_score` ports + the exact MarketChunker(30/15/10,hybrid) + MarketChunkEncoder recipe) and
`_canary_fingerprint.py` (recompute micros from real pre-entry `live_data_history` bars, compare to stored).
- `signed_bps` math VERIFIED EXACT (unit test PASS).
- Reproduction FAILS: 5/48 chunk-derived micro checks pass; the rest differ LARGE + SYSTEMATIC — bps off
  10-100x and often WRONG SIGN (e.g. btc_kraken_sell stored trade_current_chunk_bps=+98.4, recomputed -3.46;
  stored bps are consistently large + FAVORABLE for the winning sells), mean_dipole ~0 vs stored 0.17-0.41,
  `chunk_id` never matches. Because the ported math is proven, this means my reconstruction of the audit's
  INPUT (bar source / visible window / which chunk) is wrong — not the math.
- TWO hypotheses to settle: (1) WINDOW/BAR-SOURCE mismatch (benign — maybe normalized `realbins` esp. kraken,
  a different visible-window length, or the chunk selected by `chunk_id` not "most recent"); (2) the stored
  micros were computed with LOOK-AHEAD (post-entry bars in the chunk) → systematically favorable for winners
  and NOT reproducible pre-entry live (serious — threatens "fingerprint early"). The systematic favorable sign
  is suggestive of (2) but not conclusive.
- The canary correctly BLOCKED wiring an unfaithful signal. NEXT diagnostic: find the missed-winner audit-gen
  code (how it built `visible_bars` + picked the chunk per trade — likely stripped to git like
  `mock_trade_replay`); `chunk_id` (embedded in each `source_id` as `ASSET|venue|<chunk_id>|side`) is the key
  to confirm the exact window. Do NOT wire the encoder into a SignalGenerator until the canary passes.

## NEXT (build toward the goal — confirm method with Greg before heavy build)
1. **Assemble the per-cell live FINGERPRINT**: stack the live tools (gate_v2 128-dim coeff + centroid
   projection; the 6 micros recovered from git; refrag; others) into one per-trade fingerprint, computed as
   EARLY (pre-entry, minimal data) and as ACCURATELY as possible.
2. **Predict winners by distinctive fingerprint, PER CELL** — recognize a winning trade by matching its
   fingerprint to the mapped distinctive winning-trait signature for that cell. NOT a balanced-class AUC
   separator. (Exact predictor method is the open design question — frame around distinctiveness/identity.)
3. **Deploy per cell** (`deploy-signal-per-cell-not-universal`): wire the per-cell fingerprint predictor as
   a `SignalGenerator`; OD-native sizing; partial coverage is fine.

## FILES (this session, untracked in `E:\Markets` unless noted)
- Built: `_netcost_stack.py`, `_netcost_stack_balanced.py`, `_micro_attribution.py` — these are
  SEPARATION-frame tools (stack-gated net-cost, per-cell micro AUC). Kept for reference, but the reframe
  supersedes the "grade by separation/net-cost-on-a-separator" use; the STACK of tools they assemble is
  still the fingerprint material.
- Ran: `_balanced_rerun.py` → `_balanced_rerun_results.json`.
- Recover sources (git, not working tree): `mock_trade_replay.py` @ c486d3b, `live_mock_trade_replay.py`
  @ 1a92179. Live heavy tier: `_markets_gate_v2.py` (untracked, E:\Markets root).

## ENV / RULES
- Crypto trading platform per BUILD_PLAN.md only. Quote service OUT. Zero-synthetic (no synthetic trading data).
- Did NOT branch-switch shared `E:\Markets`. **Commit + push working files (code/docs) REGULARLY — git is the
  source of truth** (Greg S35; the old "no commit/push unless asked" rule is REMOVED). Data/bins stay LOCAL
  (`markets-data-lives-local-not-git`). Discovery now parallel-safe
  (`--workers 4`) after the os.replace fix — but it is DONE, do not relaunch.
