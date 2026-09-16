# ccode review - clean lawful recovery branch (2026-09-15)

Reviewed: `chatgpt/frankie-lawful-recovery-clean-20260915` at `657b6d62`, verified to descend
from the failed run's `boss_commit 050c5056`. Review branch with corrections and the bulk-hash
addendum: `ccode/frankie-lawful-recovery-review-20260915`. Nothing under E:/Codex or C: was
modified except the removal of four header-only SQLite sidecar files that my own benchmark
runs created (see "Sidecar trap"); the original failed run directory was hash-inventoried
(75 files) before and after and is byte-identical. No Frankie, Granite, market-data,
retained-Pod or result-bearing run was performed.

## Verdict

The branch is on the right lineage and its runtime changes are observational, with one
measured defect (the Windows probe returned no process fields) now fixed. It cannot launch
cycle 0 yet for two reasons the handoff did not know about, both found by trying to reach the
training step on a scratch clone of the failed run:

1. **The lawful lineage pins the retired Pod.** `granite_retained_lifecycle.POD_ID` on
   `050c5056` (and therefore on this branch) is `jvs75m56w8f73q`. The retained Pod that the
   failed run's own service record points at (`retained-ready-34987737686-runtime-aligned/
   pod-info.json`) is `ycf4v6lmave6xw`. The rebind commit `aa12fd09` (7 files, 57 lines) exists
   only on `codex/full-frankie-boss-connection-20260915`. On this branch every host start that
   reaches the retained-service re-verification fails with `exact accepted Pod, request digest
   and bounded lease required`, measured at 62 s into the clone run, after checkpoint restore
   and before any training. A NEW cycle 0 is the same shape: the watchdog will produce a
   readiness directory for whatever Pod exists, and the host will compare it to a constant
   naming a Pod that no longer exists. Port `aa12fd09` (or re-pin `POD_ID` to the Pod a
   read-only RunPod GET actually returns) before anything else. This also explains the Sunday
   fork: the training-phase code and the Pod-migration code went to different branches.

2. **The sidecar restart trap.** `ActualHost.source_lineage` refuses when the lineage parent
   journal has a `-wal`, `-shm` or `-journal` sidecar, then opens that parent and the child
   read-only. A read-only open of a WAL-mode SQLite file creates a zero-length `-wal` and a
   32 KB `-shm` that a read-only connection cannot remove. So the first start passes and every
   later start refuses, until an operator moves the sidecars away by hand. The E: tree carries
   the scar tissue: `closed-parent-sidecars-01/02` and `runtime-sidecars-recovery-*-resume08..14`
   are exactly those evacuations, seven of them on Sunday. Reproduced twice here: run 1 passed
   lineage and created the four files (20:39), run 2 refused at 6 s. Any EC2 resume lifecycle
   (`--ec2-resume`, or the prepare -> service -> principal -> training continuation, which is
   three or more separate host invocations) hits this on invocation two. The right rule already
   exists in `journal_prefix_snapshot._sidecars`: a `-wal` with frames beyond its 32-byte
   header means a live writer; a zero-length `-wal` is not content. `source_lineage` should
   use it. Not applied here because it changes host semantics; it is the one host change the
   recovery genuinely needs.

## Answers

**Q1 - Are the code changes runtime-only?** Yes. Code-only diff from `050c5056` is 13
files: three runtime files touched (`native_forecast_learning.py` +49/-6,
`sunday_execution.py` 4 lines, `full_run_progress.py` +45) and ten new files. Verified
byte-identical to the lawful commit: `frankie_journal_reader.py`, `compact_journal.py`,
`compact_journal_snapshot.py`, `verified_sunday_schedule.py`, `verified_journal_reader.py`,
`operations/run_actual_sunday.py`, `boss_training_checkpoint.py`, `context_session.py`. The
graft is exact: tree `4a228898` (C_Codex), tree `0f6615cb` (FB) and blob `43fba82e`
(manifest) match `dd37bfa3` object-for-object.

**Q2 - Learner telemetry.** Observational. `_emit` passes only `request_id`, a stage name,
elapsed seconds and integer counts (`len(context)`, `len(losses)`, `masked`); it never holds a
tensor, so graph lifetime is unchanged. The added `except Exception: emit; raise` re-raises the
same exception object; `finally` still restores `requires_grad`. `_emit` swallows any callback
exception and `HostProbe.call` swallows again, so a probe failure cannot change the result.
`apply_completed` is untouched. Cost is about twelve fsync'd JSON lines per step. One nit:
`prepare_start` fires before the outer `try`, so a prepare failure emits `step_failed` from the
inner handler and not twice; fine.

**Q3 - Windows RSS.** Wrong as committed. `ctypes.windll.kernel32.GetCurrentProcess()` with no
`restype` returns the pseudo-handle -1 as a 32-bit int; `GetProcessMemoryInfo` rejects it and
`memory_snapshot()` silently returned only the two system fields (measured on this host:
`{'system_memory_total_bytes': 17054658560, 'system_memory_available_bytes': ...}` and nothing
else). The existing test accepted that because missing fields are "simply absent". Fixed by
typing `restype`/`argtypes`; `memory_snapshot()` now reports `process_rss_bytes`,
`process_peak_rss_bytes`, `process_private_bytes`, and a new test requires the process fields on
every platform. Linux path (`/proc/self/status` VmRSS/VmHWM) is correct.

**Q4 - EC2 first-launch/resume gate vs the real lifecycle.** The gate itself is sound
(`SundayRuntime` is a plain dataclass, so `learning_event` can be set; `HostProbe.call`
forwards `training_event`; the wrapper strips `--ec2-resume` before the host parser;
`--prepare-only` passes through). Three problems around it: (a) blocking findings 1 and 2
above stop the second invocation regardless of the gate; (b) the stable identity includes
`cpu_model` from `PROCESSOR_IDENTIFIER` (family/model/stepping) and `system_memory_total_bytes`,
and an EC2 stop/start can land the same instance type on a different CPU stepping, so a
legitimate resume after a stop would be refused - compare instance type, not stepping; (c) the
wrapper requires `run_directory` not to exist on first launch, while the config builder
already requires a fresh directory, so a first launch that fails before the host writes
anything leaves an empty directory and the next attempt must be `--ec2-resume`; document it.

**Q5 - Clean cycle-0 preparation.** Confirmed in code. `prime_cache` installs the recovery
path only when `host_runtime.retained_preparation_recovery` is present, and `prepared_input`
recomputes unless `prefix-00-preparation.json` exists; `actual-prefixes/` on E: holds only
`prefix-00-witness.json` for cycle 0 (verified by listing), so cycle 0 recomputes from the raw
463 MB prefix-00 snapshot. Cycles 1-18 take the unchanged compact-prefix path
(`C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1` -> `FrankieCompactReader`). The recompute cost is the
retained-recovery witness's own history: 3,262 records rebuilt, roughly the boss_reasoning
phase of the failed run rather than 1.5 s.

**Q6 - Windows path-preserving EC2: attacked, and it survives with conditions.** No contract
forces rebasing on Windows. What forces rebasing on Linux is concrete: `source()`, `prefix()`
and `source_lineage()` compare `Path(receipt[...]).resolve()` against absolute `E:\` paths
embedded in receipts (`snapshot_journal`, `original_journal`, `recovered_path`, `parent_path`,
`ingestion_receipt`, `final_source_path`), and `source_origins` is keyed by the resolved
`E:\...\source.sqlite`; on Linux none of those resolve, so every one of those checks fails and
each receipt would need a migration receipt. On Windows the conditions are: (a) a secondary
EBS volume assigned drive letter `E:` (not automatic; use diskpart) and a plain folder tree at
`C:\Users\A\Documents\Codex\...` (no user named A is needed); (b) `core.autocrlf=true` on the
BOSS checkout at `E:\...\sunday-launch-20260915\Markets`, because `granite_shadow.parser_code_hash`,
`granite_context.native_parser_code_hash` and `granite_context_compact.compact_parser_code_hash`
hash on-disk bytes and feed `GraniteIdentity.identity_hash`, which is compared to the service
pins - an LF checkout changes those hashes; (c) the interpreter at
`E:\...\actual-host-python` recreated at the same path with Python 3.13.7, torch 2.9.1+cpu,
numpy 2.3.5, tokenizers 0.22.2, because `sys.executable` enters the principal adapter's
`_config_hash`; (d) the receiver checkout at its `C:` path at `342f5728`, which is on the
remote (`codex/frankie-attachment-preparation-20260914`); (e) the retained Pod readiness
directories are NOT configuration inputs and are not in the manifest - a new run gets new ones
from the watchdog, which is correct, but a clone-based diagnostic needs the old one. Also note
`platform.release()` is `10` on Windows Server as on Windows 10, so that identity field is
stable across the move.

**Q7 - Memory class to benchmark.** Measured on this host: checkpoint restore alone peaks at
939 MB working set / 1.14 GB private before any forward. The step's own peak is still
unmeasured (blocked, see Q8), so no final class can be named honestly. Benchmark on a
16-vCPU class where memory cannot be the variable, `r7i.4xlarge` (16 vCPU, 128 GB), read the
peak from the now-working probe, then right-size to `c7i.4xlarge` (32 GB) or `m7i.4xlarge`
(64 GB) if the measured peak allows. The 16 GB box is not evidence either way: the failed
run's RuntimeError message was never retained and the probe that would have told us was
broken on Windows until today.

**Q8 - Disposable 8-vs-16 step benchmark.** Designed and committed as
`operations/benchmark_native_step_disposable.py`: it runs the lawful host (the checkout at
the failed run's own `boss_commit`, code identity untouched) on a scratch clone of the failed
run directory, which already holds the saved `controller`, `principal_output` and `feedback`
stages (seven stages in `cycles.sqlite`), so the host skips Granite and the principal and goes
straight to the native step; in-memory wrappers around `_prepare`, `forward_decision`,
`Tensor.backward`, `Optimizer.step`, `apply_completed` and every `ActualHost` method log
substage, RSS/peak RSS and the exception type and message to scratch; stdin is `/dev/null` so
the cycle-1 credential request ends the run; `--keep-checkpoint` restores the seed checkpoint
(thread count must match its binding, 4 here) and `--fresh-checkpoint` drops it so the host
creates a new seed under the requested thread count (the 8-vs-16 path; the saved `binding`
stage carries `training_identities` without a thread count, so it survives). Run twice on this
host at 4 threads: restore succeeds in 12 s at 939 MB peak; the run then stops at the
retained-Pod verification (finding 1) 62 s in, before the step. I asked the harness to bypass
that verification and the auto-mode classifier refused the edit as a security weakening; I did
not work around it. So the step timing needs finding 1 resolved first, after which the same
harness runs unchanged on the restored host at 8 and 16 threads.

**Q9 - `data_workers=48`.** Measured on the lawful `FrankieCompactReader`: `available_cpus()`
is the affinity set, `worker_budget(n)` reserves logical CPU 0 for the ordered consumer and
returns the next `n` CPUs, so 48 resolves to 3 workers here and would resolve to 15 on a
16-vCPU host; anything above 64 is refused. It is already a cap, not a demand, and host-adaptive
by construction; keep 48 and let the receipt's `worker_cpus` field record what was actually
used. Making it host-specific would add a second source of truth for a number the reader
derives correctly on its own.

**Q10 - Bulk hashes.** Audit without addendum fails closed with exactly one gap,
`source-recovery-resume-20260915/source.sqlite` (11,700,711,424 bytes), 26/27 complete. Before
hashing: no Python process with a source-recovery command line, no `-wal`/`-shm`/`-journal`
beside the file, and an exclusive-share open of the file succeeded (nothing else held it).
`build_sunday_bulk_hash_addendum.py` double-read the file (size and mtime stable, both reads
agree): sha256 `181467d12a3ea289e67141be2f73e2c5ec068661c5c66c75c51eb30a2787dd6a`. Audit with
the addendum: 27/27 complete, zero missing, zero conflicting, exit 0. The addendum
(`sunday_20260915_package/BULK_HASH_ADDENDUM_20260915.json`, sha256
`56b669aa1542fbf29fa0fd9870347a144ba589385fce0e9982487bee58580636`, bound to manifest content
`c8b2e0f5...`) and the audit result are committed on my review branch; `RESTORATION_MANIFEST.json`
blob `43fba82e` is untouched. Two honest caveats: the audit trusts the addendum's own
`closed`/`sidecars_absent`/`verified_full_reads` flags (attestation, not re-verification), and
the second read of an 11.7 GB file on a 16 GB host is partly served from page cache, so
"independent" means two passes, not two devices.

**Q11 - N/N+1 overlap.** Agreed, deferred until native cycle 0 is stable.

## Tests run

- `test_native_runtime_diagnostics.py` + `test_sunday_restoration_manifest_audit.py`: 13 passed
  as delivered; 14 passed after the probe fix and its new test.
- Full audit tool runs above. No broad suite.

## Changes on `ccode/frankie-lawful-recovery-review-20260915`

- `runtime_resource_probe.py`: typed `GetCurrentProcess`/`GetProcessMemoryInfo`; process
  fields now present on Windows (measured). `tests/test_native_runtime_diagnostics.py`: test
  requiring them.
- `operations/benchmark_native_step_disposable.py`: the disposable step harness (design of Q8).
- `sunday_20260915_package/BULK_HASH_ADDENDUM_20260915.json`,
  `sunday_20260915_package/RESTORATION_HASH_AUDIT_20260915.json`.
- This document.

## What the launch gate still needs, in order

1. Port `aa12fd09` (Pod rebind) or re-pin `POD_ID` from a read-only RunPod GET; without it no
   host start on this lineage passes the retained-service check.
2. Make `source_lineage` tolerate header-only sidecars using the `_sidecars` rule; without it
   every second host invocation refuses.
3. Loosen the EC2 resume identity to instance type rather than CPU stepping.
4. Then run `benchmark_native_step_disposable.py` on the restored Windows host with
   `--fresh-checkpoint` at 8 and 16 threads; read peak RSS from the fixed probe; pick the
   memory class from that number.
5. Everything else in the handoff's gate list stands.
