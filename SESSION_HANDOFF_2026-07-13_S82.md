# SESSION HANDOFF — S82 (2026-07-13) — Kalshi: the per-trade LEVEL-HIT dataset built; it says the edge is EXTERNAL

Branch **`claude/kalshi-s79-kickoff-ij8t9o`** (= repo DEFAULT; push there). Harness dropped me on a fresh
branch at the stale **S70 tip `3c70ff5`** (the recurring trap the kickoff warns about) — switched to the
s79 tip `816f621`. All work committed + pushed to s79.

## The session (gameplan → build)
Read the 4 kickoff files, checked branch, and probed live data state, which reshaped the priorities:
- **Priority #1 (sub-second Pyth lag) is BLOCKED on data that does not exist.** The Pyth durable workflow
  run #1 (`29185118959`) has been stuck `queued` since ~07:59 UTC and **never executed** → `data/pyth-ticks`
  branch does not exist, zero ticks. Plus it's Sunday — energy futures reopen only ~Sun 22:00 UTC, so there'd
  be nothing but the frozen weekend price (deduped out) until then. **Greg must click "Run workflow" on
  `pyth_collector_durable.yml`** (my token can't; likely jammed behind the 6h kalshi collector).
- Greg chose **"Both: #3 then stage #2"** → build the per-trade level-hit dataset (priority-1 for 3 sessions,
  fully doable now, no external dep), then stage Thursday's natgas.

## #3 — the PER-TRADE LEVEL-HIT dataset (DONE) — `research/kalshi/level_hit_dataset.py`
Re-pulled the full **496,306-trade** WTI tape (`kalshi_history.py --series KXWTI --all --top 12
--skip-candles`, ~7 min, local). Built **200,421 level-hit events**: one row per 1¢ price transition on a
strike's trade tape, with strictly-PRE-hit context (leakage-gated closure over the last 20 trades) and a
forward trailing-exit outcome (bounded by the daily-settle exclusion). Per-cell (moneyness × side ×
velocity-regime × release), distributions not means, zero synthetic. Output `data/level_hits_KXWTI.json`
(local, gitignored). Full findings: `research/kalshi/LEVEL_HIT_FINDINGS_S82.md`.

**Leakage gate PASS (0 fails).** The context closure is invariant to future trades.

**The finding (honest — a Result-Discipline negative that sharpens the program, NOT a money result):**
1. **Level-hits MEAN-REVERT at the 1¢ scale** — continue_rate **0.383 < 0.5**, big-run(≥2) rate 0.24, run
   median 0. The bid/ask bounce dominates a 1-cent level.
2. **NO cell pays on average, even at MAKER fees** — best cell maker-mean −0.63¢; cross-cell aggregate
   −1.45¢, maker pos_frac 0.13. Trading level-hits blindly loses in all 60 cells. **This confirms S81
   (edge is SIZE-vs-FEE, direction is the easy part) at per-TRADE granularity.**
3. **Cell splits barely move net** — release≈non-release (−1.45 each; rel continues slightly LESS =
   spike already spent), fast≈slow, deep-moneyness loses least (tiny fee) but continues least (0.33).
   Winner cells = deep-moneyness × release (smallest fee × catalyst).
4. **The pre-hit ORDER-FLOW context is a WEAK big-run predictor** — winner-fingerprint lift (share among
   run≥2 minus base) is +0.00…+0.03 for herd/whale, dipole exhaustion, expect. The strongest single
   feature is `aggr` (the aggressor of the *hitting* trade, +0.05) but it is near-tautological with `dir`.

**META-CONCLUSION (the load-bearing takeaway):** the Kalshi-INTERNAL continuation predictor is weak +
fee-bound → **the tradeable edge is EXTERNAL — the futures→Kalshi LAG (S80/S81), not the book's own flow.**
The level-hit that becomes a run is most plausibly the one TRAILING a fresh NYMEX/ICE move, which is NOT in
this tape. **The natural upgrade: join the Pyth `futures_move_bps`/`lag_seconds` onto each level-hit event**
(needs `data/pyth-ticks`) → the internal context is weak precisely because the driver is external; that join
turns this scaffold into the real continuation predictor.

## #2 — Thursday 7/16 EIA natgas (STAGED, turnkey)
- `consensus_poll.py` confirms **Thu 2026-07-16 14:30 UTC Natural Gas Storage → KXNATGASD** (prev 61B;
  forecast fills in near release) + Wed 7/15 EIA crude → KXWTI. Consensus persisted to `data/kalshi/consensus.jsonl`.
- Materialized accrued `data/kalshi-bins` → `data/kalshi/KXNATGASD_bins.jsonl` (5,740 bins, current to 7/13).
- `release_book_signal.py --selftest` = leakage PASS 30/0; `--test --series KXNATGASD` runs (rel=0/event=None
  only because the release-spanning window hasn't accrued yet — it fires when Thu's bins land). Turnkey.
- **Thursday to-do:** re-run `--test` on the release-spanning bins + busy-day natgas lag on live NGDQ6 Pyth
  ticks (if feed unstuck); run `consensus_poll.py` before (forecast) + after (actual via EIA).

## Files this session
New: `research/kalshi/level_hit_dataset.py`, `research/kalshi/LEVEL_HIT_FINDINGS_S82.md`. Updated:
`KALSHI_TRADING.md` (index), `CLAUDE.md` (header + S82 delta), `.gitignore` (level_hits_*.json, pyth_ticks/).
Local-only: `data/kalshi_hist_trades/KXWTI/` (496k tape), `data/level_hits_KXWTI.json`, `data/kalshi/*_bins.jsonl`.

## END OF SESSION — Pyth feed UNSTUCK + Actions cleanup (commit `a9d590e`)
The Pyth durable run had sat `queued` and never executed because **11 legacy crypto collector workflows
were hogging the GitHub Actions runners** — worst offender `bybit_perp_history_durable` (every 15 min),
plus 8 coin/book collectors on 6h crons + `paper_trade` + 2 backfills. Greg manually dispatched the Pyth
run (now `in_progress`); then we **DELETED all 11 crypto workflows** on the default branch (recoverable via
git history), keeping only `kalshi_collectors_durable.yml` + `pyth_collector_durable.yml`. Their crons now
stop firing → runners freed. **Real Pyth ticks accrue once energy futures reopen (~Sun 22:00 UTC); the 6h
cron spans the reopen so `data/pyth-ticks` should fill tonight, well before Thu natgas.** No queued/stuck
runs remain. (If the Pyth run goes `queued` again after this, it's an account-level Actions issue — check
billing/minutes or runner cap in the repo's Actions settings, not the workflow.)

## NEXT (S83)
1. **Join Pyth futures move onto the level-hit dataset** — the external-driver hypothesis: do big-run
   continuations concentrate on level-hits trailing a fresh futures move? (needs `data/pyth-ticks`.)
2. **Sub-second lag on accrued ticks** (priority-1) — once Greg unsticks the Pyth workflow + ticks accrue.
3. **Thu natgas live** — re-run the release book test on release-spanning bins + join actual via EIA.
4. Standing: front-month roll re-point (WTIQ6 7/21, NGDQ6 7/29, BRENTU6 7/31); paper-loop RSA creds;
   OD-weather → `kalshi_score.py` (Greg's spec, hands off).

## RULES (unchanged, load-bearing)
EACH TRADE INDIVIDUALLY, never average; distributions + per-trade fingerprints not means; per-cell always
(moneyness × side × velocity/lag-class × release); exclude the settle window; catalyst = trigger + coarse
size / book+flow imbalance + exhaustion = direction + magnitude / herd breadth = continuation, whale =
scalp-only; leakage gate before any backtest; zero synthetic; provisional-until-live; weather = Greg's spec,
HANDS OFF; `--events` on news_coupling_research = BASENAME; keep `KALSHI_TRADING.md` current.
