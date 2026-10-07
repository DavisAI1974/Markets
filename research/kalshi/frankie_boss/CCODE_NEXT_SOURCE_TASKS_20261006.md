# CCode assignment — next pre-#5 source tasks

## Ownership update — Greg, 2026-10-06 22:46 ET

Greg asked Codex to handle the step-5 reader hookups while CCode continues step 6.
Codex now owns ONLY the correction-selection hooks in `teacher_knowledge.teach_accumulated`,
`experiment_exchange.accumulated_lessons` and direct lesson loading, plus the two
`learner_school(..., stage='exchange')` call sites. Do not duplicate those hooks.
CCode keeps 6R1–6R3, B2-R/B4-R/BIND-R and the scientific-owner publication/interface trace.
The latter's historical binding functions are separate from Codex's reader changes.
Fetch the reader commit before your final integration; preserve both sets of changes.
This supersedes the earlier instruction assigning those small reader hooks to CCode.

## ACTIVE review of fourth-session return — 2026-10-07

Codex fetched and integrated `276d60738c88c2aaf1384fe73b5606faa2e36b8a`, above
`6c033cd5`, preserving all returned history. Read this section before the older assignment.
Your step-6 implementation and B2–B5 follow-ups are received, not an instruction to redo them.
B3's complete plan reconstruction and B5's selected-file refusal address the named findings.
B2's per-output coverage is improved; B4 and step-6 recovery still have defects below.
The deleted historical binding stays deleted. Granite remains inference-only: your answer
and proposed separate weight-learning path are received; training decisions remain Greg's.

Codex has implemented your consumer requests in the follow-on source commit:
the existing stable per-day OUT_DIR is retained;
`runtime_failed` is read through a receipt bound to the exchange, meeting binding and input
bytes, and becomes non-blocking `waiting` in the runner/queue. An unrelated child failure
cannot reuse an unchanged old failure receipt. School/day reports already render open-item
kinds generically. No automatic artifact download/import or training is added.

Fix these SOURCE findings in your owned files, one `[skip ci]` commit per coherent group:

1. **6R1 — terminal-turn recovery (`discuss_item`).** After a valid LEAVE_OPEN/RESOLVED,
   the round is saved with `pending_call=None` and increased `rounds_completed`, but the
   terminal outcome remains only in a local variable until the later final save. Interruption
   between those saves resumes another chat instead of retaining the terminal result. Save
   terminal outcome/result atomically with the completed round and consume it on recovery.
   Also check a retained `over_cap` before sending any new request. Recovery must not repeat
   work whose completed disposition is already retained.
2. **6R2 — immutable retry evidence (`LlamaServer.retain/start`, `_meeting`).** Evidence
   numbering resets on each process; repeated labels reuse `001-...bin`, invalidating earlier
   progress witnesses even though the durable writer retains old bytes elsewhere. The single
   stderr file is appended after its old hash was recorded. Use immutable, attempt-qualified
   or content-addressed evidence paths and retain the prior attempts' witnesses in the complete
   record. Validate retained meeting binding BEFORE replacing `meeting-input.json`; a rejected
   changed-input retry currently changes the file the old binding names. Preserve old pinned
   inputs/evidence and refuse incompatible retries without mutating them.
3. **6R3 — complete request failure handling and deadline.** `_post` drops original raw bytes
   after parsing JSON. Missing `prompt`/`tokens`, a list instead of an object, or malformed
   `usage` can raise KeyError/AttributeError/ValueError outside MeetingCallFailed. Health JSON
   can do the same before `_meeting`'s stop/finally is entered. Keep the entire original
   response bytes for malformed shapes, validate each endpoint's required shape, close the
   item explicitly and release the process on every startup failure. The socket timeout is
   an inactivity timeout, not a total response-read deadline: keep the absolute remaining
   meeting deadline effective while reading successful AND HTTP-error response bodies.
   Preserve whole received bytes/partial evidence; do not introduce truncation. Keep all
   settled limits and pins. Distinguish attempt counters from complete-meeting counts when
   reusing prior rounds; zero calls in this attempt must not imply no prior model work.
4. **B2-R — aggregate comparison coverage (`compare`).** A matched output plus a declared
   JSON output with `not_comparable` (missing reference, disappeared produced file or no
   aligned members) still yields `performed_matched`: the final `comparable` filter omits
   the gap. Keep matched scope separate from all declared comparable-output coverage, and
   propagate incomplete coverage into the record summary. Prose-only declarations remain
   explicitly non-comparable; do not invent measurements for them.
5. **B4-R — operation semantics, not just file hashes (`coherence`, `_admit`, `record`).**
   The dispatch bytes are hashed but never parsed against entry/plan/run. A dispatch for a
   different operation can therefore satisfy the current chain by copying its hash. Validate
   dispatch schema, entry, plan hash, command/cwd, authorization and run correspondence.
   Admission/record must also compare the plan's current command, comparison declarations,
   binding-table/capability identities and declared inventory, not only claims/pins. Make
   comparison status follow its retained output statuses/coverage; a self-consistent pair
   of summary strings is insufficient. Do not call `run()` or regenerate evidence.
6. **BIND-R — historical binding correction completeness.** `binding_identity` compares
   only status, entry IDs and source pins; it omits input pins, command and comparison
   declarations. Exchange can therefore preserve a prior performed status after those
   parts of the binding change. Carry the complete per-entry semantic binding identity
   through the lesson and both-seat consumers. Older incomplete identities must say what
   is unestablished; don't infer equivalence or retire unrelated knowledge by table age.

Continue the six owned correction groups. The step-5 reader handshake below is now available
in the follow-on source commit: fetch CURRENT integration before building those hooks, and
trace and return the scientific-owner publication/successor interface. This is
continuation of the assigned work, not a new slice.
Do not edit Codex's brain/lane-state/runner/queue/review/search/dipole modules. Update your
step-6 report, section 8/9 of step-4, and Claude/CCode handoffs/drop-in; push. Source review,
AST without project imports and whitespace ONLY. No tests, runtime, training, installations,
data access, reproduction, AWS, starts, dispatch or E2E. Keep pins/threads null and the old
draft unchanged; never apply `9c19cc2`. Fetch CURRENT integration before editing.

## Step-5 consumer handshake for your existing B5 correction

Codex has landed the shared correction reader and `STEP5_CORRECTION_DELIVERY_20261007.md`
in the follow-on source commit. The signatures below are available for your owned hooks.
Keep your step-6 work and the B2–B5 fixes below; the following hooks belong in your existing owned
teacher/exchange files. Do not edit Codex's new `frankie_box_experiment_review.py`, brain, lane-state,
runner or search files.

- In `teach_accumulated`, call `LS.require_current_selection(input_path, brain=brain)` before
  reusing retained `inputs.json`. In `accumulated_lessons`, call it before reusing retained
  `learner-knowledge.json`. Preserve those immutable files; a refusal names the need for a checked
  successor, not permission to change their selected bytes. Direct standalone calls need this
  check even though the experiment runner now performs it at its own boundary.
- Both owned `LS.learner_school` calls use the exchange boundary: pass `stage='exchange'`.
  The default stays `classroom` for the existing classroom caller and its own-day answer wall.
- For directly supplied lesson paths in standalone exchange use, resolve them through
  `REVIEW.current_document` with the exact source content/path/bytes/hash,
  `REVIEW.corrections(LS.knowledge_roots(brain))`, `brain`, `day=day`, `stage='exchange'`.
  Preserve the returned actual path/hash. Codex already does this for runner-supplied paths.
- Trace the actual scientific-owner completion point that can call `record_correction` after
  a demonstrated error or a researched scoped replacement. Return the exact remaining successor
  scheduling interface; do not automatically label a newer/conflicting lesson as a correction.
  Partial replacements preserve all unaffected values; full replacement is explicit. No training,
  execution, guessed scientific criterion or new slice is authorized by this handshake.

## ACTIVE assignment — Greg, 2026-10-06 22:11 ET: step 6 plus return corrections

Codex fetched CCode `ecd8720edfe3078810925443a061c8bb1e07b83a` (including `c94dcac0`)
against integration `19f72f473a1156bac4bdc1cad87d63680347a1c2`. These are different branches,
not competing checkpoints. The returned correction commits are integrated with their history;
do not reapply A–D or the returned corrections. Fetch CURRENT integration before your next edit.
Greg explicitly assigned CCode step 6; Codex continues step 5 and the exact-price adapter.
This section supersedes older “nothing else assigned” statements and the CCode step-6 hold.
Source-only boundaries still apply; this is not a runtime authorization.

### 6. Finish the bounded Granite meeting source/recovery path

Read `GRANITE_INTEGRATION_RECOVERY_20261006.md` first (the named brain/queue/school/report/
owner-import wiring is ALREADY built), then `CCODE_HANDOFF_CODEX_GRANITE_RUNTIME_20261006.md`,
`CCODE_GRANITE_FACILITATOR_20261006.md`, `GRANITE_DISCUSSION_REPORT_20261006.md`, the role V2
charter and `knowledge/GRANITE_MEETING_RUNTIME_V1.json`. Trace current source, not old line numbers.

Own `frankie_box_granite_meeting.py`, its launcher/setup scripts, and
`.github/workflows/frankie_granite_meeting.yml`. Own a new `CCODE_STEP6_RETURN_20261007.md`
report. Codex reserves brain, lane-state, experiment runner, search/dipole and shared handoffs
while step 5 is in flight. Return any needed change to those files as an exact interface request.

Concrete source findings to fix within that ownership:

1. **Meeting deadline:** `_meeting` checks its deadline only BETWEEN items; `discuss_item`
   can perform six rounds, each with three HTTP requests whose timeout is 600 seconds.
   Carry the remaining meeting budget through every turn/token-count/chat request. Preserve
   the current item's completed work and list it plus every unreached item explicitly open
   when the budget expires. Use the settled 3000-second parameter; do not tune or replace it.
2. **Interrupted-call recovery:** completed meetings reuse correctly, but an interruption before
   `meeting.json` is complete loses completed turns/items and a retry can replay them. Retain
   source-bound per-item/turn progress through the existing durable writer, bind the exact
   exchange/config/charter/rules inputs before calls, and reuse completed work. An interrupted
   call with unknown completion must be explicit; no silent duplicate call or invented answer.
   Source-only implementation; do not invoke a stub or the real runtime to exercise it.
3. **Whole evidence and cleanup:** malformed coordinator output is sliced to `raw[:2000]`;
   startup stderr is sliced and a live server's piped stderr is not drained. Preserve complete
   raw call/error evidence by durable file witness where needed, with no content truncation.
   Ensure server startup failures and request failures release the ephemeral process while
   retaining partial meeting state. No new logging or validator framework.
4. **Runner return contract:** trace the existing artifact/optional PUT to the existing owner
   import. Document exact returned file/hash and missing orchestration, without implementing
   an automatic dispatch or choosing the first E2E host. Put workflow inputs into environment
   variables before shell use (current GET/PUT URLs are interpolated into shell source).
   Keep dispatch-only and inputs-only defaults; no new permissions or services.

5. **Greg's 22:12 ET weight-learning question:** the current `LlamaServer` is inference-only;
   `gate` rejects changed GGUF bytes and there is no optimizer, training feedback or learned
   checkpoint path. State this plainly in the return. Trace any existing suitable learning
   machinery and propose the smallest concrete path for Granite to improve its coordination
   from checked feedback, including retained state and recovery. Distinguish conversation context,
   retained lessons and actual weight updates. Identify the feedback/objective decisions still
   needed; do not invent them, relax the model hash gate, implement training, or run anything on
   the strength of this question. Keep Frankie's separate native learner out of this assignment.

Keep Granite the bounded post-class coordinator with zero evidentiary weight. Requests stay
requested until a code seat actually performs them. Preserve all four record categories,
source/answer walls, non-blocking runtime refusal and immediate owner publication. Pins and
all confirmed parameters are unchanged, especially `threads: null`. Accumulated-content scope
beyond the existing label/hash index and first E2E host remain Greg's decisions. Do not reopen
model selection, restore old roles, expand to a fourth lane, or reimplement completed wiring.

### Corrections still required from the returned pre-#5 queue

These are source-traced findings in the NEW return, not a request to replay earlier work.
Keep ownership of the historical/teacher modules and one `[skip ci]` commit per finding group.

| Finding | Current defect | Required correction |
|---|---|---|
| B2 follow-up | `_aligned` lists unmatched members but removes them before `_compare_json`; the latter can say `matched` when only the intersection matches. `produced_only` leaves and alignment gaps do not affect that status. | Preserve every gap and separate matched comparable scope from incomplete coverage. No whole-output `performed_matched` when declared comparable evidence is missing/unmatched. Do not invent a tolerance or scientific verdict. |
| B3 follow-up | `run()` checks the written plan against the supplied plan and rederives one executable boolean, but does not bind its command, pins, comparison declarations or capability/table hashes back to the CURRENT declared entry. `verify_staging()` only verifies the rows present, not that all declared rows exist. | Reconstruct/compare the complete declared plan and source/input/reference inventory before dispatch or reuse. A self-consistent altered/stale plan or incomplete inventory must refuse, even when its executable flag agrees. |
| B4 follow-up | `_admit` hash-checks plan/run files independently but never requires their entry IDs to equal the record's entry, `run.plan_sha256` to equal the admitted plan, or performed success to agree with returncode/timeout/dispatch. `record()` accepts that same unlinked combination. | Bind record → declared entry → plan → dispatch → run → comparison. Require coherent schemas/identities and status facts; a failed/timed-out run cannot be admitted as matched. Retain every performed status, including failures; no fabricated execution evidence. |
| B5 follow-up | `records_for(selection=...)` lists a selected missing/changed record and continues, changing the scientific evidence behind frozen inputs. | Refuse preparation/reuse on a selected missing/changed file. Continue to list genuinely new, unselected arrivals separately. Do not treat a broken selected pin as an optional absence. |

B1's removed caps, A4's discovery identity before arithmetic, C1's content-vs-path identity,
and the returned market/context classification are retained. B6's exact unsupplied-input gap
remains open; no data access is authorized. The deleted historical binding stays deleted.
D1's V2 originating INPUT contract is received; price placement belongs to Codex, not this task.

### Knowledge rule for both assignments

Older lessons remain available. Age is never a reason to retire them. Only conflicting knowledge
about the SAME thing calls for that conflict's research: determine whether circumstances explain
the difference, whether part needs replacing, or whether evidence establishes full replacement.
An unresolved conflict keeps both accounts and their scopes available. A researched partial
replacement keeps ALL unaffected knowledge available; full replacement is never the default.
This is distinct from fixing a demonstrated source/calculation error. Do not invent a recency
winner, automatic obsolescence, global lesson deletion or a scientific replacement criterion.

Return the step-6 source changes and exact remaining consumer/transport requests in the new report;
update the existing step-4 report sections 8/9 for B2–B5 fixes and your handoff. Do not edit this
shared assignment or Codex-owned files while Codex is working. Checks: source/interface review,
`ast.parse` without project imports, `git diff --check` ONLY. No tests, setup, download, model/data/
project runs, historical reproduction, AWS calls, starts, dispatch, canaries or E2E. Keep the
preserved draft unapplied; never apply `9c19cc2`. H06–H08 stay historical/not_bound.

## Greg's step-5 correction direction — 2026-10-06 21:53 ET

Greg has now discussed #5: check and correct the market research and get corrected knowledge
into Frankie promptly. No maker/taker fees, execution-cost assumptions or profit objectives
in calculations, parameter selection, confirmation or teaching. Dates/day/IDs retain their
search/grouping role; underlying market conditions supply the signals.

For the EXISTING owned correction queue, especially B7/C2/B4/B5/C1: trace affected calculations,
findings and lessons, and ensure known-wrong content cannot stay active merely because it was
frozen or recorded. Carry checked corrections to both teachers and Frankie's actual inputs via
existing knowledge/recovery paths. Do not merely append a warning while continuing to use a
known-bad conclusion. List propagation gaps precisely if the current interface does not support
the correction. Preserve raw source evidence and truthful identities; no deletion, retroactive
rewrite of predictions, new retention framework or implicit scientific rerun is authorized.
Source fixes do not themselves establish recalculated historical results.

The canonical contract is now the opening section of `SPEC-experiment-orchestrator.md`.
This clarification applies to your currently assigned files; it does not assign a separate
step-5 implementation slice or Codex's reserved search/dipole modules. Keep the current order
and disjoint ownership. Do not apply the old draft or `9c19cc2`; open mathematical decisions,
Granite pins, Memory A retirement and every execution hold remain. No tests/runs/AWS.

## Current assignment after refetching CCode `d3945e13` — 2026-10-06 night ET

Fetched integration `e697d52e` and CCode `d3945e13f48194c5a6bcf7cecfd89515fd270158`.
The only return since `fea2e165` is Claude-side documentation. A-D source is already
integrated; NONE of the correction groups below is closed by that documentation.
The new Claude handoff/drop-in's "integration review next" and "nothing else assigned"
wording is superseded by this existing, source-traced correction queue.

| Order | CCode-owned implementation | Required return to Codex |
|---|---|---|
| 1 | D1: actual originating trade INPUT identity through producer and retained open-group state | Exact schema/fields, index and ordinal units, receipt plus both recovery identities; name every necessary producer/state file. Preserve trade values/order. |
| 2 | B7 and C2: historical cost/profit contamination and both-teacher market/context distinction | Source-traced dependency/admission changes, actual arithmetic and explanation consumers, exact unsettled definitions. Preserve original audit bytes and searchable date/day/ID context. |
| 3 | B2/B3/B4/B5: immutable reference vs output, pre-dispatch identity, full admission/status, owner-local frozen selection | Full source/input/entry/operation binding and recovery behavior; no performed claim without the retained operation evidence. |
| 4 | B1/B6, A4, C1: complete evidence, original-input supply, discovery identity, native content identity | All retained evidence without caps; settled supply interface or precise gap; identity independent of arithmetic availability and local paths. |

This orders the existing queue; it creates no new slice or mathematical choice. Keep each
coherent finding group in a separate `[skip ci]` commit. B7/C2 may affect the binding semantics
that B4/B5 must freeze; reconcile them before claiming closure. Do not call reproduction or
other project code. Do not rebuild the committed claims artifact. Update sections 8/9 and
the CCode handoff with actual corrections and remaining dependencies, then push the return.

Before editing: fetch BOTH branches, inspect a clean worktree/current tips, and incorporate
the current integration branch while preserving newer work. Do not reset to any checkpoint or
reapply A-D. Codex retains `frankie_box_experiment_search.py`,
`frankie_box_experiment_dipole.py` and shared handoffs. The exact structure adapter and
provenance-channel exclusion are already built. The exact price adapter will follow a reviewed
D1 contract; V1 prices remain explicitly pending, never joined by timestamp/spool position.

Return only source/interface review, AST without project imports and whitespace results.
No tests, installs, project/model/data runs, AWS actions, dispatch or E2E. STOP before #5;
preserve its draft and Granite pins (`threads: null`); never apply `9c19cc2`.

## Greg's latest priority — market conditions only; temporal context retained (2026-10-06)

This clarification supersedes older instructions to use every scalar as a feature:
trade costs and non-market bookkeeping must not become market signals. Greg clarified:
IDs, dates and day-of-week CAN be search conditions/cells grouping actual market signals
to get forecasts. They are not numerical signals/targets themselves. The underlying
market conditions produce the prediction; date/day/ID labels group those conditions.
Keep dates, timestamps and day-of-week associated with the data and preserve causal
alignment. Do not turn identifiers/calendar numbers/availability codes into measured
market quantities, or use execution costs/profit as tuning objectives or scientific verdicts.
Retain market prices and bid/ask spread, signed flow, depth, FIFO rank/age, elapsed market
durations, market-positioning quantities and derived market geometry. Cost exclusion is
not a reason to remove a real market spread, or COT net positioning.

Codex's reserved search removes known bookkeeping/cost channels from series/cells, and
moves numeric IDs/calendar labels into categorical search cells after exact identity
placement/masks and before transforms/pair calculations. Date/weekday context cells use
the export-declared trading date, not an invented UTC day. Every excluded or moved
channel is named in manifest notes and source exclusions. Original pinned
records, timestamps, dates, hashes and weekday context remain untouched. Action/side bytes
become exact categorical values rather than arbitrary byte-number signals. Other encoded
bytes are context, not quantities. These changes do not settle every native/model consumer.

### B7 — remove cost contamination from the historical research path (priority alongside D1)

Confirmed source: `_info_dipole_harness.py`, SHA256
`c0adfc40dcc07e2e296daa26b5da9c4e20c7d00a6b34445df5ca1687e3222dda`
(the exact pinned historical driver, not a guessed successor).
`run_calls` subtracts the fee for each leg. `tune_and_score` selects its
`best` parameters by that fee-adjusted in-sample net, then computes OOS counts/timing
at those selected parameters. `SWING_THETA` is described as a tradable fee-floor
choice; `net_oos` and `net_oos_maker` enter the new `crypto_harness`
binding's `per_venue` comparison. Simply excluding those two output fields or
setting the fee to zero leaves a trading-profit selection objective and does not
establish independent market-condition research.

CCode owns historical_claims/reproduction and teacher consumers: remove this driver's
cost/profit-selected outputs from admissible market/Dipole research, including indirect
use of its selected params/counts as an independent market verdict. Keep the original
pinned source/results intact as explicitly identified historical context so we can explain
and rework the prior conclusions. No historical rewrite/rebuild, no rerun under the hold.
Revise the declared capability/record admission and both teachers' actual evidence use
accordingly. A byte-matched old cost-based run is not an admissible market-condition
reproduction. Already-existing rejected conclusions remain open for reproduction/rework;
their execution economics cannot be used to dismiss the market relation.

Trace linked drivers and their selection/labeling dependencies, not just the final fee
columns. Build only a source-traced market-only route using settled calculations. If a
cost-free research target/threshold/selection rule needs an undecided mathematical choice,
name that exact choice and leave it pending. Do not choose a gross-profit objective,
invent a turn/threshold, or silently relabel a modified calculation as the historical one.
The original whole-artifact evidence may be retained for audit without entering calculations.

### C2 — carry the same distinction through owned teacher/native/external consumers

Extend your current consumer review to non-market inputs: reference hashes, IDs, source
cursors, schema/receipt/transport metadata, availability/integrity codes, calendar/session
labels, trade fees/commissions/slippage assumptions and account/profit objectives.
Preserve their binding, mask and chronological functions. IDs/date/day CAN group actual
market signals as search conditions for forecasting; they cannot become signals/targets
themselves. Make that distinction in actual arithmetic and BOTH teachers' explanations,
not only in report prose. Dates/weekdays remain attached and searchable as context.
Attribute a forecast to the underlying market conditions identified within the group;
association with a weekday or ID does not make the label its scientific explanation.
Keep market-derived family classifications, actual price spreads and event durations;
never exclude a market value merely because a field contains `net`, `spread`,
`state`, `count` or `cost` in an unrelated domain such as energy production.
The external calendar source `calendar.sessions_since_prompt_expiry` is explicitly
calendar context; the reserved search moves numeric aliases into categorical cells while
retaining its original source. Trace the equivalent classroom/teacher route in your owned modules.
Return exact remaining classifications/interfaces; do not create a new validator framework.

All earlier A4/B1–B6/C1/D1 corrections and all execution holds below still apply.
No tests or runtime actions. Preserve the original claims artifact and Granite pins;
STOP before #5. Codex still owns experiment_search.py, experiment_dipole.py and shared handoffs.

## Codex integration review of A–D — 2026-10-06 late (supersedes closure claims below)

Reviewed CCode tip `fea2e165a3cf721760db0ac2932cf2c4ab0be859` on integration base
`80a0e2793e3cfb9cb8a2a06e03c08bed22d041fa`. Incoming implementation commits:
`c31cad06` A, `7cb2ce52` B, `11082ff8` C, `2a05c147` D; the later commits are handoffs.
Their source is retained in the integration, **not accepted as completed coverage or safe-to-run
reproduction**. All review below is static. No reproduction, teacher, search or data code was run.
Fetch the current integration HEAD before corrections; preserve newer commits and do not reapply A–D.

CCode: correct the following in your owned files, one coherent finding group per `[skip ci]` commit.
Prioritize D1 (the reserved price adapter blocker), then B2/B3/B4/B5. A's three earlier requested
corrections are present in source; do not redo them. Codex keeps search/dipole and shared handoffs.
Update your report sections 8/9 and handoff with each correction and its actual limitations.

### D1 — price provenance names the closing INPUT, not the originating trade INPUT

In `frankie_box_boss_session.Session.derive`, `adapter.apply(record)` returns `legacy_rows`
only when that instrument's event group closes. Source trace:
`research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`, `InstrumentBook.apply`, accumulates
each trade's control row in `_legacy_group_rows`; before F_LAST it returns an empty list; at the
close it returns the accumulated list. The new `prices.provenance.input_index=index` therefore
stamps the closing input on trades from earlier inputs. Its comment promising the original
record is false. `legacy_row_ordinal` is within the emitted GROUP's legacy rows, not the original
trade INPUT's emitted rows. Timestamp equality or spool position cannot repair this identity.

Carry the actual original INPUT index through the existing producer's trade-row construction/
retained group state. Preserve the existing numerical values and legacy row order. Bind the
corrected provenance semantics into receipt and BOTH recovery identities so old V1 mistaken
price identities cannot be accepted as corrected output. If an additional producer file is required,
trace it and name it in the return; that narrowly necessary producer correction is assigned to you.
Return the exact fields, schema/version, original-index units, row ordinal units and recovery contract.
Do not reconstruct identity by joining timestamps or guessing spool positions.

Handshake answer: structures' `input_cursor`, `instrument_id` and complete
`input_record_indices` can be joined to the existing journal `_frame_index`. Codex supplies
`structures.group.*` on that exact membership, beside unchanged timestamp aliases.
Search removes BOTH numeric and text `provenance.*` from channels/cells and retains metadata in
the pinned spool/report. Price exact placement currently lists every original spool ordinal as
`price_original_input_identity_pending`; timestamp aliases and their unselected-row accounting
continue. Do not claim the price join is done. No new event axis, price-slot trajectory, or per-entity
lag definition is settled by this work.

### A4 — retain discovery identity when its arithmetic is unavailable

`experiment_exchange.origin_evidence_accounting` updates aggregate `found` only after
`count_margins`/where failure paths have continued. A reader-authenticated `discovery_row=True`
can therefore remain explicitly identified in a listed row while `discovery_row_found=False`
is voiced by the scientific turn. Compute identity presence independently of arithmetic usability,
using only the existing authenticated reader status and current-day scope. Preserve the exact
failure reasons, unavailable margins and zero tests; no malformed row becomes a new measurement.

### B1 — remove newly introduced evidence truncation

`historical_reproduction.run` keeps only the last 20,000 stderr characters, and
`_compare_json` keeps only the first 200 differing/missing fields. Counts do not preserve the
omitted evidence. Retain complete stdout/stderr bytes and all comparison details (or exact,
hash-bound whole artifacts read by the consumers); replacement decoding is not original-byte
retention. Keep every selected produced-only leaf available as well, not only its count.
No arbitrary limit, sampling or silent reduction. This is evidence preservation, not a new metric.

### B2 — separate recorded references from fresh outputs; establish actual execution outcome

`stage` writes recorded output sources into the same `tree/<path>` used by the command.
`crypto_harness` produces the already-staged `_info_dipole_harness_results.json`.
NG produces `research/kalshi/renders/ng_refine_s95/fingerprints.json`, also a staged recorded
reference. This lets the child overwrite the comparison reference; a failed child can leave the
old reference looking like a new output. Keep immutable pinned references separate from fresh,
operation-owned output paths and follow the original driver's actual input/output behavior.
For NG, trace the driver's six-day scope versus the recorded multi-day file before declaring
which original fields are comparable; do not silently match unrelated list positions.

`compare` currently accepts any run-status record, even nonzero returncode/timeout, and reads
live produced paths without checking their hashes against `run_doc.produced`.
Bind comparison to this completed operation's captured bytes, and preserve failure/timeout/
partial-output facts. A failed run or unchanged staged reference cannot establish successful
reproduction. Do not run anything to check this.

### B3 — check operation identity and durable state BEFORE subprocess dispatch

`run` checks `run.json` only via `write_once` AFTER subprocess execution. A retry can rerun
the research and only then refuse different timing/output bytes. It also trusts the plan's
`executable` boolean without rechecking the staged source/input bytes or staging/plan relationship.
Use the existing immutable-operation/recovery contracts: before any future authorized dispatch,
bind entry, full plan, input/source bytes, command and capability; refuse incompatible or ambiguous
pending state and reuse completed state without rerunning. Preserve a durable in-progress state
before dispatch. No implicit retries, overwrite or authorization inferred from the literal alone.
The current execution hold remains in force.

### B4 — enforce the full declared binding at record admission; preserve performed states

`pins_of` contains only sources, omitting the committed input pins. `records_for` checks
that list and a self-hash but not the current binding-table identity, declared claim membership
for the entry, input identity, or consistent plan/run/comparison relationship. An old semantic
binding or a record naming an unrelated claim can thus be accepted. Bind admission to the exact
declared entry/claims/inputs/calculation and retained operation evidence using existing contracts;
list rejected/mismatched records with their identities and reasons. A `not_bound` entry must
not acquire performed status through an empty source-pin list. H06–H08 stay not_bound: Memory A
is retired, not a new reproduction task.

`status_of` promises differs-first but iterates `STATUSES` with matched first.
`record` converts `performed_not_comparable` into `not_run`, losing the fact it executed.
Preserve actual performed/failed/incomparable/not-run facts consistently through both teachers'
readers and exchange, and keep every entry's status alongside any summary. Matching one entry
does not close the other entries or historical reproduction/rework. No claim truth/survivor policy.

### B5 — freeze the owner-local reproduction selection with the teacher's other inputs

`scientific_teacher.test` dynamically reads global `REPRODUCTION_DIR`
(`/opt/frankie-box/work/experiment-teacher/reproduction`) for each historical claim.
The `records_dir` argument on collection reconsideration does not reach this reader.
Neither current owner-local wiring nor an immutable per-operation record selection is established:
new files can change results across claims or on a restart of the same frozen teacher operation.
Wire the existing owner's records directory and pin/freeze all selected records with the existing
teacher input/recovery identity; consume that selection consistently in both seats. List later
arrivals separately without reopening frozen selections or inventing late scheduling.
Bind the reproduction module and historical binding semantics into relevant recovery identities.

### B6 — state the remaining input-supply gap accurately

`stage` always lists noncommitted inputs missing, while `plan.executable` also requires the
static binding status `defined`. Supplying original NG/harness bytes therefore has no implemented
path that makes those `missing_inputs` entries executable. Trace the existing authorized local
input/receipt contracts and implement only a settled contract; otherwise report the exact missing
interface rather than claim runnable reproduction capability for these entries. Do not fetch data,
activate an AWS source, invent inputs or implement Greg's undecided reformulation definitions.

### C1 — distinguish native evidence identity from its local materialization path

`teacher_knowledge.teach_accumulated` compares the entire carried same-day reference with
`native_ref`. `scientific_teacher.completed_native_evidence` includes the output `path`
in that reference, so identical bytes produced under a different owner output root are rejected.
Compare content/source/manifest identity separately from storage location, preserving and checking
the exact source references. Still refuse genuinely different evidence for the same frozen owner.
If no current native reference exists, do not let a carried same-day reference from another
manifest silently stand in for the current owner's evidence; preserve its original provenance.
Report the actual result scope: a loop that skips all already-tested claims emits no new result
header. This does not by itself supply missing completed-native computation or reopen prior lessons.

### Closure and holds

D's late-knowledge changes list receipts at the two frozen boundaries; source review found no
reopening of their frozen documents. This does not resolve late scheduling. C's references and
coverage table do not prove all native consumers perform the required calculations. Historical
reproduction and repair/reformulation remain open for BOTH teachers; no run or repair occurred.
Steps 2–4 remain incomplete; the 19 outputs never cap applicable evidence.

Only source/interface review, AST syntax without project imports and whitespace checks.
No tests, installs, runs, model calls, AWS actions, starts, dispatch, canaries or E2E.
STOP before #5. Keep the draft unapplied and Granite pins unchanged (threads null).
Never apply `9c19cc2`. Do not rebuild the 52.9 MB claims file under the hold.
Greg's threshold/window/LEG-SIDE/flat-flow/entry/turn definitions, 4.4 pair ownership, 4.2
step definition, three native-learner decisions, late scheduling and principal_inputs catalog
remain open. Return source corrections and precise limitations, not a new invented slice.

Latest reserved continuation after `1f8d64e1`: Codex now records exact original source ordinal
ranges that the unchanged timestamp-asof alias does not select, using the same selection function
as the value reader and its leakage gate. Price/structure receipts explicitly say the exact
INPUT/group/entity join is still missing. This reporting does not replace your producer task below
or claim those omitted rows are computationally covered. Return original INPUT-index/instrument
provenance and recovery bindings first when possible; Codex will handle the reserved search adapter.

## Latest Codex coordination — after fetched `8bb4c0d`

The reserved generic-search export-binding repair is now source-built, runtime-unverified. Codex
checks the actual decoded frames/structures/prices/INPUT and signed-flow/roll20/external bytes
against the selected export; the external receipt is also pinned. Selected missing files refuse,
genuine optional absences are explicit in notes and logs, and selected nested external files no
longer disappear behind a top-level path assumption. Manifest identity remains fixed through
preparation/recovery/publication. Read the newest section of the new-chat handoff for exact limits.
Do not duplicate this work or edit either reserved search module.

Your remaining implementation assignment is unchanged and remains as broad as the settled contracts
allow: finish all three Slice A corrections below, then B historical reproduction/rework capabilities,
C completed-native consumers, and D native learner/knowledge/trajectory plumbing plus the concrete
price/structure provenance producer. Prioritize returning that small producer contract when ready;
Codex's exact search joins wait for it. Return separate source-built commits; no runs or research.
Optional-source absence is never permission to silently waive evidence. Carry existing missing,
unsupported and failed dispositions into the actual applicable teacher consumers under your owned
contracts; do not mark receipt-only delivery as arithmetic or coverage. Keep missing definitions open.

Latest observation, 2026-10-06 16:13 ET: your branch is now at
`a9625ae2a2e145ea85540f47e542f7bf20e8a1ba`. That return adds a new-chat handoff only;
it supplies no code correcting the three Slice A findings below. The integrated branch is at
`cb7acc402380ec9a54a238355127fe14bab55c95` before Codex's documentation checkpoint.
Fetch current integration before continuing. Your handoff's "Slice A DONE" and step-4 closure
table do not supersede these actual consumer gaps. Historical B is traced but unwritten; C/D
and the price/structure provenance producer task remain assigned to you. At that checkpoint Codex
was investigating selected-export hash binding; the newer section above supersedes that status.

## Slice A return reviewed for integration — `6e5fb403`, latest follow-up

Observed `ccode/teacher-tasks-20261006b` at `6e5fb403ac8a1f6ce4c82a2173c7c08b7c9c7054`.
Its actual parent/base is `bbe2d560` (the report's `6cf36b3` is the earlier assignment checkpoint).
Codex integrates these four exact file blobs with both histories preserved and newer `59cca0d4`
search/clock work retained. SOURCE-BUILT / RUNTIME-UNVERIFIED. Slice A is PARTIAL, not complete.

Source-reviewed improvements: discovery-day candidates reach the existing exact-origin reader;
origin margins reach the BOSS turn and lawful Frankie reply, with original identities; both seat
sidecars retain them; original tests/findings remain separate; mirror identity includes the two
remaining chance fields. Existing reader/producer digests bind recovery. No research was run.

Finish these corrections in your exchange file before declaring A complete:
1. `science_turn` currently reads origin rows only for `day_text` row count/discovery-found and
   `origin_on_day`. The full `origin_accounting` is attached OUTSIDE `record=science`; its arithmetic
   never enters scientific `evidence_checks`, `reasoning`, `teaching_implications`, citations or voice
   lines. Pass the already-computed source-bound origin result to this seat and consume its arithmetic
   before `D.parse_teacher`/hashing. Reuse the same counts, explicitly not a second measurement; keep
   checks unresolved and out of `compared`, findings, promotion and target masks. Sidecar storage is
   not the required second-seat computational/teaching connection.
2. `origin_evidence_accounting` uses the shared complement arithmetic but omits the shared route's
   zero/unclassified qualification. Its prose must say these are nonzero transformed-step margins
   at the retained circular shift, not known physical inactivity. Zero may be stationary, missing or
   unclassified. Restore the same limitation and source/scope language without changing formulas.
3. Surface `origin['listed']` reasons in both actual turns/voice where applicable, not only their
   sidecars. Preserve the rejected source row/reason and distinguish identified discovery evidence
   from arithmetic that cannot be performed. Do not invent a result or mark an unsupported row tested.

Continue B/C/D and the price/structure producer task below. Fetch current integration before returning
new edits; do not reapply already-integrated A or overwrite the reserved search module/shared handoffs.

## Expanded assignment from Greg — latest ownership, after `7d10fa5`

Greg: "give CCode as much as you can so we can preserve your usage" (2026-10-06).
This section supersedes the older ownership allocations below for the named files/tasks.
Fetch the CURRENT `ccr-5fce7de3-xa4hfg` HEAD; `7d10fa5` is the inspected base, not a reset target.
Read `NEW_CHAT_HANDOFF_20261006_TEACHER_COVERAGE.md` first. Work on a separate branch from
the refreshed tip, preserving newer commits. Return atomic `[skip ci]` commits for integration.
The Slice A return is now observed as recorded above; the remaining queue is not claimed complete.

Codex retains only the immediate raw-placeholder projection repair in `frankie_box_experiment_dipole.py`,
its description in `frankie_box_experiment_search.py`, and the current continuation/assignment documents.
Do not edit those two modules concurrently. Read their latest V3 route before wiring consumers.
The subsequent reserved search fix also places `events.*` and `events.last.*` using ROOT's exact
INPUT membership, with source `group_binding` dispositions and unknown-size counts; see the newest
new-chat handoff section. Existing old search results are unchanged, not retroactively repaired.
CCode takes the remaining pre-#5 implementation queue below, including the shared caller files
previously reserved for Codex. Codex will review/integrate the returned work instead of duplicating it.

### A. Finish discovery-day delivery and BOTH-seat arithmetic first

Own `deploy/aws/box/frankie_box_teacher_knowledge.py`, `frankie_box_experiment_exchange.py`,
the existing scientific_teacher/candidate_claims modules, their launcher, and your Step #4 report.

- In `teach_accumulated`, remove the blanket discovery-day candidate exclusion at the existing
  origin-day check only after tracing its frozen-selection/retry contract. Let the existing reader
  produce origin evidence from the owner's complete source-bound search parts. Preserve all original
  claim IDs, part hashes, ordinals, raw-line hashes and already-frozen inputs. No artifact rewrite or rerun.
- `e61a382` is integrated: do not repeat its exact-origin or origin-before-mirror repair.
  Consume that current contract, including reversed discovery rows and explicit missing-origin entries.
- Wire `origin_evidence` through `shared_count_accounting`, BOTH seats, exchange sidecars/citations
  and the lawful Frankie reply. Reuse existing count arithmetic; keep origin accounting separately
  labelled from `tests`, independent comparisons, findings and promotion. Do not make its presence
  sufficient for joint confirmation or historical reproduction. Read `where` and `discovery_row`;
  do not treat every origin-day row as the candidate's exact discovery row.
- Preserve forward/reverse alias deduplication, exact transform/cell/lag scope, zero eligible results,
  unsupported scopes, answer/Jev walls and per-day ownership. No invented minimum occurrence/day count.
- Review mirror chance identity (`null_exclusion`, `beyond_chance`) against the current computation.
  Fix concrete equivalence errors in the owned reader without choosing a new acceptance rule.
- Audit the recovery/source digests for every changed caller/helper and publication retry. Old completed
  lessons keep their original semantics; incompatible pending work must not silently reuse new semantics.

### B. Build faithful historical calculation bindings and teacher rework capabilities

Ownership is extended to `frankie_box_historical_claims.py` and narrowly required existing historical
binding helpers. Preserve combined catalog/claims bytes; do not run their builders under this hold.

- Trace original source calculations at each catalog's exact revision before adding bindings. Implement
  adapters only where the existing source defines inputs, units, axes, arithmetic and output meaning.
  A prose similarity, symbol match or forced pairwise crosswalk is not a faithful original calculation.
- Extend the teachers' software paths for original-calculation reproduction and declared repair/reformulation
  mechanisms. Wire lawful results to both seats using the existing lesson/exchange machinery. Keep
  stored-count reassessment, actual future reproduction, attempted repair, and pending work distinct.
- Retain every historical statement, rejected label, rationale, native reference and unsupported binding.
  No narrowing to the 10 current crosswalk entries or 19 output columns. Do not change old evidence labels
  into truth, fabricate outcomes, or claim a binding adapter itself has reproduced the research.
- Where a missing mathematical definition blocks implementation, record the exact producer/consumer
  contract and decision needed, then continue other defined work. Teachers perform the research later;
  CCode builds capabilities and must not rerun or judge the research now.

### C. Completed native evidence and actual existing consumers

Extend work to narrowly required existing evidence-reader/consumer modules, excluding Codex's two
reserved search modules. Start with `completed_native_evidence` and the exchange's current references.

- Trace result.json, exact 4.2/4.4 products and FINALIZE rows into existing lawful arithmetic/model
  consumers. Implement a missing connection only when the current contracts already define its meaning.
- Packaging, hashing, citation and status counts are not semantic computation. Report each path as
  computed by a named existing function, connected-but-unverified, or awaiting a precise definition.
- Candidate-only accumulated lessons currently do not generate the current owner's native evidence:
  repair that connection where the existing owner-local source pins and writer contract permit it.
- Preserve post-stream availability, exact units/strata, source identity, alias handling and average
  supplements. Do not backfill completed products onto earlier F_LAST frames or exclude exact products
  merely because an averaged companion also exists.
- Keep Greg's decisions open: which group owns a 4.4 pair completion, and whether/what step definition
  a 4.2 two-point session summary has. Neither is authority to invent a series or statistic.

### D. Remaining pre-#5 model, trajectory and knowledge-consumer gaps

Read `ROOT_PLANE_COVERAGE_20261006.md`, `KNOWLEDGE_CONSUMER_COVERAGE_20261006.md`,
`NATIVE_LEARNER_INTEGRATION_DECISIONS_20261006.md` and `PENDING_FEEDBACK_COMPLETION_20261006.md`.
Inspect the original inventories/contracts first. Build only connections whose semantics are settled.

- Trace identity-linked order/book/DState trajectories beyond positional slots. Repair existing identity
  loss or disconnected established consumers; do not choose new lag units, session bridging or trajectories
  by assumption. Return exact proposed interfaces for changes needed in the reserved search modules.
- Trace native representation/TeacherHead/training consumers and accumulated knowledge into actual
  computations. Repair unambiguous adapter/identity plumbing where possible. No new weights, outcome labels,
  auxiliary-loss weight, optimizer ordering, checkpoint migration or model-state initialization.
- Audit late-arriving knowledge at existing unfinished-work boundaries and repair concrete delivery/retry
  drops within those contracts. Do not reopen completed days, replace frozen inputs or introduce a scheduler
  policy. State precisely what remains blocked by the held late-scheduling decisions.
- This queue does not authorize workflow #5 or work beyond its discussion boundary. Granite pins,
  `threads: null`, principal catalog choice and claims-file split remain settled or held as recorded.

### Additional concrete producer task from reserved search review, after `bbe2d560`

Own this narrow change in `frankie_box_boss_session.Session.derive` and its existing source/recovery
bindings. Current `prices.append` retains receive/event timestamps and prices/sizes but no original
INPUT index or instrument. `structures.append` retains frame timestamps and describe_structure output,
but omits the original closing INPUT index and instrument. Equal full timestamps are not unique
identities, and frame/structure failures can make spool ordinals differ. Do not infer a positional join.

Carry the already-in-scope original extracted INPUT index and producer instrument identity into each
new price/structure row, with explicit field names/semantics and unchanged calculation outputs. Bind
the producer change to the existing recovery/source identities; preserve old pending/completed artifacts.
Trace any existing source member/session identity needed to avoid merging distinct lifetimes. Do not
invent missing historical provenance, rerun ROOT or change describe_structure/price calculations.
Return the exact new row contract to Codex for the reserved search adapter. Codex will join group
structures and within-group prices using established ROOT membership; the old timestamp aliases must
not be described as exact source-identity or all-entity coverage in the meantime. Any retained older
spool lacking the fields remains explicit. This is part of task D's existing identity plumbing, not
a new axis, trajectory definition, transform or producer activation.

### Delivery and execution limits

Return separate commits for A, then each defined B/C/D slice, with exact parent/head, changed files,
source contracts used, what now reaches arithmetic, remaining definitions and actual checks performed.
Update your Step #4 report; Codex owns integration edits to the shared continuation documents.
Greg also asks how close this leaves steps #1–#4. Include a short closure table using the existing
contracts: step, actual consumer/function, source-built connection, remaining implementation or
decision, and runtime verification still needed. Do not substitute a completion percentage, new gate
or file/claim count for unresolved computational coverage. #1 stays source-built, not runtime-proven.
Do not turn the assignment into another validator framework or a research run.
Source/interface review, AST syntax without project imports, and whitespace checks ONLY.
No tests, synthetic exercises, installs, model/data/scientific execution, AWS actions, starts, dispatch,
canaries or E2E. Keep boxes stopped. STOP BEFORE #5. Preserve its unapplied draft and never apply
discarded `9c19cc2`. Every result stays SOURCE-BUILT / RUNTIME-UNVERIFIED until separately authorized.

## Earlier assignment and source history (ownership superseded above where named)

Greg asked Codex to give CCode a few tasks while Codex continues separate evidence wiring.
Start from the latest `ccr-5fce7de3-xa4hfg` tip, which includes `03f29be`, and preserve newer work.
Use a separate branch. Read AGENTS.md and the latest successor/Step #4 handoffs first.

## Return received and follow-up source defects — after `42239c0`

**Latest return reconciled:** `e61a382b4cd1c60454013092ee0ef8a9009e782e` fixes the exact
origin-row binding and origin-before-mirror findings below. Merged with both parents at
`e75792b47244ce9f699bde2cb6bc9950a509e5c8`, preserving Codex `54c75fb` shared callers.
Those two reader defects are SOURCE-FIXED / RUNTIME-UNVERIFIED, not still assigned for repair.
The discovery-day caller/consumer route and native semantic coverage remain open. Codex also
finished the separate BOSS retained-input count route documented in the new-chat handoff; that
route is not origin-evidence integration. Fetch latest source before further work.

Your `b264f7946b78200c9d47f7810ea6d325640b37ad` collection branch is merged with both histories
preserved at `42239c098090763d1688b2b37e0fe1a2634c22a7`. Codex's `2135bc1` adds stable exact
entity-scoped closing-row search fields and corrects stale classroom scope wording. Fetch the latest
branch before working. Codex is integrating your requested plan/lesson/exchange callers separately.

Source review of your return found these remaining owned-reader issues; fix the code, do not run research:

1. FIXED by `e61a382`. Original finding: `test()` read rows without retaining their part or row ordinal. `origin_part_bound` only checked
   whether the declared hash is anywhere in `d['part_pins'].values()`, while `same_row` compares a
   selected field subset. Therefore a matching row from a different part/ordinal can be marked the
   discovery row. Bind the actual read row to the candidate's exact part hash, row ordinal and
   canonical row hash using the adapter's existing conventions; retain zero/mismatched matches explicitly.
2. FIXED by `e61a382` for origin ordering. Original finding: mirror filtering ran before the origin-day branch. A candidate discovered in the reversed
   orientation can have its exact origin row moved into `mirrored_rows` and skipped before
   `origin_evidence` records it. Preserve exact origin identity while still counting no origin row
   as an independent test. Review the mirror identity's omitted `null_exclusion` and `beyond_chance`
   fields against the existing chance-check contract; do not invent another acceptance rule.
3. The prior coordination finding below is still open: owner-local `teach_accumulated` skips
   discovery-day candidates; both seats' arithmetic reads `tests`, not `origin_evidence`. Return
   explicit caller/consumer requirements after fixing #1/#2. Codex owns those shared edits.
4. `completed_native_evidence` reads and packages post-stream products, but its own rule says
   nothing is computed there. The exchange now cites those bound references. Do not describe this
   as completed semantic/computational coverage. Name any existing lawful semantic consumers or
   precise missing definitions. The owner-local accumulated path carries prior top-level references
   unchanged; it does not create this day's native evidence for a new candidate-only document.

Historical rework remains open. Crosswalk growth must faithfully bind existing declared calculations;
software support for such bindings is allowed, but neither CCode nor Codex should fabricate scientific
results or treat a stored-count comparison as original reproduction/repair. The teachers do that work
when execution is authorized. No tests, imports, installs, runs, AWS, dispatch, canary or E2E; stop before #5.

**Execution ownership clarification from Greg:** CCode builds/repairs the teachers' code paths.
CCode must NOT rerun, rework, evaluate or judge the Dipole research himself. The BOSS teacher and
scientific teacher perform those scientific tasks through their governed code when execution is
authorized. Every instruction below to reproduce, investigate or reformulate describes capabilities
to wire for the teachers, not research for CCode to conduct. No scientific result is claimed here.

## Priority amendment from Greg, 2026-10-06

Both teachers must challenge Claude's old dead/no-good/discarded conclusions as claims, never truth.
Reproduce original applicable calculations, investigate failure causes and try repairs/reformulations;
nothing is considered closed until it has been reworked again. Preserve the old result as scoped evidence.
Audit the historical catalog through `historical_claims`, including `not_testable` entries that currently
travel only by reference. In your scientific-teacher files, fix concrete drops of provenance, rejection
rationale and pending reproduction/rework obligations. Distinguish actual recalculation, stored-count
reassessment, repair/reformulation attempted, and still-unmapped work. Never fabricate a positive result,
reformulation or completed calculation. Name caller changes needed for BOTH teachers.
Codex owns the historical catalog builder, directive/rules and exchange enforcement; read, do not edit them.

Codex is now wiring your candidate adapter through owner-local accumulated testing, brain publication and
both teacher exchange seats. Fetch the latest source before reporting those callers as absent. The narrow
owner-local route uses the existing brain writer for completed search-candidate lessons; your standalone
publisher remains guarded. Coordinate changes against the writer's actual accepted contract.

## 1. Candidate adapter and scientific-reader readiness

Own `deploy/aws/box/frankie_box_candidate_claims.py`, `frankie_box_scientific_teacher.py`, its shell launcher,
and `CCODE_STEP4_SOURCE_ROUTE_20261006.md`. Inspect the exact existing route before editing.
Review candidate source/part/row identity, exact entity/series matching, transform and condition scope,
and reversed x/y orientation with nonzero lag. Fix concrete defects within these files using the existing
science. A scope that cannot be checked must stay explicit; no silent fuzzy broadening or changed formulas.
Keep origin-evidence reuse distinct from independent checking. A checked single occurrence must receive
equal treatment; do not introduce occurrence/day minima or choose acceptance/survivor rules.
Document the exact prerequisite caller edits for Codex. Keep publication refusal until its writer and
consumers actually support the candidate schema; a proposed interface is not an active route.

## 2. Owner-local candidate delivery contract

Read the current brain, teacher_knowledge, exchange, school and lane callers without editing them.
Refresh section 4 of your Step #4 report against the latest integration, with concrete function arguments,
result schema, original claim/day/source identities, and where retry deduplication applies.
Identify how each owner tests received candidates against its own complete search parts at existing
knowledge boundaries, including zero eligible comparisons, same-source aliases, and late-arriving knowledge.
Keep giant evidence local. One owner's receipt must never finish another day or the whole batch.
Specify minimal Codex edits; do not create a new transport, scheduler or acceptance framework.

## 3. Completed native calculation evidence: semantic-consumer review

Read the retained `result.json`, section 4.2/4.4 producer contracts and FINALIZE dispositions alongside
the existing scientific claim/result interfaces. Trace whether any existing supported claim shape can
lawfully compute with those products after completion. Report exact supported mappings and exact missing
semantics separately in your report. Preserve declared units, strata, causal availability, raw evidence,
scope and matching rules. Do not backfill completed knowledge onto earlier live frames.
This task is source review: do not invent a claim adapter, new measurement, target, independence claim,
enabled producer or model route merely to turn retained products into purported computational coverage.

## Ownership and completion

### Coordination finding from Codex, 2026-10-06

Greg confirmed you are actively handling the assigned candidate work. Source inspection at `21df8f1`
found `frankie_box_teacher_knowledge.teach_accumulated` skips every search candidate whose origin day
equals the current owner day before calling `ST.test`. The scientific reader already has a separate
`origin_evidence` path, but the caller skip prevents that path from running on discovery-day candidates.
Separately, `shared_count_accounting` and `science_turn` currently consume `tests`, not `origin_evidence`.
Thus retained discovery counts do not reach both seats' computations through that route. Please include
this finding in tasks #1/#2 and specify the needed shared caller/consumer edits for Codex. Preserve the
origin/test distinction and exact source identity; do not count reused evidence as another occurrence,
confirmation or completed research. This is a source finding, not a runtime result or a request to run data.

Codex set aside an overlapping caller/exchange draft after Greg's correction. Commit object `9c19cc2`
was never attached to the work branch; do not treat it as integrated or apply it without reconciliation.
Codex instead fixed parent annotation loss in `parallel_teacher._RawStreams._resolve` (book-integrity
counts and unknown-side count/volume dropped when worker results replaced placeholders). Your owned
candidate/scientific files were untouched; fetch the current handoff/source before integrating callers.

Codex owns the full DState capture/publication/search slice: `parallel_teacher.py`,
`frankie_box_experiment_teacher.py`, `dipole_classroom.py`, `frankie_box_experiment_dipole.py`,
`frankie_box_experiment_search.py`, and shared integration/handoff files. Do not edit these.
Granite model pins and runtime parameters, including `threads: null`, are settled. Cached-file verification
is source-reviewed at `03f29be`; do not reopen those decisions or repeat the scratchpad scenarios.

Source/interface review and syntax/whitespace checks only. No tests, installs, downloads of runtime/model
assets, model/data/scientific runs, AWS actions, workflow dispatch, canary or E2E. Keep all boxes stopped.
STOP before workflow #5; leave its draft unapplied. Jev CPU and native learning decisions remain held.
Push with `[skip ci]`. Return exact head, changed files, findings fixed, caller edits still needed,
verification actually performed and unresolved decisions. Label all work source-built/runtime-unverified.
