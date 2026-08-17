# ChatGPT Handoff — NG Exhaustion S3 + NOVA Reducer

Status: **S3 PUBLISHED + SHA-VERIFIED; NOVA JOB-SPECIFIC REDUCER PROVEN LOCALLY; permanent Frankie untouched.**

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/ng-exhaustion-runway-clock-20260817`
Prior handoff: `CHATGPT_HANDOFF_NG_EXHAUSTION_RUNWAY_CLOCK_V0_20260817.md`
Final S3 publication proof: `research/NG_EXHAUSTION_S3_PUBLISH_PROOF_20260817.json`

## Why this step happened

The full frozen blind-record JSON member is 22,104,694 bytes for 1,711 records. The large-batch benchmark showed parsing/transport costs materially more than the deterministic runway math. Greg directed large exhaustion data to AWS/S3 and asked whether DavisAI NOVA can reduce the model-facing payload.

## S3 data plane — COMPLETE

Existing Markets doctrine was reused unchanged:

- Git = code/docs/records;
- S3 = data;
- local = disposable cache;
- `research/kalshi/platform_sync.py` is the one sanctioned S3 write door;
- bucket = `bento-568968024170-us-east-2-an`.

NG exhaustion V0 is now published at:

`nymex/ng_exhaustion/v0/`

GitHub Actions used the existing repository secrets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`; secret values were never printed or written into artifacts.

### Publication workflow

Workflow:
`.github/workflows/ng_exhaustion_s3_publish_v0.yml`

Final publication run:

- run ID: `31995977689`
- triggering SHA: `363f59a7b19e0dd8d7ee5ac96555d6b483132945`
- conclusion: `success`
- proof artifact ID: `9276834723`
- proof artifact digest: `sha256:5bc486b5a13134efe59e4c7a21cd033e05d5a5577273d72cc96cdc0074fb7885`

The workflow:

1. resolves the AWS secret names without exposing values;
2. downloads exact frozen artifact `9274443976` with the GitHub token;
3. verifies source SHA `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`;
4. runs the full isolated clock/replay/S3-stage regression gate;
5. builds the deterministic stage;
6. uploads only through `platform_sync.py`;
7. independently downloads every S3 object and verifies byte count + SHA-256;
8. verifies the prefix inventory manifest contains exactly the six staged data objects;
9. emits a non-secret publication proof artifact.

### Frozen canonical source

Canonical S3 object:

`canonical/ng_exhaustion_blind_input_artifact_9274443976.zip`

- bytes: `2,238,990`
- SHA-256: `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`

This is byte-identical to the original frozen blind-input Actions artifact and remains authoritative source truth.

### Frozen day partitions

Read-optimized V0 derivatives are fixed across Python 3.11/3.13 by normalizing the gzip OS header and pinning the compressed SHA. Any future compression/runtime drift fails closed.

- `partitions/day=20250717/records.jsonl.gz` — 420 records, 258,275 bytes, SHA `5a475a45629fe25fb1b782b0ed79b9cfec68daa8b67c080b22eddb9af22b419b`
- `partitions/day=20250923/records.jsonl.gz` — 446 records, 478,500 bytes, SHA `e7149ce7967ca6251928a41ca45197b47fcee00f926484adac8c7895bcddf6c2`
- `partitions/day=20250930/records.jsonl.gz` — 428 records, 473,415 bytes, SHA `41086c62725b26f1eef80c405bc4ebc49feebaf9db49f6f49ead1e6e3fbcc102`
- `partitions/day=20251001/records.jsonl.gz` — 417 records, 481,401 bytes, SHA `739a352e03b0da9dffa0177251ceab6a7f18e73b48da35b29ff79975388da6e7`

Total partition bytes: `1,691,591` for 1,711 records.

Final S3 `content_manifest.json`:

- bytes: `5,426`
- SHA-256: `0ee7841cdc08e49454d3eb0af936102f82b76c72f2b49c1b4ba01fd06e7c4128`

The `platform_sync.py` prefix manifest reports exactly six staged objects and writer `platform_sync.py`. Including that inventory `manifest.json`, the V0 prefix contains exactly seven objects.

### S3 staging implementation

Added/updated:

- `research/ng_exhaustion_s3_stage.py`
- `tests/test_ng_exhaustion_s3_stage.py`
- `research/NG_EXHAUSTION_S3_STAGE_PROOF_20260817.json` (historical local staging proof)
- `research/NG_EXHAUSTION_S3_PUBLISH_PROOF_20260817.json` (final remote read-back truth)
- `.github/workflows/ng_exhaustion_s3_publish_v0.yml`

The stage fails closed on source artifact SHA, classifier SHA, record/family/day counts, outcome-wall invariants, canonical gzip bytes, and pinned partition SHAs.

## NOVA reducer work

Greg directed a job-specific clone/derivative of `DavisAI1974/Nova-Optimizer` rather than changing the generic reducer globally.

Source NOVA main commit used:

`77aa7eaac492005717992c573da4929e782a801d`

Direct clone was blocked by the runtime DNS, so the connected GitHub API was used as the source transport. The GitHub integration can read NOVA but returned HTTP 403 for branch/tree writes; no change was pushed to NOVA `main`.

### Why generic NOVA is not used directly

The generic `NovaCompressor` removes underscores and truncates long keys. That is unacceptable for frozen Markets evidence because protected-key collision/semantic loss must fail closed.

### Job-specific NOVA contract

The proven local patch adds:

- `markets_ng_exhaustion.py`
- `markets_ng_exhaustion_cli.py`
- `benchmark_markets_ng_exhaustion.py`
- `tests/test_markets_ng_exhaustion.py`
- `MARKETS_NG_EXHAUSTION_REDUCER.md`
- `MARKETS_NG_EXHAUSTION_REDUCER_BENCHMARK_20260817.json`

Two representations exist:

1. `LosslessClockCodec`
   - explicit V0 key alias table;
   - string values preserved verbatim;
   - exact full clock-output round trip required;
   - unknown V0 fields fail closed.

2. `FrankieRunwayPacket`
   - compact model-facing projection;
   - S3 source/hash/classifier provenance once per batch;
   - preserves event/session/t0, family/post-state, state timing, all four total/remaining runways, exhaustion flags, basis/base confidence, microstructure/confidence modifier, gaps/reasons/falsifier state, and `future_price_accessed=false`;
   - full curves/repeated audit text stay recoverable from canonical S3 instead of consuming context;
   - protected-field exact round trip required;
   - hash/schema/enum/future-price drift fails closed.

### NOVA real-corpus proof

Tested on all 13,688 actual V0 clock outputs from the 1,711-record corpus at checkpoints `0, 30, 59.999, 60, 300, 900, 1802, 7200`:

- canonical full clock JSON: `28,655,140` bytes
- exact full-payload codec: `20,948,796` bytes (`26.893%` smaller)
- Frankie-facing NOVA packet: `1,909,199` bytes (`93.337%` smaller)
- average model packet row: `~139.44` bytes
- full-codec round-trip failures: `0`
- protected packet round-trip failures: `0`
- future-price flags: `0`

NOVA's rough `characters/4` estimate gives ~7.16M canonical tokens vs ~477k Frankie-packet tokens. These are rough NOVA estimates, not a claim about any model-specific tokenizer.

Hot-path `pack_batch`, including protected round-trip verification:

- 1 row: ~0.085 ms median
- 1,711 rows: ~95.7 ms median
- 13,688 rows: ~989 ms median

Local NOVA patch archive SHA-256:

`3f4bcf60783f6a2b05e4f0a06f75d89928a2d8b5397993a58395fc3c4f31cdbd`

Do not bypass NOVA repo permissions by committing directly to `main`. When write access exists, create a feature branch from `77aa7eaa...`, apply the proven patch, and rerun the real-corpus benchmark.

## Intended runtime architecture

`S3 canonical day partition -> SHA verify -> one deterministic exhaustion clock -> NOVA FrankieRunwayPacket -> Frankie direction/magnitude reasoning`

Rules:

- S3 canonical source is authoritative.
- NOVA packets are derived/disposable model views, never canonical data.
- One deterministic exhaustion worker remains sufficient based on the large-batch benchmark.
- Optimize partition reads/serialization before adding workers.
- Do not use AI agents to calculate deterministic exhaustion math.
- Do not change frozen classifier or reveal baselines as part of storage/NOVA work.
- Do not merge permanent Frankie brain/schema in this step.

## Current stop point / next build

**S3 work is complete.** The frozen corpus and read-optimized partitions are now on AWS and independently SHA-verified.

The next build should be the isolated S3-backed read path / near-live overlay:

1. fetch only the relevant day/leg partition from `nymex/ng_exhaustion/v0/` with local cache;
2. SHA-verify against `content_manifest.json` before serving it;
3. run the single deterministic clock;
4. emit the job-specific NOVA `FrankieRunwayPacket` once the NOVA patch is landed or vendored behind the same protected contract;
5. observe it live/near-live before any permanent Frankie brain merge.

Permanent Frankie remains untouched.
