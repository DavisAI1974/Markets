# SESSION HANDOFF — S92 (work date 2026-07-14) — NG intraday FORECASTER program: direction cracked + the coach "brain"; year-box Monday-corruption fixed

Branch: came up on the stale S70 tip, reset onto trunk `claude/kalshi-s79-kickoff-ij8t9o` (all work pushed there).

## HEADLINE
1. **The NG intraday FORECASTER program is the session's main arc — and NG DIRECTION is cracked.** Built the
   full-toolbox per-leg characterizer, ran learn/blind/hunt passes on 12 warm-season days (per-event, NO
   pooling), and found **`dip_imb_level` (pre-entry order-flow imbalance) CALLS leg direction** — LOW tercile
   7% up / HIGH 93% up, monotone in flow strength, **OOS-validated 100% on strong-flow (34/34) across 3 unseen
   days.** Direction was "the single biggest unsolved." It's a NOWCAST (flow as the leg is born) — ideal for
   the Kalshi lag (know NG's way before Kalshi reprices).
2. **The coach "brain" is built (Greg's big-picture vision).** `research/kalshi/knowledge/ng_brain.json` = the
   machine playbook (versioned plays + mechanisms + frontier) agents load and apply. The loop: load brain ->
   forecast a group of days BLIND -> score vs actual -> merge learnings back -> refine -> converge -> the agent
   becomes the COACH calling plays live (enter/ride/exit), replacing rigid coded gates. **RUN THE LOOP = S93.**
3. **Year-box data-integrity: every Monday was corrupt — root-caused + fixed + re-downloaded.**

## THE FORECASTER PROGRAM (the main work)
- **`month_characterize.py` now exposes the FULL toolbox per leg** (all committed): entry book (`aligned_imb`,
  `pre_vol`), **exhaustion suite** (`aligned_imb_push`, `exhaustion`, `far_thinning`, `spread_ratio`, `imb_R`),
  **dipole** (`dip_imb_level`, `dip_aligned_flow`, `dip_mi_flow`), **turning-point fingerprint** measured
  entry->peak (`turn_exhaustion`, `turn_far_thinning`, `turn_spread_ratio`, `turn_aligned_push`),
  **storage-surprise** (`stor_surprise`, via `eia_surprise.json`), **curve** (now live via `forward_curve`
  cache), weather, + shape OUTCOMES (`peak_usd`, `sustain_s`, `retention`, `fast_capture`, `continuation`, `dir`).
  Reuses `event_move_baseline.depth_features` + `odcore.info_dipole.signed_flow_features` (no recreated math).
- **Findings (12 warm-season NG days, per-event, exemplar-cited, NEVER pooled-as-final):**
  - **[STABLE] Magnitude law / staircase:** a leg that gets big HOLDS — $350->0.92 (n38), $500->1.00 (n11).
    The real-time $350 CROSSING is a 92% "ride it" event. (The pooled 94% survived averaging = real.)
  - **[STABLE] Grind-vs-spike:** slow grind holds, front-loaded spike round-trips (1/111 held legs spiked fast).
  - **[PROVISIONAL] DIRECTION = `dip_imb_level` flow nowcast** (above; OOS 100% strong-flow). `imb_R` = a weaker
    CONTRARIAN tilt (fade the resting wall); flow beats book 89% on disagreement.
  - **[PROVISIONAL/MECHANISM] Turning point = far-side liquidity RECRUITMENT, not consumption.** Held big legs
    GROW the far ladder by the top (`turn_far_thinning` med -0.156); reversed tops eat/stall it. Reframed n=3
    -> n=101. Second orthogonal marker: `turn_aligned_push` (support at the top). Reversal = both fire.
  - **Ruled NOISE across all 4 targets (warm-season only):** aligned_imb, exhaustion, spread_ratio, pre_vol,
    dip_aligned_flow, dip_mi_flow, depth, weather, curve(contango-flat). Storage-surprise->day-type WEAKENED
    (didn't reproduce on continuation-rate; a weak day-level trend prior only).
- **The blind-build loop ran once (group 1, 12 unseen days):** agent forecast each day's curve from
  decision-time state only, overlaid vs actual (`renders/ng_learn_s92/ng_blind_overlay_12days.png`). Magnitude/
  day-type reasonable; DIRECTION weak at the OPEN (it's an intraday nowcast, not a from-flat forecast) — 08-12
  the lesson (called up, fell -19c). This is WHY direction lives intraday, not in the day-open forecast.
- **Docs (all on trunk):** `NG_BEHAVIOR_KNOWLEDGE.md` (living, status-tagged, grows each pass) ·
  `knowledge/ng_brain.json` + `knowledge/README.md` (the machine brain + the loop + the memorization guard) ·
  `NG_FORECAST_LOG_S92.md` (the forecaster's reasoning + magnitude-scaling + the data-gap plan) ·
  `renders/ng_learn_s92/` (12 learn-day curves grid + 12 individual PNGs + the blind overlay + forecasts JSON).
- **THE GUARD (non-negotiable, in the brain meta):** general rules + mechanism + n, NEVER memorized days; skill
  judged on days never touched in any pass (TRUE HOLDOUT) + forward-live; provisional-until-live (size-vs-fee +
  Kalshi-demo paper). A hand-coded threshold IS a pooled decision (rigid); the coach reads each instant's
  fingerprint (per-event) — that's the whole point.

## MACHINERY BUILT — the loop is READY-TO-RUN for S93 (built after Greg's "build everything" call)
- **`research/kalshi/FORECASTER_RUNBOOK_S93.md`** — the VERBOSE operating manual (read this to run S93): the
  vision, the plays, the machinery, the exact loop commands, JOB 2 (net-of-fee), the guard, the NYMEX-OPTIONS
  survey, hygiene, frontier.
- **`research/kalshi/coach_replay.py`** — the ng_brain playbook as EXECUTABLE strategy code (the rigid baseline
  the adaptive coach must beat): applies direction-nowcast -> $350-ride -> recruitment-exit per leg, net-of-fee,
  per-event, NO pooling. `--selftest` PASS; dry-run NG 07-15 = 14/14 correct direction. Canary-side + INDICATIVE
  capture proxy for now -> real fill model + Kalshi/NYMEX-option venue is S93.
- **`research/kalshi/forecast_harness.py`** — turn-key loop helpers: `decision-state` (blind-safe group state),
  `overlay` (guess-vs-actual render), `brain-show`. `--selftest` PASS.
- **`research/kalshi/redownload_mondays.py`** — committed home of the Monday re-download tool (final sweep).
- **NYMEX OPTIONS (Greg S92: "look at nymex options for actual trading very soon")** — folded in as the real
  trading vehicle (RUNBOOK sec 6). Our edge is KNOWING NG's move; NG options trade it directly (bigger/more
  liquid than the Kalshi echo) and the plays already speak option language (direction=which way, $350/$500
  staircase=strike/expiry, US-session=intraday/0DTE, exhaustion=take-profit/flip). S93 first step = an options
  survey (products/liquidity/fees/Databento coverage + map each play to a structure), then price our best
  historical calls as option trades. Needs an FCM/broker to route (go-live cost); paper/analog-validate first.

## THE YEAR DATA (JOB 1) — box running; Monday corruption FIXED
- **Box `i-08cee7171c0a76a04`** (t3.xlarge, 200GB) running `pull_year_mbp10 --weekly` to
  `s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/`. At handoff: span **2025-06-30..2025-10-20** (~3.5 of
  12 months), alive, disk 186G, heartbeat fresh. ~8 more months to 2026-07; Databento-queue-paced.
- **CRITICAL FIX — every Monday was a 455-byte corrupt stub.** Root cause: week spans run Tue->Tue, so **Monday
  is the last day of every weekly batch**, and `databento_backfill._flush` used `'wb'` (overwrite) — a later
  out-of-order straggler re-created a 1-row Monday jsonl and the final `'wb'` flush CLOBBERED the full gz.
  **Fixed: `_flush` now APPENDS (`'ab'`)** (concatenated gzip members decompress as one; the reader sorts by ts).
  Committed.
- **DOW naming + calendar-aware markers (committed):** files now `{ROOT}_{YYYYMMDD}_{dow}.jsonl.gz`;
  `_expected_full`/`_s3_month_present`/the weekly marker treat weekends + CME full-closure holidays as legit-tiny
  (not corruption), so weeks/months get marked. `--reconcile-names` renames the box's date-only output + writes
  week markers (RUN after the box hits DONE). `--selftest` PASS. Reader `event_move_baseline._s3_fetch_cont_gz`
  reads dow-name with legacy fallback.
- **Monday re-download (`scratchpad/redownload_mondays.py`, running):** re-pulls each corrupt Monday as a 2-day
  `[Mon,Wed)` batch (Monday interior) + uploads clean over the stub. **NG Mondays: 14 clean.** CL: in progress.
  **CAVEAT: the box (old code) keeps minting NEW corrupt Mondays as it advances** -> a FINAL Monday sweep is
  needed after the box finishes (re-run redownload_mondays.py; it finds all sub-5KB Mondays dynamically).
- v1 dead box `i-0e56896a51243edb2` terminated.

## INFRA (JOB 2 / B) — workflows rerouted to S3; need Greg's secrets
- **`nymex_mbp10_ingest_durable.yml` rewritten** git->S3 + `--weekly` (was failing 7/7: missing DATABENTO
  secret + targeted the retired git branch). Rolls forward via a dynamic end month.
- **`nws_hourly_collector_durable.yml` NEW** — RT hourly NWS collector (historical is already complete on S3:
  25 months, raw hour-by-hour WITH precip). Re-ingests the trailing 2 months with `--overwrite` (new
  `nws_temp_feed --overwrite` flag) every 6h.
- **BOTH need Greg to add repo secrets** (Settings > Secrets and variables > Actions): `DATABENTO_API_KEY`,
  `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Claude's tools can't create secrets. **SEQUENCING:** keep the
  NYMEX workflow DISABLED until the box finishes + `--reconcile-names` writes markers (else double-pull/pay).
- `eia_surprise.json` generated (DEMO_KEY; NG+CL storage surprise back to 2013); `forward_curve` cache built
  for the learn window.

## KEY DATA FINDINGS / GAPS
- **HH Pyth close is NOT available historically** — Pyth serves ZERO natural-gas history (benchmarks has only
  UKOIL/USOIL/WTI; live NGDQ6 404s historically). Greg's call: use the **Databento NG settle** for historical
  HH; Pyth NGDQ6 accumulates forward for oracle-match.
- **NEWS: no history** (RSS forward-only) — a known gap; forward collection only. Deferred (residual-explainer:
  revisit only on a big build-vs-actual miss).
- **DIRECTION data plan** (`NG_FORECAST_LOG_S92.md`): forward news, real desk consensus (vs seasonal-proxy),
  day-ahead/spot pipeline noms (Greg's idea; Platts/NGI — new source), overnight-lean (free, we have the ticks),
  and the WINTER/backwardation tape (the decisive out-of-regime test — all 12 days were contango).

## SECRETS (session-pasted, never git): `AWS_ACCESS_KEY_ID` (AKIAYI6J...), `AWS_SECRET_ACCESS_KEY` (txRGHd...),
`DATABENTO_API_KEY` (db-3ba8...), `AWS_DEFAULT_REGION=us-east-2`. **ROTATE early (standing item).** They sit in
the box boot config + the Monday re-download runner.

## IN-FLIGHT at handoff (background)
- **Year box** pulling (~Oct 2025; ~8 months to go).
- **Monday re-download** (CL still processing).

## OPEN / S93 PRIORITIES
0. **READ `research/kalshi/FORECASTER_RUNBOOK_S93.md`** — the machinery is BUILT + tested; it has the exact
   commands for everything below.
1. **RUN THE LOOP (Greg's #1).** brain (`knowledge/ng_brain.json`) -> forecast a NEW group BLIND -> overlay
   guess-vs-actual -> distill + MERGE back into the brain (version bump) -> next group -> year -> loop back +
   refine the worst. **Group-2 decision state is staged: `scratchpad/ng_group2_decision_state.json`** (12 fresh
   days, none seen). Keep the memorization guard (true holdout + forward-live).
2. **The intraday COACH replay** — apply the playbook LEG-BY-LEG on new days net-of-fee (direction nowcast ->
   $350 ride -> recruitment exit) = the real tradeable-edge test (vs the day-open shape forecast).
3. **Characterize NG Mondays** (now clean) -> the distinct weekend-gap shape -> brain (`[OPEN]` item).
4. **Verify the box year DONE** -> `--reconcile-names` (rename + markers) -> **final Monday sweep** (re-run
   redownload_mondays.py — the box minted new corrupt Mondays past Sep).
5. **Greg adds the 3 GH secrets** -> enable the S3 workflows (NYMEX after box+reconcile; NWS anytime).
6. **ROTATE the keys.**
7. **AWS/Routine autonomous agent** for the loop (needs DURABLE creds first — the GH secrets or box config).
8. **Winter/full-year tape** = the out-of-regime test for direction + everything ruled out warm-season.
9. **NYMEX OPTIONS survey (Greg S92, "very soon")** — the real trading vehicle for our NG-move edge: products/
   liquidity/fees/Databento coverage, map each play to an option structure, price our best historical calls as
   option trades net-of-premium. (RUNBOOK sec 6.) Needs an FCM/broker to go live.

## RULES (unchanged, reinforced this session): EACH EVENT INDIVIDUALLY, NEVER pool/average as the final word
(an extreme rate is a LEAD, individual numbers pinpoint the WHEN); per-cell never pool; distributions/
fingerprints not means; leakage gate + blind wall; net-of-fee maker AND taker; exclude settle window; zero
synthetic; provisional-until-live; git = CODE, S3 = ALL DATA; NG and WTI kept SEPARATE.
