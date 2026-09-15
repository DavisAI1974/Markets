# Claude review - Frankie/BOSS dual-compute migration (2026-09-15)

Reviewed branch: `chatgpt/frankie-dual-compute-20260915` at `5b0c1b4d`, then reconciled with the
seven commits ChatGPT pushed concurrently during the review (`8cef9ca2`..`5ac9bf23`, tip
`5ac9bf23`); see "Reconciliation" at the end.
Reviewer: Claude Fable 5.1, working on the E:/Markets checkout with read-only access to the
E:/Codex/Frankie-BOSS-20260915 runtime. Nothing under E:/Codex or C:/Users/A/Documents/Codex
was modified; every file read from there was hash-checked against its witness before and after.
No Frankie, Granite, market-data or broad-suite run was performed. The only executions were
focused reader/policy unit tests on temporary journals and a read-only drain benchmark of two
closed, witness-pinned prefix snapshots.

## Verdict

Do not launch cycle 0 from this branch. Three findings block it independently, and none of them
is about the parallel reader.

1. **The branch is on the wrong lineage.** The failed cycle-00 ran with `boss_commit =
   050c5056` (`codex/sunday-runtime-grid-fix-20260915`). This branch was cut from
   `codex/full-frankie-boss-connection-20260915` (`9a38157b`). The two diverged at `35982ac7`;
   neither contains the other. The lawful lineage carries 22 files this branch lacks, including
   `frankie_journal_reader.FrankieCompactReader`, `compact_journal.py`,
   `compact_journal_snapshot.py` and `verified_sunday_schedule.py`. The lawful host's `prefix()`
   selects the compact reader for `C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1` receipts with
   `workers=host_runtime.data_workers` (the configuration says 48); this branch's host reads
   every prefix with `VerifiedJournalReader`. Measured on the real cycle-1 snapshot: the
   compact file has tables `blocks` and `seal`, no `entries`, and `VerifiedJournalReader` refuses
   it (`no such table: entries`). A rerun from this branch would pass cycle 0 and die at cycle 1.
   The "lossless parallel reader" this branch adds is a weaker re-implementation of the
   spawn-context, CPU-pinned, block-parallel reader the lawful lineage already has.

2. **The 16-core GitHub runner does not exist.** `DavisAI1974` is a User account, not an
   Organization; hosted larger runners (`ubuntu-24.04-16core`) are an Organization feature.
   The repository has zero self-hosted runners. The workflow would queue forever. There is
   nothing to correct the selector to (handoff Q7). The natural 16-CPU host with a persistent
   disk is an EC2 instance in account 568968024170, where user/Claude already holds EC2 and SSM
   access from S90/S93; GitHub Actions is the wrong shape for a stateful 19-cycle run anyway
   (ephemeral disk, 6-hour job ceiling, the run directory would have to round-trip as an
   artifact between jobs, which is exactly the concurrent-writer risk the owner direction
   forbids).

3. **The rerun cannot be "the same scientific configuration" at the bit level, and the
   workflow did not pin the things that decide that.** `BossTrainingCheckpoint` binds
   `sys.version`, `torch.__version__`, `numpy.__version__`, `torch.get_num_threads()` and
   `deterministic` into every checkpoint and refuses to advance if any changes. The failed run's
   sequence-0 checkpoint (read read-only) binds Python 3.13.7 (Windows), torch 2.9.1+cpu, numpy
   2.3.5, threads 4, deterministic False. The workflow installed unpinned torch and numpy under a
   floating `python-version: '3.12'`; two jobs weeks apart could resume nothing. Thread count
   also changes floating-point reduction order in CPU GEMM, so 16 threads vs 4 is a numeric
   change, not only a speed change. That is fine for a NEW run identity, but it must be declared
   as such, never described as identical.

What actually failed: `host-progress/progress.json` of the original run records
`phase=boss_training`, `error_type=RuntimeError`, 0 steps, after 761 s in that phase (2,383 s
total), preceded by `possible_stall` warnings. The host never interpolates exception text, so
the message is not retained anywhere in the evidence. The two RuntimeErrors the checkpoint can
raise (`training state uncertain`, `advanced elsewhere`) both require a prior mutation, and the
checkpoint holds exactly one row (sequence 0, cursor -1), so the error came from inside the
torch step itself: a float64 d_model-256, 4-layer, window-128 model with fixed 8-step
recurrence over up to 4,096 context rows, on a 16 GB, 4-thread box. Nothing in this branch
addresses that; more threads make the step faster, not smaller.

## Answers to the handoff questions

**Q1 - Does the parallel reader preserve exact acceptance/rejection semantics and order?**
Acceptance: yes. The full existing corruption suite (`test_verified_journal_reader.py`,
`test_verified_reader_concurrent_tail.py`, `test_journal_prefix_snapshot.py`) passes under
`FRANKIE_JOURNAL_VERIFY_WORKERS` = 1, 2 and 4 (166 tests green before the rebase, 126 on the
reconciled tree where ChatGPT's own explicit `workers=` parametrization replaces part of mine).
Rejection: **no, not as committed.** With `chunksize=len(rows)//workers` a chunk fails as a
unit, so on a journal corrupted at ordinal 37 the parallel reader raised after yielding 36 rows
where the single-worker reader yields 37. A valid row vanished from the consumer's view before
the error. Fixed by `chunksize=1`; the new test
`test_parallel_reader_rejects_at_the_same_row_as_single_worker` pins it. The row-local error
types survive the worker boundary (`json.JSONDecodeError` defines `__reduce__`; `ValueError`
and `struct.error` serialise cleanly).

**Q2 - Is ProcessPoolExecutor safe on a Linux runner for this reader?** As committed, no on
two counts, now fixed. (a) The pool was created in `__init__` with the default start method,
which on Linux (Python < 3.14) is `fork`: every worker inherited the parent's open SQLite handle,
the already-initialised PyTorch/OpenMP thread pool and, in the host, the whole model state. The
worker never touches those, so it did not deadlock, but `_worker_init` setting
`OMP_NUM_THREADS=1` after a fork is decorative and any future torch call in a worker would hang.
Now `forkserver` where available, `spawn` otherwise; the worker function is module-level and
importable. (b) Eager creation meant every tail-only open (`journal_prefix_snapshot` opens the
parent reader and closes it immediately; `source_recovery` likewise) spawned a full pool;
measured on Windows the existing suite went from 8 s to 127 s with two workers for that reason
alone. Now lazy on the first `entries()`. SQLite: the parent keeps sole ownership of the
read-only connection; workers receive `(ordinal, kind, body, digest)` tuples over the executor's
own transport. Cost is one serialisation of the body per row, comparable to the JSON parse it
buys; see the timing table.

**Q3 - 16 intra-op / 1 inter-op, or reserve CPUs?** Measured, not assumed: the reader drain
and the optimizer step never overlap. `native_forecast_learning.step()` drains
`journal_prefix(builder)` (the same `VerifiedJournalReader`) in the calling thread and only then
runs forward/backward; `_prepare` drains twice more, before the Granite request, inside
`prime_cache`. So the two budgets are sequential and each may use the whole host. 16/16/1 is
right for a 16-CPU host provided nothing else runs there. The lawful compact reader already
reserves logical CPU 0 for the ordered consumer (`worker_budget`), which is the one sensible
reservation; the parallel raw reader should do the same on the real host. With 16 idle pool
processes resident during the step the cost is memory, not CPU; on a 16 GB box that matters,
on a 64 GB one it does not.

**Q4 - Env var name.** Split. ChatGPT and I split it independently and its names are the
ones kept: `FRANKIE_JOURNAL_VERIFY_WORKERS` is the reader's only channel,
`FRANKIE_TORCH_INTRAOP_THREADS` and `FRANKIE_TORCH_INTEROP_THREADS` are the trainer's, all
three mandatory with no hidden default (`policy_from_environment`). `FRANKIE_CPU_WORKERS` is
dead and the tests assert a stale value has no effect.

**Q5 - What must be packaged.** Everything the configuration reads, checked by hash. Built:
`operations/sunday_restoration_package.py` walks the configuration, follows all 16 top-level
path witnesses and the 23 secondary pins inside the prefix manifest and the retained-recovery
witness, recomputes every sha256 on disk (all match), and writes
`sunday_20260915_package/RESTORATION_MANIFEST.json` (197 files). The small files (170 files,
24.05 MB: configuration, receipts, witnesses, schedule, lineage, mapping, source manifest,
frozen Memory A, retained witnesses, the verified tokenizer, every prefix receipt/witness/seed,
the failed run's small evidence) are mirrored into git under `sunday_20260915_package/FB/...`
and `.../C_Codex/...`. The 27 bulk files (18.35 GB: `source.sqlite` 11.7 GB, the 18 compact
prefix snapshots 5.4 GB, the raw cycle-0 prefix 463 MB, the compact journal 570 MB, the failed
`training.sqlite` 107 MB, `calculation_result.json` 29 MB, the cycle-0 prompt/native outputs)
are hashed and listed for object storage. Two inputs live on C:, not E:
(`tokenizer_directory`, `retained_preparation_recovery`) and the receiver checkout is a third
repository clone; all three are in the manifest. The 1,880-file BOSS checkout is not copied:
it is commit `050c5056`, on the remote. A restoration on another host still needs a path
rebase of the configuration (every witness carries an absolute E:/C: path) with the hashes
carried over unchanged; that rebaser is not built here.

**Q6 - What Granite-side CPU work can move to the Pod.** Less than the handoff hopes.
Tokenizer admission is deliberately a host-side independent measurement
(`LocalTokenizerAdmission`, pinned to `expected_tokenizer_sha256`) and the existing GitHub
watchdog repeats it independently; moving it onto the Pod would make the served model its own
admission authority. What the Pod already owns is right: vLLM's own tokenization, scheduling
and sampling. The one real candidate is Greg's: building the compact Granite context for cycle
N+1 while N trains. `ContextSessionRunner._prepare` depends on the verified prefix snapshot,
the trunk registry, `t_ctx` and the teacher, not on model weights (`model_forward_performed`
is False and no forward is in the path), so the content is weight-independent.

**Q7 - Runner selector.** See blocking finding 2. Not edited; there is no valid target.

**Q8 - Could the new run reuse the failed cycle-00 checkpoint or principal output?** Three
paths, all closable. (a) Same `run_directory`: the host resumes `training.sqlite` in place
(`create=not path.exists()`) and `host-instance.c15.json` only checks that `run_id` matches,
so a new `run_id` in the old directory fails closed, but the old `run_id` in the old directory
silently resumes. The new configuration must carry a new `run_directory` AND a new `run_id`.
(b) `retained_preparation_recovery` and `prefix-00-preparation.json` are cycle-0 reuse
witnesses from the failed run; `prepared_input` accepts them when
`training_checkpoint_hash is None and training_cursor == -1 and live_hash == native_hash`, which
a fresh run satisfies. Reusing a preparation is scientifically fine (weight-independent, hash
verified) but it must be declared in the new run's evidence, or dropped from the new
configuration for a clean benchmark. (c) `completed-journal-pins`, `host-preparation`,
`host-service` inside the old cycle-00 directory are only read from the run directory, so (a)
covers them. The cross-lineage checkpoint binding (finding 3) is the fourth defence: a
different Python/torch/threads makes the old checkpoint unresumable by construction.

**Q9 - Overlap and the barrier.** Greg's shape is the right one and the code confirms it:
Granite context preparation for N+1 can run on the Pod while N trains on the native host,
barrier at the cycle N+1 prefix receipt. The prefixes are already pre-built for all 19 cycles
(`actual-prefixes/prefix-NN.sqlite` plus receipt, witness and seed, all in the manifest), so
the Pod can be handed the snapshot file plus its receipt, never the source journal. What
blocks it today is not authority but the reuse contract: `prepared_input` requires
`training_checkpoint_hash == current` and `info['model_hash'] == live_hash`, both of which
change after step N, so a preparation made before step N is refused after it. To allow overlap
the contract has to bind the preparation to (prefix receipt, registry hash, teacher binding,
as_of, t_ctx) and record the checkpoint hash at dispatch instead. That is a change to a
retained-evidence contract, so it is Greg's call, not a review fix; it is the one genuine
wall-clock win in the dual-compute idea.

## Timing table (measured; chart in `artifacts/verified_reader_bench_20260915.png`)

Reader drain of the real cycle-0 prefix (raw layout, 463 MB, 6,524 rows, witness-pinned, hash
unchanged after every run), this 4-CPU Windows box, `chunksize=1`, idle:

| reader workers | seconds per drain | speed-up |
|---|---|---|
| 1 | 28.7 | 1.00 |
| 2 | 24.5 | 1.17 |
| 4 | 16.4 | 1.75 |

The parent's fetch, serialisation and ordered yield are the serial floor; expect the curve to
flatten well before 16. Three drains per cycle at one worker is 86 s of the failed cycle's
2,383 s; the native step alone was 761 s and never finished. The intra-op 8-vs-16 table cannot
be produced on this box (4 logical CPUs); `benchmark_verified_reader.py` is committed so the
reader half can be rerun on the real host, and the step half needs the native host and a
decision on `torch.use_deterministic_algorithms`, which the checkpoint also binds.

## Changes made on this branch

- `verified_journal_reader.py`: `chunksize=1` (row-exact failure position), lazy pool
  creation on first `entries()`, restored the equivalence docstrings the patch had deleted.
  ChatGPT's concurrent forkserver context, one-batch prefetch and env rename are kept.
- `cpu_runtime.py`: ChatGPT's version (three explicit budgets, no defaults, CPU-model receipt).
- `tests/conftest.py`: the two reader-consuming modules that construct readers through the
  environment run under workers 1, 2, 4; `test_cpu_worker_policy.py`: same-row rejection test
  (64 rows, corruption at ordinal 37; a 5-row journal cannot catch it), lazy-pool assertion.
- `.github/workflows/frankie_sunday_cycle0_github16.yml`: PYTHONPATH (the test step failed at
  collection without it, reproduced), exact torch/numpy/Python pins, the three env budgets the
  launcher now requires. Runner label untouched (finding 2).
- `operations/sunday_restoration_package.py`, `operations/benchmark_verified_reader.py`,
  `sunday_20260915_package/` (170 files + manifest), `artifacts/verified_reader_bench_20260915.*`.

Tests on the reconciled tree: 126 passed across the policy, reader, concurrent-tail, snapshot,
cache and recovery modules; the two workflow test files pass with the documented PYTHONPATH
and fail at collection without it, as the workflow was written.

## Reconciliation with ChatGPT's concurrent commits

While this review ran, ChatGPT pushed `8cef9ca2`..`5ac9bf23` to the same branch, touching the
same four files. Its reader hardening (forkserver, batch prefetch), its policy split and its
launcher guards (refuse Windows paths, refuse an existing run directory unless
`FRANKIE_GITHUB_RECOVERY=1`, write a runtime identity receipt) are all kept; the launcher guard
closes Q8(a) directly. Two defects survived its pass and are fixed here on top: the chunked
`executor.map` (its 5-row rejection test cannot see it; the 64-row test does) and the eager
pool in `__init__`. Its `operations/benchmark_verified_journal.py` and
`operations/build_sunday_restore_manifest.py` overlap with the two scripts here; the ones
here hash real witness-pinned snapshots and copy the small files into git, so I recommend
keeping these and retiring its two, but that is a cleanup for Greg to call, not done here.
None of its commits touch the three blocking findings: the branch lineage, the runner, and the
checkpoint toolchain binding are exactly as described above.

## Recommended path to the cycle-0 rerun

1. Rebase this work onto `codex/sunday-runtime-grid-fix-20260915` (`050c5056`), or cherry-pick
   only `cpu_runtime.py`, the reader fixes and the package onto it. The lawful host, compact
   reader, schedule verifier and grid fix live there and nowhere else.
2. Pick the native host: a 16-vCPU EC2 instance with enough RAM for the float64 step is the
   honest fit; GitHub hosted runners are out for a User account. Measure the step there before
   deciding 8 vs 16 threads.
3. Build the configuration rebaser: same hashes, new paths, new `run_id`, new `run_directory`,
   explicit decision on whether the retained cycle-0 preparation is reused or dropped, and the
   toolchain (Python, torch, numpy, threads, deterministic) declared in the run's own evidence
   as a new identity.
4. Put the 27 bulk files on S3 under a manifest-named prefix and verify by hash on the host.
5. Only then dispatch the credential on stdin and start cycle 0.
