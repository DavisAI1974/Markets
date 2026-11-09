# Handoff for the next session (written 2026-11-09, 00:10 Eastern)

Branch `claude/three-day-dipole-20261108` (cut from `codex/ng-shadow-discovery-20261108`), folder `tasks/family-research-20261022/claude-pass-3day/`. Nothing is merged; Greg keeps merge authority.

## 0. Read first
Read Claude's memory file `/areas/october-ng-dipole-direction.md` (Greg's strict direction and vision) and `/preferences.md`. Do not ask Greg to restate them and do not repeat them back to him as if they were new. If something is genuinely unclear, ask him before building. Before each step, say in one line what you are about to do and which of his points it serves.

## 1. Order of work (Greg, Nov 8-9 2026). Do one thing, finish it, then the next.
1. Complete the lifecycle renders for all four days (section 3A).
2. Complete the Oct 18 analysis suite on Oct 2, 3 and 17 (section 3B).
3. Continue the reverse-engineering of the Native dipoles on all four days (section 3C).
4. Only when Greg says so: put the pieces back together.

Rules that apply to every step: every event and instance is recorded individually; no averages as the final word; no signal is discarded (rejected and suppressed candidates stay in, with their disposition); results are one render per instance showing the whole lifecycle (before birth, birth, recognition, what follows, exhaustion) with time-exact layers stacked, never counts and never prebirth pieced off from the rest; data first (charts and tables before commentary); plotted points reconcile to rows; report measured things only (no gates, thresholds, pass/fail or evaluative words); label speculation.

## 2. State at the end of this session
Done and committed (earlier commits on the branch):
- Cohort suite (c24a-d), crossday tables, birth-aligned event study (x03-x10), findings files `FINDINGS_THREE_DAYS_20261108.md` and `FINDINGS_EVENT_STUDY_20261108.md`.
- Tier 2 chain (c16 lead-lag, c17 state cells, c14 condition couplings, c15 pair couplings, c18 forward stack) run on Oct 2, 3, 17 and 18 with the same code: `tables/<day>/t2_*.csv`. These have NOT been compared side by side with Oct 18 yet and have no write-up.
- Per-instance detector ledgers: `crossday/detector/ledger_saturated_seconds_<day>.csv` (every second with the 20 s ratio at exactly +1 or -1 after warm-up, with its disposition in the emulated detector) and `ledger_recorded_births_<day>.csv` (every recorded birth, whether the emulation produced it).
- Per-candidate full-life paths: `tables/dipole/<day>/instances/x13_life_paths.npz` (boundary k = -60 .. +1260 s from the birth-second boundary; same variables and orientation as x03; one row per candidate).
Scripts: `x11_det_*.py` (detector emulation), `x12_instance_renders.py`, `x13_life_paths.py`; run scripts in `run/`.

Not done: the lifecycle renders were interrupted (about 160 of 741 on Oct 2 and 138 of 832 on Oct 3 were produced from the run; none on Oct 17 or 18; the run's files are in the session workspace and are not committed). `crossday/detector/instance_life_markers_<day>.csv` is written only by a complete run.

## 3. Next research steps

### 3A. Lifecycle renders (finish first)
Run for each day: `OD_WORK=<derived dir> OD_SESS=<day> python3 -I x12_instance_renders.py <outdir>` (see `run/run_renders.sh`; about 1 s per render, two days at a time). One PNG per candidate covering k = -60 .. max(+160, later of first flip and first empty window + 60) s, capped at +1260 s with a note. Panels: oriented midpoint and spread; touch sizes; aggressor lots with and against; target-side and own-side book activity; the 20 s ratio times polarity. Markers: run onset, birth second, recognition, run end, first flip, first empty window, saved weakening transitions, every neighbouring birth. Show Greg a few (including candidates with the longest lives) before anything else, and send him each day's folder as a zip. The ordering and numbering of candidates here (n of N, by candidate-input row) will not match the other agent's #147 and #538; ask Greg which ones he means, by day, rather than assuming.

### 3B. Oct 18 suite on Oct 2, 3, 17
Inventory of the Oct 18 suite against the other days:
- Runs on all days from the raw tapes, same code: Tier 2 dense grid and couplings, lead-lag, state cells, forward stack (done, above); regime scans c19-c23 (done earlier, `tables/<day>/t3_*`); dipole cohort c24 (done).
- Exists only for Oct 18, inputs not present for the other days: Tier 1 (the 749 first-observed families from the family run, `candidate-flow-transition-audit.csv`, outcomes at fixed horizons, order-level windows per family), the 99-plane and 13-input crosswalk (`all-99-relationship-roles.csv`, `external-operands.csv.gz`). The other days have candidate inputs (741, 833, 741), research-atlas-v2 tables, root frames and standalone inputs/decisions, but no family-level audit.
- Open question for Greg (ask, do not assume): should a Tier 1 equivalent be built on the other days from their Native candidates (the closest analogue to the Oct 18 families), and with which definition of "first-observed family"?
Then: put the Tier 2 tables for all four days side by side with Oct 18, instance by instance where applicable, reconciled to rows; no averages as the final word.
- DONE 2026-11-09 (later session): `x14_tier2_crossday.py` puts c14, c15, c16, c17 and c18 side by side on the four days (`crossday/t2x_*.csv`), with a
  shifted-Y reference built from saved draws (`x16_tier2_shift_draws.py`) and the full pair-coupling family (`x17_pair_couplings_full.py`,
  `crossday/pairs_full/`); charts `x15_tier2_crossday_charts.py` -> `crossday/t2x-*.png`, every plotted count reconciled to its table rows. Write-up
  `FINDINGS_TIER2_CROSSDAY_20261109.md`. The grids were rebuilt from the tapes in that session and reproduce every committed Tier 2 table exactly.
  Still open in 3B: only the Tier 1 question above.
- DONE 2026-11-09 (same later session): the Tier 1 question is answered by section 22 of `claude-october-discovery-20261108.md`: the actual first-observed
  family starts exist for all four sessions (markets-data 7b50d634, 795 / 848 / 823 / 749). `x18_tier1_days.py` runs the Oct 18 Tier 1 chain on them
  (Oct 18 reproduces every committed table exactly), `x19_tier1_crossday.py` puts the four days side by side (`crossday/t1x_*.csv`), write-up
  `FINDINGS_TIER1_CROSSDAY_20261109.md`. Section 3B is complete.

### 3C. Reverse-engineering the detector (all four days)
Source of the detector settings: `replay-comparison/sources/research-comparison-<day>/source-receipt.json` (candidate_detection) for Oct 2, 3, 17. Note the Oct 3 receipt covers only 3,599 seconds with 0 emitted (a different slice); no receipt in the repo for Oct 18. Settings: flow is the 20 s signed ratio; warm-up 900 s and at least 600 finite observations; threshold = 0.85 quantile of the trailing finite |ratio| (always 1.0 where one-sided windows exceed 15 percent of observations); baseline = median of the finite |ratio| over t-30..t-10 (21 points); refractory 45 s; local radius 5 s; zero epsilon 1e-12.
Measured so far (x11_det_*.py, ledgers):
- Flow series: the companion 20 s flow series is reproduced from the tape (per-second lots equal on 99.98 percent of seconds) by classifying each print against the preceding completed-group midpoint; prints exactly at the midpoint appear to take the aggressor side in the detector's own series (the two Oct 17/18 births that sit on empty companion windows have such a print inside the window). With that rule recorded observations_behind_threshold = my finite count + 6 for 620 of 741 on Oct 2.
- Baseline: recorded baseline equals the median described above on 720/741 (Oct 2), 812/833 (Oct 3) and 717/741 (Oct 17) births (empty window gives 0).
- Evaluation time: the observation count behind the threshold equals the finite observations through t+5 for 710/741 births on Oct 2 (Oct 17 differs by a drifting offset of about -47; unexplained).
- Lifecycle of a recorded birth in the emulation: the first qualifying second (|ratio| at the threshold, evaluated at t+5) opens a cluster that is released 45 s later; the qualifying second with the highest prominence (|ratio| minus baseline, first wins ties) inside the cluster is the birth; lag = release - birth second. This reproduces the recorded 50 s lag for most births and the shorter lags for the rest.
- Result of that emulation (recorded births / emulated births / exact matches): Oct 2 741/803/675, Oct 3 832/843/700, Oct 17 740/800/658, Oct 18 863/863/688. On Oct 2, 647 of 675 matches also have the recorded lag.
Open (list every instance, do not average): the emulation adds and misses births; the first divergence on Oct 2 is a candidate decided exactly at the release second that the recorded run did not start a cluster from (179 clusters start at a release second in the emulation, 63 of them recorded); the extra finite seconds in the detector's series (the receipt implies about 673 more than the companion); the Oct 17 offset. Next: examine each mismatch instance individually (the ledgers already list them), test the at-release rule and the at-midpoint classification against the tape, then repeat on all four days. Per the standing rule, keep every rejected and suppressed second.

### 3D. Other open items
- The agent follow-up (same prompt and analysis on Oct 18; issue #13 on `DavisAI1974/Markets`) is drafted but unposted; Greg wants it done. Ask him before posting.
- The other agent's SAME-only first-event table is not available here; the first-event curves in `crossday/es-first-event-curves.png` use my own event definitions on all covered candidates.
- Greg's observation about the circled areas of the agent's first-event curves (distinct markers and algebraic equations in the circled parts; the one outlier on the third render looks like the first render's curves): record it as his observation; he said this is big. Do not dismiss it.

## 4. Rebuilding the data in a fresh session
Derived data (raw/recon/groups parquet and npz) lives in the session workspace under `OD_WORK` and is not committed. Tapes are in `DavisAI1974/markets-data` (blobless clone, then add the paths; sha256 values in its `MANIFEST.json`). Order: `c00_dbn_to_parquet.py` -> `c03_recon_mbo.py` -> `c01b_groups_from_recon.py` (`run/run_ingest.sh`; one UTC day per tape; sessions use the prior evening's tape, see `SESS_TAPES` in `odcfg.py`: Oct 2 = 20231001 + 20231002, Oct 3 = 20231002 + 20231003, Oct 17 = 20231016 + 20231017, Oct 18 = 20231017 + 20231018), then `c12_tier2_build.py <day>` for the grids (`run/run_grids.sh`), `run/run_session.sh <day>` for the cohort grids, c24 and the session tables, `x03_birth_paths.py` per session, `x13_life_paths.py` per session, then the renders. New data inputs go to markets-data with a MANIFEST.json entry; ROOT frame publication resumes to S3.
