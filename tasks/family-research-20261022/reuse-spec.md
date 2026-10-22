# Reuse finished research boxes

The user now explicitly requires each box that finishes its assigned fits to help
the others. This supersedes independent stop-after-shard behavior when useful
unstarted work remains. Existing preservation and scientific restrictions remain.

Use existing Python stdlib/boto3, SSM and four machines; no new resources or IAM.
Source/tests stay in the existing full-context-audit/scripts directory. Commands:
python3 -m unittest test_family_reuse test_family_completion test_family_save_stop
python3 -m py_compile family_reuse_support.py family_reuse_epoch.py

Implementation order and acceptance:
1. Test immutable per-task ownership overrides. Move ONLY freshly enumerated
   pending keys, never completed/live/preparing work. Preserve every baseline
   cohort on its original owner with at least one retained task. Empty/duplicate/
   unowned keys and incomplete preparation metadata fail closed.
2. Add isolated executor support for filtered task ownership and helper cohorts.
   Regenerate only reproducible fold caches on recipients, same raw snapshot,
   algorithms/seeds/epochs; require identical prep groups/dimensions.
3. Keep A from importing any shard until ALL shards finish the current epoch.
   Publish epoch-scoped global-fit readiness. A alone finalizes/PCA/postprocesses.
4. A verified completed shard waits for reuse or global-fit readiness before stop.
   No stop while reassignment is being prepared. All save/integrity gates remain.
5. Provide fresh snapshot/pause, immutable epoch planning, exact coordinator-only
   handoff, and callback rearm. Running Julia/wrappers stay alive. Failures before
   commit resume original coordinators; after commit preserve disjoint new owner
   authority and recover missing work, never duplicate it.
6. Deploy/test on Linux, verify all captured fits and callback identities, update
   existing heartbeat to carry out reuse when a host becomes eligible, commit/push.

Numerical sources currently loaded are not edited. Each activation uses a new
isolated source copy and fresh PID/start-token/task/cache/output/report/CPU leases.
No raw restore/hash, successful fit rerun, data deletion or second finalizer.
Host RAM admission and swap support remain. V3 frozen; semantic gate NOT_PASSED.

Heartbeat scheduling supplies reassignment decisions; AWS callbacks still finish
and stop automatically if the desktop is unavailable, after all fitting completes.
Do not claim reassignment is armed until tested source and lifecycle rollout plus
the scheduled decision procedure are deployed and verified.
