# CCode new-chat handoff: the expanded pre-#5 queue, slice A done, slice B next, 2026-10-06

## CURRENT HANDOFF — 2026-10-07 01:52 ET: the rest of Step 8

Read `CCODE_HANDOFF_STEP8_REMAINDER_20261007.md` and the top ACTIVE block of
`CCODE_NEXT_SOURCE_TASKS_20261006.md`. Greg assigns CCode the remaining Step 8 while Codex
continues other workflow pieces, then independent agent review. Your Step 8A `954f3f3`
is not yet integrated; preserve it and newer work. Exact expanded ownership, three 8A
review fixes, main/class recovery and run/day scope are in
`CCODE_STEP8_REMAINDER_ASSIGNMENT_20261007.md`. This supersedes older next-action and
ownership wording below. Source-only; no tests or AWS/runtime execution.
## STATE AFTER THE SEVENTH CHAT (2026-10-07): Step 8A RETURNED (the CPU controller's lifetime and launch routing)

Branch `ccode/teacher-tasks-20261006b`, rebased clean onto Codex's `3a1416b7` (ccr-5fce7de3-xa4hfg; it integrated the sixth
return `31832bf2`, fixed the sixth-return findings directly and assigned Step 8A), pushed. One `[skip ci]` commit per group:
`8936c260` the controller's lifetime, prerequisites and controls (`pod_root/controller.py` + the new launcher
`deploy/aws/box/frankie_box_cpu_controller.sh`) | `6048de03` the reachable Pod routes closed (`frankie_box_run.yml` + the
marker `frankie_box_pod_root_loop.sh`) | `8cfed7cc` review pass 1 (17 findings) | `d091e734` review pass 2 (10) | the docs
commit (tip). The record is `CCODE_STEP8_CPU_CONTROLLER_20261007.md`: the action map (section 1), the recovery ownership
(2), one controller per run (3), the dependencies still missing (4, above all the main box's instance profile, which cannot
be established from source and is Greg's decision), the Pod closure and the inventory of unrelated Pod entrypoints (5),
the narrow requests to Codex-owned functions (6), what the review passes fixed and kept (7), what remains of Step 8 (8).
Owned files only; the four step-6/historical modules untouched this round. SOURCE-BUILT / RUNTIME-UNVERIFIED: `ast.parse`,
`compile`, the static import and call checks, `sh/dash/bash -n`, `yaml.safe_load`, `git diff --check`; nothing run, no
AWS, no dispatch; pins and threads null untouched; STOP before #5; `9c19cc2` never applied; no cost reference anywhere.

In one paragraph: the SAME controller now runs on two hosts. On the runner it stays a bounded job (plan, status, resume,
stop, a loop whose budget end is `budget_expired`, never completion). On the main box it is a run-bound systemd unit from
the staged checkout (`--host main --budget-minutes 0`), the experiment launcher's DETACH pattern, serving every Linux
boundary of the run until the Linux lane has no remaining work or a cooperative stop is acknowledged; its state is retained
under `/opt/frankie-box/work/cpu-controller/<run>/`; an S3 lease (create-only, ETag-conditional) keeps a runner loop and a
box service off one run; a stop relays the worker's save and acknowledges with what is pending, claims untouched; a resume
reuses the original job, claim and inputs or is refused with the reason; `preflight` names each prerequisite beyond source
and refuses activation. The Jev/CLM Pod scripts are refused by the workflow before any step; the always-cleanup branch has
no provider call or key; the provider path is gone from the controller.

What Codex picks up:
1. Integration review of the five commits; anything it names comes back to CCode the same way, one commit per group.
2. The requests of the report's section 6: the main day-bound save/resume and class-child acknowledgment interface, the
   coordination gap tolerance, the worker's input-URL refresh, new queue state words.
3. Still Codex's: the step-5 reader hooks and successor scheduling, the claim-input identity mismatch, Jev's step 7, the
   shared runner/queue and main save/resume.

## STATE AFTER THE SIXTH CHAT (2026-10-07): Codex's fifth-return review BIND-F, B4-F, 6R3-F, 6R2-F RETURNED, plus two adversarial review passes

Branch `ccode/teacher-tasks-20261006b`, rebased clean onto Codex's `5e216265` (ccr-5fce7de3-xa4hfg), pushed, tip `889120af`
(docs). One `[skip ci]` commit per finding, in the task doc's order, then the review passes: `12258b3b` BIND-F | `7dd8b9a4` B4-F |
`34dab141` 6R3-F | `4b5a8eba` 6R2-F | `62eb55e3` review pass 1 (10 corrections) | `6c804bd2` review pass 2 (10 corrections) |
`889120af` docs. Codex's integration tip moved to `c816bc56` (step seven) after this branch was rebased; the next CCode chat
rebases onto it first. Owned files only (`frankie_box_granite_meeting.py`, `frankie_box_scientific_teacher.py`,
`frankie_box_historical_reproduction.py`, `frankie_box_experiment_exchange.py` outside the reader hooks). SOURCE-BUILT /
RUNTIME-UNVERIFIED: `ast.parse` without project imports, a static check that every dotted module used is imported,
`git diff --check`; nothing run, no model call, no AWS, no dispatch; `run()` never called; claims file byte-identical;
STOP before #5; `9c19cc2` never applied; pins and threads null untouched; no cost reference anywhere.

Per finding (detail: `CCODE_STEP6_RETURN_20261007.md` section 9; step-4 report section 8 paragraph and section 9 row 4):
- BIND-F: `FRANKIE_BINDING_IDENTITY_V3`, one JSON-stable identity built per entry (status, sources, inputs, command,
  recorded_outputs, calculation; tables' shape per entry), validated by the parts present; a retained V2 identity is
  converted with its association marked unestablished, never dropped; `binding_identities_differ` reports
  `equivalence_not_established` rather than inferring equality; the exchange voices it.
- B4-F: `command_argv(command)` is the producer's own contract (`['-B', script, *argv]`) checked against the run record's
  argv; one `DECLARATION_FIELDS`; the retained outputs must be the full declared comparison inventory by position; an older
  comparison without declaration fields reports inventory-not-establishable.
- 6R3-F: `http.client.HTTPConnection` owned by the meeting; every blocking read bounded by the absolute remaining deadline and
  a per-call ceiling (health 5 s, chat 600 s); partial bytes retained on every failure; `sent` on both meeting exceptions
  distinguishes a request that never reached the socket, and such a request clears `pending_call` instead of reading as
  an interrupted call.
- 6R2-F: `evidence/attempts/<attempt>-start.json` is written before Popen (spawn failure = `MeetingCallFailed`, recorded);
  attempt records are clock-free and write-once; `retained_attempts` discovers attempts from records, orphaned stderr files
  and evidence directories; the complete record carries `runtime.attempts`, `unfinished_attempts`,
  `calls.pre_send_intents_unresolved` apart from `model_calls`.
- Review passes (Greg: "this has to be the last correction"): the code-review skill run adversarially over the whole range at
  high effort, twice; the gravest finding was an `import http.client` line the 6R3-F edit script built and never applied.
  A third pass was not run (Greg: commit and push); the next CCode chat runs one before any push.

What Codex picks up:
1. Integration review of the seven commits; anything it names comes back to CCode the same way, one commit per group.
2. Still Codex's: the step-5 reader hooks (`teach_accumulated`, `accumulated_lessons`, direct lesson loading, both
   `learner_school(stage='exchange')` call sites), scheduling of scientific-owner successors, and the claim-input identity
   mismatch at the step-5 reader (step-6 return sections 6 and 8).
3. Nothing else is assigned to CCode. Greg's decisions stay open as listed in the prior sections; weight learning stays
   inference-only until Greg decides feedback, objective, pin policy and host.

---


## STATE AFTER THE THIRD CHAT (2026-10-07): Codex's correction queue D1, B7/C2, B2-B5, B1/B6/A4/C1 RETURNED

Branch `ccode/teacher-tasks-20261006b`, rebased clean onto Codex's `19f72f47` (ccr-5fce7de3-xa4hfg), pushed. One `[skip ci]`
commit per finding group, in Codex's order: `18b6edcd` D1 | `8930b4f0` B7/C2 | `5fdc14f5` B2-B5 | `45f52d28` B1/B6/A4/C1 |
then this documentation commit. Owned files only (`frankie_box_boss_session.py`, `frankie_box_historical_claims.py`,
`frankie_box_historical_reproduction.py`, `frankie_box_scientific_teacher.py`, `frankie_box_teacher_knowledge.py`,
`frankie_box_experiment_exchange.py`); Codex's two modules and the shared handoffs untouched. SOURCE-BUILT / RUNTIME-UNVERIFIED:
`ast.parse` without project imports, `git diff --check`; no test, run, install, model call, AWS action, dispatch, canary or E2E;
`frankie_box_historical_reproduction.run()` never called; the claims file byte-identical; STOP before #5; `9c19cc2` never applied.
Detail per finding: step-4 report `CCODE_STEP4_SOURCE_ROUTE_20261006.md` section 8 ("Corrections after Codex's integration
review") and the section 9 status table. Greg, 2026-10-07: no reference to transaction costs belongs in market-conditions
work: the `crypto_harness` binding is deleted from `REPRODUCTIONS` and no admission table, field or sentence about it remains.

Greg's step-5 direction (`19f72f47`) is applied to the owned consumers in `b5d0fe74`: the current declared tables decide; a
binding frozen in a lesson is superseded (listed, never used) in both seats and in Frankie's lawful reply; the five
propagation gaps the current interfaces do not cover are listed in the step-4 report section 8 (none is built).

What Codex picks up:
1. D1 handshake: prices now carry `FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2` (originating `input_index` + `legacy_row_ordinal`,
   plus `group_close_input_index` / `group_row_ordinal` = the V1 values named for what they are, `row_kind`, `origin`); structures
   and the receipt's `row_provenance_schema` stay V1 (the name the structure adapter pins); the receipt adds
   `price_row_provenance_schema` and `row_provenance_schemas`. The exact price adapter is Codex's; a V1 or provenance-free
   price spool stays listed pending. Full field/unit table in the report.
2. Integration review of the four correction commits; anything it names comes back to CCode the same way.
3. Nothing else is assigned to CCode. Greg's decisions, unchanged: the REFORMULATIONS needs; the B6 input-supply authorization; the 4.4 pair owner; the 4.2 step definition; the three native-learner decisions;
   late scheduling; the 52.9 MB claims file; the principal_inputs catalog. Memory A retired (H06-H08 `not_bound`).

---


## STATE AFTER THE SECOND CHAT (2026-10-06, later): slices A (follow-ups), B, C, D DONE on CCode's side

Branch `ccode/teacher-tasks-20261006b`, rebased onto Codex's `59cca0d4`, pushed. Commits, one per slice, all `[skip ci]`:
`9e456888` A follow-ups 1-3 (exchange) | `1eaa8c8d` B (historical bindings + reproduction capability + rework reads records)
| `a1085a6e` C (owner's completed-native evidence in every accumulated result) | `77edcf41` D (row provenance on the ROOT
price/structure spools; late knowledge listed at frozen boundaries). Detail and the closure table: step-4 report
`CCODE_STEP4_SOURCE_ROUTE_20261006.md` section 8 (per slice) and section 9. Everything SOURCE-BUILT / RUNTIME-UNVERIFIED:
`ast.parse` without project imports, `git diff --check`, `re.compile` of the recorded-output patterns read as string
constants; no test, run, install, model call, AWS action, dispatch, canary or E2E; boxes untouched; STOP before #5 kept;
the preserved draft unapplied; `9c19cc2` never applied; Codex's two reserved modules untouched.

What a next chat (or Codex's integration review) picks up:
1. Codex: integrate the four commits; the reserved search adapter for the new `provenance` row contract (report, slice D),
   including excluding `provenance.*` from channels the way `EVENT_IDENTITY_FIELDS` are excluded.
2. Greg's decisions, unchanged and now named in code: the REFORMULATIONS needs (a threshold state, a windowed transform, a
   window, a LEG/SIDE definition, a flat-flow bar, an entry and a turn definition); the 4.4 pair-completion owner; a 4.2
   step definition; the three native-learner decisions; the late-scheduling decision; the 52.9 MB claims file; the
   principal_inputs catalog. Memory A: retired, recorded as H06-H08 `not_bound` in `REPRODUCTIONS`.
3. When execution is authorized: the teachers run the bound reproductions through
   `frankie_box_historical_reproduction` (`crypto_trend_flip` is stageable from history; `crypto_harness` needs `realbins/`,
   `ng_leg_fingerprints` needs the S3 NG MBP-10 tapes and the regime caches); records land under `<work>/reproduction/`
   and `ST.test` reads them. CCode runs nothing.
Note for a rebuild of the claims file (not under the hold): the builder's own guard refuses to overwrite the committed
file because `builder_sha256` changed; the committed file is byte-identical and current.

---


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
