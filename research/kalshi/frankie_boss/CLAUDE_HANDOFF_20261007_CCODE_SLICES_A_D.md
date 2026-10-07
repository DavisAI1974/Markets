# Claude handoff, 2026-10-07: the CCode pre-#5 queue, slices A-D returned (source-only session)

This is the Claude-side handoff. The Codex-facing record is separate: `CCODE_STEP4_SOURCE_ROUTE_20261006.md` (sections 8-9),
`CCODE_HANDOFF_20261006_TEACHER_TASKS_NEXT_CHAT.md` (top section) and `CCODE_DROP_IN_20261006_NEXT_CHAT.md`. Do not merge the
two channels: Codex integrates from the CCODE documents; a Claude session starts from `DROP_IN_CLAUDE_20261007.md`.

## Where things stand (updated 2026-10-07, third session: the correction queue returned)

Codex's integration review of A-D landed as an ORDERED correction queue at the top of `CCODE_NEXT_SOURCE_TASKS_20261006.md`
(D1; B7/C2; B2-B5; B1/B6/A4/C1), in Codex's `61264cac`. This session rebased clean onto it and returned one `[skip ci]` commit
per group: `f2a43e80` D1, `3d7f1640` B7/C2, `130742ff` B2-B5, `a3651234` B1/B6/A4/C1, `744cae4c` docs, then `c94dcac0`
(B7 by deletion, Greg: no cost references, see below); tip `c94dcac0`, pushed, worktree clean, scratchpad empty. Everything
SOURCE-BUILT / RUNTIME-UNVERIFIED (`ast.parse` without project imports, `git diff --check`, the codebase-memory CLI index);
nothing run, no reproduction called, the claims file byte-identical, Codex's two modules untouched, STOP before #5 kept.
The per-finding record (what each correction does, the D1 field/unit table for Codex's price adapter, what stays open) is
the step-4 report section 8 "Corrections after Codex's integration review" + the section 9 table; the Codex-facing summary
is the new top section of `CCODE_HANDOFF_20261006_TEACHER_TASKS_NEXT_CHAT.md`. Greg, mid-session, twice: no reference to
transaction costs belongs in market-conditions work. So B7 is closed by DELETION, not by framing: the `crypto_harness`
binding is gone from `REPRODUCTIONS`, the admission table that `3d7f1640` had built around it is gone, and no field, status
word or sentence about it remains in any owned module. Do not reintroduce one.

Design choices a next session should know (so they are not re-litigated):
- D1 was fixed in `Session.derive`, not in the producer file: the producer is loaded from the PINNED checkout (`_producer_module`)
  so an in-tree edit would not run on the box without moving the pin, and its open-group row list is already the retained
  state `mbo_resume_state` exports. The derive reads that state before/after each `apply` and refuses on any drift.
- Prices got their OWN schema (`FRANKIE_ROOT_PRICE_ROW_PROVENANCE_V2`); structures stay V1 because Codex's structure adapter
  compares `provenance.schema` and the receipt's `row_provenance_schema` against the V1 literal. Do not bump V1.
- C2's classifier is the reserved search's `non_market_reason`, imported (not copied) by `frankie_box_scientific_teacher.series_role`.
- The reproduction module's schemas moved to V2 (`PLAN`, `RUN`, `STAGING`, `RECORD`); `records_for` lists V1 records as superseded.
  `record()` gained a required `operation_dir` argument; nothing calls it.
- The owner-local records directory is `<accumulated out_dir>/reproduction/` (frozen into `inputs.json`); the CLI route still
  reads `ST.REPRODUCTION_DIR` live and says so.

What a next Claude session does: Codex's review of these four commits lands in the same task doc; fix what it names, one
commit per group, same boundaries; nothing else is assigned.

## Where things stand (as of the second session, 2026-10-07 early; superseded above)

Branch `ccode/teacher-tasks-20261006b`, rebased clean onto Codex's `80a0e279` (ccr-5fce7de3-xa4hfg), pushed; tip `fea2e165`.
Commits above Codex's tip, oldest first: `b2dbc51f` (the prior chat's handoff), `c31cad06` A follow-ups, `7cb2ce52` B,
`11082ff8` C, `2a05c147` D, `0adcf3d6` handoff state, `fea2e165` CCode drop-in. Working tree clean; scratchpad empty.
Everything is SOURCE-BUILT / RUNTIME-UNVERIFIED: `ast.parse` without project imports, `git diff --check`, `re.compile` of the
recorded-output patterns read as string constants; the codebase-memory CLI index. No test, run, install, model call, AWS
action, dispatch, canary or E2E; both boxes untouched; the STOP before #5 kept; the preserved #5 draft unapplied; `9c19cc2`
never applied; Codex's two reserved modules (`frankie_box_experiment_dipole.py`, `frankie_box_experiment_search.py`) untouched.

## What was built, by slice (the detail is in the step-4 report section 8; this is the Claude-side map)

- A follow-ups (`frankie_box_experiment_exchange.py`): `science_turn(..., origin=)` consumes the BOSS seat's computed
  `origin_evidence_accounting` in its own record before `D.parse_teacher` (checks unresolved, never in `compared`/findings);
  `origin_evidence_accounting` prose carries the shared route's zero/unclassified limitation, formulas unchanged; listed
  origin rows are taught in both turns and the lawful Frankie reply, named as identified discovery evidence or not
  identifiable, never marked tested.
- B (`frankie_box_historical_claims.py`, new `frankie_box_historical_reproduction.py`, `frankie_box_scientific_teacher.py`,
  the exchange, `frankie_box_teacher_knowledge.py` identity): `REPRODUCTIONS` binds each crosswalk claim's original
  calculation to code at its exact revision (every sha256 verified from history here, never on the box): `crypto_trend_flip`
  (H01/H02, defined: all inputs committed at bb28b35e), `crypto_harness` (H01/H02, missing_inputs: realbins/), `ng_leg_fingerprints`
  (H03/H04/H05/H09/H10, missing_inputs: S3 NG MBP-10 + regime caches; recorded output fingerprints.json@21df8f14 bound by
  path+revision+sha, not in the catalog), `memory_a_retired` (H06-H08, not_bound: Greg 2026-10-06). `REFORMULATIONS` names
  what a repair/reformulation needs per claim; the decisions are Greg's. The capability does stage/plan/run/compare/record
  and a hash-bound `records_for`; `run()` refuses without the exact authorization literal; nothing calls it. The teacher
  attaches bindings per claim (frozen into claim_inputs) and READS the reproduction status from records under
  `<work>/reproduction/`; `reconsideration` counts bindings/records/needs; the exchange keeps a `performed_*` status that
  comes with a hash-bound record. The committed claims file is byte-identical.
- C (`frankie_box_teacher_knowledge.py`): `teach_accumulated` reads the owner's manifest up front and runs the reader's own
  `completed_native_evidence` once for the owner, so every accumulated result of the day (candidate-only lessons included)
  carries `completed_native_evidence.by_day[day]`; the exchange's `context_checks` then cite it in both seats. Every
  existing consumer of the completed native products is classed in the report (computed by the search: GROUP_CLOSE rows;
  selection gate: the receipt; everything else packaging/citation/presentation; 4.2 and 4.4 await Greg's two definitions).
- D (`frankie_box_boss_session.py`, `frankie_box_teacher_knowledge.py`, the exchange): every prices row and structures row
  of `Session.derive` gains a nested `provenance` (schema `FRANKIE_ROOT_ROW_PROVENANCE_V1`): prices `input_index` /
  `instrument_id` / `legacy_row_ordinal`; structures `input_cursor` / `instrument_id` / `input_record_indices` (None when
  frame sections are not retained). Calculation outputs unchanged. The legacy recovery identity, the completed-stage
  identity, the derivation receipt and both legacy layer dicts name the schema (older saved state refuses; an older spool
  without the key is explicit). The exact row contract and joins are in the report for Codex's adapter. Late-arriving
  knowledge is LISTED at both frozen boundaries (`inputs.json`, `learner-knowledge.json`) into the RECEIPTS only, never into
  the frozen files or the hashed exchange documents. Native-learner plumbing traced, not built: the three decisions block it.

## What the next Claude session does

1. Start from the drop-in box. Fetch both branches; rebase onto Codex's current tip (the last dry run was clean; Codex's
   post-merge commits touch only the reserved search module and the shared documents). If Codex edited an owned module,
   read its diff before touching that module.
2. Read `CCODE_NEXT_SOURCE_TASKS_20261006.md` top section: Codex's integration review of the four returns lands there.
   Fix every source defect it names in the owned files, one `[skip ci]` commit per finding group; do not reapply anything
   Codex already integrated.
3. The provenance handshake: answer Codex's questions on the row contract; the search adapter (including excluding
   `provenance.*` from channels the way `EVENT_IDENTITY_FIELDS` are excluded) is Codex's.
4. Nothing else is assigned. Do not open or invent a slice. If the task doc assigns more, trace first, build only within
   settled contracts, update step-4 report sections 8/9 and the CCODE handoff, push.

## Open decisions (Greg), unchanged and now named in code

REFORMULATIONS needs: a threshold numeric state (H01, H03), a windowed |imbalance|-falling transform (H02), the pre-entry
window on the F_LAST axis (H01/H02), a LEG/SIDE definition and the roll20-vs-Lee-Ready construction transfer (H03), a numeric
flat-flow bar the source never states plus an entry definition (H04/H05), a turn definition and an entry-to-peak depth change
(H09/H10). The 4.4 pair-completion owner; a 4.2 two-point step definition. The three native-learner decisions (retained
starting state; objective + auxiliary weight; cross-lane lineage). The late-scheduling decision. The 52.9 MB claims file;
the principal_inputs catalog. Memory A: retired, recorded (H06-H08 `not_bound`).

## Traps met this session (so they are not met twice)

- The Bash working directory drifts between calls (environment updates reset it); use absolute paths or a leading `cd`
  in every command.
- `python3` edit scripts with several string replacements: when one assertion fails, the earlier replacements have
  already been written. Check `git diff --stat` before assuming nothing landed; amend only an unpushed commit.
- The codebase-memory MCP tool call times out at 60 s on this repo; the CLI (`codebase-memory-mcp cli --quiet --json
  index_repository`, JSON on stdin) completes in the foreground in minutes. `.cbmignore` re-includes `deploy/`.
- The pinned recalculation producer (`a_memory_member_first_recalculation_20260828.py`, `describe_structure`) is NOT in this
  tree or its history: `Session._producer_module` loads it from the pinned producers checkout. Do not grep for it here.
- The revision `b4f364f0` of the Memory A catalog sources is not in this clone; their sha256 come from the catalog.
- A future `frankie_box_historical_claims.py --out` run refuses to overwrite the committed claims file because its own
  `builder_sha256` changed. That is the builder's guard. The committed file is current; nothing is rebuilt under the hold.
- `frankie_box_experiment_search.columns()` flattens every scalar leaf: the new `provenance.*` identity fields would be
  channels on a NEW ROOT until Codex's adapter excludes them (the frames' `input_cursor` has the same standing today). No
  search runs under the hold; the hazard is named in the report for Codex.
- Anything written into `full` in `exchange()` enters the exchange hash and the write-once documents; a value that may
  change across restarts (late knowledge) belongs in the receipt (`notes=`), or a restart declines its own bytes.
- The session-start hook warns that the NG data plane is not restored (no AWS credentials). That is expected for this
  source-only work; nothing here needs `data/` or S3.
