# ccode review — ChatGPT refinements after dd37bfa3

Date: 2026-09-15
Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-lawful-recovery-20260915`
Base / lawful failed-run commit: `050c5056c3657a954d6a3ee17f3a216999930768`

## Run first

Run `using-agent-skills` first, then the relevant review/debugging skills. Review and run focused tests only. Do **not** launch Frankie, Granite, market data, the retained Pod inference, or a result-bearing cycle.

## Why this branch exists

Your `dd37bfa3` review established that the prior dual-compute branch was on the wrong lineage. This branch is cut directly from the actual failed Sunday `boss_commit` (`050c5056`) so the lawful compact-reader/schedule/source-lineage implementation remains intact.

I intentionally did **not** port the parallel `VerifiedJournalReader` work here. `FrankieCompactReader` already provides the stronger block-parallel implementation with spawn context, CPU affinity, bounded two-block-per-worker prefetch, exact seam verification and `host_runtime.data_workers` integration. Review that it remains byte-for-byte unchanged.

## Changes I made after your review

### 1. Safe native-step substage diagnostics

Files:
- `native_forecast_learning.py`
- `sunday_execution.py`
- `full_run_progress.py`
- new `runtime_resource_probe.py`

`NativeForecastLearner` now accepts an optional diagnostic event callback. Default is `None`, so existing callers preserve old behavior. The EC2 wrapper enables it.

Recorded stages are bounded names only:
- prepare_start / prepare_complete
- causal_scan_complete
- forward_start / forward_complete
- loss_complete
- backward_start / backward_complete
- optimizer_start / optimizer_complete
- step_complete / step_failed

Records contain request id, elapsed time, safe counts, error **type only**, process RSS/peak RSS, and system total/available memory where the OS exposes them. No exception message/traceback, tensor, label, prompt, credential, market record or model output is persisted.

The callback is best-effort: any diagnostic callback failure is swallowed by the learner and cannot change the training result. This is intended to answer the question the failed run could not: whether the next RuntimeError occurs in prepare, forward, backward, optimizer step, or post-check, and what memory pressure looked like at the last completed boundary.

Please scrutinize this especially for any accidental scientific or autograd effect. It should be observational only.

### 2. Explicit NEW numeric runtime policy

New `native_runtime_policy.py` requires a `native_host_runtime` block in the NEW rerun config. It pins and applies before model/checkpoint construction:
- Python version
- torch version
- numpy version
- intra-op threads
- inter-op threads
- deterministic-algorithm mode
- minimum logical CPUs
- minimum physical memory

It writes a resume-stable runtime identity containing the full `sys.version`, package versions, thread policy, deterministic flag, OS/platform, CPU model, logical CPU count and total memory. Dynamic RSS/available memory is excluded from the identity and belongs only in diagnostics.

This explicitly acknowledges your finding: 4-thread vs 8/16-thread reruns are different numerical identities.

### 3. Fail-closed persistent EC2 launcher

New `operations/run_actual_sunday_ec2.py` wraps the existing lawful host rather than replacing it.

First launch:
- requires a new `run_id` and nonexistent `run_directory`;
- applies numeric policy before importing the actual host/model path;
- creates `native-host-runtime.json` before result-bearing work;
- enables the safe training event callback.

Later prepare/recovery continuation requires `--ec2-resume` and an exact match to that persisted stable host/toolchain identity. An old run directory without this NEW identity can never be adopted. The wrapper switch is stripped before calling the underlying host parser.

Please verify this still supports the actual prepare -> retained-service -> principal -> training continuation pattern and doesn't block legitimate same-run recovery.

### 4. Path-preserving Windows EC2 proposal (please attack this)

New `operations/build_ec2_rerun_configuration.py` implements a different restoration idea from the Linux path rebaser you proposed.

The current receipts and secondary witnesses contain absolute `E:\...` and `C:\...` paths. Rewriting those nested JSON files would change their bytes/hashes and require migration receipts for the migration receipts. Instead, my preferred option is:

1. use a Windows 16-vCPU EC2 native host with persistent storage;
2. materialize the reviewed package under the **same original E: and C: paths**;
3. checkout this reviewed recovery commit at the same `host_runtime.repository` path;
4. restore the receiver checkout/tokenizer at their same C: paths;
5. change only `run_id`, `run_directory`, `host_runtime.boss_commit`, and add the explicit `native_host_runtime` policy.

That should let the source/prefix/schedule/retained-preparation receipts keep their exact existing bytes and SHA-256 values. The config builder refuses a source config that is not the reviewed SHA `a5eef915...`, requires a fresh run id/directory, and otherwise preserves the evidence paths/pins.

Please determine whether any Windows-path/volume/receiver assumption makes this invalid. If path-preserving Windows EC2 works, I prefer it over rewriting evidence-bearing receipts on Linux. If it does not, explain exactly which contract forces rebasing and we will build the migration receipts instead.

### 5. Focused diagnostics tests

New `tests/test_native_runtime_diagnostics.py` checks safe scalar output, invalid diagnostic stages, and resource-probe value shapes. These have **not** been executed by ChatGPT. Please run them plus the directly affected existing modules; do not broaden to a giant suite unless a focused failure requires it.

## Deliberately not changed

- `frankie_journal_reader.py` / `FrankieCompactReader`
- compact journal format or snapshot receipts
- `verified_sunday_schedule.py`
- Frankie inputs/calculations/planes
- model architecture
- loss or optimizer semantics
- causal cutoffs/order
- Memory A
- Granite transport/inference
- source evidence
- principal output contract

No cycle-0 rerun is authorized from this branch yet.

## Questions for ccode

1. Diff this branch against `050c5056`: is every semantic change observational/runtime-only as intended?
2. Does optional learner telemetry alter graph lifetime, autograd behavior, exception propagation or checkpoint mutation in any way?
3. Does `runtime_resource_probe.py` report Windows RSS/peak RSS correctly on the EC2/Python combination we will use?
4. Is the EC2 first-launch/resume identity gate compatible with the actual multi-process/prepare-only lifecycle?
5. Can we use a Windows EC2 host and recreate the exact E:/C: paths so the existing evidence receipts remain byte-identical? Try hard to disprove this.
6. If Windows EC2 is viable, what 16-vCPU memory class should we benchmark first? The old 16-GB host is not acceptable evidence of enough memory. Do not pick a final instance solely by intuition; we need native-step peak memory.
7. Design/run a **disposable, non-result-bearing** cycle-0 native-step timing on the real restored host at intra-op 8 vs 16. It must use a cloned/restored seed state and retained completed feedback without advancing the production checkpoint or calling Granite/Frankie. Record wall time, peak RSS and last substage. Discard model outputs afterward.
8. Confirm the existing compact-reader `data_workers=48` simply caps to available affinity CPUs (reserving CPU 0) and decide whether its requested value should remain 48 or become explicit host-specific policy. Measure; don't guess.
9. Your dd37 restoration package has 170 small files in Git and 27 bulk files for object storage. Identify the cleanest commits/files to bring onto this lawful branch without importing the wrong-lineage runtime code.
10. Re-evaluate the N/N+1 RunPod overlap only after native cycle 0 is stable. The checkpoint-hash reuse contract change should remain a separate reviewed change, not be mixed into this recovery patch.

## Launch gate after review

Before any new cycle 0:
1. lawful branch reviewed;
2. exact restoration package present and hash-verified;
3. native host selected and runtime identity pinned;
4. 8-vs-16 step benchmark measured on that host;
5. enough memory demonstrated by measurement;
6. new run id + new run directory;
7. old failed cycle-00 directory remains untouched;
8. retained RunPod/Granite authority remains separate;
9. Greg explicitly authorizes the result-bearing rerun.
