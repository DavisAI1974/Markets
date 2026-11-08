# October replay publication and shutdown

This is the operations log for the three original RunPod replays. The [October discovery log](october-discovery-log.md) records the research context. All dates remain discovery.

| Trading date | Tape coverage | Original pod | Producer and export status at 20:20 UTC on November 8, 2026 | Git evidence |
| --- | --- | --- | --- | --- |
| 20231002 | Partial from the UTC snapshot | `skqgzuaskb6d10` | ROOT tables retained. Native input pass complete. Native member projection running. Standalone waiting. ROOT frame archive sealed in 211 parts. | [Interim ROOT tables and index](flow-book-discovery-v1/date-tables/20231002) |
| 20231003 | Full session | `902unhjrkncf8c` | ROOT tables retained. The recovery watcher resumed Native after the Python shared-memory error. Native reached 817,078 of 879,830 input records. Standalone waiting. ROOT frame archive started. | [Interim source index](flow-book-discovery-v1/date-tables/20231003) |
| 20231017 | Partial from the UTC snapshot | `9m9fubscvdgow5` | ROOT tables retained. The recovery watcher resumed Native after the Python shared-memory error. Native input pass complete. Native finalization running. Standalone waiting. ROOT frame archive sealed in 243 parts. | [Interim ROOT tables and index](flow-book-discovery-v1/date-tables/20231017) |

For each date, the source ingest is under `/opt/frankie-box/work/ingest-ng-replay-YYYYMMDD`, the control folder under `/opt/frankie-box/replay-control/YYYYMMDD`, the ROOT and Native outputs under `/opt/frankie-box/work/experiment-roots/ng-replay-YYYYMMDD`, and the standalone exports under `/opt/frankie-box/work/standalone-inputs/YYYYMMDD`. The original jobs share volume `qu5lhaqqbx`.

The input source manifests are `research/kalshi/frankie_boss/blocks/BLOCK_YYYYMMDD_SOURCE_MANIFEST.json` in the runtime checkout. ROOT runtime is `6f9178bbb97721c7a71e94bb602ac256db348c87`, the pinned producer is `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`, and the queued standalone checkout is `f06e8e90f1c44c7fa833dabfcf921969927419fc`. All three dates use the compatibility launcher from `c858547a0768462b56fab0756e0c848cb125b30d`. [Runtime and recovery details](runpod/discovery-execution-20261108.md)

For final publication, reuse the already published compact ROOT bytes. Save each date's remaining unique outputs after the producer and standalone writer finish. The October 2 ROOT frame spool alone is 520,064,232,895 uncompressed bytes, so its Git representation requires a lossless archive split into parts. Record the source path, original byte count, ordered archive parts and restoration command. Keep each ordinary Git blob below the 100 MB file limit and push batches below 2 GiB. The final commit must point to the saved files and their coverage before shutdown. [GitHub repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)

All three pods were still running required work at the observation above. Record each final publication commit and the confirmed pod stop or termination separately here. Keep the shared volume mounted for active dates.

October 2 began preparing the lossless archive of its finalized ROOT frame
spool at 20:20 UTC while Native was still running. Archive parts are staged
on the shared volume at `/opt/frankie-box/work/git-publication/20231002/root-frames`
once the writer closes the archive and publishes its part checksums and
source record. The resulting parts are one zstd stream. Restore the original
file with `cat frames.jsonl.zst.part-* | zstd -d -c > frames.jsonl`.
[Frame archive command](runpod/runpod_archive_root_frames.sh)

At 20:20 UTC the October 2 frame archive began transfer for Git publication.
The [publisher](runpod/publish_root_frame_archive.py) reads the sealed
part list, reuses existing verified blobs and adds batches under
`replay-artifacts/YYYYMMDD/root-frames`. It publishes the source record and
part checksums only after all the parts are present on the shared branch.

## Completion gate correction — November 8 continuation

`october18_inputs.py` only seals the input directory. Its receipt explicitly
keeps `full_discovery_gate=NOT_PASSED`. The separate decision runner takes the
file `standalone-inputs/YYYYMMDD/groups.jsonl.gz` as `--input`, not its parent
directory. The existing standalone waiter now runs that decision step under
the same per-date `standalone.lock`, after ROOT/Native and the input export.
It reuses a retained input directory and never launches a second export for it.

[Decision sealer](runpod/runpod_seal_touch_print.py) invokes the unchanged
`discovery_touch_print.py --day YYYYMMDD --input .../groups.jsonl.gz --output .../decisions.jsonl.gz`.
It compares the actual consumed group/print counts with the sealed input counts,
then atomically exposes `/opt/frankie-box/work/standalone-decisions/YYYYMMDD/`
containing `decisions.jsonl.gz` and `receipt.json`. The latter retains the actual
decision summary, row count, source identity, runner digest and output digest.
A failed or incomplete run cannot expose a completed result directory.
The producer and input-export source/runtime revisions above remain unchanged.

The final standalone status is now `touch-print-decisions-sealed`.
`standalone-inputs-sealed` alone never completes a date. The existing
`verify-markets-replay-receipts` heartbeat owns publication and shutdown and
has been updated to enforce this requirement. Before shutdown it must save
both input files, both decision files, required ROOT/Native outputs, and the
deployed gate code, confirm their presence on the shared Git branch, and
confirm the original pod has no required work. This is workflow completion,
not scoring admission or a claim that downstream research is complete.

At 20:27 UTC all three producers were still in `root-native`; their input
waiters were waiting. No new decision result existed yet. The October 2
ROOT publisher was still running as local Python PID 48372 against
`F:/MarketsReplayPublication/Markets.git`; no second publisher was started.
Deployment and actual per-date output observations follow below.

At 20:31 UTC gate commit `245bb7251` was deployed to the shared directory
`/opt/frankie-box/replay-control/touch-print-gate-245bb7251`. Each original
waiter was paused, confirmed to be waiting with only a sleep child, and
replaced on its original pod. New waiter PIDs are 5461 / 2650 / 2359 for
October 2 / 3 / 17. Each holds the existing `standalone.lock`. Producers
4402 / 2151 / 1790 continued unchanged. The original standalone bundle is
still `standalone-f06e8e90f`. Recovery uses the deployed waiter path with
arguments `YYYYMMDD /opt/frankie-box/replay-control/standalone-f06e8e90f`.

Seven focused local tests passed, including running the actual decision CLI
against a sealed fixture, refusing a group-count mismatch or wrong date,
refusing missing output, and reusing a completed result. The four sealer
tests also passed on the pod's Python runtime. Bash syntax and deployed
source hashes were checked. These fixture tests do not claim real-date
decision completion.

At 20:33 UTC Native projection was 17.63% for October 2 and 4.67% for
October 17; October 3 Native input processing was 99.02%. These percentages
describe only the named stage. All three progress files reported zero
failures, all three waiters remained queued, and none had actual decision
output yet. No pod was stopped. The existing heartbeat remains the sole
publication/shutdown owner. [Deployment and progress snapshot](runpod/touch-print-gate-deployment-20261108.json)

## Projection CPU recovery — 20:44–20:46 UTC

The user's timing comparison with October 18 exposed an actual placement bug.
All three projection worker maps had a one-CPU lane and one helper sharing the
coordinator's CPU. The pod shell held 32 CPUs over 16 physical cores, and the
projection helper was CPU-bound. October 2 and 17 were reading their 200.62 GB
and 224.02 GB member ledgers at about 18–19 MB/s. October 3 subsequently reached
the same one-helper configuration for its 221.90 GB ledger. This was the Native
projection stage; the standalone touch/print export had not started.

The lane cache was first populated after the Native coordinator narrowed its
own affinity. [Bootstrap fix `8ff32c2f5`](runpod/runpod_root_bootstrap.py) captures
the full pod allocation before producer imports or execution. The pinned ROOT,
Native calculators and projection source remain unchanged, so existing input
identities, Native seals and projection range bindings remain valid. The
regression test reproduces a narrowed one-CPU cache with the original bootstrap
and passes with the fix, using the actual pinned lane module.

The bootstrap is deployed at `/opt/frankie-box/replay-control/runpod_root_bootstrap.py`.
Under each existing date lock and an additional short recovery lock, the
[recovery script](runpod/runpod_resume_projection_lane.py) replaced only the
undersized projection process tree. The nohup coordinator ignores SIGINT and
defers SIGTERM until after projection, so the sole helper received SIGTERM;
`BrokenProcessPool` then unwound ROOT and released its locks. That expected
recovery exception is preserved in each `root.pre-lane-OLDPID.log`.
No producer replacement was launched until the old root exited and its date
lock was available. Waiters were suspended during that handoff and resumed.

| Date | Old ROOT | New ROOT | Retained completed member ranges | New helpers |
| --- | ---: | ---: | ---: | ---: |
| October 2 | 4402 | 5825 | 721 | 31 |
| October 3 | 2151 | 2768 | 117 | 31 |
| October 17 | 1790 | 2473 | 366 | 31 |

All three logs confirm completed Native results reused in place with no
traversal or finalization replay. Their `native-stage.json` modification times
are unchanged. Completed ranges are reused; any unreceipted interrupted range
remains retained and receives a separate attempt file. Live affinity readback
confirms every helper matches its assigned CPU. The standalone decision gate,
archive publisher, shared volume and shutdown requirements are unchanged.

For the comparison: October 18's saved standalone input receipt reports
601 seconds (about ten minutes). That small export is a different stage from
the hundreds-of-gigabytes Native projection that was stalled on one CPU here.
The previous 3–5-hour computation estimate measured that defective placement
and should not be used after this recovery.

[Before/after worker maps, retained ranges and throughput observations](runpod/projection-lane-recovery-20261108.json)

At 20:50 UTC, the first October 2 Git push had exhausted four attempts
because the shared branch moved during each transfer. Its eight hashed
parts were retained in the local publisher and reused for a push to
`codex/replay-archive-20231002`. The updated publisher stages each date
under its own ref, then adds the verified archive tree to the latest
shared branch. The final shared publication remains required for shutdown.
