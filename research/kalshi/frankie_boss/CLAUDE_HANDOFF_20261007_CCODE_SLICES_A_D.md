# Claude handoff, 2026-10-07: the CCode pre-#5 queue, slices A-D returned (source-only session)

This is the Claude-side handoff. The Codex-facing record is separate: `CCODE_STEP4_SOURCE_ROUTE_20261006.md` (sections 8-9),
`CCODE_HANDOFF_20261006_TEACHER_TASKS_NEXT_CHAT.md` (top section) and `CCODE_DROP_IN_20261006_NEXT_CHAT.md`. Do not merge the
two channels: Codex integrates from the CCODE documents; a Claude session starts from `DROP_IN_CLAUDE_20261007.md`.

## Where things stand (updated 2026-10-07, eighth session: the Step 8 remainder returned)

Greg (through Codex's `1a3e1024`, then the 02:35 ET addendum `2f0d4522`): CCode owns the rest of Step 8 and, with it, the
runner, the queue and the ledger, plus the assigned school/ROOT/Jev/voice callers. This branch was rebased onto Codex's
`78f5563d`, then `7f08d76e`, and at the end onto its current `d6af990c` (no owned file touched by Codex meanwhile). Returned, one commit per
group (the record: `CCODE_STEP8_REMAINDER_RETURN_20261007.md`): `456a006a` the three 8A findings (lease freshness at every
effect boundary, the durable unknown resume reconciled through the worker, every unsuccessful outcome nonzero) | `23e3afae`
the owner contract (one binding per day: attempt, source, exact CPUs, booking, day-bound marker; the class child's
acknowledgment; the ledger retains an owned booking on reap; save/status/resume through the queue) | `4272f949` the
run/day scope on every worker, kick and handover and the controller's `--days` | `8af0a0b8` `previous_of` persisted,
teacher knowledge bound to its producer identities | four review passes (46 findings) | `bfae4460` the school consumer on
Codex's `retained_school`, the non-reentrant `waiting_school` recovery (the one granted branch of `successor_dispatch.drain`),
Jev's day on the held CPU lane (`JEV_CPU_REQUEST_V1` persisted before dispatch, `jev` a day-run stage, receipt/status bound
to the request) | `b4c60a4d` the acknowledgment bound to the save request's identity, the kick's scope comparison |
`df51afb0` the review pass over the addendum commits | `cf1f1f2c` the shared-market policy of a NEW run on `Run.root`/plan
and `Run.teacher` (Codex published the producer at `d6af990c` while this session ran) | `24df7810` `35718474` its two
review passes | the docs commits (tip = the docs commit (reported in chat)). Checks: `ast.parse`, `sh/bash
-n`, `yaml.safe_load`, `git diff --check`; nothing run, no AWS, no dispatch.

Design choices of this round, not to re-litigate: the owner binding is written by the queue BEFORE the day's thread starts
and the Run reads its own marker (never a process-global variable); exit 75 is saved only on the day's own standing
marker, with the class child's written acknowledgment (a SIGTERM path, a vanished child or a missing receipt is unknown,
never saved); the ledger RETAINS an owned booking whose holder died instead of releasing it, and only the owner takes it
back in place (an orphan on the CPUs refuses the takeover); a failed (never saved) day gives its binding up so the
once-per-worker retry is what it was; a kick without a scope starts nothing; a worker never touches an entry outside its
scope and never starts an out-of-scope predecessor (the eligible day waits); the Jev request is written once and reused
byte for byte, a differing retained request is refused, never re-minted; the school consumer reads the checked chain and
never the bare index row, and a successor that needs its corrected meeting waits rather than failing the child; the
shared-market policy is a NEW run's plan field (a run keeps one plan; a legacy ROOT or teacher result is refused and
preserved under it, never recomputed or relabelled); the one caller whose contract is not published (the remote voice
admission) is a named dependency, not a guess.

What a next Claude session does: Codex's review of these commits lands in the task doc; fix what it names in the owned
files, one commit per group, the code-review skill over the range before every push; wire the remote voice admission only
once its contract is on Codex's tip; nothing else is assigned.

## Where things stand (updated 2026-10-07, seventh session: Step 8A returned)

Greg, at the start of the session: "Don't mess with old work. Just focus on step 8. Just do step 8A." Codex had fixed the
sixth-return findings directly and landed `3a1416b7` with the Step 8A assignment (task doc top section). This branch was
rebased onto it (every earlier commit was already integrated, so the rebase left nothing above Codex's tip), the index was
rebuilt, and the slice was returned, then rebased once more onto Codex's current `439cb0bf` (three step-5 commits, no 8A
file touched): `bc178ff3` the controller's lifetime on the main box plus launch prerequisites and
controls (`pod_root/controller.py`, new `deploy/aws/box/frankie_box_cpu_controller.sh`) | `bd28796e` the reachable Pod routes
of `frankie_box_run.yml` closed, the marker refreshed | `bdf7122b`, `cdeb61ce` the two code-review passes (17 + 10 findings)
| the docs commit (tip). Record: `CCODE_STEP8_CPU_CONTROLLER_20261007.md`; pointer in the step-6 return section 10.
Checks: `ast.parse`, `compile`, the static import and call checks, `sh/dash/bash -n`, `yaml.safe_load`, `git diff --check`;
nothing run, no AWS, no dispatch. The four step-6/historical modules untouched; boundaries unchanged.

Design choices of this round, not to re-litigate: one controller, two hosts (the runner bounded, the main box a run-bound
systemd unit with `--budget-minutes 0`); main-box actions run locally under `/bin/sh` with the SSM preamble, the worker over
SSM; the state directory is the controller's record (write-once identity per start, per-poll status, an event journal,
request/acknowledgment pairs for stop and resume, an outcome per start, never 'complete'); one controller per run by a
host lock and an ETag-conditional S3 lease, a lost lease ends the loop; a stop is a request that relays the worker's save
and acknowledges the pending state, claims untouched; a resume under a live service is a request to the service; a day
that failed to start twice ends the service as `blocked_by_start_failures`; exports go one file per call and inputs are
re-signed on every renewal because the main host signs with the instance profile's session (the worker does not refresh
URLs mid-fetch: a limit, named, with the retained-bytes resume behind it); the provider path left the controller and the
workflow refuses the Pod scripts before any step; the instance profile's permissions are named, checked by preflight and
never provisioned.

What a next Claude session does: Codex's review of these commits lands in the task doc; fix what it names in the owned
files, one commit per group, the code-review skill over the range before every push; nothing else is assigned (the main
lanes' save/resume, Jev, the reader hooks and scheduling are Codex's; the instance profile is Greg's decision).

## Where things stand (updated 2026-10-07, sixth session: Codex's fifth-return review corrected; two review passes)

Codex reviewed the fifth return (task doc "ACTIVE review of fifth-session return": BIND-F, B4-F, 6R3-F, 6R2-F) and
landed `5e216265`. This branch was rebased onto it and returned, one commit per finding: `12258b3b` BIND-F,
`7dd8b9a4` B4-F, `34dab141` 6R3-F, `4b5a8eba` 6R2-F. Greg: "this has to be the last correction", so the code-review
skill was run adversarially over the whole range at high effort, twice; its 20 findings are fixed in `62eb55e3` and
`6c804bd2` (the gravest was an `import http.client` line built by the 6R3-F edit script and never applied). Record:
`CCODE_STEP6_RETURN_20261007.md` section 9; step-4 report sections 8/9. A third pass was not run (Greg: commit and push). Pushed as `889120af`; Codex's integration tip moved to `c816bc56` (step seven) meanwhile, so the next session rebases first.
Checks: `ast.parse`, a static check that every dotted module used is imported, `git diff --check`; nothing run.
Boundaries unchanged: reader hooks Codex's, pins and threads null untouched, `9c19cc2` never applied, no cost reference.

Design choices of this round, not to re-litigate: identity V3 is per entry and JSON-stable, with V2 converted and
equivalence reported as unestablished rather than inferred; a request that never reached the socket is not a pending
call; attempt records are clock-free and write-once; evidence is content-addressed per attempt.

What a next Claude session does: Codex's review of these commits lands in the task doc; fix what it names, one commit
per group, and run the code-review skill over the range before pushing; nothing else is assigned.

## Where things stand (updated 2026-10-07, fifth session: Codex's review round returned)

Codex reviewed the step-6 return (task doc "ACTIVE review of fourth-session return") and landed the step-5 correction
reader (`97405c29`, `3bc72da8`) with Greg's 22:46 ET ownership update: the reader hooks in `teach_accumulated`,
`accumulated_lessons`, direct lesson loading and both `learner_school(stage='exchange')` call sites are CODEX's now; do
not build them. This branch was rebased onto `3bc72da8` and returned six commits, one per finding: `588c9c7f` 6R1,
`1d9a1cbf` 6R2, `d52237d3` 6R3, `6837875a` B2-R, `bf8f87a5` B4-R, `0cb6868b` BIND-R, then this documentation. Record:
`CCODE_STEP6_RETURN_20261007.md` section 8 (including the scientific-owner publication/successor interface trace Codex
asked for; nothing built, no lesson labelled a correction). Greg's instruction this session: run the codebase-memory index
BEFORE any code change; done (the first retry aborted under the rebase; the second published generation 02:41:28Z and
was used for the callers of every changed function). Boundaries unchanged; nothing run; pins and threads null untouched.

Design choices of this round: evidence is content-addressed and per-attempt (`evidence/<sha256>-<label>.bin`,
`llama-server-stderr-<attempt>.log`, `evidence/attempts/<attempt>.json`); the binding is checked against the computed
input bytes before `meeting-input.json` is touched; `_post` returns (parsed, raw) with per-endpoint shape validators;
`aggregate_status` is the one place a comparison status comes from; the dispatch marker is parsed in `coherence`;
`binding_identity` is V2 and `binding_identities_differ` never infers equality from an incomplete identity.

What a next Claude session does: Codex's review of these six commits lands in the task doc; fix what it names, one
commit per group; the reader hooks stay Codex's; the publication/successor interface is a request until Codex schedules
successors; weight learning stays Greg's decision.

## Where things stand (updated 2026-10-07, fourth session: step 6 and the B2-B5 follow-ups returned)

Greg assigned CCode STEP 6 (the bounded Granite meeting source/recovery path) plus B2-B5 follow-ups (task doc, "ACTIVE
assignment, Greg 2026-10-06 22:11 ET"); Codex continues step 5 and the exact-price adapter. This branch was rebased onto Codex's
integration `6c033cd5` (which integrated the return through the pre-rebase `ecd8720e`); the two newer commits (step-5
direction `73288615`, docs `cb458a0d`) stayed above it. Returned, one commit per group: `e922a6e2` step 6 findings 1-3
(deadline through every request, durable per-item progress with explicit interrupted calls, whole evidence and process
release), `b3fb5a26` finding 4 (workflow inputs as environment variables, return.json witness, the owner import named),
`2f1d6630` B2-B5 follow-ups, then this documentation. The step-6 record, the weight-learning answer (inference-only; the
smallest concrete path and the decisions it needs) and the interface requests to Codex-owned files are in
`CCODE_STEP6_RETURN_20261007.md`. Boundaries kept: source only, nothing run, pins and threads null unchanged, `9c19cc2`
never applied, the deleted historical binding deleted, H06-H08 not_bound.

Design choices of this session: the meeting's recovery state is `meeting-binding.json` (write-once) + `progress/<item>.json`
(durable, every completed round, a pending chat marked before it is sent) + `evidence/` (whole stderr and every failed or
malformed reply); `meeting.json` is written only when the meeting completes, so Codex's `read_meeting_record` is untouched;
the new receipt status `runtime_failed` and the open-item kinds `time_budget`, `interrupted_call`, `call_failed` are the
only new words consumers meet (requests 1, 2 and 5 of the return). `plan()` is now `plan_document()` + a write; `record()`
refuses an incoherent operation; a broken frozen record raises.

What a next Claude session does: Codex's review of these commits lands in the task doc; fix what it names, one commit per
group, same boundaries. The weight-learning decisions are Greg's; do not implement training or touch the hash gate.

## Where things stand (updated 2026-10-07, third session: the correction queue returned)

Codex's integration review of A-D landed as an ORDERED correction queue at the top of `CCODE_NEXT_SOURCE_TASKS_20261006.md`
(D1; B7/C2; B2-B5; B1/B6/A4/C1), in Codex's `19f72f47`. This session rebased clean onto it and returned one `[skip ci]` commit
per group: `18b6edcd` D1, `8930b4f0` B7/C2, `5fdc14f5` B2-B5, `45f52d28` B1/B6/A4/C1, `6002a926` docs, then `602e29f6`
(B7 by deletion, Greg: no cost references, see below); tip `602e29f6`, pushed, worktree clean, scratchpad empty. Everything
SOURCE-BUILT / RUNTIME-UNVERIFIED (`ast.parse` without project imports, `git diff --check`, the codebase-memory CLI index);
nothing run, no reproduction called, the claims file byte-identical, Codex's two modules untouched, STOP before #5 kept.
The per-finding record (what each correction does, the D1 field/unit table for Codex's price adapter, what stays open) is
the step-4 report section 8 "Corrections after Codex's integration review" + the section 9 table; the Codex-facing summary
is the new top section of `CCODE_HANDOFF_20261006_TEACHER_TASKS_NEXT_CHAT.md`. Greg, mid-session, twice: no reference to
transaction costs belongs in market-conditions work. So B7 is closed by DELETION, not by framing: the `crypto_harness`
binding is gone from `REPRODUCTIONS`, the admission table that `8930b4f0` had built around it is gone, and no field, status
word or sentence about it remains in any owned module. Do not reintroduce one.

Codex then pushed `19f72f47` (docs only): Greg's step-5 direction, canonical in the opening section of
`SPEC-experiment-orchestrator.md`. Applied to the owned consumers in `b5d0fe74` (the current tables decide; a frozen
binding is superseded in both seats and Frankie's reply); the exact propagation gaps are in the step-4 report section 8.
This branch was rebased onto `19f72f47` (hashes above are post-rebase) and force-pushed with lease, as the drop-in prescribes.

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
