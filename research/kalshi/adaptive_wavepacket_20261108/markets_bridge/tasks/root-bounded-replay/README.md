# Bounded ROOT and SQLite checkpoint

The [receipt](receipt.json) covers the first 6,000 records in the October 18 UTC member, from midnight to about 00:31 UTC. The tape prefix contains 115 trades, one opening reset and 4,489 closed groups. The full October 18 trading session contains 30,739 trades. This checkpoint measures a producer path on a small sample. The three historical repetitions still need full date-bound products.

| ROOT route | Wall time | Total CPU time | Maximum single-process RSS |
| --- | ---: | ---: | ---: |
| Replica shards, three workers | 125.12 s | 311.00 s | 285.3 MiB |
| Single replay, one book worker and two encoders | 158.71 s | 349.37 s | 283.9 MiB |

Use replica shards as the provisional default. This one paired measurement uses a four-core Linux environment. The sample is too small to establish production throughput or peak memory. ROOT published the same ordered frame, price, structure and failure spools in both modes. A stop at next input 2,999 and resume via the saved input-spool offset reproduced all four spools. The timing includes a separate digest read and excludes the interrupted run. Both routes retained about 2.92 GB on disk. The 2.90 GB frame spool accounts for most of it.

The SQLite check independently reassembled F_LAST groups and source membership from tape, compared original wire bytes and integer frame clocks, reconciled all 115 trades and recomputed 4,489 structural family identities. It found 51 first-observed families and passed SQLite integrity. The legacy price spool's floating-point clocks were checked against their declared conversion. SQLite obtains event and receive nanoseconds from the original source indices. Group-close availability is separate from the trade receive time. Family and order identities remain linkage fields.

The October 2 worker-loss test used the first 2,500 records in that UTC member. A killed replica caused one frame to be rebuilt in the main replay and the two surviving shards to restart from the next cursor. All four spools matched the healthy run. The independent SQLite check covered 1,303 groups, 89 trades and 43 first-observed families.

Native passed its pre-traversal gates and stopped before applying records. The pinned Native layout requires eight distinct cores. Default ROOT and Native overlap divides a booked lane in half by physical core, so budget at least 16 distinct physical cores in that lane. The historical October 18 ROOT and Native carriers plus the separate rich second set total about 860 GB uncompressed before the ingest journal, the roughly 35 GB Julia matrix, checkpoints and workspace overhead. The historical run used a 2,048 GiB volume. Scratch must support Linux hard links for receipt publication. Confirm peak aggregate memory and actual scratch on the first representative producer run. Historical Julia fits reached roughly 26 GiB each, so concurrent fitting needs separate admission against headroom.

## Repeat the local checkpoint

Stage the verified runtime source at `db96f24f3260bf0d70c763b297c2ba9b84f571a6` into a Linux scratch tree. Place the `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134` producer tree in `producers`. In a separate `root-producers` overlay, expose that tree's `research/kalshi/frankie_raw_mbo_benchmark` and `research/kalshi/agents` paths and install the ROOT adapter from `af36937d1e478831d4c7bc612c98d969e9a0848b` at `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`. The [receipt](receipt.json) carries the adapter digests and the comparison runtime versions. Keep the Native adapter at its own pin. An optional `root-producers-candidate` overlay takes the [ROOT queue-age patch](../root-native-efficiency-patches/root-queue-ages.patch) and its own output directory.

From the current repository, stage the prefix to an existing scratch path. Copy the two Python checkpoint scripts into the staged runtime tree beside the prefix files. Run on a Linux filesystem with at least two distinct booked cores.

```text
python -B -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.stage_root_prefix 20231018 --records 6000 --output <scratch>
```

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -B bounded_root.py 20231018 unused --prepare
FRANKIE_ROOT_LEGACY_FRAME_SHARDS=on /usr/bin/time -v python -B bounded_root.py 20231018 out/sharded
FRANKIE_ROOT_LEGACY_FRAME_SHARDS=off /usr/bin/time -v python -B bounded_root.py 20231018 out/single
FRANKIE_ROOT_LEGACY_FRAME_SHARDS=off python -B bounded_root.py 20231018 out/resume --save
FRANKIE_ROOT_LEGACY_FRAME_SHARDS=off python -B bounded_root.py 20231018 out/resume
cmp out/sharded/spool-comparison.json out/single/spool-comparison.json
cmp out/sharded/spool-comparison.json out/resume/spool-comparison.json
python -B check_sqlite.py 20231018 out/sharded out/checked-clock.sqlite
```

For the worker-loss check, stage the October 2 prefix with `--records 2500`, prepare its journal, then run replica mode in two fresh directories. Pass `--drop-shard-at 200` in the second run and compare the spool receipts. The harness requires the fallback to report one lost worker.

The offline journal used here carries actual INPUT records for the ROOT comparison. The rich teacher producer requires a sealed compact ingest with the full-book APPLIED operand. The pinned `--mode parallel --observation none` ingest path leaves that operand unavailable, and the teacher reports `equation_not_run` even when it can open shared ROOT. Use one full-observation compact ingest per approved date so the teacher and ROOT can consume the same seal. A benchmark prefix and its SQLite clocks are separate evidence from the full-date admission. [Discovery manifests](../discovery-block-manifests/README.md)
