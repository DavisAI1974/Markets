# Frankie/BOSS CPU-worker recovery — dual-compute target, 2026-09-15

Branch history began as `chatgpt/frankie-32cpu-lossless-20260915`, but Greg corrected the target during the session. The authoritative design is now **GitHub 16 CPU for native Frankie/BOSS + retained RunPod 32 vCPU/L40S for Granite/service-side work**.

## Native Frankie/BOSS

- Run native orchestration/training from GitHub Actions on the 16-core runner.
- Use up to 16 bounded verified-journal workers where safe and lossless.
- Use 16 PyTorch intra-op threads, one inter-op thread.
- Keep one causally ordered optimizer/checkpoint writer.
- Preserve inputs, calculations, planes, Memory A, evidence, cutoffs and learning order.

## Granite / RunPod

- Keep the retained L40S Pod and its included 32 vCPUs.
- Use those 32 vCPUs for Granite/service-owned work and, after review, Granite-specific preprocessing/tokenization/validation that can be moved without crossing native Frankie authority.
- Do not create a larger Pod merely for CPU.

## Lossless reader change

`verified_journal_reader.py` now supports explicit bounded parallel row-local validation through `ProcessPoolExecutor`. The parent process still verifies ordinal order, previous-hash continuity, final count/head and immutable source tail. Standalone default remains one worker; production launchers select the worker count explicitly.

Worker processes force OMP/MKL/OpenBLAS/NumExpr internal thread counts to one to avoid nested oversubscription.

## Existing Codex optimizations preserved

The actual host already integrates `VerifiedJournalReader`, `PreparedContextCache`, and retained-preparation recovery. Do not rebuild or bypass them.

## Cycle-00 owner direction

Preserve the original failed cycle-00 run and all original evidence unchanged. After Claude reviews/accepts the dual-compute migration and the lawful Sunday package is available in GitHub, run cycle 0 again from the beginning under a **new run identity**. This is not an in-place retry and must not reuse or overwrite the failed cycle-00 checkpoint.

## Important checkpoint identity rule

`BossTrainingCheckpoint` records `torch.get_num_threads()` in its runtime binding. Therefore a new GitHub16 run must create its checkpoint under the 16-thread policy from the beginning. Do not silently adopt an old checkpoint created under a different thread count.

See also:
- `DUAL_COMPUTE_TARGET_20260915.md`
- `GITHUB16_EXECUTION_TARGET_20260915.md`
- `operations/run_actual_sunday_github16.py`
- `.github/workflows/frankie_sunday_cycle0_github16.yml`
