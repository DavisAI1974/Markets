# KICKOFF S79 — Kalshi, continue (drop-in for the new session)

Read in order: `CLAUDE.md` (S78 delta at top) → `SESSION_HANDOFF_2026-07-12_S78.md` →
`KALSHI_BUILD_SCOPE.md` → `S77_REVIEW_FOR_CHATGPT.md`.
Branch: **`claude/kalshi-s78-kickoff-jb5oyx`** (based on S77 tip; all code present). Rules: per-contract
deploy; provisional-until-live; annualized-return not $/hr; git is source of truth; never size off one window.

## Where we are (end of S78)
The full Kalshi pipeline is built, verified, and pushed — collector (28 series: weather/macro/energy/
electricity), news ingest repointed to EIA/Fed/NHC with a per-contract keyword map, coupling adapter
(`--source kalshi`), settlement+scoring harness (`kalshi_score.py`), and a durable GHA collector
(`kalshi_collectors_durable.yml`, first run live → `data/kalshi-bins`). Two threads run: news→contract
coupling (macro/energy) and ⭐ weather-via-OD (Greg's own spec; `kalshi_score.py` is its scoreboard).

## FIRST: check the data pipeline
1. Did the durable run land `data/kalshi-bins`? `git ls-remote --heads origin data/kalshi-bins`. If yes,
   materialize: for each `<SERIES>_bins.jsonl.gz`, `git show origin/data/kalshi-bins:<f> | gunzip >
   data/kalshi/<f without .gz>`. If NOT (cron not on default branch yet), ask Greg to sync the workflow onto
   the default branch or Run-workflow it; meanwhile relaunch the collector in-session to accrue.
2. Run the ingest to refresh news events spanning any releases since S78:
   `python news_ingest_rss.py --output news_events.jsonl --lookback-hours 168`.

## NEXT (priority — pick with Greg)
1. **THE THESIS TEST (when bins span a real EIA/CPI/NFP/FOMC release):**
   `python news_coupling_research.py --source kalshi --data-dir data/kalshi --events news_events.jsonl
   --output-dir kalshi_coupling_out` → does a tagged release move its contract's probability beyond placebo?
   Report per-contract, per-category, per-horizon. This is the go/no-go on the news-coupling thesis.
2. **Weather-OD scoreboard** — when Greg's OD forecaster produces per-event distributions (or value+sigma),
   write them to `forecasts.json` keyed by event ticker or forecast date and run `kalshi_score.py --series
   KXHIGHNY --forecast forecasts.json --lead-minutes 60`. Edge = positive `brier_edge_vs_market` AND high
   `forecast_p_winner` on the realized bucket. **Use the lead-time bins baseline, not post-hoc last-price.**
   Same harness scores electricity (weather-driven) once regional ISO markets open.
3. **Kalshi microstructure thread** — port `research/shape_s71/early_signal.book_imbalance()` /
   `fit_direction_sign()` onto the mid-probability series (`--depth` bins carry the unified YES book). Test
   whether the wide-spread Kalshi book leans into a probability turn the way the crypto book leans into price —
   the maker edge crypto lost to the fee floor may survive here (train/test split, per-contract).
4. **Paper loop** — stand up `demo-api.elections.kalshi.com` with RSA-key auth (needs Greg's demo creds) to
   watch real fills, exactly like the S77 Hummingbot sanity check.
5. **Breadth** — add more contracts where Greg has edge (weekly/monthly WTI, jobless claims, PPI, GDP,
   hurricane-landfall, rain/low-temp). Breadth, not depth, is Kalshi's capacity answer.

## Housekeeping for Greg (his clicks)
- **Sync `.github/workflows/kalshi_collectors_durable.yml` onto the DEFAULT branch** so the 6h cron fires
  (GHA cron only runs from default; my token can't trigger runs). Optional fast smoke-test: Actions → "Kalshi
  Collectors (durable)" → Run workflow with `duration_seconds=300` → creates `data/kalshi-bins` in ~5 min.
- If you want cloud collection/storage beyond GHA: connect the Render workspace or provide AWS creds/IaC.
- Demo-API RSA key if you want the paper loop stood up.

## Guardrails carried from S78
- OD-weather honest scope: first defensible claim is OD as a **local operator / bias-correction on the exact
  station settlement variable**, tested to beat climatology + persistence + MOS — not "out-forecast ECMWF from
  raw obs." Escalate only if the modest claim clears (Result Discipline; no frame grades itself).
- `kalshi_score.py` market baseline MUST use lead-time bins (`--lead-minutes`), never settled last-price
  (post-hoc near-certain).
- Coupling: no trade flow in snapshots → volume/flow columns are N/A; the signed-bps-vs-placebo gate is the
  real test.
