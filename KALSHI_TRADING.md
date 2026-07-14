# KALSHI TRADING — file index

> **TODO — FORECAST WORKFLOW (Greg S87, not built).** Build a workflow that runs the daily NYMEX
> path-forecast lifecycle automatically:
> 1. **By 5PM the day before** — score and LOAD tomorrow's forecast (pick the analog/expected-path
>    curve for the next session, ready to trade against at open).
> 2. **In the morning** — RECALC it (refresh with overnight state: updated curve shape, news,
>    weather, storage, regime) before the session.
> 3. **Through the day** — if RT NYMEX ISN'T TRACKING the loaded forecast, FIND A NEW ONE
>    (re-match analogs / roll the forecast mid-session — the adaptive re-forecast). Distinguish
>    "analog was wrong -> re-forecast" from "move reversing -> exit."
> See `research/kalshi/PATH_FORECAST_RESEARCH_S87.md` for the methods.
>
> **HOW IT RUNS DAILY (Greg S90, "how do we remember to do this daily?").** The SAME daily lifecycle
> covers the WEATHER-DISTRIBUTION trade (KXHIGH*: score tomorrow's ladder by ~5PM, recalc in the AM,
> re-check intraday) AND the NYMEX path forecast. Do NOT rely on memory — the cadence must be a DURABLE
> DAILY TRIGGER. Mechanism: a GitHub Actions daily `cron` (matches the existing durable collectors;
> Greg dispatches/holds the secrets) OR a Claude Routine (`create_trigger`, daily cron, fires into a
> session). Wire the trigger once the forecaster EMIT (per the interface spec) + the per-cell scoring
> SCRIPT exist; until then this is recorded, not scheduled (a trigger firing into an empty pipeline is
> premature). See `WEATHER_FORECAST_INTERFACE_S90.md`.

The map of every Kalshi file: what it is, where it lives, and whether it's part of the CURRENT
pipeline or an OLD/completed piece. Keep this current — add new files to the top section, move
superseded ones down. (Started S81, 2026-07-12.)

> **FILE DISCIPLINE (Greg S87, load-bearing).** EDIT existing live files first; only create a NEW
> file if one does not already exist for that purpose. Do not spin up a parallel file that
> re-implements what a live file does — extend the live one with a flag/mode. (S87 lesson: a separate
> `lag_join_intraday.py` duplicated ~80% of `lag_join.py` and was folded back in.) Check this index
> before creating any file.

Data stores are LOCAL/gitignored (too big for git): `data/kalshi_hist_trades/` (historical trades),
`data/pyth_ticks/` (Pyth + Databento NYMEX trades ticks), `data/nymex_mbp10/` (S86: MBP-10 trade+book
depth tape), `data/kalshi/` (live bins + consensus). **S90: ALL Databento (bento) tapes now live on AWS S3,
NOT git** — bucket `bento-568968024170-us-east-2-an` (us-east-2), prefix `nymex/`: the continuous full-raw
YEAR corpus at `nymex/nymex_cont/{CL,NG}_YYYYMMDD.jsonl.gz`, the S85 trades tape at `nymex/nymex_tape/`, the
S86 depth tape at `nymex/nymex_mbp10/`. `kalshi-session-start` restores the tapes from S3 (needs AWS creds);
the continuous corpus streams on demand via `event_move_baseline.load_cont_day(..., source="s3")`. The
`data/nymex-ticks` git branch is retired for bento data (tapes removed S90; `nymex_cont/` wiped S89). Other
durable data still on branches: `data/kalshi-bins`, `data/pyth-ticks` (Pyth, non-bento). See
`research/kalshi/AWS_INGEST_SETUP_S89.md`. AWS + Databento keys are session-pasted SECRETS.

**S92 code changes (detail in `SESSION_HANDOFF_2026-07-14_S92.md`):** — the NG intraday FORECASTER program.
- `research/kalshi/month_characterize.py` — FULL-TOOLBOX per-leg characterizer: added the **exhaustion suite**
  (`depth_pieces` -> aligned_imb_push/exhaustion/far_thinning/spread_ratio, reuses `event_move_baseline.depth_features`),
  the **dipole** (`dipole_pieces` -> dip_imb_level/dip_aligned_flow/..., reuses `odcore.info_dipole`; Lee-Ready side),
  the **turning-point fingerprint** (`turn_pieces` -> turn_* measured entry->peak), and the **storage-surprise** +
  live **curve** joins. This is the per-leg fingerprint the forecaster/coach agents read.
- `research/kalshi/knowledge/ng_brain.json` (+ `knowledge/README.md`) — the machine BRAIN: versioned PLAYS
  (direction.flow_nowcast, ride.magnitude_staircase, exit.recruitment_reversal, shape.grind_vs_spike, daytype.*) +
  mechanisms + open frontier + ruled-out-by-target. The coach loads + applies it; the loop merges into it.
- `research/kalshi/NG_BEHAVIOR_KNOWLEDGE.md` — living, status-tagged knowledge base (grows every pass; the human view).
- `research/kalshi/NG_FORECAST_LOG_S92.md` — the blind-forecaster's reasoning + magnitude-scaling + the data-gap plan.
- `research/kalshi/FORECASTER_RUNBOOK_S93.md` — **VERBOSE operating manual** for the loop: the vision, the plays,
  the machinery, the exact loop commands, JOB 2 (net-of-fee coach replay), the guard, and the NYMEX-OPTIONS
  trading-vehicle survey (Greg S92: "look at nymex options for actual trading very soon"). Read this to run S93.
- `research/kalshi/coach_replay.py` — **executable playbook backtest** (the rigid baseline the adaptive coach must
  beat): applies ng_brain.json plays per leg net-of-fee, per-event, no pooling. Canary-side + indicative for now;
  real fill model + Kalshi/NYMEX-option venue = S93. `--selftest` PASS.
- `research/kalshi/forecast_harness.py` — turn-key loop helpers: `decision-state` (blind-safe group state),
  `overlay` (guess-vs-actual render), `brain-show`. `--selftest` PASS.
- `research/kalshi/redownload_mondays.py` — the Monday re-download tool (2-day [Mon,Wed) batch, upload clean over
  the stub). Re-run for the FINAL Monday sweep after the box finishes (it minted new corrupt Mondays past Sep).
- `research/kalshi/renders/ng_learn_s92/` — 12 learn-day curve grid + 12 individual day PNGs + the blind guess-vs-actual
  overlay + the forecasts JSON (for the intraday-curve grapher).
- `research/kalshi/databento_backfill.py` — **`_flush` fix: 'wb' -> 'ab' (append)** — the every-Monday-corruption
  root cause (Tue->Tue weeks made Monday the last batch day; a straggler re-created a 1-row file that the 'wb' final
  flush clobbered). Concatenated gzip members decompress as one; the reader sorts by ts.
- `research/kalshi/pull_year_mbp10.py` — **DOW naming** ({ROOT}_{YYYYMMDD}_{dow}.jsonl.gz) + **calendar-aware
  stub/marker** (`_expected_full`: weekends + CME full-closure holidays are legit-tiny, not corruption) + a
  **`--reconcile-names`** repair mode (rename date-only -> dow + write week markers; run after the box DONE) + `--selftest`.
- `research/kalshi/event_move_baseline.py` — `_s3_fetch_cont_gz` reads the dow-labeled name (legacy fallback).
- `research/kalshi/nws_temp_feed.py` — `--overwrite` flag (forward-collector top-up of the trailing months).
- `.github/workflows/nymex_mbp10_ingest_durable.yml` — rewritten git->S3 + `--weekly` (AWS+Databento GH secrets).
- `.github/workflows/nws_hourly_collector_durable.yml` — NEW RT NWS-hourly collector (trailing-2-months --overwrite -> S3).

**S91 code changes (detail in `SESSION_HANDOFF_2026-07-14_S91.md`):**
- `pull_year_mbp10.py` — **`--weekly`** (week-at-a-time S3 pull: 53 fresh per-week Databento batch jobs, per-week
  publish, marker-based resume `nymex_cont/_done/{root}_{ws}.done`) + **stub-aware resume-skip** (`_s3_month_present`
  treats a month with any sub-5KB stub or <15 days as ABSENT -> re-pulled). Runs on the durable box.
- `kalshi_collector.py` — added METALS (`KXGOLDD`, `KXSILVERD`) to the watchlist.
- `pyth_collector.py` — added Pyth `XAU`/`XAG` spot feeds (gold/silver settle number + fast underlying).
- `research/kalshi/GOLD_SILVER_LAG_FINDINGS_S91.md` — gold/silver depth-add: LAG confirmed (free Pyth), cross-strike NG-only.
- `research/kalshi/NYMEX_PRODUCTS_SURVEY_S91.md` + `KALSHI_PRODUCT_RANKING_S91.md` — the two S91 agent surveys (KXGOLDD #1).

**S90 code changes (detail in `SESSION_HANDOFF_2026-07-13_S90.md`):**
- `databento_backfill.py` — FIXED the flush bug (80% loss; hold-days-until-complete); `_download_decode_flush`
  + `redecode_job(jid)` re-decode an already-paid done job FREE.
- `pull_year_mbp10.py` — `--reuse-done-jobs` recovery mode (rebuild corrupt months from paid jobs, no re-charge).
- `event_move_baseline.py` — `load_cont_day(root, day, source="s3"|"local")` + `normalize_mbp10_row` (the JOB 2
  S3 tape reader: trade-filter + ladder-aggregate at READ time; S3 stream + local gz cache).
- `month_characterize.py` — `load_cont_full` routes through the shared reader + `--source s3|local`.
- `nws_temp_feed.py` — RAW HOURLY ingestion `--ingest-hourly` (`fetch_asos_raw`/`ingest_hourly_raw` -> every
  field/ob to `s3://.../weather/nws_hourly/`, NO roll-up); daily rollup now S3-synced (derived, not the store).
- `deploy/aws/` — the durable-box deploy kit (setup.sh + systemd units + runbook). The S90 EC2 box was launched
  ad-hoc via boto3 (AMI/SG/run_instances) with a self-configuring boot script pulling code from S3.
- `research/kalshi/WEATHER_FORECAST_INTERFACE_S90.md` — the forecaster emit-contract (per-cell distributions).

---

## CURRENT KALSHI FILES

### Collectors & data feeds
| file | what it does |
|------|--------------|
| `research/kalshi/kalshi_collector.py` | Live public-API order-book snapshot collector (28-series watchlist: weather/macro/energy/electricity). Unified YES book. → `data/kalshi/*_bins.jsonl`. |
| `research/kalshi/kalshi_history.py` | Historical settled-market trade puller — per-ticker fills WITH signed `taker_side` (real signed flow) + candles. → `data/kalshi_hist_trades/` (local). |
| `research/kalshi/pyth_collector.py` | **[S81]** Pyth Hermes sub-second tick collector for the NYMEX/ICE futures Kalshi settles on. SSE stream, dedup on advancing publish-time. → `data/pyth_ticks/`. NOTE (S84): the `NGDQ6` feed id is BOGUS (Pyth has no natgas) — fix pending; WTI works, Brent live-only. |
| `research/kalshi/pull_year_mbp10.py` | **[S87/S89]** The durable YEAR driver: pull continuous full-raw MBP-10 (CL+NG) month-at-a-time via `databento_backfill.batch_pull`, gzip each day AS IT LANDS + delete raw (local bounded to 1 day), resume-skip months already in the store. **`--dest`**: `git` (worktree of data/nymex-ticks) OR `s3://BUCKET/PREFIX` (boto3 -> PREFIX/nymex_cont/, standard AWS env auth). `--worktree`/`--scratch` to run anywhere. **S89: the tick corpus now lives on AWS S3** (`bento-568968024170-us-east-2-an`, us-east-2, prefix `nymex/`), NOT git; AWS + Databento keys are session-pasted SECRETS. |
| `research/kalshi/AWS_INGEST_SETUP_S89.md` | **[S89]** Runbook: bucket + IAM setup, the `--dest s3://…` run commands, the 6/6 disjoint-month split, resume, and end-to-end verify (download a gz, confirm 76-field raw rows). The live target + how a new session resumes the year pull. |
| `research/kalshi/databento_backfill.py` | **[S84/S85/S86]** TRUE-TICK historical NYMEX backfill from Databento (`GLBX.MDP3`): CL crude AND NG natgas at the `trades` schema (every print, nanosecond) — fixes Pyth's NG gap + 1-sec undersampling. Modes: cost / window (sync) / batch (large/cheap) / **defs** (S85: `definition` schema → `{ROOT}_definitions.jsonl` point-in-time tick size/value). **S86/S88: `--schema mbp-10`** → `_write_mbp10_df`. **S88 (Greg): keeps ALL RAW info** — every message (trades AND book updates) + every column (all 10 price levels + sizes + counts per side + action/side/depth/flags/ts_event/ts_recv/...), zero filtering/reduction/derived-fields (`_json_safe` normalizes without losing info). We paid for the full dataset, we store the full dataset; the agent sifts raw for driver→price correlations; gates ONLY on the trade side. → `data/nymex_mbp10/` (or `nymex_cont/`). `metadata.get_cost` gate. Needs `DATABENTO_API_KEY` secret. PRIMARY historical source. |
| `research/kalshi/pyth_backfill.py` | **[S84]** HISTORICAL per-second NYMEX backfill from Pyth's timestamp endpoint — windows around past releases, throttled (429/5xx backoff), dedup, → `data/pyth_ticks/` (tagged `src=pyth_hist_1s`). WTI only (Pyth has no NG; Brent-historical 404s). 1-sec UNDERSAMPLES — a lower bound, never the full tape. |
| `research/kalshi/consensus_poll.py` | Polls the free ForexFactory weekly JSON for release forecasts (Crude/NatGas/CPI/NFP/FOMC). → `data/kalshi/consensus.jsonl`. |
| `research/kalshi/month_characterize.py` | **[S88]** Per-(commodity, MONTH) CONTINUOUS-tape characterizer — the workflow's per-agent tool. Reads `data/nymex_cont/` all-session tape, detects EVERY sustained intraday move (reuses `lag_join.scan_moves`), tabulates per intraday cell (tod x dir x book {support\|oppose}; coiled/curve/temp tags) the forward-path distribution (peak_usd $/c, fast_capture, sustain_s, retention, continuation). The intraday complement to `bucket_continuation.py` (which is release-windows only). Leakage-safe (cell features pre/at-entry, invariant to future price), `--selftest` PASS. One month = one regime (anti-lock-in). |
| `research/kalshi/forecaster_month_pass.workflow.js` | **[S88]** The corpus-characterization WORKFLOW (coin-style fan-out, Greg S88). Per (commodity x month): agent runs `month_characterize.py` blind to other months -> SYNTHESIS accumulates + separates stable-across-months vs month-specific -> adversarial VERIFY kills one-month-only patterns. Structurally enforces the anti-lock-in rule. STAGED (not fired); run in waves as `nymex_cont/` fills: `Workflow({scriptPath, args:{items:[{root,month},...]}})` for months whose tape is restored. |
| `research/kalshi/bucket_continuation.py` | **[S88]** The BUCKET CONTINUATION TABLE — forecaster method #1, the honest baseline every fancier method must beat OOS. Per cell, tabulates the forward-path DISTRIBUTION off the release windows: peak_usd quantiles, fast_capture (S85 front-loaded fraction), peaked_fast, retention, sustain_s, time_to_peak, continuation rate, + curve/temp regime mix. Cell keys (from GRAPH_LEARN_FINDINGS): NG = surprise sign x mag x coiled-volume {quiet\|active}; CL = surprise sign x mag x aligned_imb_push {support\|oppose}; temp/curve stored as conditioning tags (split on the year). `forecast()` matches a new day's decision-time state to its cell. Reuses `event_move_baseline.build`. Leakage-gated (cell assignment invariant to forward outcomes), per-cell distributions, $/c never bps. `--selftest` PASS; `--run` leakage_pass 12/12 both. Ran on the 24 warm-season tapes = machinery-validation only; re-run on the year library. Table -> `data/forecast/` (gitignored). |
| `research/kalshi/GRAPH_LEARN_FINDINGS_S88.md` | **[S88]** The forecaster's exploratory graph-and-learn pass (directive method step 2) on the 24 weekly tapes. Honest corpus caveat: weekday/curve-regime/temp all collapse or collinear with the Apr-Jul calendar ramp at n=12; only surprise sign/mag + microstructure are orthogonal. CL: release weak catalyst, slow-bleed (fast_capture 0.27), hold key = aligned_imb_push->sustain +0.52. NG: release IS catalyst, front-loaded (0.66), surprise-MAGNITUDE selects shape (big->spike+short, small->grind+long), coiled-volume->magnitude per-cell. The empirical basis for `bucket_continuation.py`'s cell keys. Warm-season/n=12 provisional. |
| `research/kalshi/forward_curve.py` | **[S88]** The NYMEX forward-CURVE reader — backwardation/contango + prompt-vs-term conditioning axis (directive priority 2). Pulls Databento continuous CALENDAR-RANK bars `{ROOT}.c.0..c.11` (ohlcv-1d, ~$0.07/yr both) → per-date curve features {front, slope_1, slope_back, curvature, regime} in $ never bps. `curve_asof(D)` = leakage-safe D-1 settle (the curve the morning of D knows). `--selftest` PASS. Ran on the year: CL backwardation 311/312 (Hormuz-tight); NG summer-contango→winter-premium hump→backwardation (213/99). Cache → `data/nymex_curve/` (gitignored, $0.07 re-pull). |
| `research/kalshi/nws_temp_feed.py` | **[S88]** The gas-demand TEMPERATURE feed for the NG path forecaster (Greg S88 directive sec 6). Realized historical hourly temp+precip from the NWS ASOS network via IEM (path A, labeling/scoring) → national population/gas-weighted **HDD/CDD + precip** daily index (16 demand metros, first-cut weights, base-65, central-US gas-day boundary) + `regime_bucket` (hard_heat/mod_heat/shoulder/mod_cool/hard_cool). `forecast_index_today` = decision-time NWS-API forecast (path B, forward/live only — no historical forecast archive, so historical conditioning uses the regime-bucket proxy). Leakage-gated (day value invariant under appended future obs). `--selftest` PASS. Cache → `data/nws_temp/` (gitignored). NOTE: national demand-weighted, NOT Henry Hub's Louisiana weather; per-hub local weather = the deferred basis stack. |
| `research/kalshi/eia_surprise.py` | **[S86]** Historical release SURPRISE (seasonal PROXY: actual weekly change − 5-yr same-ISO-week avg) from EIA API v2 (DEMO_KEY): NG working gas + crude ex-SPR. → `data/eia_surprise.json`, consumed by `event_move_baseline.py --surprise-file` to split cells beat/miss×big/small. `--selftest` PASS. Forward real consensus (consensus.jsonl) preferred when present. |
| `.github/workflows/kalshi_collectors_durable.yml` | 6h durable cron: restore→collect bins + poll consensus→gzip+push to `data/kalshi-bins`. |
| `.github/workflows/pyth_collector_durable.yml` | **[S81]** 6h durable cron: restore→stream Pyth ticks→gzip+push to `data/pyth-ticks`. |
| `.github/workflows/nymex_mbp10_ingest_durable.yml` | **[S89]** Durable RAW-INGESTION cron for the continuous MBP-10 YEAR (CL+NG, 2025-07..2026-07). Runs `pull_year_mbp10.py` a MONTH AT A TIME as a Databento batch; keeps ALL raw (zero filtering); gzips each day as it lands (local never holds >1 day); ADDITIVE push to `data/nymex-ticks:nymex_cont/` (never orphan-force-push); RESUMABLE (skips months already on branch) so it survives across 6h runs. Needs the `DATABENTO_API_KEY` secret + Greg's first "Run workflow" click. |
| `research/kalshi/pull_year_mbp10.py` | **[S87/S89]** The month-at-a-time year driver behind the durable workflow: batch-pull each (month, root) → `databento_backfill.batch_pull(flush_dir=…)` gzips each day into the `data/nymex-ticks` worktree as it lands + deletes raw → commit+additive-push the month → skip months already on branch (resumable). Full-raw, zero reduction. |

### Event-move baseline (S85) — the canary-move expectation-setter [RAN ON REAL TICKS]
| file | what it does |
|------|--------------|
| `research/kalshi/event_move_baseline.py` | **[S85]** Per-EVENT move MAGNITUDE + DURATION on the true-tick futures tape (the NYMEX canary), per surprise-cell. Anchors a strictly-pre-release baseline, measures the forward peak in TICKS/$/bps (tick size POINT-IN-TIME from the `definition` store, source aggregated per-event) + duration (time_to_peak, sustain_s, retention → run/blip/fade) + the **FAST (60s) window** (`--fast`): the sub-minute lag-scalp ceiling (fast_bps/$/capture, peaked_fast). Distributions not means, per-cell, leakage-gated. Expectation-setting, sizes the hold time. `--selftest` PASS. RAN on 12 NG + 12 CL real release windows (S85). |
| `research/kalshi/EVENT_MOVE_FINDINGS_S85.md` | **[S85]** First real result: per-contract HOLD-TIME map. NG front-loaded (60s captures 66% of the move, ~$310/contract); CL slower (60s=27%, a longer hold gets the rest — e.g. $2,640 built over 17min). Both KEPT, different hold windows; EV-net-of-fee is the gate not frequency. Futures move = the CEILING, not Kalshi P&L (lag join next). Cost map + MBP-10 schema decision. |
| `research/kalshi/event_move_baseline.py --depth` | **[S86]** MBP-10 depth read: per-event resting-book imbalance at R (pre-event, leakage-gated) + at the initial push (`aligned_imb_push`, `exhaustion`, `far_thinning`), contrasted against run length. `load_tape_depth`/`depth_features`/`_depth_summary`. `--selftest` PASS (depth math + leakage). Consumes `data/nymex_mbp10/`. |
| `research/kalshi/DEPTH_RUNLENGTH_FINDINGS_S86.md` | **[S86]** Book run-length read on the canary (24 windows, leakage PASS 12/12). Logged per-cell correlation of push-book one-sidedness vs run length: **NG −0.17, CL +0.52** (opposite-signed). Provisional, n=12, Apr-Jul window only (seasonality confound — no generalization). `aligned_imb_push` = candidate hold-time signal for the lag join. |
| `research/kalshi/EVENT_STATE_DESIGN_S86.md` | **[S86]** Design sketch (Greg's driver model): events stack on prior + anticipated state. Three pillars (news / storage / market-capacity), shared drivers with per-market/per-period weights, weather split (NG temps-demand / CL adverse-supply), news in three tenses + persistent geopolitical regime, storage = physical confirmation node, human/emotion = herd run, pre-release volume = first buildable primed detector. Eyeball-validated (06-17 = Hormuz crisis). |
| `research/kalshi/PREVOL_FINDINGS_S86.md` | **[S86]** First build off the event-state model: pre-release VOLUME primed/coiled detector (leakage-safe, no new feeds). NG — quieter pre-release precedes a bigger move, consistent sign across all 3 cells (Spearman -0.5..-1.0); CL weak/mixed (consistent with CL trading Hormuz not the EIA print in-window). Per-contract normal (same scaffold, different values). Provisional n=12. |
| `research/kalshi/EVENT_SURPRISE_FINDINGS_S86.md` | **[S86]** Surprise-cell split (seasonal-proxy, 12/12 matched). Logged: NG beat|big cell (n=3) all down + fast; CL |surprise| negatively correlated with move size (the $2,640 day was a −3.1 small surprise). Opposite-signed surprise/move relation NG vs CL, Apr-Jul only — no cause claimed, no generalization. |
| file | what it does |
|------|--------------|
| `research/kalshi/futures_kalshi_lag.py` | Per-contract futures→Kalshi lead-lag (S19 operator + time-slide null). Result: futures lead, Kalshi never leads; ~half of contracts reprice a full minute late. |
| `research/kalshi/lag_exploit_backtest.py` | **[S81]** Turns the measured lag into a net-of-toll backtest. Modes: `futures` (economic gate + maker/taker exit) and `crossstrike`. `score_hold` = fire-quick-then-hold trailing exit. Per-trade, per-cell, no averaging. |
| `research/kalshi/LAG_EXPLOIT_FINDINGS_S81.md` | **[S81]** The lag findings: direction predictable (sharpens with move size, 0.77 on big moves), edge is size-vs-fee, real but rare at 1-min → needs sub-minute (Pyth). |

### Level-hit continuation thread (S82) — the per-trade continuation predictor
| file | what it does |
|------|--------------|
| `research/kalshi/level_hit_dataset.py` | **[S82]** The per-trade LEVEL-HIT dataset: one row per 1¢ level transition — pre-hit context {moneyness, side, velocity, herd/whale, exhaustion, tod, release} + forward trailing-exit outcome {continued, big-run, net taker/maker}. Per-cell (moneyness×side×velocity×release), distributions not means, leakage-gated. → `data/level_hits_*.json` (local). |
| `research/kalshi/LEVEL_HIT_FINDINGS_S82.md` | **[S82]** Findings: level-hits mean-revert at 1¢ (cont 0.38); NO cell pays even at maker fees (confirms S81 size-vs-fee); the internal flow context is a weak predictor → the edge is EXTERNAL (futures lag). Next: join Pyth futures move onto each level-hit. |

### Release / book signals
| file | what it does |
|------|--------------|
| `research/kalshi/release_book_signal.py` | Live release-triggered book signal: direction = book-imbalance sign, magnitude/fade = imbalance + dipole exhaustion. Calendar-gated. Leakage PASS 0/30. |
| `research/kalshi/release_signal_history.py` | Historical release-signal test on real signed flow. Carries the SETTLE_UTC settlement-window guard + leakage gate. (Pooled hit-rate first pass superseded by the per-trade reframe; the harness + settle filter stay current.) |

### Coupling / scoring / weather
| file | what it does |
|------|--------------|
| `research/kalshi/kalshi_coupling_adapter.py` | Feeds Kalshi mid-probability into the signed-edge-vs-placebo coupling engine (asset=series, venue=market). |
| `research/kalshi/kalshi_score.py` | Settlement + forecast SCORING harness. Realized settlement vs market-implied ladder; Brier/log-loss/edge; lead-time market baseline. The scoreboard the OD-weather thread plugs into. |
| `research/kalshi/kalshi_weather_forecast.py` | EIA storage-number baselines (climatology/persistence, walk-forward) + a (value,sigma)→kalshi_score bridge. NOTE: the weather forecaster itself is Greg's own spec — this is just the bridge/scoreboard. |
| `research/kalshi/weather_regime_score.py` (+ `weather_regime.json`) | **[S84]** Per-REGIME weather scoreboard runner: walk-forward persistence + climatology `(value,sigma)`, scored PER CELL (city × regime × swing) as DISTRIBUTIONS not means, leakage-gated (PASS 66/66). Drop-in for the OD operator's `(value,sigma)`. Forecaster HANDS OFF. |
| `research/kalshi/WEATHER_BASELINE_S82.md` | **[S82]** Daily-high temp (`KXHIGH*`) scoreboard reference: the naive baseline bar the OD operator must beat (persistence/climatology Brier ~1.1–1.3; the edge is on frontal/transition days), the market structure (6×~2°F re-centered ladder), + a worked trade example (real KXHIGHNY-26JUN29, realized 88°F) with fees/payout. |
| `research/kalshi/NYMEX_CANARY_NOTES_S84.md` | **[S84]** Load-bearing: NYMEX is the CANARY, Kalshi the delayed follower (gather NYMEX, fire on Kalshi). Resolution reality (1-min useless, 1-sec floor UNDERSAMPLES = lower bound). Data-source inventory: Pyth WTI historical works, NO natgas feed (bogus `NGDQ6` id), Brent-historical 404s; NG/Brent need Yahoo. |
| `research/kalshi/WEATHER_REGIME_FINDINGS_S84.md` | **[S84]** Distributions-not-means sharpening of S82: the naive bar is REGIME-CONDITIONAL (persistence wins calm, climatology wins transition); climatology's transition edge is COOLING mean-reversion into wide tail buckets, NOT a front forecast; WARMING-spike cells are where both baselines (and the market) go blind = the operator's real room. NY transition-rich, DEN ridge-thin. |

### Shared engines (not Kalshi-only, but the pipeline runs on them)
| file | what it does |
|------|--------------|
| `news_ingest_rss.py` | RSS ingest → contract tagging (EIA/Fed/NHC feeds → `CONTRACT_KEYWORDS` per Kalshi series; ENERGY/INFLATION/JOBS/… categories). |
| `news_coupling_research.py` | Signed-edge-vs-placebo coupling engine (`--source kalshi`). NOTE: `--events` is a BASENAME joined onto `--data-dir`. |
| `regime_classifier.py` | Regime classifier (shared). |
| `odcore/leadlag.py` · `odcore/info_dipole.py` · `odcore/leakage.py` | The operator tools the lag/signal work is built on (lead-lag, flow-dipole divergence/exhaustion, the mandatory leakage gate). |

### Skills (session rituals — `.claude/skills/`, added S83)
| skill | what it does |
|-------|--------------|
| `kalshi-session-start` | Session-start ritual: stale-tip branch check → read handoff/kickoff/index → materialize `data/kalshi-bins` + `data/pyth-ticks` locally → verify accrual (newest timestamp, not existence). |
| `kalshi-backtest` | The mandatory backtest discipline: leakage gate → settle-window exclusion → per-cell never pooled → distributions/fingerprints never means → net-of-fee at maker AND taker. |
| `kalshi-roll` | Re-point Pyth front-month feeds at contract expiry (FEEDS dict + docstring in `pyth_collector.py`, sanity-stream, push to trunk; old-symbol history kept, roll boundary = separate cells). |

### Current docs
| file | what it is |
|------|-----------|
| `KALSHI_TRADING.md` | This index. |
| `CLAUDE.md` | The lean live operating doc (S83 split; the pre-split OD/crypto/physics master is archived verbatim in `CLAUDE_ARCHIVE_OD.md`). |
| `KALSHI_BUILD_SCOPE.md` | The Kalshi build scope / thesis. |
| `research/kalshi/FORECAST_AGENT_DESIGN_S87.md` | **[S87]** Greg's spec for the path-forecasting agent (the job, structure, self-improving method). |
| `research/kalshi/PATH_FORECAST_RESEARCH_S87.md` | **[S87]** Cited methods survey for the NYMEX hold-length signal (bucket-continuation baseline first, then event-time anchor + tracking, GBT, FPCA, HMM gate). |
| `research/kalshi/FORECAST_AGENT_DIRECTIVE_S88.md` | **[S88]** OPERATIONAL directive for the forecaster-building agent — operationalizes the S87 design + research into scoped marching orders: v1 = CL+NG level only (hubs deferred); target = event-time continuation curve (magnitude+shape+continuation, never level-RMSE); blind = chronological date-cut; NG cells temp/±2wk/weekday-type (`Mon | Tue-Thu ex-storage | Storage-day | Fri | Sat | Sun`); gas-weighted HDD/CDD temp feed as a v1 build (forecast-issue for conditioning, realized for labeling); 24-weeks-then-year sequence; hold-length EV-delta output. |
| `research/kalshi/EVENT_WEIGHT_STUDY.md` (+ `event_weight_study.json`, `source_map.json`) | Per-bucket event-weight study (weather→storage strong; storage-surprise→price null). |
| `SESSION_HANDOFF_2026-07-13_S89.md` (+ S88, S87, S86, S85, S84, S83, S82, S81, S80, S79, S78) | Session handoffs (S89 latest: durable RAW ingestion BUILT + tick corpus moved to AWS S3 — zero-filter MBP-10 writer verified, `pull_year_mbp10.py --dest s3://…`, full-raw year pulling to bucket `bento-568968024170-us-east-2-an`, split container/Greg-box, resumable). |
| `KICKOFF_2026-07-14_S90.md` (+ S89, S88, S87, S86, S84, S83, S82, S81, S80, S79) | Session kickoffs (S90 next: finish/verify the full-raw year on S3, then rework the scoring scaffolding to read the raw S3 tape — pre-processing moves to the trade-signal side). |
| `research/kalshi/AWS_INGEST_SETUP_S89.md` | **[S89]** AWS ingest runbook (bucket/IAM, `--dest s3://…` commands, split, resume, verify). |
| `research/kalshi/WEATHER_FORECAST_INTERFACE_S90.md` | **[S90]** The forecast->trade INTERFACE spec: what Greg's OD temp forecaster should EMIT (per `city x regime x lead` residual DISTRIBUTION `(value,sigma[,quantiles])` + pre-hoc regime + routing, on the real KXHIGH cities not KGJT/KDDC) so it plugs into the `(value,sigma)->bucket-prob` bridge (weather-prob markets) + `nws_temp_feed` forward HDD/CDD (NG driver). Forecaster HANDS OFF; this is the scoreboard/bridge contract. |

---

## OLD / COMPLETED KALSHI PIECES

Exploratory one-off studies whose conclusions are folded into the current docs (kept for provenance,
not on the live path).

| file | what it was |
|------|-------------|
| `research/kalshi/hist/eia_bucket_study.py` (+ `eia_bucket_results.json`) | EIA storage per-bucket surprise study → folded into EVENT_WEIGHT_STUDY.md. |
| `research/kalshi/hist/event_study.py` (+ `energy_dow_results.json`) | Energy day-of-week / event study. |
| `research/kalshi/hist/intraday_study.py` (+ `intraday_results.json`) | Release-day intraday quiet→spike→decay study. |
| `research/kalshi/hist/macro_study.py` (+ `macro_results.json`) | Macro-print reaction study. |
| `research/kalshi/hist/macro_bucket_study.py` (+ `macro_bucket_results.json`) | Macro per-bucket surprise study. |
| `research/kalshi/hist/natgas_season_study.py` (+ `natgas_season_results.json`) | 4-regime natgas seasonal (degree-day) split. |
| `research/kalshi/hist/natgas_weather_chain.py` (+ `natgas_weather_results.json`) | Weather→storage→price chain study. |

### Superseded approaches (concept-level, files may still carry a current piece)
- **Pooled hit-rate / averaged-signal evaluation** — superseded by the S80 EACH-TRADE-INDIVIDUALLY /
  per-cell rule. Any surviving code (e.g. the first pass in `release_signal_history.py`) is kept only
  for its still-current parts (settle filter, leakage gate).
- **Precise surprise→move regression** — deliberately NOT built (null); replaced by the merged
  architecture (release = catalyst/coarse size; book imbalance + exhaustion = direction/magnitude).
