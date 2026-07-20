# DASHBOARD HANDOFF (S100) - read this before wiring any UI into the platform

For the dashboard-building session. The signal platform this UI sits on is live and disciplined;
this page is the map of what to read, where it lives, and the four rules that protect it.

## THE FOUR RULES (non-negotiable, same as everywhere in this repo)

1. git = CODE, S3 = ALL DATA. The dashboard reads data from S3 (or the local `data/` cache
   restored by `python research/kalshi/platform_sync.py pull --prefix <name>/`). NEVER commit
   data or credentials - this repo is/was PUBLIC.
   AWS ACCESS: USE THE KEY WHOSE SECRET BEGINS `tx` (ID `AKIAYI6JDCBVLKYQGLMH`, account
   ...4170, bucket `bento-568968024170-us-east-2-an`). The key is GOOD - if STS returns
   InvalidClientTokenId, the cloud container's placeholder env vars are overriding
   `~/.aws/credentials`: run AWS-touching commands via `bash -lc` or pass credentials
   explicitly. Full pair: ask Greg or see `~/.aws/credentials` in an existing session. See
   CLAUDE.md "AWS KEY" section.
2. ADDITIVE ONLY. Build the dashboard in its own directory (suggest `dashboard/`). Do not edit
   `research/kalshi/forecast_harness.py`, any `*_feed.py`, or `research/kalshi/knowledge/
   ng_brain.json` - those belong to the signal core and change through its own protocol.
3. PER-EVENT, never pooled averages presented as conclusions. Distributions and per-event rows;
   a mean is never the headline.
4. Confidences/probabilities shown in the UI must carry their provenance labels (blind vs
   refined, forward_evidence, provisional-until-live). No invented certainty.

## WHAT TO READ (the data plane, all on S3 bucket `bento-568968024170-us-east-2-an`)

- `python research/kalshi/platform_sync.py list` = the authoritative inventory (20+ prefixes,
  per-prefix manifests).
- DECISION STATE (the 23-block daily state the coach reads):
  `research/kalshi/forecast_harness.py::decision_state(["YYYYMMDD"])` - one call returns
  everything: storage/COT+ICE/structure/squeeze/vol/cash/flow-calendar/solar/nuclear/grid/
  options/weather (realized + MOS + cycle-level + freeze-off basins) + information clock.
- THE BRAIN (plays, doctrine, method): `research/kalshi/knowledge/ng_brain.json` (s101.2) -
  the signals inventory the UI should mirror is summarized in the S100 chat log's
  "NG Trade Signals Inventory"; the brain file is the source of truth.
- LIVE TELEMETRY: `research/kalshi/LIVE_TELEMETRY_S100.md` (first datum: GLBX NG trades,
  median 7.7ms). Live feed = Databento Python client (`databento.Live`), Standard plan,
  GLBX.MDP3 - the raw-TCP live gateway is NOT reachable from Claude cloud containers; live
  processes run on AWS boxes (see the doc).
- LAG EXECUTION MAP (feed M, in progress S100): `data/kalshi_echo/lag_map.jsonl` / S3
  `kalshi_echo/` - per (NYMEX-move-event x Kalshi bracket) rows: delay_s, pass-through,
  moneyness band, move class, time-of-day.
- KALSHI RAW: S3 `kalshi/` - trades (ms stamps) / 1m candles (two schema vintages: `close` vs
  `close_dollars` - handle both) / market definitions, per event-day.
- NYMEX TAPE: S3 `nymex/nymex_cont/` via
  `event_move_baseline.load_cont_day("NG","YYYYMMDD",source="s3")` -> dict of numpy arrays.

## COORDINATION WITH THE BUILD SESSION

- The signal-core branch is `claude/ng-coach-agent-loop-5ha5bf`. If the dashboard session works
  in the same repo, use its own branch and rebase before any push; never push to the signal-core
  branch without coordination.
- Two sessions writing the same S3 prefixes = collision risk. The dashboard READS S3; it should
  write only under a `dashboard/` prefix if it needs storage at all.
- Questions about what a field means: every feed module has a docstring + `--selftest`, and
  every decision_state block carries a `note` field explaining itself.
