# KALSHI TRADING — file index

The map of every Kalshi file: what it is, where it lives, and whether it's part of the CURRENT
pipeline or an OLD/completed piece. Keep this current — add new files to the top section, move
superseded ones down. (Started S81, 2026-07-12.)

Data stores are LOCAL/gitignored (too big for git): `data/kalshi_hist_trades/` (historical trades),
`data/pyth_ticks/` (Pyth + Databento NYMEX trades ticks), `data/nymex_mbp10/` (S86: MBP-10 trade+book
depth tape), `data/kalshi/` (live bins + consensus). Durable data accrues gzipped on branches:
`data/kalshi-bins`, `data/pyth-ticks`, and **`data/nymex-ticks`** (S85 trades tape under `nymex_tape/`;
S86 MBP-10 depth tape under `nymex_mbp10/` + depth baselines). `kalshi-session-start` restores all.

---

## CURRENT KALSHI FILES

### Collectors & data feeds
| file | what it does |
|------|--------------|
| `research/kalshi/kalshi_collector.py` | Live public-API order-book snapshot collector (28-series watchlist: weather/macro/energy/electricity). Unified YES book. → `data/kalshi/*_bins.jsonl`. |
| `research/kalshi/kalshi_history.py` | Historical settled-market trade puller — per-ticker fills WITH signed `taker_side` (real signed flow) + candles. → `data/kalshi_hist_trades/` (local). |
| `research/kalshi/pyth_collector.py` | **[S81]** Pyth Hermes sub-second tick collector for the NYMEX/ICE futures Kalshi settles on. SSE stream, dedup on advancing publish-time. → `data/pyth_ticks/`. NOTE (S84): the `NGDQ6` feed id is BOGUS (Pyth has no natgas) — fix pending; WTI works, Brent live-only. |
| `research/kalshi/databento_backfill.py` | **[S84/S85/S86]** TRUE-TICK historical NYMEX backfill from Databento (`GLBX.MDP3`): CL crude AND NG natgas at the `trades` schema (every print, nanosecond) — fixes Pyth's NG gap + 1-sec undersampling. Modes: cost / window (sync) / batch (large/cheap) / **defs** (S85: `definition` schema → `{ROOT}_definitions.jsonl` point-in-time tick size/value). **S86: `--schema mbp-10`** → `_write_mbp10_df` keeps trade events + their concurrent 10-level book (top-of-book + per-side depth totals) → `data/nymex_mbp10/`. `metadata.get_cost` gate. Needs `DATABENTO_API_KEY` secret. PRIMARY historical source. |
| `research/kalshi/pyth_backfill.py` | **[S84]** HISTORICAL per-second NYMEX backfill from Pyth's timestamp endpoint — windows around past releases, throttled (429/5xx backoff), dedup, → `data/pyth_ticks/` (tagged `src=pyth_hist_1s`). WTI only (Pyth has no NG; Brent-historical 404s). 1-sec UNDERSAMPLES — a lower bound, never the full tape. |
| `research/kalshi/consensus_poll.py` | Polls the free ForexFactory weekly JSON for release forecasts (Crude/NatGas/CPI/NFP/FOMC). → `data/kalshi/consensus.jsonl`. |
| `research/kalshi/eia_surprise.py` | **[S86]** Historical release SURPRISE (seasonal PROXY: actual weekly change − 5-yr same-ISO-week avg) from EIA API v2 (DEMO_KEY): NG working gas + crude ex-SPR. → `data/eia_surprise.json`, consumed by `event_move_baseline.py --surprise-file` to split cells beat/miss×big/small. `--selftest` PASS. Forward real consensus (consensus.jsonl) preferred when present. |
| `.github/workflows/kalshi_collectors_durable.yml` | 6h durable cron: restore→collect bins + poll consensus→gzip+push to `data/kalshi-bins`. |
| `.github/workflows/pyth_collector_durable.yml` | **[S81]** 6h durable cron: restore→stream Pyth ticks→gzip+push to `data/pyth-ticks`. |

### Event-move baseline (S85) — the canary-move expectation-setter [RAN ON REAL TICKS]
| file | what it does |
|------|--------------|
| `research/kalshi/event_move_baseline.py` | **[S85]** Per-EVENT move MAGNITUDE + DURATION on the true-tick futures tape (the NYMEX canary), per surprise-cell. Anchors a strictly-pre-release baseline, measures the forward peak in TICKS/$/bps (tick size POINT-IN-TIME from the `definition` store, source aggregated per-event) + duration (time_to_peak, sustain_s, retention → run/blip/fade) + the **FAST (60s) window** (`--fast`): the sub-minute lag-scalp ceiling (fast_bps/$/capture, peaked_fast). Distributions not means, per-cell, leakage-gated. Expectation-setting, sizes the hold time. `--selftest` PASS. RAN on 12 NG + 12 CL real release windows (S85). |
| `research/kalshi/EVENT_MOVE_FINDINGS_S85.md` | **[S85]** First real result: per-contract HOLD-TIME map. NG front-loaded (60s captures 66% of the move, ~$310/contract); CL slower (60s=27%, a longer hold gets the rest — e.g. $2,640 built over 17min). Both KEPT, different hold windows; EV-net-of-fee is the gate not frequency. Futures move = the CEILING, not Kalshi P&L (lag join next). Cost map + MBP-10 schema decision. |
| `research/kalshi/event_move_baseline.py --depth` | **[S86]** MBP-10 depth read: per-event resting-book imbalance at R (pre-event, leakage-gated) + at the initial push (`aligned_imb_push`, `exhaustion`, `far_thinning`), contrasted against run length. `load_tape_depth`/`depth_features`/`_depth_summary`. `--selftest` PASS (depth math + leakage). Consumes `data/nymex_mbp10/`. |
| `research/kalshi/DEPTH_RUNLENGTH_FINDINGS_S86.md` | **[S86]** The book run-length read on the canary (24 windows, leakage PASS 12/12). PER-CELL split: **NG = exhaustion** (one-sided book at the push → SHORTER run, Spearman −0.17/−0.40) vs **CL = continuation** (one-sided supportive book → LONGER run, +0.52). Corroborates the S85 magnitude split from resting-book dynamics. Provisional n=12; full-year pull confirms. `aligned_imb_push` = the hold-time signal for the lag join. |
| `research/kalshi/EVENT_SURPRISE_FINDINGS_S86.md` | **[S86]** Surprise-cell split (seasonal-proxy, 12/12 matched). **NG: surprise IS the catalyst** — big bearish beat = fast all-down burst (peaks 9s, 60s=100%, all 3/3 down). **CL: surprise does NOT drive the big moves** — the $2,640 day was a −3.1 small surprise; the biggest surprises made the smallest moves → CL big fires are exogenous to storage (macro/geopolitical). KEEP per-cell: gate NG off the surprise, not CL. |
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
| `research/kalshi/EVENT_WEIGHT_STUDY.md` (+ `event_weight_study.json`, `source_map.json`) | Per-bucket event-weight study (weather→storage strong; storage-surprise→price null). |
| `SESSION_HANDOFF_2026-07-12_S85.md` (+ S84, S83, S82, S81, S80, S79, S78) | Session handoffs (S85 latest: Databento LIVE, event_move_baseline first real result = per-contract hold-time map, MBP-10 schema decision, data persisted on `data/nymex-ticks`). |
| `KICKOFF_2026-07-12_S86.md` (+ S84, S83, S82, S81, S80, S79) | Session kickoffs (S86 next: MBP-10 depth + full-year pull, surprise join, lag join). |

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
