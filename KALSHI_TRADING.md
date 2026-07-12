# KALSHI TRADING — file index

The map of every Kalshi file: what it is, where it lives, and whether it's part of the CURRENT
pipeline or an OLD/completed piece. Keep this current — add new files to the top section, move
superseded ones down. (Started S81, 2026-07-12.)

Data stores are LOCAL/gitignored (too big for git): `data/kalshi_hist_trades/` (historical trades),
`data/pyth_ticks/` (Pyth ticks), `data/kalshi/` (live bins + consensus). Durable data accrues on the
`data/kalshi-bins` and `data/pyth-ticks` branches.

---

## CURRENT KALSHI FILES

### Collectors & data feeds
| file | what it does |
|------|--------------|
| `research/kalshi/kalshi_collector.py` | Live public-API order-book snapshot collector (28-series watchlist: weather/macro/energy/electricity). Unified YES book. → `data/kalshi/*_bins.jsonl`. |
| `research/kalshi/kalshi_history.py` | Historical settled-market trade puller — per-ticker fills WITH signed `taker_side` (real signed flow) + candles. → `data/kalshi_hist_trades/` (local). |
| `research/kalshi/pyth_collector.py` | **[S81]** Pyth Hermes sub-second tick collector for the NYMEX/ICE futures Kalshi settles on (WTIQ6/NGDQ6/BRENTU6). SSE stream, dedup on advancing publish-time. → `data/pyth_ticks/`. |
| `research/kalshi/consensus_poll.py` | Polls the free ForexFactory weekly JSON for release forecasts (Crude/NatGas/CPI/NFP/FOMC). → `data/kalshi/consensus.jsonl`. |
| `.github/workflows/kalshi_collectors_durable.yml` | 6h durable cron: restore→collect bins + poll consensus→gzip+push to `data/kalshi-bins`. |
| `.github/workflows/pyth_collector_durable.yml` | **[S81]** 6h durable cron: restore→stream Pyth ticks→gzip+push to `data/pyth-ticks`. |

### Lag thread (S80–S81) — futures LEAD Kalshi
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

### Shared engines (not Kalshi-only, but the pipeline runs on them)
| file | what it does |
|------|--------------|
| `news_ingest_rss.py` | RSS ingest → contract tagging (EIA/Fed/NHC feeds → `CONTRACT_KEYWORDS` per Kalshi series; ENERGY/INFLATION/JOBS/… categories). |
| `news_coupling_research.py` | Signed-edge-vs-placebo coupling engine (`--source kalshi`). NOTE: `--events` is a BASENAME joined onto `--data-dir`. |
| `regime_classifier.py` | Regime classifier (shared). |
| `odcore/leadlag.py` · `odcore/info_dipole.py` · `odcore/leakage.py` | The operator tools the lag/signal work is built on (lead-lag, flow-dipole divergence/exhaustion, the mandatory leakage gate). |

### Current docs
| file | what it is |
|------|-----------|
| `KALSHI_TRADING.md` | This index. |
| `KALSHI_BUILD_SCOPE.md` | The Kalshi build scope / thesis. |
| `research/kalshi/EVENT_WEIGHT_STUDY.md` (+ `event_weight_study.json`, `source_map.json`) | Per-bucket event-weight study (weather→storage strong; storage-surprise→price null). |
| `SESSION_HANDOFF_2026-07-12_S80.md` (+ S79, S78) | Session handoffs (S80 latest committed; S81 pending). |
| `KICKOFF_2026-07-12_S81.md` (+ S80, S79, `KICKOFF_S78/S79_KALSHI.md`) | Session kickoffs. |

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
