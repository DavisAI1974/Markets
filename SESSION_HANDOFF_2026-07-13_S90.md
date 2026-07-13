# SESSION HANDOFF - S90 (work date 2026-07-13) - full-raw year relaunched to S3; weather temp-edge discussion

Branch: came up on the stale S70 tip `3c70ff5`, rebased onto the s79 trunk `claude/kalshi-s79-kickoff-ij8t9o`.
Work in progress - the year pull is running in the background at handoff time; this doc is a LIVING record
(Greg: "update the handoff with your questions now so we don't forget"). Open questions are the last section.

## JOB 1 - finish/verify the full-raw MBP-10 year on S3

### What we found (load-bearing)
- **The S3 bucket was EMPTY** at session start - only `nymex/_healthcheck.txt`. Neither the S89 container half
  (Jan-Jun 2026) nor Greg's box half (Jul-Dec 2025) had landed ANY data. The whole year was unpulled.
- **Databento had already-DONE, already-PAID batch jobs that never reached the bucket.** 16 jobs on the key;
  the MBP-10 year ones done: CL Jul-2025 (x4), NG Jul-2025 (x2), CL Jan-2026 (x3), CL May-2026, NG May-2026,
  plus the CL 05-14 one-day proof and the CL 06-15..18 window. The duplicates (CL-Jul x4, CL-Jan x3, etc.)
  were Greg's own RANDOM TEST PULLS while iterating - NOT a runaway loop. ~$62 spent so far, ~$35 of it on
  those duplicate re-submits (the resume-skip checks the bucket, which was empty, so each re-run re-charged).
  The completed batch files ARE still downloadable (verified list_files: ~29-30 per-day .dbn.zst per month).
- **Greg's call: do NOT recover the old done jobs; just pull everything fresh to AWS.** "do not use old data
  that isn't already on aws." Clean uniform corpus > saving ~$22. Use the existing `pull_year_mbp10.py`
  (`--dest s3://...`), do NOT create a new file.

### What is running (background, this container)
`python3 research/kalshi/pull_year_mbp10.py --start 2025-07 --end 2026-07
   --dest s3://bento-568968024170-us-east-2-an/nymex --scratch /tmp/nymex_scratch`
- Full year CL+NG, month-by-month batch (day-split) -> download .dbn.zst -> decode -> 76-field raw JSONL ->
  gzip per day -> upload to `nymex/nymex_cont/{CL,NG}_YYYYMMDD.jsonl.gz` -> delete local (disk bounded ~1 day).
- **Zero filtering CONFIRMED in code** (not just the handoff note): batch request (schema=mbp-10, whole
  contract) -> `DBNStore.from_file(p).to_df()` (all messages/columns) -> `_write_mbp10_df` writes EVERY row
  (line 157-181), keeps ALL columns verbatim (line 174), `_json_safe` only makes cells serializable (no
  rounding/dropping); the old silent row-drop is fixed via the `_undated` fallback (lines 171-172).
- Resumable: if the container is reclaimed, re-run skips months already in the bucket. Greg pastes the
  DATABENTO_API_KEY + AWS keys (secrets, scratchpad-only, never git).
- At handoff: job 1 (CL 2025-07) still `queued` at Databento; bucket still filling. A background watcher
  pings when the first month lands -> then VERIFY a sample day end-to-end (download gz, confirm 76 fields).

## JOB 2 - rework scoring to read the RAW S3 tape (NOT STARTED, Greg said discuss first)
Four local-tape readers to point at S3 (all read `data/nymex_cont/` or `nymex_mbp10/` today):
`month_characterize.py` (`load_cont_full`), `lag_join.py` (`load_nymex_cont`), `bucket_continuation.py`
(via `event_move_baseline.load_tape`/`load_tape_depth`), `event_move_baseline.py`. Plan: ONE shared S3
reader (stream a day's gz via boto3 + gunzip, local gz cache) behind a `--source s3|local` flag - extend the
live files, do NOT fork (FILE DISCIPLINE). Keep leakage gates, per-cell distributions, $/c never bps.

## Weather temp-edge thread (Greg's OD forecaster - HANDS OFF; we build scoreboard/bridge + trade side)
Greg shared part 1 of `od_weather_discovery_knowledge.json` (part 2 + a doc land later via another session,
pushed to this trunk - a watcher is armed for it).
- **What it is:** OD corrects GFS 2m-temp error (`y = T_obs - T_gfs`, Day 2-5, 00Z, F). Bar = beat
  gradient-boosted MOS OOS (NOT raw GFS). Train 2022 / test 2023. Station KGJT (terrain) is the target;
  KDDC (flat) is the honesty control (null as intended).
- **It is a FLOOR, not a ceiling (Greg):** the numbers are the "GFS-only, before f000/ERA5 state features"
  phase - "if we did nothing else." The Day 2-5 numbers are being RE-RUN now; disregard whatever is on the
  JSON currently. State features + rerun + real-city breakdown can only ADD. The floor already CLEARS the
  bar (OD 3.11 < GBM 3.88 overall, and per winning cell), so it is a passing result, not a hope.
- **The edge is BROAD, and partly inverts the old S82 read (Greg corrected me):** not "transition days only."
  `where_OD_wins`: winter DJF +21%, MID-error 2-5F days +21% (n=626, the LARGEST cell), 32-50F +20%, hot
  95-105F +10%, autumn SON +6%, ALL leads f048-f120 +7..9%. Hard >5F swings are OD's SMALLEST edge (+3%).
  So the bread-and-butter is the everyday few-degree miss (most days), not rare frontal blowups. Route-away
  is narrow: easy <=2F days -> raw, <32F and 50-70F -> climo.
- **BUT depth/capacity is UNKNOWN (Greg: "we don't know if it's tall, it only broke down like that").** Those
  cells are the lens it was sliced on, not established structure. Provisional until the rerun. Do NOT bank
  the specific values or over-build sizing on them - bank the SHAPE (broad, everyday), not the magnitude.
- **Two trading surfaces for the same forecast:** (1) DIRECT - Kalshi KXHIGH* daily-high temp markets
  (6-bucket ~2F ladder; the `(value,sigma)->bucket-prob` bridge + `kalshi_score.py`/`weather_regime_score.py`
  score it per cell vs the market baseline). (2) DRIVER - a better forward gas-weighted HDD/CDD
  (`nws_temp_feed.py` path B) feeds the NG path forecaster's temp-conditioned cells (`bucket_continuation.py`).
- **Trade distribution (illustrative walkthrough, NOT a backtest):** a book of many small per-(city x bucket
  x day) binary bets; on a mid-error day OD hands a full ladder distribution, you buy the 1-3 buckets the
  market centered away from, small size (books thin -> depth is the binding constraint, not fee), only on
  non-route-away cells; ~8-20 lines/day x ~5-8 cities; the edge shows in the AGGREGATE of ~50-100 lines/week,
  never a single line. Per-cell never pooled; report the edge DISTRIBUTION across lines.

## RESOLUTIONS (Q1-Q4 worked in order this session; Greg took Q5 = IAM rotation)
- **Q1 pre-processing scope - RESOLVED.** The ingest-side pre-processing to move to the trade side is
  concretely (a) TRADE SELECTION (raw tape is every message; `price` is present on book-update rows too, so
  filter `action=='T'` to rebuild the S85 trade-print price path) + (b) LADDER AGGREGATION
  (`bid_dep=sum(bid_sz_00..09)`, `ask_dep=sum(ask_sz_00..09)`, top-of-book = level 00). Both are leakage-
  neutral per-row derivations. Old reduced tapes already had these baked in at ingest.
- **Q2 weather interface - DONE.** `research/kalshi/WEATHER_FORECAST_INTERFACE_S90.md` (the emit-contract:
  per-`(city x regime x lead)` residual distribution `(value,sigma[,quantiles])` + pre-hoc regime + routing,
  on the real KXHIGH cities not KGJT/KDDC). Indexed.
- **Q3 sizing/EV harness - DEFERRED (Greg's call).** Build only once the rerun gives real per-cell
  distributions; the EV/variance math is captured (daily std ~$296 fixed at 200x12; edge sets EV/day).
- **Q4 S3 reader - BUILT + self-tested.** `event_move_baseline.py`: `normalize_mbp10_row` (auto-detect
  raw-vs-reduced), `load_cont_day(root, day, source='local'|'s3', trades_only=True)` (S3 stream + local gz
  CACHE per Q4), `_list_cont_days`. `month_characterize.py` routes `load_cont_full` through it + `--source
  s3|local`. Normalizer/reader fixture self-tests PASS (trade-filter, ladder-agg, dedup, gz); both modules'
  `--selftest` still PASS (zero regression). NOT yet validated against a real S3 day (bucket still filling) -
  validate a sample day end-to-end when the first month lands. REMAINING JOB 2 piece: rework
  `bucket_continuation.py`/`event_move_baseline` RELEASE-WINDOW loaders to slice windows from the raw S3
  continuous tape (bigger; the continuous reader is the delivered core the kickoff asked for).
- **Weather scoring = SCRIPT first, workflow only for the verify pass later (Greg Q this session).** Do NOT
  build a workflow to CONSUME the interface - scoring a distribution over a ladder is deterministic numpy
  (extend `weather_regime_score.py` + the `(value,sigma)->bucket-prob` bridge). A fan-out WORKFLOW fits only
  the adversarial anti-lock-in verify pass (per cell: survives OOS? one-season-only? regime pre-hoc? flat-
  control leaking?) - and when built, EXTEND `forecaster_month_pass.workflow.js`, do not fork. Deferred until
  the rerun + confirmed depth. The forecaster's own run (`run_complete.py`) is already Greg's workflow.
- **2nd trading platform (Greg this session):** we will likely need a 2nd prediction-market venue for
  capacity, but NOT until we are live here - deferred, not a today job.
- **AWS deploy kit BUILT (Greg S90: "get things set up on aws correctly for our code to live there").**
  `deploy/aws/` — the "prep the deploy kit" path (Greg's choice): `setup.sh` (idempotent box setup: deps,
  `/etc/markets/markets.env` from `env.template`, install systemd units, enable daily trunk-update),
  `nymex-pull.service` (resumable year pull to S3), `markets-update.{service,timer,sh}` (keep checkout on
  trunk), `markets-daily.{service,timer}` + `daily_lifecycle.sh` (the daily forecast/trade lifecycle,
  timer DISABLED until the scorer exists), `README.md` (runbook). Recommends an IAM instance ROLE so the
  only on-disk secret is the Databento key. Syntax-checked, no secrets committed (placeholders only). Greg
  spins up an instance + runs `setup.sh`; I cannot provision compute (S3-only creds).
- **ALL bento data moved git -> S3 (Greg S90: "move all the bento data from git to aws").** Copied the S85
  trades tape (`nymex_tape/`, 28) + S86 depth tape (`nymex_mbp10/`, 27) from the `data/nymex-ticks` branch to
  `s3://bento-568968024170-us-east-2-an/nymex/nymex_tape/` + `nymex/nymex_mbp10/` (55 files, 3.75 MB;
  verified), then removed them from the branch tip (pushed `ee9f393..1634d1f`; 0 bento files remain on tip;
  history still holds old copies, not purged). Updated `kalshi-session-start` to restore these from S3 (boto3)
  instead of git, and KALSHI_TRADING.md's data-store note. The continuous year corpus was already S3-only.
  Net: git holds NO bento data now; the bucket is the single store for all Databento tapes.
- **Durable AWS box LIVE (Greg S90: "you do it end to end", EC2FullAccess granted).** After Lightsail had no
  managed full-access policy, used EC2: launched `i-0017dc36072eaa6c8` (t3.large, 30GB, us-east-2,
  3.144.199.236) via a self-configuring boot script (pulls code from `s3://.../deploy/markets_code.tar.gz`,
  writes env, runs the recovery service). Running `pull_year --reuse-done-jobs` = re-decode paid Jul/Aug/Jan
  free + submit the rest, all with the flush fix. Secrets are in the box's boot config/env -> ROTATE the
  Databento + AWS keys after the pull completes (Q5). Box can be stopped after the year lands, or repurposed
  for the daily lifecycle. EC2 launcher steps (AMI/SG/run_instances) were ad-hoc via boto3 from the session.
- **Daily cadence = a DURABLE TRIGGER, not memory (Greg S90: "how do we remember to do this daily?").**
  The weather-distribution trade is same-day (score tomorrow's KXHIGH ladder ~5PM, recalc AM, re-check
  intraday) - the same daily lifecycle as the NYMEX path forecast (the FORECAST WORKFLOW TODO in
  KALSHI_TRADING.md). Mechanism = a GitHub Actions daily cron (matches the durable collectors; Greg
  dispatches) OR a Claude Routine (create_trigger daily cron -> session). Wire it once the forecaster emit
  + the per-cell scoring script exist; recorded now, scheduled later (a trigger into an empty pipeline is
  premature). Noted in the KALSHI_TRADING.md FORECAST WORKFLOW block.

## OPEN QUESTIONS (superseded by RESOLUTIONS above; kept for the audit trail)
1. **JOB 2 pre-processing:** what SPECIFICALLY is the "pre-processing on the ingest side" to move to the
   trade side? The scaffolding already reads raw rows + derives at scoring time - is JOB 2 mainly (a) swap
   the data SOURCE to S3, or (b) is there a concrete derivation/reduction to relocate? Need one concrete
   example to aim right.
2. **Interface for the weather session (so they emit the right thing):** the KXHIGH market needs a per-
   `(city x regime x lead)` RESIDUAL DISTRIBUTION (value + sigma + tail), NOT MAE - MAE cannot price a 2F
   bucket. And the rerun should be on the ACTUAL KXHIGH cities (NY/CHI/LAX/DEN/AUS/ATL/BOS/DAL/HOU/PHX/
   SATX/SFO), not KGJT/KDDC (those are the science contrast, not markets). Confirm the edge holds at the
   near-term leads the contracts actually settle on. Should we write this interface spec down for them?
3. **Trade-side sizing/EV harness** (`weather_trade_book.py`-style: OD (value,sigma) + live ladder + book
   depth -> per-line edge/fee/Kelly-size + book EV/variance) - DEFERRED per Greg ("we don't know if it's
   tall"); do not build until the edge depth is known from the rerun.
4. **S3 reader stream-vs-cache:** OK to cache each downloaded day's gz locally (gitignored, ~400MB/yr) so
   repeat scoring passes don't re-pull from S3? (Default assumption: yes.)
5. **IAM key hygiene:** rotate/deactivate the `Claude` IAM key once the year pull is done (S89 standing item).

## RULES (unchanged): historical data RAW / keep-all-info / zero gates on the data side; gates ONLY on trade
signals; leakage gate before any scoring; exclude settle window (trade side); net-of-fee maker AND taker;
zero synthetic; provisional-until-live; NYMEX=canary/fire on Kalshi; weather forecaster = Greg's spec HANDS
OFF; DATABENTO_API_KEY + AWS keys are session-pasted SECRETS (never commit).
