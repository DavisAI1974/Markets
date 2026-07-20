# DASHBOARD HANDOFF (S100.1) - read this before wiring any UI into the platform

## S100.1 ADDENDUM (dashboard wiring session, 2026-07-20) - what is BUILT and how the snapshots were made

State: the READ PLANE EXISTS. Branch `claude/dashboard-wiring-rgvahe` (cut from the signal-core
tip), everything under `dashboard/` (see its README.md): FastAPI server + read-only adapters
(brain / decision_state with blockwise awaiting-data fallback / lag map / fees / kalshi candles
both schema vintages / nymex minute bars / data-plane health) + the v0.1 prototype frontend wired
via `adapter.js` with per-panel truth badges (REAL DATA / AWAITING DATA / SIMULATED). Verified
end-to-end 2026-07-20: 21/22 decision blocks fed on walk-window days (holiday=None is correct
absence), lag map 76,594 rows / ATM 42% serving the edge clock per cell, real NYMEX tape charted
for 20260122. Executor lane deliberately NOT built (Greg: last). Store->local path conventions
that cost time: cot_combined/ -> data/cot_combined, steo_vintage/ -> data/steo_vintage,
nuclear_outages/ -> data/nuclear_outages, weather/mos_asof/ -> REPO/weather/mos_asof (tracked in
git - the S3 refresh is skip-worktree'd locally, NEVER commit it), options_ng: pull ONLY
surface.json.gz (the raw/ dbn archives are 859MB and feed-I-phase-ii only).

SNAPSHOT ARTIFACTS (v0.1.1, published 2026-07-20, private to Greg, for cruising + notes):
- Desktop (also auto-fits a phone turned sideways):
  https://claude.ai/code/artifact/89eadfbc-ab1c-4241-a113-8a0c1a426bb7
- Portrait phone (bottom-tab nav, single column):
  https://claude.ai/code/artifact/1c257290-ee89-451b-a03a-95a5542718b6
HOW: `dashboard/make_snapshot.py` (run the server, stores pulled, then one command) captures
/desk/snapshot for a set of as-of days + the ATM lag window + kalshi day list + minute bars for
tape days (~0.6MB total), and assembles ONE self-contained HTML per form factor: inlined CSS +
frontend body + a shim that overrides window.fetch for /api/v1 paths to serve the embedded JSON.
TRAPS (each cost an iteration, all encoded in the script): base css sets body min-width
1180/1120 - the phone build zeroes it with !important; do NOT use CSS zoom to fit (mobile
layout-viewport expansion fights it); the desktop build fits rotated phones via
`<meta name="viewport" content="width=1130">` (classic desktop-site scaling, no JS). Embedded
days 2025-12-23 / 01-07 / 01-20 / 01-22 (default, tape) / 01-30 / 07-17; Feb 2026 EXCLUDED
(blind-run hygiene, G12/G13 un-walked - the script has a guard; lift it only after the walk).
REFRESH: rebuild the files, then republish - the SAME conversation republishing the same file
path keeps the URL; a NEW session must pass the artifact URL to the Artifact tool or it mints a
new link. Greg's future asks recorded: a properly scaled-down responsive version later;
historical options data on the dash (parked, Greg thinking on scope).

---
Original S100 handoff below, unchanged.

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
