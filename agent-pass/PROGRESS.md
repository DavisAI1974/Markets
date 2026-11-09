# Native dipole research pass progress

Current storage instruction (user, 2026-11-08): publish code/findings to Markets and data/renders/workbooks/provenance to markets-data. The local-only rule is removed. No further desktop computation. Earlier checkpoint descriptions record what happened, not current storage instructions.

## Launch

- Issue: https://github.com/DavisAI1974/Markets/issues/14
- Agent: Codex (Copilot was explicitly superseded by the user).
- Base branch: codex/ng-shadow-discovery-20261108
- Base commit: a1c4d6f32a03a21795f411e509f7fc77d479b3bb
- Working branch: codex/native-dipole-agent-pass-20261108
- Workspace: E:/Markets-native-dipole-agent-pass
- Scope: additive only under repository-root agent-pass/.
- Commit 1ce1fd8 is reachable locally as 1ce1fd89e9b3dec43e7fbb50abc3138415460c49.
- Setup performed: created an isolated sparse worktree; saved the verbatim issue specification and execution instructions. No research calculation has run in this pass yet.
- Row counts: not yet measured. The requested 863 births / 852 covered are to be reconciled against source data, not assumed.
- Reading order and task phases: follow TASK.md and EXECUTION.md.
- Next: read the required sources in order; begin Part 1A; write and inspect complete distributions and figure reconciliations before interpretation; commit and push progress.

## Source reading and execution assumptions

Read in required order: primer at 1ce1fd89; discovery log I-M and Handoff; c24a/a2/b/c/d; all 863 candidate rows and completed-group flow schema. Also read project AGENTS, chart-reading note, research memory and replay-comparison source coordinates. Applied git-workflow-and-versioning and spreadsheet skill for checkpoints and deliverables.

Pinned source base is a1c4d6f32a03a21795f411e509f7fc77d479b3bb. Raw tape revision 1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202 is reachable, as are saved October 18 groups at b5f28bd57 and additional groups at 2f12d6d47. No producer or infrastructure is needed. Large source/cache files will remain ignored under agent-pass/cache, with hashes and regeneration commands committed to avoid duplicating repository storage.

Part 1A reading: retain the original 852-covered subset, plus the 11 original seam exclusions as a separately labeled supplement when the archived full-session group source covers them. Birth paths use exact integer-second cutoffs from -60 through recognition, plus the exact recognition close. No averages, smoothing or scaling of dipole values. Matched controls use same archived session, spread regime and trailing-trade-count activity quintile at strict prebirth; deterministic seeds and all control coordinates are retained. A second draw checks control-choice dependence. Calendar labels are provenance, never numeric features.

Predictions recorded before computations: I think the saved detector uses delayed local extrema and plateau handling; let's see what the data says. I think natural path groupings may depend on representation; no cluster count will be stipulated. Operator forms to examine: constant recognition lag; signed rolling-flow update identity; flow sign determines quote-move sign; depth sign determines quote-move sign; rolling magnitude decays monotonically after birth. Each form will retain its individual residuals and exceptions. Moonshots will use discrete group quote changes and raw trade-side runs, with no claim that these exhaust all natural event definitions.

Next: compute Part 1A paths, controls, raw case traces and chart reconciliation before writing interpretation.

## Part 1A completed

Commands: `python agent-pass/scripts/part1a.py 20231018`; `python agent-pass/scripts/verify_part1a.py`; `python agent-pass/scripts/workbook_data.py part1a`; bundled Node `agent-pass/scripts/workbook.mjs`. Generated 36 charts, 270 reconciled panel rows, 288,144 path rows, 863 candidate paths and 1,726 controls (1,532 distinct anchors). Original coverage 59+793+11=863 retained; primary chart population 852. All 863 prebirth and recognition quote checks agree. All 583,688 saved group closes match cursor/receive/F_LAST in 771,787 raw records. Cases retain all raw messages for each chosen path and both controls.

Charts and CSV were built before FINDINGS measurements/interpretation. Inspected the FLIP quote heat strips visually. Spreadsheet bundled runtime is available; an E-drive junction was unsupported, so the builder uses createRequire anchored to the bundled Node runtime without modifying dependencies. Workbook contains exact review rows, with long paths in CSV.gz. No missing data source is being replaced by another population.

Next: Part 1B detector recovery, complete added/missed birth lists, operands and three lag clocks. New artifacts only under agent-pass/.

## Part 1B completed

Commands: `python agent-pass/scripts/part1b.py 20231018`; `python agent-pass/scripts/verify_detector.py`; workbook builder rerun. Completed-group series: 866 recovered, 842 matched, 21 missed, 24 added, 840 exact nominal timings. Native action-time reconstruction: 863 recovered, 863 matched, zero missed/added, all 863 nominal and actual recognition times exact. Six recorded operand columns each reconcile for 863. Saved full comparisons, empty/nonempty difference lists, every judged-second disposition, all lag rows and six-panel full-distribution figure. Fixed clipped chart titles after viewing the first rendering.

Raw action quote reconstruction checks 583,687 usable closes against saved book state. Initial incomplete quote is preserved and not tested as a two-sided book. The recovered detector was checked against pinned original source on plateau, quiet, and variable synthetic streams (27/24/35 outputs); all operands and clocks identical. Nominal lag equals 50 minus winner position for all 863. The observed extra wait is the first group close in a second after the nominal second. No producer reran.

Workbook review found that long clock strings could be coerced to floating point by the artifact library. Builder now prefixes exact nanosecond strings for literal-text preservation and widens identifier/clock columns. CSV remains the authoritative exact observations. Nullable clocks for the two later-day finalization-only records will use pandas Int64, avoiding float conversion.

Next: Part 2, replication of A/B on each archived day, full path-distance hierarchy without preset cluster count, governing-form counterexamples against both control draws and across days. Keep partial Oct 2/17 separate from full-session research.

## Storage policy change received during Part 2

Historical checkpoint: artifact publication was deferred at this point. The user removed that restriction on 2026-11-08. Current routing is code/findings to Markets and data/renders/workbooks/provenance to markets-data; no desktop computation or AWS/S3.

Already published before the change:
- `a4064816d`: Part 1A, `agent-pass/tables/20231018-*` (candidate operands, path members, paths.csv.gz, path dispositions, cases, case raw records, figure reconciliation); `agent-pass/figures/20231018-*` (36 figures); `agent-pass/research-tables.xlsx`; receipt and source manifest JSON.
- `50e04fce5`: Part 1B, `agent-pass/tables/20231018-*` detector comparisons, missed/added lists, detected births, per-second dispositions, lag rows and detector figure reconciliation; `agent-pass/figures/20231018-lag-distributions.png`; updated workbook and source manifest.

Both pushes succeeded with GitHub's repository-size warning. The index and unpublished commit range were inspected on receipt of the policy; the index is empty and no unpublished commit exists. Generated-data changes were unstaged at that checkpoint and are now migration inputs. At that checkpoint the October replication wrote under agent-pass/; its artifacts now belong in markets-data. Inventory will use only local file/blob sizes, never missing-as-zero. Verified markets-data destinations and manifests are recorded in PUBLICATION.md.

## Storage plan correction

Historical checkpoint: AWS/S3 was ruled out. The subsequent 2026-11-08 user correction requires artifact publication to markets-data with immutable paths and hashes. Earlier published artifacts remain disclosed above.

## Part 2 running checkpoint

All four A/B replications have completed once. Archived populations are 741/833/741/863; live recognitions 741/832/740/863. Native action-time reconstruction recovers every birth and nominal time; the two finalization-only records now take their actual recorded nominal availability from the operand object, never a substitute live group. Completed-group missed/added counts are 5/5, 5/5, 11/10 and 21/24. All six operand comparisons and live-clock checks are being checked across days.

C/D first computations also ran on all four dates. Each path representation is unscaled and keeps its individual time coordinates. Pairwise distances, every single-linkage merge, largest-gap membership and missing-coordinate patterns are saved locally. The largest-gap partition is explicitly a descriptive convention, not proof of one natural cluster count. Operational lifetime ends at the third consecutive opposite-sign second, or is right-censored at tape end. Undefined anchor flow has no lifetime; it is not a zero-second event. Five proposed relations plus the signed-net rolling recurrence have every candidate/control residual retained.

A final rendering/numerical-precision refresh is running before the Part 2 commit: full PNGs now allocate enough vertical pixels to every candidate heat-strip row; round-trip CSV parsing preserves written floating operands; undefined control lifetimes are blank instead of zero. Commands: for each archived date, `part1a.py`, `part2.py`, then `crossday.py`. The original calculation was not duplicated while active; this refresh follows its completion and addresses the observed rendering/missing-value issues. No new generated artifact was staged at that checkpoint. Part 3 code is prepared but will run after Part 2 checks/checkpoint.

## Read-only review evidence and corrections

The parent review independently checked all four days' six operand columns, exact live recognition clocks (741/832/740/863), null live clocks (0/1/1/0), and the nominal-lag identity for every birth. Path rows 254,025/283,542/253,764/288,144 match member totals, have unique candidate/kind/relative coordinates, and start at minus 60. Each day has 21 traced case/control members; corresponding raw record counts are 6,161/1,483/5,345/3,122.

A concrete plotting defect was found: undefined monotone-decay control observations carried numeric zero residuals and were plotted as zero. The calculation now records NaN, plots only defined dispositions, and verify_all asserts agreement between every operator panel and operator-summary. A figure-only correction script preserves the existing raw paths and hierarchy results. It will run once after the current refresh finishes, together with title padding and explicit October 18 863-versus-852 labels.

Scientific scope is explicit: the three-consecutive-opposite-second lifetime is an analyst-defined operational convention, marked SPECULATIVE beside life plots. It is not a recovered natural lifetime. Largest-gap partitions are conventions on the full hierarchy, not the discovered number of natural groups. No series, target or family is removed.

## Concrete recurrence alignment defect isolated

The universal-zero assertion stopped verification, so the 26 nonzero October 18 rows were investigated rather than removed. Native-flow cache seconds are contiguous and its independently recomputed recurrence is zero at those coordinates. Root cause: 13 sampled book-control anchors are before Native flow starts at 1697580000. Part 2 converted their times to negative array indices, which NumPy wrapped to the session's end; the expiry guard then used zero because the indices were negative. This is a source-alignment implementation error, not a market counterexample.

Preserved before/after evidence locally: `20231018-outside-flow-control-anchors.csv` (all 13); `20231018-negative-index-diagnostic.csv.gz` (all 289 incorrectly wrapped transitions, including the 26 nonzero residuals, explicitly labeled superseded). Their valid book paths and matching strata remain unchanged. Flow-sign and life/decay measurements now carry outside_native_flow_coverage/undefined; no control is silently replaced. Part 1A already represented these controls' out-of-range completed-group ratio as missing.

Only affected October 18 operator outputs are recomputed via `part2.py 20231018 --operators-only`, followed by cross-day charts. Verification now recomputes every stored recurrence residual from pinned source operands, checks its count against operator-summary, and asserts `source_second = anchor_second + relative_second`; it no longer assumes a proposed relation must have zero residual. This prevents the negative-index alias independently of the scientific outcome. The parent review independently found the same mismatched expiry coordinates.

## Part 2 completed

Verified all four days after the concrete fixes. `verify_all.py` reconciles 254,025/283,542/253,764/288,144 path rows, 2,223/2,496/2,220/2,589 matched path anchors, six detector operands and 741/832/740/863 exact live clocks. It verifies 342 panels per day; the 108 cross-day panels are also reconciled and were independently reviewed. Final valid life-transition rows are 90,556/103,968/86,559/107,181 (388,264 total). The 13 out-of-flow-coverage controls are retained as unavailable for flow-dependent forms; the 289 superseded wrapped transitions remain in the diagnostic artifact.

C/D/E results and all limitations are in FINDINGS.md, generated from actual output tables after distributions. At this checkpoint the full hierarchies and governing-form residuals had not yet been published. Largest-gap groups are representation-dependent; they are not a unique natural taxonomy. Lifetime plots explicitly label the analyst's three-opposite-second convention as SPECULATIVE. Shared cross-day y scales preserve raw units. No new dataset/chart was staged at that checkpoint.

Commands for final checks: `part2.py 20231018 --operators-only`, `crossday.py`, `verify_all.py`, `report.py`. The operator-only run completed output writes then encountered an empty hierarchy-list print error; its print guard was corrected without rerunning completed calculations. Subsequent verification and report generation succeeded.

Next: run Part 3 M1/M2 identically on all four archived dates, verify every event/disposition/figure denominator, finish workbook and publication inventory, update draft PR. Optional M3 remains unrun.

Report rendering correction: pandas Markdown coercion displayed integer date labels in scientific notation. The report helper now writes exact YYYY-MM-DD strings with numeric re-parsing disabled. Read-back confirms the four dates remain distinct in every generated comparison table. Part 3 is actively running October 18 followed by October 2/3/17; core computation is complete.

## Part 3 complete; recognition-boundary correction in progress

M1 and inclusive M2 completed on all four archived dates: 311,822/328,946/309,816/290,875 structural-event rows; 2,223/2,496/2,220/2,589 candidate/control paths; 31,122/34,944/31,080/36,246 first-event rows. Every event type and absent disposition is retained. Side-by-side M1/M2 figures add 540 reconciled series panels.

Parent review found that inclusive M2 counted 133/157/148/105 first-event rows at the recognition endpoint itself. This does not establish a pre-recognition footprint. The inclusive originals are preserved with `inclusive-legacy-` filenames. Primary M2 now uses [birth, recognition) with exact integer candidate recognition clocks and exact paired integer durations for controls; all first events, quantities and cross-side orderings are recalculated together. `footprint-endpoint-audit.csv` retains exact inclusive/strict quantities and endpoint-only dispositions. Only M2 is recomputed via `--footprints-only`; M1 raw scans and A-D remain unchanged. All raw intervals and absent paths stay in the denominator.

The parent is independently analyzing the common recognition-delay term in the visually similar sorted M1 distributions. `clock_decomposition.py` and `clock-decomposition-*` names are reserved for that work; this pass does not duplicate it.

## Verified input repository integration

The user supplied `DavisAI1974/markets-data`, cloned by the parent at `E:/markets-data`, commit `968fa11324f66b70cd318140c51bf19e23f9ee4e`. New processes explicitly set `MARKETS_DATA_DIR=E:/markets-data`. The additive loader checks the original-path to markets_data_path mapping, declared SHA256, optional declared byte size, and byte equality against the pinned research cache before accepting an external input. Missing or null-hash entries retain the pinned revision/cache fallback. Changed hashes or populations raise an error. Existing computed caches are not restarted for routing.

`verify_data_inputs.py` verifies 25 hashed entries, labels one null-hash entry unverified and three absent external archive references missing, and accepts nine byte-identical inputs already used by this pass. Several manifest byte-size fields are null; these are not interpreted as zero or as a mismatch when their hashes agree. Negative checks cover altered population, tampered input, null hash and absent mapping. Local `input-routing-receipt.json` records the repo commit, manifest hash, individual statuses and exact matching pinned revisions. No modifications were made to markets-data or Ccode's setup. The repository was used for inputs at this checkpoint; the user now explicitly requires outputs there too. No AWS/S3 is used.

Strict M2 verification completed on all four dates. Present event-type rows across candidates and controls are 24,496/26,301/24,443/28,147. Endpoint-only first events are 133/157/148/105, occurring in 84/94/75/63 candidate paths; controls have none at their exact paired endpoint. Independent parent raw-stream checks give 739/741, 824/832, 731/740 and 859/863 candidate paths with any strict pre-recognition event. Every first clock is verified against its completed group and strict integer endpoint; quantities reconcile as strict plus endpoint equals inclusive. The report preserves all missing-event combinations, which are observations rather than rejected candidates.

`verify_all.py` still reconciles all four archived populations, six operands, exact live clocks, path coordinates, control strata and source-aligned life recurrence. Each date has 504 series-panel reconciliation rows, plus 108 core cross-day and 540 moonshot cross-day rows (2,664 total). A render-only title-padding correction resolves the observed overlap at the top of the all-footprint figures without recomputing M1/M2. Workbook columns were widened after visual inspection showed clipping. The exporter reports a nonzero process status after its explicit successful save; cell-level XLSX read-back is therefore checked independently.

User priority changed to three four-day shape overlays. The parent owns `shape_overlays.py` and `shape-overlay-*`; this pass does not stage that script until the parent confirms it is checked. The separate timing decomposition is deferred.

The parent completed, visually inspected and delivered exactly three requested SAME four-day overlay renders, and authorized inclusion of `shape_overlays.py`. Each plot preserves original sorted ranks and raw seconds, with 1,695 input rows, 1,693 points and two unavailable clocks. All three have source hashes and reconciliation tables locally. Including these figures brings the local total to 215 PNGs and 2,676 panel/series reconciliation rows. The separate clock decomposition is deferred, not completed or inferred from visual resemblance.

## Completed research and checked deliverables

A/B/C/D/E and M1/M2 are complete on all four archived dates. Optional M3 was not run. The parent then completed the shape follow-up and exact clock decomposition after the user's overlay review. `clock_decomposition.py` retains 9,534 birth-definition rows: 9,528 exact integer identities and six unavailable live endpoints. Twelve full-distribution overlays and 48 series reconciliations separate event waiting time from the shared recognition delay. FINDINGS.md contains measured counts/Pearson pairings and a separately labeled SPECULATIVE interpretation; no independent mechanism is inferred from sorted resemblance. Both parent-authored scripts were checked and authorized for this code-only checkpoint.

Final figure verification: 227 PNGs, 2,724 panel/series rows, no unreconciled or missing figures. Final XLSX read-back: 18 sheets, 18,942 source rows and 25,432 exact text clocks; every exported source cell agrees with workbook-input.json. Workbook previews were visually inspected and long labels widened. The export omitted optional worksheet dimension metadata; verification counts actual XML-backed rows rather than assuming max_row exists. The 18-sheet workbook contains core and strict M2 review tables; the later shape/clock follow-ups remain fully represented in their local CSV and chart artifacts.

`verify_data_inputs.py`, `verify_moonshots.py`, `verify_all.py`, `verify_figures.py` and `verify_workbook.py` completed. All Python scripts compile and the code/Markdown diff has no whitespace errors. Current local file hashes, measured byte sizes and all 21 present pinned source blobs are inventoried by `inventory_local.py`; PENDING_PUBLICATION.md references that exact local manifest. At this checkpoint only scripts and Markdown had been published. The current destination for generated datasets, charts, workbooks and receipts is markets-data. PR #15 remains draft and unmerged.

## Additive shape-form follow-up: preregistered descriptions

Scope: the three SAME overlays, all four original archived dates including October 18. Existing A-E/M1/M2 results and populations remain unchanged. Parent owns shape_tail_audit.py and shape-tail-*; this pass owns shape_forms* and does not duplicate the parent's identity audit.

Soft predictions recorded before fitting: (SPECULATIVE) the negative signed-time portions may admit different compact descriptions for quote relocation, touch-size changes and aggressor-run starts; their apparent similarity may vary when a day's parameters are frozen and evaluated on another date. A displaced quote curve may resemble an aggressor-run curve over some original ranks while disagreeing at others. Every contradiction remains a measured residual; no winning model or acceptance threshold is defined.

Sections are full curve, negative, exact zero and positive recognition-minus-event seconds. Negative means the first structural event is AFTER recognition, not an earlier chronological dipole. Ranks remain the original zero-based sorted-observation ranks; no within-section rank reset, rescaling, warping, smoothing or averaged curve is introduced. Every adjacent rank gap and change in that gap is retained as a possible descriptive marker, without a preset jump threshold.

Candidate forms, before fitting: line a+b*r; logarithm a+b*log(r+c); shifted reciprocal a+b/(r+c); vertically shifted exponential a+b*exp(-r/tau). For the last three, c or tau is selected from the declared rank-unit grid 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024. Each grid point fits a,b by minimum sum of absolute residuals (linear programming); the grid point with smallest total absolute error is retained, ties use grid order. This is a finite fitting convention, not an event threshold or a natural constant. Boundary choices and underidentified/constant basis cases are retained. Fewer than two distinct original ranks yields an explicit unavailable fit, not a substitute zero curve. No mean error, R-squared winner, or sorted-curve Pearson mechanism claim is used.

Each fit is frozen and applied to every target day at that target's original ranks and same signed-time section. Ranks outside the source section's observed rank interval are labeled out_of_source_rank_domain; their mathematical predictions and residuals remain recorded and visibly distinguished. Quote-to-aggressor comparisons use every source/target day pairing, not only a selected similar curve. Full per-point CSVs, all fitting parameters, all residuals and denominator reconciliations will precede interpretation. Artifacts had not yet been published at this checkpoint; current output destination is markets-data. PR15 remains draft/unmerged.

Environment linkage uses the already-extracted structural events and archived path/matching/M2 tables; no new raw-event extraction or 13-external-point join is introduced. Each original SAME candidate-definition row retains candidate/control1/control2 timing, exact paired endpoint, actual spread/activity strata, quote change and existing strict M2 action counts/quantities. Missing finalization-only control paths remain explicit. The 13-external-point inventory belongs to a different 749-family-start population and has not been substituted into this research.

Marker convention before the marker-only calculation: exact signed-section boundaries, plus every interior local maximum/minimum of adjacent rank gaps (not smaller/larger than either neighbor and strictly different from at least one). These are mathematical features of a sorted distribution, not chronological event transitions. No jump-size cutoff or marker selection threshold is fitted; all original points and every neighbor-undefined case remain in the marker table.

## Shape-form and paired-environment checkpoint complete

The SAME follow-up applies identical code to October 2/3/17/18. All 5,085 birth-definition rows remain; 5,079 have a live signed-time value. Negative-section populations are quote 44/88/39/43, touch-size 6/7/7/9 and aggressor-run 107/123/102/112. The full, negative, zero and positive sections retain original ranks, and all adjacent gaps/gap changes and local extrema remain available. Exact-zero sections are constant-response descriptions, not identified shift mechanisms.

There are 192 fitted descriptions, all 1,920 grid attempts, and 271,040 model-target residual rows. Those rows include 160 unavailable-clock comparisons and 22,664 out-of-source-rank-domain extrapolations. No model winner or acceptance cutoff is declared. Every frozen source-day fit is applied to the other dates; all quote-to-run and quote-to-touch transfers remain, with each residual plotted and domain explicitly colored. Figure-only refresh uses common original-unit axes within comparable rows/matrices, after visual review found independently autoscaled panels obscured direct comparison. Calculations and fits were not rerun for this formatting change.

The environment attachment retains 15,255 candidate/control/event rows and 10,170 paired timing contrasts. It joins existing raw-derived event clocks, independently audited spread/activity strata, quote changes and strict M2 action counts/quantities. Verification independently checks exact clock subtraction, first-subsequent-event minimality, strata equality, candidate equality to the original overlays, gap arithmetic/local markers, fitted-grid objective selection, all per-point predictions/residuals and domain labels. No 13-external-point data was joined or excluded; no family-start population was substituted.

Shape follow-up artifacts: 110 local PNGs and 1,904 reconciled panel/series rows, including three compact negative-section overlays for phone review. The overall local set now has 337 PNGs and 4,628 reconciliation rows, with none missing/unreconciled. Source observations, model parameters, all residuals, matched controls and exceptions precede the separately labeled SPECULATIVE interpretation in the appended FINDINGS section. Earlier findings were preserved. The existing 18-sheet workbook remains the completed core review workbook; new shape tables are local CSVs. All scripts compile. Parent's separate shape-tail audit remains its own work; its files are not staged by this pass without authorization.

The local publication inventory has been refreshed with exact SHA256/byte sizes. Only shape_forms scripts, FINDINGS.md, PROGRESS.md and PENDING_PUBLICATION.md are staged for this checkpoint. Artifacts had not yet been published at this checkpoint; publish them to markets-data. No AWS/S3, merge or ready-for-review transition.


## GitHub publication and evidence reconciliation, 2026-11-08

The user removed the local-only rule. Corrected active instructions, persistent memory, historical references and three generators that could recreate it. Published 593 native-dipole artifacts (361,592,154 bytes) to markets-data at 0487d83b1ddb1abe5e4cfae12e8b88797801f428. Every artifact was checked against source hashes, committed bytes and a fresh independent remote fetch. No research calculations were rerun. PUBLICATION.md records scope and remaining broader migration. Existing input paths and other sessions' changes were preserved.

Read Desktop's new 9622d038f lean source and saved outputs, inspected its figure, and appended agreement/difference/unresolved evidence to FINDINGS.md. Recorded the user's clarification about averaging roughly 2,000 recurring historical shapes. Exact historical generators and individual table remain unresolved. The new source reveals defined-window denominators, 200 lean-control draws versus 500 midpoint draws, and the k20-to-k21 transition. Paper readiness remains unverified; retained hypotheses are preserved and no orders were submitted. PR15 remains draft/unmerged.
