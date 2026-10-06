# CCode new-chat handoff: the expanded pre-#5 queue, slice A done, slice B next, 2026-10-06

Branch `ccode/teacher-tasks-20261006b`, tip = slice A commit on top of Codex's `bbe2d56` (ccr-5fce7de3-xa4hfg).
Fetch latest and preserve newer commits:
  git fetch origin ccode/teacher-tasks-20261006b ccr-5fce7de3-xa4hfg
  git checkout -B ccode/teacher-tasks-20261006b origin/ccode/teacher-tasks-20261006b && git log --oneline -1
If ccr moved again, rebase onto it (Codex's commits have not touched CCode's files so far; the last rebase was clean).

SOURCE-BUILT / RUNTIME-UNVERIFIED throughout. Source/interface review, `ast.parse` without project imports and
`git diff --check` only. No tests, runs, installs, model calls, AWS actions, dispatch, canaries or E2E. STOP before #5.

## Read, in order (research/kalshi/frankie_boss/)

1. `NEW_CHAT_HANDOFF_20261006_TEACHER_COVERAGE.md` (Codex's detailed continuation; the newest section is the
   event-group membership fix in its reserved search module, which does not change CCode's assignment).
2. `CCODE_NEXT_SOURCE_TASKS_20261006.md`, the expanded top section: slices A, B, C, D and the delivery limits.
3. `CCODE_STEP4_SOURCE_ROUTE_20261006.md` sections 7 and 8 (what CCode built and what remains).
4. `CCODE_HANDOFF_CODEX_DIPOLE_TEACHERS_20261006.md` and `CCODE_DIPOLE_COMBINED_COLLECTION_20261006.md`.

## Ownership now (from the expanded assignment)

CCode: `frankie_box_teacher_knowledge.py`, `frankie_box_experiment_exchange.py`, `frankie_box_scientific_teacher.py`
and its launcher, `frankie_box_candidate_claims.py`, `frankie_box_historical_claims.py` and narrowly required
historical binding helpers, evidence-reader/consumer modules for slice C, the Step #4 report and CCode's own docs.
Codex: `frankie_box_experiment_dipole.py`, `frankie_box_experiment_search.py`, the shared continuation/assignment
documents. Do not edit those two modules; read their latest route before wiring consumers.

## Slice A: DONE (step-4 report section 8)

- `teach_accumulated` no longer skips discovery-day candidates; the frozen selection precedes the scheduling loop and
  the identity (own file + ST/EX/CC/LS/BR sha256) refuses older pending inputs; the reader's origin path lists the
  discovery rows from the owner's complete hash-checked parts, counting none as a test.
- exchange: `count_margins` factored out of `shared_count_accounting` (output unchanged); `origin_evidence_accounting`
  applies the same exact margins to the current day's origin rows; BOSS turn states it beside the shared accounting;
  scientific turn's `day_text` names the origin rows and whether the exact discovery row was found, sidecar
  `origin_on_day`; both turn records carry `origin_accounting`; Frankie's reply learns the lines plus the R06 sentence
  and his sidecar carries `origin_evidence`; items name `origin_rows_on_day`. Nothing enters tests, findings,
  confirmation, promotion or historical reproduction.
- reader: `MIRROR_FIELDS` names `null_exclusion` and `beyond_chance`.

## Slice B: NOT STARTED in code; traced, with one decision taken

Traced each crosswalk claim's original calculation to code at its exact revision (pins computed, not yet written):

| claims | original calculation | where (revision, catalog id) | inputs | recorded output |
|---|---|---|---|---|
| H01, H02 | `odcore.info_dipole.divergence`; driver `_info_dipole_trend_flip.py` (pooled n=1560) and `_info_dipole_harness.py` | bb28b35e; review.091 / .112 / .095 | `fingerprint_dataset/test_bars/*.json` (6 committed 1-min files) or `realbins/*_bins.json` (materialized from data/* branches) | docstring numbers; `_info_dipole_harness_results.json` (review.096) |
| H03 | `month_characterize.dipole_pieces(a, ei, sign, win_s=300, nbins=10)` -> `dip_imb_level` | 21df8f1; swept month_characterize | NG MBP-10 leg day tapes + legs (S3, S92/S95 renders) | ng_brain: 1,537 legs, 87.6 percent (baseline ng_brain, bb28b35e) |
| H04, H05 | `event_move_baseline` `imb_R` (resting-book imbalance, 10 levels); at-entry use in month_characterize | 21df8f1; swept | NG MBP-10 | ng_brain direction.book_contrarian |
| H09, H10 | `month_characterize` turn pieces -> `turn_far_thinning` (`characterize_turns.py` driver) | 21df8f1; swept; `renders/ng_refine_s95/fingerprints.json` (NOT in the catalog: no "dipole" in its text; bind by path+revision+sha) | six pivotal NG days MBP-10 | fingerprints.json values |
| H06, H07, H08 | Memory A: `a_memory_member_first_recalculation_20260828.py` (NOT in the catalog) and the A-memory positive knowledge document | b4f364f0; baseline.a_memory_promoted_positive_knowledge, baseline.a_memory_member_first_recalculation_receipt | the A-memory ledger (sha bc0788b5...) | receipt counts; 0.315686; depth 1,342/698 |

DECISION (Greg, 2026-10-06, in chat): Memory A is no longer used. H06, H07 and H08 keep their statements, labels and
rationale as historical claims (CLAUDE.md 2026-09-27: the Memory A requirement is removed, historical files preserved
as evidence), but their original construction is NOT bound for reproduction and no Memory A path is built. Record
them as `reproduction: not_bound, reason: Memory A retired by Greg 2026-10-06; original evidence preserved`. Codex did
not ask for Memory A; the three claims came from the 2026-09-29 crosswalk.

Plan for the code (nothing of it written yet):
1. `frankie_box_historical_claims.py`: a declared `REPRODUCTIONS` table (per claim: bound sources by path + revision
   + sha256 + catalog id where present, entry point, inputs required and where they live, the recorded outputs, and
   `defined`/`missing`), and a `REFORMULATIONS` table recording, per claim, what a declared repair or reformulation
   needs (H01: a numeric-state condition, not searched; H02: a "|imbalance| falling" transform, a mathematical decision;
   H03/H04/H05: the |0.15| and flat-flow conditions; H09/H10: a turn definition). The claims FILE stays byte-identical
   (its builder is not run under the hold): the teacher attaches the tables at read time by claim id.
2. A staging/plan/run/compare capability for reproduction: stage bound bytes where history exists (git show at the
   revision, sha verified), write a plan, run the entry only when execution is authorized, compare to the recorded
   outputs field by field, write HISTORICAL_REPRODUCTION_V1 (performed_matched / performed_differs / not_run with the
   missing inputs named). Never invoked now.
3. `frankie_box_scientific_teacher.py`: `historical_claims()` attaches `reproduction` and `reformulation` per claim;
   `test()`'s `research_rework` reads a HISTORICAL_REPRODUCTION_V1 record under `<work>/reproduction/` when one exists
   (status from it), else `pending_teacher_work`; the reconsideration block counts bound / not bound.
4. `frankie_box_experiment_exchange.py`: the historical item's `rework` must not overwrite a performed reproduction
   status with `not_established_by_this_exchange` (today it does); keep the reader's value when it reports a
   hash-bound performed record.
Pins computed this session (write them into the table, do not recompute on the box, which has no history):
  odcore/info_dipole.py@bb28b35eefd3 0fb1f3d868973fcf0ee25be30d7ffe1f7b388a9235a19d893f8495012c0df23b
  _info_dipole_trend_flip.py@bb28b35eefd3 954f6699bd38483a5df1489a14b3fb71b822ed2c55b47b58b2ed2ef15b73cb35
  _info_dipole_harness.py@bb28b35eefd3 c0adfc40dcc07e2e296daa26b5da9c4e20c7d00a6b34445df5ca1687e3222dda
  _info_dipole_harness_results.json@bb28b35eefd3 ace94a10b8bb2b35f45a37a519ef7fb364c138f10508ce5d6a72c3a8026130e8
  _info_dipole_swing_backtest.py@bb28b35eefd3 7f0f9ce36cc3feec0e1e509b190d4b6ca0c1614ffaab288b969f128b59f94964
  _info_dipole_flow_detrend.py@bb28b35eefd3 69e8ba1ea42794aa40cddc62b7538766a356bda823958d8d7a0686968b782dfc
  research/kalshi/knowledge/ng_brain.json@bb28b35eefd3 bf473faef4d5a1b8fc68a214616e6c6163f0db1794ac98818a5401225563da57
  research/kalshi/month_characterize.py@21df8f140e6e 9480cbe7f62f3d10a3e51068d170f47813ac2f1df3195386f4c6f0b7946a36aa
  research/kalshi/event_move_baseline.py@21df8f140e6e 1d84f91f5a6b3faf24803b7564ee6b29652dd683159cc7e4afc6c86fdba5a503
  research/kalshi/characterize_turns.py@21df8f140e6e 8544d26475c5baedce90c0df210095b2027dedcc2c0a3dc5d646c0793751bc7d
  research/kalshi/renders/ng_refine_s95/fingerprints.json@21df8f140e6e e215180898ad260e555edbde643e334538f2cb649fe3b444b59a3c5a658a7099
  fingerprint_dataset/test_bars/{btc,eth}_{bybit_perp,coinbase,kraken}_minbars.json at HEAD: f804b3f8..., b5e0f30d..., 58dfa5b7..., eb475f74..., 8876a78b..., 53cfd00e...

## Slices C and D: not started

C: start from `completed_native_evidence` (scientific teacher) and the exchange's `context_checks`; report each
product as computed-by-a-named-function / connected-but-unverified / awaiting-a-definition; repair the
candidate-only accumulated route so it generates the current owner's native evidence where the pins and writer
contract permit. D: read ROOT_PLANE_COVERAGE, KNOWLEDGE_CONSUMER_COVERAGE, NATIVE_LEARNER_INTEGRATION_DECISIONS,
PENDING_FEEDBACK_COMPLETION first; build only settled connections; return exact interfaces for the reserved modules.

## Closure table (required by the assignment; against existing contracts)

| step | actual consumer / function | source-built connection | remaining implementation or decision | runtime verification needed |
|---|---|---|---|---|
| 1 | lane save/resume (Codex) | built | none named for CCode | whole |
| 2 | `teach_accumulated` -> `ST.test` -> brain writer -> exchange seats -> Frankie reply | candidates incl. discovery-day; origin evidence to both seats (A) | historical reproduction/repair bindings (B); native semantic consumers (C); late knowledge (D) | whole |
| 3 | `experiment_search.build_series` + transforms/coupling (Codex) | Codex's raw/closing-row/event-group fixes | conditions, transforms, targets, trajectories: definitions held | whole |
| 4 | `ST.test`, `candidate_claims_doc`, exchange | exact origin identity, mirror dedupe, origin accounting (A) | survivor/acceptance rules: #5 | whole |
| 5 | discussion | STOP | Greg | n/a |

## Decisions for Greg (open)

- The 4.4 pair-completion group definition; a 4.2 session-summary step definition.
- Whether the 52.9 MB claims file stays one file; whether principal_inputs switches to the combined catalog.
- Memory A: confirmed retired in chat; recorded above as the H06-H08 disposition.
