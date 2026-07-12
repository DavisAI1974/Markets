# SESSION HANDOFF — S79 (2026-07-12) — Kalshi: pipeline validated turnkey, consensus accrual live, event-weight study, and the MERGED signal architecture

Branch **`claude/kalshi-s79-kickoff-ij8t9o`** (fast-forwarded from the S78 tip `claude/kalshi-s78-kickoff-jb5oyx`
— the s79 branch was cut from a stale S70 crypto tip and was missing all Kalshi work; s78 was a clean superset,
0 divergence, so ff was clean). PUSHED. All S78 code present. Standing rules unchanged: per-contract deploy;
provisional-until-live; annualized-return not $/hr; never size off one window; zero synthetic; git is source of truth.

## What this session did

### 1. Reconciled the branch + validated the whole pipeline TURNKEY (all 4 stages, on live data)
- Live Kalshi API reachable through the proxy (real two-sided books). News ingest → 6 real events, correctly
  tagged (EIA→KXWTI/KXBRENTD, Fed→KXFEDHIKE, NHC→KXTROPSTORM).
- **Coupling engine (`news_coupling_research.py --source kalshi`) runs clean** on live depth: a synthetic BULLISH
  event on a fast KXWTI/KXBRENTD bridge collection produced 48 event obs vs 960 placebo, with the event-vs-placebo
  signed-bps AND hit-rate gate both computing. Numbers are noise (synthetic event, 8-min window); the point is the
  machinery is turnkey. **GOTCHA for next session: `--events` is joined onto `--data-dir` (line 431), so pass the
  BASENAME, not a full path.**
- **Score harness (`kalshi_score.py`) validated** on real settled NYC data: realized values exact (JUL03=98,
  JUL10=85), Gaussian-over-buckets + partition-ladder + Brier/edge all correct. Confirmed the load-bearing caveat
  LIVE: the market baseline is post-hoc-certain (0.95 on every event) until bins accrue → the weather-OD edge test
  is only meaningful against LEAD-TIME bins spanning a future settlement.
- Bridge collections were ephemeral (`data/kalshi_fast/`, `kalshi_coupling_dryrun/` — both gitignored). The broad
  28-series sweep is too slow for in-session depth (~90s/cycle); a focused 2-3 series fast collection (interval 5,
  max-markets 8) builds depth fast.

### 2. Kicked off thread (a): forward CONSENSUS accrual — the surprise axis
- **`research/kalshi/consensus_poll.py`** (new, committed): stdlib-only poll of the FREE ForexFactory weekly
  calendar JSON `https://nfs.faireconomy.media/ff_calendar_thisweek.json` (browser UA, no auth). Verified live:
  carries `forecast`/`previous` for USD Crude Oil Inventories, Natural Gas Storage, CPI, NFP, FOMC. Maps each
  release title → Kalshi series. Idempotent keyed store → `data/kalshi/consensus.jsonl`. Ran once (captured this
  week's forecasts: Crude fc=−1.9M, NatGas fc=+60B, CPI, etc.).
- **HONEST caveat:** the feed has forecast+previous but **NOT `actual`** (and only the CURRENT week — month/last/next
  404). So `surprise = actual − forecast` requires: poll forward for the forecast (scarce, unrecoverable later) +
  join `actual` from the primary (EIA API / BLS) at release time. Energy actuals are already deep+free via EIA API.
- **Wired into `kalshi_collectors_durable.yml`:** polls consensus each cycle, restores + gzip-persists
  `consensus.jsonl` on the `data/kalshi-bins` branch alongside the order-book bins. Retargeted CODE_REF / checkout /
  push-trigger to the s79 branch. A push-triggered durable run (#4, id 29177730054) is live and will create
  `data/kalshi-bins` with bins + consensus.

### 3. Historical event-weight study + source map (background agent; committed)
Deliverables: `research/kalshi/EVENT_WEIGHT_STUDY.md`, `event_weight_study.json`, `source_map.json`, `hist/` scripts.
Raw CPC/EIA downloads local (`data/kalshi_hist/`, gitignored). Per-bucket (never pooled |move|), placebo baselines.
- **4-regime natgas split, DATA-DISCOVERED from degree-days** (not calendar): winter-withdrawal (HDD hump, N=186),
  summer-withdrawal (CDD power-burn hump, N=152), spring-injection (105), fall-injection (78). Double-hump demand
  CONFIRMED. Honest caveat: summer is a build-MINIMUM on the national aggregate (+52 median), not a net draw.
- **Weather→storage LINK STRONG:** winter R²=0.85, 91% surprise-sign accuracy (pooled R²=0.73). **The OD-weather
  forecaster IS a storage-print forecaster** → a real, non-arbed edge on any contract that settles ON the storage
  NUMBER (distinct from the price reaction).
- **Storage-surprise→PRICE ≈ NULL** (release-hour hit 0.52; large sell-the-news bucket; winter is the biggest MOVER
  but the seasonal proxy is directionally BLINDEST there). Reason: the number is so weather-predictable that it's
  priced by release; the 5yr-seasonal proxy is a poor consensus stand-in (esp. winter). The genuine tradeable
  surprise is the RESIDUAL vs street consensus — which is exactly what the consensus poller isolates going forward.
- **Intraday spike real for natgas** (release-hour |move| = 1.57× same-hour placebo on NG=F), weak for crude
  (1.12× on CL=F) → daily bars wash it out; measure/trade intraday. (Intraday sample small: ~122 releases, Yahoo
  intraday ~2yr.)

## THE STANDING DESIGN RULES established this session (load-bearing — carry forward)

1. **Score events PER BUCKET, never a pooled |move|** (the crypto never-pool / bucket-distinctiveness rule applied
   to events). Buckets = signed SURPRISE × signed REACTION: {expected-up&up (confirm), expected-up&down
   (sell-the-news), expected-down&down, expected-down&up (reversal), in-line}. Let the buckets self-distinguish;
   don't force a fixed grid. Pooling flattens the directional signal (proven: pooled surprise→price is a coin flip).

2. **⭐ THE MERGED SIGNAL ARCHITECTURE (Greg, S79, load-bearing) — this is the whole game:**
   > **News release = the CATALYST/trigger** (an event is coming; coarse size hint "a lot vs a little different" —
   > a range/ratio at most, DO NOT build a precise surprise→move regression, it overfits and is null anyway; also
   > the PAUSE-through-the-first-seconds gate). **Book imbalance + dipole exhaustion on the contract's probability
   > series = the actual DIRECTION + MAGNITUDE-class read.** Book imbalance SIGN → direction (incl. sell-the-news,
   > which the book shows and the number can't); book imbalance MAGNITUDE + exhaustion state → little-or-a-lot +
   > will-it-hold-or-fade. This is the crypto FILTER+TIMING stack (`early_signal.book_imbalance` +
   > `odcore/info_dipole.divergence()` exhaustion), now FIRED BY a scheduled release instead of hunting turns blind.
   This RESOLVES the surprise→price null: direction/size were never in the surprise; they're in the book. The
   sell-the-news bucket is not noise — it's exactly what exhaustion catches (bullish print into a spent book → fade).
   BUILD CONSEQUENCE: do NOT build a surprise regression. Surprise = coarse regime flag + calendar gate; the signal
   work is book-imbalance + exhaustion on the accruing Kalshi order-book series AROUND releases. Makes the
   microstructure thread (#3) central. Phase-2 test: does book imbalance at release call direction, and exhaustion
   call the fade?

3. **Release-day playbook (Greg, S79):** scheduled releases have a quiet→spike→decay shape — vol compresses for
   hours before, explodes ~1h at release, decays; normal days flat. So (a) measure INTRADAY not daily (daily
   averages the quiet+spike and cancels the signal); (b) the pre-release quiet = a "release imminent" detector +
   the `PAUSE_NEW_ENTRIES` trigger (pull resting makers before the gap); (c) stand aside THROUGH the spike (gap
   risk) or only take the side the book dictates; (d) the decay/overshoot is a possible mean-reversion window.
   Generalizes across all families (FOMC pre-announcement vol-crush is the textbook case) → platform-level rule.

4. **Two-phase news-scoring model:** Phase 1 (now, deep history) = the UNDERLYING market's reaction gives the
   event's FUNDAMENTAL impact (a prior, independent of Kalshi mechanics). Phase 2 (once Kalshi bins accrue) = the
   TRANSFER FUNCTION — how much of that underlying move shows up as a PROBABILITY move on a specific contract
   (depends on strike-vs-spot / time-to-settle / liquidity; only learnable from real contract data). Underlying =
   event impact; Kalshi data = the binary-option transfer; tune, don't re-derive.

5. **Weather is the ROOT signal for the whole energy complex (convergence):** weather → heating/cooling demand →
   {storage draw/build → natgas price} AND {electricity load → power price} AND {weather-contract settlement}. One
   station-level degree-day/temperature forecaster feeds THREE contract families. Demand-vs-temperature is
   DOUBLE-HUMPED (cold→heating, hot→power-burn, mild shoulders low). HONEST SCOPE (unchanged): OD-weather's
   defensible first claim is a local operator / bias-correction on the exact station settlement variable, tested to
   beat climatology+persistence+MOS — NOT "out-forecast ECMWF." The study shows why: weather→storage is 0.85 R² so
   the market already prices it; the edge is only the residual skill over the market's own weather input.

## NEXT (priority)
1. **Greg's click — make `claude/kalshi-s79-kickoff-ij8t9o` the repo DEFAULT branch.** The push fired durable run
   #4 once; the 6h cron only fires from the default branch. Setting s79 default turns on continuous accrual of bins
   + consensus (the data both threads need). (Current default is `claude/new-session-o3vnm`, unintended.)
2. **Build the release-triggered BOOK signal (the merged architecture, rule #2)** on the accruing Kalshi order-book
   series: `early_signal.book_imbalance` (direction) + `info_dipole` exhaustion (fade), gated by the release
   calendar. This is the real deliverable now, not a surprise regression.
3. Let `data/kalshi-bins` + `consensus.jsonl` accrue across real EIA/CPI/NFP/FOMC releases → run the coupling test
   (`--source kalshi`, basename events path) with REAL street-consensus surprise (residual vs the seasonal proxy),
   and `kalshi_score.py` with `--lead-minutes` baselines.
4. **AGA pre-2002 weekly natgas storage (1994–2002)** — history extension for the bucketing (AGA resource library /
   EIA archives; NYMEX futures back to 1990). Bonus N; not a blocker (EIA 2002-present ~1,200 weeks already ample).
   Note AGA released Wednesday vs EIA Thursday — era-specific release timing.
5. Plug the OD-weather forecaster into `kalshi_score.py` when ready (it IS a storage-print forecaster → also a
   candidate direct edge on any storage-NUMBER-settled contract).
6. Paper loop on `demo-api.elections.kalshi.com` (RSA-key demo creds — Greg).

## Files this session
New: `research/kalshi/consensus_poll.py`, `research/kalshi/EVENT_WEIGHT_STUDY.md`, `event_weight_study.json`,
`source_map.json`, `research/kalshi/hist/*` (event_study/intraday/macro/eia_bucket/natgas_season/natgas_weather).
Edited: `.github/workflows/kalshi_collectors_durable.yml` (consensus poll + persist + s79 retarget), `.gitignore`.
Local-only (gitignored): `data/kalshi_hist/` (CPC/EIA raw), `data/kalshi_fast/`, `kalshi_coupling_dryrun/`.
Commits `a489c15`, `5003509` on `claude/kalshi-s79-kickoff-ij8t9o` (PUSHED).
