# Codex handoff, 2026-10-21 ~13:50Z: finish the group 2050 recovery and the Search `.building` probe fix on the box

Claude's cloud session could read every box over SSM but the harness refused every write to the box, so the
work below is handed to Codex, which runs on the box. Read `ASSEMBLY_GROUP2050_NFS_FINDINGS_20261021.md` first
(evidence for every statement here), then this file top to bottom. The patch and its check are beside it:
`ASSEMBLY_GROUP2050_CATALOG_RESTAMP_20261021.patch`, `assembly_group2050_catalog_check_20261021.py`.
They are on GitHub branch `ccr-c0271308-0ywvss` (commit 0ecf3d6); the box branch does not have them yet.

## State as of 13:45Z (verify again before acting; nothing below was changed by Claude)

- Account 568968024170, us-east-1. main i-035994afa8bdf66a5, helper i-0d17573dbce871520, third i-031eeb577ad72b064:
  all RUNNING, all SSM Online. Run e2e-20231018-a2 / 20231018, owner e2e-20231018-a2-20231018-a1.
- Box source: /opt/frankie-box/work/source-session63-assembly, branch codex/search-assembly-20261021, HEAD d03035a, clean.
  Catalog module there: deploy/aws/box/frankie_box_search_catalog.py, 589 lines,
  sha256 6afe56c1fd45086954e556ef83307190ff124fd4d8f2d518ecbc40fba6c4e603 (the patch is against exactly this).
- MAIN SEARCH IS NOT RUNNING. The class scope is PARKED (`/opt/frankie-box/work/frankie-queue/parked/class-b2c953a8f1a004d6.json`,
  worker_end stopped_at_failed, code_root 6feaf9c). Only `frankie-queue-parked-watch-1792587678` (6feaf9c) runs on main.
  Root worker idle, CPUs released, booking day-run-20231018-day_slot_finish-1792587558-55984 released. Helper: no frankie
  process. Third: frankie-search-calculations.service failed (exit 1, 12:24:02Z) on 9d0c449.
- Search volume (main /dev/nvme2n1p1, exported as cycle-00): 155 GB free at 13:14Z against the session66 disk floor of
  100 GB. 19 unsealed `.building` files of 1.3 to 3.3 GB from the 12:52-13:00 runs sit in factored-v2/groups; retain them
  (native `ready()` keeps an unsealed file for recovery). 50 `*.building-journal` files there, none hot (zero header).
- Group 2050: bytes verified (sha256 matches seal and receipt), only mtime/ctime restamped by nfsd at 12:24:02.225Z.
  Receipt stat [3021979648, 1792585377505033483]; live stat [3021979648, 1792585442225004446]. Leave the file, the
  seal and the receipt alone; the patch handles it at the next open.
- Third ledger /opt/frankie-assembly/e2e-20231018-a2-20231018-a1/assembly.sqlite: 4105 groups, 7760 job rows, 111
  streams; 2050 absent from `groups`. assembly-v1/coordinator.lock and workers.lock: 0-byte, no holder. Local generation
  marker `session66` (12:24:02) plus three `session66.native-assembly-resumed-*` markers present. Do not clear the native
  queue-owner marker; use Q._archive_marker only on the exact LOCAL marker after exclusive lifecycle proof.

## Job 1 (do now, source only): land the Catalog restamp fix on the box branch

1. `cd /opt/frankie-box/work/source-session63-assembly && git status && git log --oneline -3` ; preserve anything newer than d03035a.
2. Confirm `sha256sum deploy/aws/box/frankie_box_search_catalog.py` is 6afe56c1...; if it moved, re-read the patch hunks
   (three: imports `socket`/`time`; the stat-mismatch line calls `self._verify_restamped(stat)`; new method before `db`).
3. Get the two files onto the box (fetch branch ccr-c0271308-0ywvss, or paste them), then
   `git apply --check ASSEMBLY_GROUP2050_CATALOG_RESTAMP_20261021.patch && git apply ASSEMBLY_GROUP2050_CATALOG_RESTAMP_20261021.patch`.
4. `/opt/frankie-box/venv/bin/python -m py_compile deploy/aws/box/frankie_box_search_catalog.py && git diff --check`.
5. Run the check with the box runtime, outside the source tree:
   `/opt/frankie-box/venv/bin/python /path/to/assembly_group2050_catalog_check_20261021.py $PWD/deploy/aws/box`
   Expect check1..check5 ok and ALL CHECKS PASSED; it builds one tiny catalog in a temp dir and removes it. Keep only the
   printed lines as the receipt (a small JSON under /opt/frankie-box/work/handoffs is fine); delete nothing else.
6. Commit on codex/search-assembly-20261021 with [skip ci]; explicit `git add` of the module and the docs below only.
   No pack, no stage, no restart in this job: a staging receipt IS the next step's code on this queue
   (frankie_box_frankie_queue.py ~line 901, newest_staged_checkout), so staging equals activation.

What the fix does and does not do: on a stat mismatch at equal size, `Catalog.__init__` computes the full sha256; equal to
the sealed receipt's sha256 (and stat unchanged across the hash) re-mints `stat` through the native `_atomic_json`,
retaining the old stat under `stat_superseded` (time, host, why). Different size or digest still raises
`immutable search catalog changed; retained`. The sqlite open stays `mode=ro&immutable=1`; the `sources` pins are untouched.
It is not a stat refresh to silence anything and not a Catalog bypass: the seal's content address decides.

## Job 2 (needs Greg's design call first; prepare the patch, do not stage): the `.building` probe over NFS

Why Search dies: `frankie_box_search_aliases.pending_is_compact` (line ~39-50) opens `<group>.sqlite.building` with
`sqlite3.connect(uri + '?mode=rw')` to let SQLite roll back a hot journal before `PRAGMA table_info(inputs)`. Called from
`frankie_box_search_factored.dispatch_group_batch` (line ~507) and `_prepare_groups` (line ~290). From the helper this is a
writable open, over NFSv4.1 (rw, local_lock=none), of files it did not finish writing or that another host owns. Three
runs today died at helper batch index 369 with `sqlite3.OperationalError: disk I/O error` inside that PRAGMA
(tickets remote-cells/8bc58d68..., 32ed610c..., f9faf9a9...; status.json `OperationalError: disk I/O error`), and the
coordinator turns one worker's error into `search helper exited without result 369; retained, no local retry`, exit 1
before the native save boundary, class line failed, re-kick, same death. Measured: the 50 leftover journals have a zero
8-byte header (not hot); a `mode=ro&immutable=1` probe from the helper reads every one (5121, 2104, 527 compact with
`ordinal`; 5130, 5146 not); the helper's cycle-00 mountstats carry 45 WRITE and 41 REMOVE errors. The rw open makes SQLite
unlink a stale non-hot journal, which is the write that fails over NFS.

Put this to Greg, with the recommendation:

- Option A (recommended, minimal): probe read-only. `mode=ro` (not immutable) still honours locks and reports a genuinely
  hot journal as a readonly-recovery OperationalError instead of rolling it back. Treat that error as "this group's
  writer has to roll it back", i.e. in `dispatch_group_batch` leave `results[position] = None` for that job (the caller
  already accepts None per job, see `_stop_requested`), log the path, and let the phase's own `completed != len(group_jobs)`
  check report it if it never clears. Rollback of a `.building` then happens only where the Writer opens it rw
  (`Writer.__init__`, catalog.py ~line 248), which is the host that builds it. Same change at `_prepare_groups` line 290.
- Measure before deciding whether A is enough: on the helper, copy ONE stale pair (e.g. 000000005121.sqlite.building and
  its -journal) into a scratch directory on the same NFS mount, open it the way Writer does (`sqlite3.connect(path)`, rw),
  under `strace -f -e trace=unlink,unlinkat,write,fsync -o /dev/shm/probe.strace`, and read the errno. If the owner host's
  own rw open also fails over NFS, Option A moves the failure, it does not remove it, and the group build itself must leave
  NFS (helper builds on local disk and transfers sealed files, as `frankie_box_search_assembly` already does with
  `.transfer`/`.building`; the helper root has 35 GB free, so that needs a volume). Remove the scratch copies after.
- Do not delete the 50 journals by hand and do not touch the 19 unsealed `.building` files: `ready()` retains an unsealed
  catalog for recovery and the owner's Writer is the native path that finishes or restarts it.
- Mount-option changes on the helper or third are infrastructure changes: Greg's word only.

## Job 3 (only on Greg's explicit go): restart at the genuine boundary

Order, once Job 1 (and Job 2 if Greg takes it) are committed:

1. Stage natively the way `assembly-integrated-20261021-handoff.md` describes (import_pack of the verified compact pack,
   fetch the new commit, create_pack/stage). Record the pack sha and the 4361-file guard result. From that moment the
   parked class scope re-kicks on this checkout at its next wake (`frankie-queue-parked-watch` is running) or on
   ACTION=kick/resume; do not kick before Job 2 is decided, or Search dies again at batch 369 within ~90 s.
2. Recheck before the kick: free space on cycle-00 against the 100 GB floor (155 GB at 13:14Z, and the re-run will write
   more `.building` data), owner e2e-20231018-a2-20231018-a1 unchanged in `frankie-queue/root.json`, no booking held.
3. Third lane: it needs a new calculation config and unit for the new commit (the failed unit's ExecStart hard-codes the
   9d0c449 code root and /opt/frankie-assembly/config-session66.json; the inactive 6feaf9c config is
   /opt/frankie-box/work/handoffs/assembly-integrated-20261021-config-INACTIVE.json, prepare_nominations=true,
   early_fitting absent; keep early_fitting absent). Prove the EX leases are free (coordinator.lock, workers.lock: the
   nonblocking EX probes from the previous chat), prove none of the old worker PIDs exist, then start. On first pass its
   `_admit` reaches 2050 through the helper stream ip-172-31-46-110-48454.jsonl at durable position 216; with Job 1 the
   `Catalog(path)` open hashes the 3 GB file once over NFS (expect ~1 min), re-mints the receipt, and inserts the group
   with the unchanged sha256 pin. Watch the unit for that line; a second `immutable search catalog changed` there means
   the patch is not on the code the unit runs.
4. Main/helper preparation and the third's calculations share the owner/booking; never start the old 9d0c449 release into
   the same group, and never restart a healthy process.

## Job 4: records

- Add the top bullet to the box AGENTS.md (the box copy is newer than GitHub's): group 2050 intact, cause nfsd
  CB_GETATTR restamp on a helper write delegation, fix committed <sha>; Search parked since 13:01Z on the `.building`
  rw probe over NFS, decision pending; nothing restarted.
- Copy `ASSEMBLY_GROUP2050_NFS_FINDINGS_20261021.md` into research/kalshi/frankie_boss on the box branch and a short
  pointer into /opt/frankie-box/work/handoffs/assembly-group2050-findings-20261021.md. Update
  assembly-next-chat-failure-20261021.json with `actual_sha256_recomputed: true`, the digest, and `cause`.
- Standing rules still apply: preserve all 30-day ingestion copies, saved progress, answer walls, exact owner/bookings;
  no BuildMap, no public push beyond [skip ci] commits on the box branch, no additional days, no early_fitting, no
  healthy-process restart, no edits to the downstream window's checkout
  /opt/frankie-box/work/source-indexed-consumers-20261021.
