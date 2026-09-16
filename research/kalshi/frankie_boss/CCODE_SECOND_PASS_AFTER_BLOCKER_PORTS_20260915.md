# ccode second pass — blocker ports after 6c48af7e

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/frankie-lawful-recovery-clean-20260915`
Lawful ancestor: `050c5056c3657a954d6a3ee17f3a216999930768`

Run `using-agent-skills` first. Focused review/tests only. Do not launch Frankie, Granite, market data, retained-Pod inference, or a result-bearing cycle.

## What was integrated from your review

Your review commit `6c48af7efdab027f0431b5acabc697b2712d5ca5` was a strict fast-forward from the ChatGPT branch, so the clean branch now contains your Windows RSS fix, 27/27 bulk-hash closure/addendum, restoration audit, disposable benchmark harness, focused test update, and full review doc exactly as pushed.

## Blocker 1 — retained Pod migration

I inspected `aa12fd0912575508d5bf3a5bae491f8e4bdc91d0` and selectively ported its migration semantics onto the lawful branch rather than merging its divergent parent lineage.

Ported:
- `.github/workflows/frankie_retained_granite.yml`: concurrency key now `ycf4v6lmave6xw`.
- `granite_retained_lifecycle.py`: `POD_ID=ycf4v6lmave6xw`; a provider-migrated Pod already in RUNNING state is validated and observed, never sent a second start.
- `granite_cloud_resume.py`: `validate_running_migration` from `aa12fd09`.
- `granite_retained_completion.py`: completion pins ycf and uses the migration-specific retained journal generation.
- `granite_retained_host.py`: migration receipt transforms the independently retained old pod-info into the exact migrated ycf identity, checks canonical `INFO_SHA256`, and uses the migration-specific S3 journal generation.
- `granite_runpod_cloud_control.py`: immutable intent validation accepts only the original name or exact `-migration` suffix for the same nonce.
- `granite_retained_migration_receipt.json`: exact migration receipt from `aa12fd09`.

Do not accept a mere constant swap as sufficient; review the whole migrated evidence chain above against `aa12fd09` and confirm no unrelated divergent-parent behavior was imported.

## Blocker 2 — SQLite sidecar restart trap

I did **not** alter the lawful `operations/run_actual_sunday.py` host globally.

New `source_lineage_resume.py` is recovery-only and duplicates the lawful `ActualHost.source_lineage` checks except for exactly one predicate: instead of rejecting any `-wal/-shm/-journal` pathname, it calls the already-audited `journal_prefix_snapshot._sidecars` rule.

Therefore:
- rollback journal => hot/refuse;
- WAL > 32-byte header => hot/refuse;
- zero/header-only WAL => not content;
- SHM residue alone => not content;
- every recovery receipt, file SHA, tail count/head, child anchor and source-origin check remains unchanged.

`operations/run_actual_sunday_ec2.py` subclasses `ActualHost.source_lineage` only for the NEW EC2 recovery path and calls this helper. The original lawful host remains untouched.

Please run a two-invocation scratch test proving invocation 1 can create harmless read-only sidecars and invocation 2 still passes lineage without moving/deleting them. Also prove a >32-byte WAL and a rollback journal still fail closed.

## Completion-workflow lineage leak closed

The source Sunday configuration still pointed `host_runtime.completion_workflow_ref` at the divergent `codex/full-frankie-boss-connection-20260915` branch.

`build_ec2_rerun_configuration.py` now requires `--completion-workflow-ref`, refuses that old divergent branch explicitly, and writes the reviewed recovery ref into the NEW config. `frankie_retained_completion.yml` already checks out the exact `inputs.code_commit`, while the publisher also verifies `git rev-parse HEAD == code_commit`, so final publication remains commit-bound.

Please verify that the final workflow ref we use exists at the same reviewed tip as `host_runtime.boss_commit` when the production configuration is generated. Branch drift should fail closed, not silently select a different completion implementation.

## Focused migration tests added

`tests/test_lawful_recovery_migration.py` covers:
- exact `-migration` intent acceptance;
- migration receipt old Pod -> ycf binding;
- migration validator restores the caller's recorded status;
- already-RUNNING migrated Pod produces `observe_migrated_start` and no POST start;
- header-only WAL/SHM residue is not hot, while WAL frames and rollback journal are.

These tests have not been executed by ChatGPT. Run them plus the directly affected retained-Pod lifecycle/resume/completion tests and the existing native-runtime diagnostics. Do not broaden unless a focused failure requires it.

## Disposable benchmark caveat

I briefly modified your benchmark to import the new recovery helper, then caught the identity error and restored your file byte-for-byte (`51589b7f...`). Your harness intentionally points `--repository` at the failed run's `050c5056` checkout so the saved scratch execution identity remains valid; it therefore cannot simply import new recovery-branch modules.

Please decide the clean benchmark mechanism now that the two recovery fixes are reviewed. Preferred options, in order:
1. apply only the reviewed `aa12fd09` migration and `_sidecars` recovery semantics **in memory inside the disposable harness**, clearly marked benchmark-only; or
2. construct a direct native-step harness from the cloned checkpoint/feedback that does not traverse retained-service admission at all, while still exercising the exact native learner path.

Do not weaken or skip a security check generically. The benchmark remains non-result-bearing and must never advance production state or call Granite/Frankie.

After that, run fresh disposable clones at intra-op 8 and 16 on the restored Windows `r7i.4xlarge`, capture wall time/peak RSS/last substage, then right-size memory from measurement.

## EC2 resume identity decision

You noted `cpu_model` stepping + total RAM can reject an EC2 stop/start. For the first 19-cycle result-bearing rerun I am intentionally keeping the strict same-observed-host identity and treating **no EC2 stop/start during the run** as an operational requirement. That is safer than letting one checkpoint trajectory resume on a possibly different CPU dispatch path. Do not loosen this in the second pass unless you find a correctness problem with keeping the instance continuously running.

## Gate after this pass

Report back before result-bearing execution with:
1. focused test results;
2. whether the selective `aa12fd09` port is complete/equivalent for the migrated retained service;
3. two-invocation sidecar-resume result;
4. completion workflow ref/commit-binding verdict;
5. disposable benchmark design correction;
6. if EC2 is available/restored, 8-vs-16 timing + peak RSS.

No cycle-0 result-bearing rerun until Greg explicitly authorizes it after this second pass.
