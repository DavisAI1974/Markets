# Spec: Raw-MBO blind benchmark restart safety

Date: 2026-08-28

Branch: `codex/frankie-boss-raw-mbo-benchmark-20260828`

Governing process: `addyosmani/agent-skills` release `0.6.7`.

## Objective

Add a controller-neutral, restart-safe checkpoint and progress contract for the October 4-5 raw-MBO blind benchmark before any expensive Frankie, BOSS, recurrent-reasoning, or Granite run is launched.

The checkpoint layer must make interruption recovery cheap without changing the scientific input, causal order, controller behavior, or blind/reveal wall.

The benchmark matrix governed by this spec is:

- A-clean: ChatGPT controls the Frankies on native raw MBO, without prior Oct-4/5 reduced-surface findings.
- A-memory: same ChatGPT controller and same native raw MBO, with only Frankie's unrevealed prior reduced-surface Oct-4/5 knowledge added.
- B0-clean / B0-memory: fixed-depth native BOSS control.
- B1-clean / B1-memory: native BOSS plus whole-representation recurrent reasoning loops, no Granite.
- B2-clean / B2-memory: recurrent BOSS plus Granite 4.2 8B reasoning assistance.

Step-1 remains sealed until all eight required outputs are frozen and hashed.

## Assumptions

1. Canonical market input is the native Databento `.mbo.dbn.zst` MBO stream. The reduced seconds surface, MBP projection, `V4_NATIVE_FULL_MBO_SECONDS`, Step-1 event evidence, Step-1 self-fit, Step-1 scores, and answer-bearing Step-1 products are forbidden benchmark inputs.
2. `ts_recv_ns` is the causal availability clock.
3. Checkpoints are allowed only after a completed `F_LAST` event group. A checkpoint taken inside an open event group must fail closed.
4. Checkpoints occur at configurable completed-event-group intervals, at every raw DBN file boundary, and immediately before and after each expensive model/controller invocation.
5. Progress percentage is derived from a hash-bound raw-MBO source/count manifest. Elapsed wall time is never used as the scientific percentage denominator.
6. A resume restores the exact market continuation state, not merely a file cursor. Orders, FIFO queues, rolling activity state, integrity counters, clocks/watermarks, source cursor, and controller/model checkpoint references required for byte-equivalent continuation are persisted.
7. The same checkpoint schema and verification rules are used by Chat, B0, B1, and B2. Controller-specific opaque state may be referenced by hash but cannot weaken the shared source/causal checks.
8. Existing fixed-depth `Trunk` remains untouched as B0. Recurrent reasoning and Granite remain additive later slices.

## Tech stack and commands

Language: Python 3, standard library for the checkpoint core.

Focused checkpoint tests:

`python -m unittest research.kalshi.frankie_boss.tests.test_benchmark_checkpoint -v`

Static compile gate:

`python -m compileall -q research/kalshi/frankie_boss`

Existing BOSS preservation suite, when the repository environment has pytest/torch:

`pytest -q research/kalshi/frankie_boss/tests/test_causal_packet.py research/kalshi/frankie_boss/tests/test_trunk.py research/kalshi/frankie_boss/tests/test_seam.py research/kalshi/frankie_boss/tests/test_state_serialization.py`

## Project structure

- `research/kalshi/frankie_boss/benchmark_checkpoint.py`: controller-neutral checkpoint/progress contract.
- `research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py`: small standard-library behavioral tests.
- later raw-MBO runner integration remains separate from this first slice.
- later recurrent BOSS and Granite runtime modules remain separate from this first slice.

## Code style

Prefer immutable/canonical JSON-compatible records and explicit validation over hidden mutable state.

Example shape:

```python
checkpoint = build_checkpoint(
    run_id="B2-clean",
    sequence=12,
    source_manifest_hash=manifest_hash,
    completed_mbo_records=420000,
    total_mbo_records=1000000,
    event_group_open=False,
    adapter_state_hash=adapter_hash,
    controller_state_hash=controller_hash,
    previous_checkpoint_hash=previous_hash,
)
```

No unrestricted passthrough mappings for answer-bearing content.

## Testing strategy

TDD is mandatory.

RED tests must prove the absent implementation is required for:

- deterministic checkpoint hash;
- monotonic sequence and completed-record cursor;
- source-manifest immutability;
- checkpoint hash-chain integrity;
- rejection of mid-event-group checkpoints;
- rejection of progress outside `[0,total]`;
- resume rejection after final lock;
- tamper detection;
- percentage derived exactly from completed/total MBO records;
- controller identity and clean/memory mode retained in the checkpoint;
- Step-1/answer/reveal labels rejected from checkpoint metadata.

GREEN implementation must be the smallest standard-library code satisfying those tests.

## Boundaries

### Always

- Preserve every MBO event in causal receive order.
- Bind every checkpoint to the exact raw-source manifest.
- Write checkpoints atomically in runtime integration.
- Verify the full checkpoint chain before resume.
- Persist negative, null, contradictory, abstention, no-call, and KILL outputs.
- Keep progress observable independently of scientific results.

### Ask first

- Changing the benchmark arm matrix.
- Changing the held-out October 4-5 window.
- Changing the memory-assisted knowledge boundary.
- Changing the raw-MBO normalization semantics.
- Adding model downloads/provider calls or launching expensive compute.

### Never

- Read or serialize Step-1 answer-bearing artifacts before all eight locks.
- Substitute the reduced seconds surface for native raw MBO.
- Estimate percent complete from elapsed time.
- Resume from an unverified or source-mismatched checkpoint.
- Mutate a finalized/locked arm.
- Expose one current benchmark arm's outputs to another arm before all relevant locks.

## Success criteria

This slice is complete only when:

1. Focused RED tests are observed failing because the checkpoint module is absent/incomplete.
2. Minimal checkpoint implementation makes the focused suite pass.
3. Compile gate passes.
4. Existing BOSS files, especially `trunk.py`, are unchanged by this slice.
5. The remote commit is verified and the focused CI receipt is recorded.
6. No Frankie, Granite, BOSS benchmark, or Step-1 reveal is launched by this slice.

## Next slices after this one

1. Exact V4 adapter snapshot/restore, proven by continuous replay versus checkpoint-restore-continue equivalence.
2. Native raw-MBO packet/stream integration for the Chat lane using the same source manifest.
3. B0 fixed-depth controller integration.
4. Additive B1 recurrent reasoning controller with B0 preserved.
5. Granite 4.2 8B runtime/serializer probes and B2 integration.
6. Eight-arm blind execution with interval checkpoints and progress probes.
7. Single Step-1 reveal only after every required arm is frozen and hashed.
