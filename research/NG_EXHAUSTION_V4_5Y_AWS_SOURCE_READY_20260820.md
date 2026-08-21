# NG Exhaustion V4 — Five-Year AWS/S3 Source Wiring (2026-08-20)

## Scientific scope

The purpose of the five-year pass is to group exhaustion events into chain families and then determine the exact architecture and characteristics of those exhaustion events. It is **not** a generic classification exercise, and the invalid V3 empirical runs are not a basis for this work.

Frankie himself is excluded from exposure to this research run. The source plumbing below does not read, modify, or learn from permanent Frankie.

## Five-year source of truth

The historical native MBO corpus is in AWS:

- Region: `us-east-2`
- Bucket: `bento-568968024170-us-east-2-an`
- Prefix: `nymex/ng_mbo_5y_v0/`
- Consolidation marker: `nymex/ng_mbo_5y_v0/_consolidation/COMPLETE.json`
- Durable EC2 documented by the repository: `i-08cee7171c0a76a04`
- Repository path on EC2: `/opt/markets`

The current compact archive audit reports 61/61 expected intervals with jobs, zero missing intervals, zero unresolved reservations, 102 native DBN objects and 1,470,112,040 native DBN bytes. It also reports three exact duplicate intervals and four unexpected partial-August overlaps. For that reason, the new source resolver refuses a naive prefix-wide enumeration.

## New additive source contract

`research/ng_exhaustion_mbo_5y_aws_source_20260820.py`

This script:

1. reads the consolidation manifest (or an explicit object manifest);
2. accepts only an explicit canonical/selected/native DBN object list;
3. fails closed when no exact list is present or same-tier selections conflict;
4. inventories exact S3 objects with `head-object`;
5. optionally stages only those keys to local EC2 storage;
6. writes a deterministic source receipt;
7. never launches the empirical census itself.

No old 54/55-week corpus is used.

Example inventory-only command on the durable EC2:

```bash
cd /opt/markets
git fetch origin
git checkout chatgpt/ng-exhaustion-entry-timing-revival-20260818
python research/ng_exhaustion_mbo_5y_aws_source_20260820.py --inventory-only
```

If `_consolidation/COMPLETE.json` does not itself expose an exact canonical DBN list, the command intentionally stops. Supply a curated exact JSON manifest with `--object-manifest`; do **not** replace that failure with `aws s3 ls` over the whole prefix.

## Full V4 native state

The already-validated adapter, `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`, reconstructs the native MBO book and FIFO queues. Its ordinary serialized per-F_LAST event frame is deliberately compact: top-10 levels plus aggregate full-depth metrics.

That compact serialization must not be mistaken for the information available to V4.

`research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py` is the additive bridge for the five-year research engine. At every completed event group it exposes:

- the compact event frame;
- full reconstructed bid and ask depth;
- every resting FIFO queue represented by the adapter;
- per-order size, volume ahead, priority receive time/sequence/age;
- rolling add/cancel/modify/trade/fill activity;
- native source/clock context;
- `ts_recv_ns` as causal availability.

The downstream chain-family engine should import `replay_dbn_files()` and consume each full-state envelope in process. Full books do not need to be serialized at every tick just to remain available; native DBN remains canonical and replayable.

## What this checkpoint does not do

- It does not run the five-year empirical census.
- It does not group chain families yet.
- It does not import the old V3 training/evaluation machinery.
- It does not mutate the frozen detector, frozen canonical evidence, frozen runway clock, Phase-1/Phase-2 artifacts, permanent Frankie, Frankie 1, or `spawn.py`.
- It does not prove the `LEGACY_CONTROL` projection equivalent to the historical legacy corpus.
- It does not choose between duplicate/overlapping S3 objects unless an explicit canonical manifest does so.

## Next execution steps

1. Pull the exact committed branch checkpoint on `i-08cee7171c0a76a04`.
2. Run the new AWS source resolver in `--inventory-only` mode.
3. Inspect the resulting exact object receipt. If consolidation does not provide a canonical list, create an explicit curated object manifest from the consolidation/job provenance; do not enumerate the entire prefix.
4. Stage a bounded canonical slice and exercise the native full-state replay.
5. Verify source/contract/clock continuity and the `LEGACY_CONTROL` compatibility projection where overlap evidence exists.
6. Only then connect the full-state replay to the V4 chain-family grouping/architecture engine.
7. Preserve every case. Negative, short-lived, censored, disagreement, and no-lock cases are findings, not discarded “failures.”
8. Run the full five-year census only after the exact candidate/source manifest and research rules are frozen and explicitly authorized.
