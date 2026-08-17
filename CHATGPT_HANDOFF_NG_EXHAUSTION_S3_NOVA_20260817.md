# ChatGPT Handoff — NG Exhaustion S3 + NOVA Reducer

Status: S3 STAGING PROVEN; NOVA JOB-SPECIFIC REDUCER PROVEN LOCALLY; S3 PUT NOT EXECUTED IN THIS RUNTIME. Permanent Frankie remains untouched.

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/ng-exhaustion-runway-clock-20260817`
Prior handoff: `CHATGPT_HANDOFF_NG_EXHAUSTION_RUNWAY_CLOCK_V0_20260817.md`

## Why this step happened

The full frozen blind-record JSON member is 22,104,694 bytes for 1,711 records. The large-batch benchmark showed parsing/transport is materially more expensive than the deterministic runway math. Greg therefore directed large exhaustion data to AWS/S3 and asked whether the DavisAI NOVA token reducer can reduce the model-facing payload.

## Existing AWS doctrine reused

Do not create a second S3 uploader.

`research/kalshi/platform_sync.py` is already the canonical one-way/auditable door between local cache and S3:

- Git = code/docs/records;
- S3 = data;
- local = disposable cache;
- bucket = `bento-568968024170-us-east-2-an`;
- per-prefix `manifest.json` is written by `platform_sync.py`.

NG exhaustion V0 uses new data prefix:

`nymex/ng_exhaustion/v0/`

## S3 staging implementation

Added:

- `research/ng_exhaustion_s3_stage.py`
- `tests/test_ng_exhaustion_s3_stage.py`
- `research/NG_EXHAUSTION_S3_STAGE_PROOF_20260817.json`

The staging script consumes the exact frozen GitHub Actions input artifact and classifier. It fails closed unless both exact hashes match:

- blind input artifact ID = `9274443976`
- blind input artifact SHA-256 = `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`
- frozen classifier SHA-256 = `698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9`

It preserves the exact 2,238,990-byte ZIP as the canonical S3 source object and produces deterministic read-optimized JSONL.GZ day partitions.

Partition proof:

- 20250717: 420 records, 258,275 bytes compressed, SHA `5a475a45629fe25fb1b782b0ed79b9cfec68daa8b67c080b22eddb9af22b419b`
- 20250923: 446 records, 478,500 bytes compressed, SHA `e7149ce7967ca6251928a41ca45197b47fcee00f926484adac8c7895bcddf6c2`
- 20250930: 428 records, 473,415 bytes compressed, SHA `41086c62725b26f1eef80c405bc4ebc49feebaf9db49f6f49ead1e6e3fbcc102`
- 20251001: 417 records, 481,401 bytes compressed, SHA `739a352e03b0da9dffa0177251ceab6a7f18e73b48da35b29ff79975388da6e7`
- total partitions: 1,691,591 compressed bytes / 1,711 records

Staging tests: 3/3 PASS, including source SHA drift rejection and repeated-build partition-hash identity.

The staged directory includes `content_manifest.json` with source/member/classifier hashes and all partition hashes. This is distinct from the S3 prefix `manifest.json` that `platform_sync.py` writes.

Canonical upload command from a credentialed Markets runtime:

`python research/kalshi/platform_sync.py push --prefix nymex/ng_exhaustion/v0/ --src data/ng_exhaustion_s3_stage --execute --note 'NG exhaustion V0 canonical blind source + deterministic day partitions'`

This ChatGPT runtime has neither AWS credentials nor an AWS/S3 connector, so the actual PUT/read-back was not executed here. Do not record it as uploaded until `platform_sync.py` reports verified objects + manifest from a credentialed runtime.

## NOVA reducer work

Greg directed a clone of `DavisAI1974/Nova-Optimizer` and changes specific to this exhaustion job.

Direct `git clone` is blocked in this runtime by outbound DNS. The connected GitHub API was used as the source transport from NOVA `main` at commit:

`77aa7eaac492005717992c573da4929e782a801d`

A job-specific local NOVA patch was built rather than changing the generic compressor globally.

### Why the generic compressor is not used directly

The existing generic `NovaCompressor` removes underscores and truncates long keys. That is acceptable for generic token optimization but not for frozen Markets evidence where a protected key collision or semantic loss must fail closed.

### Job-specific NOVA contract

The local patch adds:

- `markets_ng_exhaustion.py`
- `markets_ng_exhaustion_cli.py`
- `benchmark_markets_ng_exhaustion.py`
- `tests/test_markets_ng_exhaustion.py`
- `MARKETS_NG_EXHAUSTION_REDUCER.md`
- `MARKETS_NG_EXHAUSTION_REDUCER_BENCHMARK_20260817.json`

Two representations are implemented:

1. `LosslessClockCodec`
   - explicit frozen V0 key alias table;
   - string values preserved verbatim;
   - exact full clock output round-trip required before emission;
   - unknown V0 fields fail closed.

2. `FrankieRunwayPacket`
   - compact model-facing projection only;
   - full S3 bucket/key, source SHA and classifier SHA appear once in a batch header;
   - per-row fixed columns + explicit enum tokens;
   - preserves event/session/t0, family/post-state, state timing, all four total/remaining runways, exhausted flags, basis/base confidence, microstructure/confidence modifier, gaps, reason codes, falsifier state and `future_price_accessed=false`;
   - full normalized curve and repeated audit/render text remain recoverable from canonical S3 and are not repeated in model context;
   - protected projection exact-round-trip required before emission;
   - hash/schema/enum/future-price drift fails closed.

### NOVA real-corpus proof

Tested against all 13,688 actual V0 outputs from the 1,711-record frozen blind input at checkpoints `0, 30, 59.999, 60, 300, 900, 1802, 7200`.

Results:

- canonical full clock JSON = 28,655,140 bytes
- exact full-payload codec = 20,948,796 bytes, 26.893% smaller
- Frankie-facing NOVA packet = 1,909,199 bytes, 93.337% smaller
- average NOVA packet row = ~139.44 bytes
- full-codec round-trip failures = 0
- protected model-packet round-trip failures = 0
- future-price flags = 0

NOVA uses its existing rough token estimate (`characters / 4`) for this benchmark; these are not model-specific tokenizer claims:

- canonical estimate = ~7,163,785 tokens
- Frankie-packet estimate = ~477,299 tokens

Hot-path `pack_batch` includes protected round-trip verification:

- 1 row: ~0.085 ms median
- 1,711 rows: ~95.7 ms median
- 13,688 rows: ~989 ms median

This is fast enough for per-leg/live use. The hot path should use `FrankieRunwayPacket`; the full lossless codec is an audit/transport option, not required on every live update.

### NOVA repository write limitation

The GitHub integration can read `DavisAI1974/Nova-Optimizer` but returned HTTP 403 `Resource not accessible by integration` for both branch creation and Git tree writes. The proven patch therefore remains local rather than being written directly to NOVA `main`.

Local patch archive SHA-256:

`3f4bcf60783f6a2b05e4f0a06f75d89928a2d8b5397993a58395fc3c4f31cdbd`

Do not bypass this by committing directly to NOVA `main`. Once NOVA write permission is available, create a feature branch from `77aa7eaa...` and apply the job-specific patch unchanged, then rerun the real-corpus benchmark.

## Intended runtime architecture

`S3 canonical day partition -> SHA verify -> single deterministic exhaustion clock -> NOVA FrankieRunwayPacket -> Frankie direction/magnitude reasoning`

Rules:

- S3 canonical source is authoritative.
- NOVA packets are derived disposable views, never canonical data.
- One deterministic exhaustion worker remains sufficient based on the large-batch benchmark.
- Optimize S3 partition reads/serialization before adding worker processes.
- Do not use an AI agent to calculate deterministic exhaustion math.
- Do not change frozen classifier/baselines as part of storage or NOVA integration.
- Do not merge permanent Frankie brain/schema in this step.

## Current next step

From a credentialed Markets runtime, regenerate the stage directory with `ng_exhaustion_s3_stage.py`, execute the recorded `platform_sync.py` push, and verify S3 read-back hashes. After NOVA repository write access is available, land the proven reducer patch on its own NOVA feature branch. Then wire the isolated clock + NOVA packet to the near-live feed overlay; permanent Frankie still stays untouched until a separate deliberate brain merge.
