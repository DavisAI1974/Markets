# SESSION HANDOFF — S88 (work date 2026-07-13) — data feeds + the RAW-INGESTION correction

Branch: rebased onto the s79 trunk at start. All code pushed to `claude/kalshi-s79-kickoff-ij8t9o`.

## The headline: the operating principle got corrected to RAW INGESTION (Greg S88)
- **Historical data is RAW and we keep ALL of it** -- every message, every column the dataset carries. We
  paid for the full dataset; we store the full dataset. The agent sifts the raw data for correlations
  (how events / weather / storage / curve move price). We score the raw data; we do not reduce it on the
  data side.
- **Gates live ONLY on our side, for TRADE SIGNALS** (the execution/entry layer) -- never on the
  historical data.
- This corrected the earlier framing in-session (which had leaked trade-side pre-processing onto the data
  side). The data feeds (pull, curve, temp) were already raw; the fix below and the S89 rework align the
  rest.

## What was BUILT / FIXED (on the trunk)
1. **`databento_backfill._write_mbp10_df` REWRITTEN to keep ALL raw info** (S88 `487e633`): every MBP-10
   message (trades AND book updates) + every column (all 10 price levels + sizes + counts per side,
   action/side/depth/flags/sequence/ts_event/ts_recv/...). Zero filtering, zero reduction, zero derived
   fields. `_json_safe` normalizes cells (Timestamp->epoch, numpy->python, NaN->None) without losing info.
2. **`nws_temp_feed.py`** -- gas-weighted HDD/CDD + precip from the NWS ASOS network (IEM), national
   demand-weighted stations, realized (path A) + decision-time forecast (path B). Temp cache committed
   (`data/nws_temp/gw_degree_days.json`, ~378 days) for durability. Selftest PASS.
3. **`forward_curve.py`** -- backwardation/contango + prompt-vs-term axis from Databento calendar-rank
   daily bars. Ran on the year (CL backwardation, NG seasonal hump). Leakage-safe D-1 asof. Selftest PASS.
4. **`FORECAST_AGENT_DIRECTIVE_S88.md`** -- Greg's forecaster spec captured (per-commodity, per-location
   deferred, temp/precip/weekday conditioning, anti-lock-in, coin-style workflow). NOTE: its cell/scoring
   language predates the raw-ingestion correction -- reconcile in S89 so the DATA stays raw and any cell
   structure is DISCOVERED from the full raw tape, with gates kept on the trade side.

## Scaffolding built in-session that needs REWORK to raw (S89)
`month_characterize.py`, `bucket_continuation.py`, `forecaster_month_pass.workflow.js`,
`GRAPH_LEARN_FINDINGS_S88.md` -- the scoring/forecaster scaffolding. It proved out the tooling
(leakage gates, per-cell distributions, the coin-style fan-out workflow ran end-to-end and flushed real
bugs incl. a date-format leakage bug now fixed). But it pre-processes on the ingest side; per the
raw-ingestion principle that pre-processing moves to the trade-signal side, and the scoring reads the FULL
raw tape. Rework AFTER the ingestion workflow is landing the raw corpus.

## The pull situation
- `pull_year_mbp10.py` proved the pull mechanics (batch -> decode -> gzip-per-month -> push -> delete
  local, resumable) but needs a live session and kept dying on container restarts.
- **S89 = build a DURABLE raw-ingestion workflow** (reuse a coin durable-collector cron as template, point
  at Databento MBP-10, longer duration) -- see `KICKOFF_2026-07-14_S89.md`.
- Size plan: raw is large but gzips hard; gzip per month (or per DAY if a month's local decode exceeds the
  ~24GB container disk) and delete local each chunk. Branch holds the gzipped corpus, restored free.
- CORRECTION (Greg, S89): there is NO "reduced" data tier -- that framing was a mistake. All historical
  data is RAW and we keep ALL of it. The `nymex_cont/` that was on the branch was simply an earlier,
  INCOMPLETE pull (written before the S88 raw writer, so it did not carry every column). It has been
  WIPED and is being re-pulled full-raw for all 12 months (2025-07..2026-07) via the S89 durable workflow.
  Wherever this handoff says "reduced," read "earlier incomplete pull" -- the only data we store is the
  full raw tape.

## RULES (unchanged + S88): historical data RAW, keep ALL info, zero gates on the data side; gates ONLY on
trade signals; the agent sifts raw data for driver->price correlations; leakage gate before any scoring;
exclude the settle window (trade side); net-of-fee maker AND taker; zero synthetic; provisional-until-live;
NYMEX=canary, fire on Kalshi; Databento = pay-once to the git branch; weather forecaster = Greg's spec
HANDS OFF; DATABENTO_API_KEY is a secret.
