# NG Exhaustion October-Only Sharded Full-MBO / Full-V4 Handoff — 2026-08-24

## Takeover instruction

Take over the October-only acceleration work on branch:

`chatgpt/ng-exhaustion-october-sharded-20260824`

Read this file first. Current branch state and the frozen candidate inputs are truth. Do not redo settled NG exhaustion research and do not change the scientific program.

## User intent

Clone the exact program currently used for the bounded three-month Step-1 run, but make a second runner dedicated to **October 2021 only**:

`2021-10-01T00:00:00Z` through `2021-11-01T00:00:00Z`

Then parallelize October across multiple CPU workers so the month can finish materially faster. The user is comfortable paying for additional CPU/instance capacity when it produces a meaningful speedup.

This is an orchestration/performance change only. **Do not create a reduced, pilot, summary, structural-only, MBP-derived, or simplified scientific mode.**

## Frozen scientific contract

The October-only run must preserve the same full-MBO/full-V4 treatment as the intended five-year program and the current bounded three-month run:

- every raw MBO message in the target interval;
- full reconstructed order-book state, queue/FIFO/order-count/depth state;
- adds, cancels, modifies, trades and signed flow;
- full exhaustion detection;
- full V4 state, taxonomy and geometry;
- predecessor/descendant/reset/timing state;
- chain and case retention with no case dropping because it is weak, losing, sparse, negative, inconclusive or disagreeing;
- exact provenance, contract resolution, source integrity and missingness semantics;
- identical causal rules and frozen feature definitions;
- deterministic output identities, receipts and hashes;
- no permanent Frankie mutation and no trading release claim.

If a statistic genuinely requires more history than October provides, mark it insufficient. Do not redefine it to make the one-month run pass.

## Authoritative frozen inputs

Repository: `DavisAI1974/Markets`

Frozen candidate SHA:

`0d318335825b4a0e19a5a2881522f3da0374788e`

Primary Step-1 implementation:

`research/ng_exhaustion_mbo_5y_step1_census_20260822.py`

Full V4 replay:

`research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`

V4 state adapter:

`research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`

Current three-month launcher to clone at the orchestration level:

`.github/workflows/ng_exhaustion_step1_parallel_3mo_20260823.yml`

The current bounded branch contains that workflow at blob SHA:

`1cfebf571f45061c7696ad3f488b897c6df2ea81`

Canonical source manifest:

`research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json`

Use only the exact objects/hashes in the frozen manifest. Do not broad-scan an S3 prefix and substitute whatever is present.

## Critical sharding constraint — do not naively cut October by dates

A read-through of the frozen V4 replay code found an important state boundary:

- `replay_dbn_files(...)` constructs one `V4MboAdapter()` and carries that reconstructed book state across all DBN files supplied to that replay;
- separate worker processes instantiate separate adapters;
- therefore an arbitrary October date/object split can silently reset book state and change the science at a shard boundary.

Before launching sharded October, prove the shard boundaries are scientifically safe.

Allowed approaches, in order of preference:

1. **Canonical reset/snapshot boundaries.** If the exact October source objects contain a complete, deterministic book snapshot/reset at a candidate boundary, prove that replay beginning there reconstructs the same state as the monolithic path before using it as a shard start.
2. **Deterministic warmup/checkpoint.** Give each shard enough exact predecessor input or a hash-verified predecessor-state checkpoint to recreate the same starting book state, then trim all warmup output so each target second/event is emitted exactly once.
3. **Other truly independent partition.** Only use instrument/contract partitioning if code inspection and an equivalence test prove there is no cross-partition state/chain dependency.

Do not assume a file boundary, calendar day, contract boundary or worker boundary is a safe reset merely because it is convenient.

## Important implementation seam

`process_segment(...)` currently names its deterministic seconds and receipt outputs from `segment_id`. Replaying subsets of the same October segment into one output directory will collide.

Also, the existing `object_dates` subset path is labeled `REVEALED_OVERLAP_OBJECTS`; do not misuse that receipt mode to represent the new authoritative October sharding program.

Build an orchestration-only October shard wrapper with isolated per-shard output roots/IDs and an explicit shard receipt schema. Reuse the frozen MBO/V4 replay machinery rather than reimplementing the scientific calculations.

A safe design is:

- freeze the exact October object roster from the canonical manifest;
- derive a deterministic shard plan with explicit source-object hashes, target start/end and any warmup range;
- run each shard in an isolated directory/unit;
- emit shard receipt + seconds gzip hash + engine/source hashes;
- trim warmup deterministically;
- merge target outputs in canonical temporal order;
- run downstream October reconciliation/event detection on the merged canonical stream so cross-shard predecessor/descendant/chain logic remains intact;
- emit a top-level October merge/equivalence receipt.

## Equivalence gate is mandatory

Do not treat the sharded October result as authoritative merely because all workers exit successfully.

Before promotion, compare it with a **monolithic October replay using the same frozen candidate and source objects**. The sharded path must demonstrate the precise equivalence expected from the chosen boundary strategy. At minimum verify deterministic source/engine identity, complete/unique target coverage and content equivalence of the canonical merged seconds stream. Where byte-for-byte identity is expected, require the hashes to match; if gzip container metadata makes byte identity inappropriate, compare the decompressed canonical records and document why.

Fail closed on any unexplained boundary difference. Do not tune the science to make the sharded and monolithic paths agree.

## CPU / compute direction

Use available CPUs aggressively **after** shard-boundary correctness is proven.

- Current three-month machine is a 4-vCPU `t3.xlarge` and the existing three month workers already consume three cores.
- Do **not** kill or slow those existing workers just to make room for October.
- The user has authorized spending for additional CPU capacity when worthwhile, so a separate/resized compute target with more vCPUs is acceptable for the October acceleration after the shard plan is validated.
- Prefer the number of workers that matches proven independent shards and actual available vCPUs; do not create fake concurrency that contends on one core or duplicates the same target evidence.
- Record `nproc`, CPU affinity/quota, intended worker count and a short utilization canary before the production launch.
- Record the selected instance/capacity and approximate expected cost before launch for provenance, but cost minimization is secondary to a meaningful safe speedup.

Do not claim linear speedup in advance. Measure it.

## Existing three-month run — leave it alone, but monitor it

AWS region: `us-east-2`

Existing EC2 instance:

`i-08cee7171c0a76a04`

S3 bucket:

`bento-568968024170-us-east-2-an`

Frozen launch prefix:

`nymex/ng_mbo_5y_v0/step1_census/launches/0d318335825b4a0e19a5a2881522f3da0374788e/`

Current three target workers:

- `ng-exhaustion-step1-p3m-20210901_20211001`
- `ng-exhaustion-step1-p3m-20211001_20211101`
- `ng-exhaustion-step1-p3m-20211101_20211201`

The original five-year serial controller is stopped. **Do not automatically resume it.**

The existing three-month workers should continue to completion even if the new October-only path moves forward in parallel. Do not kill them unless there is a new explicit reason and authorization.

### Monitoring semantics

Use read-only checks. Completion is proven by the exact target segment receipts and hashes, not by a process disappearing or a systemd unit becoming inactive.

Authoritative existing local receipt pattern:

`/mnt/markets/ng_exhaustion_step1_5y_20260822/0d318335825b4a0e19a5a2881522f3da0374788e/full/segments/*.receipt.json`

Authoritative S3 progress receipt pattern is under the candidate's **`full/progress/segments/`** path.

Do not rely on the older `ng_exhaustion_mbo_5y_step1_status_20260823.yml` S3 heartbeat for completion; that workflow reads a stale `preflight/progress` path. A dedicated read-only monitor for the exact `full` receipts/processes is preferable.

For the new October shard run, monitor:

- unit/process state and elapsed CPU time;
- per-shard target coverage;
- per-shard receipts/hashes;
- merge receipt;
- monolithic-vs-sharded equivalence gate;
- memory/disk pressure and errors.

## Existing three-month launch provenance

Parallel launch workflow:

`.github/workflows/ng_exhaustion_step1_parallel_3mo_20260823.yml`

Launch receipt:

`research/kalshi/NG_EXHAUSTION_STEP1_PARALLEL_3MO_LAUNCH_20260823.json`

Successful SSM launch command recorded previously:

`e4833cec-09ba-43b6-93c5-e76defedc95a`

Earlier failed acceleration attempts and the diagnostic artifact are provenance. Do not delete them casually:

`research/kalshi/NG_EXHAUSTION_STEP1_PARALLEL_3MO_FAILURE_DIAG_20260823.json`

## Immediate next sequence

1. Inspect the current branch and exact October segment/object roster from the frozen manifest.
2. Clone the three-month launcher into a dedicated October-only orchestration path; do not touch the existing production workers.
3. Determine and **prove** safe shard boundaries from actual snapshot/reset/warmup behavior.
4. Build deterministic isolated shard outputs and a merge receipt.
5. Add focused tests for source coverage, no duplicates/gaps, boundary-state preservation, deterministic merge and fail-closed behavior.
6. Run a small correctness canary if needed; do not weaken science for the canary.
7. Choose worker count / additional compute based on proven shardability. The user is comfortable paying for additional CPUs for meaningful acceleration.
8. Launch October shards only after the correctness gates pass.
9. Monitor both the existing 3-month workers and the new October run.
10. Run/retain the monolithic October equivalence reference and do not promote the sharded result until equivalence passes.
11. Freeze all receipts/hashes/results. Do not auto-mutate permanent Frankie and do not auto-resume the five-year serial census.

## Standing interpretation rule

A negative, weak, sparse, losing, inconclusive or disagreeing October result is still evidence. Preserve every case and let the data tell the story. Nothing is dropped merely because it is not the result hoped for.
