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
