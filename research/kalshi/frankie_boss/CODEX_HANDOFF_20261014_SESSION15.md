# Session 15: updated gauge passed; remaining saved day authorized

Repository `DavisAI1974/Markets`, branch `ccr-d2f8f826-iefeah-frankie`.
Fetch CURRENT HEAD and preserve newer work. Runtime fix published and deployed:
`02d61cfe778fceb687d77db45eda1a134f890bcd`.

Greg explicitly authorized finishing the remaining one-day workflow, cleanup
first, faster disks, and stopping unused compute. His later “Proceed” includes
continuing after the classroom wrapper's protective save. SESSION14's earlier
no-start/no-resume gate is historical. No 30-day work, replacement runners,
extra test framework or deferred draft integration is authorized here.

## Latest verified runtime, 2026-10-14 07:10 UTC

AWS account is Greg Davis's `568968024170`, region `us-east-1`.
Main `i-035994afa8bdf66a5` is running, r7i.16xlarge, 64 CPUs.
Both other EC2 instances are stopped; all-region inventory found no additional
running EC2. Preserve EBS, snapshots, S3 and the retained Lightsail services.

Exact run/day: `e2e-20231018-a2 / 20231018`.
Exact attempt: `e2e-20231018-a2-20231018-a1`.
Exact held CPU booking:
`day-run-20231018-day_slot_repoint-1791535148-1706`, CPUs 0–63.
Teacher, ROOT and all 47 block lessons were already complete; do not redo them.
Whole-day classroom was saved after `package`, not finished. Search/lessons,
exchange, Jev, meeting, school and reports remain the existing remaining route.

Owner worker PID 3122 runs the verified 02d61cf checkout. It is making one
complete shared second-set reading and has advanced through 110,804,434,944
bytes of the 161,126,241,394-byte sidecar. Its shared-product lock prevents a
second consumer from duplicating that pass. Do not interrupt this progressing
read. The new shared reading product did not exist at startup.

The classroom wrapper initially launched with an older queue entrypoint despite
new `--code-root` arguments. It was waiting on the second-set lock. Switching
that wrapper triggered the existing cooperative save path:
`parallel classroom/search interrupted`, marker created 07:00:59 UTC. A new
02d61cf class worker correctly acknowledged that standing marker and exited
saved at 07:01:32 UTC. This is an operational protective save, not a new request
from Greg to stop the day. The owner is still finishing its retained reading.
Wait for its save boundary, then use existing ACTION=resume on the SAME owner;
do not kill its reading, erase the marker manually or invent a new attempt.
The original saved `package` has not yet been observed restoring in this run.

## Gauge and actual block findings

Read `BLOCK1_GAUGE_RESULT_20261014.md` and its three raw evidence files.
Existing block-1 gauge, updated source 88d1e7b, full classroom/external,
shadow encoding: 116.626 s wall, 90.850 s classroom session versus previously
recorded 159.0 s. 173 shadow comparisons, zero mismatches. Candidate-only gauge
time was not measured. The second set and original referenced planes were kept.

Original 47 completed day block sessions cover all 771,787 rows. All are TEACH,
complete, with consistent answers, main and external teacher completion, and
zero unresolved grading disagreements. The preserved novel-finding files hold
1,960 block-scoped hypothesis instances across 151 distinct pair IDs, 15–61 per
block. Do not collapse those instances into 151 interchangeable observations.
All 1,960 novelty investigations record
`PARTIALLY_TESTABLE_NOVEL_HYPOTHESIS`, `RETAIN_AS_NOVEL_HYPOTHESIS`, and
`independent_discovery_eligible=false`. These are differences between endpoint
direction and consecutive-step co-movement, not completed independent discoveries.
Example block 1: front-order age and absorption share ended in the same
direction, while their consecutive both-PRESENT steps moved together 21 times
and oppositely 74 times. Broader mathematics/source/causal scientific checks
remain required; no rarity discount or minimum-occurrence gate is introduced.

Findings were inspected with existing `block_load` to resolve saved block-store
references; no raw-reference wrapper was mistaken for an investigation result.

## Teacher findings startup fix and preserved replay evidence

Read `TEACHER_FINDINGS_MOVE_REUSE_20261014.md`. Moving the original sidecar changed
mtime, so the old cache rejected complete findings and both startup consumers
repeated the 161 GB findings scan. Fix 02d61cf reuses only a complete-source claim
matching the cached SHA/bytes and current resolved file identity/tail, and locks
account publication. Missing/invalid claims take the original computation path.

The old move's successful full write-stream hash was recovered from its clean
receipt, matched to the original findings SHA and actual file, and recorded with
the existing claim helper in teacher rows and beside the archived file. Cached
findings and original source metadata were not rewritten. Real deployed
`load_or_compute` reused all 771,787 rows in 2.251 s; a failing replacement for
compute in that isolated check confirmed no scan was entered.

Full retained sidecar SHA:
`83081ea3ed71ecfc63c6c6d0012af37fa8c86aeb7f2e0bafc739509c4e47d985`.
Completed original teacher publication was copied aside under fast disk
`day-a2-20231018/teacher-publication-before-replay/`.
Only the verified redundant findings replays were cancelled cooperatively.
Their partial spool remains, with a 216,265-byte extra copy at
`/opt/frankie-box/day-resume-20261014/teacher-reconciliation-duplicate-replay-1791960738.partial.jsonl`.
Their stack traces and save/resume logs remain in that same receipt directory.

## Disks, mount identities and cleanup

Main original root `vol-0d36715924f03b86c` and archive
`vol-004b68c077be09cc9` remain on main. Their previous performance reductions
are still optimizing; AWS rejects another modification during that state.
Do not repeatedly retry or wait for those disks as a prerequisite.

Fast disk `vol-0fbf7bc0991bc8e39` was raised to 16,000 IOPS / 1,250 MB/s and the
modification completed. It now belongs physically to MAIN `/dev/sdg`, mounted
at `/mnt/frankie-fast-output`. Second instance `i-0d17573dbce871520` is stopped
with its original root detached. Its original data is preserved on this disk.
NEVER detach or return this disk while the remaining day depends on its output.

The two root disks have duplicate filesystem UUID/PARTUUID. The fast mount's
fstab entry deliberately uses exact serial identity:
`/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol0fbf7bc0991bc8e39-part1`.
Do not replace this with UUID-based mounting. Avoid rebooting a live calculation.

Original classroom path remains:
`/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1/work/classroom`.
It is a bind mount of fast disk `day-a2-20231018/classroom`. All non-block saved
state was copied losslessly with rsync and a dry comparison. Original directory
is retained alongside as `classroom.retained-20261014`. Its complete blocks are
bound into the active classroom's `blocks` directory, retaining original inodes.
No 229 GB block-data recopy or input truncation was used. fstab holds both binds;
backup and receipt: `/opt/frankie-box/day-resume-20261014/`.

Saved package is retained at
`saved-phases/bc4a71180870f7945155fbb02f4b0a2e3faa2a62d6d31b7039013055ed19869a.pkl`,
2,605,095,972 bytes. `phase-state.pkl` and `phase-progress.json` remain.
400 GB archive swap is active with priority -1.

Existing guarded code cleanup removed only 30 unused checkouts and 18 transfer
caches, freeing 38,373,535,744 actual bytes. Receipt:
`/opt/frankie-box/receipts/code-cleanup-20261014T061639Z.json`.
The old completed gauge was compressed by the existing mover to fast disk
`archives/gauge-b8ec5d3d-20261009T161259Z.tar.zst`, 25,034,377 bytes, SHA
`cb6d2a145f626f4c4431dd4289c26b1ebdafabc8c1e5747d9ed4ad0f4a2da14c`.
Its original path has a restore README and archive symlink. About 40 GB was
freed in total. Active teacher sources, 47 blocks, brain and partial science
were preserved. Main root has about 779 GB free; fast disk about 1.9 TB free.

Latest gauge full directory is now reachable on MAIN at
`/mnt/frankie-fast-output/opt/frankie-box/gauge-block1/88d1e7b-20261014T055854Z/88d1e7b8-20261014T055855Z`.

## Previous mystery save resolved

The old day save request was created October 10 at 23:54:14 UTC by
`teacher boundary: validated; stop after validation, clean on save (Greg 2026-10-08)`.
Classroom completed package, then honored it at October 11 00:09:20 UTC.
Teacher clean had completed but its trigger was not published. Existing boundary
logic already reuses a saved unfinished trigger instead of recleaning data.
This was not an unidentified external stop; retain its original receipts.

## Next actions and safe close

Keep the progressing shared second-set read attended. After the owner saves on
the wrapper-change marker, resume the exact retained owner with the existing
queue script, current checkout, `FRANKIE_ROOT_DIGEST=off`,
`FRANKIE_CLASSROOM_CPUS=all`, `FRANKIE_EVIDENCE_ENCODING=fast`.
Confirm both actual Python entrypoints name current checkout, not only arguments.
Confirm package restores and subsequent genuine classroom phases progress.
Then watch all remaining existing workflow stages; no claim of whole-day
completion follows from a wrapper launch, reports file or ROOT state `done` alone.

Stop main promptly only after exact owner ROOT state `done`, finish `finished`,
`hub_runtime.owner_finished` true and no unfinished child/revival/native work.
Set KeepRunning=false, StopInstances, retain all disks/snapshots/data. Preserve
partial state on any failure. An external completion watch is active as backup;
it must be updated with this protective-save continuation and paused after safe
completion. The hub doctor repairs dead work, but does not itself stop EC2.

Local-only drafts are unchanged and unintegrated:
`codex/deferred-ingest-root-20261014` at `22d32aba3abe795d1c25c05c3500e77ecf84645a`;
`codex/deferred-gauge-checkpoint-20261014` at `5f34cf7b9f682da9cd7211c725115923e2f18c26`.
Do not publish, discard or integrate them. SESSION14 holds their exact notes.
