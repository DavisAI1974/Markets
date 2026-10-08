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

## Commit hashes (on ccr-d2f8f826-iefeah-frankie; rebased onto the parent's box records)
- `eb1bafe3` - the fleet module + its 14 toys.
- `7bbdae02` - the handoff hooks (gate + release) + 4 toys.
- `268f70cf` - the stack fleet steps (launch-template fleet spec, fleet-launch, golden-ami) + 10 toys + the atomic
  fake-store fix.
- (this status file + the E2E section land in a following commit.)
Verification on every touched file: py_compile + ast.parse on .py, bash -n on the stage script, git diff --check clean;
28/28 toys pass (`python -m unittest tests.test_frankie_box_fleet tests.test_frankie_box_fleet_handoff
tests.test_frankie_aws_stack_fleet`).

## Open decisions for Greg
1. **Self-driving stage vs. the SSM reviewed-helper stage.** The fleet user-data stages the commit by `git clone/checkout`
   under `/opt/frankie-box/code/<commit>`, not the `frankie_box_stage_code.sh` reviewed-helper path (that path needs the
   CODE_B64/PACK_* inputs the SSM dispatcher supplies, which a box has no way to produce at boot). The clone needs the
   GitHub token from SSM (`/markets/frankie/github-token`, us-east-2) and the repo being reachable. Confirm this is the
   staging you want for a self-driving fleet box, or whether fleet-launch should instead leave the box idle and the
   staging be driven by the workflow as today (`frankie_box_run.yml` ACTION=stage) before the days start.
2. **Spot boxes and the classroom.** Spot is lawful for ROOT only (resumable), so a `--spot` box's two days' classrooms
   must run on an On-Demand box. The S3 lease serialises classrooms fleet-wide and a Spot box reaching the gate still
   waits in line, but nothing yet STOPS a Spot box from holding the lease and being reclaimed mid-classroom. If that
   matters, the gate should refuse the lease to a box tagged `ClassroomEligible=false` (a few lines; needs the box to
   read its own tag). Named, not built, pending your call.
3. **The gate stage.** The classroom gate is placed at the `teacher`->classroom boundary (`FRANKIE_FLEET_CLASSROOM_GATE_STAGES`
   default `teacher`), on the reading that the teacher is the box's own parallel work and the classroom is the serial
   shared phase. If the serial phase should begin earlier or later, set that env to the right stage(s).
4. **Clean-on-save at the gate stage.** In fleet mode the gate stage (teacher) does NOT run the clean-on-save optimisation
   (a save+resume there would race the lease). The teacher outputs are cleaned later by their own day's chain / the
   archive step, not at the gate. Accept, or we wire a post-classroom clean of the teacher outputs.
5. **The day-list prefix and the run name.** `FRANKIE_FLEET_DAY_LIST` defaults the bucket to the granite bucket; the day
   list is seeded by `frankie_box_fleet.py seed-day-list` or an operator. The launch steps default `--run e2e-20231018-a2`
   and `--fleet-day-list fleet/<run>`. Confirm the run name and prefix for the real fleet.

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
