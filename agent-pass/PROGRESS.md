# Native dipole research pass progress

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

Effective immediately, no new data, CSV/XLSX, extracted inputs, charts or bulk research outputs will be staged, committed or pushed to Markets. New code, Markdown and provenance references remain in scope. Generated artifacts stay local pending the user's markets-data repository and S3 destinations. No duplicate destination will be created. Existing published history will not be rewritten.

Already published before the change:
- `a4064816d`: Part 1A, `agent-pass/tables/20231018-*` (candidate operands, path members, paths.csv.gz, path dispositions, cases, case raw records, figure reconciliation); `agent-pass/figures/20231018-*` (36 figures); `agent-pass/research-tables.xlsx`; receipt and source manifest JSON.
- `50e04fce5`: Part 1B, `agent-pass/tables/20231018-*` detector comparisons, missed/added lists, detected births, per-second dispositions, lag rows and detector figure reconciliation; `agent-pass/figures/20231018-lag-distributions.png`; updated workbook and source manifest.

Both pushes succeeded with GitHub's repository-size warning. The index and unpublished commit range were inspected on receipt of the policy; the index is empty and no unpublished commit exists. Current generated-data changes will remain unstaged. The still-running October replication writes exclusively under agent-pass/ and will not publish artifacts. Inventory will use only local file/blob sizes, never missing-as-zero. Pending destination coordinates and immutable manifest will be linked when supplied.

## Storage plan correction

Latest user correction supersedes the prior S3 plan: AWS/S3 cannot be used now. Ccode owns creation of a three-tier repository layout. Do not create a competing layout or assume tier names. Generated artifacts remain local, with no new data committed to Markets. Code/documentation checkpoints continue. Actual Ccode destinations and immutable provenance/hash conventions will be adopted only when supplied. The earlier already-published artifacts remain disclosed above; published history is unchanged.

## Part 2 running checkpoint

All four A/B replications have completed once. Archived populations are 741/833/741/863; live recognitions 741/832/740/863. Native action-time reconstruction recovers every birth and nominal time; the two finalization-only records now take their actual recorded nominal availability from the operand object, never a substitute live group. Completed-group missed/added counts are 5/5, 5/5, 11/10 and 21/24. All six operand comparisons and live-clock checks are being checked across days.

C/D first computations also ran on all four dates. Each path representation is unscaled and keeps its individual time coordinates. Pairwise distances, every single-linkage merge, largest-gap membership and missing-coordinate patterns are saved locally. The largest-gap partition is explicitly a descriptive convention, not proof of one natural cluster count. Operational lifetime ends at the third consecutive opposite-sign second, or is right-censored at tape end. Undefined anchor flow has no lifetime; it is not a zero-second event. Five proposed relations plus the signed-net rolling recurrence have every candidate/control residual retained.

A final rendering/numerical-precision refresh is running before the Part 2 commit: full PNGs now allocate enough vertical pixels to every candidate heat-strip row; round-trip CSV parsing preserves written floating operands; undefined control lifetimes are blank instead of zero. Commands: for each archived date, `part1a.py`, `part2.py`, then `crossday.py`. The original calculation was not duplicated while active; this refresh follows its completion and addresses the observed rendering/missing-value issues. No new generated artifact is staged. Part 3 code is prepared but will run after Part 2 checks/checkpoint.

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

C/D/E results and all limitations are in FINDINGS.md, generated from actual output tables after distributions. Every full hierarchy and governing-form residual remains local. Largest-gap groups are representation-dependent; they are not a unique natural taxonomy. Lifetime plots explicitly label the analyst's three-opposite-second convention as SPECULATIVE. Shared cross-day y scales preserve raw units. No new dataset/chart is staged.

Commands for final checks: `part2.py 20231018 --operators-only`, `crossday.py`, `verify_all.py`, `report.py`. The operator-only run completed output writes then encountered an empty hierarchy-list print error; its print guard was corrected without rerunning completed calculations. Subsequent verification and report generation succeeded.

Next: run Part 3 M1/M2 identically on all four archived dates, verify every event/disposition/figure denominator, finish workbook and publication inventory, update draft PR. Optional M3 remains unrun.

Report rendering correction: pandas Markdown coercion displayed integer date labels in scientific notation. The report helper now writes exact YYYY-MM-DD strings with numeric re-parsing disabled. Read-back confirms the four dates remain distinct in every generated comparison table. Part 3 is actively running October 18 followed by October 2/3/17; core computation is complete.
