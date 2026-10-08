# Independent RE-REVIEW, pass 2: the fixes for B1-B7 of REVIEW_20261008_FLEET_SOURCE.md (2026-10-08; READ-ONLY, this file only)

Scope: branch `ccr-d2f8f826-iefeah-frankie`, fix commits 0c1b9d6c, 73293c51, cda7b0e3, b11b541d, c914f658 (tip read:
a62862b5, which adds only a box snapshot record on top of c914f658). Inputs read: the original review (B1-B7 and their
scenarios), the findings table in FLEET_SOURCE_STATUS_SESSION8.md, the slice-(f) section of E2E_ONE_DAY_20231018.md,
then `git diff 90e46f33..c914f658` on the six fleet files, the toys `tests/test_frankie_*fleet*.py`
(run: `python -m unittest discover -s tests -p 'test_frankie_*fleet*.py'` -> 64 tests OK, 0.5 s), and the call sites
into the queue / cores / experiment modules where a fix depends on them. Nothing run on a box, no AWS call.
Line numbers are those of tip c914f658 unless a file is named at another commit.

Method per B item: the ORIGINAL scenario re-traced against the new code (CLOSED / STILL OPEN / PARTIALLY with file:line),
then what the fix introduced. Findings are written incrementally below as each item is traced.

---------------------------------------------------------------------------------------------------------------------------

## Verdict up front

- **ONE proof box, day list ON, ONE day on the box: YES** (with the role applied, a clean-box AMI, and the day driven by
  run.yml stage+start as the fix says). The one-box E2E with the list unset is byte-for-byte unchanged (verified below).
- **ONE proof box with TWO classroom-arm days: NO as built** -- the box deadlocks itself at its second gate (B4 fleet
  half alone: both days saved with 32 CPUs retained each, each classroom needing the other's 32) and the idle guard then
  stops it (NEW-2). Launchable only with `FRANKIE_CLASSROOM_CPUS=held` in the dispatch (lawful, see B4) -- which runs the
  classroom on 32, not Greg's 64 -- or with one day per box, until the queue's booking-release-on-save lands.
- **The 15-box fleet: NO.** Two NEW BLOCKING findings the fixes introduced: NEW-1 (a live but CPU-blocked head-of-line
  waiter makes every other box yield forever: a fleet-wide deadlock with the lease FREE; reproduced on the toys' own
  store) and NEW-2 (a box whose days are all waiting in line has no live worker, so the queue clears KeepRunning and the
  idle guard stops it within 6 h; after a manual start nothing re-stamps the tag, so it is stopped again).

---------------------------------------------------------------------------------------------------------------------------

## B1-B7 re-traced

### B1. User-data cannot start a day -- CLOSED (by redesign)
`FLEET_USER_DATA_TMPL` (S:122-191) no longer calls `ACTION=start`; it reads tags, wipes first-boot state, stages the
pinned commit, writes `/opt/frankie-box/fleet.json` and installs `frankie-fleet-day.service` (reboot-resume only). The
original scenario (plan refused for a missing class / MAP_URL) cannot occur because no start is attempted; the fresh
start is run.yml's, with the full dispatch set. No `|| echo` remains in the user-data or the driver (`frankie_fleet_day.sh`
honours every exit code). Introduced: (a) run.yml has NO fleet awareness (grep: no `fleet`/`FRANKIE_FLEET` in
frankie_box_run.yml); fleet mode reaches a run.yml-dispatched start only through `fleet.json` (`_config_file`, F:103-111)
-- that works, but a restage by run.yml to a NEWER commit leaves `fleet.json.code_root`/`commit` and the systemd unit's
`ExecStart` on the user-data's commit, so a reboot-resume resumes the day on the OLD checkout (NEW-6). (b) `set -euo
pipefail` + `fail()` writes `fleet-boot-failed.json` only for the tag checks; a failing `aws ssm get-parameter` / `git
clone` / `git fetch` exits the script with NO marker (S13 is half-closed; NIT-3).

### B2. The second day never starts -- CLOSED (by redesign)
No self-start, so no second `ACTION=start` on one run. The driver resumes every saved day of the run in one loop
(frankie_fleet_day.sh:31-45) with `ACTION=resume` + `ACTION=kick` per day, which the queue accepts repeatedly. The
external start is documented as one `DAYS="D1,D2"`; run.yml is unchanged, so that is an operator convention, not code.

### B3. The claim is a no-op on a real box -- PARTIALLY
Closed: the driver runs `claim-day` under `/opt/frankie-box/venv/bin/python -B` (frankie_fleet_day.sh:15-16, 34), the
exit split is real (0 won / 1 lost -> `continue` / >=2 -> `exit` at :35-36), OFF returns 2 (F:984-986), an exception
returns 2 (F:1001-1005). STILL OPEN in substance: `claim_day` now has exactly ONE caller, the reboot driver (grep over
deploy/ and .github/: no other `claim_day`/`claim-day`). The fresh day-start path (run.yml stage+start) never claims, and
the handoff's gate uses `record_root_finished` + the lease, both keyed by (run, day) with no instance check at entry. The
original scenario (two boxes dispatched the same day) now runs the day on both boxes through ROOT and teacher, and the
second box queues for the lease and runs a SECOND classroom for the same day after the first: the "hard guarantee" is
enforced only on a reboot. Fix: claim (run, day, 'root') in the handoff at the first fleet boundary of the day (or in
`classroom_gate` before `record_root_finished`), refusing the day loudly on `won=False` (status `fleet_duplicate`, the
day saved, nothing started); the driver's claim then becomes the idempotent re-check it already is.

### B4. Two days per box deadlock the box holding the GLOBAL lease -- CLOSED for the lease, the box still deadlocks
`acquire_classroom_lease` (F:569-590, the check at F:587) asks `classroom_cpus_ready` (F:548-566) BEFORE writing the lease; `lane_for` is
read-only (cores:315-501 reads `live_bookings()`/`core_map()`, writes nothing), so the poll every 30 s has no ledger
side effect. With `waits_for > 0` the lease is NOT taken: the original fleet-wide hold (A holds the lease through B's
ROOT) cannot occur. Lawfulness of the `held` fallback: cores:420-425 answers the held booking with no `waits_for` key for
`FRANKIE_CLASSROOM_CPUS=held`, `classroom_cpus_ready` reads it as 0 -> ready; the classroom then runs on the day's own
32 while the sibling's ROOT keeps its 32, the lease is released at the classroom boundary, the sibling's WAIT unit
acquires and resumes on its RETAINED set (resume_owner, queue:2331-2340: `REBOOK=on` only matters when the booking is
gone; with it retained the same 32 are reused). Lawful, at the cost of a 32-CPU classroom.
The fleet half ALONE (queue unchanged, `FRANKIE_CLASSROOM_CPUS` unset -> default `all`): A at its gate while B is in
ROOT -> `waits_for=32` -> `fleet_waiting` -> saved, its 32 RETAINED (queue:1704); B reaches its gate -> A's retained 32
are `taken` -> `waits_for=32` -> saved, retained. Both WAIT units poll `lane_for` forever (each needs the other's
retained 32). The lease stays free (no fleet damage from the lease), but every two-arm-day box is dead at its second
gate, and NEW-2 then stops it. So: cannot deadlock the LEASE; does deadlock the BOX. The fail-open on `None`
(F:565: PlanRefused/no ledger -> proceed) also has a cost once the queue half lands: a waiting day whose booking was
released has no booking -> PlanRefused -> proceed -> it takes the lease, then queues for admission behind the sibling's
grown 64 through the sibling's whole tail (data/search/.../jev, hours) while holding the lease (NEW-4).

### B5. The golden AMI defaults to the main box -- CLOSED
`step_golden_ami` reads the root volume size (S:729-738) and refuses `root_gib > --max-root-gib` (default 300; S:751-757);
the main box's ~2 TB root is refused, a 3072-GiB fleet root is refused too (so a fleet box can never be re-imaged by
accident). The user-data wipes `work/frankie-queue`, `work/cpu-bookings`, `cpu-bookings`, `work/experiment`, `work/logs`
on first boot only (S:154-159), which matches `Q.QUEUE` (queue:96), `C.LEDGER` (cores:120, with `released/` and
`waiting/` under it) and `RUNS` (experiment:164-165). The `.fleet-prepared` marker guard is correct for a reboot.
Introduced: the size proxy is only a proxy -- a small-root box imaged AFTER it was fleet-prepared ships `.fleet-prepared`,
`fleet.json` and an ENABLED `frankie-fleet-day.service`; on the new box that unit can run before cloud-init rewrites
`fleet.json` and resume the IMAGED box's run/days under the new instance. Cheap guard missing: the driver should refuse
when `fleet.json.instance` != IMDS instance-id (NEW-7).

### B6. The idle guard stops every fleet box; a stopped box never resumes -- PARTIALLY
Closed: the template (S:538) and the per-box tags (S:893) stamp `KeepRunning=true`; `step_day_box_role`'s policy
grants `ec2:CreateTags` on Project=frankie instances (S:646-648) so the box's own `keep_running` succeeds; the driver
runs on every boot (user-data unit `WantedBy=multi-user.target`, S:177-187) and resumes `saved` days. STILL OPEN, two
ways: (1) the tag is cleared by the box itself in the fleet's NORMAL state. `keep_running(False)` runs at the end of the
orchestrator start (experiment:5413) and at every line worker's end (queue `X.keep_running(run_name, False, ...)`, the worker-end block), guarded only by `box_in_use`
(experiment:737-770: orchestrator starts, line-worker locks, CPU controllers, recent kicks -- NOT the fleet WAIT or
heartbeat units). A box whose days are all saved at the gate waiting for the lease has no worker alive -> the tag is
cleared -> the guard (idle_instance_guard.py:118-130: tag != true and no lane lease; a day-box has no lane lease,
`protects()` :85-93) stops it within 6 h. With 15 boxes serialised on one lease, waiting in line IS the common state for
hours. (2) After that stop, a manual start runs the driver, which resumes + kicks but never re-stamps `KeepRunning=true`
(only the orchestrator start does, experiment:5408; the driver and the kicked worker do not), so the guard stops the
box AGAIN within 6 h, now mid-ROOT, worker alive or not (the guard reads only the tag and the leases). Reboot-resume also
covers only `saved` (or done+finish saved) entries (F:447-475): a day left `running`/`unknown` by a reboot mid-stage is
not resumed (resume_owner accepts `unknown`; the driver does not list it, and nothing reconciles before it lists).
See NEW-2 and NEW-5.

### B7. Real-store fairness: a dead earliest waiter stalls the fleet -- CLOSED, with a new hole beside it
`S3Store.head` returns a float epoch (F:322-324); the WAIT unit re-PUTs its marker every poll (`heartbeat_waiting`,
F:512-523, called at F:916) keeping `root_finish_epoch` for ORDER; `acquire` yields only while the earlier waiter's
heartbeat silence is under `fair_wait` (F:596-608). The original scenario (box 3 dies after writing its marker) is
closed: its heartbeat goes silent, the next poller passes it after 300 s. Toys cover it (`test_dead_earlier_waiter_does
_not_deadlock`). No `drop-waiting` CLI; acceptable given the silence rule. The hole the fix opens is NEW-1: liveness is
now measured but READINESS is not, and the gate enters the line (`record_root_finished`, F:719) BEFORE the CPU check.

---------------------------------------------------------------------------------------------------------------------------

## One-box E2E with FRANKIE_FLEET_DAY_LIST unset: unchanged (checked line by line)

Every changed line in the handoff is under `fleet is not None` or inside the gate branch, which additionally needs
`e.get('classroom_arm')`; the moved release (H:353-362) is under the same guard, and `_fleet()` only imports the module
and asks `enabled()`. `enabled()` now also reads `/opt/frankie-box/fleet.json` (F:103-117): absent on the main box and
in the container -> `{}` -> OFF; it is never created by anything but the fleet user-data. `instance_id()` and
`location()` read the same file with the env winning. The queue, cores, experiment and the idle guard are untouched by
these commits. The stack's non-fleet steps changed only in the launch-template/golden-ami/fleet-launch steps (never
applied to the main box). `TestFleetOff.test_off_takes_no_fleet_branch` holds. No side effect outside the guard found.

## Secrets and tokens
User-data: the GitHub token is read into `GH`, folded into a base64 `AUTHORIZATION: basic` header, `GH` unset, the header
passed as `git -c http.extraheader=...` for the clone and the fetch only (`-c` is per-invocation, never written), then
`remote set-url origin` to the tokenless URL (S:160-166). `.git/config` is clean; the user-data log has no `set -x`;
the receipt and `fleet.json` carry no secret. Residual: the base64 header is in `git`'s argv for the clone/fetch
duration (ps-visible to any local user; the box is single-tenant) -- NIT. `_detached_env` passes every `AWS_*` variable
(F:678-692); on a role-credentialed box none is a static key -- NIT.

## Quota / usage arithmetic
`used` = vCPUs of every `running` + `pending` instance whose `InstanceLifecycle` matches the market (S:839-850; On-Demand
has no lifecycle field -> `is_spot False`, correct); all families counted (over-conservative, safe); `need = count *
_vcpus_for_type(type)` (S:774-781, unknown size -> 64, never too small); `headroom = quota - used`; refused when `need >
headroom`. Correct for the stated purpose.
