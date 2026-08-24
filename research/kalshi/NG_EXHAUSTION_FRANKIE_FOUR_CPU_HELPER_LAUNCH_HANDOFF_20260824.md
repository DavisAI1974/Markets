# Frankie four-CPU helper correction and immediate October launch

> **Required first read:** Read and obey
> `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md` in full before this handoff.
> This handoff supplies month-specific identities and exceptions only. If it conflicts with the canonical
> procedure, stop and resolve the conflict explicitly rather than silently choosing one.

Date: 2026-08-24
Target branch: `chatgpt/ng-exhaustion-october-sharded-20260824`

## Governing scope

Take over the completed Frankie full-stack October integration. Change only the four-helper execution path so the four helpers run concurrently, one pinned to each of the four CPUs, then publish and launch October.

Do not reopen the integration. Do not retest, rebuild, inspect, or revise any other subsystem. Do not perform a broad repository or build inspection. In particular, do not revisit the knowledge plane, source inventories, 1,940-path/46-block registry, weather or storage ingestion, H modules, provisional components, sealed Step-1 wall, provider tool bounds, dependency locks, credential isolation, S3 staging, or prior scientific decisions. Those are complete and reviewed.

Do not rerun October Step-1. Do not create or push a launch marker until the CPU correction and its narrowly focused tests pass.

## Exact defect

The four roles exist, but `frankie_full_stack_runtime_adapter_20260824.py` currently invokes them through a sequential `for role in HelperRole` loop. There is no CPU affinity or concurrent helper executor. This wastes the four-CPU launcher capacity and increases full-month wall time.

## Required execution design

Within each lane, use exactly four concurrent worker threads and this immutable mapping:

| Helper role | CPU |
|---|---:|
| `HelperRole.RECURRENCE` (`recurrence`) | 0 |
| `HelperRole.EXTENSION` (`extension`) | 1 |
| `HelperRole.TIMING` (`timing`) | 2 |
| `HelperRole.CONTEXT` (`context`) | 3 |

- Use the identical immutable causal prefix and prefix hash for all four helpers.
- Pin each worker before its live provider call and verify its observed affinity is the expected singleton.
- Restore affinity when the worker exits.
- Fail before any provider request if CPUs 0, 1, 2, and 3 are not all available.
- Preserve result ordering by the existing `HelperRole` enum.
- Frankie remains the fifth provider call and starts only after all four helpers finish.
- Preserve lane order: run the control lane's four-helper batch plus Frankie, then the combined lane's four-helper batch plus Frankie. Do not launch eight helper workers across both lanes.
- Keep both lane clients, response IDs, ledgers, state hashes, and combined-only provisional behavior independent and unchanged.

## Required receipts and concurrency safety

Add an immutable, content-addressed helper CPU-affinity receipt containing at least role, requested CPU, observed singleton affinity, native thread ID, mapping version, start/end/duration timing, and receipt hash. Bind all four receipts and the exact map into each lane result and `PAIRED_PREFIX_ACCEPTED` event.

Make only the directly shared concurrent writers thread-safe: `DurableJsonlLedger`, `RecordingEventSink`, and `CausalEvidenceJournal` append/head/count paths. Do not refactor unrelated persistence.

Set the provider systemd unit to `CPUAffinity=0 1 2 3`. Its launch gate must require four valid role-to-CPU receipts per lane, four distinct CPUs, observed singleton affinity, valid hashes, and an effective CPU set containing 0-3.

## Allowed implementation files only

- `research/kalshi/frankie_full_stack_runtime_contracts_20260824.py`
- `research/kalshi/frankie_full_stack_runtime_adapter_20260824.py`
- `research/kalshi/frankie_causal_runtime_tools_20260824.py`
- `research/kalshi/frankie_full_stack_paired_lane_orchestrator_20260824.py`
- `research/kalshi/ng_exhaustion_frankie_fullstack_october_20260824.py`
- `.github/workflows/ng_exhaustion_frankie_fullstack_october_20260824.yml`
- The six directly corresponding test files named below.

Do not modify other files unless one of these focused tests produces a concrete CPU-path failure that cannot be corrected in the allowed files. If that occurs, stop and report it instead of expanding scope.

## Measure, then verify only this change

Capture the pre-change fact that the helper loop is sequential/unpinned. Measure the focused fake-provider helper-batch wall time under fixed delays. After the change, repeat the identical measurement and retain the optimization only if four helpers overlap and wall time is materially below the serial baseline.

Run only these focused tests:

```bash
python -m pytest -q \
  research/kalshi/tests/test_frankie_full_stack_runtime_contracts_20260824.py \
  research/kalshi/tests/test_frankie_full_stack_runtime_adapter_20260824.py \
  research/kalshi/tests/test_frankie_causal_runtime_tools_20260824.py \
  research/kalshi/tests/test_frankie_full_stack_paired_lane_orchestrator_20260824.py \
  research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_october_20260824.py \
  research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_october_launch_workflow_20260824.py
```

Required focused proofs:

- A barrier-based fake provider shows all four helpers simultaneously active on four distinct native threads with observed affinity sets `{0}`, `{1}`, `{2}`, and `{3}`.
- Fewer than four available CPUs fails before any provider call.
- Frankie synthesis starts only after the four-helper barrier completes.
- Both lanes retain the exact mapping without concurrent cross-lane helper batches.
- Tampered CPU identities, affinity observations, timing, or receipt hashes are rejected.
- Concurrent ledger, event-sink, and causal-journal records remain complete and hash-valid.
- The post-change helper-batch timing beats the same serial baseline by more than measurement noise.

Do not run the prior 104-test suite or any other broad regression/build inspection. Do not re-audit completed features.

## Publish and launch immediately after the narrow gate

1. Commit only the allowed CPU-path changes and focused tests.
2. Re-fetch the target branch and stop only on real remote drift.
3. Publish the CPU correction as a fast-forward implementation commit.
4. Regenerate `research/kalshi/NG_EXHAUSTION_FRANKIE_FULLSTACK_OCTOBER_LAUNCH_20260824.json` with that exact remote implementation SHA.
5. Publish the marker as the next fast-forward commit.
6. Monitor the push-triggered workflow through its focused build gate and first live acceptance evidence.
7. Confirm `systemctl show` reports CPUs 0-3 and verify the durable helper affinity/timing receipts in the first `PAIRED_PREFIX_ACCEPTED` event.

Do not stop after the CPU correction. Launch October in the same chat.
