# Independent review: Frankie fleet source (2026-10-08, review role; READ-ONLY, no file but this one touched)

Scope: branch `ccr-d2f8f826-iefeah-frankie`. The brief named eb1bafe3 / 7bbdae02 / 268f70cf / e984ec33 (docs 33f777fa,
764366a5). While this review ran, slice (d) landed on the same branch (b35b6939 code + 90e46f33 docs: Greg's five decisions,
the `claim-day` CLI, `classroom_eligible`, `--allow-spot-days`, `--run` without default). Slice (e) (d78e0f95 + 5cada66f: the `day-box-role` IAM step, launch-template refusing an absent profile) landed too. The review is of the CURRENT tip
**5cada66f** (it includes everything in the brief); where a finding was fixed by (d) it is said so. Method: source read,
every call site traced into the queue / experiment / cores / handoff modules; nothing run, no AWS call, no box.

Files: `deploy/aws/box/frankie_box_fleet.py` (F), `deploy/aws/box/frankie_box_stage_handoff.py` (H),
`deploy/aws/frankie_aws_stack.py` (S), `.github/workflows/frankie_fleet.yml` (W), `deploy/aws/box/frankie_fleet_status.py`
(P), toys `tests/test_frankie_box_fleet*.py`, `tests/test_frankie_aws_stack_fleet.py`, `tests/test_frankie_fleet_status.py`.
Line numbers are those of tip 5cada66f.

Verdict up front:
- **First proof box with the day list OFF**: the box CODE is safe (the one-box E2E is unchanged with `FRANKIE_FLEET_DAY_LIST`
  unset, verified below), BUT a box launched from the fleet template/user-data cannot run a day at all (B1, B2, B3) and
  would be imaged from the main box (B5) and stopped by the idle guard (B6). A proof box must be driven the existing way
  (frankie_box_run.yml stage + SSM start with the full dispatch set) until B1-B3, B5, B6 are fixed. The user-data path
  turns fleet mode ON unconditionally, so "day list OFF" is not even reachable from the template as built.
- **Fleet with the day list ON**: NO. B1-B7 must change first; S2, S4 and S14 before a 30-day run.

---------------------------------------------------------------------------------------------------------------------------

## BLOCKING

### B1. The fleet user-data cannot start a day: the orchestrator is called with a fraction of its inputs
S:163-170 (`FLEET_USER_DATA_TMPL`, the per-day loop). The user-data runs
`CODE_ROOT=.. MARKETS_SHA=.. RUN=.. DAYS=$D DAY_CPUS=.. DETACH=on frankie_box_experiment.sh ACTION=start` and nothing else.
The one-box E2E start (E2E doc L48, L180; frankie_box_run.yml L440/L639) carried PLAN or DAY_CLASS, CLASSROOM_ARM, BRAIN,
EXTERNAL_HISTORY_RUN, the presign (`MAP_URL`), DAY_CPUS and the FRANKIE_* run settings.
Scenario: box boots -> `load_plan` (frankie_box_experiment.py:346-400): `klass = a.day_class or doc.get('class')` is None
-> the plan is REFUSED ("the run class must be one of ..."); even with a class, `fetch` is refused without MAP_URL
(experiment.py:1550 "MAP_URL not set: dispatch with presign=...") and a fleet box has no sealed ingest, so the day stops
before ROOT. The `|| echo "frankie: day $D start returned $?"` (S:169) swallows the exit: the box sits RUNNING at $4.23/h
with no day and no receipt anyone reads. By design "the box's role reads nothing in S3" (run.yml L35): a self-driving
box has no lawful route to its partitions at all.
Minimal fix: either (a) drive fleet boxes the existing way (frankie_box_run.yml `ACTION=stage` then `ACTION=start` per
instance id with the full variable set and the presign; the user-data then only stages and exports fleet mode), which the
status file already names as decision-1's alternative, or (b) put the whole dispatch set on the box (a committed plan JSON
path + DAY_CLASS + CLASSROOM_ARM + BRAIN + EXTERNAL_HISTORY_RUN as tags or one SSM parameter per run) AND give the box a
lawful partition route (role-based read of `frankie/ingest/*`, which the fetch step does not use today). Either way the
start's exit code must stop the user-data loudly (no `|| echo`).

### B2. The second day of every box never starts
S:164-169. Two separate `ACTION=start DETACH=on` calls on the SAME RUN. frankie_box_experiment.sh:144-147 refuses a second
orchestrator while one is alive ("not started twice", exit 3); the orchestrator (`Run.start`, experiment.py:4982) lives for
the whole run. Scenario: day 1 starts; day 2's start exits 3; `|| echo` swallows it; the box runs ONE day; the day list
shows day 2 forever at '-'; nothing reports it. Minimal fix: one start with `DAYS="$D1,$D2"` (and `PARALLEL_DAYS=2` if the
two ROOTs are to run side by side at 32 each), and the exit code honoured.

### B3. The per-day claim is a no-op on a real box (the "hard guarantee" never runs)
S:166-167. (d) added the `claim-day` subcommand (F:709-712, F:733-736), but the user-data runs it with `python3 -I -S -B`: `-S`
drops site-packages, so `import boto3` / `from botocore.exceptions import ClientError` (F:269, F:287) raise ImportError
(boto3 1.42.23 lives in `/opt/frankie-box/venv`, frankie_box_worker_setup.sh:50). And `|| echo "already claimed; skipping"`
does not skip: there is no `continue`, so a LOST claim (exit 1) and an ERROR (traceback) both still start the day.
Scenario: two boxes tagged the same day (an operator typo in --days or a second fleet-launch) -> both "claim" (both fail
to import boto3) -> both run the day -> two sets of ledgers for one day on two boxes. Minimal fix:
`/opt/frankie-box/venv/bin/python -B` for every fleet call in user-data; split exit codes (1 = lost -> `continue`,
>= 2 = error -> stop the user-data loudly); make `main()` return 2 when fleet mode is OFF for `claim-day` (today F:725
prints "OFF" and returns 0, which the user-data would read as a win).

### B4. Two days per box deadlock the box while it holds the GLOBAL lease
H:426-447 (gate), frankie_box_cores.py:426-471 (classroom-day defaults to ALL = grow to 64, "grow WAITS ... visibly"),
cores.py:746-751 (`usage()`: a retained booking holds its CPUs), experiment.py:2702-2715 (a waiting grow returns
'waiting'), queue request_save (2205): a saved day RETAINS its booking.
Scenario: box with days A and B at DAY_CPUS=32 each. A finishes ROOT+teacher first, gate -> proceed (A holds the fleet's one
lease). A's classroom plans ALL (64) -> grow needs B's 32 -> B is in ROOT -> the lease is held for B's whole ROOT (hours)
while nothing else in the fleet can enter a classroom. Then B reaches the gate -> waiting -> SAVED with its 32 RETAINED ->
A's grow can never complete (retained = taken) -> A's classroom stays 'waiting', the lease stays held, every other box's
WAIT unit polls forever: the fleet is dead. The same holds with B saved first. Minimal fix (a decision for Greg, the
parent must pick one): (1) in fleet mode the user-data sets `FRANKIE_CLASSROOM_CPUS=held` for a two-day box (the classroom
runs on the day's 32; the box's other day keeps running), or (2) one day at a time per box (DAYS sequential,
PARALLEL_DAYS=1: the classroom gets all 64 but ROOT is not 2 x 32 in parallel), or (3) the gate's `fleet_waiting` save
releases B's booking (and the WAIT unit resumes with REBOOK=on) so A can grow; (3) changes the save contract and needs the
queue owner. Whichever: the gate must not take the lease until the box can give the classroom its CPUs (take the lease
AFTER the grow succeeds, or make the WAIT unit's acquire conditional on the free-CPU check).

### B5. The golden AMI defaults to the MAIN box: every fleet box boots with a2's queue, ledger and 2 TB of data
S:932 (`--source-instance-id` default `BOX` = i-035994afa8bdf66a5), step_golden_ami S:677-704. The main box's root volume
holds `/opt/frankie-box/work/frankie-queue/root.json` (the a2 entry SAVED with an owner binding), `cpu-bookings/` (the
retained booking CPUs 0-31, drop-in: "booking retained"), `work/experiment/e2e-20231018-a2/` and the day's ~1.4 TB.
Scenario: a fleet box boots from that image -> the ledger says 0-31 are retained by e2e-20231018-a2/20231018 -> the first
new day books 32-63, the second day (if B2 is fixed) waits for CPUs forever, any classroom grow to 64 waits forever;
every box's queue shows a foreign saved day "its owner's, ACTION=resume"; 15 copies of a2's data. The step's cost line
("a lean ~100 GB root") describes an image that does not exist. Minimal fix: golden-ami REFUSES a source whose root
volume exceeds a lean bound or whose `/opt/frankie-box/work/frankie-queue` / `cpu-bookings` hold entries (a read through
SSM, or simply a size check on the root volume from describe_volumes), and the user-data wipes box-local run state
(`work/frankie-queue`, `cpu-bookings`, `work/experiment`, `logs`) before the first start; image a CLEAN staged box.

### B6. The idle guard stops every fleet box within six hours; a stopped fleet box never resumes
S:499-500 (template tags `KeepRunning=false`, `Name=frankie-day-box` / fleet-launch `Name=frankie-day-...`),
deploy/aws/idle_instance_guard.py:72-97 (`Name` starting `frankie-` is a candidate; "any other frankie-* box is not
protected by a lease"), cron `17 */6 * * *` (frankie_box_idle_guard.yml:9), experiment.py:829-855 (`keep_running` needs
ec2:CreateTags on self; the Ssm role has it for the MAIN box only, per the drop-in's audit). Scenario: fleet box launches
13:00, ROOT runs; 13:17 the guard: running, KeepRunning != true (the run's keep_running(true) failed on AccessDenied and
was recorded, never raised), no fresh lane lease -> StopInstances. The box is STOPPED mid-ROOT (data kept, terminate-on-
shutdown does not apply to an API stop) and user-data runs only at first boot, so a start never re-runs its days: the
day list shows the day at 'root' forever. Minimal fix: the frankie-day-box role (CreateTags on Project=frankie) BEFORE any
launch (already proposed), the template stamps `KeepRunning=true` at launch (the run clears it at its end as today), and
the guard leaves `Role=day-box` instances alone while their day list entry is not done.

### B7. Real-store fairness differs from the toy: a dead earliest waiter stalls the whole fleet, with no operator tool
F:298-306 (`S3Store.head` returns `mtime=LastModified`, a datetime) vs F:476 (`age = ... if isinstance(head.get('mtime'),
(int, float)) else 0.0`). On the REAL store age is always 0.0, so every non-earliest waiter yields unconditionally; the
"a stale earlier waiter never deadlocks the line" clause (F:472-480, docstring) holds only in the file-backed fake (float
mtime). Scenario: box 3 writes its waiting marker then dies (reclaimed, crashed, its WAIT unit killed); the lease frees;
boxes 4-15 each read `next_in_line` = box 3, yield, poll, yield ... forever. `takeover-lease` does not drop a waiting
marker and there is no `drop-waiting` CLI; `release_classroom_lease` deletes only the caller's own marker. Minimal fix:
`S3Store.head` returns `mtime=LastModified.timestamp()`; the WAIT unit re-PUTs its own waiting marker on every poll
(same body, `heartbeat_epoch` refreshed) so "live" means polling and `fair_wait` measures silence, not age since creation
(this also fixes S1); an operator CLI `drop-waiting --run --day --by --force` that records an audit object.

---------------------------------------------------------------------------------------------------------------------------

## SHOULD FIX

### S1. Even on a correct-epoch store, ROOT-finish order degrades to first-poller-wins after 300 s
F:472-480. `fair_wait` (300 s) is measured from the marker's CREATION; a waiter that has waited through one classroom (> 5
min) is "stale" to everyone else, so when the lease frees the first poller wins, not the first finisher. The contract is
"first box pair to finish is first in line". Fix: as B7 (heartbeat the marker; yield while the earlier waiter's heartbeat
is younger than N x poll). Two boxes in the same second: `round(epoch, 3)` then `day` string (F:441) is deterministic;
fine. Note the epoch is the box's own clock across 15 boxes (NTP, fine) but the S3 LastModified would be one clock (NIT).

### S2. The lease is not released on every exit path, and a failed resume strands it
- H:349-356: the release runs only when `record.status in ('done','reused')`; a classroom that FAILS (status failed)
  returns `nothing_to_hand_off` at H:347 BEFORE the release -> the holder (alive, knowing it failed) keeps the lease; the
  fleet waits for an operator takeover. Fix: release on a failed classroom record too (the holder's own decision), named on
  the receipt; a crash/kill stays operator-only as the contract says.
- F:656-660 `fleet_resume` failure ("the day stays saved, an operator resumes by hand") leaves the lease HELD by this box
  with no classroom running. Fix: release the lease on resume/kick failure (holder == this box), say so in the receipt.
- F:665-688 `wait_action`: `acquire_classroom_lease` and `set_day_stage_state` are not wrapped; one S3 blip after hours of
  polling kills the unit (or, worse, after the acquire and before the resume: lease held, day saved, nobody polling). Fix:
  try/except per poll; release-if-held on an exception after acquire.
- F:610-615 `start_wait_unit` returns `already_started` on the create-only marker even when the unit is dead (box reboot,
  OOM). Fix: `systemctl is-active` the recorded unit (or check the pid) before refusing to start another.
- SystemExit 75 / save: handled (the gate stage saves BEFORE acquiring nothing; a save during the classroom keeps the lease,
  which is right: the resumed classroom continues as holder). Double-claim WAIT unit vs hand resume: `acquire` is idempotent
  for the holder and `resume_owner` (queue:2314) refuses a non-saved day, so the second resume fails loudly; fine.

### S3. Non-arm days take the global classroom lease for nothing, and never become "done"
H:426 gates on `stage in fleet.gate_stages()` with no arm check; queue:1446 / 1525-1535: a non-arm day runs data/search/
accumulated_lessons and `_close` with NO `jev` boundary (jev is 'skipped', queue:1562-1566). Scenario: a non-arm day
reaches the teacher gate, acquires the lease, holds it through its whole data stage until the 'data' safety-net release
(H:350) -> every arm day in the fleet waits on a search; and its `done_utc` is never set (FLEET_DONE_STAGES = ('jev',)) so
the probe shows it unfinished forever. Fix: gate only when `e.get('classroom_arm')`; record the non-arm tail
(`accumulated_lessons` / `survivors`) or `_close` as done; FLEET_DONE_STAGES per arm.

### S4. Lost updates on the shared day list (15 writers, unconditional read-modify-write)
F:364-382 `record_stage_progress`, F:385-397 `set_day_stage_state`: get -> mutate -> put on one object from every box at
every boundary. Scenario: box 2 records `teacher done` while box 9 records `classroom lease_held`; the later put wins and
one of them is gone; the probe shows a stale stage, or a day's `done_utc` vanishes and the operator re-runs it. Fix:
per-day, per-stage create-only objects (`days/<run>/<day>/<stage>.json`) folded by the probe; or If-Match on the ETag with
retry. (Advisory in name, but the probe is the operator's only fleet view.)

### S5. The day list cannot name boxes before launch, claim_day never records the box, and box-less days are DROPPED
F:351-361 `seed_day_list` needs `box` ids that exist only after RunInstances; S:802 discards the RunInstances response
(no InstanceId on the receipt); F:401-415 `claim_day` writes the claim object but never sets `entry['box']` on the list;
P:85 `if box and box not in seen` skips every day whose box is None -> those days do not appear in the status output
at all ("nothing dropped"). Fix: fleet-launch --apply records each InstanceId + its two days on the receipt and seeds /
updates the list; `claim_day` sets the entry's box; the probe lists unassigned days under an explicit row.

### S6. fleet-launch: silent day drop, under-counted usage, no partial-launch record
- S:714-718 `_day_pairs(days, count)[:count]`: 30 days with --count 10 launches 20 days and says nothing about the other 10.
  Fix: refuse `len(days) > 2 * count` (or list the unassigned days on the receipt and in the plan output).
- S:758-768: usage counts only state `running` (AWS counts `pending` too) and every family (G/P instances draw on other
  quotas; over-conservative, safe) ; `need = count * 64` ignores `--instance-type` (S:770). Fix: states pending+running,
  Standard families by type prefix, vCPUs from the instance type.
- S:786-802 + S:947-963: under `--apply` the first RunInstances error (VcpuLimitExceeded between the quota read and the
  loop, InsufficientInstanceCapacity) raises out of the step; `run()` writes the receipt only after the step returns, so
  the boxes already launched are recorded NOWHERE. Fix: per-box try/except, record launched ids and the failure, return
  the receipt with status `partial`.
- `$Latest` template version (S:794) is not pinned on the receipt (see S8).

### S7. Terminate-on-shutdown + DeleteOnTermination root = one `shutdown` away from losing a day
S:493-509. No box script calls shutdown/poweroff (grepped), so a day that fails early does NOT self-terminate: its data
stays, the box runs idle at $4.23/h until stop-all (cost, not loss). The hazard is the reverse: an operator `sudo
shutdown` over SSM, a kernel panic reboot policy or any future "done -> poweroff" deletes the root volume with the
un-archived day (the Glacier second copy is optional and runs AFTER the clean). Fix: `InstanceInitiatedShutdownBehavior=
stop`; terminate by API only after the archive receipt; or `DeleteOnTermination=False` on the root.

### S8. The day-list location is baked into the template, the run is stamped per box, and `$Latest` ties them loosely
S:135 (`FRANKIE_FLEET_DAY_LIST="{day_list}"` filled at template creation from `--run`), S:789-794 (per-box `Run` tag,
`Version: '$Latest'`). Scenario: template created for run X; later `fleet-launch --run Y` from `$Latest` -> boxes run Y's
days (RUN tag) under X's day list and X's lease prefix: two fleets serialised on one lease, Y's days written to X's list
(or absent from it). Fix: carry the day-list location as an instance tag (like Run/Commit) the user-data reads; fleet-launch
verifies the template version's user-data matches `--run` and pins the version number on the receipt.

### S9. The GitHub token is persisted in `.git/config` on every fleet box
S:143-146 `git clone "https://x-access-token:$GH@github.com/..."` stores the token as the origin URL; a golden AMI taken
from such a box ships it. Fix: `git -c http.extraheader="AUTHORIZATION: basic <b64>"` (or GIT_ASKPASS) for clone/fetch, or
`git remote set-url origin https://github.com/<repo>` right after the clone; never echo it (the log is `exec >>` without
`set -x`, good).

### S10. The WAIT unit dumps the ENTIRE environment into systemd-run -E
F:619-625: `env = dict(os.environ, ...)` then `-E k=v` for every variable, no allowlist, no newline filter, unlike
`start_clean_unit` (H:311-319) and `_run_settings_env` (queue:521-545). A value with a newline breaks the unit creation
(falls back to a new session, silently); anything secret-shaped in the worker env lands in `systemctl show`. Fix: the same
allowlist as the clean unit plus `FRANKIE_FLEET_*` and `FRANKIE_QUEUE_*`.

### S11. IAM: the key set is right for the default prefix, wrong for any other, and an AccessDenied is a silent WAIT
Keys the module writes (all under `<prefix>` = `FRANKIE_FLEET_DAY_LIST`, default `fleet/<run>`):
`day-list.json` (Put create-only, Get, Put RMW); `claims/<run>/<day>/<stage>.json` (Put, Get);
`waiting/<run>/<day>.json` (Put, Get, Delete; List on `waiting/`); `classroom.lease.json` (Put, Get, Delete, Head);
`classroom.lease.takeover-<epoch>.json` (Put). With the default prefix every key is under `fleet/*` on the granite bucket:
the proposed grant (ListBucket + Get/Put/DeleteObject on `fleet/*`) covers it; HeadObject needs GetObject (granted).
BUT `location()` (F:107-123) accepts any prefix or another bucket, and `_fleet_day_list_location` (S:185-194) mirrors it:
`--fleet-day-list runs/x` puts every key outside the grant -> AccessDenied -> `classroom_gate` (F:577-580) treats it as
WAIT and the WAIT unit retries forever. Fix: the launcher refuses a location not under `fleet/` on the granite bucket
unless `--allow-any-prefix` names the widened role; the gate's receipt and log name the S3 error code and key; the status
probe shows "store error" instead of "free".

### S12. No heartbeat is ever sent during the classroom
F:492-502 `heartbeat_classroom_lease` has no caller. The lease's heartbeat is its acquire time, so the operator (the only
one allowed to take over) cannot tell a three-hour classroom from a dead holder. Fix: a tiny systemd timer unit started on
`proceed` (or a hook in the classroom's progress loop) that heartbeats every poll interval while the day holds the lease.

### S13. IMDS tag reads with no retry, no `-f`, and a fatal user-data leaves a silent idle box
S:125-130: `curl -s` without `-f` returns the 404 body as the value (tags can lag IMDS by seconds after launch); the hex
check then exits 2. S:111 `set -euo pipefail` ends the script; the instance stays running, untagged, unreported. Fix: retry
the tag reads for ~60 s with `-f`; on a fatal user-data error write a `fleet-boot-failed.json` where the probe looks and
`shutdown -h` (with S7's `stop` behaviour) so the box costs EBS only.

### S14. `FRANKIE_FLEET_WAIT_SECONDS` = 86400 strands the tail of a 30-day fleet
F:69, F:684-686: a WAIT unit gives up after 24 h (exit 2, "the day stays saved for an operator"); with `fleet-wait.started`
create-only (F:610) no second unit starts. 30 serial classrooms at 2-3 h each is 60-90 h, so the last boxes time out while
still lawfully in line. Fix: unbounded while heartbeating (B7), or a bound in days with a re-arm on re-entry.

---------------------------------------------------------------------------------------------------------------------------

## NIT

- N1. `record_root_finished` (F:418) is written at the TEACHER gate: the queue is ordered by teacher-finish time, not ROOT
  finish; say so in the name/receipt (decision 3 puts the gate there, so the order is honest, the name is not).
- N2. After an operator takeover (F:525-541) the prior holder's classroom keeps running: two classrooms until it ends; put
  that on the audit object and the CLI help.
- N3. W:150-172 stop-all: ids named in `instances` but not found are silently ignored (print them); `tag:Project` is
  case-sensitive ('frankie' here vs 'Frankie' in the previous template).
- N4. S:143 the first clone is a full-history clone (slow on this repo); `git fetch --depth 1 origin <sha>` works on
  GitHub (reachable SHA) - fine; `aws` CLI on the AMI is assumed, unverified.
- N5. The non-fleet `launch-template` step now needs `--run`/`--fleet-day-list` (S:525-529): a full-stack `--apply` stops
  there with needs_input - loud, acceptable; note it in FRANKIE_AWS_STACK_README.md.
- N6. W:96 pip pins (boto3 1.42.23 / botocore 1.42.97) match frankie_box_run.yml:253 and the box venv; good.
- N7. F:671-672 `__doc__.split('\n', 1)[0]` is fine; `status`/`queue` CLI print the whole day list (30 entries) - fine.
- N8. P:60-68: a day whose classroom state is `waiting`/`ineligible` renders as its current stage only; show the gate
  state too so an ineligible (Spot) day is visible in the one-line view.

---------------------------------------------------------------------------------------------------------------------------

## The seven questions, answered

1. Claim / lease exclusivity. On the real store `put_object(IfNoneMatch='*')` (F:268-279) is the S3 conditional write;
   412 -> `PreconditionFailed`, and the 409 `ConditionalRequestConflict` race code is handled; the box venv's boto3 1.42.23
   supports the parameter. Exclusivity holds. A crashed holder is never auto-taken (only `takeover-lease --force`, audited).
   Release only by the holder (F:505-515). Queue order: ROOT(teacher)-finish epoch then day (deterministic tie). BUT the
   fairness/liveness logic diverges between fake and real (B7), the order degrades after 300 s (S1), and on the box the
   claim never executes (B3).
2. Handoff gate. `fleet_waiting` saves the day (request_own_save) and the caller's check_save exits 75; the WAIT unit's
   resume + kick re-enter the boundary, the receipt is moved aside and the gate re-runs idempotently -> `fleet_proceed`.
   No double-claim (acquire is idempotent for the holder; a second resume is refused by the queue). Release is NOT on every
   exit path (S2). One-box E2E with the list unset: `_fleet()` (H:141-149) only imports the module; every fleet branch is
   under `fleet is not None`; the two touched conditions (`('validated','fleet_proceed')`, the `fleet_waiting`/
   `fleet_ineligible` move-aside) need statuses only fleet mode writes; `request_own_save`, the clean and the trigger are
   untouched; the toy `TestFleetOff` confirms. Byte-for-byte on the box path: yes. The stack's non-fleet `launch-template`
   step changed its template content and defaults (never applied before; N5).
3. Stage names. The handoff's STAGES keys match every `_boundary(...)` call in the queue (root, teacher, classroom, data,
   search, accumulated_lessons, lessons, survivors, jev; class-line keep() for classroom/data/search/lessons/...).
   'jev' is reached ONLY for classroom-arm days (queue:1571); non-arm days never pass a 'jev' boundary (S3). 'voice' is
   recorded 'waiting' by design (experiment.sh header); not a mismatch.
4. fleet-launch quota. Reads the LIVE quota (L-1216C47A / L-34B43A08 with --spot) minus `running` usage split by
   `InstanceLifecycle` (S:758-768). `pending` is not counted; all families are; `need` ignores the type (S6). The `--spot`
   default refusal and `--allow-spot-days` are built in (d) (S:733-740) and the toys cover them.
5. User-data. Full-hash pin + rev-parse check + staging receipt are built in (d) (S:149-160). DAY_CPUS is explicit. BUT
   the orchestrator inputs are not (B1), the second day never starts (B2), the claim never runs (B3), the token is stored
   on disk (S9), a failed boot is silent (S13). Terminate-on-shutdown: a day that fails early does not terminate the box
   (no shutdown path exists), so nothing is lost by that route; the risk is the opposite one (S7).
6. Workflow. Confirm compare is exact (`[ "$CONFIRM" != "GREG_GO_AWS_STACK" ]`, W:118). stop-all excludes the two main
   boxes unless named, never terminates; status is read-only (the probe only describes/gets). Concurrency group
   `frankie-fleet`, cancel-in-progress false. No secret is echoed (the secrets step prints a boolean; user-data fetches the
   token at boot). `run` is required since (d).
7. IAM. The key patterns (S11) all fall under `fleet/*` for the default prefix; any other `--fleet-day-list` escapes the
   grant and fails closed as a silent WAIT (S11). The fleet box also needs CreateTags on itself (B6) and, if it is to run a
   day at all, a route to its partitions (B1).
   Slice (e) (`day_box_role_policy`, S:573-612; `step_day_box_role` S:619-676): the inline policy grants ListBucket on the
   granite bucket and Get/Put/DeleteObject on `fleet/*` (every pattern above), CreateTags on Project=frankie instances
   (B6's tag), DescribeInstances, Bedrock, the four SSM parameters and the archive bucket; never widens an existing
   inline policy; the launch-template step (S:530-545) refuses an absent profile on NoSuchEntity. Two notes: any OTHER
   error on `iam:GetInstanceProfile` is 'unverified, not fatal' (S:541-545), so a runner key without that permission can
   still create a template naming an absent profile (NIT); and the policy's `fleet/*` grant is exactly why S11's
   operator-chosen prefix must be refused by the launcher.

## RUNTIME-UNVERIFIED by this review too
Everything above is traced from source. Not exercised: S3 conditional-write behaviour on the bucket, IMDS tag timing,
systemd-run on the fleet AMI, the queue's re-admission latency after the WAIT unit's kick (if the ROOT line worker is busy
with the box's other day, the lease is held idle until the handover; B4 covers the CPU side of the same hole).
