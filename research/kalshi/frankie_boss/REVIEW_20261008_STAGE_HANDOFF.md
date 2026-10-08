# Review 2026-10-08: the session-6 stage handoff (validate -> save -> clean -> trigger)

Independent reviewer (read-only on the box and AWS; nothing ran there). Reviewed tree: branch `ccr-d2f8f826-iefeah-frankie`,
started on tip `1d80cd6` (stage_handoff 554 lines, root_move 422 lines) and finished on `b20374a` (stage_handoff 614
lines, root_move 743 lines: bind mount of the guarded directories, redundant native-segment archive, Glacier second copy,
box_in_use counting the clean unit, digest off on non-arm days), which landed while the review ran. Line numbers below
are `b20374a` unless marked. Every finding carries a toy reproduction or the exact line; nothing here is an impression.

## Verdict: BLOCKED as wired (two findings make the unattended run start a stage on failed data or halt silently);
## APPROVED WITH FIXES once findings 1, 2, 3 and 4 are applied (patch text below, each a few lines).

The sequence itself (validate once on the lane -> the day's own marker -> exit 75 -> detached clean -> resume + kick on
the launching checkout) is sound and the contract is honoured at every call site I traced. What is wrong is the
"once per boundary" rule: it also skips re-validation after a FAILED validation and after a clean that never finished,
and the queue's own once-per-worker-start retry of a failed finish makes the first case automatic, not hypothetical.

## 1. Findings

| # | Severity | File:line (b20374a) | Scenario (concrete) | Fix |
|---|---|---|---|---|
| 1 | CRITICAL | `frankie_box_stage_handoff.py:333-337` with `frankie_box_frankie_queue.py:2046-2049` | The ROOT validation finds `sha256_differ` on one layer -> handoff `failed` -> the day's finish `failed` (queue 1938-1940). The ROOT worker retries a failed finish ONCE PER WORKER START (`_needs_finish` 1662, `retried` 2046-2049): the next kick (the orchestrator's routine, an operator's kick for another day in scope) re-admits the finish; `boundary()` finds `handoff.json` with status `failed` in the `already` set and returns `already`; `_boundary` treats anything but `failed` as go; `run.check_save()` finds no marker; the teacher starts on the data that failed validation. Reproduced: probe P1 (`already`, `earlier_status=failed`). | Patch A below: a `failed` handoff is not "handed off before"; rename it aside and validate again (partial.json reuses every file whose stat is unchanged, so only changed files are re-read). |
| 2 | HIGH | `frankie_box_stage_handoff.py:333-337`; `frankie_box_root_move.py:344-355, 510-521, 551` | The clean dies between `os.rename(old, aside)` and `os.symlink` (reboot, SIGKILL at TimeoutStopSec, ENOSPC inside `_replace_with_symlink`): the pinned path is gone, `<old>.moving-aside` / `.archiving-aside` / `.premount-aside` holds the bytes. Nothing relaunches the clean; an operator resumes by hand; the boundary returns `already` (earlier status `saved`, `trigger.json` absent or `failed`) WITHOUT validating; the successor reads a missing path (loud failure) or, for a bind mount whose `unwind` could not umount (busy) and whose `os.rename(aside, old)` then raised, reads the copy that FAILED verification through the mount (silent). Reproduced: probe P2 (aside listed as unpinned `stay`, pinned path `missing`, boundary would say `already`). | Patch B: (i) `boundary()` returns `already` only when `trigger.json` says `done`; otherwise it validates again (cheap on unchanged stat) and goes on without a second clean; (ii) `plan()` recovers `*.moving-aside`, `*.archiving-aside`, `*.premount-aside` left without their original (rename back) before planning; (iii) `do_bind_mount.unwind` never renames the aside back over a still-mounted path. |
| 3 | HIGH | `frankie_box_root_move.py:329-342, 485-513, 669-705`; no `disk_usage` anywhere (probe P4b) | On a2 the clean now copies ~1.3 TB onto the archive volume (497 GB `.rows` + 194 GB `work/bedrock` by bind mount, 472 GB inline layer by move, the two native segments as tar.zst). The gp3 2048 GiB volume already received session 5's freed data; its free space is not checked. ENOSPC: `_copy_hashed` raises from `out.write`, `execute` lists the item failed, the partial `<new>.part` (up to hundreds of GB) is LEFT on the volume (probe P4: `.part` exists after the failure), the clean is `failed`, the day stays saved, no resume, the 30-day run halts until an operator notices `ACTION=status`. Then the Glacier copy (`upload_archives`) re-uploads 1.3 TB per day, 30 days, with no size or cost guard (recorded refusal only when the bucket is unset). | Patch C: `plan()` refuses (every item `stay`, reason named, the boundary then goes on WITHOUT a save) when `shutil.disk_usage(archive_root).free < planned bytes + 5 %`; `_copy_hashed` unlinks its `.part` on any exception; `upload_archives` records the bytes it is about to send and refuses above `FRANKIE_ARCHIVE_S3_MAX_BYTES` (default 2 TiB per clean) instead of uploading unbounded. |
| 4 | HIGH | `frankie_box_root_validate.py:370-387 (_walk_pins)`, `389-405 (collect_generic)`; `frankie_box_stage_handoff.py:186-196` | For every non-ROOT stage EVERY `{path, bytes, sha256}` object anywhere in the stage's receipt files is a must-be-unchanged pin and is READ IN FULL at that boundary: inputs included (probe P7). Two consequences. (a) The second pass Greg eliminated comes back per stage: a receipt that witnesses a ROOT spool or layer as its input (the exchange step records `teacher_rows` and `lessons` witnesses, exchange.py 334-335; Jev's request carries `original_inputs` witnesses, jev_cpu 22) re-reads that file on the lane at that stage's boundary. (b) A pinned INPUT that another lane legitimately rewrites between the receipt and the boundary (the 30-day run has two lanes; a batch lessons file, a school chain file, any shared store a later day appends to) fails THIS day's validation with `sha256_differ`, and the day fails for a file it does not own. I could not enumerate every receipt's witnesses without the box; the mechanism is proven and the policy is wrong in shape. | Patch D: `collect_generic(..., only_under=roots)`: a witness whose path is outside the stage's own output roots is recorded as `listed_input` (stat only: present and size equal, never read, never fatal); a witness under the roots is a pin as now. The ROOT collector is unchanged (its pins are attempt-local). |
| 5 | MEDIUM | `frankie_box_root_move.py:134-176 (plan bind_mount block)` | A guarded directory that is ALREADY a bind mount (a second clean of the same ROOT by hand after a failed item elsewhere; the argv is recorded for exactly that) is planned as `bind_mount` again: `_copy_tree_hashed(old, new)` copies 497 GB onto itself through the mount (identical bytes, 1 TB of needless I/O), then `os.rename(old, aside)` of a mount point raises EBUSY -> the item fails -> the clean fails -> no resume. | Patch E: in `plan()`, `os.path.ismount(directory)` -> `stay` with reason `already bind-mounted`; `add_manifest` already accepts it as `bind_mount_ok`. |
| 6 | MEDIUM | `frankie_box_root_move.py:542-550` with `/etc/fstab` | The clean appends `<archive copy> <old path> none bind,nofail 0 0` for every bind mount (2-3 per ROOT, 30 days = 60-90 permanent lines, never removed when a run is retired) and relies on the archive volume's own fstab line preceding them. If the archive volume is not in fstab (session 5 mounted it by hand; not verifiable from here) a reboot brings every bind mount up on an EMPTY mount-point directory (`nofail`): every safe_path reader finds nothing, loudly; and the moved-file symlinks dangle. Also `shutil.rmtree` of an attempt directory (no such code in the box today; an operator's `rm -rf` of an old attempt, which the disk floor work has asked for) descends INTO a bind mount and deletes the archive copy. | Patch F: write the bind lines with `x-systemd.requires-mounts-for=<archive root>` (or refuse the bind mount when `archive_root` is not itself a mount point in fstab: `findmnt --fstab <archive_root>` rc 0 required), one line per attempt in a marked block so `retire_run` can remove them; the README beside the mount point says `umount` first and never `rm -rf`. |
| 7 | MEDIUM | `frankie_box_stage_handoff.py:446-467` | `successor_running` greps `frankie_box_experiment` and units named with the run and day. A live ROOT-line worker's argv is `frankie_box_frankie_queue.py --action worker --line root --scope RUN:DAY...` (no `frankie_box_experiment`), its unit is `frankie-queue-root-<epoch>` (no run or day): the guard never sees it (probe P5: `[]`). The trigger is still safe because `ACTION=kick` refuses when a worker holds the lock and `resume_owner` is idempotent on a saved entry, so this is a guard that guards nothing, not a double start. | Patch G: match `frankie_box_frankie_queue.py --action worker` lines whose `--scope` names the run and day, and `frankie-queue-*` units through `worker_state(line)`; or delete the guard and say so in the docstring (a guard that cannot fire misleads the next reader). |
| 8 | MEDIUM | `frankie_box_frankie_queue.py:1876-1887 (_archive_marker)`; `frankie_box_experiment.py:802-813` | `ACTION=resume` archives the marker and the class ack but not `<marker>.clean.json`; the note survives at the same path for every later save of the same run/day. `ACTION=status` then shows the ROOT stage's clean under the teacher's save until the teacher's clean overwrites it, and `box_in_use` reads a stale `status: running` note (a clean killed mid-run, or the box rebooted before the note was overwritten) as the box in use forever: `keep_running(False)` is refused at every worker end and the idle guard never stops the box. | Patch H: `_archive_marker` moves `<marker>.clean.json` with the marker; `box_in_use` treats a `running` note as live only while its recorded `pid` exists (`/proc/<pid>`). |
| 9 | MEDIUM | `frankie_box_stage_handoff.py:572-589` | The Glacier second copy runs AFTER the trigger, inside the clean unit pinned to the retained lane: the resumed day is re-admitted on exactly those 16 CPUs (`_book_slot` books `owner['cpus']`) and its teacher reads the 497 GB `.rows` copy from the archive volume while the unit uploads the same 1.3 TB from the same volume on the same CPUs. The day's chain does not wait, as the docstring says, but it runs at a fraction of its I/O and CPU for the upload's duration (1.3 TB at the volume's 1000 MiB/s shared both ways: 30-60 min). | Patch I: the upload runs under `taskset` of the lane's idle sibling threads only, or after the resumed day's next boundary; at minimum `nice -n 19 ionice -c3`. Recorded as Greg's call (f) in the receipt. |
| 10 | LOW | `frankie_box_stage_handoff.py:394-400` (and the build's open call) | A stage whose outputs are all under the 1 GiB floor validates and goes on WITHOUT a save: the teacher (rows directories, usually small), lessons, survivors, voice, jev, reports never stop after validation. Greg's directives 4 and 7 were said about the ROOT; directive 9 extended the sequence to every piece. Whether "validate, then stop" or "validate, then go on when there is nothing to clean" is the rule for the small pieces is his call, not the build's; the build chose the second silently for the small ones. | No patch; a one-line question to Greg, recorded on the handoff receipt either way (`reason` already says it). |
| 11 | LOW | `frankie_box_stage_handoff.py:115` | `roots=('rows',)` on the teacher entry is dead (the teacher step receipt carries rows under `inspection.outputs.rows`, experiment.py 4232; probe P3: `output_roots` on the real shape gives `[]`). Fixed at b474c51 by `roots_from=_teacher_rows_dirs`; the dead field remains and misleads. | Delete `roots=('rows',)` from the teacher entry. |
| 12 | FYI | `frankie_box_experiment.py:1729` (`DIGEST='on' if classroom_arm or plan root_digest on else 'off'`) | Landed in the same WIP commit, outside the handoff: the ROOT no longer builds process 4 on non-arm days. a2 (20231018) is an arm day, untouched. It changes a ROOT output on 24 of the 30 days and the brain entry's sources; the authority cited is "some of these end steps feel redundant". Needs Greg's explicit yes before the 30-day run, not a reading of a feeling. | None in code. |
| 13 | FYI | `frankie_box_root_move.py:255-312 (redundant_ledger_segments)` | The pre-save ledger copy and the append segment are called redundant on SIZES ONLY (final == prefix + append) and archived as tar.zst, never deleted; nothing later reads them while `native-stage.json` is complete. Sound as archival, and reversible. The arithmetic is not a content proof; the docstring says so. | None. |

Findings I looked for and did not find (per axis, "none found" is stated only where I traced the code):
- (1) The marker is requested only after validate exit 0 and only when the plan has work (`boundary` 349-406); `check_save` at
  every call site right after `_boundary` (queue 1377, 1423, 1511, 1522, 1533, 1552; class keep 808); the resumed day's
  root step is the finish path (`_finish_job`, no `run.root`), `root_of` names the same attempt, `_boundary('root')` is
  `already` after a DONE trigger; exit codes 0/3/75/4 mapped (`boundary` 358-373); on a2 the owner binding is reused by
  `_bind_owner` (owner present, 1210), `_source_wait` rebinds the source to the launching checkout (530-566), `C.retain`
  keeps the 16 CPUs (`_end_slot` 1676), the wrapper refuses a CODE_ROOT outside `/opt/frankie-box/code` and a
  `MARKETS_SHA` that is not HEAD (sh 38, 65, 74, 80). `request_save` requires `running` or `done+finish running`: on the
  resumed finish path `x['finish']` is set to `running` at take (2064) before the thread starts. None found.
- (2) systemd-run flags: `--collect`, `KillMode=mixed`, `StandardOutput=append:` (systemd >= 240), `-E` env, `taskset -c`
  of the retained lane; the wait is bounded (1800 s, poll 10 s); the clean's `open_files` excludes only its own pid and
  the worker thread has ended before `wait_saved` returns; cross-device copy + verify + rename-aside + symlink; zstd
  failure keeps the source and names it; `KeepRunning`: the worker's `keep_running(False)` sees the clean's pgrep /
  unit / running note (experiment 784-813, landed at b474c51) and keeps the tag. Findings 2, 3, 5, 6, 8 above are what
  remains.
- (3) Exactly once by `trigger.fired` create-only (481); saved-state guard (487); resume then kick with `CODE_ROOT`,
  `MARKETS_SHA`, `RUN`, `DAY` of the LAUNCHING checkout (494-506); a refused resume returns `failed` with both exit codes
  and no kick (B18); the resumed entry goes back `queued` / finish `resume` with the same owner (`resume_owner` 2286-2337).
  Finding 7 above.
- (4) Both receipt forms, the reference layers' index claims, the spools' count, every pin read once (A3-A5 of the
  build's suite; `check_job` one `scan_spool` or one `witness`), largest first through `lane_pin.ordered_map`, exit 75
  with `partial.json` and stat-keyed reuse, the manifest's archive and bind-mount kinds by stat only, exit 4 on a
  symlink under a guarded prefix (probe P6). Finding 4 above.
- (5) `write_chunks` (durable 53-103): the pending write, fsync, `.retained-<sha>` link, directory sync, `os.replace`,
  directory sync are in the same order as before; the two read-backs are replaced by two size checks; bytes identical
  (D1-D3). `filehash.remember` keys on (resolved path, dev, ino, size, mtime_ns, ctime_ns): a file rewritten in place
  gets a new ctime, so a stale hash cannot be served; `remember` refuses when the size on disk differs. The digest's
  `remember(destination, staged)` is on the published inode after the link check (628). The `dict(path=..., **witness())`
  shape: experiment_root 418 fixed; the 16 other sites (exchange 334-335, 1948, 1964; school_knowledge 465, 484, 503;
  jev_cpu 280, 618; survivor_update 646, 740; experiment_native 192; experiment_review 763; receipts 101-104;
  scientific_teacher 2131-2133) all use `frankie_box_durable.witness` or the filehash-backed local `witness`, which return
  `{bytes, sha256}` without `path`: no TypeError remains. None found.
- (6) Receipt names per STAGES confirmed by the build's follow-up against the writers (teacher rows receipt, classroom
  completion/receipt, exchange receipt, data/search MANIFEST, reports receipt, school: none). The switch is read in
  `on()` only and passed through to the unit (295-299). Finding 10 (the floor rule) and 11 above.
- (7) Hangs: `wait_saved` bounded; `kick` waits at most 60 s for the lock; the wrapper calls are `subprocess.run` of
  short actions (the kicked worker is detached under systemd-run or a new session with its own log, so it does not hold
  the trigger's pipes); the validator and the copies are the work itself and honour the stop file / SIGTERM. Swallowed
  exceptions: `keep_running`, `_note_beside_marker`, the Glacier copy, and `lane_of`'s ledger read are the only
  `except` that do not record a status, each a cost guard or a note, each printed. None found beyond those.
- (8) The three named gaps stand as named: guarded prefixes are declared for the ROOT only (the bind mount now moves them);
  the class save-ack path is unexercised (two workers needed); the serial loop and the mailbox lane are not wired. The
  class path by reading: the class worker's `keep()` saves on the owner's marker, exits 75, writes the ack (queue
  1030-1035), the owner's `_child_save_verdict` loop ends it saved; the clean unit started from the CLASS worker waits on
  the ROOT entry's state and resumes both entries. Consistent; untested.

## 2. The patches

Patch A (finding 1), `frankie_box_stage_handoff.py` at 332-342:

```
-    if existing and existing.get('status') in ('saved', 'failed', 'validated'):
+    trigger_done = ((_load(out_dir / 'trigger.json') or {}).get('status') == 'done')
+    if existing and existing.get('status') == 'failed':
+        # a FAILED validation is never "handed off before": the retry of a failed finish (the queue's once-per-worker-
+        # start rule) validates again; partial.json reuses every file whose stat is unchanged
+        os.replace(out_dir / 'handoff.json', out_dir / ('handoff.failed-%d.json' % int(existing.get('at') or time.time())))
+        existing = None
+    if existing and existing.get('status') == 'validated' or (existing and existing.get('status') == 'saved' and trigger_done):
```

Patch B (finding 2), same block, after Patch A, plus `frankie_box_root_move.py`:

```
+    if existing and existing.get('status') == 'saved' and not trigger_done:
+        # the clean never triggered (box reboot, a failed item, a hand resume): validate again (unchanged stat = no read),
+        # then go on WITHOUT a second clean; the earlier receipts stay beside this one
+        os.replace(out_dir / 'handoff.json', out_dir / ('handoff.unfinished-%d.json' % int(time.time())))
+        base['earlier'] = dict(status='saved', trigger=(_load(out_dir / 'trigger.json') or {}).get('status'))
+        base['clean_again'] = False
```
and in `boundary()` after the validation, `if base.get('clean_again') is False: return _write(..., status='validated', reason='re-validated after an unfinished clean; no second clean')`.

In `plan()` (root_move 134, before the walk):
```
+    for root in roots:
+        for aside in list(Path(root).rglob('*.moving-aside')) + list(Path(root).rglob('*.archiving-aside')) + list(Path(root).rglob('*.premount-aside')):
+            original = Path(str(aside).rsplit('.', 1)[0])
+            if not original.exists() and not original.is_symlink():
+                os.rename(aside, original)                       # a crash between rename-aside and symlink/mount: put back
+                items.append(dict(kind='stay', old_path=str(original), new_path=None, bytes=original.stat().st_size if original.is_file() else _du(original),
+                                  pinned=False, reason='recovered from %s (an interrupted earlier clean); planned afresh below' % aside.name))
```
In `do_bind_mount.unwind` (515-525):
```
-        subprocess.run(['umount', old], capture_output=True) if mount_cmd == 'mount' else None
-        try:
-            os.rmdir(old)
-        except OSError:
-            pass
-        os.rename(aside, old)
+        if mount_cmd == 'mount' and subprocess.run(['umount', old], capture_output=True).returncode != 0 and os.path.ismount(old):
+            out.update(status='failed', reason=why + '; umount %s refused (busy): the copy STAYS MOUNTED, the original is at %s; '
+                       'an operator umounts and renames it back; the next boundary validates again' % (old, aside))
+            return out
+        os.rmdir(old)
+        os.rename(aside, old)
```

Patch C (finding 3), `frankie_box_root_move.py`:

```
 def plan(...):
     ...
+    planned_bytes = sum(i['bytes'] for i in redundant + items if i['kind'] != 'stay')
+    free = shutil.disk_usage(archive_root).free if Path(archive_root).exists() else 0
+    if planned_bytes and free < planned_bytes * 1.05:
+        return [dict(i, kind='stay', new_path=None, reason='archive volume %s: %d bytes free, %d planned (+5%%): nothing moved; '
+                     'free the volume or raise it' % (archive_root, free, planned_bytes)) if i['kind'] != 'stay' else i
+                for i in redundant + items]
```
```
 def _copy_hashed(source, destination):
     ...
-    with _open_read(source) as src, open(part, 'wb') as out:
-        ...
+    try:
+        with _open_read(source) as src, open(part, 'wb') as out:
+            ...
+    except BaseException:
+        with contextlib.suppress(OSError):
+            os.unlink(part)                                      # never a partial copy left on the archive volume
+        raise
```
```
 def upload_archives(...):
+    limit = int(os.environ.get('FRANKIE_ARCHIVE_S3_MAX_BYTES') or (2 << 40))
+    total = sum(os.path.getsize(c[0]) for c in copies if os.path.isfile(c[0]))
+    receipt['bytes'] = total
     if switch == 'off': ...
+    elif total > limit:
+        receipt.update(status='refused', reason='%d bytes exceed FRANKIE_ARCHIVE_S3_MAX_BYTES %d; nothing uploaded' % (total, limit))
```

Patch D (finding 4), `frankie_box_root_validate.py` `collect_generic` and `_walk_pins`:

```
-def _walk_pins(pins, source, value, where):
+def _walk_pins(pins, source, value, where, only_under=None):
     ...
         if _has_witness(value) and isinstance(value.get('path'), str) and value['path'].startswith('/'):
-            count = ...
-            pins.claim(...)
+            real = os.path.realpath(value['path'])
+            if only_under and not any(real == r or real.startswith(r + '/') for r in only_under):
+                pins.listed_inputs.append(dict(source='%s:%s' % (source, where), path=value['path'], bytes=value['bytes'],
+                                               present=os.path.exists(value['path']),
+                                               size_matches=(os.path.getsize(value['path']) == value['bytes']) if os.path.exists(value['path']) else None))
+                return n                                            # an INPUT of the stage: listed by stat, never read, never fatal
+            count = ...
+            pins.claim(...)
-def collect_generic(receipt_paths, root=None):
+def collect_generic(receipt_paths, root=None, only_under=None):
+    pins.listed_inputs = []
     ...
-            n = _walk_pins(pins, path.name, body, '')
+            n = _walk_pins(pins, path.name, body, '', only_under=[os.path.realpath(str(r)) for r in (only_under or [])] or None)
```
and in `frankie_box_stage_handoff.collect` / `clean_action`: `V.collect_generic(files, root=..., only_under=roots)` for every non-ROOT stage; the receipt gains `listed_inputs`. (A stage without output roots then pins nothing but its receipt files, which is the correct reading of "every artifact the stage pinned".)

Patch E (finding 5), `frankie_box_root_move.py` 149-152:
```
             if not directory.is_dir() or directory.is_symlink():
                 continue
+            if os.path.ismount(directory):
+                items.append(dict(kind='stay', old_path=str(directory), new_path=None, bytes=_du(directory), pinned=True,
+                                  reason='already a bind mount (an earlier clean); nothing planned'))
+                skip.add(os.path.realpath(str(directory)))
+                continue
```

Patch F (finding 6), `frankie_box_root_move.py` 542:
```
-    line = '%s %s none bind,nofail 0 0' % (new, old)
+    if subprocess.run(['findmnt', '--fstab', '--target', str(Path(new).anchor if archive_root is None else archive_root)], capture_output=True).returncode != 0:
+        return unwind('the archive volume %s has no fstab entry: a bind line would come up on an empty directory after a reboot' % archive_root)
+    line = '%s %s none bind,nofail,x-systemd.requires-mounts-for=%s 0 0  # frankie-clean %s' % (new, old, archive_root, Path(old).parts[-3] if len(Path(old).parts) > 3 else old)
```
(and `retire_run` removes the `# frankie-clean <attempt>` lines of a retired run after `umount`).

Patch G (finding 7), `frankie_box_stage_handoff.py` 446-467: replace the pgrep pattern with two: `frankie_box_experiment` (stage children, as now) and `frankie_box_frankie_queue.py --action worker` whose line contains `--scope <run>:` and the day; and the unit check with `Q.worker_state('root')[1]` (the lock) plus the scope text. Or delete the guard and the docstring's claim.

Patch H (finding 8), `frankie_box_frankie_queue.py` 1882: `for path in (Path(marker), Path(str(marker) + '.class-ack.json'), Path(str(marker) + '.clean.json')):`; `frankie_box_experiment.py` 810: `if status == 'unreadable' or (status == 'running' and Path('/proc/%s' % note_pid).exists())` with `note_pid = json.loads(...).get('pid')`.

Patch I (finding 9), `frankie_box_stage_handoff.py` 576: wrap the upload in `nice -n 19 ionice -c 3` by running it as a child under `taskset -c <the lane's second threads only>`, or move it to a separate detached unit started after the trigger with no lane pin.

## 3. Tests run (exact output)

The build's suite, re-run on this tree twice (`python3 -B scratchpad/root_validate/test_s6_handoff.py`):
- on `1d80cd6` at 02:4xZ: `70 passed, 0 failed` (rc 0, 26.8 s wall; the record said ~75 s; same count)
- on `b20374a` (the test file updated by the build in the meantime): `84 passed, 0 failed` (rc 0)
  Saved: `scratchpad/review_handoff/test_s6_rerun.txt`, `test_s6_rerun_head.txt`.

My probes (`scratchpad/review_handoff/review_probe.py`, output `review_probe_out.txt` on 1d80cd6 and
`review_probe_out_head.txt` on b20374a; identical results):
```
PASS  P1 first pass: validation mismatch -> failed  validation exit 3: ...
PASS  P1 the retry of the same boundary: status is 'already' (the day goes on to the teacher on data that failed validation)  this boundary was handed off before (failed); the clean left no receipt; the trigger left no receipt; the day goes on to teacher
PASS  P2 after a crash mid-move the aside file is listed as stay (unpinned) and the pinned path is simply absent: {'layer.json.moving-aside': ('stay', 'not pinned by any receipt (listed, not moved on its own)')}
PASS  P2 the validator would now report the pinned path missing (missing), but a resumed boundary returns already without validating
PASS  P3 output_roots("teacher", <real-shaped teacher record>) == [] (STAGES teacher roots=("rows",) is dead: nothing is ever cleaned for the teacher)
PASS  P3b output_roots("root") on the same shape finds the attempt dir
PASS  P4 a failed copy: item failed=failed, source kept=True, but the partial .part is left on the archive volume (exists=True, 4096 bytes)
PASS  P4b no free-space check anywhere in root_move/stage_handoff
PASS  P5 a live root worker for the run/day is not seen by successor_running: []
PASS  P6 the validator exit on a verified spool behind a symlink under work/derived/.rows is 4 (4 = verified, not readable); the boundary then FAILS the day (handoff 322-324)
PASS  P7 a receipt that records an INPUT witness ({path,bytes,sha256}) makes it a must-be-unchanged pin: 1 pin(s) from an inputs-only record

11 passed, 0 failed
```
(P3 describes 1d80cd6; at b474c51 `roots_from=_teacher_rows_dirs` supplies the teacher's rows directories when
`<TEACHER_ROWS>/<day>` exists; the dead `roots=('rows',)` field remains, finding 11.) Every PASS above is a reproduction
of a finding, not a pass of the build. Static: `git diff --check` clean on the reviewed files; nothing on the box or in
AWS was touched or read.

## 4. What I could not verify without the box
- The archive volume's free space and whether it is in `/etc/fstab` (findings 3 and 6 turn on it).
- The sizes under a2's `work/classroom/<attempt>`, the data/search targets and the exchange directory (which
  non-ROOT outputs reach the 1 GiB floor), and which later readers of those outputs use `safe_path` (no guarded
  prefixes are declared for them; a moved file there is readable through `open()` but not through `safe_path` or Jev's
  "absolute and symlink-free" rule, experiment.py 3770).
- Every receipt's witness inventory (finding 4's blast radius: which receipts pin inputs that another lane rewrites).
- systemd-run under the box's systemd (StandardOutput=append, KillMode=mixed, `-E` env), `mount --bind` as the unit's
  user, `taskset` on the retained lane, the real `zstd -T0` and the volume's throughput, `request_save` from inside the
  day thread, the class worker's acknowledgment path, the resume+kick against a live queue, the Glacier upload itself.
- Whether 20231018's ROOT receipt (written by c9bf631) carries `receipt_sha256` on `days/20231018/root.json` (the
  validator falls back to "self (measured)" if not; either way correct).
