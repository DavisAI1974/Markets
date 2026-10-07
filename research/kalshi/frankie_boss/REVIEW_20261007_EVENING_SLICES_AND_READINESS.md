# Independent review: the evening slices and day-1 readiness (ccode_review, 2026-10-07)

Reviewer: ccode_review. Greg asked for this role to be resumed ("respawn and finish"), and the parent relayed the
request. This review is read-only. It fixes nothing; the owners carry the fixes. No git write commands were used.
Account work was limited to Describe, Get, List and Simulate calls. Nothing was started, stopped, tagged or written.

What was reviewed: the committed state of `ccr-d2f8f826-iefeah-frankie` at `c8c8fb0`, read through `git show` from a
scratch extract. The working tree was not used. Commits covered: 9a2cf53, eff34d5, eca308a, 7211b0d and 06cb302, plus
the Step 8 side the merge brought in (`f5d4d7e...origin/ccode/teacher-tasks-20261006b-step8-corrections`, mainly
9d4291e; fbb4bcb is the account record).

Checks: AST parse without project imports passed on all 28 changed `.py` files. `git diff --check f5d4d7e c8c8fb0` is
clean. `bash -n` passed on all 8 changed `.sh` files. No tests were run and nothing was executed.

Status: SOURCE-BUILT / RUNTIME-UNVERIFIED. This review is not an E2E verdict. A fresh review of the fixes is required
before integration.

## Verdict: BLOCKED for integration

Five items block integration: B1-B3 (Jev, KeepRunning and the idle guard), B4 (the all-99 overclaims) and B5 (the
search `not_run` wait). The account side has two further day-1 blockers, R1 and R2. Everything else is approved, or
approved with non-blocking findings, as listed below.

## Blocking findings, most severe first

**B1. Jev can never run: the caller and the helper disagree on the runtime contract.**
- Where: `deploy/aws/box/frankie_box_experiment.py` Run.jev (about lines 2755-2800, from 9d4291e) and
  `deploy/aws/box/frankie_box_jev_cpu.py` runtime_check and `_run` (from 06cb302).
- Defect: Run.jev puts the Granite meeting config into `request['runtime']`. That file is
  `knowledge/GRANITE_MEETING_RUNTIME_V1.json`, schema `FRANKIE_GRANITE_MEETING_RUNTIME_V1`. Run.jev also records any
  `JEV_CPU_RUNTIME_V1` file (plan `jev_runtime` or `<run>/jev-runtime.json`) as "superseded and NOT used".
- The helper, `runtime_check`, requires `schema == 'JEV_CPU_RUNTIME_V1'`, `engine == 'llama.cpp-cpu'`, every
  `PROPOSED_FIELDS` row, and Greg's `approved` block.
- Failure path: every Jev child fails with "Jev runtime refused: ... not legacy Pod/model labels; ... unset: cpus ...".
  This holds even after Greg approves the proposed rows, because the approved file never reaches the request. Jev never
  produces claims, so lessons and the exchange carry no Jev evidence on any day.
- Minimal fix (two owners): Run.jev must pin the `JEV_CPU_RUNTIME_V1` file (plan `jev_runtime` or
  `<run>/jev-runtime.json`) as `request['runtime']`. The shared runtime result stays in `request['shared_runtime']`,
  which the helper already cross-checks against `local_runtime`. If no approved file exists, Run.jev should record
  `waiting`, with the helper's `--propose` output named as what Greg must approve.

**B2. Jev approval gate: it cannot be bypassed by the code, but it can be self-attested.**
- Where: `frankie_box_jev_cpu.py` runtime_check and `main --propose` (06cb302).
- Defect: the gate only checks that `approved.by` contains the string "Greg" and that `approval_sha256` equals a hash
  of the file's own values. `--propose` prints `approved_example` with the exact hash to paste. Any writer of the
  runtime file (an agent, a script) can therefore produce a passing approval. Nothing binds it to Greg.
- Failure path: an agent copies `approved_example` into `jev-runtime.json` and Jev runs on unapproved budgets.
- Minimal fix:
  - Keep the approval outside the runtime file, in a committed record such as `knowledge/JEV_CPU_RUNTIME_APPROVAL.json`
    landed by the parent on Greg's word. The request should pin that record's sha256 and the plan should save it.
  - Stop printing a ready-to-paste `approved_example`.

**B3. KeepRunning and the idle guard can stop a box that is in use.**

*B3a. The main box tag is cleared while a kicked line worker is still starting.*
- Where: `frankie_box_experiment.py` main(), the `finally: keep_running(a.run, False, ...)` after `run.start()`
  (about line 3999); `box_in_use` (about lines 596-628); `frankie_box_frankie_queue.py` kick() (lines 360-420).
- Defect: kick() releases its probe lock and starts the worker detached (systemd-run or a new session), then
  returns. start() returns, and the `finally` runs box_in_use. At that moment the new worker usually does not hold
  `<line>-worker.lock` yet, because Python start-up and imports come first. So `KeepRunning=false` is written while a
  ROOT is about to run for hours.
- The same gap exists at a line worker's end. When the root worker ends before the class line has been kicked,
  box_in_use only sees locks, not pending queue entries.
- Failure path: the tag reads false and no lease has `host == 'main'` (for example the Linux lane controller is
  hosted on the runner, or has already finished). The next guard run stops the main box mid-ROOT.
- Minimal fix: box_in_use should also count unfinished queue entries of any run, and a kick in the last N minutes.
  Alternatively, kick should wait until the worker holds its lock before returning.

*B3b. The idle guard only protects the main box for leases hosted on main.*
- Where: `deploy/aws/idle_instance_guard.py` protects() (lines 85-91).
- Defect: a lease protects the main box only when `lease['host'] == 'main'`. But every controller, including a
  runner-hosted one, calls `box('queue'|'claim'|'export'|'release'|'coordinate'|'prepare', MAIN)` over SSM
  (`pod_root/controller.py` lines 516, 821, 857, 925, 987, 1010). The runner route is still listed
  (`frankie_box_cpu_controller.sh` lines 2-3).
- Failure path: a runner-hosted controller holds a fresh lease and the main box tag is false. The guard stops the main
  box, and the controller's next claim or export over SSM fails mid-day.
- Minimal fix: any fresh or unreadable lease protects both boxes. Also re-describe the instance (re-read its tag)
  immediately before StopInstances, to close the window between the snapshot and the stop.

*B3c. An unknown worker status is treated as idle.*
- Where: `research/kalshi/frankie_boss/pod_root/controller.py` finish() (lines 1547-1560).
- Defect: the worker tag is cleared unless `ctl.last_worker` shows a live job. When last_worker is None or older than
  the last submit (for example the lease is lost before the first status poll), the job's state is unknown, yet the
  tag is cleared.
- Failure path: the job keeps running on the worker, the tag is false and the lease is stale. The guard stops the
  worker mid-job. This breaks the 8A rule "uncertain resumes retain unknown".
- Minimal fix: when there is no worker status newer than the last submit, leave the tag true and record "unknown".

*B3d. The tagging cannot work under the current role policy.* See R1. On the box, CreateTags is denied, so
`keep_running(True)` is recorded as failed and the tag never becomes true. The run then depends entirely on the lease
rule, which B3a and B3b show is insufficient.

Note on the schedule: `.github/workflows/frankie_box_idle_guard.yml` is not on the default branch
(`claude/kalshi-s79-kickoff-ij8t9o`), so its cron does not fire today. Merging it there turns on automatic
StopInstances every six hours, and that needs Greg's explicit go. The identity behind the runner secrets was not
checked (UNVERIFIED).

**B4. The adviser's all-99 rows assert arrivals that did not happen.**
- Where: `deploy/aws/box/frankie_box_adviser_market.py` ROUTES and all_99_coverage (06cb302, about lines 440-560 and
  710-720); inherited by `clm_sidecar/sit_in.py all_99_for_jev`.
- Defect 1: a `('consumer', 'brain')` or `('consumer', 'knowledge')` route becomes `arrived_at_consumer` whenever the
  piece's consumer value is truthy. For Jev, the "brain" is his own peer knowledge. For the meeting, "knowledge" is
  the knowledge_index. As a result:
  - `authoritative_s135_construction`, `complete_s105_9_brain` and `doctrine_reasoning_play_index_evidence` are
    reported as arrived at Jev and the meeting;
  - all nine `frozen_learned_structure` entries are reported as arrived at the meeting.
- This contradicts the classroom list, which says "the Kalshi NG brain is not an input ... registry file not read",
  and the scientific list, which reaches them only through the historical crosswalk.
- Defect 2: `selected_same_arm_profile` (a DELIVERED binding control) is routed `retired`, with the reason "Memory A /
  arm profile retired". It is not Memory A.
- Failure path: Greg's day-1 inspection shows these registry entries reaching Jev and Granite when they did not. That
  is a false coverage statement on his top priority, the 99 layers combined for Frankie.
- Minimal fix: route these entries `not_read_by_this_piece`, with the analogue consumer named, as the classroom does.
  Route `selected_same_arm_profile` as a control.

**B5. A day with no frame spool never finishes.**
- Where: `frankie_box_experiment.py` Run.jev (about lines 2749-2753) against Run.search `not_run` (about line 3406,
  from 9d4291e).
- Defect: Run.search records `not_run` (listed) when the ROOT has no book-frame spool. Run.jev then requires
  `search.status in ('done', 'reused')` and records `waiting` permanently.
- Failure path: the day stays `unfinished` (exit 3) forever. A missing operand blocks the whole day's completion
  instead of only the equation that needs it.
- Minimal fix: when the owning search is `not_run`, Run.jev records `not_run` (listed, with the search's reason).

## Non-blocking findings (required before day 1 or recommended)

- **N1. `market_timeline.py` input_witness is not bound to a path** (SharedMarketTimeline.__init__, eff34d5).
  - The reader skips its own full hash when the caller's `{bytes, sha256}` equals the pin, but the witness carries no
    path.
  - The teacher hashes `receipt_dir/journal_file`, while the reader opens `source['container']['path']`. If those
    paths ever differ, the bytes actually read are unmeasured until the head-hash check at exhaustion (line 465).
  - The classroom callers measure the pin's own path, so they are fine.
  - Fix: include `path` in the witness and require it to equal `input_pin['path']`.
- **N2. Stage 10 is built but not wired.** `frankie_box_survivor_update.py` has no caller in Run, and `STAGES` has no
  survivors step. The one-day E2E will not run stage 10.
- **N3. The ROOT-side all-99 list has group-level proxies and a labelling slip** (all99_admission, 9d4291e).
  - All 40 native-carried calculation entries become `admitted` whenever both native ledgers are selected. That is a
    group-level proxy, not a per-layer check.
  - `a_clean_overlay` is labelled `retired` with the Memory A reason, but the crosswalk says NOT_APPLICABLE and A-clean
    is not Memory A.
- **N4. The classroom "arrived" means the substrate was present.** Several entries share one probe; for example
  `frame_fifo_queue` stands for fifo_queues, queue_age, queue_concentration and orders_ahead. The `limit` text says
  this honestly. The inspection markdown should say "carrier present", not "layer computed".
  - `decision_open` still says "bedrock off" for shared-policy plans, which now run bedrock on.
- **N5. Jev's exchange-context reuse path is wrong** (`frankie_box_jev_cpu.py`, about line 353).
  - `out.parents[2]` is `<run>/days`, but the exchange writes `<run>/exchange/<day>/`; the right parent is `[3]`.
  - Jev also runs before the exchange in stage order, so reuse never hits. The cost is efficiency only, and the miss is
    recorded.
- **N6. The Granite config text is stale.** `GRANITE_MEETING_RUNTIME_V1.json` `settled.hosts_in_order` still lists the
  GitHub runner first. Greg's 10-07 decision makes `voice_route=local` the default. Documentation only.
- **N7. Unknown status is counted as finished.** `all99_coverage.py` `_plane_disposition` treats `clock` as `arrived`
  without a test reading it. The adviser treats a missing consumer as `consumer_not_reported`, which is good.

## Per-file verdicts

| Commit | File | Verdict | Note |
|---|---|---|---|
| 9a2cf53 | frankie_box_boss_session.py | APPROVED | refusals written before raise; integrity kept distinct from missing coverage |
| 9a2cf53 | frankie_box_experiment_day_reports.py | APPROVED | school file read once and hashed once; index/successor checks; mismatch is visible |
| 9a2cf53 | frankie_principal_adapter.py | APPROVED | disposition fields only |
| eff34d5 | frankie_box_market_timeline.py | APPROVED (N1) | pin, identity and head-hash check unchanged |
| eff34d5 | frankie_box_experiment_data.py/.sh | APPROVED | pins invariant; a producer-pin mismatch raises with both values named |
| eff34d5 | frankie_box_experiment_search.py | APPROVED | FFT cache keyed by cell and partner; transforms deterministic; rows invariant |
| eff34d5 | frankie_box_experiment_teacher.py/.sh | APPROVED | equation_not_run contract matches Run.teacher |
| eff34d5 | frankie_box_workflow_inspection.py | UNVERIFIED | union hunk not reviewed in depth |
| eca308a | frankie_box_classroom_code.py | APPROVED (N4) | 99 routes; honest limit |
| eca308a | frankie_box_classroom_reader.py, experiment_classroom_v2.py/.sh | APPROVED | witness thread error re-raised after join |
| 7211b0d | frankie_box_all99_coverage.py | APPROVED (N7) | arrival at source granularity, documented |
| 7211b0d | frankie_box_survivor_update.py/.sh | APPROVED as built (N2) | no same-day promotion (DAY_KINDS survivors 50, own-day and origin evidence never counted); nothing averaged |
| 7211b0d | frankie_box_scientific_teacher.py | APPROVED | needle filter: every byte still hashed; selected rows, ordinals and line hashes invariant |
| 7211b0d | frankie_box_experiment_review.py, school_knowledge.py | UNVERIFIED | not reviewed in depth |
| 06cb302 | frankie_box_jev_cpu.py | BLOCKED | B1, B2 (N5) |
| 06cb302 | frankie_box_granite_meeting.py | APPROVED | whole picture; system prompt counted once and every round counted; over the cap the item is left open with no call and nothing trimmed |
| 06cb302 | frankie_box_adviser_market.py | BLOCKED | B4; parse-back failures raise (good) |
| 06cb302 | frankie_box_experiment_exchange.py | APPROVED | |
| 06cb302 | clm_sidecar/sit_in.py | APPROVED with B4 inherited | |
| 9d4291e | frankie_box_experiment.py | BLOCKED | B1, B3a, B5 (N3) |
| 9d4291e | frankie_box_frankie_queue.py | BLOCKED | B3a (worker-end clear) |
| 9d4291e | pod_root/controller.py | BLOCKED | B3c; the preflight's DescribeInstances is unprovisioned (R1) |
| 9d4291e | deploy/aws/idle_instance_guard.py | BLOCKED | B3b |
| 9d4291e | .github/workflows/frankie_box_idle_guard.yml | APPROVED as a file | landing it on the default branch needs Greg's go |
| 9d4291e | frankie_box_successor_dispatch.py, experiment.sh | UNVERIFIED | not reviewed in depth |
| 5f11188/9cd1e2a | granite_runner, cores, cpu_controller.sh, pod_root_loop.sh, run.yml, granite_meeting.yml | UNVERIFIED | not re-reviewed in this pass; exit codes spot-checked (failed means unfinished, which means exit 3) |

## The specific checks

- **(a) Efficiency changes: pass.**
  - input_witness: N1.
  - Parallel pinning: same bytes and sha256; a producer pin is checked.
  - FFT cache: deterministic; per cell; memory cap of 512 MB per worker.
  - Needle filter: hashes every byte; both escaping forms of each name are used; parsing is skipped only on lines that
    cannot match.
  - Single-read reports: pass.
  - Retained-context reuse: N5, efficiency only.
  - None of these touches a pinned identity, cursor domain, event order, decoded entries, counts or head hashes.
- **(b) The all-99 claim: not every entry reaches Frankie's computation.** Every one of the 99 entries is listed with
  a reason in each piece, so nothing is silently dropped. What actually reaches what:
  - Classroom: only `derived_roll20_and_dipole_state` (through the Dipole teacher rows) enters the arithmetic. Raw and
    calculation entries reach the anchor pictures and the full reader as context.
  - Scientific stages: entries arrive at source granularity through the search's coupling rows.
  - Adviser: rows overclaim (B4).
- **(b) The four registries disagree.** They are: experiment.py ALL99_GROUPS (ROOT), all99_coverage REGISTRY
  (scientific), classroom ALL99_ROUTES and adviser ROUTES. Disagreements found:

| What | ROOT (experiment.py) | Scientific (all99_coverage) | Classroom | Adviser |
|---|---|---|---|---|
| causal_clocks role | `calculation` | `clock` | `calculation_clock` | `clock` |
| sealed role | `sealed` | `sealed_answer` | `sealed_answer` | `sealed_answer` |
| sealed disposition | `sealed` | `withheld_by_role` | `sealed` | `withheld_by_rule` |
| shadows / outputs (role names) | `shadow` / `output` | `shadow` / `output` | `disabled_shadow` / `append_only_output` | `shadow` / `output` |
| Memory A (3 entries) | `retired` | `disabled` (the shadows' word) | `retired` | `historical_not_bound` |
| a_clean (NOT_APPLICABLE) | `retired`, with the Memory A reason | `absent` (policy) | `retired` | `not_applicable` |
| selected_same_arm_profile | `knowledge` | `absent` (policy) | `control_of_orchestrator` | `retired` (wrong) |

  - Current brain runtime entries: ROOT `knowledge`; scientific `thin`/`absent` (historical); classroom
    `not_read_by_this_piece`; adviser `arrived_at_consumer` (B4).
  - Per-entry carriers also differ between the classroom and the adviser. Each pair below is classroom first, adviser
    second:

| Entry | Classroom carrier | Adviser carrier |
|---|---|---|
| order_lifecycle_fills | native.member / root.frames | root.structures `fill_disposition` |
| order_identity_transitions | root.structures | bedrock |
| contract_session_roll_state | native / at.session_id | bedrock |
| mechanics_actions_by_side_and_level | root.frames.activity | root.structures |
| aggressor_and_native_signed_flow | root.frames.activity | completed |
| derived_roll20_and_dipole_state | dipole operand | completed roll20 |
| clock_prospective_discovery_confirmation | native.lifecycle | lessons consumer |
| clock_model_evaluation / clock_lock_time | native / stamped | host_clock |

  - The disposition vocabularies differ in size: 9, 7, 14 and about 15 words.
  - Registry sourcing differs too. ROOT reads the file and its pin. Scientific embeds the list and compares. Classroom
    embeds the bytes and sha and reads the file. Adviser reads the pin and falls back to a partial 68-name list.
  - All four agree on the 99 identities and on the 18 group IDs.
- **(c) Idle guard and KeepRunning: fail.** They can stop a box that is in use. B3a-B3c are concrete paths, and R1
  disables the tagging altogether.
- **(d) Jev gate: fails as a contract (B1) and is self-attestable (B2).** The Granite per-call cap is good: it refuses
  visibly with an open item and no call, and nothing is trimmed.
- **(e) Stage 10: pass.**
  - No same-day promotion: the boundary day's own classroom is excluded through DAY_KINDS, and the claim's own day
    and origin day are never counted.
  - No averaging: days are named per mark and the counts are counts.
  - Not wired (N2).

## JOB 2: day-1 readiness (read-only account, 2026-10-07)

### S3 (us-east-2 `bento-568968024170-us-east-2-an`)

Days with a complete ingestion receipt and journal in S3 AND a day file: **20221011, 20221012, 20221018, 20221019,
20231003, 20231004, 20231010, 20231011, 20231017, 20231018** (10 days).
- Each has `ingestion-receipt.json` (`BOSS_BLOCK_INGESTION_RECEIPT_V1`, writer compact) and `completion.json`
  (`BOSS_SOURCE_CONFORMANCE_V1`, RESULT_BEARING).
- `journal_count` equals `2 x record_count` on all ten.
- The receipt's journal_bytes equals the S3 object size on all ten.
- The S3 journal sha256 was not re-hashed (UNVERIFIED).
- Each day file is `day-external.json` plus its receipt, `FRANKIE_DAY_EXTERNAL_RECEIPT_V1`. 20221011's receipt lists 21
  missing items, which means a thinner picture, not a refusal.

Other S3 holdings:

| Days | Ingest in S3 | Day file in S3 |
|---|---|---|
| 20250930, 20251001, 20251014 | yes, as box archives (`FRANKIE_BOX_INGEST_ARCHIVE_V1`, split objects) | no |
| 20211005, 20211006, 20211012, 20211013, 20211020, 20221004, 20221005 | no | yes |

Box-local ingests for the 2021 and 20221004/05 days: UNVERIFIED. Checking them needs SSM SendCommand, which is not
read-only.

The full-book `observation` field the teacher needs was not seen in the receipts (UNVERIFIED). A journal without it
gives `equation_not_run`, which is listed.

### S3 (us-east-1 `frankie-granite42-568968024170-us-east-1`)

- `pod-root/`: `days-20260930-1/` and `pods/` only. No lease of a new run.
- `box-runs/`: 41 GitHub run prefixes. These are old presign maps and outputs.

### Lane instances

| Instance | Type / lanes | State | Profile | KeepRunning | SSM |
|---|---|---|---|---|---|
| i-035994afa8bdf66a5 (frankie-ingest32-20260917) | r7i.8xlarge, two main lanes | stopped (user-initiated 13:08:15Z) | instance-profile/Ssm | `false` (plus KeepRunningPolicy) | not registered (stopped) |
| i-0d17573dbce871520 (frankie-linux-r7i4xl) | r7i.4xlarge, one Linux lane | stopped (13:02:40Z) | instance-profile/Ssm | `false` (plus KeepRunningPolicy) | not registered (stopped) |
| i-08cee7171c0a76a04 (markets-year-pull-v2) | r6i.2xlarge, us-east-2 | stopped | Ssm | none | n/a |

fbb4bcb says the main box was left running with KeepRunning=true. It is now stopped with KeepRunning=false. Someone
changed it after the record was written; it is not in fbb4bcb.

### Role `Ssm` policy

Attached: `AmazonSSMManagedInstanceCore`, plus the inline `FrankieBoxStep8A-20261007`. The inline policy matches
fbb4bcb verbatim. IAM SimulatePrincipalPolicy results:

| Action and resource | Decision |
|---|---|
| s3 Get/Put `pod-root/*` (transfer bucket) | allowed |
| s3 Get `frankie/ingest/*` (bento) | allowed |
| ssm:SendCommand on the worker | allowed |
| **ec2:CreateTags** on either box | **implicitDeny** |
| **ec2:DescribeInstances** | **implicitDeny** |
| ssm:SendCommand on the main box | implicitDeny (not needed; the main-hosted controller runs main actions locally) |
| s3 Get `frankie/day_history/*`, `nymex/ng_fut_parent_v0/*` | implicitDeny (runner-presigned today) |
| s3 Put `clm-sidecar/*` | implicitDeny (runner-presigned today) |
| ec2:StopInstances | implicitDeny |

### Day-1 blockers on the account side

- **R1.** The policy predates 9d4291e, so it lacks two actions the code now calls:
  - `ec2:CreateTags` for KeepRunning: experiment.keep_running and controller.keep_running. Both record the failure;
    neither raises.
  - `ec2:DescribeInstances`: the controller preflight's "worker KeepRunning tag" check (controller.py lines
    1280-1284). That check will be missing, so preflight exits 2 and `frankie_box_cpu_controller.sh start` refuses.
    **The Linux lane cannot start.**
  - Minimal grant: `ec2:DescribeInstances` with Resource `*`, and `ec2:CreateTags` on the two instance ARNs with the
    condition `aws:TagKeys` limited to KeepRunning and KeepRunningReason. This is an account write, so it needs
    Greg's go.
  - The idle guard itself runs with the GitHub secrets' identity (UNVERIFIED).
- **R2.** The worker disk had 19 GB free of 116 GB (fbb4bcb, section c). One day's journal alone is 8.8-14.7 GB,
  before the ROOT spools and the native ledgers. The Linux lane's ROOT-to-finish probably does not fit. The exact need
  is UNVERIFIED; measure it, or free space, before day 1.

### Pinned install (fbb4bcb)

- Main box: `/opt/frankie-box/granite/llama-b11440/llama-server`, sha256 `b30ec35b...`, equal to the pin.
- `granite-4.2-3b-Q4_K_M.gguf`: 2,244,011,552 bytes, sha256 `e0406663...`, equal to the pin.
- `provenance.json`: `FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1`; 50 files verified; gate reasons [].
- The checkout it came from is the ingest worktree at 5f11188. The main `/opt/frankie-box/markets` is at 25b30d9.
  Day 1 must stage the reviewed integrated commit.
- None of this was re-checked on the box in this pass, since the box is stopped and SSM is a write. It is taken from
  the record.
- The meeting runtime parameters were confirmed by Greg on 2026-10-06 (config note).

### Still unsupplied

- Greg's approval of the proposed Jev rows, in a form B2 can verify.
- The B1 caller fix.
- The R1 policy grant (Greg's go).
- A worker disk decision (R2).
- Stage 10 wiring (N2).
- Choosing the ONE day from the ten S3-complete days. All three lanes need a day each only for the three-day run; the
  one-day run uses one lane and must be configured as the three-day run.
- Greg's go for the E2E.
- Greg's go before the idle-guard workflow lands on the default branch.

## Skills and account calls

Skills (Skill tool): `api-and-interface-design`, then `code-review-and-quality`. No `retrieve_skill` was needed.

Account calls, all through the `Aws` connector `run_script`. All were read-only and changed nothing:
- sts GetCallerIdentity (root of 568968024170).
- s3 ListObjectsV2 x7:
  - bento `frankie/ingest/` and `frankie/day_external/`, delimited and full;
  - transfer bucket `pod-root/`, `box-runs/` and the top level.
- s3 GetObject x24, us-east-2: 10 completion.json, 10 ingestion-receipt.json, 3 archive-manifest.json, and 1
  day-external-receipt.json.
- ec2 DescribeInstances, us-east-1 and us-east-2.
- ssm DescribeInstanceInformation, us-east-1 and us-east-2.
- iam: GetInstanceProfile Ssm, ListAttachedRolePolicies Ssm, ListRolePolicies Ssm, GetRolePolicy
  Ssm/FrankieBoxStep8A-20261007.
- iam SimulatePrincipalPolicy x12 on role Ssm.

Two script submissions were rejected by the connector's code validator before running; no API call was made by them.
