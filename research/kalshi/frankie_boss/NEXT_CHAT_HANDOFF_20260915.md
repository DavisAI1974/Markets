# NEXT CHAT HANDOFF — Frankie lawful recovery + architecture follow-up

Date: 2026-09-15
Repository: `DavisAI1974/Markets`
Authoritative branch: `chatgpt/frankie-lawful-recovery-clean-20260915`
Lawful failed-run ancestor: `050c5056c3657a954d6a3ee17f3a216999930768`
Branch tip immediately before this handoff file was created: `6ec0a9201c06f2fde1148b339bc09c20dc12c2d1`.

## Start here

Run `using-agent-skills` first, then the relevant context/review/debugging skills. Stay on the authoritative branch. Verify the remote branch tip before changing anything.

Read in this order:

1. `research/kalshi/frankie_boss/CHAT.md`
2. `research/kalshi/frankie_boss/CCODE_REVIEW_LAWFUL_RECOVERY_20260915.md`
3. `research/kalshi/frankie_boss/CCODE_SECOND_PASS_AFTER_BLOCKER_PORTS_20260915.md`
4. `research/kalshi/frankie_boss/CLAUDE_TOKEN_CONDENSATION_AND_CYCLE_REUSE_ADDENDUM_20260915.md`
5. Claude's merged/collapsed architecture sheet when Greg supplies it in the new chat.

Do not reconstruct the project from older divergent handoffs unless one of these files explicitly points there.

## Owner intent

Get the lawful Sunday 19-cycle run stable and executable with the smallest safe set of runtime/infrastructure changes. Preserve Frankie's science exactly. After Sunday is stable, use the Claude architecture answer to reduce repeated token/I/O/build work for future day groups.

Do not wander into broad A/B testing or discovery overkill. Do focused verification, fix real blockers, then move toward a working run.

## Immutable scientific contract

Do not change Frankie inputs, calculations, planes, adapters, replay, Memory A, native model architecture, loss/optimizer semantics, causal cutoffs/order, source evidence, or principal contract. No silent dropping, arbitrary limits, truncation, averaging, smoothing, normalization, or causal leakage. Every retained field/record must reach computation.

Native Databento MBO, full depth/FIFO/resting state/queue position/order age/raw action groups/event clocks/F_LAST and all required causal layers remain authoritative.

## Correct lineage and preserved evidence

The failed Sunday run used `boss_commit 050c5056c3657a954d6a3ee17f3a216999930768`. The recovery branch descends from that lawful lineage.

The original failed cycle-00 run remains immutable. It completed Granite + principal evidence, then failed in native `boss_training` after about 761 seconds with zero completed optimizer steps. Its old RuntimeError message was not retained. Do not overwrite or adopt that run directory as the new result-bearing run.

The new cycle 0 must start from the lawful source boundary under a fresh run ID, fresh run directory and new numeric/runtime identity.

## Restoration package

ccode's 170 small files (~24 MB) were grafted onto the lawful branch by exact Git object identity. The 27 bulk files (~18.35 GB) remain external.

Bulk hash closure is complete:

- `source.sqlite` SHA-256: `181467d12a3ea289e67141be2f73e2c5ec068661c5c66c75c51eb30a2787dd6a`
- addendum SHA-256: `56b669aa1542fbf29fa0fd9870347a144ba589385fce0e9982487bee58580636`
- audit result: 27/27 hash-complete, zero missing, zero conflicts
- original restoration manifest remains unchanged.

Windows path-preserving restoration is viable. Preferred first native host is Windows EC2 so the existing `E:\...` and `C:\...` receipt paths can remain byte-identical. Important conditions from ccode: assign `E:` explicitly, use `core.autocrlf=true` where required by the on-disk parser hashes, recreate the expected Python/toolchain path and versions, and restore the receiver checkout at its pinned C: path/commit.

## Current native-host plan

Native/stateful Frankie/BOSS: persistent Windows EC2.

Granite/service work: retained RunPod `ycf4v6lmave6xw` (32 vCPU + L40S), kept as a separate authority domain.

Do not split one native optimizer step across hosts and do not create concurrent native writers.

For the first 19-cycle result-bearing run, keep the same EC2 instance continuously running. The resume identity remains intentionally strict; do not loosen CPU/host identity merely to support EC2 stop/start during this first run.

## ccode review already integrated

ccode review branch `ccode/frankie-lawful-recovery-review-20260915 @ 6c48af7e...` was exactly one commit ahead of the ChatGPT clean branch and was fast-forwarded into it.

That integrated:

- measured Windows RSS fix;
- restoration hash addendum/audit;
- disposable native-step benchmark harness;
- focused diagnostic test update;
- full ccode review findings.

## Blocker 1 — migrated retained Pod

ccode discovered the lawful lineage still pinned retired Pod `jvs75m56w8f73q`, while the retained service evidence uses `ycf4v6lmave6xw`.

ChatGPT selectively ported the migration semantics from `aa12fd0912575508d5bf3a5bae491f8e4bdc91d0` onto the lawful branch rather than merging the divergent parent. The recovery branch now includes the migration receipt, ycf Pod identity/journal generation, migrated-intent validation, completion binding, and the rule that an already-RUNNING migrated Pod is observed instead of sent another start.

This selective port still needs the ccode second-pass review/tests described in `CCODE_SECOND_PASS_AFTER_BLOCKER_PORTS_20260915.md`.

## Blocker 2 — SQLite sidecar restart trap

ccode reproduced that the lawful `source_lineage` rejects sidecars that read-only WAL opens can create themselves, causing later host invocations to fail.

The base `operations/run_actual_sunday.py` remains untouched. A recovery-only `source_lineage_resume.py` uses the already-audited `journal_prefix_snapshot._sidecars()` liveness rule:

- rollback journal => refuse;
- WAL carrying frames beyond its header => refuse;
- empty/header-only WAL => not content;
- SHM residue alone => not content.

The new EC2 wrapper uses that verifier only on the recovery path. ccode must still prove a two-invocation scratch lifecycle passes harmless sidecars while real WAL frames / rollback journal still fail closed.

## Completion-workflow lineage leak

The old source config pointed completion publication at the divergent `codex/full-frankie-boss-connection-20260915` branch.

`build_ec2_rerun_configuration.py` now requires `--completion-workflow-ref` and refuses that old divergent branch. Before production config creation, verify the completion-workflow ref resolves to the same reviewed recovery implementation/commit expected by `host_runtime.boss_commit`. Completion publication itself checks out exact `code_commit` and verifies it.

## Native-step benchmark — still the immediate performance gate

The real expensive problem is the native step, not journal reading. ccode measured checkpoint restore at about 939 MB WS / 1.14 GB private, but the forward/backward peak is still unknown.

ccode's `operations/benchmark_native_step_disposable.py` deliberately uses the old `050c5056` scratch checkout so saved scratch execution identity remains valid. Do not import new recovery-branch helpers into that old checkout casually and do not generically bypass retained-service/security checks.

Second-pass task: choose a clean benchmark mechanism using only the reviewed migration/sidecar semantics or a direct native-step harness from cloned checkpoint/feedback. It must be non-result-bearing, never call Granite or Frankie, never touch the original run, and never advance production checkpoint state.

Then benchmark restored Windows `r7i.4xlarge` at PyTorch intra-op 8 and 16 with fresh checkpoint. Record wall time, peak RSS/private memory and last completed substage. Use the measured peak to decide whether later runs can right-size to 64 GB or 32 GB; do not guess.

`data_workers=48` stays. It is already a cap: on 16 visible CPUs the compact reader resolves it to 15 workers while reserving CPU 0 for the ordered consumer.

## Token condensation + reusable day/cycle architecture

Greg asked two additional architecture questions:

1. Are there more exact token-condensation opportunities beyond compact/stacked work?
2. Can we avoid rebuilding the 19-cycle machinery every time we start another group of days?

Our proposal sheet is:

`CLAUDE_TOKEN_CONDENSATION_AND_CYCLE_REUSE_ADDENDUM_20260915.md`

Key proposals: immutable static packet header + cycle deltas, reversible compact grammar/columnar blocks, content-addressed deterministic intermediates, separating weight-independent preparation from checkpoint identity, virtual/content-addressed prefix views instead of 19 cumulative SQLite files, one-pass 19-cutoff compiler, reusable source indices, `DAY_PACK_V1`, pre-sealed 19-cycle preparation surfaces, golden initialization/checkpoint restore, and lawful warm-host reuse.

Do not implement those yet. Greg is having Claude answer/challenge the addendum and collapse it with his existing architecture sheet into one consolidated source. In the new chat, use that merged Claude sheet as the authority for this optimization phase.

## Immediate next-chat sequence

First ingest Claude's merged sheet if Greg provides it. Reconcile its token/cycle-reuse answer with the current lawful recovery branch without altering science.

Separately finish ccode's second-pass verification of the Pod migration, sidecar restart fix, completion ref binding, and disposable benchmark design. Then run the 8-vs-16 benchmark on restored Windows EC2 when the host/package is ready.

Only after those gates pass should you prepare the final new-run configuration and ask Greg for explicit authorization to launch result-bearing cycle 0.

## Launch gate

No result-bearing Frankie/Granite/market-data run is authorized merely by opening the next chat. Launch only after focused blocker-port tests pass, two-invocation sidecar behavior is verified, retained Pod migration is verified, restoration is complete, 8-vs-16 native-step timing/peak memory is measured, final EC2/toolchain/run identity is pinned, final completion workflow ref is on the reviewed lawful recovery lineage, and Greg explicitly says to launch.
