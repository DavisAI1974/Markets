# Session 17: same owner restarted on shared-section readers; full day still running

Repository DavisAI1974/Markets; branch ccr-d2f8f826-iefeah-frankie.
Fetch CURRENT HEAD and preserve newer work. This document is operational continuity, not completion.
Read SESSION16 and SESSION15 for original source pins, mounts, saved package and cleanup receipts.

## Greg's latest scope

Finish the ENTIRE existing one-day e2e-20231018-a2 / 20231018 workflow, including Frankie, classroom/search/lessons, exchange, Jev, meeting, school and reports. Then safely stop unused compute preserving every disk and data file.
Greg explicitly narrowed the sidecar audit: do NOT work on future days now; apply fixes to the code for already-completed processes and remaining consumers of this day, including revisits, without rerunning completed calculations.
No 30-day launch, replacement runner, discarded evidence, new owner or rebooking.
He is frustrated by the time spent and asks to prioritize finishing. He asked to be told when restarted; that notification was given.

## Actual restart and latest verified state

AWS connected and verified account 568968024170, us-east-1.
MAIN i-035994afa8bdf66a5 running. Other instances remain stopped; preserve them.
Owner e2e-20231018-a2-20231018-a1.
Booking day-run-20231018-day_slot_repoint-1791535148-1706, retained CPUs0-63.
Fast disk vol-0fbf7bc0991bc8e39 holds active output; NEVER detach.

Old PID4103 completed the protected pass and saved at08:10:27Z. Class acknowledged08:09:46Z. No live worker remained before this resume.
Existing ACTION=resume was executed at2026-10-14T08:46:57Z (04:46:57 Eastern), on the SAME owner and booking. Its existing marker was archived by the native operation, not manually removed.

Source commit running:
 8bb2eb2250123801da095eac60243d03d5c02391
Checkout:
 /opt/frankie-box/code/8bb2eb2250123801da095eac60243d03d5c02391-push-20261014T084221017982704Z/markets

At08:54:08Z:
- root_entry.state=done, finish.state=running, finish PID5637.
- class_entry.state=running; class worker PID5657.
- actual classroom child PID5820, started08:48:18Z; native core wrapper PID5818.
- recovery doctor PID5670, CPU watcher PID5666.
- ALL those observed actual script argv paths point to8bb2eb2. Not merely code-root arguments.
- owner commit/code_root rebound to8bb2eb2; exact attempt/booking preserved.
- classroom restored/read the saved package and is computing: phase-progress now last_event=saved_state, saved_at1791967856.0958061, stop_requested=false, still only package in saved_phases.
- package timings.restored=false is the historical setdefault value, NOT proof of a new package build. The child read2.494GB physical bytes, ~3.025GB rchar, had~30GB RSS at08:51; cumulative CPU325.21s user at08:54.
- NO whole-day later completed phase observed yet.
- shared-products still only second-set-reading.json and lock at08:54. The new row sections/index conversion has NOT yet been reached. Do not claim actual-day reconstruction equivalence or indexed cutoff timing is runtime-proven.
- no new161GB raw sidecar traversal observed.

Resume command receipt:
 /opt/frankie-box/work/frankie-queue/session17-resume-8bb2eb2.json
Despite suffix it contains launcher log lines plus JSON. A follow-up json.load failed and made SSM command092914de-82f7-4139-b205-6c11c41e78ef report Failed, BUT RESUME ITSELF SUCCEEDED. Do not resume again because of that parse failure.
Native parked-watch raced the explicit kick and started workers on the same NEW checkout. Root worker environment lacked FRANKIE_EVIDENCE_ENCODING=fast per kick's recorded settings difference; no process interruption was made merely to change encoding. Root digest=off and classroom CPUs=all were retained. Native allocation split classroom32 even CPUs beside the independent work, inside the same64-CPU booking.

## Published source changes

d39be9586e860c4f0fba984c06bd39715ab39117:
 queue kick, handover, parked-watch actual argv used caller HERE even when a newer code_root was supplied. All three now name selected code_root/deploy/aws/box/frankie_box_frankie_queue.py.

8bb2eb2250123801da095eac60243d03d5c02391:
- teacher_products.indexed_second_set: legacy teacher-second-set.pkl converted ONCE into existing immutable RecordWriter/RecordStore/JoinedRecords in shared-products/indexed-second-set/<source identity>. Original pickle retained. Records in4096-row chunks. Native joined source returned directly.
- ensure_sidecar_sections: original snapshot RowsStream (6.16GB) plus indexed typed records reconstruct exact original sidecar JSON using existing teacher._sidecar_line and EACH sealed block's teacher_as_of. Requires each block's original byte count+SHA AND entire161126241394-byte original SHA before publishing sections.json. Reads only original sidecar header and bounded file-claim tails, never full161GB sidecar.
- shared-products/sidecar-sections/<original sidecar SHA>/ contains independently hashed columns using existing stores, all original fields, a first-set column preserving original key order/values, identity column, cursor index. No data truncation, dropping or clock replacement.
- whole SidecarStream now uses these sections with NO raw full-sidecar fallback.
- cutoff reads seek the last applicable row via cursor index; leaf and multi-leaf readers request only needed role columns. Combined cutoff fetches complete final row separately.
- completed-block iter_block and BlockSidecarStream revisits use sections too. Partial, still-producing sealed-block reads remain bounded raw-range readers. Completed-block digest recreates original JSON bytes from exact columns to preserve original stream.record.
- queue main execs the selected script BEFORE any action if invoked from another checkout; child environment forces selected CODE_ROOT/MARKETS_SHA/PYTHONPATH; doctor revive box paths select current checkout.
- teacher producer was NOT changed. Section preparation deliberately requires a current complete-source file claim and completed sealed-block publication. A changed/missing claim refuses instead of triggering a full-sidecar fallback. Investigate genuine corrected-source cases if this day reaches them; do not relax evidence gates.

Bounded local checks passed (not a new repo test framework):
 /tmp/check_sections.py in this session, working repo /workspace/scratch/5223e26b9a92/VerifiedMarkets.
Used real source modules (only package __init__ eager torch import suppressed locally).
- exact original lesson JSON bytes and summary equal.
- exact original cutoff product equal.
- exact original selected-block rows and stream.record equal.
-99 planes, per-block200/300 fixture locks, typed-to-JSON lists/scalars, selected role reads, warm reuse without legacy reload, changed-source refusal.
- py_compile and git diff --check.
Earlier mock kick test verified actual root/class argv and environment from selected checkout even if HERE points old.

Actual-day equivalence still gates on ensure_sidecar_sections reconstruction. Preserve partial products if it fails. Completed part manifests are reused on retry; unpublished pending files retained, not deleted. Legacy unpickle is one-time and memory-intensive; do not interrupt it or mistake it for a161GB raw scan.

## Deployment receipts

Existing push-code route staged exact8bb2eb2, verified4182 files,23.60s.
SSM command4a88ea30-9661-4c8d-aba6-8875c4019dc0 succeeded.
S3 frankie-granite42-568968024170-us-east-1:
 readiness/20260923/code-push/session17/8bb2eb2250123801da095eac60243d03d5c02391.pack
295384 bytes, SHA25678a4b97373aa589e1ac01b66998c30925abda073c57a9f722ea44c42c8941acc.
Delta base1dedd031c1b13c047080c2f7529ef1b155b6d616.
Staging receipt beside checkout. No secrets or presigned URLs in this document.

An exact staged-source snapshot for local verification was uploaded:
 readiness/20260923/code-push/session17/current-code-snapshot.tar.gz
in same bucket. Code only, no scientific run data;1,226,435,320 bytes.
Local VerifiedMarkets was extracted from this exact1dedd staged checkout. New8bb2eb2 Git commit/tree objects reconstructed from GitHub metadata and verified exact before packing. It is a shallow local snapshot; older deferred LOCAL branches are elsewhere, untouched. Do not reset/clean other work.

## Remaining read limitations: do not overclaim

The161GB whole-reader path is removed in running source, but actual shared section preparation has not run yet.
Whole lesson still needs all its original values and writes whole required lesson evidence; sections remove redundant raw decoding/scans, not the required scientific work.
At restart ROOT and CLASS brain stage_source_witness each hashed the retained52.7GB pickle (rchar~55GB each, read_bytes0 from page cache). Log says no work/file-claims.jsonl above that archived source. This is an EXISTING additional reuse gap; not fixed by8bb2eb2. Do not say all huge reads are eliminated.
Brain sidecar witness DID use its existing claim; combined BOSS second-set measurement was reused, no161GB measurement replay.
Original snapshot6.16GB and legacy52.7GB index preparation are expected once for this retained old day. Saved147GB block lesson ledgers are not used as a disguised full-read replacement.

## Attendance and completion

Business-account hourly automation was created successfully:
 title Finish Frankie’s one-day run
 id6acf4277f388819187610ec14d7b497d
 enabled, first scheduled05:51 America/New_York, hourly thereafter. Old personal-account watch remains PAUSED.
It is instructed to inspect live state, leave healthy progress alone, use existing recovery for failures, notify only on full completion or material blocker, and stop MAIN only after all full completion conditions. Avoid racing an active parent operation; inspect first.

Completion means root.state=done AND finish.state=finished AND hub_runtime.owner_finished=true, actual whole-day classroom/search/lessons/exchange/Jev/meeting/school/reports current, no child/revival/native successor/correction work unfinished.
Only then KeepRunning=false, StopInstances (never terminate); preserve every disk/data file.
Running/root done/a report file are NOT completion.

Use AWS run_script via call_boto3 SSM. Its validator rejects string literals containing attribute traversal .__file__; inspect actual process argv or inspect.getfile when needed. Avoid printing entire owner/status history: select root_entry.state, finish.state/pid, class_entry.state, owner attempt/booking/commit, marker, booking. Queue logs have old giant JSON snapshots; prefer new suffix or actual stage log, not historical states.
