# Fleet source status - session 8 (2026-10-08, BUILD role; source only)

Both not-built pieces the parent named are built, source only, nothing run on a box, no AWS call. On branch
`ccr-d2f8f826-iefeah-frankie`. Full record (contract, line ranges, toys): the "Session 8: fleet source" section at the
end of `E2E_ONE_DAY_20231018.md`.

## What is built

### (a) The shared day list on S3 + the cross-box classroom claim
- NEW `deploy/aws/box/frankie_box_fleet.py` (682 lines): the S3 day list (30 days, assigned box, per-stage state), the
  per-day claim by conditional write (PutObject If-None-Match: *), the ONE global classroom lease (holder/day/heartbeat,
  released by the holder, operator-only forced takeover), the waiting queue ordered by ROOT-finish time, and
  `classroom_gate` + the detached WAIT unit. Inert unless `FRANKIE_FLEET_DAY_LIST` is set (the one-box E2E is unchanged).
- `deploy/aws/box/frankie_box_stage_handoff.py`: `_fleet()` guard; at the gate stage (default `teacher`) the boundary
  claims the lease -> `fleet_proceed` or `fleet_waiting` (save + WAIT unit); at the classroom (and data, as a safety net)
  boundary it releases the lease. All behind one `_fleet() is not None` check.
- Toys: `tests/test_frankie_box_fleet.py` (14), `tests/test_frankie_box_fleet_handoff.py` (4). Pass.

### (b) The fleet launch (dry-run steps in `deploy/aws/frankie_aws_stack.py`)
- `golden-ami`: CreateImage (NoReboot) of a STOPPED staged box; name carries the commit; refuses a running instance.
- `launch-template`: `frankie-day-box` -- r7i.16xlarge, IMDSv2 + InstanceMetadataTags, Ssm, detailed monitoring,
  terminate-on-shutdown, root gp3 3072 GiB / 16,000 / 1,000 encrypted with the account CMK, tags Project=frankie +
  Role/Name/Day/Commit/Run, and user-data that installs nothing, reads its two days + commit from its tags, stages the
  commit, and starts each day on the root line with DAY_CPUS explicit.
- `fleet-launch --days <list> --count N [--spot]`: RunInstances from the template, two days per box, refusing when N x 64
  exceeds the LIVE service-quota (On-Demand L-1216C47A, Spot L-34B43A08) minus running usage. Spot boxes tagged ROOT-stage.
- Toys: `tests/test_frankie_aws_stack_fleet.py` (10). Pass. Dry-run CLI exercised (receipts written, needs-input gating).
- All dry-run by default; `--apply --confirm GREG_GO_AWS_STACK` was NEVER run.

### (c) The fleet workflow + status probe
- `.github/workflows/frankie_fleet.yml` (NEW), modelled on `frankie_box_run.yml`: `plan` (dry-run fleet-launch, records
  nothing), `launch` (fleet-launch `--apply --confirm GREG_GO_AWS_STACK`, refused unless the confirm input equals that
  exact string), `status` (read-only probe), `stop-all` (refuses without confirm; STOPS never terminates every
  Project=frankie fleet box; never the main boxes `i-035994afa8bdf66a5` / `i-0d17573dbce871520` unless named in the
  `instances` input). `frankie_box_run.yml` is unchanged.
- `deploy/aws/box/frankie_fleet_status.py` (NEW): the read-only probe the `status` action runs. Joins the S3 day list +
  EC2 DescribeInstances into one line per instance; runnable locally with `--day-list <path>` (no boto3, no AWS).
- Full-day stage tracking (Greg's scope note 1): a day does NOT end at the classroom. `frankie_box_fleet` gains
  `record_stage_progress` + `FLEET_DONE_STAGES=('jev',)`; the handoff records every stage DONE on the day list as the
  day runs its full sequence (classroom -> data/search -> scientific-teacher -> voice meeting -> jev -> end), done only
  at the tail (jev). The lease still covers ONLY the classroom; the post-classroom stages run per-box on the grown 64
  lane after release.
- Toys: `tests/test_frankie_fleet_status.py` (7). Pass.

### (e) The day-box-role IAM step + launch-template defaults to frankie-day-box
APPLIED IN THE ACCOUNT 2026-10-08 15:19-15:28Z: Greg created the role `frankie-day-box` + instance profile + inline
policy `FrankieDayBox-20261008` in the IAM console; the parent verified 13/13 statements in the scripted order via the
connector. launch-template's read-only GetInstanceProfile check now resolves. Nothing more for fleet-source here.
A dry-run `day-box-role` step (never applied by this role) that creates the fleet boxes' OWN role `frankie-day-box`
(trust ec2), attaches AmazonSSMManagedInstanceCore, puts the one inline policy `FrankieDayBox-20261008` (13 statements,
exactly the drop-in's IAM-gap list), creates the instance profile and adds the role, tags both Project=frankie;
idempotent, never widens an existing inline policy, and the dry run prints the full policy JSON on the receipt.
`launch-template` now defaults `--instance-profile frankie-day-box` and refuses (read-only GetInstanceProfile) when the
profile is absent. Greg applies it with `--apply --confirm GREG_GO_AWS_STACK --steps day-box-role` or from the console.
Toys: policy builds+validates, creates-when-absent (5 writes), present-when-all-exist (0 writes), launch-template
refuses an absent profile.
Two facts confirmed by the parent (2026-10-08, verified (e) here 44/44 + the dry run printing the full policy):
- The four SSM parameter ARNs are CONFIRMED exact matches against the Ssm role's inline policy (the "best-known" caveat
  is removed; the code comment now says confirmed): .../markets/frankie/github-token, .../granite-service,
  .../runpod-serverless (us-east-2) and .../markets/DATABENTO_API_KEY (us-east-1).
- The container's dry run runs as IAM user `Claude`, which has NO IAM permissions, so `iam:GetInstanceProfile` returns
  AccessDenied here (not NoSuchEntity). That is why launch-template's profile check only REFUSES on NoSuchEntity and
  merely NOTES any other error (AccessDenied, no creds) so an offline/limited dry run still prints the plan -- kept as
  built. Greg applies `day-box-role` as root (console or a root-credentialed shell); the main box's Ssm role is never
  touched.

### (d) Greg's five decisions applied
See "Decisions - ALL RESOLVED" below: staging pins a full commit hash + writes a receipt; a Spot/ClassroomEligible=false
box is refused the classroom lease and fleet-launch refuses --spot for day boxes without --allow-spot-days; the gate
stage and the gate clean-on-save are kept as built; --run has no default and a missing run is refused. Plus the
`claim-day` CLI the user-data calls. Toys added: ineligible gate, claim-day CLI, missing-run refusal,
spot-refused-without-allow, spot-with-allow, launch-template needs-location, user-data rev-parse/receipt assertions.

## Commit hashes (on ccr-d2f8f826-iefeah-frankie; rebased onto the parent's box records; hashes are the current ones)
- `eb1bafe3` - the fleet module + its 14 toys.
- `7bbdae02` - the handoff hooks (gate + release) + 4 toys.
- `268f70cf` - the stack fleet steps (launch-template fleet spec, fleet-launch, golden-ami) + 10 toys + the atomic
  fake-store fix.
- `33f777fa` - the first docs (E2E section + this status file's first version).
- `e984ec33` - (c) the fleet workflow + status probe + full-day stage tracking + 7 toys.
- `33f777fa` / `764366a5` - the (a-c) docs.
- `b35b6939` - (d) Greg's five decisions applied + the claim-day CLI + 5 more toys.
- `90e46f33` - the (d) docs.
- `d78e0f95` - (e) the day-box-role IAM step + launch-template default/refusal + 4 toys.
- (this docs update lands in a following commit.)
Verification on every touched file: py_compile + ast.parse on .py, YAML safe_load on the workflow, bash -n on the pure
run blocks AND the rendered user-data, git diff --check clean; 44/44 toys pass (`python -m unittest
tests.test_frankie_box_fleet tests.test_frankie_box_fleet_handoff tests.test_frankie_aws_stack_fleet
tests.test_frankie_fleet_status`).

## Decisions - ALL RESOLVED (Greg, 2026-10-08, "Do what is best for science and speed"; relayed by the parent; applied in b35b6939)
1. **Staging = self-driving git, pinned to a full commit hash.** DECIDED: keep the self-driving boot-time stage, but it
   MUST pin a full 40-hex commit (a branch name or short hash is refused), verify `git rev-parse HEAD` equals it, and
   write a staging receipt (FRANKIE_FLEET_STAGE_V1: status staged, commit, tree_sha, file_count) so every box's receipt
   names the identical commit. Built in the user-data; the SSM reviewed-helper dispatch is NOT used for a self-driving box.
2. **Spot = never the classroom.** DECIDED: a ClassroomEligible=false box is REFUSED the classroom lease (the gate
   returns 'ineligible', takes no lease, starts no WAIT unit, and the handoff saves the day at the gate for an operator
   to run its classroom on an On-Demand box). fleet-launch tags every --spot box ClassroomEligible=false AND refuses
   --spot for day boxes unless --allow-spot-days is given. Spot is for stateless burst work (the digest render), not day
   boxes.
3. **Gate stage = teacher->classroom.** DECIDED: kept as built (FRANKIE_FLEET_CLASSROOM_GATE_STAGES default `teacher`).
4. **Clean-on-save at the gate.** DECIDED: kept skipped at the gate stage (a save+resume there would race the lease);
   the day's chain cleans later.
5. **Run name = no default, refused when missing.** DECIDED: --run has no default in fleet-launch (and launch-template
   refuses without --run or --fleet-day-list to form the day-list location; the workflow's run input is required;
   seed-day-list already requires --run), so no fleet reuses the one-box a2 run e2e-20231018-a2.

Two scope notes from the parent (also applied, in e984ec33):
- **Full day sequence (not just the classroom).** The lease covers ONLY the classroom; data/search -> scientific-teacher
  -> the Granite voice meeting -> jev -> end run per-box on the grown 64 lane after the lease is released. The day-list
  state + the status probe mark a day done only at jev/end (FLEET_DONE_STAGES).
- **Instance profile = the fleet boxes' OWN role `frankie-day-box` (RESOLVED by slice e, replacing the "reuse Ssm"
  residual).** The parent's read-only IAM audit (drop-in "IAM gap for fleet boxes") confirmed the main box's Ssm role
  does NOT cover the fleet/* prefix, the archive bucket, self-tagging or Bedrock, so widening Ssm is wrong. Slice (e)
  adds the dry-run `day-box-role` step that creates a NEW role `frankie-day-box` + instance profile with the one inline
  policy `FrankieDayBox-20261008` (the audit's exact statements); launch-template now defaults
  `--instance-profile frankie-day-box` and refuses when that profile is absent. Greg applies the role with
  `frankie_aws_stack.py --apply --confirm GREG_GO_AWS_STACK --steps day-box-role` (or from the IAM console); I did NOT
  create or change any IAM. No residual IAM item remains.

## RUNTIME-UNVERIFIED (everything; the container has 4 CPUs, no ledger, no S3)
The real S3Store against the bucket (412 handling, paging); classroom_gate + the WAIT unit end to end on the box; the
handoff gate skipping clean-on-save in a live Run; the fleet user-data booting (IMDS tag reads, the git stage, experiment
ACTION=start); fleet-launch RunInstances + golden AMI against the account; the quota read and the running-usage split by
market. The toys cover the pure logic and the control-plane semantics via the file-backed fake store only.

## Not touched (other roles' files)
`frankie_box_cores.py` internals, `frankie_box_cpu_watch.py` (the CPU-plan work) -- the fleet piece does not call the
resolver (the classroom grow to all-64 is already the resolver's classroom-day default; the lease only decides WHICH box
runs its classroom at a time, not the CPU set). The classroom/teacher/queue/experiment stage files are unchanged; the
fleet logic lives in the new module and the handoff only.

## Review findings resolution (REVIEW_20261008_FLEET_SOURCE.md, commit 19598860) -- slice f
Each finding was verified against the code and fixed, or answered with the traced reason. Commits on
ccr-d2f8f826-iefeah-frankie: batch1 0c1b9d6c (user-data B1/B2/B3/B5-wipe/B6/S9/S13), batch2 73293c51
(B4/B7/S1/S2/S14), batch3 cda7b0e3 (B5 golden-ami/S5/S6/S7/S8/N3), batch4 b11b541d (S3/S4/S5/S10/S11/S12/N8),
batch5 (N1/N2/N4/N5 + these docs). 64 fleet toys pass; py_compile/ast.parse/YAML/bash -n (incl. the rendered
user-data + the day driver)/git diff --check clean. Nothing run; no AWS call.

| # | finding | resolution |
|---|---------|-----------|
| B1 | user-data can't start a day (fraction of inputs, no partition route, `|| echo`) | FIXED 0c1b9d6c. User-data no longer attempts a fresh start; it PREPARES the box and installs a reboot-resume driver. Fresh day-start is driven per instance by frankie_box_run.yml (stage+start, full dispatch set + presign) -- review option (a), chosen. No `|| echo`. |
| B2 | second day's start refused (two ACTION=start) | FIXED 0c1b9d6c. No self-start in user-data; the reboot-resume driver resumes BOTH saved days. The external run.yml start uses one DAYS="D1,D2". |
| B3 | claim-day a no-op (`-S` drops boto3; no `continue`) | FIXED 0c1b9d6c. The driver runs claim-day under the venv python with an exit split (0 won / 1 lost->skip / >=2 error->stop); claim-day returns 2 when fleet mode is OFF and 2 on any error. |
| B4 | two-day box deadlocks holding the GLOBAL lease | FIXED (fleet half) 73293c51: the gate takes the lease ONLY when the box can give the classroom its CPUs (resolver waits_for==0), and the WAIT resume passes REBOOK=on. ANSWERED (queue half): the parent's full option-3 (a fleet_waiting day RELEASES its booking so the holder grows to 64) needs request_save to drop the booking on a fleet-gate save -- today it RETAINS (queue:2205). One-line queue change for CCode/the queue owner (request_save honoring a release flag). No-queue-change fallback also named: FRANKIE_CLASSROOM_CPUS=held runs the classroom on the box's own 32. |
| B5 | golden AMI defaults to the main box (foreign queue/bookings/2 TB) | FIXED cda7b0e3 (golden-ami refuses a root over --max-root-gib) + 0c1b9d6c (user-data first-boot wipe of box-local run state). |
| B6 | idle guard stops fleet boxes; a stopped box never resumes | FIXED 0c1b9d6c. Template + per-box tags stamp KeepRunning=true (the idle guard stops only KeepRunning!=true; the day-box role from slice e lets the box keep it true); user-data installs a systemd unit that re-runs the day driver on EVERY boot (reboot-resume). |
| B7 | real-store fairness (datetime mtime) stalls on a dead earliest waiter | FIXED 73293c51. S3Store.head returns a float epoch; the WAIT unit heartbeats its waiting marker; fairness measures heartbeat SILENCE, so a dead earliest waiter no longer deadlocks the line. A drop-waiting operator CLI is NOT added (the heartbeat-silence skip removes the need; takeover-lease handles a stale lease). |
| S1 | order degrades to first-poller after 300 s | FIXED 73293c51. The marker keeps root_finish_epoch for ORDER and a separate heartbeat_epoch for liveness. |
| S2 | lease not released on every exit path | FIXED 73293c51. Release at the classroom/data boundary runs BEFORE the FINISHED check (a failed classroom frees it); fleet_resume releases on a resume/kick failure; wait_action wraps each poll and releases-if-held on an exception; start_wait_unit no longer refuses on a DEAD unit. |
| S3 | non-arm days take the lease; never "done" | FIXED b11b541d. The gate fires only for e['classroom_arm']; done_utc at jev (arm) or accumulated_lessons/survivors (non-arm). |
| S4 | lost updates on the shared day list (15 writers) | FIXED b11b541d. Stage state moved to per-day progress objects (one writer per day); the day list keeps only static assignments; the probe folds them. |
| S5 | InstanceId/box not recorded; box-less days dropped | FIXED cda7b0e3 (fleet-launch records each InstanceId+days on the receipt) + b11b541d (claim_day records the box; the probe shows unassigned days in their own row). |
| S6 | silent day drop; under-counted usage; no partial record | FIXED cda7b0e3. fleet-launch refuses a day overflow (names the dropped days); counts pending+running; sizes need by --instance-type; per-box try/except records launched ids + returns 'partial'. |
| S7 | terminate-on-shutdown + DeleteOnTermination root | ANSWERED/FIXED cda7b0e3. --shutdown-behavior {terminate,stop}, default terminate (Greg's choice, cited in the quota appeal; no box script calls shutdown, so no self-terminate path); stop offered for the cautious. Greg's call on the default. |
| S8 | day-list baked in template; $Latest loose | FIXED cda7b0e3. fleet-launch pins the template version number and stamps a per-box DayList tag; the user-data reads the tag (falls back to the baked value). |
| S9 | GitHub token persisted in .git/config | FIXED 0c1b9d6c. Clone/fetch use a one-shot http.extraheader auth; `remote set-url` to a tokenless URL; the token is never in a URL or on disk. |
| S10 | WAIT unit dumps the whole env into -E | FIXED b11b541d. Detached units get an allowlist (_detached_env: FRANKIE_*/AWS_* + a few); newline values dropped. |
| S11 | any prefix escapes the IAM grant -> silent WAIT | FIXED b11b541d. The launcher refuses a location outside fleet/ on the granite bucket unless --allow-any-prefix; the probe shows a store error, not "free"; the gate records the S3 error. |
| S12 | no heartbeat during the classroom | FIXED b11b541d. classroom_gate on 'proceed' starts a detached heartbeat unit that refreshes the lease while the box holds it. |
| S13 | IMDS tag race; a fatal user-data = silent idle box | FIXED 0c1b9d6c. Tag reads retry ~60s with curl -f; a bad/absent tag writes fleet-boot-failed.json and exits 2. |
| S14 | 24h WAIT bound strands the tail of a 30-day fleet | FIXED 73293c51. Bound is 7 days with the marker heartbeated; a reboot re-arms the unit via the reboot-resume driver. |
| N1 | record_root_finished at the teacher gate (not root) | FIXED b11b541d+batch5. The marker carries basis='teacher-finish'. |
| N2 | takeover leaves the prior holder's classroom running | ANSWERED batch5. The takeover audit + CLI note warn to force only once the prior holder is confirmed dead (two classrooms otherwise). |
| N3 | stop-all silently ignores unmatched named ids | FIXED cda7b0e3. stop-all prints ids named in --instances but not running/pending. |
| N4 | full-history clone; aws CLI assumed | FIXED/NOTED 0c1b9d6c+batch5. The clone is --depth 1; the aws/git assumption is noted in the README. |
| N5 | launch-template now needs --run/--fleet-day-list | NOTED batch5 in FRANKIE_AWS_STACK_README.md (intentional, loud). |
| N6 | pip pins match | No change (already correct). |
| N7 | __doc__ split / CLI prints whole list | No change (fine). |
| N8 | probe hides the gate state | FIXED b11b541d. A waiting/ineligible day shows gate:waiting / gate:ineligible; unassigned days get their own row. |

ONE open item for the owners (not fleet-source): B4's booking-release-on-save (the queue's request_save), a one-line
change for CCode/the queue owner so the parent's full option-3 works end to end; the fleet-source half and the
no-queue-change fallback are built.
