# Clean role record, 2026-10-08 01:29-01:46Z (session 6): PREPARED clean+zip of run e2e-20231018-a2's ROOT output

Box i-035994afa8bdf66a5 (us-east-1). R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1.
Archive volume /opt/frankie-box/archive (nvme1n1, gp3 2048 GiB, 1000 MiB/s). Root volume nvme0n1 (1250 MiB/s).
READ-ONLY on the box except ONE write: /opt/frankie-box/archive/.logs/clean-a2.sh (26,661 B, mode 700,
sha256 2831bf345d35d4e692a56905945440ff242d3c1d2c632fa41cb98f9cbf33e5e4, bash -n ok, written 01:45:04Z by SSM command
6fd1be60-961e-4680-9671-b72923bc7218). NOTHING executed it. Local copy: this directory's clean-a2.sh (same sha256).
Repo read at tip efb934e (WIP snapshots; never stage). Nothing killed, moved, removed, tagged.

## Box state at the last read (01:45:04Z)
- ROOT pid 14860 ALIVE, stage root-digest (progress.json 01:33:06Z), Sl 42% CPU, elapsed 03:01. Stages seen this
  task: root-projection-member 01:30 (84.8% of 193.7 GB) -> root-projection-lifecycle 01:31 -> root-projection-publication
  01:32 (19.6% of 46) -> root-digest 01:33. work/derive.json written 01:33 (80,813 B). work/legacy-stage.json 01:17
  (59,810 B). calculations-receipt.json ABSENT. The HOLD FIRED at 01:20:55Z: marker standing, entry save_request set,
  entry state still 'running' ("save pending acknowledgment"); the day becomes 'saved' when ROOT exits 75 after the
  receipt. Teacher: none. The disk guard (15 GB) still polls.
- Root free 603,207,778,304 B (603.2 GB) at 01:45Z, falling while the projection/digest writes (658.9 GB at 01:30Z,
  621.7 at 01:32Z): work/derived/.projection-v2 = 97,835,917,374 B at 01:45Z (79.3 GB at 01:32Z). Archive free
  1,725,022,765,056 B (1,725.0 GB).
- /opt/frankie-box/work/experiment-teacher-rows is STILL the session-5 symlink -> archive/work/experiment-teacher-rows.tar.zst
  (24,863,644,343 B, sha256 5d3dd82d8f3af932...). The a2 teacher writes experiment-teacher-rows/<day>/ (OUT / day,
  frankie_box_experiment_teacher.py:45,550) and would fail under a tarball.

## The session-5 method REUSED (archive/.logs/batch-worker3.sh, 3113 B, sha 99be15a7648e294f; batch.log 92 lines, 50 VERIFIED+REMOVED)
tar -cvvf - (listing at creation) | zstd -T2 -3 -q | tee >(sha256sum) > OUT (sha256 on the WRITE stream); .pipestatus;
then (batch) one decompress-list read-back compared with the write listing; rm -rf SRC && ln -s OUT SRC; README
"<name> moved <utc> to <out> (<B>, sha256 <sha>, computed on the write stream); verified ...; Restore: zstd -dc OUT | tar -C P -xf -".
clean-a2.sh keeps exactly that pipeline shape (tar -vv listing, zstd -T0 -3 -q, tee, sha256 on the stream, .pipestatus,
.sha256, symlink + ARCHIVED README) and REMOVES the read-back pass (Greg: "we only do 1 pass. Eliminate the 2nd pass"):
the creation checks are tar/zstd/tee/sha256sum pipestatus all 0, write-listing entry/file/byte counts equal to the
source's find counts, archive size > 0. Pinned to measured-idle sibling pairs (taskset), zstd -T0 inside each job's set.

## The (A)/(B)/(C) plan, with sizes (du -xb / stat at 01:30-01:45Z) and the reader evidence

Rule: a file a later stage reads BY PATH moves behind a symlink only if that reader follows symlinks. Two reader
classes exist in the box code:
- plain open (follows symlinks): frankie_box_joined_teacher._job_stream (216-225: `opener(path)`), frankie_box_teach._stream_layer
  (45-63: `Path(entry['path']).is_file()` + open), frankie_box_monday_calculations.load_retained_layers (76: `path.open`),
  frankie_box_digest_sources._read (772) and the layer copy (755: fstat S_ISREG on the opened fd, follows), frankie_box_filehash.witness
  (37: open). frankie_box_experiment_data.py:402/419/448 SKIPS symlinks (`not p.is_symlink()`): archived paths drop out of the
  data catalog, which is correct for withheld BEDROCK state.
- safe_path-class (REFUSES a symlink at the path or any parent): frankie_box_prepare_trading_day.safe_path (31-37) and
  open_regular (O_NOFOLLOW, 40-47); frankie_box_market_timeline._local (92-96) used by _json (99), _rows (114) and _rows_parallel
  (211, 227): the teacher's shared reader opens the .rows spools through it (522: the pin path must equal
  root/'work/derived/.rows'/<role>.jsonl); frankie_box_experiment_native._take_all (166-170: `any(p.is_symlink() for p in
  (path, *path.parents))`) for work/bedrock/recovery-*/receipt.json, result.json, the three final ledgers, and
  work/derived/.projection-v2/<section>.json.gz + plan.json (189); frankie_box_segmented_ledger.ordered_chunks (62);
  frankie_box_native_checkpoint 296/319/334/354; frankie_box_bedrock.ledger_path (894). The root validator records the same
  three guarded prefixes (frankie_box_root_validate.READER_GUARDS 64-69; frankie_box_stage_handoff.STAGES 'root' guarded=
  work/derived/.rows/, work/bedrock/, work/derived/.projection-v2/).
- frankie_box_experiment.root() 1609/1623 refuses a symlinked ATTEMPT DIR and reads calculations-receipt.json,
  work/derive.json, work/derivation-digest-full.md, external-computation.json (1645-1648) by path: never touched.

### (A) MOVE (plain copy to the archive volume, same relative layout, sha256 on the write stream == the ROOT's pin, then a symlink)
| item | bytes | evidence |
|---|---|---|
| work/derived/legacy_book_imbalance.json | 472,040,420,230 | pinned in work/legacy-stage.json artifacts[8] (bytes+sha256; the script compares the stream hash with it); read after ROOT only through plain opens: joined teacher _job_stream (295: every derive layer file without a published layout is streamed sequentially), teach._stream_layer, load_retained_layers (ROOT's own resume/render). NOT read by market_timeline (its LAYERS are the .rows spools, the native ledgers and external). |
Total (A): 472,040,420,230 B (472.04 GB). New path: /opt/frankie-box/archive/work/experiment-roots/e2e-20231018-a2-20231018-a1/work/derived/legacy_book_imbalance.json (+ .sha256).
Trade-off for Greg: the teacher then streams this layer from the archive volume at 1000 MiB/s instead of 1250 MiB/s:
472.04 GB takes ~450 s instead of ~360 s per full sequential read (+90 s per read). Default: archive volume (the root
volume needs the space; the file stays readable in place through the symlink).

### (B) ZIP (tar -vv | zstd -T0 -3, sha256 on the write stream, listing at creation, source removed, symlink + README)
| item | bytes | evidence that NO later stage reads it |
|---|---|---|
| work/bedrock/recovery-6f84a8a86f454010b61346b401e3eb5f/ledgers/exact_member_rows.append.jsonl | 127,622,314,364 | the resumed sink's "fresh append segment" (frankie_box_segmented_ledger._resume_sink 387-398: `append_path = sink.path.with_suffix('.append.jsonl')`, opened 'xb'); its bytes are already materialized in the final ledger: 66,121,336,080 (pre-save prefix) + 127,622,314,364 = 193,743,650,444 = exact_member_rows.jsonl exactly (native-stage.json artifacts[2]); `grep -rn 'append.jsonl'` over deploy/aws/box finds no reader (only that writer); not among native-stage.json / derive.json pins; not a parent of any pinned path (the symlink check in _take_all walks the pinned file and its parents only). |
| work/bedrock/ledgers/ (the pre-save copy: exact_member_rows.jsonl 66,121,336,080 + exact_lifecycle_rows.jsonl 1,689,507,648 + legacy_observable_rows.jsonl 263,848,914) | 68,074,692,642 | named only by checkpoints/controller-state-000005.json descriptor['ledgers'] (read by frankie_box_native_checkpoint.restore_driver 330-340 / compare_reconstructed_prefix 345-360 and frankie_box_finalization.restore_closed 189 ON A NATIVE RESUME FROM CHECKPOINT); that resume cannot happen: the native stage is complete (work/native-stage.json 00:15:04Z; R/note "bedrock: completed native results reused in place; no traversal or finalization replay"; frankie_box_boss_session 3267-3275 reuses a completed native-stage.json after witnessing its artifacts; frankie_box_bedrock.recovery_checkpoint 414 is reached only inside B.run). Its bytes are the byte PREFIX of the final ledgers (compare_reconstructed_prefix semantics; member 66,121,336,080 + append = final). Session-5 drop-in listed it "must stay (checkpoint 000005 names it)" while ROOT was still running; it is ZIPPED, not deleted (restorable). To keep it untouched instead: Greg's call; the job is the PRESAVE_REL line of the script. |
| work/bedrock/recovery-6f84.../ledgers/exact_lifecycle_rows.append.jsonl | 3,035,329,789 | same class as the member append (1,689,507,648 + 3,035,329,789 = 4,724,837,437 = native-stage.json run/execution/ledger_materialization/lifecycle; the final exact_lifecycle_rows.jsonl 7,560,352,552 adds the finalize rows). |
Total (B): 198,732,336,795 B (198.73 GB) uncompressed. Compression: the Monday root compressed to 0.696 (297.47/427.27 GB,
mixed content); numeric JSONL rows at zstd -3 are expected at 0.35-0.5. Archive bytes for (B): 69.6-139.1 GB.

### (C) STAY (never touched)
- The attempt dir R itself; calculations-receipt.json, work/derive.json, work/derivation-digest-full.md, external-computation.json
  41,956; calculation-pins.json 33,283; source-binding.json 7,631; progress.json, note, phase, native-overlap/, checkout-rebinds/, out/.
- GUARDED (safe_path-class readers): work/derived/.rows/frames.jsonl 496,743,568,399 (market_timeline._local; the teacher
  streams it: this is the big one that cannot move without a bind mount or a reader change: Greg's call), structures.jsonl
  1,063,001,944, input-34b2...jsonl 537,361,074, prices.jsonl 17,393,149, failures.jsonl 0;
  work/bedrock/recovery-6f84.../{receipt.json 30,083, result.json 224,765,615, ledgers/exact_member_rows.jsonl 193,743,650,444,
  exact_lifecycle_rows.jsonl 7,560,352,552, legacy_observable_rows.jsonl 742,788,266} (experiment_native._take_all);
  work/derived/.projection-v2/ 97,835,917,374 at 01:45Z and growing (same reader; plan.json 147,541,031).
- Under the 1 GiB floor: work/derived/legacy_structure_observables.json 943,063,633; legacy_native_signed_flow.json 5,301,145;
  legacy_per_second_roll20.json 1,042,750; legacy_price.json 1,594; 49 bedrock layer stubs of 121 B; recovery-.../ledgers/
  legacy_observable_rows.append.jsonl 478,939,352; work/bedrock/checkpoints/ 341,767,005; legacy-state.pkl 860,663.
- By decision: work/bedrock/recovery-6f84.../checkpoints/ 1,839,806,943 (the lineage's leaf checkpoint-000009 named by
  native-overlap/checkpoints.json; 1.8 GB is 0.1% of the volume, not worth a symlink inside the guarded prefix).

Totals: taken off the root volume 670,772,757,025 B (670.77 GB) = 472.04 (A) + 198.73 (B). Stays on root: ~1,280 GB of
the attempt (frames 496.7 + final ledgers 202.0 + projection-v2 ~98+ + the rest).

## clean-a2.sh (sha256 2831bf345d35d4e692a56905945440ff242d3c1d2c632fa41cb98f9cbf33e5e4)
Modes: `dry-run` (default; writes nothing, not even the log), `execute`, `rows-dir` (step 0 only), `__job` (internal).
Step 0 (first, idempotent, printed by dry-run): /opt/frankie-box/work/experiment-teacher-rows symlink -> REAL empty directory
with ARCHIVED-OTHER-DAYS.README.txt inside naming the tar.zst, its bytes, its sha256 (from the .sha256 beside it), its
listing and the restore line; the original .ARCHIVED.README.txt stays beside it; verified by test -d and ls -la. Refused if
a teacher process runs. Reader check: every a2 stage addresses experiment-teacher-rows/<day> of the run's OWN days only:
frankie_box_experiment.py rows_of 536-547 (TEACHER_ROWS / entry['day']), 2260, 4109 (stale receipt of e['day']), 4160
(receipts of the batch's days), school 3552-3560 (day_rows(e)); frankie_box_experiment_classroom(.sh) and classroom_v2 take
--teacher-rows <day dir>; frankie_box_school_knowledge.py 91-101/237-241 reads <teacher-rows>/receipt.json of its day;
no glob/iterdir over the directory anywhere; frankie_box_teacher_knowledge.py and frankie_box_scientific_teacher.py never
name it (their "other days" are lesson references). For a one-day run the empty real directory is the fix; nothing to extract.
Preflight (execute refuses on any FAIL; dry-run prints PASS/FAIL per line):
 1. R is a directory, not a symlink.  2. R/calculations-receipt.json exists (not a symlink).
 3. queue entry e2e-20231018-a2 / 20231018 in /opt/frankie-box/work/frankie-queue/root.json has state == 'saved'.
 4. no process holds a file or cwd under R open (/proc/*/fd and /proc/*/cwd scan; count must be 0).
 5. no frankie_box_experiment_root.py / *_teacher / batch-worker / frankie_box_root_move / frankie_box_root_validate process.
 6. archive volume mounted (findmnt).  7. archive free >= plan bytes (uncompressed) + 15 GB.  8. root free >= 15 GB.
 9. tar, taskset, flock, sha256sum, tee, findmnt, zstd, python present.
10. measured-idle sibling pairs >= 3 (two /proc/stat samples 5 s apart; both siblings < 10% busy; cpu0's pair excluded).
11. the move's pin found in work/legacy-stage.json (else derive.json) with bytes equal to the file.  12. plan not empty.
Execution: flock on .logs/clean-a2.lock; jobs largest-first, 3 concurrent, each job its own process group (setsid) pinned
by taskset to 5 idle sibling pairs = 10 CPUs (job i takes idle pairs i, i+3, i+6, ...; with 31 CPUs idle after the save:
job0 = 1,17,4,20,7,23,10,26,13,29; job1 = 2,18,5,21,8,24,11,27,14,30; job2 = 3,19,6,22,9,25,12,28,15,31; pair 0,16 left
to the system and the hold watcher). zstd -T0 -3 inside each set. Disk guard every 2 s: below 15 GB free on EITHER volume
SIGSTOP every job's process group, log GUARD PAUSED; SIGCONT above 40 GB. Per job: .part written, renamed only after the
creation checks; a failed job keeps its source and its .part.rejected. Outputs per item: the archive/plain copy, .sha256
(stream), .listing.txt (tar -vv) and .pipestatus for zips, ARCHIVED README at the old path, symlink at the old path.
Idempotent: a source already a symlink is listed DONE/skipped; a stale .part is discarded; an existing output beside a live
source is REFUSED (operator decides), never overwritten. Moved-manifest:
/opt/frankie-box/archive/work/experiment-roots/e2e-20231018-a2-20231018-a1.moved-manifest.json, schema
FRANKIE_ROOT_MOVE_MANIFEST_V1 (what frankie_box_root_validate.add_manifest reads: kind move|archive, old_path, new_path,
bytes, bytes_copied|bytes_archived, sha256, listing_path, entries, status; plus op: move|zip, pin for the move); a re-run
merges earlier moves. Log /opt/frankie-box/archive/.logs/clean-a2.log (+ .results.jsonl, job-N.out); final line
CLEAN_RECEIPT {schema FRANKIE_CLEAN_A2_RECEIPT_V1, status, jobs_done/failed, root_free_before/after, root_freed,
archive_free_before/after, archive_written, manifest, log, script_sha256, cpu_sets}; exit 0 only when every job is done.
Local tests (fake tree, zstd shim, test-only env overrides CLEAN_R/AR/Q/ROWS/FLOOR/GUARD_MIN/IDLE_PAIRS/PY/ZSTD/
SKIP_MOUNT_CHECK): dry-run with FAILs writes nothing; execute refuses on FAILs (exit 2); execute runs step 0 + 4 jobs,
stream sha256 == pin, symlinks/READMEs/listings/pipestatus/manifest/receipt as specified; re-execute skips everything and
keeps the manifest; a wrong pin leaves the source and lists the failure; usage error exits 2.

## Exact commands for the parent to relay (SSM AWS-RunShellScript, i-035994afa8bdf66a5, us-east-1)
Only after the hold log shows the day saved (hold-a2.log: ACTION=status entry_state 'saved'; or ACTION=status):
1. `bash /opt/frankie-box/archive/.logs/clean-a2.sh dry-run`      (prints step 0, preflight PASS/FAIL, the plan with sizes,
   the idle pairs, the estimate; ~6 s; writes nothing)
2. `bash /opt/frankie-box/archive/.logs/clean-a2.sh execute`      (executionTimeout >= 3600: the run is ~10-20 min; or, to
   survive an SSM disconnect, `systemd-run --unit=frankie-clean-a2 --collect -p KillMode=mixed bash /opt/frankie-box/archive/.logs/clean-a2.sh execute`
   and then tail /opt/frankie-box/archive/.logs/clean-a2.log for the CLEAN_RECEIPT line)
Nothing in the script resumes or kicks the queue; the restage + ACTION=resume + kick stay with the parent.

## Expected duration (measured rates) and disk projection
- Rates: root sequential read 1.09-1.25 GB/s (measured on ROOT's own reads tonight); archive volume write cap 1000 MiB/s =
  1.049 GB/s; the Monday 427.3 GB tar.zst took 908 s (00:06:45-00:21:53) = 470 MB/s on a loaded box; zstd -3 -T0 on 10 CPUs
  per job compresses JSONL at >= 1 GB/s input (not the bottleneck); sha256sum on the stream ~1.5 GB/s single thread.
- Archive write total 541.6-611.2 GB (472.04 plain + 69.6-139.1 compressed) -> 516-583 s at the cap; root read 670.8 GB ->
  537-615 s; the two volumes work in parallel. The 472 GB move is one stream (dd|tee|sha256sum): 7.5-8.7 min at 0.9-1.05
  GB/s. Expected wall: 10-13 min; pessimistic 20 min (pipe chain at 0.5 GB/s). The three jobs run side by side; the two
  small zips finish in the first minutes.
- Root volume: 603.2 GB free at 01:45Z while ROOT still writes (projection-v2 + digest, unmeasured; ~16 GB/min at 01:30-01:32Z);
  the clean adds +670.77 GB -> about 1,220-1,270 GB free afterwards (whatever ROOT ends at, plus 670.77).
- Archive volume: 1,725.0 GB free -> 1,113.8-1,183.4 GB free afterwards (peak transient = final; .part becomes the file by
  rename). The 15 GB guard is never approached on either volume; it stays armed anyway.

## Caveats / to relay
1. The frames spool (496.7 GB) STAYS: the teacher opens it through market_timeline._local which refuses symlinks. Moving it
   needs a bind mount (mount --bind <archive copy dir> R/work/derived/.rows, which makes the path a real directory again) or a
   reader change on the restaged tip: Greg's call (b)/(f). The same holds for the 202 GB final ledgers and .projection-v2.
2. The pre-save ledger copy (68.07 GB) is zipped (reversible), against the session-5 "must stay" written while ROOT was
   still able to resume its native stage; it is now byte-redundant with the final ledgers' prefix. Greg may strike it.
3. .ARCHIVED.README.txt files land beside pinned files in recovery-.../ledgers/ and in work/derived/ (plain files, as the
   batch did elsewhere); the data stage catalogs them as withheld BEDROCK state / unpinned, never as evidence.
4. The validator at the restaged boundary should be given the moved-manifest path above (add_manifest) so the moved
   layer's symlink is checked rather than listed as a stray link.
5. ROOT was still in root-digest at 01:45Z with root free falling ~16 GB/min during the projection; 603 GB remain; the
   disk guard is armed. The clean cannot start before the receipt + the save (preflight 2-4).
6. The hold watcher's 30-minute ACTION=status loop (hold-a2.sh, pid 54716) is read-only and does not block the preflight.
