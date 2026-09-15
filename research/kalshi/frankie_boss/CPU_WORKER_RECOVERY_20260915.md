# Frankie/BOSS 32-vCPU CPU-worker recovery — 2026-09-15

Branch: `chatgpt/frankie-32cpu-lossless-20260915`
Base: `9a38157b696f1d92bf88b7cf112280695b44e136`

## Owner direction

Use the retained 32-vCPU capacity efficiently for Frankie/BOSS as well as Granite. Preserve every market record, field, causal cutoff, FIFO/full-book/dipole input, Memory A, calculation, plane and existing cycle-00 evidence. No silent dropping, truncation, averaging, smoothing or normalization is authorized by this performance work.

## What changed

1. `verified_journal_reader.py`
   - keeps the existing read-only/checkpoint-bound verified reader contract;
   - adds bounded ordered `ProcessPoolExecutor` validation;
   - production worker count is selected explicitly by `FRANKIE_CPU_WORKERS`;
   - row-local JSON/decode/canonical/hash work may run in parallel;
   - previous-hash continuity, ordinal order, final count and trusted head hash remain checked by the parent process;
   - batches are bounded to `workers * 4` rows;
   - worker processes force OMP/MKL/OpenBLAS/NumExpr thread counts to 1, preventing nested oversubscription;
   - standalone default remains one worker so unrelated tooling/tests do not silently spawn 32 processes.

2. `cpu_runtime.py`
   - declares the production policy: 32 verification workers, 32 PyTorch intra-op CPU threads, one PyTorch inter-op thread, one internal thread per verification worker;
   - configures the policy before model/checkpoint construction;
   - does not alter model inputs, calculations, planes, evidence, loss or optimizer order.

3. `operations/run_actual_sunday_32cpu.py`
   - production entry point applying the 32-vCPU policy before importing/running the actual Sunday host.

4. `tests/test_cpu_worker_policy.py`
   - verifies the declared 32/32/1/1 policy;
   - verifies exact ordered parity between single-worker and parallel verified reads;
   - verifies environment-selected worker count.

## Existing optimizations retained

The actual host already integrates `VerifiedJournalReader`, `PreparedContextCache`, and retained-preparation recovery. Do not rebuild or bypass them. The cache performs one exact preparation under bound identities and reuses independent copies while source/model/teacher/checkpoint identities remain unchanged.

## Critical cycle-00 boundary

The current Sunday cycle-00 evidence and principal/Granite outputs remain authoritative and must not be recreated. The retained `BossTrainingCheckpoint` records `torch.get_num_threads()` inside its runtime binding. Therefore:

- do **not** launch `run_actual_sunday_32cpu.py` against the retained cycle-00 checkpoint until its recorded thread count is read;
- if the retained checkpoint already records 32 PyTorch threads, the new policy matches it;
- if it records another value, migrate explicitly from the last lawful checkpoint after preserving its exact hash/state. Never silently mutate the old checkpoint identity;
- no Granite retry or Frankie principal replay is authorized merely to adopt this CPU policy.

## Next operational step

Read the retained cycle-00 `BossTrainingCheckpoint` runtime binding from the E: recovery state and record its `binding.runtime.threads` value. Then choose either identity-preserving resume (if 32) or explicit checkpoint migration (if different) before continuing cycle 00 training. All subsequent new-day runs should start through the explicit 32-vCPU launcher from checkpoint creation onward.
