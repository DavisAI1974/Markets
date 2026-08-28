# Implementation plan: Raw-MBO blind benchmark restart safety

Governing spec: `SPEC-raw-mbo-blind-benchmark-restart-safety-20260828.md`.

This bounded plan is intentionally isolated from the shared `tasks/plan.md` after a stale-write guard fired there. Do not overwrite concurrent lifecycle planning merely to satisfy a filename convention.

## Dependency graph

`spec` -> `RED checkpoint tests` -> `minimal checkpoint core` -> `focused CI` -> `adapter exact snapshot/restore` -> `raw-MBO runner integration` -> `B0` -> `B1` -> `B2` -> `eight blind locks` -> `single Step-1 reveal`

## Phase 1: Checkpoint contract

### Task RCP-1 — RED tests

Acceptance:
- deterministic hash and exact progress percentage are specified by tests;
- source-manifest drift, tampering, skipped sequence/cursor regression, mid-F_LAST checkpoint, post-lock resume, and Step-1/reveal metadata all fail closed;
- tests use Python standard library only.

Verify:
`python -m unittest research.kalshi.frankie_boss.tests.test_benchmark_checkpoint -v`

Expected RED result: import/behavior failure before implementation.

Files:
- `research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py`

### Task RCP-2 — GREEN checkpoint core

Acceptance:
- minimal controller-neutral implementation passes RCP-1;
- checkpoint hash chain is deterministic and source-bound;
- no BOSS trunk/provider/Frankie/Step-1 code is changed.

Verify:
- focused unittest passes;
- `python -m compileall -q research/kalshi/frankie_boss` passes.

Files:
- `research/kalshi/frankie_boss/benchmark_checkpoint.py`

### Checkpoint RCP-A

- focused tests green;
- compile gate green;
- diff contains only spec/plan/checkpoint/test/CI files;
- no model or scientific run launched.

## Phase 2: Exact MBO continuation state

### Task RCP-3 — RED restore-equivalence tests

Acceptance:
- construct synthetic normalized MBO sequence crossing adds/modifies/cancels/trades and rolling windows;
- continuous replay final state must equal checkpoint -> restore -> continue final state;
- checkpoint is refused while an event group is open.

### Task RCP-4 — additive adapter snapshot/restore

Acceptance:
- exact continuation state includes orders, FIFO levels, rolling activity rows/windows, integrity, clocks/watermarks, event-group closure state, record/group counters;
- no native DBN is rewritten;
- existing adapter behavior remains unchanged when snapshot/restore is unused.

### Checkpoint RCP-B

- continuous-vs-resumed equivalence tests green;
- existing adapter focused tests green where environment supports them.

## Phase 3: Native raw-MBO benchmark stream

### Task RCP-5 — source/count manifest and progress probe

Acceptance:
- only `.mbo.dbn.zst` raw sources accepted;
- exact source SHA/bytes/date role and raw MBO record count bound into manifest;
- progress = completed raw MBO records / total declared raw MBO records;
- Oct 1/3 tagged warmup/development; Oct 4/5 tagged held-out benchmark;
- no Step-1-derived file accepted.

### Task RCP-6 — Chat-lane raw-MBO packet seam

Acceptance:
- replace prior reduced-seconds scientific input with native raw-MBO causal replay;
- preserve existing two-Frankie packet/lock/orchestration machinery;
- full depth/FIFO/raw actions remain available without seconds collapse;
- clean and memory-assisted modes are explicit and separately locked.

### Checkpoint RCP-C

- raw source identity and progress probe verified;
- no Frankie launch yet.

## Phase 4: BOSS controls

### Task RCP-7 — B0 fixed-depth integration

Preserve current `Trunk` byte-for-byte as the baseline controller.

### Task RCP-8 — B1 recurrent reasoning

Add shared-weight whole-representation recurrent reasoning beside `Trunk`; define bounded depth and explicit recurrence receipts without altering B0.

### Task RCP-9 — B2 Granite 4.2 8B integration

Use the existing deterministic state serializer; prove objective warmup probes before held-out use; bind exact model/checkpoint/runtime identity; B2 is B1 plus Granite assistance.

### Checkpoint RCP-D

- B0/B1/B2 selectable without changing raw evidence;
- controller isolation tests green;
- Granite cannot see Chat/B0/B1 current outputs.

## Phase 5: Blind execution

Run and checkpoint:
- A-clean, A-memory;
- B0-clean, B0-memory;
- B1-clean, B1-memory;
- B2-clean, B2-memory.

Every arm:
- same native raw MBO source manifest;
- same causal receive-time wall;
- interval saves + file-boundary saves + pre/post expensive-call saves;
- independent frozen final receipt/hash.

Only after all eight locks verify may Step-1 be unsealed once for reconciliation/scoring.
