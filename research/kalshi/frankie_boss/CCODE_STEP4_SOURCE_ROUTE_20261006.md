# CCode step #4: candidates, scientific double-checks and survivor connections (2026-10-06)

Branch `ccr-5fce7de3-xa4hfg`, cut from checkpoint `c75a805a` of `chatgpt/frankie-30day-aws-workflow-20261006` (its tip at
the time of fetching; nothing newer was on it). SOURCE-BUILT / RUNTIME-UNVERIFIED: every statement comes from reading
producers, readers and callers in this checkout. No search, teacher, ROOT, exchange, E2E, install, dispatch or AWS
action ran. Checks performed: `py_compile` of the two Python files, `bash -n` of the launcher, `git diff --check`,
module import, and a shape exercise of the projection on one hand-built row in the scratchpad (not market data, not
committed, not a test of the scientific calculation). The codebase-memory MCP executable is absent here; nothing is
attributed to it.

Files CCode edits (ownership from `HANDOFF_20261006_CCODE_STEP4.md`): `deploy/aws/box/frankie_box_scientific_teacher.py`,
`deploy/aws/box/frankie_box_scientific_teacher.sh`, the new narrow adapter `deploy/aws/box/frankie_box_candidate_claims.py`,
and this report. No other file was changed. The preserved draft `drafts/SEARCH_SURFACE_AND_CONFIRMATION_NOT_APPLIED_20261006.patch`
stays unapplied; no freeze/holdout/evaluation behaviour was implemented; no bedrock producer was activated.

## 1. The map: producer -> legal claim/projection -> real calculation -> scoped result -> acceptance/survivor -> consumer

Status words: **called** = implemented and reached by an active caller on the experiment path; **uncalled** = built, no
caller reaches it; **absent** = no implementation found anywhere in the repository; all of it **runtime-unverified**.

| # | producer (what it emits) | legal claim / projection | real calculation | scoped result | acceptance / survivor treatment | knowledge / teacher consumer | status |
|---|---|---|---|---|---|---|---|
| A | the search `_cell_job` -> `couple` (`frankie_box_experiment_search.py`): one row per x, y, transform pair, cell at the best lag with the circular-shift chance check | `Run.search_knowledge` (`frankie_box_experiment.py` 1645-1672): `FRANKIE_SEARCH_FINDINGS_V1` = every `beyond_chance` row individually with part/row sha256, written `knowledge-findings.json` beside the MANIFEST | none beyond the search itself (the row IS the discovery evidence) | per row: counts, lag, cell, transforms, chance check, on one day | **absent** (the file's own `status` says "scientific double-checks and survivor treatment occur in their code stages"; no stage did either) | `Run.brain_stage(day,'search',[MANIFEST, findings])` -> brain `<day>-search` (findings inline whole, `inline_limit=len(raw)`) -> `lane_state.learner_knowledge` -> (i) classroom `stage_knowledge_reproduction` (`frankie_box_classroom_code.py` 623): rows with `x`/`y` are matched to today's Dipole pair review and marked `today_pair_measured`, explicitly `full_claim_tested=False`; (ii) `teach_accumulated.take` lists them "not a completed native scientific lesson; no claims synthesized"; (iii) exchange `accumulated_lessons.take` lists them "not a scientific lesson result consumed by this exchange" | producer **called**; scientific check **absent** before this step; after this step **uncalled** (section 3) |
| B | Frankie's classroom: `dipole_novel_findings` (ledgers.json) and the external projection `external-novel-findings.json` | `frankie_claims` (`frankie_box_scientific_teacher.py`): series from `evidence_refs`, direction from the premise's step counts, no lag, no cells; external IDs namespaced | `test` on every finished discovery search (`SEARCHES`): counts per matched pair, per day, both orientations; `row_scope_reasons` marks rows outside the claim's transforms/lag/cells/condition `counts_only` | `FRANKIE_LESSONS_V1` under `experiment-teacher/frankie/<day>-frankie.json`; per claim `tests`, `counts`, `days_tested`, `disposition` (orientation), `challenge`, `untested`, `cannot_test_yet` | none (disposition word only, R14) | `publish_lessons` -> `brain.write_lessons_entry` `<day>-lessons`; read by `learner_knowledge` (classroom, exchange, school), `teach_accumulated`, exchange `accumulated_lessons`/`claims_of`, `frankie_box_school_knowledge` section `scientific_teacher` | **called**: `Run.lessons` (batch, non-queued arm days) and `frankie_box_frankie_queue.frankie_lessons` (class worker) |
| C | Jev's `JEV_CLAIMS_V1` | `jev_claims` | `test` | `JEV_LESSONS_V1`; uploaded to Jev's brain through MAP_URL; `brain.write_stage_entry(day,'jev-tested')` | none | `<day>-jev-tested` stage entry; accumulated retests use the ordinary lessons entry | reader **called** by `Run.lessons` when an entry carries `jev_stamp`; `Run.jev` itself records `waiting` (no CPU transport; Pods retired), so no claim file is produced on this path |
| D | the committed historical catalog `HISTORICAL_CLAIMS_V1` | `historical_claims` (direction, lag, cells, condition, transforms carried) | `test` | `HISTORICAL_LESSONS_V1` under `historical/<days>-<sha12>.json` | none | `publish_lessons` into each tested day's `<day>-lessons` | **called** by `Run.lessons` when `plan.historical_claims` |
| E | completed lessons of B/C/D (their `claim_inputs` projection) available in the brain/school | `frankie_box_teacher_knowledge.teach_accumulated`: `learner_knowledge(day,'exchange')` + `learner_school`; `exchange.claims_of` recovers the exact claims; identity key = digest(author, claims_sha256, claim) | `ST.test` on the owner's own complete search parts (hashes checked against the MANIFEST) | deterministic result files `scientific-knowledge/results/<digest>.json`, `knowledge_retest` identity, original author/day/scopes kept | an exact claim already tested on this manifest is **reused, not counted again** | `publish_lessons` -> `<day>-lessons`; the exchange seats then read them in the same stage | **called**: `frankie_box_experiment_exchange.main` (classroom-arm days) and `Run.accumulated_lessons` via the CLI accumulated mode (non-classroom days, `_finish_day`) |
| F | the exchange's teachers' findings `FRANKIE_TEACHERS_FINDING_V1` (`science_turn`): a search row (x, y, lag, cell, transforms) the BOSS teacher's rows also measured one way; `status='HYPOTHESIS'`, `promotion` text = equal single-occurrence treatment after double-checks | none (they live inside `exchange.json` / `exchange-frankie.json`) | none | scope = pair, cell, lag, x/y transforms, teacher axis, counts of both instruments | **absent** ("this exchange does not complete survivor promotion") | brain `<day>-exchange` -> classroom `school_reproduction` (`frankie_box_classroom_code.py` 600-612): `_recognize_pattern` on `joint_way` against today's teacher-row steps only, `full_claim_tested=False` | producer **called**; scientific check **absent**. Their search half is the same row as A (same day, same evidence); testing them as a second claim would use identical evidence twice, so they are NOT projected (section 5, decision 4) |
| G | survivor / acceptance | consumed as `plan.frozen_survivors` -> `FROZEN_SURVIVORS` -> `--frozen-survivors` (search runs only the listed pairs on a `confirmation` day); `frankie_box_pod_root`, `frankie_box_day_facts`, `frankie_box_jev_relay.sh SURVIVORS`; brain stages `survivors` and `confirmation` are in `write_stage_entry`'s allowed set | none | none | the list itself | no writer anywhere: **absent by design** (step #5 discussion); the draft patch's frozen-lag confirmation (`couple(frozen_lag=...)`, `double_check` dot products) is unapplied | consumers **called** (refuse without the list); producer **absent** |
| H | nonlinear / multivariable discovery | `odcore/symbolic.py` (PySR): callers are `scripts/od_pysr_discover.py` and `tests/test_symbolic_anchor.py` only; not on the experiment path. The nonlinear content on the path is the search's transform roster (`frankie_box_experiment_transforms.py`: run length, magnitude class, level crossing, acceleration) applied pairwise | none | none on the path | none | none | none | **built_not_called** (symbolic); multivariable fitting on the path **absent**; a mathematical/compute decision for Greg and Codex, not mine |
| I | classroom recognition (`_recognize_pattern`, `stage_knowledge_reproduction`, `school_reproduction`, external `stage_knowledge_reproduction` reuse) | prior findings matched to today's pair review | the teacher-row step predicate only | `pattern_again` / `relation_differs` / `today_pair_measured` ... each `independent_scientific_verification=False` | none | the classroom's own ledgers/questions | **called**; explicitly not a scientific test |

Per-cell, per-day, never pooled is preserved throughout: `test` keeps every row as its own `tests[]` entry and the
disposition word is orientation (R14). The settle-window/leakage gates belong to the search, unchanged.

## 2. Actual callers of the scientific teacher (unchanged by this step)

- `frankie_box_scientific_teacher.sh` <- `Run.lessons` (`frankie_box_experiment.py` 1709-1754): one child per
  historical / jev / frankie call, `SEARCHES` = every finished discovery-day search of the run; waits when a searched day
  is remote (`remote_root`), the explicit cross-owner batch gap.
- `frankie_box_scientific_teacher.sh` <- `frankie_box_frankie_queue.frankie_lessons` (class worker, 518-558).
- `frankie_box_scientific_teacher.sh` accumulated mode <- `Run.accumulated_lessons` (1674-1707) <- `_finish_day`
  (non-classroom days) and `Run.start` lessons loop.
- `ST.test` / `ST.load_searches` / `ST.publish_lessons` <- `frankie_box_teacher_knowledge.teach_accumulated` <-
  `frankie_box_experiment_exchange.main` and the accumulated CLI mode.
- `ST.publish_lessons` <- `Run.lessons` and `frankie_lessons` on reused files; `ST.frankie_claims` <- `Run.lessons_written`
  (claim-set hash check) and `exchange.claims_of` (legacy lessons without `claim_inputs`).
- `ST.jev_claims` / `ST.historical_claims` <- `exchange.claims_of` (legacy fallback).
- The Linux lane (`pod_root/pod_agent.py` 745-757) transports `days/<day>/*.json` receipts, the teacher receipt and the
  batch `lessons` receipt; `Run.remote_stage` on main returns `waiting` until the owner publishes a completed receipt.

## 3. What this step changed (additive; every existing caller and byte-identity preserved)

1. **`deploy/aws/box/frankie_box_candidate_claims.py` (new, 93 lines).** `candidate_claims(path)` and
   `candidate_claims_doc(doc, claims_sha256=, source=)` project a `FRANKIE_SEARCH_FINDINGS_V1` into the claim shape
   `test` already consumes: `id = search:<day>:<part sha12>:<row>`, `series = [x, y]` with `series_exact=True`,
   `direction` = the way the row's counts pointed, `lag = best_lag` in the row's x -> y orientation, `cells = ['<col>=<value>'
   or 'whole-day']` (the exact labels `row_scope_reasons` builds), `x_transform`/`y_transform`, `condition=None`,
   `day_made`, `origin` = day, search manifest sha256, part, part sha256, row ordinal, row sha256, and `source_claim` =
   the whole row (all counts retained). `claims_sha256` binds the findings file bytes (or the brain source's recorded
   sha256 for the inline variant). It refuses a finding without part/row provenance or one that is not beyond its own
   chance check. No threshold, formula, pooling, rarity gate or acceptance rule.
2. **`test`:** (a) a claim with `series_exact` is matched by exact name only; the fuzzy `match` (containment for names of
   4+ characters, e.g. `frames.mid` -> `frames.mid_delta`, `dipole.E` -> `dipole.extension_count_log`) still serves
   free-text claims unchanged. (b) A claim with `origin` has the rows of its origin day listed under `origin_evidence`
   with full counts, `discovery_row` = whether the row equals the retained candidate row, and `mark='origin_evidence'`;
   they are never `held`/`shown_otherwise`/`unresolved`/`counts_only` and never enter `counts`, `days_tested` or the
   disposition. Two `untested` lines name an origin day absent from the searches given and the no-other-day case,
   stating explicitly that acceptance of a checked single occurrence is the pending step #5 decision. Results carry
   `origin`, `origin_evidence`, `origin_rule`. Rows of other days, scope reasons, marks, dispositions, challenges and
   every count are computed exactly as before.
3. **`write` / `publish_lessons`:** author `search` -> `SEARCH_CANDIDATE_LESSONS_V1` under `experiment-teacher/search/
   <day>-candidates-<manifest sha12>.json`, with `source_manifest_sha256`, `origin_rule` and
   `publication='retained only'`. `write` does NOT call `publish_lessons` for this author and logs why;
   `publish_lessons` refuses the author with the exact reason: `frankie_box_brain.write_lessons_entry` admits
   `frankie`/`historical`/`jev` only (Codex-owned). Nothing is marked published that is not.
4. **CLI / launcher:** `--search-findings PATH` (`SEARCH_FINDINGS` in the `.sh`, constrained to
   `/opt/frankie-box/work/experiment-search/*/knowledge-findings.json`), combinable with the other claim flags, refused in
   accumulated mode, and refused when every `--search` given is the candidates' own day (origin evidence is not a test).

Status of the new route: **built, uncalled, unpublished.** No orchestrator stage passes `SEARCH_FINDINGS`; no brain
entry can hold the result. It is not complete.

## 4. Exact edits outside my ownership (for Codex), in the order that makes the route live

1. **`frankie_box_brain.write_lessons_entry`**: add `'search': 'SEARCH_CANDIDATE_LESSONS_V1'` to `schemas`; for author
   `search` take `days` from `searches` (like `historical`), so results publish into each TESTED day's `<day>-lessons`
   (the origin day already holds the candidate in `<day>-search`). Then `ST.publish_lessons` can drop its `search`
   refusal and the `write` skip (mine; I will do that once the writer exists).
2. **`frankie_box_teacher_knowledge.py`**: `LESSONS['SEARCH_CANDIDATE_LESSONS_V1'] = 'search'`; in `teach_accumulated.take`,
   when an inline stage source has `schema == 'FRANKIE_SEARCH_FINDINGS_V1'`, call
   `frankie_box_candidate_claims.candidate_claims_doc(content, claims_sha256=member['sha256'], source=member['path'])`
   and append its claims as a document (author `search`) EXCEPT claims whose `origin.day == day` (this owner's own
   candidates: origin evidence, listed, never tested here). Everything downstream already fits: `claim_key` digests the
   claim, `already_tested` reuses an exact claim tested on the same manifest, result files are deterministic,
   `expected`'s `schema`/`author` come from the lesson dict (use `schema='SEARCH_CANDIDATE_LESSONS_V1'`, `stamp`,
   `claims_source` from the projection). This is the owner-local route: each lane tests every other day's candidates on
   its own complete search parts, giant files never move, and the result reaches the exchange seats in the same stage.
3. **`frankie_box_experiment_exchange.py`**: `LESSONS['SEARCH_CANDIDATE_LESSONS_V1'] = 'search'` and an `AUTHOR_LABEL['search']`
   ("the search's own candidate: a count beyond its chance check on one day, a claim, never truth: R11"), so completed
   candidate lessons get BOSS/scientific/Frankie turns like the others. `claims_of` already handles `claim_inputs`.
4. **`frankie_box_experiment.Run.lessons` / `lessons_written`** (optional standalone route): a call
   `('candidates-%s' % day, dict(SEARCH_FINDINGS='<search target>/knowledge-findings.json'))` per searched day with
   `SEARCHES` = the OTHER searched days; `lessons_written` for kind `candidates` -> `LESSONS_ROOT/'search'/
   '<day>-candidates-<manifest sha12>.json'`. The accumulated route (2) is preferred: it is owner-local and does not
   wait on remote searches.
5. **`frankie_box_school_knowledge.py`**: a `scientific_teacher` item for `SEARCH_CANDIDATE_LESSONS_V1` of the day
   (untested/cannot_test_yet subset), so the school carries the candidate tests like Frankie's lessons.

### The cross-owner batch contract (numbered gap #4/#8), specified, not implemented

Request (small, owner-local, from the lane that finished a search): `{run, day, search_manifest_sha256,
findings_sha256}` is already transported by the existing `<day>-search` brain entry and its lane snapshot; no new
message is needed. Each OWNER lane, at its next lessons boundary, tests every other day's candidates on its OWN search
(route 2 above) and publishes per-candidate results bound to `(input_sha256, claims_sha256, claim_inputs_sha256,
search_manifest_sha256)`. The batch receipt on main may only aggregate `{contributing_day, manifest_sha256, result file
sha256s}` per owner as they arrive; a result from one owner completes that owner's contribution only, never the batch,
never another day. `Run.lessons` keeps waiting on remote days for the historical/Jev/Frankie calls, as today; it must not
copy remote parts to run them centrally. Equal treatment: a candidate tested on zero other days keeps its origin
evidence and an explicit `untested` line; no occurrence minimum anywhere.

## 5. Remaining decisions, documented instead of chosen

1. **What makes a candidate's double-check "hold" (acceptance).** Existing alternatives in the repository: (a) `test`'s
   dispositions over the other days (`held`/`shown_otherwise` per row, R14 orientation); (b) the draft patch's frozen-lag
   independent dot-product `double_check` on the same axis (unapplied, step #5); (c) the exchange's second instrument
   (BOSS teacher rows measured the same way). None is wired as acceptance; `survivors`/`confirmation` brain stages have
   no writer. Greg's step #5 discussion decides; this step only makes candidates testable on independent days.
2. **Scale.** `test` keeps every row of every wanted pair of every day in memory; a day's candidate set can cover most
   pairs, so the candidate route may load most rows of every search given (`lag_profile` included). The owner-local route
   bounds this to one search per lane. Measure on the authorized E2E before widening.
3. **Author label** `search` versus `scientific_teacher`; and whether candidate lessons publish into the tested day's or
   also the origin day's `<day>-lessons` (I propose tested days only, as historical does).
4. **Teachers' findings (row F)** carry the same search row as the day's candidate plus the BOSS rows; projecting them
   as separate claims would test identical evidence twice. Proposal: cite them from the candidate result by identity
   (x, y, lag, cell, transforms, day) rather than test them again; they lack part/row hashes today.
5. **Nonlinear/multivariable discovery (row H)**: `odcore/symbolic.py` is off the path; the step-3 report's gaps 1-4
   (per-level FIFO/activity spooling, Dipole states as cells, `DState`, `info_dipole` on the signed flow) still bound what
   the candidates can be made of.
6. **Jev** (row C): the reader is complete; the producer waits on the CPU transport decision.

## 6. Boundaries kept

No freeze/holdout/evaluation behaviour, no draft applied, no bedrock, no AWS, no installs, no dispatch, no tests or
validator framework, no E2E claimed. Scientific formulas, claim selection, source-scope checks, the raw-Jev wall and
every existing caller's inputs and outputs are unchanged; the new behaviour is reached only by `series_exact`, `origin`,
author `search` or `--search-findings`, none of which any existing producer emits.

## 7. CCode tasks 1-3 of 2026-10-06 (the corrected assignment, CCODE_NEXT_SOURCE_TASKS_20261006.md)

Branch `ccode/dipole-collection-20261006` on top of Codex's `21df8f1`. SOURCE-BUILT: py_compile, whitespace check,
direct source tracing; no run, no test, no model, no research performed or judged by CCode.

### Task 1: historical reconsideration wired (frankie_box_scientific_teacher.py)

Traced: catalog (now the combined `DIPOLE_SHARED_CATALOG_20261006_COMBINED.json`, 1,538 sources) -> the committed
claims file (`HISTORICAL_CLAIMS_V1-9dc79ca359e9.json`: 82,372 candidates, 10 crosswalk claims, 82,365 not_testable)
-> `historical_claims()` read only `claims` and dropped the rest by reference in prose -> `test()` -> `write()` ->
`HISTORICAL_LESSONS_V1` -> the exchange (`load_lessons`, one item per RESULT, both seats; Codex's `research_rework`
of 3e0a6f0 per item) -> Frankie's reply. So both teachers saw exactly the 10 mapped claims and nothing of the 82,365
open statements; the "no crosswalk entry" label worked as a silent filter. The BOSS teacher never reads the claims file
itself; it meets historical claims only as exchange items, so the same filter applied to it.

Built, all in the owned module:
- `reconsideration(...)`: every historical claims document now carries `FRANKIE_HISTORICAL_RECONSIDERATION_V1`, bound to
  the claims file by sha256, with the four statuses counted: `stored_evidence_reassessed` (the mapped claims, read
  against stored search counts here; explicitly NOT a reproduction), `original_calculation_awaiting_teacher_reproduction`
  (pending_teacher_work, per mapped claim with its construction), `teacher_repair_or_reformulation` (pending, performed
  0; this file never marks it performed), `missing_inputs_or_unsupported_computation_open` (the not_testable count by
  open class: awaiting_teacher_binding 81,655; code_source_constructions 710; missing_inputs; unsupported_computation),
  plus `prior_labels` (each mapped claim's source evidence labels and the builder's own research_rework). `write()` puts
  it in the lessons file top level, so the exchange's both seats can read it without opening the 53 MB claims file.
- every historical result carries `research_rework` with the same four statuses for that claim, its construction, its
  prior labels and the rule that a label never closes reconsideration (R11, R13, R14).
Not built, on purpose: no heuristic that turns an unmapped statement into a testable claim. Putting a statement in
testable form is a crosswalk entry (series the search carries, a pairwise step relation), which is research work the
assignment forbids CCode; the crosswalk lives in Codex's builder. The 81,655 therefore stay explicitly pending, now
counted and visible in every historical lessons file instead of invisible.

Codex caller edits (both teachers):
1. `frankie_box_experiment.py` plan `historical_claims`: name the combined file
   `research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json` (the launcher's pattern admits it).
2. `frankie_box_experiment_exchange.py`: read `lessons['reconsideration']` once per historical lessons file and put
   its `statuses` into BOTH seats' turns (`boss_turn` and `science_turn`: a line each stating mapped N of candidates M,
   open by class, pending reproduction/repair counts), and into `research_rework` of every historical item as
   `collection=` so a seat's item never implies the mapped subset is the collection; keep HISTORICAL_REWORK next_test.
3. `frankie_box_experiment_teacher.py` (BOSS): no file input change is needed for the exchange route; if the BOSS
   teacher is to compute on historical claims outside the exchange, give it the same `--historical-claims` file and
   the same `reconsideration` carry (it reads only the directive today).
4. `frankie_box_teacher_knowledge.teach_accumulated` / `frankie_box_lane_state.learner_knowledge`: carry
   `reconsideration` through the accumulated-lessons selection unchanged (it is a top-level key of the lessons file).
5. Growing the crosswalk (the only binding mechanism): a declared-table edit in `frankie_box_historical_claims.CROSSWALK`
   per statement, Codex-owned; each new entry moves one statement from awaiting_teacher_binding to mapped, and nothing
   else changes the counts.

### Task 2: candidate reader and scientific reader defects

Reviewed `frankie_box_candidate_claims.py` (identity: claim id = day + part sha12 + row; origin carries part, part
sha256, row, row sha256; series exact; direction, lag and transforms are the row's own; cell label matches the reader's
labels) and `frankie_box_scientific_teacher.test` / `row_scope_reasons`. Verified defects, fixed with the existing
mathematics only:
1. REVERSED ORIENTATION COUNTED TWICE. The search writes every ordered pair (`_cell_job` partners), and for (y, x) the
   statistic is the (x, y) one read backwards: D_yx[k] = sum_t sy[t] sx[t+k] = D_xy[-k] (couple()). The reader read
   both rows and appended two verdicts, so every held/shown_otherwise/unresolved count was doubled and `tests` reported
   two tests of one measurement, at any lag including nonzero. Fix: `mirror_of()`; a reversed row whose forward row has
   the same cell, swapped transform pair, negated best lag and identical counts and chance check is listed under the
   result's `mirrored_rows` (mark `mirror`) and never counted; a reversed row with no forward counterpart (a survivor-
   restricted search, or a tied lag the tie-break resolved to the other sign) is read on its own as before, with the
   claim's transforms swapped and lag negated (`row_scope_reasons(reverse=True)`, unchanged and correct).
2. ORIGIN ROW IDENTITY BY FIELD VALUES ONLY. `discovery_row` was true when a row's field values equalled the candidate's
   `source_claim`; the part identity (origin `part_sha256`) was never compared with the given search's part pins. Fix:
   `load_searches` carries `part_pins`; `discovery_row` requires both field equality and the origin part sha256 among
   the given search's parts (`origin_part_in_search`); a mismatch is listed under `untested`.
3. (Codex's review of 046361e.) ORIGIN BOUND TO THE PART ONLY. `discovery_row` required the origin part sha256 to be
   among the search's part pins and the field values to match; the row was not bound to its exact part, ordinal and
   raw line. Fix: every row read from a part now carries `where` (part, the search's pinned part sha256, ordinal, the
   raw line's sha256, the same three values `Run.search_knowledge` records as part_sha256/row/row_sha256);
   `discovery_row` is true only when all three equal the candidate's origin; `fields_equal` and
   `origin_part_in_search` are reported beside it; a discovery row not found among the given search's rows is said
   under `untested`. Every test row and mirrored row names its `where` too.
4. (Codex's review of 046361e.) MIRROR SKIP BEFORE ORIGIN EVIDENCE. On the discovery day a reversed row that mirrored a
   forward row was dropped into `mirrored_rows` before the origin branch could list it. Fix: the origin-day branch runs
   first; a reversed origin-day row is listed as origin evidence with mark `origin_evidence_mirror` and its `mirror_of`,
   never counted, never dropped.
Reviewed and found correct: exact series matching (`series_exact`), transform scope in both orientations, cell scope
(`col=value` and whole-day labels), the lag window, the condition rule, the origin-day never-a-test rule, the source
counts travelling whole in `source_claim`. No acceptance or survivor rule chosen. `frankie_box_candidate_claims.py` is
unchanged: its projection was not the defect.

### Task 3: completed native evidence (result.json, sections 4.2/4.4, FINALIZE), interface review

Route: `frankie_box_experiment_native.selected_files` pins `receipt.json`, `result.json`, the three ledgers and the
gzip-json section products `bedrock_section_4_2` / `bedrock_section_4_4` from a completed, source-bound bedrock ROOT;
`read_columns` places GROUP_CLOSE ledger rows with exact emission provenance on the existing F_LAST axis (searched);
FINALIZE rows get the retained disposition `post_stream_knowledge_only`; `result`, `receipt`, the legacy observable
rows and both sections are listed as "completed calculation/section evidence; no whole-day summary backfill" and
become no series. So they reached the search inputs as pinned files and dispositions, and no teacher computation
consumed them. FIXED (Greg, 2026-10-06: "fix it so the correct place consuming them"): the correct consumer of post-
stream, whole-day completed knowledge is the teachers' exchange, not the group-close search axis. The scientific
teacher now reads each searched day's completed native evidence whole from the files the search pinned, bytes
verified (`completed_native_evidence`): the receipt's verdict and gates; result.json's section summaries whole and its
averaged companions labelled supplement-only (D37); section 4.2's exact first/last book of each day-segment-phase and
its declarations, companion rows labelled averages; section 4.4's matching rule and its STREAM_END rows, with its
GROUP_CLOSE offers cross-referenced to the already searched native.lifecycle.mirror.* series rather than duplicated;
and every FINALIZE row of the exact member and lifecycle ledgers, parsed only at the ordinals the search listed
post_stream_knowledge_only while the whole ledger is hashed against the search's pin. Written once per day to
`<work>/native/<day>-completed-native.json` (same bytes reuse, different bytes refuse) and carried in EVERY lessons file
as `completed_native_evidence.by_day[day]` (path, sha256, counts, receipt, matching rule) with `listed` for anything
absent, so a search without native evidence is listed, never an error. Codex: `frankie_box_experiment_exchange.py`
boss_turn and science_turn cite `lessons['completed_native_evidence']['by_day'][day]` (sha256-bound) in their
evidence_checks, and `teacher_knowledge.teach_accumulated` carries the key through; nothing else changes.
What each piece is for, and what still needs a definition:
- 4.4 (mirror lifecycle pairs, `native_mirror.MirrorMatcher`): its GROUP_CLOSE offers are already searched as
  native.lifecycle.mirror.* rows; its STREAM_END rows and matching rule are now consumed above. A per-group count of
  pair completions as a searchable series would need the semantic definition (which group close a completed pair
  belongs to, by its later leg's exact group) in the search's `build_series` (Codex, a mathematical decision).
- 4.2 (first/last book of each day-session, `BookRegimeCalculator`): two points per session, so the step series the
  coupling needs (m >= 2 steps, far shifts beyond the exclusion) does not exist on this axis; a consumer needs a
  definition of what step series a session summary is, which is a mathematical decision, not a connection; listed.
- `result.json` `averaged_companions` rows and section summaries: averages, which D37 keeps out of evidence; listed,
  never searched; no consumer should be built for them.
- FINALIZE rows: no group, no axis position (the module refuses a FINALIZE row that names a live group); they are
  post-stream knowledge, now read whole into the per-day completed-native file and carried in the lessons for both
  seats; never a search step.
Nothing here was invented or run; storage, hashing and inventories were not counted as coverage.

## 8. The expanded pre-#5 queue (CCODE_NEXT_SOURCE_TASKS top section), on `ccode/teacher-tasks-20261006b` from `6cf36b3`

**Current review qualification (2026-10-06 night ET):** the following slice descriptions
are the original return, not correction closure. Refetch found CCode `d3945e13`, a
documentation-only successor of already integrated `fea2e165`; no correction source
returned. `CCODE_NEXT_SOURCE_TASKS_20261006.md` owns the full A4/B1-B7/C1-C2/D1 queue.
In particular, the V1 price contract below incorrectly promises originating INPUT identity:
the producer stamps the group-closing index on earlier trades. Its row ordinal is within
the emitted group, not the originating INPUT. Do not implement its proposed exact price
join. Codex's exact structure join and provenance-channel exclusion are already built.
Historical bindings below are audit/capability wiring with open admission, recovery and
cost/profit-contamination defects, not safe runnable market-research reproduction.

### Slice A: discovery-day delivery and BOTH-seat arithmetic (parent `6cf36b3`)

Changed: `frankie_box_teacher_knowledge.py`, `frankie_box_experiment_exchange.py`, `frankie_box_scientific_teacher.py`.
- `teach_accumulated`: the blanket discovery-day exclusion is removed. Traced first: the frozen selection (`inputs.json`,
  identity = day + manifest witness + brain + this file's and the readers' sha256) is captured BEFORE the scheduling
  loop, so removing the skip changes no selection; a changed reader/producer sha256 already refuses an older
  `inputs.json` ("belongs to another search or reader"), so incompatible pending work cannot silently reuse the new
  semantics; a scheduled discovery-day candidate reaches the existing `ST.test` with this owner's complete,
  hash-checked search parts, whose origin path lists its rows (each bound by part sha256 + ordinal + raw-line sha256,
  `discovery_row` true only on the exact row, reversed rows marked `origin_evidence_mirror`) and counts none as a test.
  Result identity (`claim_inputs_sha256`) differs from a never-run earlier shape, so no retained result is overwritten.
- exchange: `count_margins(row)` factors the exact-integer checks and complements out of `shared_count_accounting`
  (its output unchanged); `origin_evidence_accounting(result, day, src)` applies the same margins to the reader's
  `origin_evidence` rows of the current day, keeps `where`, `discovery_row`, `mark`, `mirror_of` and the chance check,
  and says in every teaching line that an origin row is not a test, not an independent measurement, not another
  occurrence and not a confirmation. `boss_turn` takes `origin=` and states it beside the shared accounting (checks,
  reasoning, teaching_implications); `science_turn` extends `day_text` with the origin rows on the day and whether the
  exact discovery row was found, and returns `origin_on_day` in its sidecar; both seats' turn records carry
  `origin_accounting`; the lawful Frankie reply learns the origin lines plus the R06 sentence and its sidecar carries
  `origin_evidence` (rows by identity, listed, `counts_as_test` false); each item's `lessons` names
  `origin_rows_on_day`. Nothing enters `tests`, findings, joint confirmation, promotion or historical reproduction.
- reader: `MIRROR_FIELDS` now names `null_exclusion` and `beyond_chance` (both functions of m, L and the null counts,
  so a true mirror carries them equal); no acceptance rule chosen.
- digests: `teach_accumulated` identity binds its own file and ST/EX/CC/LS/BR; `accumulated_lessons` identity binds the
  exchange file and LS/BR/ST/K/SEARCH/DC; both change with these edits and refuse older pending inputs. Publication
  retry is unchanged (same-bytes reuse, different-bytes refuse).
Not done: `frankie_box_classroom_code.exchange_reply` is untouched (origin lines are added to the reply by the exchange).
Checks: `ast.parse` without project imports, `git diff --check`. No run.

### Slice A follow-ups 1-3 (parent `ef12b0eb` on Codex's `59cca0d4`; commit `9e456888`)

Changed: `frankie_box_experiment_exchange.py` only.
- (1) `science_turn(..., origin=)` takes the ONE computed `origin_evidence_accounting` object (the BOSS seat's) and consumes
  its teaching lines in its own `evidence_checks` (result unresolved), `reasoning`, `teaching_implications` and cites before
  `D.parse_teacher` / hashing: the same counts, explicitly not a second measurement; never in `compared`, findings,
  promotion or target masks. `day_text` names the origin rows with margins stated and those listed without arithmetic;
  sidecar `origin_accounting_consumed`. `exchange()` passes the object to both seats.
- (2) the origin prose carries the shared route's qualification verbatim in meaning: nonzero transformed-step margins at the
  retained circular shift, not PRESENT masks or known physical inactivity (zero may be stationary, missing or unclassified);
  `formulas` and `alignment` recorded per row; the formulas are `count_margins`, unchanged.
- (3) `origin['listed']` reasons are taught: a current-day origin row whose arithmetic cannot be performed keeps its source
  row and reason, is named as identified discovery evidence (exact row / mirror / fields-equal / same pair) or as not
  identifiable, and is never marked tested; the lines reach the BOSS turn, the scientific turn and the lawful Frankie reply.
Slice A is now complete on CCode's side pending Codex's integration review. Checks: `ast.parse`, `git diff --check`. No run.

### Slice B: faithful historical calculation bindings and the teachers' reproduction capability

Changed: `frankie_box_historical_claims.py` (tables + accessors; `build()` output unchanged except `builder_sha256`),
NEW `frankie_box_historical_reproduction.py` (the capability; never invoked), `frankie_box_scientific_teacher.py`,
`frankie_box_experiment_exchange.py`, `frankie_box_teacher_knowledge.py` (identity binds the two new readers).
The committed claims file `HISTORICAL_CLAIMS_V1-9dc79ca359e9.json` is byte-identical; the builder was not run.

Traced first (every pin computed from git history here, verified byte-equal to the handoff's; none recomputed on the box):

| binding | claims | original calculation (entry) | sources @ revision (catalog id) | inputs | recorded outputs | status |
|---|---|---|---|---|---|---|
| `crypto_trend_flip` | H01 H02 | `_info_dipole_trend_flip.py` main: `signed_flow_features` over the 30-min pre-entry window of 1-min bars per winner onset; confirm/diverge split; the aligned <= -0.2 gate; the 2-factor gate with `odcore.info_dipole.divergence` | `odcore/info_dipole.py` (review.091), `_info_dipole_trend_flip.py` (review.112), `_info_dipole_flow_detrend.py` (review.107, cited negative) @ `bb28b35e` | 6 `fingerprint_dataset/test_bars/*.json` + `fingerprint_dataset/onsets/winner_onsets.json` (1,560), all committed @ `bb28b35e` | 10 printed patterns (POOLED 1560 / 50 / 38 / +12; temporal +4 / +18; gate ~65 tol 1; per cell 100 / 84; 2-factor 317 / 64 / 58 / 52 / 49) + 2 prose (early 70 / late 62; "neutral") | defined |
| `crypto_harness` (DELETED 2026-10-07, Greg: not market-conditions work; no reference remains in code) | H01 H02 | `_info_dipole_harness.py` main: same timing trigger, champion OFI filter vs challenger `divergence()`, ZigZag theta 20 bps, OOS 40 percent | `_info_dipole_harness.py` (review.095), `_info_dipole_swing_backtest.py` (review.111), `odcore/info_dipole.py`, `_info_dipole_harness_results.json` (review.096) | `realbins/*_bins.json`: not in the repository at any revision | the results json, leaf by leaf (`config`, `per_venue`) | missing_inputs |
| `ng_leg_fingerprints` | H03 H04 H05 H09 H10 | `characterize_turns.py <days>` -> `month_characterize.characterize_day("NG", day, "s3")`: legs by `lag_join.scan_moves` (TRIG 0.015); per leg `dipole_pieces` (dip_imb_level), `depth_pieces` (imb_R, aligned_imb_R, book), `turn_pieces` (turn_far_thinning), `move_path` (dir, continuation) | `month_characterize.py`, `event_move_baseline.py`, `characterize_turns.py`, `lag_join.py`, `forward_curve.py`, `nws_temp_feed.py` @ `21df8f14` (three swept catalog ids; the rest pinned here), `odcore/info_dipole.py` @ `bb28b35e`, `renders/ng_refine_s95/fingerprints.json` @ `21df8f14` (NOT in the catalog: bound by path + revision + sha256), `ng_brain.json` @ `bb28b35e` | NG MBP-10 day tapes on S3 (`nymex_mbp10/`) + local regime caches: not in the repository | `fingerprints.json` per leg, per claim field set; ng_brain prose (1,537 legs / 87.6 percent AND the brain's own recount 2,459/3,697 = 0.665; book_contrarian confidence 0.5 / UNCLEAR; turn_far_thinning demotion "held legs ~half negative"), each declared not comparable by code | missing_inputs |
| `memory_a_retired` | H06 H07 H08 | Memory A exact native MBO closes (Oct 4 / Oct 5 2021) | the two catalog sources (positive knowledge doc, member-first receipt) @ `b4f364f0`, sha256 from the catalog (that revision is not in this clone); the recalculation script is in neither the catalog nor this repository's history | the A-memory ledger: not bound | preserved as evidence; not compared | not_bound: "Memory A retired by Greg 2026-10-06; original evidence preserved" |

Built:
- `frankie_box_historical_claims.REPRODUCTIONS` (the table above, every source with path, revision, sha256, role and catalog
  id where one exists; entry point with cwd/script/argv/produced files; inputs with where they live; recorded outputs typed
  `printed` / `json_file` / `prose`), `REFORMULATIONS` (per claim what a declared repair or reformulation NEEDS: H01 a
  derived `aligned_flow` series, a threshold state and a pre-entry window; H02 a windowed `|imbalance| falling` transform
  (none of `TRANSFORMS` is one); H03 the construction transfer roll20 vs Lee-Ready ~300 s, the |x| >= 0.15 state and a
  LEG/SIDE definition; H04/H05 a numeric flat-flow bar the source never states, an entry definition, and n vs 10 levels;
  H09/H10 a turn definition (the favourable peak within POST_S) and an entry-to-peak depth change; H06-H08 not_bound), the
  accessors `reproduction_of`, `reformulation_of`, `binding_tables_sha256`. `frankie_box_experiment_surface.state_masks`
  (sign states, built, unwired) and `frankie_box_experiment_transforms.TRANSFORMS` are named as the places; the decisions
  are Greg's (mathematical), none is taken.
- `frankie_box_historical_reproduction.py`: `stage` (git show at the pin, sha verified, into `<out>/tree/<path>`; on the box
  everything is listed, nothing staged), `plan` (`HISTORICAL_REPRODUCTION_PLAN_V1`, executable yes/no), `run` (refuses
  without the exact `AUTHORIZATION` literal or with missing inputs: `not_run` with the inputs named; never a stand-in),
  `compare` (printed regex fields with the recorded tolerance only where the record says "~"; produced json vs the pinned
  recorded file leaf by leaf over the declared fields; prose declared not comparable), `record`
  (`HISTORICAL_REPRODUCTION_V1`: performed_matched / performed_differs / not_run, pins, `record_sha256`; written once under
  `<work>/reproduction/`), `records_for` (hash-bound read: record sha holds AND pins equal the declared table's, else
  listed), `status_of`. Nothing calls it today.
- `frankie_box_scientific_teacher.py`: `historical_claims()` attaches `reproduction` and `reformulation` per claim (so they
  freeze into `claim_inputs`); `test()`'s `research_rework` READS the status from the hash-bound records under
  `REPRODUCTION_DIR` (`performed_matched` / `performed_differs` / `not_run`), else `pending_teacher_work`, or `not_bound`
  for H06-H08; it carries `reproduction_binding` (pins, missing inputs), `reproduction_records` (records + listed),
  `repair_or_reformulation` (`not_bound` / `pending_teacher_work`) and `reformulation_needs`; `reconsideration` counts
  bindings by status, records by status (and the listed ones), reformulation needs by status, and says the bindings cover
  the mapped claims only: every not_testable statement has none and stays open.
- `frankie_box_experiment_exchange.py`: the historical item's `rework` keeps a `performed_*` reproduction status when the
  reader reports a hash-bound record of that status (`reproduction_status_source` says so) and otherwise writes
  `not_established_by_this_exchange` as before; the untested line says which. Repair/reformulation stays not established.
- `teach_accumulated` identity binds `frankie_box_historical_claims` and `frankie_box_historical_reproduction` beside the
  other readers (older pending `inputs.json` refuse the new semantics; completed results keep theirs).
Not done, on purpose: no reproduction, repair or reformulation was run or judged; no condition, transform, window, turn
or entry definition was chosen; the not_testable 82,365 have no binding (a binding needs a crosswalk entry first).
Consequence to note: a future `frankie_box_historical_claims.py --out` run would produce a file differing from the committed
one only in `builder_sha256` and refuse to overwrite it ("move it aside first"); that is the builder's own guard, unchanged.
Checks: `ast.parse` of the five modules without project imports; the 10 recorded-output regexes compile (`re.compile` over the
string constants read by `ast`, no project import); `git diff --check`. No run, no test.

### Slice C: completed native evidence, its actual existing consumers, and the candidate-only accumulated route

Changed: `frankie_box_teacher_knowledge.py` only (the repair); the rest of this slice is the source trace below.

Every existing consumer of the completed native products (the receipt, `result.json`, sections 4.2 / 4.4, the FINALIZE
rows), traced by name, each classed as COMPUTED by a named existing function / CONNECTED but unverified (packaging,
hashing, citation or presentation: not semantic computation) / AWAITING a precise definition:

| product | existing consumer (function) | what it does with it | class |
|---|---|---|---|
| member and lifecycle GROUP_CLOSE rows (exact emission provenance) | `frankie_box_experiment_native.read_columns` -> `frankie_box_experiment_search.build_series` -> transforms / `couple` | placed on the F_LAST axis at the exact INPUT cursor + instrument + receive time; every scalar leaf becomes a searched series (`native.lifecycle.mirror.*` = the 4.4 GROUP_CLOSE offers) | COMPUTED (the search) |
| receipt (verdict, failed gates, groups, records, span, warm-up, minimum) | `frankie_box_experiment_native.selected_files` (gate: bedrock policy, completion status, pins); `frankie_box_scientific_teacher.completed_native_evidence` (read whole); `frankie_box_experiment_exchange.context_checks` (cited, sha256-bound) | selection gate; packaging; citation | COMPUTED as a selection gate only; otherwise CONNECTED-unverified |
| `result.json` `section_summaries` | `frankie_box_boss_session._reusable_projection` and `frankie_box_projection.project` (pinned into the projection plan spec); `frankie_box_bedrock.project_sections` (copied whole into the section files); the scientific reader; the exchange citation | identity / packaging / citation; no arithmetic reads a summary number | CONNECTED-unverified |
| `result.json` `averaged_companions` rows | the same three, plus the digest tables `bedrock.companions.4.2` (`frankie_box_digest_sources` / `_parallel` / `_render`) | copied, rendered; labelled supplement (D37) | by design NO semantic consumer: averages are not evidence |
| 4.2 `first_last_pairs` + `declarations` (`native_book_regime.BookRegimeCalculator`) | `frankie_box_bedrock.project_sections` / `frankie_box_projection.project` (filed as the section file); digest tables `bedrock.first_last.4.2`, `bedrock.declarations.4.2`; the scientific reader; the exchange citation | packaging, presentation, citation; the books themselves are already on the frame axis (searched as frames) | AWAITING a definition: the step series a two-point session summary is (Greg; a mathematical decision, not a connection) |
| 4.4 `matching_rule` + STREAM_END rows (`native_mirror.MirrorMatcher`) | `frankie_box_bedrock.project_sections` (the `mirror` lifecycle rows copied whole); digest tables `bedrock.lifecycle.mirror`, `bedrock.matching_rule.4.4`; the scientific reader; the exchange citation | packaging, presentation, citation | AWAITING a definition for any per-group pair-completion series: which group close owns a 4.4 pair completion (Greg) |
| FINALIZE rows (member and lifecycle ledgers) | `frankie_box_experiment_native.read_columns` (disposition `post_stream_knowledge_only`, exact ordinal ranges; refuses one that names a live group); `frankie_box_scientific_teacher._finalize_rows` (parsed only at those ordinals while the whole ledger is hashed against the pin); the exchange citation | never a search step (no axis position); read whole into the per-day completed-native file | CONNECTED-unverified; post-stream knowledge has no step, so its only lawful consumer today is the teachers' exchange as cited knowledge |

Nothing above was re-described as semantic coverage: packaging, hashing, citation and status counts are not computation.
No claim adapter, measurement, target, independence claim, enabled producer or model route was invented.

The repair (owner-local, within the existing pins and writer contract): `teach_accumulated` previously copied a retained
lesson's `completed_native_evidence` through unchanged, so a candidate-only lesson (built from the owner's
`FRANKIE_SEARCH_FINDINGS_V1`, which carries no such key) produced results with NO native evidence for the owning day, and
every other retained lesson carried only its original days' references. Now the owning search's manifest is read up front
(hash-checked; the parts are still hash-verified before the first new test) and the scientific reader's own
`completed_native_evidence(days[0], out_dir)` runs once for the owner (its pinned receipt / result / sections / ledgers,
bytes verified, written once under `<out_dir>/native/`; same bytes reuse, different bytes refuse). Every result header of
the day carries `completed_native_evidence.by_day[day]` = that reference beside the retained lesson's references for other
days (unchanged; a conflicting reference for the same day refuses), the merged `listed`, and `owner_day` naming the owning
manifest. The exchange's `lesson_context` / `context_checks` then cite the owner's completed-native reference for the current
day in BOTH seats, as they already do for lessons that carry one. No product is backfilled onto an earlier frame: the
reference lives in the retest lessons of the completed owner day. Older pending `inputs.json` refuse (producer sha changed).
Decisions kept open (Greg): which group owns a 4.4 pair completion; whether a 4.2 two-point session summary has a step
definition. Neither is authority to invent a series or statistic, and none was. Checks: `ast.parse`, `git diff --check`. No run.

### Slice D: identity plumbing (the price/structure producer task), native-consumer trace, late-arriving knowledge

Changed: `frankie_box_boss_session.py` (the producer task), `frankie_box_teacher_knowledge.py` and
`frankie_box_experiment_exchange.py` (late knowledge listed at the frozen boundaries). Read first: `ROOT_PLANE_COVERAGE`,
`KNOWLEDGE_CONSUMER_COVERAGE`, `NATIVE_LEARNER_INTEGRATION_DECISIONS`, `PENDING_FEEDBACK_COMPLETION` (all 2026-10-06).

**The producer change (`Session.derive`), the exact new row contract for Codex's reserved search adapter:**

`ROW_PROVENANCE_SCHEMA = 'FRANKIE_ROOT_ROW_PROVENANCE_V1'`. Both legacy spools keep every existing field and value
(calculation outputs unchanged) and gain ONE nested key, `provenance`, built only from identity already in scope where the
row is appended; nothing is inferred, no positional join is made, no timestamp is used as an identity.

| spool | existing fields (unchanged) | `provenance` (new) | semantics |
|---|---|---|---|
| `prices.jsonl` | `ts_recv`, `ts_event`, `price`, `size`, `bid_px_00`, `ask_px_00` | `schema`; `input_index` (int); `instrument_id`; `legacy_row_ordinal` (int) | `input_index` = the original extracted INPUT index of the record whose application produced this legacy row (the loop index; the same units as `frames.input_cursor` and `frames.input_record_indices[i]`); `instrument_id` = that INPUT record's `instrument_id` as the record carries it (None stays None); `legacy_row_ordinal` = the row's ordinal among that record's legacy rows (one record can yield several trade rows), so (`input_index`, `legacy_row_ordinal`) is unique |
| `structures.jsonl` | `ts_recv_ns`, `ts_event_ns`, every `describe_structure(...)` key | `schema`; `input_cursor` (int); `instrument_id`; `input_record_indices` ([int] or None) | `input_cursor` = the closing INPUT index (the record whose application closed this F_LAST group: equal to `frames.input_cursor` of the same close); `instrument_id` = `frame['instrument_id']`; `input_record_indices` = the group's member INPUT indices when the frame sections retain them (equal to `frames.input_record_indices` of the same close), else None (never reconstructed) |

Joins the adapter can make exactly, without timestamps: a structures row <-> its frame by (`provenance.input_cursor`,
`provenance.instrument_id`) == (`frames.input_cursor`, `frames.native_frame.instrument_id`) under ROOT's own membership
(`experiment_journal._frame_index`); a prices row -> its group by `provenance.input_index` in that group's
`frames.input_record_indices` (exact membership). A structure failure (a frame without a structures row) no longer
shifts any join, because each row names its own close. Detection: the derivation receipt carries `row_provenance_schema` and
`row_provenance_fields`; `layers.legacy_price.row_provenance` and `layers.legacy_structure_observables.row_provenance` name
the fields with the rule "identity fields, not observations: never a searched series". A retained older spool has no
`provenance`: explicit, unsupported for these joins; the old timestamp aliases are not exact identity.

Bindings: the legacy recovery identity (`legacy-state.pkl`) and the completed-legacy-stage identity (`legacy-stage.json`)
both carry `row_provenance_schema`, so an older saved state or completed stage refuses with the existing messages and is
preserved, never resumed under the new semantics (the same mechanism `FRAME_SECTIONS_SCHEMA` V1 -> V2 used). A non-recovery
rerun still moves an earlier derivation aside with its receipt. `load_retained_layers` reads rows as dicts (extra key fine);
the digest writer already renders nested frame fields (`book`, `transition`), so a nested `provenance` is within its contract.
Interim hazard, stated for Codex's adapter (change #1): `frankie_box_experiment_search.columns()` flattens every scalar
leaf, so until the reserved search excludes `provenance.*` the way it lists `EVENT_IDENTITY_FIELDS`, a NEW ROOT's spools
would present `prices.provenance.input_index`, `structures.provenance.input_cursor`, `...instrument_id`,
`...input_record_indices[i]` and the text `...schema` as channels; the same already holds today for the frames'
`input_cursor` / `input_record_indices` leaves, which this change mirrors. No search runs under the hold.
`describe_structure` lives in the pinned producers checkout (`_producer_module`, not this tree); nesting under `provenance`
keeps its keys untouched whatever they are.

**Identity-linked trajectories beyond positional slots (trace; interfaces returned, no unit or bridging chosen):**
- Identity-linked today: frames by (`input_cursor`, instrument) with exact member indices; journal entries per exact group
  (`journal.group.entries[position].*`, Codex); dipole target rows per group and the closing aliases per entity
  (`dipole.group_close.by_entity.<publisher>:<instrument>.*`, incl. `dstate.state.*`): a DState trajectory per entity across
  that entity's closes IS identity-linked by (publisher_id, instrument_id) on the existing F_LAST positions
  (`retained_evidence_counts` already reads it that way); events per exact group (Codex's fix); now prices/structures (above).
- Not identity-linked (positional): `dipole.group.rows[slot]`, `frames.book.*_levels_full[i]`, `...fifo_queue[j]`, native
  lifecycle `[slot]`s. A per-order or per-level trajectory needs an axis keyed by `order_id` / price level across closes:
  the data is present (`fifo_queue[j].order_id`, `observation.*`), the DEFINITION (which key, which lag unit, session
  bridging) is held; proposed interface only: `build_series` derives `order.<order_id>.<field>` from the retained
  `fifo_queue` leaves at each close of the order's instrument, lag unit = that instrument's closes (the existing axis);
  no such series is built here.
**Native representation / TeacherHead / training consumers:** per the decisions document the three decisions (retained
starting state; objective + auxiliary weight; cross-lane lineage) are open for Greg; `NativeForecastLearner.step` reports
`teacher_optimized=False`; the experiment classroom records `model_calls=0`. No adapter or identity plumbing is unambiguous
without those decisions, so none was built; nothing is relabelled as training. Blocked precisely by: decision 1 (locate or
declare the retained state), decision 2 (objective/auxiliary combination and its versioned state migration), decision 3 (a
versioned model lineage with queued updates across the three lanes).
**Late-arriving knowledge (audit + repair within the contracts):** both unfinished-work boundaries freeze their selection
once (`teach_accumulated` -> `inputs.json`; `accumulated_lessons` -> `learner-knowledge.json`) and a restart re-reads the
frozen selection; knowledge published after the freeze was silently invisible. Now each restart LISTS it: `late_arrivals()`
computes what `learner_knowledge(day, 'exchange')` would select now minus the frozen sha256s (documents and containers), and
the listing goes to the RECEIPTS (`accumulated_claim_tests.late_knowledge`; the exchange receipt's `late_knowledge` via the
new `notes=` argument), never into the frozen files or the hashed, write-once exchange documents (a restart must reproduce
their bytes exactly). Nothing is consumed late, no completed or frozen day is reopened, no scheduler policy is introduced.
Blocked by the held late-scheduling decision: whether, when and under which owner a later retest consumes listed late
knowledge (today: at the next owner boundary that freezes after it, by the existing selection).
Checks: `ast.parse` of the three modules without project imports; `git diff --check`. No run.

### Codex review and adapter integration after the fourth-session return (2026-10-07)

Integrated CCode through `276d6073`. Complete-plan reconstruction (B3) and selected-file
refusal (B5) address their named findings. Further B2 aggregate-coverage, B4 operation-semantic
and historical-binding-identity corrections are assigned at the task doc top; do not mark
historical reproduction/rework closed for either teacher. CCode owns those implementations.

The reserved exact-price adapter is now source-built on `FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2`:
`prices.group.rows[slot].*` requires the original INPUT's membership, matching instrument and
emitting close; original/local identity and emission/slot identity are checked independently.
Every declared group-row slot is preserved, including gaps; every unplaced ordinal has a
reason. V1 price rows/opening-state origins do not supply exact trade identity. Structure V1
joins and provenance-channel exclusion remain. No timestamp or spool-position identity is
inferred; these projections add no independent observations or identity-linked trajectories.

Step 5's shared correction interfaces are described in `STEP5_CORRECTION_DELIVERY_20261007.md`.
CCode's owned reader hooks and scientific-owner publication/successor interface are assigned.
Step 6's remaining three recovery groups are also in that task; the Codex runtime-failure
consumer wiring is built. No scientific computation or runtime verification occurred.

### Corrections after Codex's integration review (2026-10-07; CCODE_NEXT_SOURCE_TASKS top section, in its order)

Commits on `ccode/teacher-tasks-20261006b` atop Codex's `19f72f47` (rebased 2026-10-07): `18b6edcd` D1 | `8930b4f0` B7/C2 |
`5fdc14f5` B2-B5 | `45f52d28` B1/B6/A4/C1 | `6002a926` docs | `602e29f6` B7 by deletion | `0ed26712` handoff | `b5d0fe74` step-5 direction. SOURCE-BUILT / RUNTIME-UNVERIFIED (`ast.parse` without project imports,
`git diff --check`); nothing run, no reproduction called, the claims file untouched, Codex's two modules untouched.

**D1 (`frankie_box_boss_session.py`): the corrected price row contract for Codex's exact price adapter.** Codex's trace
holds: `InstrumentBook.apply` accumulates each T action's control row in `_legacy_group_rows` and returns the list only at
the instrument's F_LAST close, so V1 stamped the closing index on earlier trades. The correction stays in `Session.derive`
(no producer file changed: the producer is loaded from the pinned checkout and its open-group state is already the
retained state `mbo_resume_state` exports): before every `apply` the derive reads the instrument's open-group row count and
checks it against its own attribution (`ValueError` on any drift); after a non-closing `apply` (and after a failed one)
the rows the producer appended are attributed to THIS input; at the close the returned list is zipped with those
attributions. Values and row order unchanged. No timestamp or spool-position join; nothing inferred.

| field (`prices.provenance.*`) | unit / meaning |
|---|---|
| `schema` | `FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2` (prices only; structures keep `FRANKIE_ROOT_ROW_PROVENANCE_V1` unchanged, the name Codex's structure adapter pins) |
| `input_index` | the ORIGINAL extracted INPUT index whose application appended the row: the loop index over the sealed source's records, the same units as `frames.input_cursor` / `frames.input_record_indices[i]`; `None` for a row the opening adapter state carried in (`origin` says so) |
| `legacy_row_ordinal` | 0-based ordinal among the legacy rows THAT input's application appended; (`input_index`, `legacy_row_ordinal`) unique within the source |
| `instrument_id` | as the originating INPUT record carries it (None stays None); the book's instrument for an opening-state row |
| `group_close_input_index` | the INPUT whose application closed the emitting group (= that group's `frames.input_cursor`): the V1 `input_index`, named for what it is |
| `group_row_ordinal` | 0-based ordinal within the emitted group's legacy rows (the V1 `legacy_row_ordinal`) |
| `row_kind` | `trade` (a T action's control row) or `projection_at_event_group_end` (the producer's projection of the last A/C/M (else last non-F/N) member, appended by the closing input; the projected member's own index is NOT carried by the producer and is not guessed) |
| `origin` | `this_source`, `this_source_apply_failed` (appended before the producer raised on that input, which is in `failures`), `open_group_before_this_source` |

Joins: a prices row -> its group by `group_close_input_index` == `frames.input_cursor` (same instrument); its originating
member by `input_index` in that group's `frames.input_record_indices` (exact membership, V2 frames). Bindings: the legacy
recovery identity (`legacy-state.pkl`, which now also carries `pending_legacy_rows`) and the completed-stage identity carry
`price_row_provenance_schema`, so older saved state refuses; the derivation receipt carries `row_provenance_schema` (V1,
structures, unchanged for Codex), `price_row_provenance_schema`, `row_provenance_schemas` per spool and
`unclosed_legacy_rows`; `layers.legacy_price.row_provenance` names V2 and marks V1 `superseded`. A spool whose rows carry
V1 (or no `provenance`) is never read as originating identity: the adapter should keep listing those ordinals pending.
No new event axis, price-slot trajectory or lag definition.

**B7 / C2 (`frankie_box_historical_claims.py`, `frankie_box_scientific_teacher.py`, `frankie_box_experiment_exchange.py`).**
B7, per Greg (2026-10-07): no reference to transaction costs belongs in market-conditions work, so none remains in the
owned modules. The `crypto_harness` binding (the `_info_dipole_harness.py` driver and its results file, whose calculation
was not market-conditions work) is DELETED from `REPRODUCTIONS`; H01/H02 stay bound by `crypto_trend_flip` (counts only).
No admission table, no field, status word or sentence about it exists in the code (`8930b4f0` had added one; `6002a926`'s
successor commit removes it). `binding_tables_sha256` covers the two tables. C2, in the arithmetic: `ST.test` classifies
every tested and origin row's x/y with the reserved search's own `non_market_reason` (`series_role`): a context label or a
bookkeeping/clock/diagnostic channel makes the row `counts_only` with its reason (so the verdict counts exclude it);
claimed series of those roles are named in `untested`; every result carries `market_context` (roles, counts, the cell
rule: labels group, market conditions explain). Both seats voice the distinction through `context_checks`. Dates, days
and IDs stay attached to every row (`day`, `cell`, `where`). Not a validator framework: one classifier, reused.

**B2-B5 (`frankie_box_historical_reproduction.py` V2 schemas; the teacher, the knowledge replay, the exchange).**
B2: recorded references (`role` starting `recorded output`) are staged under `<out>/recorded/`, never in the tree the
driver runs in; `compare` takes a COMPLETED run only (status `run`, returncode 0, not timed out; else `performed_failed`
with the facts), re-reads produced files against the hashes the run captured and the reference at its pin, and compares
within a declared scope: the NG 108-day file on the six argv days only, legs aligned by `entry_idx` (`_NG_SCOPE`), never
by position; unaligned members and unequal lists are listed. B3: `run` refuses, BEFORE dispatch, a plan that differs from
the written `plan.json`, a staging that is not the plan's, staged bytes that changed, an `executable` flag that does not
follow from the facts, a `run.json` of another plan and a `dispatch.json` without `run.json` (no implicit retry); a
completed `run.json` of the exact plan is returned, never rerun; `dispatch.json` is written before the subprocess. B4:
`pins_of` = sources AND committed inputs; `record` keeps `performed_not_comparable` / `performed_failed` as statuses and
binds the operation evidence (plan/run paths + file and canonical hashes), the tables and the admission; `records_for`
admits only on the full declared binding (entry, claims, status, pins, tables) and, for a performed status, retained
consistent operation evidence on a `defined` binding (a `not_bound` entry can never acquire a performed status); every
rejected record is listed with identity and reason; `status_of` precedence is explicit (differs first); `status_summary`
keeps every record's status beside the word; older `HISTORICAL_REPRODUCTION_V1` files are listed as superseded. B5:
`record_selection(dir)` freezes the owner's record files; `teach_accumulated` freezes `<out_dir>/reproduction/` into
`inputs.json` with the other scientific inputs (`claim_inputs` binds its digest and the binding tables, so result identity
changes with them); `ST.test` / `reconsideration` / `historical_claims` take `records_dir` + `records_selection`, read only
the frozen files bytes-verified, and list later arrivals apart (also in the receipt's `late_knowledge.reproduction_records`).
The CLI route (`ST.main`) still reads `REPRODUCTION_DIR` live, stated in the result (`selection_frozen` false).

**B1 / B6 / A4 / C1.** B1: `run` writes `stdout.bin` / `stderr.bin` with every original byte (write-once, hash-bound in
the run document) and keeps the decoded text whole; `_compare_json` keeps every differing, missing and produced-only leaf.
B6: `plan.input_supply` states the exact gap: no settled interface supplies an input that is not in the repository
(realbins/, S3 NG MBP-10, regime caches); the receipt contract such an interface needs is named beside the nearest
existing contracts (the derive `source_binding` container pin, the search manifest parts, `witness`); nothing built,
fetched or activated; a `missing_inputs` binding never claims runnable reproduction. A4: `discovery_row_found` is set from
the reader's authenticated `discovery_row` on the current day BEFORE the arithmetic-unavailable path lists the row;
`discovery_row_margins_stated` / `discovery_row_listed_without_arithmetic` say which case holds. C1: the completed-native
reference carries `identity` (day, owning manifest, sha256, bytes, `read_from`) apart from `path`;
`native_evidence_identity` compares identities (same bytes under another output root = same evidence, listed; different
evidence for the same owner refuses); a carried same-day reference of another manifest never stands in when the owner has
none (listed with its provenance, left out of `by_day`); `teach_accumulated` returns `scope` (new result files, reuses,
`all_reused`).

**Greg's step-5 direction applied to the owned consumers (`b5d0fe74`; SPEC-experiment-orchestrator.md opening section,
Codex `19f72f47`).** The direction: a known error fixed at its source must not stay active because a record froze it;
carry checked corrections to both teachers and Frankie's actual inputs through existing paths; list propagation gaps
precisely. Traced: (a) a historical claim projected from a retained lesson carries the reproduction/reformulation binding
frozen into its `claim_inputs` at test time, and `ST.test` / `reconsideration` preferred that frozen binding; (b) the
exchange copied a retained result's `research_rework` (its binding and reproduction status) forward into both seats'
records and Frankie's `research_rework`. Both would have kept the deleted harness binding active. Now `ST.current_binding`
always takes the CURRENT tables and lists a differing retained binding as `retained_binding_superseded`
(`binding_identity` = status, entry ids, source pins); the exchange's `binding_correction` does the same per historical
item: `context_checks` voices it in BOTH seats, the rework record carries the current binding and `binding_superseded`, a
reproduction status read against a superseded binding is not `performed`, and Frankie's lawful reply learns one correction
line beside the rework he already receives. No lesson, result, record or brain file is rewritten or deleted; nothing is
relabelled as recalculated; a superseded binding's lesson bytes remain evidence.

Propagation gaps the current interfaces do not cover (listed, not built; each would be a new recovery/retention mechanism):
1. An owner's frozen `inputs.json` (`teach_accumulated`) refuses after any reader or table change ("retained scientific
   knowledge belongs to another search or reader"), so a corrected successor retest of an ALREADY-frozen owner day needs a
   new accumulated out_dir or a move-aside-with-receipt of `inputs.json`; `teach_accumulated` has no move-aside (derive
   has `_move_aside`). A fresh out_dir produces a successor result whose identity differs (`claim_inputs` binds the tables).
2. The exchange's frozen `learner-knowledge.json` refuses the same way (producer/reader sha in its identity): a corrected
   exchange of an already-frozen day needs a successor run directory; none is scheduled by anything.
3. Published brain lessons carrying a superseded binding stay selectable by `learner_knowledge`; they are corrected at
   consumption (this commit), not in the brain: the brain writer is append-only and nothing marks a published lesson
   superseded there. Consumers that do not pass through `ST.test` or the exchange (digest renders,
   `frankie_box_classroom_code.exchange_reply` text, Codex's modules) still show the frozen bytes.
4. Frankie receives the correction line only on exchange days; on non-classroom days the accumulated results published
   through the brain writer carry the current binding, but no separate delivery to Frankie exists outside the exchange.
5. A performed reproduction record written against earlier tables is listed, not admitted, by `records_for`; a corrected
   reproduction is new authorized execution, which nothing here performs or implies.

**B2-B5 follow-ups (Codex's review of the return; `2f1d6630`, 2026-10-07).** B2: `_compare_json` keeps the compared
scope apart from coverage: unaligned members, lists with unrelated positions, argv keys the record lacks and produced-only
leaves are coverage GAPS (`coverage.gaps`); with any gap the output is `incomplete`, never `matched`; the entry status
`performed_incomplete` sits between differs and matched in `STATUSES`; no tolerance or verdict. B3: `plan_document()` builds
the complete declared plan purely (command, pins, recorded outputs, tables, capability, `declared_inventory`, executable
with every reason); `run()` reconstructs it from the CURRENT entry and the staging and refuses a plan differing in any field
(the differing fields named), even when `executable` agrees; `inventory_complete()` requires every declared source, reference
and committed input to be staged, recorded apart or listed missing with the declared bytes, and nothing undeclared
(non-committed inputs are declared-missing by design). B4: `coherence()` chains record, entry, plan, dispatch, run and
comparison (schemas, entry ids, `run.plan_sha256`, the dispatch marker the run names, the comparison's run facts) and ties
the status to the run facts (a failed or timed-out run is only `performed_failed`; a completed run is never `not_run`);
`record()` refuses an incoherent operation before writing; `_admit()` re-checks the chain on read; every performed status
is retained. B5: a selected frozen record that is gone or changed now RAISES in `records_for` (preparation and reuse refuse
through `ST.test` / `teach_accumulated`), never listed as an absence; unselected late arrivals stay listed apart.

**Codex's review round on the follow-ups (`6837875a` B2-R, `bf8f87a5` B4-R, `0cb6868b` BIND-R; 2026-10-07).** B2-R:
`aggregate_status()` makes the whole-output status follow the coverage of every declared comparable output (a declared
printed/json output not compared at all is a gap: `performed_incomplete`, never matched); `compare()` records
`coverage`. B4-R: `coherence()` parses the dispatch marker (`read_dispatch`) and binds it to the entry, the plan hash,
the run's argv/cwd/start, an explicit authorization and the capability; the plan is bound to the CURRENT entry's
command, recorded outputs, declared inventory, status/calculation, pins and tables; the comparison status is recomputed
from its retained outputs; `record()` and `_admit()` both apply it. BIND-R: `binding_identity` is the complete
per-entry identity (`FRANKIE_BINDING_IDENTITY_V2`: inputs, commands, recorded outputs, calculations beside status,
entry ids, sources), carried in the lesson's `reproduction_binding.identity`; an older projection names its
unestablished parts and is `equivalence_not_established`, never inferred equal, in `current_binding` and the exchange's
`binding_correction`; a performed status is carried only on a complete, equal identity. Detail:
`CCODE_STEP6_RETURN_20261007.md` section 8.

Still open after these corrections (unchanged decisions): everything in section 5 and the Claude handoff; the exact
price adapter (Codex, on the V2 contract above); runtime verification of all of it.

## 9. Closure table after slices A-D (against the existing contracts; SOURCE-BUILT / RUNTIME-UNVERIFIED throughout)

**Codex fourth-session return review, 2026-10-07:** CCode through `276d6073` is integrated.
The current task doc assigns B2-R/B4-R/BIND-R and step-6 recovery corrections; B3/B5's named
source findings are addressed. B6 input supply remains open. D1 V2 and the exact-price adapter
are source-built, runtime-unverified. Greg authorized source work on step 5 and assigned CCode
step 6; neither authorizes execution. See the new section 8 integration note and step-5 report.

**Current correction status (supersedes the original closure table below):**

| Step | After the 2026-10-07 corrections (`45f52d28`); SOURCE-BUILT / RUNTIME-UNVERIFIED |
|---|---|
| 2 | A4, C1, C2, B4/B5 source-corrected (section 8, Corrections). Open: native-learner and late-scheduling decisions (Greg); Codex's integration review of the corrections; runtime verification. |
| 3 | D1 source-corrected: `FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2` (contract in section 8). Codex's exact price adapter is source-built. Open: the held trajectory/4.2/4.4 definitions. Exact structures unchanged (V1). |
| 4 | B1-B7 source-corrected (B7 by deletion); B2-B5 follow-ups source-corrected (`2f1d6630`); Codex's review round source-corrected (`6837875a` B2-R coverage, `bf8f87a5` B4-R operation semantics, `0cb6868b` BIND-R complete binding identity). Open: the input-supply interface (B6: named, not built; Greg's authorization); reproduction/reformulation open for BOTH teachers; nothing run. |
| 5 | Authorized source work: scoped correction delivery and stale-input refusal built. Open: scientific-owner publication, standalone hooks and corrected-successor scheduling. Old draft unapplied. |

The table distinguishes source implementation from the remaining review and workflow gaps. The older table records
what A-D attempted to connect; it does not waive implementation defects or reduce remaining
work to execution alone. H06-H08 remain historical/not_bound. All runtime verification is open.

| step | actual consumer / function | source-built connection | remaining implementation or decision | runtime verification needed |
|---|---|---|---|---|
| 1 | lane save/resume (Codex) | built | none named for CCode | whole |
| 2 | `teach_accumulated` -> `ST.test` -> brain writer -> exchange seats -> Frankie reply | A: discovery-day candidates and origin evidence to BOTH seats' records and the lawful reply, listed reasons voiced; C: the owner's completed-native reference in every accumulated result; D: late knowledge listed at both frozen boundaries; B: historical reproduction status read from hash-bound records | the three native-learner decisions and the late-scheduling decision (Greg); Codex's integration review | whole |
| 3 | `experiment_search.build_series` + transforms/coupling (Codex) | D: price V2 and structure V1 exact INPUT/instrument provenance now consumed by the reserved adapters; `provenance.*` excluded from channels | conditions, transforms, windows, turn/entry definitions (REFORMULATIONS); 4.4 pair ownership and a 4.2 step definition (Greg) | whole |
| 4 | `ST.test`, `candidate_claims_doc`, exchange, `frankie_box_historical_claims` bindings, `frankie_box_historical_reproduction` | A: exact origin identity + both-seat arithmetic; B: REPRODUCTIONS / REFORMULATIONS (3 bound, 1 not_bound), stage/plan/run/compare/record capability (never invoked), `research_rework` reads records; C: every completed-native consumer classed | survivor/acceptance rules (#5); the teachers' authorized execution of the bound reproductions (inputs for two bindings are off-repository) | whole |
| 5 | explicit scoped correction reader and existing knowledge consumers | source-built; see step-5 report | scientific-owner publication, standalone hooks and successor scheduling | whole |
