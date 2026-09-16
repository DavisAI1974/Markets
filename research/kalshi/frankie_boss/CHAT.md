# CHAT — Frankie lawful recovery current state

Date: 2026-09-15
Repository: `DavisAI1974/Markets`
Authoritative branch: `chatgpt/frankie-lawful-recovery-clean-20260915`
Lawful failed-run ancestor: `050c5056c3657a954d6a3ee17f3a216999930768`

## Purpose

This file is the compact chat-state snapshot for the next conversation. It records the decisions and verified state that should not be reconstructed from memory.

## Scientific contract — unchanged

Do not change Frankie inputs, calculations, planes, adapters, replay, Memory A, model architecture, loss/optimizer semantics, causal order, or source evidence. No silent dropping, truncation, averaging, smoothing, normalization, or causal leakage. Every retained record/field must still reach computation.

## Current recovery architecture

Native/stateful Frankie/BOSS is moving to a persistent Windows EC2 host. RunPod remains the separate Granite/service host. Do not combine their CPU counts into one native optimizer process and do not create concurrent writers to native state.

The new cycle 0 is a fresh run/numeric identity. The failed cycle-00 directory remains immutable evidence and is never adopted as the new production checkpoint/run.

Windows path-preserving restoration is viable and preferred because receipts contain absolute `E:\...` and `C:\...` paths. Recreate those exact paths on EC2 rather than rewriting evidence-bearing receipts.

## ccode review incorporated

ccode reviewed the clean lawful branch and pushed `6c48af7efdab027f0431b5acabc697b2712d5ca5`. That review was fast-forwarded into the ChatGPT clean branch.

Verified/fixed there:

- branch lineage is correct;
- learner telemetry is observational;
- Windows RSS probe was fixed and measured;
- exact restoration package is grafted by Git object identity;
- all 27 bulk restoration objects are now hash-complete;
- `source.sqlite` SHA-256 is `181467d12a3ea289e67141be2f73e2c5ec068661c5c66c75c51eb30a2787dd6a`;
- bulk-hash addendum SHA-256 is `56b669aa1542fbf29fa0fd9870347a144ba589385fce0e9982487bee58580636`;
- `data_workers=48` is already a host-adaptive cap and should remain so;
- checkpoint restore alone measured about 939 MB working set / 1.14 GB private before the native step.

## Two runtime blockers ccode found, now selectively addressed

### Retained Pod migration

The lawful lineage had still pinned retired Pod `jvs75m56w8f73q`. Migration semantics from `aa12fd0912575508d5bf3a5bae491f8e4bdc91d0` were selectively ported onto the lawful branch, not merged wholesale.

The recovery branch now binds retained Granite to `ycf4v6lmave6xw`, carries the migration receipt/journal generation, validates the migrated intent, and observes an already-running migrated Pod instead of sending another start.

### SQLite sidecar restart trap

The lawful host rejected any `-wal/-shm/-journal` path even though its own read-only WAL opens can leave harmless sidecars. The original host file remains untouched. A recovery-only source-lineage verifier now uses the already-audited `_sidecars()` rule: rollback journal or WAL frames fail closed; header-only/empty WAL and SHM residue alone do not.

A focused second ccode pass is still required to verify the selective Pod migration and two-invocation sidecar behavior.

## Completion-workflow lineage

The old Sunday config pointed completion publication to the divergent `codex/full-frankie-boss-connection-20260915` branch. The EC2 config builder now requires an explicit `--completion-workflow-ref` and refuses that old divergent branch. Completion publication remains exact-commit bound.

## Native-step benchmark still required

The 8-vs-16 PyTorch intra-op comparison has not been completed. ccode built `operations/benchmark_native_step_disposable.py`, but its scratch identity deliberately uses the old `050c5056` checkout. Do not generically bypass security checks to make it run.

After the recovery semantics are reviewed, run a disposable, non-result-bearing benchmark on restored Windows `r7i.4xlarge` at 8 and 16 intra-op threads, with a fresh checkpoint, recording wall time, peak RSS and last substage. Do not call Granite/Frankie and do not advance production state. Right-size EC2 memory only from that measurement.

For the first result-bearing 19-cycle run, keep the same EC2 instance continuously running. Do not loosen the strict observed-host identity merely to support stop/start migration during this first run.

## Token / 19-cycle architecture question now with Claude

New addendum:

`research/kalshi/frankie_boss/CLAUDE_TOKEN_CONDENSATION_AND_CYCLE_REUSE_ADDENDUM_20260915.md`

It asks Claude to challenge and merge two architecture topics into the main review sheet:

1. additional exact token-condensation opportunities beyond the current compact/stacked work;
2. how to stop rebuilding the full 19-cycle machinery for every new group of days.

Highest-value proposals include virtual/content-addressed prefixes rather than 19 cumulative SQLite copies, one-pass 19-cutoff compilation, reusable `DAY_PACK_V1`, separating weight-independent preparation receipts from model/checkpoint receipts, static-prefix + exact cycle deltas for Granite, reversible compact/columnar grammar, golden seed checkpoint restore, and lawful warm-host reuse across adjacent day groups.

Wait for Claude's merged answer before implementing those architecture changes. They are separate from the immediate Sunday recovery path.

## Do not launch yet

No result-bearing cycle-0 rerun is authorized yet. Before launch: second ccode blocker-port review must pass, the disposable native benchmark must produce 8-vs-16 timing/peak-memory evidence, restoration/Windows EC2 must be verified, the final new-run config must be pinned to the reviewed recovery commit/workflow ref, and Greg must explicitly authorize launch.
