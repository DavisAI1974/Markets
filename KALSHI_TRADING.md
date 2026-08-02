# KALSHI TRADING — file index

## NEW IN S109 (2026-08-01, current) — G22 blind, holes #9/#10/#11, the AUDITOR role, brain s103.7

**THE SIXTH AGENT ROLE (audit and forecast are now separate jobs)**
- `research/kalshi/agents/state_auditor.md` — CANONICAL, static, drop into every group unchanged. Reads
  the WHOLE block before the blind spawns and hunts inputs that would mislead a specialist; emits NO
  forecasts. Resolves hole #11's tension: cross-day reading is how eleven holes were found, but a
  forecaster reading across days acquires information past its own decision point. The auditor
  cross-compares freely (nothing to contaminate); the specialists run on causal slices. Carries the five
  known KINDS of silently wrong input, the declared-vs-silent split, the findings schema, and a FIX-PHASE
  contract. Trialled blind on G21: found the off-instrument defect S108 called the hardest of eight,
  WITHOUT the scored-leg reconciliation S108 used.

**CAUSALITY (hole #11 — the state let every specialist read past its own decision point)**
- `research/kalshi/build_causal_slices.py` — cuts ONE SLICE PER DAY: every block <= day X, later blocks
  dropped. A day's tape is served under the NEXT day's key, so the whole block in one file let a
  specialist read its own outcome. All three first-run G22 specialists reached forward and all three
  declared it. Self-audits; `forward_stamps()` also reports capture stamps past the decision point.
- `research/kalshi/merge_perday.py` — joins per-day posteriors into the per-specialist `days[]` shape the
  coordinator reads, GUARDED on owner_map: a mis-owned or missing day fails at the join.

**DATA-INTEGRITY GUARDS (the enemy has now worn FIVE faces: empty, wrong-value, off-instrument, wrong-ENCODING, frozen-but-LIVE)**
- `research/kalshi/state_health.py` — two new RECONCILIATION guards, not presence checks:
  the b_share identity (`session_b_share == session_b_share_two_sided * (1 - unsided_volume_frac)`) HARD
  at >0.002 (hole #9), and `squeeze_watch._live` vs `flow_calendar` (hole #10). Both negative-tested
  against the real defect and across all 17 groups for false positives.
- `research/kalshi/bshare_restage_repair.py` — HOLE #9. Recovers `session_b_share` by algebraic identity
  without a data plane; idempotent, dry-run by default, declares each repair via `session_b_share_basis`.
- `research/kalshi/squeeze_watch_live_repair.py` — HOLE #10. Re-derives the `_live` calendar limbs from
  `flow_calendar` and the dead-sponsor arm from the block's own expiry calendar. Nulls
  `calendar_limb_satisfied_live` rather than emitting a confident false — a derived boolean whose input
  is masked must not be served as `false`.
- `research/kalshi/build_anchor_block.py` — the anchor was NEVER DELIVERED to the agents (only g15 ever
  had an anchor file). VERIFIES rather than asserts: each anchor must equal the PRIOR group's actual
  last-day close (chain holds exactly G17->G23) and `anchor_lasthr_dir` is re-derived from the price
  path. Carries `direction_caveat` / `close_in_range` / `net_ticks` — both G22 and G23 anchors sit at the
  price RESOLUTION FLOOR.

**THE WEATHER / DEMAND STACK (rebuilt on Greg's desk knowledge)**
- `research/kalshi/gas_call_residual.py` — `demand - solar - wind - nuclear` (coal deliberately NOT
  subtracted: that reproduces `gas_mwh` by construction). Two alignments, mechanism and decision-time.
  Result: **UNTESTED IN ITS CLAIMED REGIME** — every block carrying `grid_stack` is WARM (mean gw_hdd
  0.12-0.72) and Greg scopes the residual to cold/turning-cold. Prints its own power warning.
- `research/kalshi/forecast_harness.py` — CDD FORWARD LADDER served (`forecast_gw_cdd`, `d_gw_cdd`,
  `fwd7_gw_cdd_span`), `gw_cdd_d0` + `d_gw_cdd` on `sunday_reopen`, a `seam_delta_warning` (run deltas
  baseline run-over-run, so across a seam difference the LEVELS) and a `ladder_basis_note` (an
  unreachable absolute HDD bar is UNEVALUABLE in summer, not satisfied and not refuted).

**THE RECORD (Greg, S109: "if you only have actions without context, it's tough to learn and to replicate")**
- `research/kalshi/G22_REASONING_LEDGER_S109.md` — WHY each specialist decided what it did, attributed:
  the right calls with their reasoning, the catches, and the after-the-fact corrections — including
  Greg's four corrections and the places I was wrong.
- `research/kalshi/S109_MERGE_PROPOSAL_G22.md` — P0 through P0.8, each with a falsifier. P0 weather as
  hill+spike; P0.5 seasonal station weights (OHIO HAS NO STATION); P0.6 coal headroom; P0.7 the renewable
  subtractor; P0.8 the residual's cold-only scope.
- `SESSION_HANDOFF_2026-08-01_S109.md` + `DROP_IN_S110.md`.

## S108 (2026-08-01) — G20 done, G21 walked, holes #7/#8, brain s103.6

**Data-integrity guards (the recurring enemy has now worn THREE faces: empty, wrong-value, off-instrument)**
- `research/kalshi/tape_reconcile.py` — HOLE #8. Asserts `tape_conditions` measures the CONTRACT BEING
  FORECAST by reconciling its trade count against the scored leg; hard-fails outside [0.95, 1.05]. Wired
  into `stage_group` after `state_health`. Presence is not enough and internal consistency is not enough -
  only reconciliation settles it. Also carries `load_leg_trades`, the leg reader the harness now uses.
- `research/kalshi/state_health.py` — extended: a `provisional_tail` weather day is now HARD (hole #7).
- `research/kalshi/archive_blind.py` — THE FILENAME COLLISION (3rd occurrence). Archives the blind's
  posteriors by MOVE, not copy, so a specialist that fails to write hard-fails the guard instead of
  silently serving blind numbers at the refine's filename.
- `research/kalshi/group_coordinate_refine.py` — `assert_not_the_blind()`: hashes every round-1 posterior
  against its blind archive and refuses a byte-identical match. Negative-tested. Also renders
  blind-vs-refine-vs-price.
- `research/kalshi/group_coordinate_blind.py` — speaks the ENGINE schema natively (accepts
  `expected_magnitude_usd`/`path_p50_curve` as well as the legacy names), killing a per-run hand-built
  alias that lived in the scratchpad and did not survive a session. Regression-proven byte-identical.

**Session bootstrap**
- `research/kalshi/session_bootstrap.py` — one command from empty to ready: keys chmod 600, STS verify
  (prints only the account tail), restore, then the completeness gate. `--verify-only` reports without
  writing. Strips the container's PLACEHOLDER creds on every AWS call.
- `scripts/session_start.sh` — extended to restore automatically when creds are present and to NO-OP
  LOUDLY when they are not.

**Measurement / scoring tools (all read committed artifacts only - no restore, no creds)**
- `research/kalshi/blind_score_nonpooled.py` — **the scoring view doctrine now requires**: per-day errors,
  `sum|err|`, drift AND the survival ratio together, because drift is a sum of SIGNED errors and cancels.
- `research/kalshi/blind_drift_trend.py` — forward-curve drift group over group.
- `research/kalshi/blind_lean_decomp.py` — is the blind's error a LEVEL bias or SHAPE? (answer: shape).
- `research/kalshi/bshare_normalization_probe.py` — the probe that found the b_share defect.
- `research/kalshi/blind_input_audit.py` — what the BLIND actually sees in a staged state.

**Harness fixes**
- `research/kalshi/flow_read.py` — two-sided b_share series + `unsided_volume_frac` + `phase_volume_lots`
  / `phase_n_trades`; reads the SCORED LEG when a group context is supplied.
- `research/kalshi/forecast_harness.py` — `prior_full_session` (the Monday stub fix), the two-sided
  copy-through, `squeeze_watch`'s live calendar limb, `--group` on decision-state, leg-targeted tape read.
- `research/kalshi/nws_temp_feed.py` — flags `provisional_tail` on the last day of any fetch range.
- `research/kalshi/group_he24_he1_handoff.py` — stage-time exit-state precompute + `chain_regime_age_sessions`.
- `research/kalshi/stage_group.py` — passes `--group`, runs the reconciliation, precomputes exit states.

**Brain + merge record**
- `research/kalshi/knowledge/ng_brain.json` — **s103.6, 67 plays** (backups s103.2/.3/.4/.5).
- `research/kalshi/G20_MERGE_PROPOSAL_S108.json`, `BSHARE_NORMALIZATION_PROPOSAL_S108.json`,
  `BSHARE_REPOINT_COMPLETION_S108.json`, `G21_MERGE_PROPOSAL_S108.json`,
  `BSHARE_REPOINT_GAP_S108.md` — the four merges and the gap C found in the first b_share fix.
- `research/kalshi/adjudicate_g20_merge.py` — takes ANY proposal path; verifies strictly-additive.
- `SESSION_HANDOFF_2026-08-01_S108.md` / `DROP_IN_S109.md` — the record + the next box (the branch box
  is BOX 1 there, to be pasted alone first).

## NEW IN S104 (2026-07-21, current) — Friday->Monday cascade cleanup, G15 MBO round 2, coordinator guard

- `research/kalshi/agents/mbo_refine_shared.md` + `mbo_specialist_{A,B,C,D,E}.md` — CANONICAL MBO
  5-specialist causal-refinement files (A weekend/B Monday/C core/D Thu-EIA/E Fri-expiry), incl. the
  round-2 HE24->HE1 handoff protocol + output contract. Registered in agents/README.md.
- `research/kalshi/coordinate_g15_mbo.py` — now GUARDED (SELECT/ASSEMBLE only; hard-fails on any
  day-move no specialist owns) + `--r2` round-2 mode + actual-curves-only render (own p50 path,
  no re-anchored/scaled lines, no gap bridges). The guard + render pattern to port to every coordinator.
- `research/kalshi/forecasts/grp15_mbo_specialist_{A..E}_r2.json` + `grp15_mbo_refined_r2.json` +
  `renders/ng_refine_s95/g15_mbo_comparison_r2.json` — G15 MBO round 2: 12/12 dir, mean abs err 66.
- `research/kalshi/knowledge/ng_brain.json` — **s102.5, 46 plays** (backup ng_brain_s102.4_backup.json;
  the three cleanup proposals kept as review artifacts: ng_brain_{friday,midweek,monday}_proposal.json).
- `research/kalshi/CASCADE_S104_friday_cleanup_summary.md` / `CASCADE_S104_monday_fix_summary.md` —
  the per-day cascade tables (committed copies of the specialists' analyses).
- `SESSION_HANDOFF_2026-07-21_S104.md` / `DROP_IN_S105.md` — the record + the next box.

## NEW IN S101 (2026-07-21) — G12+G13 walked, day-class doctrine, rest-of-year data machine

- `research/kalshi/run_g12_rt_s101.py` / `run_g13_rt_s101.py` — G12/G13 actuals (rt.json) +
  continuous renders on the walked NG.n.0 basis from the local n0 store (the run_g11 precedent).
- `research/kalshi/pull_july_2026_cl.py` — CL July 2026 raw top-up (CL year store ended 06-30).
- `deploy/aws/pull_rest_2026.py` — THE REST-OF-YEAR DATA MACHINE (detached box job): NG.n.0/n.1
  trades Mar->present, NG.FUT + ON/LNE.OPT + CL.FUT + LO.OPT statistics/definitions raw, CL.n.0/n.1
  full year. Resumable, cost-guarded ($1.10 total measured).
- `deploy/aws/cl_redecode_runner.py` — the 51 CL stub-Monday FREE redecode from done Databento
  jobs (box-detached; window closes ~Aug 12-14).
- `research/kalshi/knowledge/ng_brain.json` — s101.6, 27 plays (backups: s101.2/s101.5;
  proposals: s101.3/s101.6 kept as review artifacts).
- forecast_harness.py additions: `--mask-after` one-shot masking fix; squeeze_watch prompt-expiry
  fields + unwind_watch.
- Extended stores (S3-pushed): storage_consensus (hole closed, 47 reports), steo_vintage (11
  vintages), flow_calendar + solar_calendar (-> 2026-12-31), vol_regime (-> Mar 13), n0 tape
  (-> Mar 13 local; box extends to present on S3).
- `SESSION_HANDOFF_2026-07-21_S101.md` / `KICKOFF_2026-07-21_S102.md` — the record + the next box.

## NEW IN THE DASHBOARD SESSION (2026-07-20, current)

- `dashboard/` — the Mission Control READ PLANE (dashboard wiring session, branch
  `claude/dashboard-wiring-rgvahe`): FastAPI server (`dashboard/server.py`) + read-only
  adapters over the signal core (brain / decision_state / lag map / fees / kalshi candles /
  nymex minute bars / data-plane health) + the S100 prototype frontend wired with
  REAL DATA / AWAITING DATA / SIMULATED truth badges. Executor lane deliberately NOT built
  (last, per Greg). See `dashboard/README.md`; landing pad `DASHBOARD_HANDOFF_S100.md`.

## NEW IN S100 (2026-07-20, current)

- `research/kalshi/mos_cycle_feed.py` — feed A ph1: cycle-level MOS as-of (00z/06z/12z/18z,
  weekend cycles; availability wall runtime+4.5h). Store S3 `weather/mos_cycle/`.
- `research/kalshi/freeze_risk_feed.py` — feed E: basin freeze-off MIN temps (MAF/OKC/PIT/SHV),
  thresholds-as-data. Store S3 `weather/mos_freeze/`.
- `research/kalshi/lag_execution_map.py` + `kalshi_fill_model.py` — feed M: the lag execution
  map on the KXNATGASD life + verified fee/spread model. Store S3 `kalshi_echo/`. Findings:
  `research/kalshi/KALSHI_ECHO_MAP_S100.md` (maker-first verdict).
- `research/kalshi/TWO_COACH_SPEC_S100.md` — Tier 3 item 6, printed (approval pending).
- `research/kalshi/pull_july_2026.py` — the July 1-18 NG tape pull (done, idempotent).
- `research/kalshi/LIVE_TELEMETRY_S100.md` — the live loop's first datum (7.7ms median).
- `research/kalshi/vendor/` — verbatim vendor references: Databento raw-API example, the
  IV/Black-76 tutorial (feed I ph ii pattern), `DATABENTO_LIVE_OPS_NOTES_S100.md` (M5 collector
  design constraints: replay/snapshot/limits/reconnect).
- `DASHBOARD_HANDOFF_S100.md` (repo root) — the parallel dashboard session's landing pad.
- Brain: `knowledge/ng_brain.json` = **s101.2** (Tier 3 doctrine merged; s100.3 backup kept).

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

## S99 — four gate feeds + the Monday repair (CURRENT)
- **`research/kalshi/steo_vintage.py`** + S3 `steo_vintage/` — FEED T (WIRED): the 7 frozen STEO
  vintage workbooks (sep25..mar26), all 37 Table-5a series, MEASURED release-date joins
  (knowable_from = release+1; Last-Modified never used), per-workbook column-origin detection,
  revision deltas vs prior vintage (the freeze re-mark readable from 2026-02-11). Selftest 22/22.
  `STEO_VINTAGE_NOTES_S99.md`.
- **`research/kalshi/nuclear_outages.py`** + S3 `nuclear_outages/` — FEED R arm 1 (WIRED): EIA
  daily US nuclear capacity-out 2007->present, wall period+1 strictly-prior, gaps stay gaps; the
  freeze's 1.8->3.2 GW jump at D+1. `NUCLEAR_OUTAGES_NOTES_S99.md` — ALSO carries the Pyth
  reckoning (NGD feeds never published; NATGAS 24/7 = Pyth Pro; FREE HERMES DIES 2026-07-31 ->
  pyth_collector sunset decision) and the KXNATGASD settlement verification (Pyth per-contract
  NGD 1-min close 17:00 EDT; 5bd-forward underlying roll; expiration_value = the settle print).
- **`research/kalshi/grid_stack.py`** + S3 `grid_stack/` — FEED Q (WIRED): EIA-930 daily per-BA
  demand + DAY-AHEAD demand forecast (DF) + gen by fuel + shares + labeled US48 burn estimate;
  wall period+2; Eastern framing; freeze ramp 28.3->41.1 Bcf/d decision-time-visible.
  `GRID_STACK_NOTES_S99.md`.
- **`research/kalshi/options_surface.py`** + S3 `options_ng/` — FEED I phase i (WIRED; G13 gate
  item CLOSED): NG options OI pin map off GLBX definition+statistics, BOTH roots (ON+LNE — the
  "NG.OPT resolves to nothing" symbology trap), 81 sessions, top-5 OI walls / P/C / OI-weighted
  strike / opex clock; opex anchors cross-check flow_calendar exactly. $4.67 substrate; monthly
  chunking beats the 4-month 504. `OPTIONS_SURFACE_NOTES_S99.md`.
- **`research/kalshi/databento_live_smoke.py`** — one-shot validation of the Bento LIVE plan
  (Standard $179/mo, SUBSCRIBED S99 close; smoke test = S100 opener).
- **`research/kalshi/renders/settle_delta_sweep_s99.json`** — Kalshi settle vs NYMEX 17:00 tape,
  full KXNATGASD life: matched days median 0.1c; all big deltas = 5bd roll-window contract
  mismatch (calendar spread, not oracle error).
- **`research/kalshi/redownload_mondays.py`** (pre-existing S92 script, re-run S99) — repaired
  the 22 NG stub Mondays Feb 2 - Jun 29 2026 found by the sweep (incl. ALL G12/G13 Mondays). CL's
  51 stubs HELD for Greg (paid ~$130-165 vs free redecode before job expiry ~Aug 12-14).

## S98 — the rewritten DATA GATE (the build list before any new group runs)
- **`research/kalshi/knowledge/ng_brain.json`** — **s100.3, 23 plays** (MERGED 2026-07-20, Greg
  approved: the C2 measurement - ratio reformulation REFUTED on comparable data, 0120 0.714 vs 0107
  0.718; C2 kept + scoped per-instance, flip confirm completes as C1+C3+C4 on the modern tape
  class; forward test rides G12). Backup `ng_brain_s100.2_backup.json`; record
  `C2_RATIO_FINDINGS_S98.md` + `run_g11_fingerprints_s98.py` (all 12 G11 sessions fingerprinted on
  NG.n.0, series_basis-tagged, pre-G11 counts reproduced exactly).
- **`research/kalshi/storage_consensus.py`** + S3 `consensus/` — FEED D (WIRED): the EIA weekly
  storage SURVEY CONSENSUS (the number the market is positioned against, vs the seasonal proxy),
  29/29 weeks Sep 2025-Mar 5 2026, per-house rows + disagreement exposed, holiday-shifted prints
  verified (incl. the Dec 29+31 double-print week), 0 blind-wall violations, named forward hole
  Mar-Jul 2026. `STORAGE_CONSENSUS_NOTES_S98.md` = sources/caveats; 17 weeks of as-printed vs
  current-vintage diffs handed to feed K.
- **`research/kalshi/platform_sync.py`** — the ONE door between local cache and the S3 data plane
  (M2): list / pull / push with per-prefix manifests, dry-run default, post-push verify.
- **`research/kalshi/kalshi_ng_backfill.py`** + **`data/kalshi_ng/`** (local, gitignored; S3 push
  pending) — FEED L: Kalshi NG family backfill off the public API's live+historical endpoint split
  (`/historical/cutoff` = the moving boundary, 2026-05-21 at build). Full raw definitions + trades +
  1-min candles for KXNATGASD/KXNATGASW/KXNATGASMON life and the winter annual NG markets.
  `--selftest`, `--coverage`. HEADLINE FINDING: KXNATGASD did not exist before 2026-03-27 — the
  walked winter has NO Kalshi NG daily market (Jan-Feb 2026: zero NG-linked Kalshi markets at all);
  feed M's winter echo replay is structurally impossible, its lag/fill work runs on the Mar 30+
  life instead. Dailies skip FRIDAYS (the weekly market owns Friday).
- **`research/kalshi/KALSHI_NG_COVERAGE_S98.md`** — feed L's deliverable: branch-bins inventory
  (collector born 2026-07-12; one named 12h outage Jul 16-17), the two-worlds API map + S80 code
  drift, the 119-date winter coverage table (every date a named gap for the family), what
  live-forward capture provides that history cannot (books, sub-minute).
- **`research/kalshi/DATA_GATE_S98.md`** — THE AUTHORITATIVE DATA PLAN (Greg 2026-07-20: "this is what
  we're doing before we do any more runs"). Supersedes the GATE section of
  `SESSION_HANDOFF_2026-07-19_S97.md`. Organized by regime family (DEMAND / POSITIONING / DELIVERY):
  Tier 0 = wire the three landed S97 feeds + `squeeze_watch` + the information clock; Tier 1 = G11
  fingerprints on `.n.0` -> the C2 ratio reformulation (the G12 critical path); Tier 2 = feeds A-M
  (model-cycle timing, vol regime, model disagreement, storage CONSENSUS, freeze-off risk, flow
  calendar, cash basis, COT combined, options surface [required for G13], LNG feedgas sizing spike +
  paid-data survey, revision-vintage audit, Kalshi NG data restore [L], lag echo replay + Kalshi
  fill/fee model [M]); Tier 3 = brain doctrine (usage guidance, flip driver checklist, evidence-day
  registry, two-books scoring split, squeeze-regime doctrine, the TWO-COACH spec). Section 0c = the
  TWO-COACH ARCHITECTURE (Greg 2026-07-20): Kalshi = initial primary vehicle, NYMEX dailies quickly
  after, one shared signal core, two separately-scored coaches; the lag is the Kalshi edge.
  Gate-closure condition at the bottom defines when G12/G13 may run.
- **`deploy/aws/AWS_PLATFORM_S98.md`** — the platform consolidation + AWS migration plan (Greg
  2026-07-20: end the data sprawl; platform lives in AWS, hybrid with git). git = CODE, S3 = ALL
  DATA one bucket + manifests, local = cache, live loop us-east-1 co-region with Kalshi.
  Execution-speed verdict: the established 7-20s+ futures->Kalshi lag needs SUB-SECOND not sub-ms;
  LLM never in the hot path; lag telemetry per fire (decay watch, never a retest). M1-M6 steps;
  M1 = key rotation (Greg) blocks all pushes.
- **S97 feed modules (landed S97, indexed here):** `research/kalshi/cot_feed.py` +
  `data/cot/` (CFTC COT, publication-time blind wall); `research/kalshi/storage_regional.py` +
  `data/storage_regional/` (EIA five-region + salt/non-salt); `research/kalshi/contract_structure.py`
  + `data/contract_structure/` (49 fields incl. the CALENDAR-FRONT block that sees what the
  OI-continuous front hides). WIRED into decision_state in S98 Tier 0 (audit-joins: 0 violations,
  101 days).

## S96 — G7 winter block + per-group refine + the settled protocol (CURRENT)
- **PROTOCOL (Greg S96):** one-shot block-blind = the CANONICAL skill test; refine after EVERY group
  (iterate until refined curves track via GENERAL rules only, n>=2 spanning groups; irreducibles declared);
  renders PRINTED (sent to Greg) before each refine.
- **`research/kalshi/forecast_harness.py`** — S96 BLIND FIX (storage/surprise joins strictly-prior-day; the
  old `<=` leaked a storage Thursday's own 10:30 print) + **`reveal` subcommand** (day-sequential rolling-anchor
  reveal packages: per-day actuals + per-leg fingerprint counts; kept for the LIVE-coach mode).
- **`research/kalshi/forecasts/grp7.json`** — G7 blind + refined fields per day; `grp7_seq_experiment.json` —
  the paused 3-day day-sequential experiment (its 1106 +1450g/+1350a hit = the day-boundary-turn evidence).
- **`research/kalshi/knowledge/ng_brain.json`** — **s99.2, 21 plays** (S96 arc added: giveback_exhaustion_
  boundary, mature_swing_alternation, giveback_origin_shelf, catalyst_continuity_frontrun,
  chain_polarity_flip [four-condition confirm], failed_rally_tell, crash_regime_bands,
  post_parabolic_bleed). Backups + all proposals alongside.
- **`research/kalshi/forecasts/grp{7,8,9,10}.json`** — blind + refined fields per day for the four winter
  blocks; `grp9` = the December surplus-collapse crash (lean-miss 1 -> polarity flip); `grp10` = the January
  bleed (lean-miss 2, the false flip -> the hardened confirm + the bleed class).
- **`research/kalshi/renders/ng_refine_s95/`** — g{7,8,9,10}_{continuous,overlay}.png + *_refined_*.png +
  rt/score jsons + grp*_state.json + grp7_reveals.json; fingerprints.json spans Nov 4 -> Jan 16
  (52 characterized days).

## S95 — continuous-curve + roll-adjustment + refinement machinery (CURRENT)
- **`research/kalshi/continuous_rt.py`** — THE RENDER FILE (canonical, date-parameterized): real-price RT
  curve + optional `--guess` forecast overlay, rolls marked, weekend bridges broken. Use for any window.
- **`research/kalshi/roll_adjust.py`** — contract-roll detection (instrument_id change) + back-adjust offsets.
- **`research/kalshi/fast_tape.py`** — fast trade-price loader (grep-prefilter + npz cache, ~7x).
- **`research/kalshi/precache_window.py`** — pre-decode a date window to npz.
- **`research/kalshi/continuous_score.py`** — per-event scorecard + roll-adjusted skill overlay.
- **`research/kalshi/characterize_turns.py`** — merge per-leg fingerprints into `fingerprints.json`.
- **`research/kalshi/extract_guesses.py`** — pull guess-vs-actual scalars from the brain -> `guesses.json`.
- **`research/kalshi/AGENT_RUNBOOK_S95.md`** — the two agent prompts (blind forecaster + unblinded refine).
- **`research/kalshi/forecasts/`** — committed per-group forecast records (guess curve + reasoning) grp{3,4,5,6}.
- **`research/kalshi/renders/ng_refine_s95/`** — committed renders (g3g4g5_continuous.png, g6_continuous.png,
  *_rt.json, fingerprints.json, guesses.json, *_state.json) so they need no regeneration.
- **`research/kalshi/knowledge/ng_brain.json`** — the ONE-FILE brain (s95.1; + s95.2 proposal to merge).

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

**S93 changes (detail in `SESSION_HANDOFF_2026-07-14_S93.md`):** — the coach agent moved INTO AWS.
- `deploy/aws/COACH_AGENT_SETUP_S93.md` — **NEW**: reproducible box-agent setup (SSM access, Bedrock in us-east-1
  vs S3 in us-east-2, Node+Claude Code install, `/etc/markets/coach.env`) + the THREE pluggable LLM backends —
  Claude Code+Bedrock, Anthropic API direct, and **OpenAI** (Greg S93). The open Claude-Code model-preflight snag.
- `SESSION_HANDOFF_2026-07-14_S93.md` / `KICKOFF_2026-07-15_S94.md` — the S93 record + S94 priorities (JOB 1 =
  make the agent LLM invoke on the box; JOB 2 = run the loop on the box; brain still s92.1, not advanced).
- `scratchpad/ssm_run.py` (gitignored) — SSM send+poll helper to drive the box `i-08cee...` from a session.
- AWS access state: `Claude` IAM user (acct 568968024170) = S3Full + EC2 + SSMFull + BedrockFull + inline
  `pass-ssm-role`; no permissions boundary. Bedrock model access enabled in **us-east-1 ONLY**. Box instance
  profile = `Ssm` (SSM-only role); coach uses static `Claude` keys for S3+Bedrock.

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
