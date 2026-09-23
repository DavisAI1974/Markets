# Codex handoff — Monday full pipeline wiring — 2026-09-23

## Read this first; do not drift

This handoff supersedes earlier handoffs for current execution status. Keep earlier documents for reducer designs and provenance:
1. This file.
2. CODEX_HANDOFF_20260923_SESSION.md.
3. CODEX_HANDOFF_20260923_REDUCERS.md.
4. CLAUDE.md, especially the FRANKIE / BOSS standing rules.

Repository: DavisAI1974/Markets.
Branch: claude/agent-skills-execution-tzh7sw.
Latest runtime commit: e3a72f69fce63c2fc4f43bc202e3d3399fe90de4.
This documentation commit is a child of that runtime commit.

Greg's latest request was to commit/push completed work, create this handoff, and supply a drop-in for a new chat. No launch was attempted in this handoff turn. Earlier Greg explicitly authorized starting Monday after the remaining wiring is done. Do not ask him repeatedly to reauthorize the same scoped work, but do not pretend unfinished wiring is a complete run.

**Stay focused: finish remaining execution wiring, omit no required stage, commit/push atomically, then start the actual full Monday run. No side work, new validator framework, extra test cycles, or canary/comparison run. Report real progress and real blockers, not estimates disguised as measurements.**

Greg repeatedly said to stop checking tests and move forward. No tests were dispatched or polled after that correction. Existing automatic push workflows may still run; do not turn them into new gates. Do not remove existing scientific integrity requirements to make a run appear successful.

## Greg's final clarification: manual orchestration is authorized

Greg explicitly said that if workflows already exist for everything but are not wired together, run those workflows manually as in earlier work. This is for the NEXT chat, not a launch during this handoff turn.

Do NOT make a new orchestration layer a prerequisite for running. Inspect the existing workflow entry points and their actual inputs/outputs, execute the existing stages serially when they cover the required work, and pass their real artifacts to the next stage. Only implement a genuinely missing capability or binding that cannot be supplied through the existing operational route. The code-level gaps listed below are a map of the current automated path, NOT an instruction to redesign or close every gap before using a complete manual route.

Nothing required may be omitted or falsely reported complete. Preserve all operational constraints and the full Monday scope. If an existing manual route bypasses a host bootstrap dependency legitimately using actual producer/brain artifacts, use it instead of expanding the host implementation. No tests/canaries/new validators as detours. Commit any necessary small changes atomically and push, then execute the complete sequence with actual receipts.

## Actual state

- All completed runtime edits from this session were already committed and pushed through e3a72f69; the branch tip was confirmed through GitHub during handoff.
- No completed runtime edit is knowingly left only in session memory.
- Rejected/uncompleted in-memory drafts were NOT published: an extra next-session validator helper, its alternate importing contract, and two appended test drafts. They are not needed to preserve finished work. Do not recreate them as a supposed missing commit.
- No C:/E: repository writes in this remote-only continuation. Skills were read from C: without modifying them.
- This is NOT a certification that every unknown local change from Claude or older chats has been found. No local dirty-worktree audit was done under the remote-only constraint. Do not claim otherwise.
- Monday has NOT started. No Monday model call, root calculation run, classroom run, or end-to-end execution was made by this continuation.
- Latest runtime commit is NOT staged on the box. The last confirmed inactive staging is older, described below.
- The pipeline is NOT yet launch-ready. The gaps below are implementation gaps, not a request for another validation project.

## Binding scope and operations

- Monday 20211004 is ONE full trading day: 2021-10-03T22:00Z through 2021-10-04T21:00Z (Sun 18 ET–Mon 17 ET, 23 hours).
- Use the entire sealed Monday source across both UTC members. No Sunday-number caps, arbitrary row windows, six-hour configuration, or invented cutoff/cycle structure.
- 4096 must not be used as a fabricated source cutoff. Existing model-internal architecture constants are a separate matter; do not change the science.
- Stack applicable exact/lossless reducers together; do not replace one with another. Do not claim Monday savings until measured on Monday.
- All native/root calculations, all three producer bedrock groups, full Granite critic/reading, classroom teaching/grading/correction, and retained knowledge belong in the run.
- Here “bedrock groups” means repository calculation groups, NOT Amazon Bedrock. Amazon Bedrock is prohibited.
- Frankie's knowledge comes from /opt/frankie-box/brain/cycle-NN, not a newly invented Memory A principal package.
- No ingestion restart/replay, pod/instance stop, pinned-bootstrap change, evidence deletion, key disclosure, BOSS output caps, parallel work, or new push-trigger automation.
- Reading the existing sealed journal is allowed; reingestion is not.
- No shell sleep/timeout/tail -f waiting.
- Work through GitHub and the remote box; do not create repository artifacts on C: or E:.
- Atomic commits, no force push. Commit messages end with:
  Co-Authored-By: Codex <noreply@openai.com>
- Preserve:
  /opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite
  23,687,368,704 bytes
  SHA256 947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888
  /opt/frankie-box/work/sealed-recovery-35796793428

## Forecast decision and honest pending state

Greg allowed the run day's forecast or the next day. The implementation/spec chose Tuesday 20211005, using whole Monday as input so the target is future rather than leaked Monday outcomes. Tuesday was the agent's explicit design choice, not a verbatim user-mandated date.

The committed SPEC-monday-next-day-forecast.md records that choice.
Full Monday calculations, reading and classroom must still run.
If verified Tuesday outcomes are unavailable, retain the issued forecast and classroom work with status pending_target_outcomes. Never fabricate labels, apply native learning with empty labels, or mark the cycle complete.
The new pending receipt is a restart checkpoint for the pending state; it is NOT a finished implementation for later ingesting Tuesday outcomes and completing training.

## Recent pushed increments

### e3a72f69fce63c2fc4f43bc202e3d3399fe90de4

feat: retain Monday classroom while next-session outcomes are pending

Eight runtime files changed, no tests/workflows in this commit. Not tested after Greg's stop-testing instruction.

- research/kalshi/frankie_boss/source_contract_runtime.py:
  bind_cycle supports opt-in forecast_mode=whole_day_next_session, a pending-outcomes split, explicit forecast_target, feedback_status=pending_target_outcomes, and null learning boundaries. It consumes a contract; it does not author one.
- research/kalshi/frankie_boss/frankie_principal_adapter.py:
  request instructs full calculations/reading/classroom/correction/lessons without fake feedback; recover retains null feedback with pending descriptor; verify retains existing request/input/source identity checks and returns None for this explicit pending mode. Existing principal constructor/bootstrap remains Memory-A-shaped and is not yet replaced by a brain route.
- research/kalshi/frankie_boss/feedback_cycle.py:
  awaiting_target_outcomes mode saves classroom_lessons and pending_feedback, preserves the checkpoint, emits pending status, and does not construct/apply a native learner or mark complete. Resume returns the saved pending stage without reissuing the forecast.
- research/kalshi/frankie_boss/sunday_execution.py:
  accepts the whole-day schedule mode, forwards pending mode, returns saved pending state, writes pending-feedback.c15.json instead of completion.c15.json.
- research/kalshi/frankie_boss/operations/run_actual_sunday_classroom.py:
  reports pending_target_outcomes/classroom complete/native training false/cycle complete false; returns 3 for that pending condition, not a claim of full completion.
- research/kalshi/frankie_boss/operations/record_actual_frankie_response.py:
  candidate includes feedback_contract; lessons/classroom/attestation still run; outcome-only checks execute only when actual feedback exists.
- deploy/aws/box/frankie_box_boss_session.py:
  labels writes an explicit pending-target document in the new mode without demanding a later authored cycle. Writing includes that document in its identity and emits feedback=None plus a bound pending descriptor. Full normal stage sequence is unchanged.
- deploy/aws/box/frankie_box_receipts.py:
  answer wall exposes pending status and distinguishes classroom feedback from forecast-outcome feedback.

IntegratedDipoleClassroomPrincipalAdapter still performs the initial grading, relationship crosschecks, novelty/investigation, teaching, correction exchange, completion/transcript retention before returning the principal envelope. Do not bypass it when wiring pending mode.

### 2f911f52447ed80116079df5616d8bec46e6e478

feat: route full-member binding through sealed compact storage

- frankie_source_mapping.py now chooses VerifiedJournalReader for raw entries or CompactReader for sealed blocks, read-only and serial.
- V2 multi-member binder no longer requires callers to supply a special compact-reader factory.
- CLI build-scope creates the existing block source scope from ordered member paths, manifest/hash, extraction pin and member-ledger witness.
- Existing V1 behavior retained.
- Existing CI run 35862037008 was observed successful before Greg stopped test checks. No new count is asserted.

### 9562cf867de8ee6cf9b96c0bb55e00fc8f5bfbe2

feat: bind whole-day schedules to future-session pending feedback

- trading_day_schedule.py adds BOSS_WHOLE_DAY_NEXT_SESSION_SCHEDULE_V1 and build_whole_day_schedule.
- Exactly one terminal step, all source records in model context, explicit future trading-day target, pending feedback and no learning cutoff.
- Uses verified sealed-source/mapping coverage and terminal prefix evidence. No source mutation, model call or calculation.
- verified_sunday_schedule.py dispatch supports this mode.
- The builder's actual production caller remains unwired.
- Earlier observed CI run 35861613592/job107182933181: 265 passed in 19.53 seconds. This is historical evidence, not validation of e3a72f69.

### Earlier work retained in branch history

c493ae7 stacked ingest/Granite/root/cache reducers; 2a6eabf width guard;
72a536b lazy book; 43d3027 exact legacy book projection; 3ed1dc4 reuse book_transition.after;
7bc3686 root probes; 6573e55 early-refusal probe initialization;
da8bb75 classroom cache progress; 7f24af9 fixture;
983e022 probe CLI/docs; 29483a0 whole-Monday/next-day spec;
e94f/82d94b V2 source mapping; 07a695/4a7a5e scope builder.
Use actual Git history for full SHAs, not guessed expansions.
Original Claude handoff dd99a1d4 is historical ancestry, not the current head.

## Remaining wiring — implement in dependency order

### 1. Author and prepare the real full-source Monday execution

Files:
- research/kalshi/frankie_boss/operations/prepare_trading_day.py
- research/kalshi/frankie_boss/operations/run_actual_sunday.py
- research/kalshi/frankie_boss/operations/run_actual_sunday_compact_source.py
- research/kalshi/frankie_boss/trading_day_schedule.py

prepare_trading_day still assumes an intraday cutoff roster, calls the old schedule builder, indexes feedback.as_of, and materializes prefixes/context seeds. Wire the new whole-day builder and explicit target without inventing cutoffs.

ActualHost.source still checks old principal pins up front (memory, contract, mapping, retained_witnesses, delivery_receipt, calculation_result, source_manifest). Parts of its source handling recognize only the old trading schema. encoding_options also expects old trading prefix/context-seed sidecars; the full-source genesis case needs the proper no-prior-prefix path.

The compact host subclass expects old snapshot receipts. Prefer directly referencing the already sealed full Monday container with its real evidence rather than copying 23 GB or replaying ingestion. Reuse the existing reader/checks; do not build a new validation subsystem.

Useful existing entry: deploy/aws/box/frankie_box_monday_read.py open_view(output) builds a recovered-ingestion descriptor from existing verified recovery evidence, asserts the protected original container, and opens the completed source view. Reading this sealed source is not ingestion replay. The legacy Monday-read launcher is NOT the complete desired pipeline.

### 2. Fresh producer/root result and Monday pin; brain-based principal input

There is still NO Monday calculation pin/result/delivery binding in actual launch configuration.
The current principal bootstrap expects a pre-existing calculation result and historical Memory A package before the session does its root calculations. This dependency must be resolved, not bypassed.

Relevant code:
- deploy/aws/box/frankie_box_boss_session.py:
  Session.derive, _input_records, _derive_bedrock, _pin, _pin_matches_request, _derive_needed, brain_ready.
- deploy/aws/box/frankie_box_brain.py:
  capture_base, snapshot_entries, pin_session_base, write_entry, check, entries_before.
- research/kalshi/frankie_boss/frankie_principal_adapter.py:
  prepare, _receiver_input_block, _render_retained, _memory_witness, _admission_record, _files, _check_preparation.
- load_cycle_calculation_pin supports an optional pin filepath, but the session currently uses the global default. Existing cycle-0 group coverage is not proof of a Monday-specific binding.

Prefer a fresh isolated Monday work directory and real producer evidence, then reuse that calculation work. Do not calculate the full source twice as a convenience. Do not forge a controller request or historical admission.
Session._derive_needed compares digest/pin/layer presence but is not by itself sufficient to establish that old work belongs to this new source. Do not reuse an old Sunday directory.

Brain pin_session_base captures retained prior cycle-0 knowledge as well; preserve it.
Avoid creating historical-prompt.md for the fresh Monday route: brain_ready has a legacy frozen-prompt path.
The principal currently requires a knowledge receipt/bundle, exactly 18 historical sections, and protected files. Adapt honestly to actual brain inputs; do not fill historical slots with counterfeit Memory A content.
Reuse the pinned receiver's real calculation/delivery verification and input block.

Pinned producer code ref already inspected:
2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134
Useful files under research/kalshi/frankie_raw_mbo_benchmark:
- native_boss_attachment.py: _result_integrity, _delivery_run_binding, verify_attachment
- prepare_boss_attachment.py
- native_staging.py: stage_spawn_request, build_handoff, read_back
- native_a_arm_launch.py: launch and existing producer lifecycle/checkpoint features

No pinned-bootstrap change is authorized.

### 3. Existing producer lifecycle and checkpoint coverage

The box bedrock runner currently uses real NativeCalculationRun, NativeReplayDriver, serial counted records, NeverInvoke and all three ledger groups, then reconciliation and result hashing.
However its own receipt explicitly lists differences from the producer launcher:
- no PeriodicCheckpointer/seal_start;
- no stage_spawn under NeverInvoke;
- no producer pre-traversal registry identity / precall-layer / RT-surface stages;
- result lacks launcher gates/evidence_identity/slice fields.

Inspect the existing launcher and wire the necessary existing lifecycle/output/checkpoint pieces without duplicating the entire producer or adding new speculative gates. “Nothing omitted” must not be claimed while these remain unexplained gaps.
Greg requested root/classroom probes, real percentages where a measured denominator exists, save points and checkpoint reads. Probe scaffolding exists; the root wrapper checkpoint omission is not solved merely by displaying progress.
“Only three groups” never authorized dropping calculations within those groups or changing the science.

### 4. Connect the actual host/session/box launch path

run_actual_sunday_ec2.py composes the compact-source host over the mandatory classroom host. Use the full classroom path.
The session's full stage order remains:
verify -> pin match -> brain_ready -> labels -> engine -> derive/reuse -> compare -> full reading -> classroom -> teach -> receipts -> writing -> push
Correction runs the existing correction exchange and push.

Box handoff/callback/config still contain old host assumptions, including Windows path constants. Wire a genuinely box-local flow. Do not export to C:/E: or claim that running the legacy read script constitutes the full run.

### 5. Full-source native/Granite admission and eventual outcomes

The new schedule retains ALL Monday records. The actual native/Granite prompt fit has not been measured for Monday; the critic has a physical 131072-token context.
Do not silently truncate, cap BOSS output, or substitute staged reading summaries for the exact critic science. Full staged Frankie reading can process chunks, but that is not automatically an equivalent critic input.
If this is an actual unresolved execution blocker, report it honestly rather than claiming launch readiness.

Verified Tuesday labels and the later pending-to-completed native learning transition are not implemented/available here. Retain pending status; do not invent labels or skip classroom because labels are pending.

## Last confirmed remote staging, not current deployment

Inactive staged commit: 983e022fb63bf041936c8934de32771d0c878838.
Workflow run 35857458598, job 107169296581, observed successful.
Staged path:
/opt/frankie-box/code/983e022fb63bf041936c8934de32771d0c878838-35857458598-1/markets

Receipt at that time: active_checkout_changed=false, model_calls=0, source_replays=0, files=3645.
Active checkout was older 2ae4da2 with untracked files, last known. Do not overwrite casually.
None of the newer whole-day/mapping/pending commits were staged by this continuation.

Existing mechanism:
.github/workflows/frankie_box_run.yml
deploy/aws/box/frankie_box_stage_code.sh with ACTION=stage
Instance i-035994afa8bdf66a5, region us-east-1.
No direct remote shell connector was available in the prior turn; GitHub API handles repository writes and the existing workflow/browser handles box operations. Discover current available tools before assuming that limitation is permanent.
Do not dispatch the old Monday-read-only command as the full run.
Do not claim “started” without actual launch evidence.

## Prior measured source facts, not new performance claims

Full Monday: 2,032,203 records; 4,064,406 journal entries; 1,535,939 F_LAST groups.
Selected member records: member 0 = 57,027; member 1 = 1,975,176.
Member 1 physically contains additional next-day records outside this trading day; source selection must use the existing verified Monday scope, not simply every record in each UTC member.
Manifest hash: a399377b5b005d989daa467048438437c47b8597dc8cfb5861c3706c6f92a355.
37,934 compact blocks; 23,628,634,795 block bytes.
No Monday end-to-end throughput or Granite fit measurement has been made in this continuation.

## Do not use these old launch paths

- frankie_box_author_monday_launch.py cutoff/window authoring: rejected 6500/window path.
- frankie_box_principal_inputs.* historical Memory A path.
- frankie_box_host_config.py / frankie_box_cycle0.sh pinned six-hour configuration.
- ingest measurement/replay scripts as a launch workaround.
- Original handoff's legacy Monday-read command as if it runs root/native/Granite/classroom end to end.

## New chat working discipline

Use using-agent-skills and context-engineering to establish the narrow context; use Git atomic-commit practices for each finished increment and shipping guidance within Greg's constraints.
Do not turn generic skill suggestions into another testing/validator detour.
Read relevant function bodies at the current branch tip; do not trust old in-memory drafts, print entire large files repeatedly, or restart completed reducer work.
No parallel agent/workstream.
Do not call the remaining work “just one line” or provide an invented ETA.
Next action is to inspect the existing workflow entry points for the complete Monday sequence and manually run them serially if they already cover the work. Implement only genuinely missing pieces; do not require an automated orchestration rewrite. Use the gap map above to avoid omitting stages or substituting stale artifacts.
The final handoff request pauses launch for the new chat; no background task was left running by this handoff turn.
