# S10 fleet: a box keeps its days end to end, now ENFORCED (2026-10-09, FLEET role)

Greg's rule (2026-10-08, reaffirmed 2026-10-09): a fleet box keeps the days assigned to it from the first stage to the
end. No box switching. No day, and no stage of a day, ever runs on another box. The classroom lease only orders WHICH
box's day goes next. Before this change nothing moved a day, but nothing enforced the rule either. This is source
only: nothing ran on a box and no AWS call was made.

## What changed

`deploy/aws/box/frankie_box_fleet.py`
- **The day's owner.** `day_owner(run, day)` returns the day's box from the seeded day list. When the list has no box
  for that day, it returns the create-only pin `owners/<run>/<day>.json`. `check_day_owner(run, day, stage)` writes
  that pin on the first claim of ANY stage, using `put_if_absent`, so two boxes racing for the pin end up with exactly
  one owner. Every later call from another box is refused with the reason
  `day <d> is assigned to box <b>; a box keeps its days end to end`. If the pin exists but cannot be read, the call is
  refused.
- **`claim_day`.** The owner check runs first. A box that is not the owner gets `won=False`, `not_owner=True` and the
  reason, and nothing is written. The CLI exits 1 (the driver skips the day). ROOT and every later stage use the same
  check.
- **`_update_progress`.** It never rewrites `doc['box']` once it is set. A write from a box other than the day's owner,
  or other than the box already on the object, raises `NotDayOwner`. The handoff records that error on the receipt
  (`fleet_stage.error`). The gate's advisory writes go through `_try` and are dropped, but the gate checks ownership
  itself first.
- **`acquire_classroom_lease`.** Only the day's owner can take the lease for that day. Any other box gets
  `acquired=False, not_owner=True`. The gate and the WAIT unit both acquire through this call.
- **`classroom_gate`.** It checks the owner first. A box that is not the owner gets decision `not_owner`: no waiting
  marker, no lease and no WAIT unit. If the store cannot be read, the gate falls through to the lease take, which
  checks again and refuses (fail closed).
- **`wait_action`.** If the lease take answers `not_owner`, the unit exits with code 3 and never resumes the day.
  `fleet_resume` is reached only after an owner-checked acquire.
- **`takeover_classroom_lease`.** Kept as it was. It moves the order token, not the day. Its audit now records
  `day_owner`. If the operator's box is not the owner, that box gets nothing it can run, because acquire and the gate
  refuse it for that day.

`deploy/aws/box/frankie_box_stage_handoff.py`
- In fleet mode, after validation, the boundary checks the owner and pins the day on its first boundary. A box that is
  not the owner saves the day with status `fleet_not_owner`, and it never hands off to the successor on that box. A
  store error here is recorded and does not stop the day, because the day is already running on the box that ran its
  earlier stages. The gate's `not_owner` decision maps to the same save.

`deploy/aws/box/frankie_fleet_day.sh`: one echo line. Exit 1 now reads "owned or claimed by another box".

## Paths checked
- **Reboot-resume driver (`frankie_fleet_day.sh`).** It resumes only this box's own queue-saved days. Each resume goes
  through `claim-day`, so the owner is enforced.
- **WAIT unit.** It resumes only after an owner-checked acquire, and exits 3 on `not_owner`.
- **Heartbeat unit.** It only refreshes a lease this box holds. It runs nothing.
- **Lease release.** It runs only when this box holds the lease.
- **Lease takeover.** It moves the order token only (see above).
- **Classroom gate and every handoff boundary.** Both are owner-checked.
- **Rebook.** `REBOOK=on` re-books CPUs on the same box during a resume that has already passed the owner check. It
  never picks another box.
- **Open gap, outside this file set: a FRESH day start through `frankie_box_run.yml` (`ACTION=stage` then `start`)
  calls no claim.** If an operator dispatches it to the wrong instance, ROOT runs there. The day is then caught and
  saved at its first handoff boundary (`fleet_not_owner`), so no later stage runs on that box. Catching it before ROOT
  starts would need a `claim-day` call in the queue's start path.

## Verification
- `python3 -m py_compile` passes on both Python files, and `bash -n` passes on the driver.
- `tests/test_frankie_box_fleet.py` and `tests/test_frankie_box_fleet_handoff.py`: 31 passed, with no fixture changes.
- A one-off inline run on the fake store, with no new test file, gave these results:
  - A claim from a box that is not the assigned box was refused.
  - The first claim of an unassigned day pinned it, and a second box was refused.
  - A progress write and a lease take from a box that is not the owner were refused.
  - The gate returned `not_owner` for a box that is not the owner and `proceed` for the owner.
