# Lossless compression for replay scratch

Use a dedicated Linux Btrfs scratch filesystem with `compress=zstd:1` for live ROOT frame and ledger files. Btrfs compresses file extents while the applications continue to use normal paths, logical byte offsets and ordinary file reads. Keep copy-on-write and data checksums enabled. Keep each producer's files and its publication staging directory on the same filesystem for hard links and atomic publication. [Btrfs compression documentation](https://btrfs.readthedocs.io/en/latest/Compression.html)

The October 2 test ran the pinned ROOT producer from scratch and then with a stop and resume at source record 1,249. Both runs matched the ext4 frame, structure, price and failure spool hashes. The existing checkpoint sought to its saved input offset. Seven direct frame reads from the resumed spool matched the same logical offsets and lengths after a read-only remount. SQLite reconciled 2,500 input records, 1,303 structures, 89 trades and 43 first-observed families. The two ROOT frame files represented 1.59 GB of logical bytes. Btrfs reported 123 MB used across the isolated test volume after both runs and the SQLite check, including filesystem metadata. That is final occupied space for this sample. [Compression receipt](compression-receipt.json)

Separate Zstandard level 1 archives of the sealed ROOT frames also passed full decoded SHA-256 and size checks.

| ROOT prefix | Original frame bytes | Archive bytes |
| --- | ---: | ---: |
| October 2 | 796,297,501 | 44,122,358 |
| October 18 | 2,903,246,916 | 164,920,866 |

Use standalone archives for retention or transfer. Restore and verify the logical file before an existing consumer opens it by byte offset. Reproduce the archive check with `python -B measure_compression.py <sealed-frames.jsonl> <expected-logical-sha256> <new-archive.jsonl.zst>`. The compact ingest journal and Native projection artifacts already use compressed storage formats.

## First execution-host check

1. Confirm the scratch mount with `findmnt -n -o FSTYPE,OPTIONS --target <scratch>`. Check the production filesystem, kernel, volume type and COW settings before staging the replay.
2. Repeat the [bounded ROOT check](README.md) with output paths on that scratch mount. Run the matching Native and rich second-set prefixes there and exercise their normal stop and resume paths. Compare source and output hashes and indexed reads before admitting full dates.
3. Measure peak physical use on the isolated volume through checkpoints and publication using `btrfs filesystem usage -b <scratch>` or free-space deltas. On the test volume, the per-file `stat` block count reflected logical size, while Btrfs volume accounting captured compression. Record aggregate CPU and wall time during overlap separately from the stored size.

The local test covered ROOT only. Native and the rich second set still need a compressed-scratch canary on the execution host. Use the existing storage allowance until that canary measures their output, checkpoint and publication peaks. Keep the Native core and Julia memory requirements from the [replay runbook](../../../../../../tasks/family-research-20261022/three-date-replay-runbook.md) when planning concurrent dates.
