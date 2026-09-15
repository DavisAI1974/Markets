# Claude review handoff — Frankie/BOSS dual-compute migration

Date: 2026-09-15
Owner: Greg Davis
Repository: `DavisAI1974/Markets`
Review branch: `chatgpt/frankie-32cpu-lossless-20260915`
Current tip when this handoff was written: `34490fcf40a1119704bea10a3e1d0dca99c6e035`
Base: `9a38157b696f1d92bf88b7cf112280695b44e136`

## Run this first

Run `using-agent-skills` first, then use the relevant code-review/debugging skills. Analyze before launching anything. Do not start Frankie, Granite, a market-data run, or a broad test suite until you have reviewed this patch and reported concerns to Greg.

## Owner direction — authoritative

This is a **dual-compute** design, not an either/or choice:

- **GitHub 16 CPUs**: native Frankie/BOSS orchestration, causal training, checkpoints and cycle state.
- **Retained RunPod 32 vCPUs + L40S**: Granite inference and Granite/service-owned CPU work.

The two machines may work concurrently on different owned phases. Do not split one native optimizer step across both hosts and do not create concurrent writers to the same Frankie checkpoint/model state.

After review/acceptance, Greg wants **cycle 0 run again from the beginning under a NEW run identity**. Preserve the original failed cycle-00 run, checkpoint, Granite result, Frankie principal result, logs, receipts and evidence unchanged. The new cycle-00 run must use the same lawful source/scientific configuration with only the corrected execution infrastructure.

## What was discovered

The prior assumption that cycle 0 had a 32-process Frankie worker pool was wrong. The native learning path is one causally ordered `NativeForecastLearner.step`: one CPU PyTorch forward, backward and optimizer update. PyTorch internal CPU threading can use multiple cores. `BossTrainingCheckpoint` records `torch.get_num_threads()` in its runtime binding, so a thread-count change cannot be silently applied to an existing checkpoint.

The actual Sunday host already contains two important Codex optimizations that were initially overlooked and were preserved:

1. `VerifiedJournalReader` is wired into the actual host for immutable source-prefix snapshots.
2. `PreparedContextCache` is wired into the actual host so an expensive context preparation can be reused under exact identity checks.

## Changes made

### Lossless bounded parallel journal validation

Modified `research/kalshi/frankie_boss/verified_journal_reader.py`.

Row-local JSON/decode/canonical-hash work can run in a bounded `ProcessPoolExecutor`. The ordered parent process still enforces ordinal order, previous-hash continuity, final count/head and immutable-tail checks. No row or field is dropped, reordered, averaged, normalized, smoothed, or retained-but-uncounted. Standalone default remains one worker; production chooses the worker count explicitly. Worker processes force OMP/MKL/OpenBLAS/NumExpr internal pools to one thread to prevent nested oversubscription.

### Explicit native CPU policy

Added `research/kalshi/frankie_boss/cpu_runtime.py`.

Native Frankie now defaults to **16** workers / 16 PyTorch intra-op threads / 1 inter-op thread. The policy fails closed if the host exposes fewer CPUs than requested and must be applied before model/checkpoint construction. It does not alter model inputs, calculations, planes, evidence, loss or optimizer order.

### GitHub16 launcher

Added `research/kalshi/frankie_boss/operations/run_actual_sunday_github16.py`.

It applies the 16/16/1/1 native policy before importing/running the actual Sunday host. A misleading native `run_actual_sunday_32cpu.py` created earlier in the session was deleted after Greg clarified that the 32 CPUs belong to the RunPod/Granite side.

### GitHub cycle-0 workflow scaffold

Added `.github/workflows/frankie_sunday_cycle0_github16.yml`.

It targets a 16-core Ubuntu larger runner, checks `os.cpu_count() >= 16`, sets bounded thread env vars, installs CPU PyTorch, and runs only the focused CPU/reader checks. The result-bearing launch is intentionally gated because the old Sunday configuration contains local `E:/...` paths and the failed local checkpoint. Do not enable the final launch until the exact lawful source/configuration package is restored for GitHub under its existing hashes/receipts and a NEW run identity.

### Dual-compute authority record

Added `research/kalshi/frankie_boss/DUAL_COMPUTE_TARGET_20260915.md`.

RunPod remains Granite's host. Its 32 vCPUs can own Granite/service CPU work and potentially Granite-specific preprocessing/tokenization/validation, provided that moving those tasks does not cross the native Frankie authority boundary. If journal-derived data is moved to the Pod, preserve the exact lossless format, verified-reader semantics, causal cutoffs and receipts.

## What is not done yet

1. **The lawful Sunday source/configuration package is not yet GitHub-restorable.** The active old config references local E: paths. A deterministic GitHub restoration package/manifest is still required before a result-bearing rerun.
2. **Granite-side 32-vCPU preprocessing has not been moved yet.** The Pod already owns Granite service/model serving. Review whether moving Granite-bound context encoding/tokenizer admission to the Pod is worth doing and whether its trust boundary remains clean.
3. **No result-bearing cycle-0 rerun has been launched.** That is intentional pending your review and the GitHub-restorable lawful package.
4. **Focused tests were added but were not executed from this ChatGPT connector session.** The GitHub workflow contains those focused test commands; do not report them as passed until an actual runner executes them.

## Review questions for Claude

Please answer these before launch:

1. Does the parallel verified reader preserve exact acceptance/rejection semantics and deterministic order relative to the old reader?
2. Is `ProcessPoolExecutor` safe on the GitHub 16-core Linux runner for this reader, including SQLite read-only parent ownership and worker serialization cost?
3. Is 16 PyTorch intra-op / 1 inter-op the right native policy, or should some CPUs be reserved for orchestration/I/O while training runs?
4. Should `FRANKIE_CPU_WORKERS` remain the reader env name or be renamed to make native-vs-Granite ownership clearer?
5. What exact artifacts from the old E: runtime must be packaged into GitHub so the new cycle-0 run uses the identical lawful source/scientific configuration but a fresh checkpoint/run identity?
6. Which Granite-specific CPU tasks are safe to move onto the retained 32-vCPU Pod without creating a second authority over native evidence or training state?
7. Does the GitHub larger-runner label used in the workflow match the runner Greg actually has provisioned? If not, correct only the runner selector; do not change the 16-CPU target.
8. Do you see any path where the new run could accidentally reuse the failed cycle-00 checkpoint/principal output? If so, block it before launch.

## Scientific boundaries — do not change

Do not change Frankie inputs, calculations, planes, adapters, replay, Memory A, source records, causal ordering, loss definition, optimizer semantics, model architecture, or evidence retention. No silent dropping, arbitrary truncation, averaging, smoothing or normalization of raw evidence. Every retained record/field must still reach computation under the established contract.

## Files to review first

- `research/kalshi/frankie_boss/verified_journal_reader.py`
- `research/kalshi/frankie_boss/cpu_runtime.py`
- `research/kalshi/frankie_boss/operations/run_actual_sunday_github16.py`
- `.github/workflows/frankie_sunday_cycle0_github16.yml`
- `research/kalshi/frankie_boss/DUAL_COMPUTE_TARGET_20260915.md`
- `research/kalshi/frankie_boss/CPU_WORKER_RECOVERY_20260915.md`
- `research/kalshi/frankie_boss/tests/test_cpu_worker_policy.py`
- existing `operations/run_actual_sunday.py`
- existing `prepared_context_cache.py`
- existing `boss_training_checkpoint.py`
- existing `granite_runpod_service.py`

## Bottom line

The patch is intended to turn the previous mostly single-host/single-process bottleneck into a clean dual-compute system: **GitHub16 for stateful native Frankie, RunPod32+L40S for Granite/service work**, while retaining exact evidence and one native training authority. Review that boundary rigorously before Greg authorizes the new cycle-0 benchmark.
