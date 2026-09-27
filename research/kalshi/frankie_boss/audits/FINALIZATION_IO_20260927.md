# Monday finalization I/O observation - 2026-09-27

## Actual running state

Canonical ROOT36309059667 remains runtime293113435a8fdf7bd5566f2652e1a1f7a1734c35,
PID56833, token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:52429441. It entered
root-native-finalize at11:22:06Z. No runtime transition or process change was made.
User observed that finalize probably needs CPUs and helpers. Read-only counters
and the exact runtime/pinned producer source were inspected in response.

## Measured counters

Existing progress script RESOURCE_METRICS=1 reads process and host counters;
it does not attach a profiler, modify affinity, or run calculations.

- Workflow36316055960,11:32:40.904582-11:33:00.906937Z: ROOT read3,589,144,576
  physical bytes and used5.97CPU-seconds over20.00236seconds. End RSS11,379,764KiB,
  swap0. Host I/O pressure avg10 approximately67.18percent.
- Workflow36316750429,11:45:42.654614-11:46:02.657075Z: ROOT read3,580,100,608
  physical bytes and used5.94CPU-seconds over20.00247seconds. End RSS11,379,764KiB,
  swap0. Host I/O some/full pressure avg10 approximately69.10/69.04percent.
- Both samples retain the original PID/token, root-native-finalize, failed=0,
  and ten saved/read_verified checkpoints, latestcheckpoint-000009.json.

These samples establish active disk reading and substantial I/O waiting, not a
measured storage throughput ceiling, a finalization percentage, or a speedup.
No EBS configuration/capacity limit was newly verified.

## Exact source finding

At runtime2931134, deploy/aws/box/frankie_box_bedrock.py closes RuntimeSections
before root-native-finalize. It then materializes all three ledgers, calls the
pinned driver.finalize, and calls sinks.reconcile_all. At producer pin2ebb8ce8,
native_row_sink.py reconciles member, lifecycle and legacy serially. Each
reconcile closes/flushed the sink, rereads its whole file, counts rows/bytes and
computes SHA256, checking those against emitted evidence and expected counts.

The wrapper then saves/read-verifies the terminal full checkpoint and writes
result.json. Its subsequent LEDGER_FILES loop rereads each whole ledger to count
rows and calls witness(path), which rereads it again in1MiB chunks for SHA256.
Thus reconciliation and later witness construction perform three full passes per
ledger in this portion of the path. These are evidence scans, not a replay of
the scientific source calculations. Projections/digest follow later.

The pinned NativeReplayDriver.finalize also closes stream-end structures and
retains explicit unresolved/censored rows; NativeCalculationRun.finalize emits
the result and built-in gates. Scientific dependencies and these gates remain
required. The seven result-layer containers are not a reduction of the18
historical calculation sections.

## Candidate improvement - NOT implemented or deployed

- Bounded ordered read-ahead helpers for the required independent on-disk
  verification; SHA256 for each ledger must still consume original byte order.
- Preserve exact line-count semantics and independently verify emitted rows,
  bytes and SHA256. Never replace the file read with writer counters alone.
- Reuse the resulting verified count/byte/hash witness for the later result
  ledger inventory only while the same closed file is demonstrably unchanged.
  Bind file identity and change metadata; a mutation must invalidate reuse.
- Independent ledgers can be checked concurrently with bounded I/O, but their
  shared disk and unequal sizes mean helper count is not a speedup guarantee.
- Measure actual benefit on authorized real work; no extra scientific tests,
  canaries, comparison runs, validators, source replay, or duplicate calculation.

Assigning extra CPUs to the unchanged serial loop does not create helpers.
Adding helpers changes runtime code. User's no-hot-patch/no-restart restriction
remains in force; any separately authorized ROOT transition still requires a
fresh verified checkpoint. The terminal checkpoint has not appeared in these
observations. Nothing was activated, paused, deleted or reconfigured.

## Pending

Ledger publication/reconciliation receipts, terminal checkpoint, projections,
digest, calculations-receipt.json, existing classroom staging36311196131,
inputs/configuration/host/Granite/principal/classroom/grading/correction/retention.
Tuesday and learning outcomes remain pending. Continue the original manual
sequence after actual calculation completion and staging success.

## User's stop/change tradeoff question

Read-only checkpoint workflow36317133363 obtained descriptor000009:
12,036bytes SHA256c932ff5c0b8ef67344ab71c4b428b18afa6f0b3b003bc375ad40808efdd8b42f.
It records1,978,789completed records, finalized=false. Complete driver state is
489,263,908bytes SHA256daf2a325910d9098cda2a92d57c68d17192d4a3d0bc6ca244c74b195b7f1a429.
Ledger bytes at that checkpoint: member523,315,776,595;
lifecycle9,880,382,546; legacy1,291,044,396; total534,487,203,537.
This is53,414records short of the complete source, not a safe completed-run
restart point. Final ledgers can be larger than these checkpoint extents.

Timing EXTRAPOLATION requested by the user, not an observed remaining duration:
at the second sample's178.983MB/s, one pass over that checkpoint size would take
49.77minutes; two passes99.54minutes. The later buffered hash pass may run faster.
This does not establish the current scan offset, remaining finalization time,
or net savings from a code transition.

Existing frankie_box_pause_root.sh only accepts a fresh read_verified nonterminal
checkpoint during root-native-records (or the older reconstruction boundary).
It neither requests a new checkpoint on demand nor accepts root-native-finalize
or a locked terminal checkpoint. A finalized-state handoff would need a reviewed
change; no such change has been implemented or executed.

Existing restore_prefixes verifies old bytes and creates a new append/materialized
ledger generation even for the wrapper's finalized resume. A new full copy would
exceed the350.64GB free observed11:06Z, against534.49GB already checkpointed. That
capacity observation is historical, not a fresh disk read. Reusing sealed files
safely would need a reviewed restore change; deleting evidence is not authorized.

Recommendation communicated: prepare the candidate while required verification
continues; consider a changeover only after a fresh verified checkpoint and a
safe route that reuses sealed ledgers. This is a recommendation, not user approval
to stop ROOT, implemented source, or a claim of measured improvement. The original
no-hot-patch/no-restart restrictions remain in force.
