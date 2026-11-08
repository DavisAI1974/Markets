# Discovery ingest manifests

Each manifest names the exact DBN member bytes at `1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202`. The archived block manifests contain different compressed object hashes. These manifests bind the Git members to newly verified scope identities. All three dates are discovery data. The October 18 reference remains a discovery date in the later four-date run.

| Trading date | Selected source | Records | Closed groups |
| --- | --- | ---: | ---: |
| October 2 | October 2 UTC midnight snapshot through the halt | 808,453 | 600,291 |
| October 3 | 4,889 records from the October 2 UTC tail followed by 874,941 from October 3 | 879,830 | 653,912 |
| October 17 | October 17 UTC midnight snapshot through the halt | 841,601 | 635,170 |

The manifests were checked by the pinned `block_source_scope`, `partial_takes` and `tail_skips` readers. The counts were checked directly from the tape by original record order and F_LAST. Reproduce with `python -B -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.stage_discovery_block_manifests --output <empty-directory>`.

Stage the three named compressed members under `data/nymex_mbo/ng_v0_oct2023` at the tape revision into one local sources directory. Keep the filenames and verify each manifest size and SHA-256. Supply that directory to the pinned ingest and publish into a fresh directory per date. The `--sources-dir` route uses local files. The compact journal includes the full-book observation required by the rich second set.

```bash
python -m research.kalshi.frankie_boss.operations.ingest_block_sources \
  --manifest <date-manifest> --sources-dir <local-dbn-directory> \
  --output-dir <date-ingest-directory> --session-policy cme_trading_day \
  --writer compact --mode sequential --observation full --workers <encoder-workers>
```

Set the encoder worker count from the booked CPU lane. The ordered replay applies the market records while the compact writer's workers encode independent blocks.

October 3 can take October 2's verified closing book through `--opening-receipt` after the source and adapter state match. The default first-member warmup provides the same scope when a compatible receipt is unavailable. The partial dates start at the recorded midnight snapshot. Preserve the explicit partial scope on all downstream receipts.
