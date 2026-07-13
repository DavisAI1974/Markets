# SESSION HANDOFF — S87 (work date 2026-07-13) — P3 lag join BUILT + intraday framework + Databento year-pull infra + the forecasting program

Branch: worked on harness branch cut from the stale S70 tip (rebased onto the s79 trunk at start). **All
code pushed to the canonical trunk `claude/kalshi-s79-kickoff-ij8t9o`** (default; pull before push). Data
on **`data/nymex-ticks`** branch (new `nymex_cont/` subdir = the continuous MBP-10 year tape, gzipped).

## The headline: P3 (the lag join) is BUILT and it PAYS (provisionally), and the program grew a forecaster
S87 turned the S85/S86 futures-move CEILING into a realized-EV trade engine, extended it from the single
14:30 release to the WHOLE intraday session, stood up the Databento year-pull infra, and — with Greg —
designed the next phase: an intraday NYMEX path FORECASTER as a stacked hold-length signal.

## What was BUILT (all on the trunk)
1. **`research/kalshi/lag_join.py`** — the lag join, ONE trade engine, TWO modes (folded together S87):
   - **RELEASE mode** (default): 14:30-anchored per-cell study (contract x surprise x coiled).
   - **INTRADAY mode** (`--intraday --day/--event/--root`): scan a day's continuous tape for EVERY sustained
     move (Greg: the storage print is one catalyst; headlines/leaks/risk moves are others — trade all day).
   - Trade model: ENTRY = taker the moment NYMEX moves trigger_usd DOLLARS and HOLDS confirm_s (sustained,
     not a poke); STAND-BACK if Kalshi already caught up; HOLD via a NYMEX DOLLAR TRAILING STOP (Greg's
     trend-hold — ride the trend, exit on a reverse_usd retrace, don't churn each sub-move); EXIT =
     maker-best-number (sell the top into the herd, ~0 fee) vs pure-taker floor. All $/c, never bps, tuned
     PER CONTRACT. Leakage-gated, settle-excluded, per-cell distributions, net-of-fee maker AND taker.
     `--selftest` PASS (leakage + fee + sustained-move detector).
   - RESULTS (PROVISIONAL, tiny-n, Apr-Jul): release CL taker +1c/57% maker +8c/86%, NG taker +17c/100%
     maker +21c/100% (the trend-hold made the TAKER floor positive, not just maker). Intraday 06-17 (Hormuz
     day): 49 sustained moves, the trend-hold flipped -115c -> +202c maker (65% pos, 82% fill). HEAVY
     caveats: one day / tiny-n / leans on the optimistic MAKER fill (taker floor marginal) / params tuned.
2. **`research/kalshi/databento_backfill.py`** — added `range` mode (sync continuous pull to a separate
   `--out-dir`, canary-sized) + **`batch_pull`** (submit -> poll -> download -> decode streaming, bounded
   memory) + `pull` mode. Canary validated: 3-day CL batch = $0.71, 173k rows; gzip = ~13x (14MB->1.07MB).
3. **`research/kalshi/pull_year_mbp10.py`** — month-by-month year pull: batch_pull CL+NG -> gzip into the
   `data/nymex-ticks` worktree's `nymex_cont/` -> delete local -> commit+push -> next month. Resumable.
   **STATUS: May-2026 driver canary was IN FLIGHT at handoff.** batch_pull + gzip+push validated separately;
   VERIFY the May canary landed on the branch, then launch the full year (below).
4. **Docs (the forecasting program):** `PATH_FORECAST_RESEARCH_S87.md` (cited methods survey — the honest
   verdict: intraday LEVEL near-unpredictable but continuation/shape CONDITIONAL ON EVENTS has measured
   skill, strongest around releases + high-vol days = OUR setup) + `FORECAST_AGENT_DESIGN_S87.md` (Greg's
   spec for the forecasting agent — see below).

## The forecasting program (Greg's S87 design — the next big build)
Forecast the intraday NYMEX (canary) TRADE-CURVE shape; use RT-vs-forecast tracking as the HOLD-LENGTH
signal (ride long legs, cut chop — fees force selectivity, the forecast is the selector). Greg's spec
(`FORECAST_AGENT_DESIGN_S87.md`): score/forecast PER COMMODITY and per LOCATION/variant SEPARATELY; the
agent DISCOVERS how each piece correlates with price-change/direction/momentum/exhaustion (pieces hit
several; correlate with each other; differ per commodity), conditioned on season/weather/regime. METHOD =
diverse sample of past days -> graph & learn -> BLIND forecast the curve -> compare to actual -> rescore ->
sharpen (walk-forward self-supervised; blind = the leakage guard). Build order (from the research): bucket
continuation table (baseline) -> event-time anchor + residual-z/shape-corr tracking overlay -> GBT
continuation classifier -> rolling FPCA -> HMM chop gate. FPC1/FPC2 = "how big" + "front-loaded vs
slow-bleed" = literally the S85 hold-time map.

## Data / cost decisions (Greg S87)
- **Databento historical = pay-ONCE.** Pull once -> gzip to the git branch -> restored FREE every session
  (session-start). No per-session re-pay. The git branch IS the permanent home.
- **Storage: 1-year to the git branch NOW, 2-year to S3 at go-live** (AWS is the live env). Cost map
  (free metadata.get_cost): 1yr MBP-10 CL+NG = $129.66 (~$5 over the ~$124.6 credit); 2yr = $279.19
  (~$154 real). Year gz ~400MB on the branch (~13x). MBO stays off. Live feed ($179/mo) = a go-live cost.
- **Forward-curve reader** (Databento deferreds) = to build; the tightness + prompt-vs-term conditioning
  axis. TradingView is display-only (no API); build the curve ourselves from Databento.

## OPEN / NEXT (priority order)
1. **Launch the full year pull** — `DATABENTO_API_KEY=db-... python research/kalshi/pull_year_mbp10.py
   --start 2025-07 --end 2026-07` (after: `git worktree add --force /tmp/nymexdata data/nymex-ticks`).
   Resumable, ~$130, multi-hour, pushes per-month to `data/nymex-ticks:nymex_cont/`. VERIFY the May canary
   result first. NEEDS A LIVE SESSION (background proc dies on container reclaim; just re-run to resume).
2. **Build the forward-curve reader** (Databento deferreds -> backwardation/contango + horizon map).
3. **Build the forecaster v1** (bucket continuation table) on the year library, then the tracking overlay
   into `lag_join.py`, per `FORECAST_AGENT_DESIGN_S87.md` + `PATH_FORECAST_RESEARCH_S87.md`.
4. **The forecast WORKFLOW** (noted top of KALSHI_TRADING.md): score+load tomorrow's forecast by 5PM the
   day before, recalc in the morning, re-match mid-session if RT stops tracking.
5. Standing: robustness of the intraday framework across calm+trending days (needs the year); NGDQ6 fix;
   weather forecaster scoring (Greg's spec, HANDS OFF).

## RULES (unchanged + S87 additions): each trade individually / per-cell / distributions not means; all
movement in $/c NEVER bps; tune PER CONTRACT but never to grab one trade and lose five; forecast predicts
CONTINUATION/HOLD-LENGTH not price; the tracking overlay is risk-control (net-of-fee EV delta vs fixed-hold)
not new alpha; FILE DISCIPLINE — edit live files first, only new-file if none exists (fold don't duplicate);
leakage gate before any backtest; exclude the settle window; net-of-fee maker AND taker; zero synthetic;
provisional-until-live; NYMEX=canary, fire on Kalshi; Databento = pay-once to the git branch; weather
forecaster = Greg's spec HANDS OFF; DATABENTO_API_KEY is a secret (db- prefix, re-export per session).
