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

## Source preparation after the user's elapsed-time correction

At 12:07:49Z workflow36317931214 reported root-native-finalize, original
PID/token alive, failed=0, ten saved/read_verified checkpoints and latest000009.
Elapsed stage time was45minutes33seconds, NOT100minutes. The approximately100
minutes above refers only to extrapolated future duplicate passes. Already
elapsed work is a sunk cost and is not evidence that continuing is faster.

This commit prepares a narrow wrapper change to reuse the actual disk
reconciliation's rows/bytes/SHA256 in the ledger inventory. The producer's
reconcile_all remains unchanged and still reads every ledger independently.
Before reconciliation the wrapper closes/fsyncs each sink and records regular-file
device/inode/size/mtime_ns/ctime_ns. Reuse requires that identity to remain the
same and the disk receipt to match the closed sink and expected count. Any
mismatch raises instead of returning a completed receipt. No writer counters
alone substitute for disk verification.

Static review followed the complete producer reconcile/close/receipt path and
wrapper checkpoint path. In-memory Python syntax compilation passed without
imports, workload execution, pycache or local artifacts. No scientific tests,
canaries, comparison runs or additional validators were run. The change removes
two complete scans by inspection; elapsed-time improvement is not yet measured.

This is SOURCE ONLY. It does not alter running runtime2931134 or queued classroom
runtimea80990d. No ROOT stop/restart, hot patch, affinity change or stage dispatch
was issued. Read-ahead helpers and sealed-ledger recovery are still design work,
not implemented by this commit. The current recovery route would verify/copy
large prefixes and would redo53,414records from000009; its cost must be included
in any changeover estimate. A fresh verified checkpoint is still required for
a runtime transition under the user's standing instruction.

Remaining source inspection: projection already fans out to all required layers
in ONE member-ledger pass. project_sections rereads the smaller lifecycle ledger.
frankie_box_digest_document.py includes repeated table proofs and document hash
passes; their actual output sizes and time costs have not been measured. They
are not included in the100-minute estimate, and no change to exact digest proofs
was prepared. Unknown later costs justify investigation, not an invented saving.

## Authorized finalized-state transition preparation

The user said "Proceed" after the source-only scan removal and recovery-cost
discussion. This authorizes completing the optimization and its checkpointed
transition; the fresh verified checkpoint requirement and all conservation,
no-extra-science, no-hot-patch, evidence-retention and manual-sequence rules remain.

Read-only workflow36318605580 at12:20:11Z reports checkpoint000010 as the eleventh
saved/read_verified checkpoint, original PID/token alive, failed=0 and stage
root-native-finalize. Its reported verification time is1790511419.4061108.
The terminal descriptor must still be inspected and freshly verified before
any process signal. No completed calculations receipt is established by this.

Prepared implementation:
- A bounded disk scan uses coordinatorCPU1 and14 helper threads CPUs2-15,
  CPU0 reserved. Helpers read up to28 pending8MiB chunks and count newlines.
  Coordinator hashes bytes in original order. All three ledgers remain required.
  Exact rows/bytes/SHA256 and stable device/inode/extent/mtime/ctime are checked.
- Finalized recovery references the existing closed materialized files in place.
  It performs one independent disk verification and reuses that observation for
  final reconciliation and receipts. No ledger copy, hardlink, deletion or
  scientific replay occurs. Fresh empty sink placeholders remain retained.
- Projection follows the exact paths in the verified run receipt. Producer math,
  all sections, source records and reducer semantics are unchanged.
- Full-state runtime compatibility permits only the exact deployed serializer
  629b1355... and ledger storage b6636165... plus previously permitted lineage;
  Python, cloudpickle and complete driver identity must still agree.
- Existing identity-bound pause script adds terminal-finalize mode. It requires
  all2032203records, locked/finalized state, closed materialized ledgers and the
  original source/run/runtime identity. It freshly verifies the checkpoint chain,
  adapter and serialized full-state bytes before signaling the exact ROOT pidfd.
  It refuses if ROOT has advanced beyond finalization or calculations are retained.

Review covered byte ordering, final-line counting, bounded memory, read descriptor
lifetime, closed-sink refusal, unchanged-file checks, exact runtime compatibility,
terminal recovery bindings and existing projection consumers. In-memory Python
syntax compilation passed for modified Python and the pause script's Python body.
No scientific tests, canaries, comparison runs, extra validators or parallel
agents were run. Workflow bash syntax validation remains required before execution.
No speedup or deployment is claimed in this source commit.

Activation sequence: inspect terminal descriptor; dispatch the existing pause
route at this immutable source; verify actual pause receipt and exited PID;
allow existing classroom staging36311196131 to finish; stage this distinct
finalization runtime using the existing staging route; resume the same calculation
root from the exact terminal checkpoint. This is a runtime transition of the same
completed scientific calculation, not a duplicate calculation or classroom stage.
Any failure leaves all checkpoint/ledger evidence retained. Do not fall back to a
nonterminal checkpoint or silently replay scientific work.

## Actual transition and live resume — 2026-09-27 12:34Z

User's "Proceed" was carried out using the terminal checkpoint; no record replay.
Runtime is now01caae9d3a0e7ccdb165c734fe25ecf130c5c0f5, immutable ref
codex/frankie-finalization-runtime-01caae9. Active resume workflow:
https://github.com/DavisAI1974/Markets/actions/runs/36319242284
CODE_ROOT=/opt/frankie-box/code/01caae9d3a0e7ccdb165c734fe25ecf130c5c0f5-36319063424-1/markets
Same calculation root, original source binding/authorship, data_workers=48.
New PID58168, token099d4eb6-a46d-4b94-a888-f15e55c1ee7e:53570313.
Do not start another process, replay calculations or hot-patch this runtime.

Terminal descriptor read36318732685 confirms checkpoint000010:
completed2032203, finalized=true, all three ledgers closed/materialized.
Full driver165849388bytes SHA2567d305c7086faaddaeef6357e47dac6022eaff9b4983fe4c61a44dec0d62ddf20.
Checkpoint hashf0dc28f2d67292cf69e8023c5a7f618e477b7488a5f1cfbbca059a0da4aa6945.
Member537182189410bytes/1535939rows SHA2560ebc951a6e3d7b936aba15be1d3aac5cbee076de373e6e77bc442654b0e6e598;
lifecycle14424155424bytes/13402454rows SHA256d3db0c628eef377e136d0e1809b69babd942e621b314c6893b062327dbb4752a;
legacy1323153203bytes/1006873rows SHA2560c1043b78ea029ea46f256c12002fdd13ab8c5e09839400e9915e899150b1635.

Pause36318825831 succeeded: fresh chain/adapter/full-state readback at
1790511834.0294225, exact old PID56833 exited at1790511849.5112448 after
SIGINT then SIGTERM; no owned native child remained, no unsaved reconstruction.
Receipt /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/pause-for-terminal-finalize-56833.json:
1706bytes SHA256a2077f99a7a5ee1fb6cbe67059b8a5705329918bd9284b2449b39538af15e1a5.
Old ROOT36309059667 concluded failure due to this intentional verified handoff.

Existing classroom staging36311196131 SUCCESS, without duplication:
CODE_ROOT=/opt/frankie-box/code/a80990d42161c3020c21363137439da7dd6ba527-36311196131-1/markets
intent76a7dc5ae9542e32a11591ab259e78f2084bd6aeb509f854b78108895ca5d2d8;
pack509c57700dd5e395cb11f044a2afda76bbfae8ebd1313818d5244ae011dce0f8.
Finalization staging36319063424 SUCCESS at12:30:07Z:
intentf2f6f90fd5d72f3c98eec447ee6deefa778529124c9955ac69a2f46d0bba823a;
packe0f54aa5f9cbcd9110e7cbfe38de60160eb639d180e4109a1df95248223927ea,
589553625bytes,3681files. Neither stage changed the active checkout; model_calls=0,
source_replays=0. The resume explicitly selects the staged finalization checkout.

Live probe36319263275 at12:31:51Z: new PID alive, root-legacy-reuse, failed=0.
Resource observation36319354416 at12:33:23–12:33:43Z confirms
root-ledger-verify-member. Latest sample's stage counter:
59684945920/537182189410 BYTES, failed=0 (counter timestamp12:33:33.958Z).
Entering this scan requires the CPU1 coordinator and14 CPU2–15 reader helpers to
pass affinity readback and startup barrier. Full helper execution receipts remain
pending successful complete scans. RSS582056KiB, swap0, process threads46
(includes library threads; not46 ledger workers). During20.002575seconds rchar
advanced26633830400bytes while physical read_bytes was unchanged: this interval
was cache-backed, NOT a sustained-storage throughput or controlled speedup result.

The new full-state unpickle, final reconciliation receipt/checkpoint, projection,
digest and completed calculations receipt remain pending. No calculation
completion, actual classroom delivery/acknowledgment, learning or Tuesday outcome
is claimed. All original evidence is retained. Continue the original manual
Monday inputs/config/host/Granite/principal/classroom/initial grade/same-session
correction/final grade/retention sequence only after actual calculation completion.
