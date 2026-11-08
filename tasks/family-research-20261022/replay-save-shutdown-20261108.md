# October replay publication and shutdown

This is the operations log for the three original RunPod replays. The [October discovery log](october-discovery-log.md) records the research context. All dates remain discovery.

| Trading date | Tape coverage | Original pod | Producer and export status at 18:35 UTC on November 8, 2026 | Git evidence |
| --- | --- | --- | --- | --- |
| 20231002 | Partial from the UTC snapshot | `skqgzuaskb6d10` | ROOT tables retained. Recovered Native reached 221,622 of 808,453 input records. Standalone waiting. | [Interim ROOT tables and index](flow-book-discovery-v1/date-tables/20231002) |
| 20231003 | Full session | `902unhjrkncf8c` | ROOT tables retained. The recovery watcher resumed Native after the Python shared-memory error. Native reached 42,246 of 879,830 input records. Standalone waiting. | [Interim source index](flow-book-discovery-v1/date-tables/20231003) |
| 20231017 | Partial from the UTC snapshot | `9m9fubscvdgow5` | ROOT tables retained. The recovery watcher resumed Native after the Python shared-memory error. Native reached 135,515 of 841,601 input records. Standalone waiting. | [Interim ROOT tables and index](flow-book-discovery-v1/date-tables/20231017) |

For each date, the source ingest is under `/opt/frankie-box/work/ingest-ng-replay-YYYYMMDD`, the control folder under `/opt/frankie-box/replay-control/YYYYMMDD`, the ROOT and Native outputs under `/opt/frankie-box/work/experiment-roots/ng-replay-YYYYMMDD`, and the standalone exports under `/opt/frankie-box/work/standalone-inputs/YYYYMMDD`. The original jobs share volume `qu5lhaqqbx`.

The input source manifests are `research/kalshi/frankie_boss/blocks/BLOCK_YYYYMMDD_SOURCE_MANIFEST.json` in the runtime checkout. ROOT runtime is `6f9178bbb97721c7a71e94bb602ac256db348c87`, the pinned producer is `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`, and the queued standalone checkout is `f06e8e90f1c44c7fa833dabfcf921969927419fc`. All three dates use the compatibility launcher from `c858547a0768462b56fab0756e0c848cb125b30d`. [Runtime and recovery details](runpod/discovery-execution-20261108.md)

For final publication, reuse the already published compact ROOT bytes. Save each date's remaining unique outputs after the producer and standalone writer finish. The October 2 ROOT frame spool alone is 520,064,232,895 uncompressed bytes, so its Git representation requires a lossless archive split into parts. Record the source path, original byte count, ordered archive parts and restoration command. Keep each ordinary Git blob below the 100 MB file limit and push batches below 2 GiB. The final commit must point to the saved files and their coverage before shutdown. [GitHub repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)

All three pods were still running required work at the observation above. Record each final publication commit and the confirmed pod stop or termination separately here. Keep the shared volume mounted for active dates.
