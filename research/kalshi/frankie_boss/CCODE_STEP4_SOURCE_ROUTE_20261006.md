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
