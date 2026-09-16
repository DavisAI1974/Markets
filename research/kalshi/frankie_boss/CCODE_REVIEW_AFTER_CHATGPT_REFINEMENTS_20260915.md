# ccode review — ChatGPT refinements after dd37bfa3

Date: 2026-09-15
Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-lawful-recovery-clean-20260915`
Base / lawful failed-run commit: `050c5056c3657a954d6a3ee17f3a216999930768`

## Run first

Run `using-agent-skills` first, then the relevant review/debugging skills. Review and run focused tests only. Do **not** launch Frankie, Granite, market data, the retained Pod inference, or a result-bearing cycle.

## Why this branch exists

Your `dd37bfa3` review established that the prior dual-compute branch was on the wrong lineage. This branch is cut directly from the actual failed Sunday `boss_commit` (`050c5056`) so the lawful compact-reader/schedule/source-lineage implementation remains intact.

A previous staging branch named `chatgpt/frankie-lawful-recovery-20260915` accumulated temporary package-staging commits after the good EC2-resume fix. Ignore that branch. This **clean** branch was cut from `7981d0936a1c929d0b965ad9908fdcdcadd4f0cd` and is authoritative for this review.

I intentionally did **not** port the parallel `VerifiedJournalReader` work here. `FrankieCompactReader` already provides the stronger block-parallel implementation with spawn context, CPU affinity, bounded two-block-per-worker prefetch, exact seam verification and `host_runtime.data_workers` integration. Review that it remains byte-for-byte unchanged from the lawful lineage.

## Exact ccode restoration package now imported

The small-file package from your `dd37bfa3` branch is now grafted into this lawful branch by **exact Git object identity**, not reconstructed file-by-file:

- `C_Codex` tree: `4a2288986f83e0a13a1f6401feab847a33df9407`
- `FB` tree: `0f6615cb5956874479affdd3e0cc1b6ddbbd9500`
- `RESTORATION_MANIFEST.json` blob: `43fba82e294dc881ed72b1a1c46fbe878b215284`

So the 170 small files / ~24 MB package is now on the lawful branch without importing any runtime code from the divergent dual-compute branch. The 27 bulk files / ~18.35 GB remain external and must be restored and verified before launch.

Please audit the manifest for any bulk entry whose `files[].sha256` is null because the packaging script had a hash-size threshold. If any result-bearing input lacks an independently usable SHA-256 elsewhere in `pinned_files` / `secondary_pins`, close that gap on the source workstation before object-store upload. No bulk object is accepted by path/size alone.

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

The first launch persists the full runtime observation. EC2 resume compares only **stable** identity fields: toolchain, thread/determinism policy, OS/platform, CPU model, logical CPU count and total RAM. Dynamic available-memory/RSS observations remain diagnostic and no longer make a healthy resume fail.

This explicitly acknowledges your finding: 4-thread vs 8/16-thread reruns are different numerical identities.

### 3. Fail-closed persistent EC2 launcher

New `operations/run_actual_sunday_ec2.py` wraps the existing lawful host rather than replacing it.

First launch:
- requires a new `run_id` and nonexistent `run_directory`;
- applies numeric policy before importing the actual host/model path;
- creates `native-host-runtime.json` before result-bearing work;
- enables the safe training event callback.

Later prepare/recovery continuation requires `--ec2-resume` and an exact match to the persisted **stable** host/toolchain identity. An old run directory without this NEW identity can never be adopted. The wrapper switch is stripped before calling the underlying host parser.

Please verify this still supports the actual prepare -> retained-service -> principal -> training continuation pattern and doesn't block legitimate same-run recovery.

### 4. Clean cycle-0 rerun policy

`operations/build_ec2_rerun_configuration.py` now removes `host_runtime.retained_preparation_recovery` from the NEW configuration. Cycle 0 therefore recomputes its context preparation from the lawful source boundary instead of adopting the failed run's run-specific retained-preparation recovery.

The imported `actual-prefixes` package contains `prefix-00-witness.json` but no committed `prefix-00-preparation.json`; cycles 1..18 retain their separately verified compact prefix/seed machinery. Please verify that this really means cycle 0 starts clean while preserving the same source/cutoff/scientific inputs.

### 5. Path-preserving Windows EC2 proposal (please attack this)

The current receipts and secondary witnesses contain absolute `E:\...` and `C:\...` paths. Rewriting those nested JSON files would change their bytes/hashes and require migration receipts for the migration receipts. Instead, my preferred option is:

1. use a Windows 16-vCPU EC2 native host with persistent storage;
2. materialize the reviewed package under the **same original E: and C: paths**;
3. checkout this reviewed recovery commit at the same `host_runtime.repository` path;
4. restore the receiver checkout/tokenizer at their same C: paths;
5. change only `run_id`, `run_directory`, `host_runtime.boss_commit`, remove run-specific retained preparation recovery, and add the explicit `native_host_runtime` policy.

That should let the source/prefix/schedule evidence receipts keep their existing bytes and SHA-256 values. The config builder refuses a source config that is not the reviewed SHA `a5eef915...`, requires a fresh run id/directory, and otherwise preserves the evidence paths/pins.

Please determine whether any Windows-path/volume/receiver assumption makes this invalid. If path-preserving Windows EC2 works, I prefer it over rewriting evidence-bearing receipts on Linux. If it does not, explain exactly which contract forces rebasing and we will build the migration receipts instead.

### 6. Focused diagnostics tests

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

1. Diff this branch against `050c5056`: is every semantic code change observational/runtime-only as intended?
2. Does optional learner telemetry alter graph lifetime, autograd behavior, exception propagation or checkpoint mutation in any way?
3. Does `runtime_resource_probe.py` report Windows RSS/peak RSS correctly on the EC2/Python combination we will use?
4. Is the EC2 first-launch/resume stable-identity gate compatible with the actual multi-process/prepare-only lifecycle?
5. Does removing `retained_preparation_recovery` actually force a clean cycle-0 preparation without disturbing the lawful cycle-1..18 compact-prefix path?
6. Can we use a Windows EC2 host and recreate the exact E:/C: paths so the existing evidence receipts remain byte-identical? Try hard to disprove this.
7. If Windows EC2 is viable, what 16-vCPU memory class should we benchmark first? The old 16-GB host is not acceptable evidence of enough memory. Do not pick a final instance solely by intuition; we need native-step peak memory.
8. Design/run a **disposable, non-result-bearing** cycle-0 native-step timing on the real restored host at intra-op 8 vs 16. It must use a cloned/restored seed state and retained completed feedback without advancing the production checkpoint or calling Granite/Frankie. Record wall time, peak RSS and last substage. Discard model outputs afterward.
9. Confirm the existing compact-reader `data_workers=48` simply caps to available affinity CPUs (reserving CPU 0) and decide whether its requested value should remain 48 or become explicit host-specific policy. Measure; don't guess.
10. Audit the restoration manifest's bulk hashes. Every result-bearing bulk object must have an independently checkable SHA-256 before S3 upload/restoration; path/size alone is not enough.
11. Re-evaluate the N/N+1 RunPod overlap only after native cycle 0 is stable. The checkpoint-hash reuse contract change should remain a separate reviewed change, not be mixed into this recovery patch.

## Launch gate after review

Before any new cycle 0:
1. lawful clean branch reviewed;
2. exact restoration package present and hash-verified;
3. **all** bulk objects have independent usable SHA-256 pins and are restored by hash;
4. native host selected and runtime identity pinned;
5. 8-vs-16 step benchmark measured on that host;
6. enough memory demonstrated by measurement;
7. new run id + new run directory;
8. cycle-0 retained preparation recovery absent for the clean rerun;
9. old failed cycle-00 directory remains untouched;
10. retained RunPod/Granite authority remains separate;
11. Greg explicitly authorizes the result-bearing rerun.
