# Assembly line, 2026-10-21 13:30Z: group 2050 is intact; two NFS-side failures, both with cause

Written from a Claude cloud session over SSM, read-only on every box. Nothing on main, helper or third was
started, stopped, edited, re-minted or cleared. The box source tree codex/search-assembly-20261021 is at
d03035a, clean. A one-file source fix for the group 2050 class of failure is attached as a patch
(`ASSEMBLY_GROUP2050_CATALOG_RESTAMP_20261021.patch`) with its disposable check
(`assembly_group2050_catalog_check_20261021.py`); the harness refused to write it onto the box, so it is NOT
applied, NOT committed, NOT staged.

## 1. Group 2050: bytes intact, metadata restamped by nfsd

- Recomputed on main, read-only, 9.5 s: `sha256sum` of
  `discovery.partial/recovery/factored-v2/groups/000000002050.sqlite` =
  `012469590b1c648cc8a1b4d3ad2e79ac510d48ff6596b2e1ac54cc4a2a767c45`, identical to the sealed receipt and the
  seal. Size 3021979648 on disk, in the receipt and in the seal. The stat after hashing was unchanged.
- Receipt stat mtime 1792585377.505033483 = 12:22:57.505 UTC (the helper's last WRITE at seal time). Actual
  mtime 1792585442.225004446 = 12:24:02.225 UTC, and ctime is identical to the nanosecond. atime only moves
  with reads. A write or truncate would have changed bytes or size; neither did.
- Sweep of all 4294 sealed group receipts against live stats: exactly one mismatch, 2050.
- Who sealed it: the ready stream is `assembly-v1/ready/ip-172-31-46-110-48454.jsonl`, i.e. helper worker
  pid 48454, writing the group over the helper's rw NFSv4.1 mount of cycle-00
  (`vers=4.1, acregmin=1, acregmax=1, local_lock=none`). The helper's ready line for 2050 landed at 12:23:59;
  the third admitted it at 12:24:02 and its `Catalog()` stat is the first GETATTR from another client.
- Mechanism (Linux fs/nfsd/nfs4state.c, read from the kernel tree): `nfsd4_deleg_getattr_conflict` runs when
  a GETATTR from a different client hits a file under a write delegation. nfsd sends CB_GETATTR to the holder;
  if the change attribute differs from grant time or the size differs, `cb_getattr_update_times` runs. For a
  holder whose delegation is a plain OPEN_DELEGATE_WRITE (no delegated timestamps; `deleg_attrs_deleg` is
  false, which is every NFSv4.1 mount) it sets `ATTR_MTIME | ATTR_CTIME` with no value, so the server stamps
  both with its current time. That is mtime == ctime == the instant of the third's stat, with no write. The
  helper client is "Linux NFSv4.1 ip-172-31-46-110" in `/proc/fs/nfsd/clients/4/info`; the helper worker
  48454 was alive until 12:58 and still held the delegation 65 s after the seal. The helper's mountstats show
  42.5M DELEGRETURNs on that mount, which is why the other 4293 groups were already returned before anyone
  else stat'd them; 2050 lost that race by seconds.
- So the third's `ValueError('immutable search catalog changed; retained')` is a true statement about the
  stat gate and a false alarm about the content. The catalog is content-addressed (receipt and seal pin the
  sha256); the stat is only the cheap gate in front of it. It is not NFS attribute caching: the server's own
  inode was restamped.

## 2. Main Search is NOT running, and its cause is a second NFS problem, not group 2050

The handoff's "last verified running 12:29Z" is stale. Timeline from the native queue (`frankie-queue`
class/root events, the run log `experiment/e2e-20231018-a2/logs/20231018-search.log`, the helper tickets):

- 12:58:30 helper ticket 32ed610c (e9944a6): `sqlite3.OperationalError: disk I/O error` in
  `frankie_box_search_aliases.pending_is_compact` -> `PRAGMA table_info(inputs)` on a `.building` file opened
  with `mode=rw`, called from `frankie_box_search_factored.dispatch_group_batch` (line 507). Main's
  `remote.ordered_cells` then raised `search helper exited without result 369; retained, no local retry`, the
  compute-only search exited 1 before its native save boundary, the class line failed at 12:59:18
  (`booking ... day_slot_search_disk_recovery-1792569879-50861 is not in the ledger`).
- 12:59:47 the ROOT line re-kicked the parked scope ("retry of a FAILED finish on a new booking") on the
  NEWEST STAGED CHECKOUT, which is our 6feaf9c candidate (`newest_staged_checkout`, Greg 2026-10-09: a running
  day's next step uses the newest code). "Staged, not active" is therefore not a state this queue has: a
  staging receipt is the next step's code. Nobody started it by hand.
- 13:00:29 helper ticket f9faf9a9 (6feaf9c): the identical traceback, batch index 369 again. 13:01:13 the
  search failed the same way, 13:01:18 the class line failed, the scope PARKED (`parked/class-...json`,
  `worker_end: stopped_at_failed`), `frankie-queue-parked-watch-1792587678` (6feaf9c) is the only frankie
  process on main, root worker idle, CPUs released, the session66 space watch ended at 13:01:29
  (`guard_ended, finish: failed`). The helper has no frankie process; the third is failed as reported.
- The same batch index 369 also killed the 08:05 run at 08:34:05 (ticket 8bc58d68, release 8a6b40ad), and
  index 257 killed the 06:18 and 07:51 runs. Each time the whole search dies on the first error of one helper
  worker.
- Evidence on the probed files: at both 12:58:29-31 and 13:00:29 the helper's batch created tiny `.building`
  files for selections 5119-5183 and the pool died within the second, leaving 50 `*.building-journal` files
  on NFS. The journals are NOT hot (8-byte header all zero) and a read-only immutable probe from the helper
  reads every one of them (`PRAGMA table_info` returns the columns; 5121, 2104, 527 are compact with
  `ordinal`, 5130 and 5146 are not). The production probe opens `mode=rw`, which makes SQLite try to remove a
  stale non-hot journal; the helper's mountstats show 45 WRITE and 41 REMOVE errors on that mount. The rw
  probe exists so an interrupted same-host writer's hot journal can be rolled back before the schema is read;
  over NFS from the other host it is a write to a file it does not own.
- Free space on the search volume fell from 425 GB (12:29) to 155 GB (13:14): 19 `.building` files of 1.3 to
  3.3 GB were written 12:52-13:00 by the two runs and are retained unsealed, plus the sealed 349, 2098, 2150,
  2100, 371. The session66 disk floor is 100 GB; it was not reached.

I did not touch the journals, the `.building` files, the parked scope, the bookings or any mount.

## 3. Third lane and leases, rechecked 13:14-13:20Z

- `frankie-search-calculations.service` failed, exit 1, 12:24:02.976 UTC, 38.3 GB peak; no frankie process
  on the third. Ledger `/opt/frankie-assembly/e2e-20231018-a2-20231018-a1/assembly.sqlite`: 4105 groups all
  scheduled=0, 7760 job rows (7512 committed + 248 pending as the handoff counts them), 111 streams; group
  2050 is not in `groups`, so the first admission after the fix inserts it (`INSERT OR IGNORE`, pin = sha256,
  unchanged). `coordinator.lock` and `workers.lock` (assembly-v1) are 0-byte files from 09:23:59 with no
  holder. Local generation marker `session66` (12:24:02) and the three `session66.native-assembly-resumed-*`
  markers are present and untouched. The third's cycle-00 mount is rw NFSv4.2.
- Owner/booking: the class line's last booking `day-run-20231018-day_slot_finish-1792587558-55984` was
  released; the run entry is owned by `e2e-20231018-a2-20231018-a1` (unchanged). `frankie-queue/root.json`
  holds it; the next ACTION=resume/kick re-kicks on the newest staged checkout.

## 4. The fix for the group 2050 class (patch attached, not applied)

`deploy/aws/box/frankie_box_search_catalog.py`, `Catalog.__init__`: on a stat mismatch, instead of refusing
at once, call `_verify_restamped(stat)`: equal size required; full sha256 of the bytes must equal the sealed
receipt's sha256 and the stat must be unchanged across the hash; then the receipt's `stat` is re-minted
through the native `_atomic_json`, with the superseded stat retained under `stat_superseded` (time, host,
why). Any other outcome raises the same `immutable search catalog changed; retained`. A read-only mount keeps
the verified receipt in memory. The 'sources' pins and the sqlite open (`mode=ro&immutable=1`) are unchanged;
no scientific path is touched. Cost: one digest only when the stat gate fails (3 GB = ~10 s on main, longer
over NFS on the third). This is not a Catalog bypass and not a stat refresh to silence the error: it is the
seal's own content address deciding.

The attached check builds a tiny catalog with the native Writer/seal, then: untouched open leaves the
receipt alone; a utime restamp opens and re-mints with the old stat retained; a second open rewrites nothing;
one flipped byte at equal size is refused; a size change is refused. It runs in a temp dir and removes it.
It was NOT run on the box (write refused). It ran in the Claude cloud container against a byte-identical copy of
the box file (sha256 6afe56c1fd45086954e556ef83307190ff124fd4d8f2d518ecbc40fba6c4e603, 589 lines, fetched read-only):
all five checks pass with the patch, and the unpatched module fails check 2 with exactly
`immutable search catalog changed; retained`. Apply on the box with `git apply` in
/opt/frankie-box/work/source-session63-assembly, rerun the check there with the venv python, commit [skip ci].

With that fix in the next staged code, the third lane's `_admit` of 2050 passes on its own, and so would any
future helper-sealed group that loses the same race. Alternative without a code change: retain the stale
receipt under another name and let native `ready()` re-mint it from the seal (it digests the file and
writes `stat`); that is a hand edit of a saved artifact and leaves the race live, so I did not do it.

## 5. What needs Greg's call before anything starts

1. The `.building` probe over NFS (section 2) is why every search restart dies at batch 369 and why a
   re-kick on 6feaf9c failed within 85 s. It is in the preparation path shared with the production Search
   (`dispatch_group_batch` line 507 and `_prepare_groups` line 290 call `pending_is_compact`, which opens
   `mode=rw`). Minimal proposal, not written: probe the schema with `mode=ro` (no journal removal, no
   writes; SQLite reports a genuinely hot journal as a readonly-recovery error, which should defer that group
   to its writer host rather than kill the pool), and leave rollback of a `.building` to the host that writes
   it. The 50 stale journals then stop mattering. Deciding who owns recovery of a `.building` on NFS is a
   design call; I did not make it.
2. Restart order once both fixes are staged: the parked class scope re-kicks on the newest staged checkout
   by itself at the next wake (or ACTION=kick/resume); the third lane needs its unit started by hand on that
   same code, with `Q._archive_marker` only on the exact LOCAL generation marker after the exclusive
   lifecycle proof the handoff describes. No start was performed.
3. early_fitting stays absent; nothing in this session touched the fitting candidate or prepared.pkl.

## Evidence index (all read-only)

main `ssm` commands this session: stat/sha256 of 2050; receipt sweep (4294 checked, 1 mismatch);
`/proc/fs/nfsd/clients/{4,6,10}`; `/etc/exports`; `frankie-queue/{class,root}-events.jsonl`,
`class-kick.json`, `parked/`, `wake/`; `experiment/e2e-20231018-a2/logs/20231018-search.log`;
`remote-cells/{32ed610c...,f9faf9a9...,8bc58d68...}/{ssh.log,status.json,ticket.json}`; groups dir
`.building`/`-journal` listings by mtime. helper: `/proc/self/mountstats` (cycle-00 WRITE errors 45, REMOVE
errors 41, DELEGRETURN 42.5M), journal headers, immutable read-only probes. third: unit status, journal,
ledger schema and counts, locks, markers, config-session66.json. Kernel: torvalds/linux fs/nfsd/nfs4state.c
(`nfsd4_deleg_getattr_conflict`, `cb_getattr_update_times`) and fs/nfsd/state.h (`deleg_attrs_deleg`).
