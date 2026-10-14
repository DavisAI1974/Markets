# Session 16 handoff: deployed combined reading; active old worker; durable reuse unfinished

Repository: DavisAI1974/Markets
Branch: ccr-d2f8f826-iefeah-frankie
Runtime code published HEAD before this documentation: 1dedd031c1b13c047080c2f7529ef1b155b6d616.
Fetch CURRENT HEAD and preserve newer work. Read this file FIRST, then SESSION15 for mounts, cleanup and earlier receipts.

## Greg's current instructions and account transfer

Greg authorized finishing the ENTIRE remaining one-day workflow, including Frankie's existing cycle, search/lessons, exchange, Jev, meeting, school and reports. No 30-day launch or broader 30-day work. No replacement runners/frameworks. Preserve complete evidence, all 99 planes, original clocks, exact owner/booking, saved package, partial outputs and 47 completed block lessons.

Latest correction: "Make sure there are no more going forward and I thought we built durable tables or something so that multiple steps could use 1 read." He means eliminate repeated full 161 GB reads using existing durable/shared data. The narrow combined-findings/measurement change below DOES NOT solve all downstream reads. Do not repeat the previous overstatement that all reads are gone.

Greg is moving to a NEW CHAT ON HIS BUSINESS ACCOUNT because this session became buggy. Finish handoff, then transfer work. Old scratch paths or this account's automations may not be accessible in the new account. AWS and GitHub connectors remain the authoritative route. No new code draft for the broader durable reuse was created.

## Exact AWS owner and latest verified live state

AWS: Greg Davis, account 568968024170, us-east-1.
MAIN: i-035994afa8bdf66a5, running, r7i.16xlarge / 64 CPUs.
Other EC2 boxes remain stopped; preserve all disks/data.
Run/day: e2e-20231018-a2 / 20231018.
Owner attempt: e2e-20231018-a2-20231018-a1.
CPU booking: day-run-20231018-day_slot_repoint-1791535148-1706, CPUs 0-63.

At 2026-10-14 08:00:55 UTC (04:00:55 ET):
- ROOT entry state done, finish state RUNNING, PID4103.
- Class entry RUNNING, PID4122, waiting for shared second-set lock.
- Actual BOTH Python entrypoints and --code-root use OLD checkout 85da915b559c06efbe2d19acd4ec7cb650f99bcc-push-20261014T071758041257862Z/markets, runtime equivalent to 02d61cf.
- PID4103's open sidecar FD position was 120,997,208,064 of 161,126,241,394 bytes. This pass is progressing. DO NOT kill, interrupt or restart it.
- Whole-day classroom phase-progress remains the original saved package only: saved_phases ["package"], last_event "saved: 75", original saved_at 1791677360.3732605.
- package.second_set.json and package.second_set.jsonl do NOT exist in whole-day classroom.
- No whole-day package restore or later classroom phase has yet been observed. Completed block lessons are retained; do not rerun them.
Read live state again before acting; these values are a timestamped observation, not current guarantees.

This is the third large read Greg identified. It is a SECOND-SET MEASUREMENT replay inside root's teacher knowledge publication, while classroom waits; it is not evidence the next classroom phase has progressed.

## Why deployed code did not run

Original PID3122 completed its full shared second-set reading around07:24 UTC, then completed publication work and reached the protective saved boundary at07:31:02 UTC.
The session resumed EXACT same owner with existing ACTION=resume at07:33:42 UTC on then-current85da915, BEFORE the new combined-read code was ready.
The new code was published and staged at07:43:43 UTC. Staging changes /opt/frankie-box/code/current; it does not reload already-running Python workers or their captured child script paths.
This sequencing caused the old worker to remain active. Do not confuse "deployed/staged" with "actual entrypoint executing."

Resume chmod changed ctime on ROOT referenced files, teacher receipt and state split while bytes, inode and mtime stayed unchanged. Old all-dependency shared cache rejected the existing product and replayed the161GB scan. New code below reuses the unchanged sidecar measurement separately and refreshes other parts.

## Current protective marker: let the pass finish, then use corrected code

At07:54:50 UTC, existing Q.request_save wrote:
 /opt/frankie-box/work/frankie-queue/save/e2e-20231018-a2-20231018.save-request.json
by:
 "Activate verified single-pass reuse after the current full reading finishes; continue same owner on current code (Greg authorized remaining workflow)"
It retains the SAME attempt/booking/CPUs. It does not release the booking.
Existing owner code stops at its next save boundary; current SidecarStream pass does not stop mid-read.
Do not manually erase this marker. After current read and genuine save/ack/no-child boundary, existing ACTION=resume archives it. Greg's authorization to continue persists.
Before resuming, resolve latest corrected source and deal with the remaining durable reuse gaps below so you do not launch another avoidable161GB traversal.
Use existing queue operation, never a replacement owner:
 CODE_ROOT=<verified current staged checkout>
 MARKETS_SHA=<that checkout's HEAD>
 FRANKIE_ROOT_DIGEST=off
 FRANKIE_CLASSROOM_CPUS=all
 FRANKIE_EVIDENCE_ENCODING=fast
 ACTION=resume SCOPE=e2e-20231018-a2:20231018 RUN=e2e-20231018-a2 DAY=20231018
 sh deploy/aws/box/frankie_box_frankie_queue.sh
Verify actual Python executable SCRIPT paths, not just --code-root args, after resuming. Native checkpoints decide data reuse; code fields are recorded, not scientific identity gates.

## Implemented, published and staged: focused combined measurement

Commit: 1dedd031c1b13c047080c2f7529ef1b155b6d616
Message: Fold teacher findings and second-set reading into one traversal [skip ci]
Parent: 3796a85b52ab12a5d856539a8936a1a0aa8fcb6c
Tree: cd9b10a59d97fae505baf94763715958519352c6
Only changed files:
 deploy/aws/box/frankie_box_teacher_rows.py
 deploy/aws/box/frankie_box_teacher_findings.py

Current AWS checkout:
 /opt/frankie-box/code/1dedd031c1b13c047080c2f7529ef1b155b6d616-push-20261014T074343246813405Z/markets
Existing push-code staging verified4181 files in8.11 seconds.
Its staging receipt is in the parent directory. Both live workers remain85da915.

What changed:
- Existing SidecarStream findings loop feeds _SidecarReading accumulator: identical roles/counts/missing ordinal ranges/plane reference counts/book statuses during that same complete decode.
- Findings and second-set reading use the SAME existing second-set-reading.lock.
- Cold reading-first requests obtain findings+measurement together; findings-first publishes reusable measurement.
- New shared-products/second-set-sidecar-reading.json binds exact sidecar file identity. Reuse also recognizes the sidecar part of the OLD full shared product.
- Reference availability, receipt pin comparisons, late lists, state split and account parts refresh independently. Existing full all-dependency product identity remains intact.
- Changed sidecar bytes/identity invalidate; partial/truncated scans never publish complete sidecar cache.
- Original output schemas/types/order/hash formula remain unchanged.

Verification:
Scratch-only bounded fixture /workspace/scratch/f0c5d005edc7/fold-check/check.py (not repo-committed, may not survive/account-share).
Compared original and changed exact c15 evidence_bytes. All99 plane entries, missing roles/ranges, clocks/book states, concurrent readers, receipt/list/reference availability changes, sidecar modification, truncated source covered.
Findings-first and reading-first/concurrent each use ONE sidecar traversal for those two outputs; metadata/list/receipt refresh uses zero extra scans. py_compile and git diff --check passed.
Actual deployed isolated check on this day: original complete reading == new refreshed reading by evidence_bytes; SidecarStream.__iter__ replaced with failure to prove zero scans; all771,787 rows retained, result1.311271022 seconds (07:45 UTC).
This proves measurement reuse, NOT elimination of every downstream data read.

Bundle:
 S3 bucket frankie-granite42-568968024170-us-east-1
 key readiness/20260923/code-push/1dedd031/06bedc013ad58fd7b2a332f978b56937b2794666275144a8546816627e767e81.pack
 bytes110695, SHA25606bedc013ad58fd7b2a332f978b56937b2794666275144a8546816627e767e81
No credentials/presigned URLs belong in handoff.

## Remaining durable/shared reuse: NOT implemented

Existing durable source module is deploy/aws/box/frankie_box_teacher_products.py:
- RecordWriter / RecordStore: independent hash-bound pickle records, uint64 offsets, immutable manifest last, saved partial continuation.
- JoinedRecords / publish_joined / load_joined: complete source-bound parts.
- ensure_teacher_key: shared exact typed key/ledgers and lookup.
This is real existing code; reuse it rather than invent a table framework.
Newest teacher producer uses teacher-second-set.json plus teacher-second-set-blocks. THIS retained day predates that storage route.

Actual AWS inventory at07:57:12 UTC:
 /opt/frankie-box/work/experiment-teacher-rows/20231018/
 teacher-second-set.pkl =52,688,476,687 bytes, old retained publication.
 teacher-second-set.pkl.ARCHIVED.README.txt exists.
 teacher-findings.json =99,657,421 bytes.
 teacher-second-set-read.boss.json =31,887 bytes.
 shared-products has ONLY second-set-reading.json (37,067 bytes) and its lock.
 NO teacher-second-set.json or teacher-second-set-blocks directory appeared in top-level inventory.
The complete shared-reading product is a summary, not a row table. It cannot alone supply all row content to later consumers.

Inspect concrete remaining consumers in existing teacher_rows:
- second_set_lesson: SidecarStream over EVERY row, aligns snapshot (cursor,target_hash), writes WHOLE package.second_set.jsonl, records missingness/clocks/planes, resolves anchor planes. Whole-day phase second_set not yet saved.
- second_set_at_cutoff: scans whole SidecarStream when its exact cutoff product missing; exchange/Jev can share existing cutoff cache.
- second_set_field and second_set_leaf_ledgers: use SidecarStream; multi-leaf path already folds named leaves/cutoff together.
- scientific/BOSS/teacher-seat readings share second_set_reading after the published fix.
- Brain stage_source_witness and boundary hashes have existing file-claim reuse; check actual no-repeat path, never weaken source identity.

Reference map:
 research/kalshi/frankie_boss/HUB_CALC_ORDER_MAP_20261009.md, section D4 lists the repeated second-set readers; C8/X5/J2 list lesson/cutoff/Jev paths.
 deploy/aws/box/frankie_box_experiment_teacher.py:
 _sidecar_document/_sidecar_line (1172/1183), _write_rows_sidecar (1188), _BlockFeed._lines (1365), final pin (~1560).
Current producer writes full adapter-row RecordStores but sidecar is entity/snapshot rows with original per-block locks. Reconstructing or migrating old table requires EXACT evidence equivalence, not a plausible projection.
Block sidecar locks are each block's teacher_as_of; do NOT replace with whole-day max lock.
JSON source values use lists; typed pickle records may have tuples/other representations. Preserve original c15 types/order and original lesson JSON bytes.
Do not declare "read once across every step" based only on cached counts. Do not merely move the same full scan to a different file and call it eliminated.
No broader reuse code draft/migration is in the working tree. Source inspection only, no full-table conversion launched.

## Existing Frankie cycle and full remaining workflow

Claude's existing route is already constructed; do not build a substitute:
 queue._classroom_and_search -> Run.classroom (reuses47 block lessons) beside independent data/search.
 Whole-day classroom_v2 restores package, runs learner inputs/readings, guided/shared market evidence, exhaustion, second-set lesson, answers, external section, assembly/grading/novelty, corrections/acknowledgements, completion, brain_publication <day>-cycle-00.
 class_day then batch_lessons when applicable, frankie_lessons (tests new findings), exchange, jev, voice/meeting, school, reports.
 ROOT owner finish waits actual class completion, Jev readback/current reports, drains successor/native recovery work, then closes.
Remaining means finish ALL of these; queue running, ROOT state done, or a reports file does not prove completion.
Teacher/ROOT/all47 block lessons complete.771,787 rows;1,960 block hypotheses across151 pair IDs; all hypotheses remain unpromoted.

Saved package:
 /opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1/work/classroom/
 saved-phases/bc4a71180870f7945155fbb02f4b0a2e3faa2a62d6d31b7039013055ed19869a.pkl
 bytes2,605,095,972.
 phase-state.pkl and phase-progress.json preserved.
phase timings uses setdefault on restore; an old timings.package.restored=false can remain even after actual restoration. Verify actual saved-file load and next genuine phase, not that flag alone.

## Mounts, local refs and safe stop

Fast volume vol-0fbf7bc0991bc8e39 remains physically attached MAIN /dev/sdg and mounted /mnt/frankie-fast-output. NEVER detach while day depends on output.
Active classroom path is bind mount from fast day-a2-20231018/classroom; completed blocks bind from original classroom.retained-20261014. Exact identities/fstab and cleanup receipts in SESSION15.
Original MAIN root vol-0d36715924f03b86c and archive vol-004b68c077be09cc9 remain attached.400GB archive swap active. Preserve everything; no reboot of live calculation.
No further cleanup/delete was performed here.

Old local checkout /workspace/scratch/86bd7a42d29b/Markets may be inaccessible from new business account.
Deferred LOCAL branches remain untouched/unintegrated/unpublished:
 codex/deferred-ingest-root-20261014 @22d32aba3abe795d1c25c05c3500e77ecf84645a
 codex/deferred-gauge-checkpoint-20261014 @5f34cf7b9f682da9cd7211c725115923e2f18c26
A new local backup codex/local-single-pass-20261014 preserves equivalent local commit3e94409faab68be0ab10f87bdd09b49818aa0afb. Published1dedd03 has identical tree; local branch was aligned with published commit before transfer.
Do not integrate/discard either deferred branch.

Stop MAIN only after exact owner root.state=done AND finish.state=finished, hub_runtime.owner_finished=true, no unfinished child/revival/native work and current reports/late corrections complete. Set KeepRunning=false, StopInstances (never terminate), preserve disks/snapshots/S3.

## Completion watch and tool access

Personal-account hourly completion watch:
 ID6acf293a18308191bb302f54e0703a66, title Frankie Day Completion.
PAUSED at08:01:36 UTC for cross-account handoff to avoid racing the new chat; no future next_run_time. Last_run_time07:58:58.398963 UTC. Pausing does not prove an already-started invocation ended; read live before mutations.
This business-account chat may not be able to access that automation. Do not assume it will resume or stop the instance. Continuing agent owns attendance/recovery and safe stop.

AWS connected tools work via run_script / call_boto3 SSM SendCommand and GetCommandInvocation. Verify APIs succeeded. Use short read-only checks and compact output; do not print full queue owner history.
Use existing systemd-run for durable long-running operations, not a new runner; SSM session timeout is not a scientific job lifetime.
GitHub connector create_blob/tree/commit/update_ref or contents API works. Local git push lacked username credentials.
At08:00 UTC local exec-server disconnected/recovery timed out. This is a session transport failure, not evidence AWS worker stopped. GitHub/AWS connectors still work.

Next chat should read live AWS state, let this active pass finish its save boundary, complete remaining durable reuse/source checks, stage corrected code and resume SAME owner through ALL existing stages. No further blanket completion/read-elimination claims without actual consumer evidence.
