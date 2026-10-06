# CCode handoff to Codex: the Dipole collection in one place, and the teachers' capabilities on it, 2026-10-06

Branch `ccode/dipole-collection-20261006`, cut from `ccr-5fce7de3-xa4hfg` at Codex's `21df8f1` (your four commits
7bef0c5, b129dc6, 3e0a6f0, 21df8f1 are the base; nothing of yours was edited). Three CCode commits on top:

| commit | what |
|---|---|
| `7c555fe` | the Dipole collection combined into one catalog, and its claims build (Greg: "anything dipole, in one place") |
| `046361e` | tasks 1-3 of CCODE_NEXT_SOURCE_TASKS: reconsideration statuses, the mirrored-orientation double count, origin identity, the native-evidence review |
| `728f1f7` | the native evidence consumed: each searched day's completed native evidence read whole and carried in every lessons file |

SOURCE-BUILT / RUNTIME-UNVERIFIED throughout: py_compile, JSON parse, whitespace checks, direct source tracing. No run,
no test, no model, no AWS, no dispatch. CCode performed, reran or judged no Dipole research. Read in order:
`CCODE_DIPOLE_COMBINED_COLLECTION_20261006.md`, then `CCODE_STEP4_SOURCE_ROUTE_20261006.md` section 7, then this.

## 1. The collection (new files; the Sept 22 catalog and its claims file untouched beside them)

- `research/kalshi/frankie_boss/operations/build_dipole_combined_catalog.py`: sweeps every non-data origin branch tip
  (`git grep -il dipole`), one entry per distinct (path, blob), revision = newest tip carrying it, every other tip
  under `provenance.also_on`; carries the 127 Sept 22 entries byte-for-byte; lists machine data and this pipeline's
  own outputs separately; validated by `dipole_shared_knowledge._catalog`. Nothing swept is dropped.
- `knowledge/DIPOLE_SHARED_CATALOG_20261006_COMBINED.json` (4.8 MB): 1,538 sources (127 + 1,411), 46 data listed,
  3 derived excluded, 199 branches, review groups K01-K10 carried. 392 of the paths were absent from this branch
  (the whole Aug 28 native raw-MBO knowledge base among them); 182 differed across branches and every version is kept.
- `knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json` (52.9 MB raw, 7.6 MB packed; above GitHub's 50 MB soft warning,
  under its limit): built by YOUR builder unchanged (`frankie_box_historical_claims.build(catalog_path=<combined>)`):
  all 1,538 sources read at their catalog revision, 82,372 candidates, 10 claims (the existing crosswalk H01-H10),
  82,365 not_testable with path:line, catalog id, statement and reason.

## 2. The scientific teacher (CCode's module; every change additive, every existing caller unchanged)

- `historical_claims()` returns `reconsideration` (FRANKIE_HISTORICAL_RECONSIDERATION_V1), bound to the claims file by
  sha256, counting the four statuses: stored evidence reassessed (the mapped claims, here; NOT a reproduction);
  original calculation awaiting teacher reproduction (pending); teacher repair/reformulation (pending, performed 0);
  missing inputs or unsupported computation open (82,365 by class: awaiting_teacher_binding 81,655,
  code_source_constructions 710, missing_inputs, unsupported_computation). `write()` puts it at the lessons top level.
- every historical result carries `research_rework` with the same statuses, its construction and its prior labels; a
  rejected/dead/no-good label travels as a label and never closes anything (R11, R13, R14).
- `mirror_of()`: the search writes both orientations and D_yx[k] = D_xy[-k]; a reversed row that mirrors a forward row
  (same cell, swapped transform pair, negated lag, identical counts and chance check) is listed under
  `mirrored_rows`, never counted. Before this every held/shown_otherwise/unresolved count was doubled.
- `discovery_row` of a search candidate now requires the origin part sha256 among the given search's part pins
  (`load_searches` carries `part_pins`); a mismatch is listed under `untested`.
- `completed_native_evidence(d, ROOT)`: per searched day, the files the search pinned and did not search, read whole
  with bytes verified: receipt verdict/gates; result section summaries (averaged companions labelled supplement-only,
  D37); 4.2 exact first/last books and declarations; 4.4 matching rule and STREAM_END rows (GROUP_CLOSE offers
  cross-referenced to native.lifecycle.mirror.*, not duplicated); every FINALIZE row of the exact ledgers at the
  ordinals the search listed post-stream, the whole ledger hashed against the pin. Written once to
  `<work>/native/<day>-completed-native.json`; every lessons file carries `completed_native_evidence.by_day[day]`
  (path, sha256, counts, receipt, matching rule) and `listed`.
- `frankie_box_candidate_claims.py` and the launcher: reviewed, unchanged (the launcher's HISTORICAL_CLAIMS pattern
  already admits the combined file).

## 3. Your edits, in order (named, not made)

1. `frankie_box_experiment.py` plan `historical_claims` -> `research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9dc79ca359e9.json`.
2. `frankie_box_experiment_exchange.py`: per historical lessons file read `lessons['reconsideration']` once and state
   its `statuses` in BOTH seats' turns (mapped N of M candidates; open by class; reproduction/repair pending counts),
   and attach it as `collection` to each historical item's `research_rework`; keep HISTORICAL_REWORK as next_test.
3. `frankie_box_experiment_exchange.py` boss_turn and science_turn: cite
   `lessons['completed_native_evidence']['by_day'][day]` (sha256-bound) in evidence_checks; averages only as labelled
   supplements.
4. `frankie_box_teacher_knowledge.teach_accumulated` / `frankie_box_lane_state.learner_knowledge`: carry the two
   top-level keys `reconsideration` and `completed_native_evidence` through the accumulated selection unchanged.
5. `frankie_box_experiment_teacher.py` (BOSS): no input change for the exchange route; if the BOSS teacher is to
   compute on historical claims outside the exchange, give it the same claims file and the same carry.
6. `frankie_box_historical_claims.CROSSWALK` (yours): the only mechanism that moves a statement from
   awaiting_teacher_binding to mapped; each entry names a source anchor, series the search carries and a pairwise step
   relation. Growing it is teacher-binding work, not CCode's.
7. `frankie_box_principal_inputs.py` still reads the Sept 22 catalog for the principal's 71 artifacts; switching to the
   combined catalog widens the principal's retrieval set from 127 to 1,538 sources: your call with Greg.

## 4. Still Greg's

- A searchable per-group count of 4.4 pair completions needs the definition of which group close a completed pair
  belongs to (its later leg's exact group?), a mathematical decision; 4.2 session summaries need a definition of what
  step series a two-point session summary is, if any.
- Whether the 52.9 MB claims file stays as one committed file or the not_testable list moves to a sibling file (the
  teacher reads it by reference either way).

## 5. Boundaries kept

No install, download, model call, workflow dispatch, AWS action, test framework, canary or E2E. Granite pins and
parameters (threads null) untouched. Step #5 untouched; the preserved draft unapplied. Brain, experiment, queue,
exchange, classroom, lane, search and native-capture files untouched. Scratchpad cleared.
