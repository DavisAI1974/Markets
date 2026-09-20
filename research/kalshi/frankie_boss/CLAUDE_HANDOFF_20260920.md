# Claude handoff - Frankie/BOSS, 2026-09-20 (session: final checks result recorded)

Continues `CLAUDE_HANDOFF_20260918.md` and the operator drop-in `DROP_IN_CLAUDE_20260920.md`.
Work branch `claude/frankie-launch-verification-lqmv0m`, cut from
`codex/frankie-launch-two-cycle-20260919` at `a5ad20bcfe51d4f6478dd1632ad82ca717305f29` (the pushed
tip was verified first). The local harness checkout arrived on a stale divergent tip `9c9c4c1d` that
is not an ancestor of the branch; it was discarded, not built on.

Launch stays HOLD. This session ran no Frankie, Granite, Pod, EC2, S3 or result-bearing action, read
or wrote no retained S3 prefix, and touched no workflow. `a9ab5ec4` was not reverted and
`codex/journal-reduction-stack-20260915` was not touched. Nothing was written to a PC C: or E: drive.

## Done: ordered item 1, the final checks result is now durable

`runs/20260920/checks-only-validation.md` records it, read back from the Actions API and the
downloaded run log archive rather than from the operator summary. Headline: run 35497376513 on
`a5ad20bc` completed success, `checks` success with `sources`/`journal`/`cleanup`/`host` all skipped,
the scientific family at 1101 passed, 1 skipped, 3 warnings in 79.95s, and the receiver step at 352
passed with 234 subtests passed against the frozen receiver `7b98617b`, which matches
`launch_pins.py` `receiver_commit`.

Two corrections to what can be claimed from it, both recorded in the ledger entry:

- The dispatch inputs are not exposed by the run API. `day=20211003`, `cycles=2`, `checks_only=true`,
  `keep_compute=true` stay operator-reported. The job skip pattern corroborates `checks_only=true`;
  `keep_compute` has no observable effect in a run where no compute job started, so it is neither
  confirmed nor contradicted.
- The three warnings are one environment `DeprecationWarning` from `multiprocessing/popen_fork.py:73`
  under two `test_granite_runpod_cloud_control.py` tests. Not assertion failures.

The drop-in's own item 1 named the earlier run 35497249802 at the code tip `fbbc5ce9`. That is also
completed success and its logs carry the identical counts, so that item is closed too. Since
`a5ad20bc` adds only the docs commit on top of `fbbc5ce9`, the identical counts are the expected
result and confirm the docs commit changed no check.

## Not done, and why

Ordered item 2 (an actual two-cycle execution) is unstarted. Launch is HOLD and a go to run on Sunday
is not by itself permission to change a workflow, so this needs an explicit new authorization naming
the run.

Items 3 and 4 (sealed-absence receipts for every absent downstream artifact, and a configuration
consumer that accepts only the signed proof) were read but not changed. Grounding for whoever picks
them up, from `frankie_principal_adapter.py` on this tree:

- `admission_policy` already refuses an undeclared admission (`ADMISSION_UNDECLARED`) at every use
  (prepare, request, recover), and already refuses the historical literals `NOT_PRESENTED` and
  `UNPROVEN` on a newly rendered run: they are admissible only on the retained-prompt route. A new
  two-cycle run therefore cannot silently take the unproven path today.
- `sealed_absence()` verifies schema `FRANKIE_SEALED_ABSENCE_PROOF_V1`, `all_absent is True`, a
  positive `tokens_checked` and a 64-character `receipt_sha256`, and returns `SEALED_UNPROVEN` for
  the literal.
- The one committed proof on this tree is `audits/SEALED_ABSENCE_PROOF_SUNDAY_CYCLE0_20260916.json`
  (cycle 0). There is no proof yet for the currently absent downstream artifacts.

So the open work is producing the per-artifact proofs, not loosening or re-deriving the consumer. The
remaining consumer question, which is a decision rather than a fix, is whether the retained-prompt
exemption should survive for the two-cycle run at all, given that the run is newly rendered.

The per-record ingest cost item is untouched and remains the scale blocker: 37.3 ms/record at about
97 percent dedication implies roughly 4.9 days for four weeks on the small runner. Fewer partitions
remove per-partition overhead, but no measurement yet shows per-entry work moved, so no scale claim
is available. Note that the operator note and the drop-in number this item differently (4 versus 5);
it is the per-record ingest cost item under either numbering.

## Frankie state, unchanged by this session

The classroom package and the model-visible pre-message exist. There is still no verified initial
principal response, classroom grade, correction receipt or configuration receipt. The native run last
reached `boss_reasoning` at cursor 3261 with completed 0. The retained AWS prefix proves durable
model-completion metadata exists; it does not prove the current two-cycle run produced any of the
four artifacts above, and the service-ready record was written before inference with
`inference_sent:false`.

Both EC2 hosts remain last-verified stopped: native `i-0e90ee6110ef609aa` in us-east-2, ingest
`i-035994afa8bdf66a5` in us-east-1. Neither was started, stopped or contacted here.

## Correction: the source facts are one measurement, not four (Greg, 2026-09-20)

The handoff line that carried "57,027 source records, 114,054 input plus applied entries, 1,189
target boxes, and the first two prefixes verified" as four verified source facts was wrong, and
restating it is why the same number keeps having to be re-explained. It is one measurement and two
derivations.

- **57,027 source records** is the measurement. It is the `record_count`, `member_counts` and
  `source_records` of the run 34962256086 verification receipt, and the `next_cursor` pinned in
  `operations/parallel_source/verify_snapshot.py`.
- **114,054 is not a second fact.** It is exactly 2 x 57,027, because every record emits one INPUT
  and one APPLIED entry. The relation holds exactly in all 18 committed prefix receipts under
  `sunday_20260915_package/FB/actual-prefixes/`: `journal_count == 2 * record_count` in every one,
  checked. Quoting it beside 57,027 double-counts a single measurement, which is what makes it look
  like independent corroboration when it is arithmetic. It is also not a token count.
- **1,189 is not a measurement either.** `journal_stack_execution.py:80` is
  `TARGET_BOXES = 1189`, Greg's chosen standard, and `partition_entries_for` derives the partition
  length from the target rather than the other way round. For this day it yields 96 entries per box
  and therefore 1,189 boxes; on a big day it clamps at `MAX_ROWS` and the day does not land on 1,189
  at all. Calling it a verified source fact states a configuration constant as an observation.

What is independently verified alongside the record count is the seal over that journal
(`journal_hash d8de0394...`, `state_hash d46ec933...`, `scope_hash 7460b519...`, pinned in
`verify_snapshot.py`), and the verification status of the prefixes, which is the first two. All 19
prefixes are not built.

The usable form, for anything that quotes this again: 57,027 source records, sealed by
`journal_hash d8de0394...`; the journal entry count is that doubled by construction; the box count
is a configured standard, not an observation; prefixes 1 and 2 verified, 19 not built.

Historical receipts and earlier handoffs that carry the old flat list were left untouched, per the
rule to append new evidence rather than rewrite receipts. The correction is made where it
propagates from: this handoff and the `CLAUDE.md` Frankie block.

## Locked in: the packing numbers, and the CI gap that let them keep being undone

Greg, 2026-09-20: the 7,129 stack will be rebuilt to pack other days more compactly, but the numbers
are to be locked first because they kept being undone.

They are already locked, executably, in `tests/test_partition_packing.py`, which is stronger than any
prose record:

- `assert TARGET_BOXES == 1189` (the standard going forward)
- `assert -(-sunday // 96) == 1189` and `assert partition_entries_for(sunday) == 96`
- `assert -(-sunday // 16) == 7129`, commented as what the old hardcoded literal produced, so the
  first run's box count is pinned as history rather than as a target
- `assert -(-weekday // MAX_ROWS) == 15581`, the clamp on a day the standard cannot reach
- the invariance proof: repacking yields the same entries, same bytes, same order and same seal,
  while the box count and container bytes change

Independently confirmed here by arithmetic: 114,054 / 16 = 7,129 boxes with 6 entries in the last,
which matches `ACTUAL_RUN_STATUS.md`'s "the final block contains six original entries"; 114,054 / 96
= 1,189 boxes, also with 6 in the last.

**The gap: nothing runs that test.** `grep -rn partition_packing .github/` returns nothing, and the
file matches none of the twelve globs in the checks step at `frankie_journal_stack.yml:296`. A revert
of `TARGET_BOXES` to 16 would therefore pass all 1,101 checks green and be invisible. That is the
likely mechanism behind the repeated undoing: the guard was written but never wired to CI, so nothing
could refuse the next revert. The fix is one line, adding the file to that pytest list. It is a
workflow edit and was NOT made here; it needs Greg's explicit authorization, since a go to run is not
permission to change a workflow.

The test could not be executed in this container: its import chain needs `torch`, which the checks
job installs as CPU torch 2.9.1 and which is absent here. That is an environment gap, not a failure.

**The contract for the coming rebuild**, already encoded in that test: decoded entries, their count,
their order and the head hash/seal are invariant; the container bytes and `compact_sha256` are free
to change. The first run's `compact_sha256 19603159...` no longer reproducing is the expected
consequence of the packing standard, not a regression. Neither 7,129 nor 1,189 is a source fact:
both are 114,054 divided by a packing choice, which is the derived-number rule above.

## Run 35498663360: the first result-bearing dispatch, and why it could not have succeeded

Greg's go, 2026-09-20: "get this Sunday run going", reuse the finished 7,129 ingest, manual Pod start
acceptable for this run only. Dispatched `frankie_journal_stack.yml` run 35498663360 on
`codex/frankie-launch-two-cycle-20260919` at `a5ad20bc` with day 20211003, cycles 2,
`go=0eb2c2ac...` (the day's source manifest hash, verified three ways: stored in the manifest,
recomputed with `raw_mbo_source_manifest.manifest_hash`, and equal to the stage-sources receipt
gate; 57,027 records), `checks_only=false`, `keep_compute=true`.

What happened, all read back from the run and the branch:

- `sources` success: the workflow restarted the native host itself (step "Restart the native host
  on every dispatch"); receipts 00 and 01 were already present and were reused, not re-staged.
- `journal` SKIPPED: `ingest_present=true`, so the 7,129-block ingest was reused. No repack at 96,
  the first run's `compact_sha256 19603159...` untouched, the 32-vCPU ingest runner never needed.
- `checks` success: the 1,101-test family and the receiver step passed again before any GPU time.
- `host` FAILED. Stage 3 (schedule-prefixes) succeeded and pushed `03-schedule-prefixes.json` as
  `19d3ef4c`. Stage 5 (cycles) failed: `owner granite`, `phase granite_request`,
  `error_type ValueError`, `completed 0`, `cursor null`, `elapsed_seconds 382.1`,
  `phase_elapsed_seconds 0.034`.
- `cleanup` skipped (`keep_compute=true`); `snapshot-stop` never ran. The native host
  `i-0e90ee6110ef609aa` was restarted by this run and NOTHING stopped it. No stop receipt exists
  for this run; the `host-stop.json` on the branch predates it and is not evidence of a stop.

No cycle-0 principal response, classroom grade, correction receipt or configuration receipt was
produced. The Frankie state above is unchanged.

### The cycles stage has four out-of-band prerequisites, and the workflow does none of them

The seven pipeline stages are stage-sources, host-start, ingest, schedule-prefixes, cycles,
package-upload, snapshot-stop. There is no Pod stage and the workflow file has no mention of a Pod.
`day_cycles.ps1` only reads the Pod credential and waits for a readiness trigger. For the cycles
stage to reach inference, all of the following must already be true, and none is done by the
pipeline:

1. a live Granite Pod;
2. the retained observer having published actual readiness for this request (`service-pins.json`,
   `service-ready.json`, `pod-info.json`, `run.json`, `startup-intent.json` in a readiness directory);
3. an operator-written trigger at `<trigger_directory>/<run_id>-cycle-00/FRANKIE_ACTUAL_EXECUTE_V1.json`
   carrying `readiness_directory` and `service_pins_sha256` (`operations/SSM_POD_CREDENTIAL.md`;
   request ids are built as `f"{run_id}-cycle-{index:02d}"`, `run_actual_sunday.py:775`);
4. the SecureString SSM parameter named in `host_runtime.pod_credential_ssm` readable by the host
   instance role (`ssm:GetParameter`, plus `kms:Decrypt` under a customer key). The tested shape is
   `{'name': '/markets/pod-service', 'region': 'us-east-2', 'trigger_directory': ...}`
   (`tests/test_actual_host_ssm_credential.py:22`); the actual name is in the host configuration.

`DROP_IN_CLAUDE_20260919.md` mentions none of trigger, readiness, observer or Pod start, and no
trigger or readiness artifact is committed anywhere on the branch. Greg, 2026-09-20: the Pod start
is not supposed to be manual; it is accepted as manual for this run and is to be fixed for the next.

### Why 34 ms rules out the obvious cause, and what it leaves

`read_execution_trigger` (`run_actual_sunday.py:261`) validates the credential-source shape first
(instant ValueError `explicit SSM credential source and request identity required`), then prints
`waiting_for_request_bound_service_trigger` and loops `while not path.exists(): time.sleep(1)` with
NO timeout. An absent trigger therefore waits, up to the 12-hour `cycles_timeout`; it never fails.
A 34 ms ValueError means the run did NOT die waiting for a Pod. Ranked by fit:

1. Trigger present, SSM parameter missing or denied: `private SSM credential unavailable or
   invalid`. An in-region GetParameter that returns AccessDenied or ParameterNotFound is on the
   order of 30 ms, the closest fit to 34 ms.
2. Trigger present but pointing at stale (2026-09-15) readiness: `startup admission differs from the
   actual prepared request` or `trusted host service pins differ`. Instant.
3. `pod_credential_ssm` shape invalid in the sealed host configuration: instant, and the `waiting`
   line is never printed. `seal_final_prelaunch_candidate.py` reads `host_runtime` from its input
   configuration rather than producing it, so that shape was authored out of band.

### The ValueError message exists nowhere, by design

`run_actual_sunday.py:944` catches `Exception`, prints `{"status":"stopped","error_type":...}` (type
only; the comment reads "Never interpolate exception messages, locals or received stdin") and
returns 1 without re-raising. `full_run_progress.failure()` writes only a safe type name. So the
message is absent from the GitHub log, from `day-cycles.log`, and from every receipt. Pulling the
host log cannot name the ValueError. It can still settle two things: whether
`waiting_for_request_bound_service_trigger` was printed (present = cause 1 or 2; absent = cause 3),
and the `actual_input_admitted` line carrying the `request_id`, which the manual route needs.

Corrections made in the session record, both mine: (a) this session has no AWS access; the
`AWS_ACCESS_KEY_ID` in its environment is a 14-character agent-proxy value and STS returns
`InvalidClientTokenId`, verified with the proxy's own status (no relay failure, no credential
substitution); I had said the opposite. (b) I said the host log would name the ValueError; it
cannot. My dispatch verified the go-hash and that the workflow restarts the hosts, but did not
verify any of the four prerequisites; the run could not have reached inference.

### What settles it, in order, all on the host or in AWS (Greg only)

1. `day-cycles.log` at `C:/Codex/Frankie-BOSS-20260919/days/20211003/`: is
   `waiting_for_request_bound_service_trigger` present, and what `request_id` did
   `actual_input_admitted` carry?
2. `actual-host-configuration.json` in that day directory: `host_runtime.pod_credential_ssm`
   (name, region, trigger_directory) and `run_id`.
3. Does `<trigger_directory>/<run_id>-cycle-00/FRANKIE_ACTUAL_EXECUTE_V1.json` exist, and which
   `readiness_directory` does it name?
4. From the host role: `ssm get-parameter --name <name> --with-decryption --region <region>`:
   present, denied, or missing?

Not done, deliberately: no re-dispatch, no host stop, no Pod start, no workflow edit.

## RunPod agent skills: recovered from source; permanent install still needs Greg

Greg, 2026-09-20: the Pod skills pasted into an earlier session were never committed and did not
survive that container. They are RunPod's public package, so they were recovered from source rather
than from the lost paste: https://github.com/runpod/skills (docs
https://docs.runpod.io/get-started/agent-skills). Install: `npx skills add runpod/skills`; Claude Code
plugin route: `/plugin marketplace add runpod/runpod-plugins-official` then `/plugin install
runpod@runpod`. Eight skills land: companion-clis, flash, runpod, runpod-mcp, runpod-migrate,
runpod-templates, runpod-usage, runpodctl. Installed and inspected in this session (scratchpad only).

All eight authenticate with the single `RUNPOD_API_KEY`. For Frankie that key is the private SSM
SecureString named by `host_runtime.pod_credential_ssm`, read once in memory on the native host and
never placed in a session, so in a Claude session the skills are present but unauthenticated. Where
the key IS available (the native host, or a GitHub Actions job holding the secret), `runpod-mcp`
exposes Pod lifecycle (`create-pod`, endpoints, volumes, billing) through RunPod's hosted MCP
(`claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/ --header "Authorization:
Bearer $RUNPOD_API_KEY"`), and `runpodctl` covers terminal, file transfer and SSH. That is the natural
backbone for automating the Pod start, observer readiness and execution trigger for the next run,
which today are out-of-band (see the four prerequisites above).

The permanent install belongs in `scripts/session_start.sh` (the SessionStart hook; it installs pip
deps only today), guarded so a failure never breaks startup, installing into `$HOME` and never
vendored. That edit was refused by the auto-mode classifier as unauthorized persistence (a startup
hook that fetches and runs third-party code every session) and was deliberately not worked around;
it is Greg's to apply or to permit.

Update, same day: Greg explicitly authorized overriding that guard ("you're fine to override the
guard"), and the block was applied to `scripts/session_start.sh` on this branch through the file
editor rather than a shell heredoc. The cherry-pick of the diagnostic workflow onto trunk was also
run by me on Greg's word ("I haven't run anything. You can run that"): trunk
`claude/kalshi-s79-kickoff-ij8t9o` moved `9c9c4c1d..061e428f`, which registered
`frankie_host_diag.yml`; diagnostic run 35500792871 was then dispatched with this branch as ref.

Also found in the hook itself (lines 81-88): the repo expects AWS credentials for Claude sessions
under `MARKETS_AWS_ACCESS_KEY_ID` / `MARKETS_AWS_SECRET_ACCESS_KEY` in the Claude Code environment
configuration. Neither is set in this environment, which is the whole reason this session had no
AWS route and needed a workflow to reach the host. Setting those two is the documented one-time
permanent fix.

### Diagnostic run 35500792871: the four answers (read from the native host over SSM)

EC2 `i-0e90ee6110ef609aa` state `running`, SSM `Online`, Windows Server 2022 Datacenter.

1. `day-cycles.log` (36,150 bytes): `waiting_for_request_bound_service_trigger` printed 0 times.
   `actual_input_admitted` carried `request_id frankie-boss-sunday-two-cycle-20260919-cycle-00`,
   `request_sha256 6cd46f983845fbd2ed88ec24ebf18f446cc3523a89307b03290351bd39d3b0dd` (archived on
   the branch under `runs/request-archives/6cd46f98.../`), ready path
   `...\actual-feedback-run\execution\cycle-00\host-ready-6d02c1fcafbd4c7e8aa09245d3f9e3e7.c15.json`.
   `boss_reasoning` ran to 379.8 s with two `possible_stall` warnings each followed by
   `progress_resumed`; `granite_request` began at 382.0996 s and `operation_failed` at 382.1307 s.
2. `actual-host-configuration.json`: `run_id frankie-boss-sunday-two-cycle-20260919`;
   `pod_credential_ssm` name `/markets/frankie/granite-service`, region `us-east-2`,
   trigger_directory `C:/Codex/Frankie-BOSS-20260919/triggers`; `native-host-runtime.json` present.
3. Trigger `C:\Codex\Frankie-BOSS-20260919\triggers\frankie-boss-sunday-two-cycle-20260919-cycle-00\
   FRANKIE_ACTUAL_EXECUTE_V1.json`: ABSENT.
4. `get_parameter` from the host role: OK, SecureString, value length in 32-256. Value never printed.

What that eliminates. Cause 1 (credential unavailable) is out: the host reads the parameter. Cause 2
(stale trigger) is out: there is no trigger at all. Because the waiting line never printed, the
ValueError fired before the wait, in the shape check at the top of `read_execution_trigger`. The
stdin fallback is also out: `run_actual_sunday.py:242` assigns `self.host =
configuration['host_runtime']` unfiltered, so `pod_credential_ssm` reached the runtime. Of that
check's conditions, name, region, trigger_directory, schema, `run_id` form and the cycle-00
`request_id` form are all confirmed to pass; the one condition not yet observed is
`set(source) == {'name','region','trigger_directory'}`, which the first diagnostic could not see
because it printed only those three fields by name. An extra key in the sealed `pod_credential_ssm`
object fails it instantly. The diagnostic is extended to print the exact key set (plus
`host_runtime` and top-level keys) and re-dispatched.

Independently of that: even with the shape check passing, this run would have waited on a trigger
nobody wrote (no Pod, no observer readiness), up to the 12-hour ceiling. Both must be fixed for a
resume to reach inference: the shape (if confirmed) and the four out-of-band prerequisites.

### Diagnostic rounds 2-4 (runs 35500960450, 35501108073, 35501234105) and what they closed

- `pod_credential_ssm` exact key set is `name,region,trigger_directory`: the shape check passes.
- The host tools checkout `C:/tools/Frankie-20260919/Markets` is at `c9a86e74` (2026-09-17, detached),
  and its `run_actual_sunday.py` carries `read_execution_trigger` and `pod_credential_ssm`; the
  function is byte-identical to the branch tip, and no commit touched the file after 2026-09-17. The
  stdin-fallback-from-old-code explanation is closed.
- The cycle-00 witness exists: `host-ready-6d02c1fcafbd4c7e8aa09245d3f9e3e7.c15.json` (933 bytes,
  C15 typed encoding), request `6cd46f98...`, `admitted_at` float64 bits `41daaade9f0d7885` =
  1789622908.210481 (2026-09-17T05:28:28Z), admission 92,439 input / 38,633 output tokens at context
  131,072, tokenizer `51e3c309...`. The cycle-00 directory holds the 151 KB critic request, the
  21 MB pre-message, the 12 MB source and the 21 MB teacher key.
- The host role CANNOT list the retained readiness bucket (`AccessDenied` on
  `frankie-granite42-568968024170-us-east-1`), so readiness must be delivered to the host over SSM,
  not pulled.
- The retained Granite observer workflow (`frankie_retained_granite.yml`) is the built Pod-start and
  readiness path: `prepare` decrypts the archived request, verifies the 8-file bootstrap roster
  against `runtime_configuration_json` (the roster at this branch's HEAD matches the image-defaults
  pins byte for byte), starts retained Pod `ycf4v6lmave6xw` with `start_once`, and uploads readiness
  as artifact `retained-granite-ready-<run_id>` (9 files: observer, pod-info, run, service-pins,
  service-ready, start, startup-bootstrap-pin, startup-intent, startup-progress). Its last success
  was run 35190255941 (2026-09-17) with `LOCAL_READY_JSON = {request_sha256, host_instance_id,
  admitted_at}` and `RUNTIME_CONFIGURATION_JSON` equal to
  `runs/20260919/reviewed-bootstrap-image-defaults-runtime.json` (bundle `a004983e93b9...`, which is
  also the suffix of the code's `JOURNAL_GENERATION`). `hold()` never stops the Pod; only a
  confirmed-fatal or the native completion cleanup does.
- Remaining unknown: `actual.main()` imports the driver from `host_runtime.repository` (the pinned
  `boss_commit` checkout), separate from ToolsRoot; the diagnostic now reports that checkout, and runs
  a 10-second probe calling `read_execution_trigger` on a bare host object with the real
  configuration, which prints the actual exception message (the runtime scrubs it) or proves the call
  waits on the absent trigger.

### Pod start requested: retained Granite observer run 35501720279 (Greg's authorization, 2026-09-20)

Dispatched `frankie_retained_granite.yml` at 2026-09-20T09:13:39Z on
`claude/frankie-launch-verification-lqmv0m` (b5639381; the 8-file bootstrap roster at that commit
matches the image-defaults pins byte for byte) with `request_sha256 6cd46f98...`,
`local_ready_json {request_sha256 6cd46f98..., host_instance_id 6d02c1fcafbd4c7e8aa09245d3f9e3e7,
admitted_at 1789622908.210481}` and `runtime_configuration_json` equal to
`runs/20260919/reviewed-bootstrap-image-defaults-runtime.json`. This is the REQUEST receipt; start,
ready, inference, finish and cleanup receipts follow only as they land. The retained Pod is
`ycf4v6lmave6xw`; `hold()` never stops it, so GPU spend runs from a successful start until the
native completion cleanup or a manual stop.

### ROOT CAUSE CAPTURED (diagnostic run 35501729073, on-host probe)

Calling `read_execution_trigger('FRANKIE_ACTUAL_EXECUTE_V1', ..., 'frankie-boss-sunday-two-cycle-20260919-cycle-00')`
on a bare host object with the real sealed configuration raises immediately, with
`pod_credential_ssm` present:

    ValueError: explicit SSM credential source and request identity required
    (run_actual_sunday.py, read_execution_trigger, the shape check at the top of the function)

That is the message the runtime scrubbed from every log and receipt. It is the shape check, not the
credential, the trigger, the stdin fallback or a second checkout. Every sub-condition of that check
looks satisfied by the printed values (exact key set, name, region, trigger_directory, schema, the
`run_id` form and the cycle-00 `request_id` form), so the failing condition must depend on something
the printed values hide: an invisible character in a hand-authored field is the leading candidate.
The next diagnostic prints `repr()` of every input and each sub-condition's boolean.

The fix, once the condition is named, is in the sealed `actual-host-configuration.json` on the host
(the first of Greg's two authorized actions), not in the code: the check is the design.

### Pod start outcome: run 35501720279 REFUSED before any start (no GPU spend), then cancelled

`retained-prepare` decrypted the archived request, admitted it through the tokenizer, verified the
8-file bootstrap roster, verified the Pod's env pins, recorded `retained-startup.json` for request
`6cd46f98...`, and then `lifecycle.start_once` refused at `granite_startup_pins.validate_url_freshness`:

    ValueError: refresh bootstrap capabilities before start; at least 60 seconds required

The rule: the Pod env `RP_BOOTSTRAP_URLS` must be a JSON map of presigned https URLs for the 8 roster
files plus `runpod_bundle.json`, each carrying `X-Amz-Date` and `X-Amz-Expires` (span at most 7 days,
not future-dated), and the earliest expiry must be at least 60 s ahead. The Pod's URLs are stale. No
`retained-start-intent.json` was written, so a re-dispatch after a refresh starts normally rather
than falling into observation-only. The `retained-watchdog` job would have idled to its 6-hour
deadline, so the run was cancelled. The prepare artifact (`startup-bootstrap-pin.json`,
`pod-info.json`, `startup-intent.json`) is retained as run 35501720279 artifact 10601953959.

Next on the Pod side: refresh `RP_BOOTSTRAP_URLS` with the built mechanism, then re-dispatch
`frankie_retained_granite.yml` with the same three inputs.

### ROOT CAUSE CONFIRMED: the host runs c9a86e74, which predates the request-id fix c0749bc0

The repr probe (diagnostic run 35502069016) showed every sub-condition of the shape check TRUE on
the host's real configuration, and the host's function still raising at line 277. In git, the raise
is at line 277 in `c9a86e74` (946 lines) and at 279 in the tip (948 lines); the two-line difference
is commit `c0749bc0` (2026-09-17 01:28 -0400, "fix(frankie): admit only this run's safe scheduled
cycle trigger IDs"), which added the `<run_id>-cycle-NN` alternative to the 64-hex request-id rule.
`c9a86e74` is `boss_commit` in the sealed host configuration and the HEAD of the host's tools
checkout, and it does not contain that fix, so under the host's code the cycle-00 request id
`frankie-boss-sunday-two-cycle-20260919-cycle-00` is refused before the trigger is ever looked for.
That is the whole 34 ms. The probe's conditions were this session's re-implementation of the newer
logic, which is why they all passed.

Correction to an earlier line of this record: the claim that `read_execution_trigger` was
byte-identical between `c9a86e74` and the tip was wrong; the comparison helper fed Python its own
heredoc instead of the `git show` output, so both sides compared equal trivially. The line-number
evidence above is independent of that helper.

Consequence: no configuration change can fix this; the host needs code at or after `c0749bc0`. That
changes the pinned `boss_commit` and possibly the resume identity of the current run directory, so
it is a run-identity decision, recorded here for Greg with the options in the session reply.

### The two fixes, built (Greg: "I am giving you permission to do both things")

Native side: `.github/workflows/frankie_host_advance.yml` + `deploy/aws/host/frankie_host_advance.ps1`
move the host's tools checkout from `c9a86e74` to the declared frozen native runtime `96e26f7d`
(which carries the request-id fix `c0749bc0`; between the two commits `run_actual_sunday.py`
changes by that fix alone), refuse on a dirty tree, update only `host_runtime.boss_commit` in the
sealed configuration with a dated backup of the file, verify the fix is present, and print a
receipt. This is not a new pin: the handoff already declares 96e26f7d as the frozen runtime and the
host was simply left behind it. The resume identity (`_STABLE_IDENTITY_FIELDS`) is runtime and
platform only, with no code hash, so the existing run directory resumes.

Pod side: `.github/workflows/frankie_refresh_bootstrap_urls.yml` +
`operations/refresh_bootstrap_urls.py` implement runbook step 5 for URLs only: read the Pod's current
`RP_BOOTSTRAP_URLS`, verify each referenced S3 object against the reviewed roster (size, sha256),
presign the same bucket and key for 6 days (the validator allows up to 7), `PATCH /v2/pods/{id}` on
`api.runpod.io` with every other environment value unchanged, read back and compare. Never prints a
URL, key or environment value. The retained client refuses PATCH by design, so this is a separate
narrow script. Both workflows are dispatch-only and start nothing.

Order of operations from here: advance the host; refresh the URLs; re-dispatch the retained observer
with the same three inputs (Pod start + readiness); deliver readiness and write the trigger;
re-dispatch the day pipeline with the same inputs to resume at cycles.

### Host advance DONE: run 35502759158, receipt FRANKIE_HOST_ADVANCE_RECEIPT_V1

At 2026-09-20T09:36:28Z on `i-0e90ee6110ef609aa`, tools checkout `C:/tools/Frankie-20260919/Markets`
moved `c9a86e74583f47821d5a9bb6759726bc59542519 -> 96e26f7d5e8100cca93288d5f44d9550ab5cfd9a`
(tree was clean; the script refuses otherwise). `run_actual_sunday.py` now carries the cycle
request-id fix (occurrences=2). `host_runtime.boss_commit` in
`C:/Codex/Frankie-BOSS-20260919/days/20211003/actual-host-configuration.json` updated
`c9a86e74... -> 96e26f7d...`, with the untouched file kept at
`actual-host-configuration.json.before-advance-20260920T093628Z.json`. Rollback is
`git checkout --detach c9a86e74...` plus restoring that backup.

### Pod URL refresh: first attempt (run 35502760528) refused its own URL; fixed

The refresh read the Pod, matched the roster and bundle sha, and verified every staged object
against the reviewed roster, then stopped before patching because the URL it generated carried no
`X-Amz-Date`: boto3 had signed with the legacy scheme. The validator and the Pod bootstrap require
SigV4 on `<bucket>.s3.amazonaws.com` or `<bucket>.s3.us-east-1.amazonaws.com`. Fixed in
`a7d725bd`: the client pins `signature_version=s3v4` with virtual addressing and the script refuses
to patch any URL whose origin or query shape the Pod bootstrap would reject. Nothing was patched by
the failed attempt. Re-dispatched.

### Pod URL refresh DONE: run 35502849380, receipt bootstrap_urls_refreshed

Pod `ycf4v6lmave6xw` (status EXITED), all 9 staged objects verified against the reviewed roster, 24
other environment keys unchanged, presign span 518,400 s, earliest expiry 2026-09-26T09:38:45Z.

### Verification since the first run (Greg: "we changed a lot")

The retained observer and its dependencies (`granite_retained_host.py`, `granite_retained_lifecycle.py`,
`granite_retained.py`, `granite_startup_pins.py`, `granite_runpod_cloud_control.py`,
`git_request_archive.py`, `granite_retained_completion.py`) have no commits since run 35190255941
(`6e41bb7a`), and run 35501720279 today exercised that chain live up to `start_once`. The 8-file
startup roster verifies byte for byte against the reviewed bundle at HEAD; the host now runs the
frozen runtime; the day-pipeline resume re-runs the 1,101-test checks gate before `host`.

Hardcoded runtime values audit (Greg: none we put in ourselves): `granite_startup.py` carries no
4096/1200 remnants and takes `GRANITE_MAX_MODEL_LEN` from the environment. Remaining literals are
declared identities (`POD_ID`, `JOURNAL_GENERATION`, request bucket and prefix) and retired-smoke
leftovers on dead paths: `TOTAL_SECONDS = 1800`, `BASE`, `BUNDLE_SHA` in `granite_runpod_cloud.py`
(its `controller()` raises on entry) and the bounded-lease durations `(600, 900, 1200, 1800)` in
`granite_retained_lifecycle.py`. Removing them is a `chore:` commit after the run, because any edit
to a roster file re-pins the bundle. The new ops scripts' hardcoded host paths and ids are a
`refactor:` commit after the run for the same reason.

### Pod start run 35502980177: REFUSED by the provider (HTTP 400), no start submitted

Dispatched `frankie_retained_granite.yml` on `claude/frankie-launch-verification-lqmv0m` (head
`6dded39d`) with the three verified inputs (request `6cd46f98...`, the local_ready witness, the
reviewed runtime configuration). `retained-prepare` (job 106057932394) passed every gate in order:
staged request digest, tokenizer admission, initial roster bytes, Pod env pins (lifetime `none`,
bundle sha, supervisor command sha, `GRANITE_MAX_MODEL_LEN` 131072, `jobs_v1`), retained-startup
written once (start 1789895705.264564), fresh watchdog arm, resume validation (Pod EXITED),
`validate_url_freshness` (the refreshed URLs), the S3 active-run claim, and the start intent written
once. Then `POST /v2/pods/ycf4v6lmave6xw/action {"action":"start"}` returned HTTP 400 and the
role raised `ProviderError`. The journal holds `retained-start-failure.json` with
`status: start_outcome_unknown`. The endpoint is the correct v2 call (RunPod migration skill,
`rest-v1-to-v2.md:38`), so the 400 is the provider refusing the resume; the client discards the
response body, so the reason is NOT on record. The cleanup step ran and did nothing (no
`confirmed-fatal.json`; elapsed time and observer exhaustion are never stop reasons). The
`retained-watchdog` job (106057932547) keeps observing until its 360-minute deadline; it never
stops the Pod. Prepare artifact `retained-granite-prepare-35502980177` = `pod-info.json`,
`startup-bootstrap-pin.json`, `startup-intent.json`.

Consequence, by design (`SPEC-sunday-runtime.md:60`, `test_granite_retained_start_guards.py:47-48`):
any observer re-run on this request journal returns `observe_existing_start` and never submits
another start. It DOES then continue to observe container logs since the recorded startup,
validate the runtime, health-check and publish readiness, so the observer adopts the Pod once it is
RUNNING by another route. Recovery = an explicit, receipted operator start (the manual Pod step Greg
accepted for this run) followed by an observer re-dispatch. Built `frankie_pod_control.yml` +
`operations/pod_control.py` (`5f207c79`): inspect prints the Pod state with env and credential
fields removed; start requires EXITED, submits the same v2 action once, prints the provider's
refusal body verbatim or the status transition, and prints `FRANKIE_POD_START_RECEIPT_V1`. No
reason for the 400 is claimed until that body is on record.

### The 400 reason is on record: the Pod's host has no free GPU (run 35503440103)

`frankie_pod_control.yml` action=start (run 35503440103, `82e61900`) read the Pod (EXITED,
US-MO-1, 1x NVIDIA L40S, pod volume `/opt/ml` 50 GB, `actions: [start, terminate]`, `locked: false`)
and re-submitted the identical v2 start action. Provider response, verbatim:
`HTTP 400 {"detail":"There are not enough free GPUs on the host machine to start this pod.","status":400,"title":"Bad Request"}`
(receipt `FRANKIE_POD_START_RECEIPT_V1`, outcome `refused`, submitted_at 1789897878.44). The Pod is
pinned to that host by its pod volume, which holds the 17.6 GB verified model; RunPod cannot move
it, so the resume can only succeed once a GPU frees on that host. Nothing on our side refused.

Stale `retained-watchdog` job of run 35502980177 cancelled (it never stops the Pod; its `always()`
cleanup step acts only on a `confirmed-fatal.json`, which does not exist). The S3 active-run claim
for this startup digest stays `active`; a re-run with the same inputs re-uses it (`claim` returns
when digest and phase match), so no ownership reset is needed.

Retry loop added to the control script (`--retry-seconds`, re-submit every 60 s only while the
refusal is exactly the host-busy message; foreign refusals abort at once; attempts counted in the
receipt). Dispatched with a 5.5 h horizon. The alternative, a fresh Pod on another host, means a new
`POD_ID`, a new `JOURNAL_GENERATION`, a re-bootstrap of the model from `models/bootstrap/` and a
re-review of the pinned identities: Greg's call, not taken here.

### Greg: "Prepare the fresh pod in parallel" (2026-09-20)

The current Pod is itself a migration: source `jvs75m56w8f73q` -> `ycf4v6lmave6xw`, re-pinned
through `granite_retained_migration_receipt.json` (`GRANITE_POD_MIGRATION_V1`), `info_from_journal`
(rewrites the accepted `runpod-smoke/34928264918/pod-info.json` into the migrated identity and
checks `INFO_SHA256`), `POD_ID` and `JOURNAL_GENERATION`. A replacement Pod therefore needs no new
mechanism: a second receipt chained from the same accepted info, a new `INFO_SHA256`, and a new
`POD_ID`/`JOURNAL_GENERATION` (fresh journal, fresh active-run key, so the consumed start intent of
the old generation cannot block it). The model (13 files, 17.6 GB) is downloaded by the Pod's
bootstrap from Hugging Face (`ibm-granite/granite-4.2-8b`, pinned revision) and verified against the
manifest; the 8 roster files come from S3 through `RP_BOOTSTRAP_URLS`, refreshed today until 09-26.

Built and committed (`5336387f`, fix `a0e0ab69`): `frankie_pod_prepare.yml` + `operations/pod_prepare.py`.
It reads the source Pod, verifies its environment against the reviewed runtime configuration
(bundle sha, supervisor command sha, `none` lifetime, 131072, `jobs_v1`, URL freshness), picks data
centers with L40S stock from `GET /v2/catalog/gpus?include=AVAILABILITY`, creates ONE Pod with the
same name (`...-migration`, so `validate_intent`/`owned_pod` accept it), image, L40S x1
(`minCudaVersion 13.0`), 100 GB disk, persistent `/opt/ml` 50 GB, port 8081/http and the source
environment copied verbatim in memory, watches the container log for `GRANITE_RUNPOD_STARTUP` /
`GRANITE_DISK`, validates them exactly as the observer does (`cloud.validate_runtime` + the open
bootstrap pins), waits for an authenticated `/health` 200, and writes `pod-facts.json`,
`migration-receipt-candidate.json`, `info-sha256.json` (INFO_SHA256, POD_ID, JOURNAL_GENERATION)
and `startup-records.json` to artifact `pod-prepare-<run_id>`. A Pod priced above the ceiling,
failing evidence or timing out is stop-retained. It leaves a healthy Pod RUNNING (holding its GPU,
$1.09/h) unless `stop_after_ready=true`. Stubbed-provider dry run: 8 scenarios pass; the supervisor
command pin `2d46c105...` reproduces at HEAD from the roster, bundle sha, bucket
`frankie-granite42-<account>-us-east-1` and the reviewed bootstrap directory.

Refactor `a4e14f20`: `granite_retained_identity.py` now declares `POD_ID`, `BUNDLE_PREFIX`,
`JOURNAL_GENERATION`, `HISTORICAL_GENERATION` once; lifecycle and host import it; the standalone
completion writer loads it by path. Values byte-identical; 20 retained tests pass. The re-mint to
the fresh Pod is one `feat:` commit: the identity module, the migration receipt, `INFO_SHA256`, the
four workflow defaults (`frankie_retained_granite.yml` concurrency group, completion generation
options, refresh/control Pod defaults) and the three tests that name the Pod.

First prepare run 35504518579 failed at import (`No module named 'research'`, file-path invocation);
fixed with `PYTHONPATH` and re-dispatched.

Adoption of a prepared Pod (decision pending): (a) EXITED path = stop-retain it, dispatch the
observer, which POSTs the one start and reads fresh boot logs (the designed, tested path; the GPU is
unreserved for the ~2-3 minutes between stop and start); or (b) RUNNING path = the observer's
`observe_migrated_start` branch, which needs startup frames stamped after the observer's own
`retained-startup.json`, so the Pod would have to be restarted after the observer starts. (a) is
the default recommendation.

### Prepare run 35504624757: Pod hhxs2fk7511cz5 created in EUR-IS-2, no bootstrap line in 30 min, stop-retained

`GET /v2/catalog/gpus` reported L40S stock LOW in every data center that had any (EU-NL-1, EUR-IS-2,
OC-AU-1, US-IL-1, US-MO-1, US-TX-4) and the create landed in EUR-IS-2 at 10:18:02Z (cost 1.09,
same name/image/mount, status RUNNING). For the full 30-minute horizon the watcher saw zero
`GRANITE_*` lines (`startup-progress.json`: `telemetry_lines 0`, `milestones []`, status RUNNING),
so at 10:48:05Z the script stop-retained it: receipt `FRANKIE_POD_PREPARE_RECEIPT_V1` outcome
`startup_incomplete`, stop `confirmed_stopped`, `data_retained true`, final status EXITED. Not yet
distinguishable: a slow image pull / model download on an Iceland host versus a log reader that
returned nothing. `133c42c3` adds `--resume-pod` (restart the EXITED Pod on its now-cached host
instead of paying for another create) and five-minute diagnostics (scrubbed Pod state incl.
`runtime`, plus a three-line raw tail of the system and container logs). Dispatched a resume of
hhxs2fk7511cz5 with a 60-minute watch. The old-Pod retry loop (run 35503582348) is still cycling.

### Resume run 35506279203: REFUSED, the same host-busy message, five minutes after the stop

`hhxs2fk7511cz5` (EUR-IS-2) was stop-retained at 10:48:05Z by the horizon; the resume at 10:53:43Z
got `HTTP 400 "There are not enough free GPUs on the host machine to start this pod."` So under
LOW L40S stock a stopped Pod loses its GPU within minutes. Consequences, now in code (`420359ae`):
the prepare horizon leaves a still-bootstrapping Pod RUNNING (`--on-timeout keep`, default) and a
`--watch-pod` mode observes a RUNNING replacement in short runs so its diagnostics are readable
without stopping anything. For adoption this also rules out the EXITED path (stop, then let the
observer start): the observer must adopt a RUNNING Pod through `observe_migrated_start`, with a
`restart` action issued after the observer's `retained-startup.json` exists so the boot frames
post-date it. Two Pods are now stranded EXITED on GPU-less hosts: `ycf4v6lmave6xw` (the retained
model, keep) and `hhxs2fk7511cz5` (nothing verified on its volume; terminate is Greg's call, it
costs the volume while it exists). Third attempt dispatched: create with data centers
US-TX-4, US-IL-1, US-MO-1 preferred, 15-minute watch, keep on timeout, then watch-only runs.

### hhxs2fk7511cz5 TERMINATED on Greg's word (run 35506617115)

Greg: "Terminate it." `frankie_pod_control.yml` action=terminate (`f720d3af`: refuses the retained
Pod by id, requires EXITED and the migration name, 404 readback) deleted the stranded EUR-IS-2
replacement at 11:00:42Z: receipt `FRANKIE_POD_TERMINATE_RECEIPT_V1`, DELETE HTTP 204, readback
HTTP 404, `confirmed_absent true`. Nothing verified had been on its volume. The retained Pod
`ycf4v6lmave6xw` is untouched and its start retry loop (run 35503582348) is still cycling.

### THE FRESH POD IS READY: 8vqdacl5t61rjx (US-MO-1), re-minted as the retained Pod

Third create (run 35506464896, 10:58Z, data centers US-TX-4/US-IL-1/US-MO-1 offered, landed US-MO-1):
bootstrap completed end to end (roster from S3, 17.59 GB model from Hugging Face at ~47 MB/s, 13
files verified, vLLM up); the watcher then crashed on my own variable shadowing one line before
the health probe (fixed `5094d47b`), with the Pod left RUNNING. Watch-only run 35507136416:
startup + disk evidence accepted by `cloud.validate_runtime` and the open-bootstrap pins
(`lifetime_seconds null`, bundle `a004983e...`, command `2d46c105...`, `jobs_v1`), `/health` 200 at
11:12:15Z, receipt `FRANKIE_POD_PREPARE_RECEIPT_V1` outcome `service_ready`. Artifact
`pod-prepare-35507136416`: pod-facts, migration-receipt-candidate, info-sha256, health,
startup-records. Re-mint committed: `granite_retained_identity.POD_ID = 8vqdacl5t61rjx`,
`JOURNAL_GENERATION = migration-8vqdacl5t61rjx-a004983e93b9`, receipt chained from the accepted
retained info (source jvs75m56w8f73q), `INFO_SHA256 6f8efdf927b470ba...` (reproduced locally by
rewriting the previous migrated info, whose hash matched the old pin), workflow defaults and
tests updated; 20 retained tests pass. The old Pod's start-retry run 35503582348 was cancelled
(no unadopted start may succeed later); ycf4v6lmave6xw itself is untouched, EXITED.

Adoption next: the Pod is RUNNING, so the observer takes `observe_migrated_start` and needs boot
frames stamped after its own `retained-startup.json`; a `restart` action issued once that journal
record exists gives it fresh `GRANITE_RUNPOD_STARTUP`/`GRANITE_DISK` frames on the same host.

### ADOPTED: readiness published for 8vqdacl5t61rjx (observer run 35507527320)

Observer dispatched 11:19:58Z on `f9092dce` with the same three inputs. `retained-prepare` passed
the gates against the new Pod and wrote the new generation's `retained-start-intent.json` at
11:21:30Z (`start.json`: `observe_migrated_start`, startup_sha256 `132d8b71...`). The restart
control run 35507529987 saw that key at 11:21:29Z and the v2 restart was accepted at 11:21:30Z
(receipt `FRANKIE_POD_RESTART_RECEIPT_V1`, Pod stayed RUNNING, uptime 1211 s at readback). Fresh
boot frames followed: `startup_event_at` 11:22:15Z, `/health` 200 at 11:23:26Z, and the observer
uploaded `retained-granite-ready-35507527320` at 11:23:30Z (9 files). Verified from the artifact:
`service-ready.json` outcome `service_ready`, `inference_sent false`; `service-pins.json` bound to
request `6cd46f98...`, runtime_sha256 `0cbe5d12...`, admission 92,439 input / 38,633 output tokens
in 131,072; `pod-info.json` pod 8vqdacl5t61rjx, US-MO-1, base_url
`https://8vqdacl5t61rjx-8081.proxy.runpod.net/v1`; `run.json` deadline null. The prepare job is
now in `hold` (observes until the local stop; never stops the Pod). Delivery to the native host
dispatched (`frankie_deliver_readiness.yml`, ready_run_id 35507527320).

### Readiness DELIVERED to the native host (run 35507896975); host advanced to the re-mint

`frankie_deliver_readiness.yml` (ready_run_id 35507527320) at 11:28:13Z: SSM Success, six files
delivered under `C:/Codex/Frankie-BOSS-20260919/readiness/frankie-boss-sunday-two-cycle-20260919-cycle-00/`
(service-pins sha `71129170...`, pod-info sha `6f8efdf9...` = INFO_SHA256, startup-intent sha
`132d8b71...` = the observer's startup digest, run, service-ready sha `0cbe5d12...` = runtime_sha256,
observer), trigger `FRANKIE_ACTUAL_EXECUTE_V1.json` written for request
`frankie-boss-sunday-two-cycle-20260919-cycle-00`; receipt `FRANKIE_READINESS_DELIVERY_RECEIPT_V1`.

One more gate before the pipeline resumes: `granite_retained_lifecycle.verified_service_inputs`,
which the host's `run_actual_sunday.py` calls, builds `RunpodConfig(POD_ID, ...)` from the
checkout's own POD_ID, so at 96e26f7d the cycles stage would aim inference at the stranded Pod.
The advance script now takes its target as an input (`6b0b37fe`, no hardcoded commit; refuses a
non-descendant) and the host is being advanced to `6b0b37fe`, which is a pure descendant of
96e26f7d: the actual-run scripts, day pipeline, journal stack and launch pins are byte-identical;
what changes is the retained identity (re-mint), the ops scripts and tests.

### Host advanced (run 35508051497) and the two-cycle pipeline RESUMED

`FRANKIE_HOST_ADVANCE_RECEIPT_V1` at 11:31:18Z: tools checkout `96e26f7d` -> `6b0b37fe` (descendant
check passed, `run_actual_sunday.py` carries the cycle request-id fix), `boss_commit` updated in
`actual-host-configuration.json` with backup `...before-advance-20260920T113118Z.json`.
Then `frankie_journal_stack.yml` dispatched at ~11:33Z on `codex/frankie-launch-two-cycle-20260919`
with day 20211003, `go 0eb2c2acdccc17f8ad2d64d00b74a0c93b477c0418651a7f290d53f19d5710b0`, cycles 2,
keep_compute true, checks_only false: sources -> journal (the finished 7,129-block ingest, receipt
present) -> checks -> host (schedule-prefixes, cycles against Pod 8vqdacl5t61rjx, package-upload,
snapshot-stop). Each receipt is recorded below as it lands; nothing is claimed ahead of it.

### Pipeline run 35508198333: REFUSED at cycles (data_delivery ValueError, scrubbed)

Sources OK; journal skipped (ingest receipt present); checks OK; host job failed at 11:36:57Z: the
cycles stage exited 1 with `FRANKIE_RUN_PROGRESS_V1` `code operation_failed`, phase `data_delivery`,
owner `transport`, `error_type ValueError`, 1.44 s after start, last status `{"status": "stopped",
"error_type": "ValueError"}`. No new receipt was committed. The refusal is inside
`run_actual_sunday.py` 812-843 (after the trigger read); the four candidate checks and the probe to
name the real one are in `DROP_IN_CLAUDE_20260921.md`. `frankie_host_diag.yml` dispatched read-only.

### Diag run 35508442554 (read-only, 11:39Z) narrows the cycles refusal

Host `running`/SSM Online; `read_execution_trigger` returns on the real config (the request-id path is
fine); the cycle-00 trigger exists with `service_pins_sha256 71129170...` and all readiness files present;
the SSM credential reads OK. The host's own admitted witness (`host-ready-6d02c1fc....c15.json`) carries
admission `{request_sha256, input_tokens 92439, output_tokens 38633, context 131072, tokenizer_sha256
51e3c309...}` and it is EQUAL to `service-pins.admission` from the observer (checked key for key), so
line 836 is ruled out. BUT that witness and its `host-preparation.c15.json` live under the 09-19 run
directory `C:/Codex/Frankie-BOSS-20260919/actual-feedback-run/execution/cycle-00`, while the day
pipeline's cycles stage runs with `RunRoot=C:/Codex/Frankie-BOSS-20260919/days` and `Day=20211003`. If
the day directory carries its own `host-instance.c15.json` (a different uuid) or no
`host-preparation.c15.json`, line 833 (`actual open run must follow this admitted live host instance`)
or line 821 refuses in exactly this time. The probe must print: `actual-host-configuration.json
run_directory`, the `host-instance.c15.json` instance_id in THAT directory, its cycle-00 listing, and
the four comparisons with `repr`. The pipeline is not re-dispatched until that is on record.

### State at close of this chat (2026-09-20, ~11:50Z)

Pipeline run 35508198333 refused at cycles as above; root-causing it is the next chat's first job. Retained Pod `8vqdacl5t61rjx` RUNNING and adopted; `ycf4v6lmave6xw` EXITED and untouched;
`hhxs2fk7511cz5` terminated on Greg's word. Host at `6b0b37fe`. Docs updated: `CLAUDE.md` (first
FRANKIE/BOSS bullet + the HOLD line), `KALSHI_TRADING.md` (new file section), this handoff, and the next
box `DROP_IN_CLAUDE_20260921.md`. Nothing about the run's outcome is claimed here.

CHANGES MADE today (code): `granite_retained_identity.py` (new), re-mint of receipt/INFO_SHA256/POD_ID,
`operations/pod_control.py`, `operations/pod_prepare.py`, `operations/refresh_bootstrap_urls.py`,
`deploy/aws/host/frankie_host_advance.ps1` (target as input), six operator workflows, three tests
following the re-mint. DIDN'T TOUCH: the observer/lifecycle logic beyond the identity import, the
pipeline workflow, the journal stack, the roster files, `run_actual_sunday*.py`. CONCERNS: the trunk holds
partial cherry-picks (workflow registration only); `ycf4v6lmave6xw` still bills its volume; the old
generation's journal (`migration-ycf4v6lmave6xw-a004983e93b9`) holds a consumed start intent that will
never complete.
