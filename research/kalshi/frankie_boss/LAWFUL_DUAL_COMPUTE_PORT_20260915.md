# Lawful dual-compute port — 2026-09-15

Branch: `chatgpt/frankie-lawful-dual-compute-20260915`
Lawful base: `050c5056c3657a954d6a3ee17f3a216999930768` (`codex/sunday-runtime-grid-fix-20260915`)
Review source: divergent ccode/Claude review line ending at `dd37bfa3`

## Ported onto the lawful lineage

1. `verified_journal_reader.py`
   - bounded `ProcessPoolExecutor` for row-local JSON/decode/canonical-hash validation;
   - parent retains ordinal, previous-hash, terminal count/head, and immutable-tail authority;
   - `forkserver` where available, otherwise `spawn`;
   - worker OMP/MKL/OpenBLAS/NumExpr pools pinned to one thread;
   - pool created lazily on first `entries()` call;
   - `chunksize=1` so a corrupted row fails at the same consumed ordinal as the single-worker reader.

2. `cpu_runtime.py`
   - independent explicit knobs for journal workers, PyTorch intra-op threads, and PyTorch inter-op threads;
   - fails closed if the host exposes fewer logical CPUs than requested;
   - records CPU model and PyTorch thread identity;
   - does not alter inputs, calculations, planes, evidence, loss, optimizer order, Memory A, or checkpoint semantics.

3. `tests/test_cpu_worker_policy.py`
   - focused policy separation tests;
   - exact single-vs-parallel reader equivalence;
   - exact same-row rejection position;
   - verifies stale `FRANKIE_CPU_WORKERS` has no effect.

4. `operations/benchmark_verified_reader.py`
   - read-only benchmark against witness-pinned closed prefix snapshots;
   - hashes before/after and refuses live sidecars;
   - no market-data/model/cloud run.

5. `operations/sunday_restoration_package.py`
   - inventories the lawful Windows runtime under its existing hashes;
   - copies only small files into a package;
   - lists bulk files for object storage without modifying the original E:/ or C:/ runtime.

## Existing lawful machinery retained, not reimplemented

The lawful line already has `frankie_journal_reader.FrankieCompactReader`, `compact_journal.py`, `compact_journal_snapshot.py`, `verified_sunday_schedule.py`, and the actual host's compact-prefix selection. Cycles using `C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1` stay on `FrankieCompactReader`; the raw `VerifiedJournalReader` is not substituted for compact snapshots.

The old Sunday configuration contains `host_runtime.data_workers = 48`. In the lawful compact reader that is a requested upper budget, not proof of 48 available CPUs: `worker_budget()` limits workers to the host affinity set and reserves one logical CPU for the ordered consumer when possible. Do not interpret that old value as a physical-host inventory.

## Deliberately not ported

- `.github/workflows/frankie_sunday_cycle0_github16.yml`
- `operations/run_actual_sunday_github16.py`
- the ccode parallel-source workflows/scaffolding
- the divergent branch's duplicated runtime/Granite modifications
- any result-bearing run output as executable state

Reason: Claude's review found the GitHub 16-core hosted-runner assumption invalid for this User-owned repository and found the source branch to be off the lawful `050c5056` lineage. Porting those pieces would recreate the same blockers.

## Native training identity constraint

`BossTrainingCheckpoint._layout()` binds Python, torch, numpy, byte order, `torch.get_num_threads()`, deterministic-algorithm state, and checkpoint code hash. A rerun with a different thread count/toolchain must therefore be a NEW run identity with a fresh training checkpoint. The failed cycle-00 evidence remains immutable.

## Remaining work before any result-bearing rerun

1. Select the real native host. Claude's review recommends a persistent 16-vCPU EC2 host with sufficient RAM rather than GitHub Actions. Measure the actual float64 step there before choosing 8 vs 16 PyTorch intra-op threads.
2. Generate the lawful restoration manifest from the existing Windows runtime and place the manifest-named bulk objects in S3, verifying every object by SHA-256 on the native host.
3. Build/apply a deterministic configuration path rebase: same pinned bytes/hashes, new host paths, NEW `run_id`, NEW `run_directory`, and an explicit decision on retained cycle-00 preparation reuse versus clean regeneration.
4. Declare the new run's Python/torch/numpy/thread/deterministic identity before checkpoint construction.
5. Only after those gates pass should cycle 0 be dispatched.

## Run state

No Frankie, Granite, market-data, training, or result-bearing cycle was launched by this port.
