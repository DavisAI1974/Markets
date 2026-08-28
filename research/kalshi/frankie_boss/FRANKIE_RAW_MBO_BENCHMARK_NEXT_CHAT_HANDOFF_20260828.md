# Frankie raw-MBO benchmark — next-chat handoff

Date: 2026-08-28

Repository: `DavisAI1974/Markets`

Primary BOSS benchmark branch: `codex/frankie-boss-raw-mbo-benchmark-20260828`

Chat benchmark branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`

Governing engineering process: `addyosmani/agent-skills` release `0.6.7`.

## Read first

1. `research/kalshi/frankie_boss/SPEC-raw-mbo-blind-benchmark-restart-safety-20260828.md`
2. `research/kalshi/frankie_boss/PLAN-raw-mbo-blind-benchmark-restart-safety-20260828.md`
3. `research/kalshi/frankie_boss/FRANKIE_BOSS_TWO_DAY_BLIND_BENCHMARK_HANDOFF_20260828.md`, but treat its older Step-1-derived input language as superseded by the contract below.
4. `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py`
5. `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`
6. `research/kalshi/frankie_boss/FRANKIE_BOSS_BROWNFIELD_ARCHITECTURE_INVENTORY_20260828.md`
7. `research/kalshi/frankie_boss/FRANKIE_BOSS_GRANITE42_RESEARCH_CANDIDATE_20260828.md`
8. `research/kalshi/frankie_boss/state_serialization.py`
9. `research/kalshi/frankie_boss/benchmark_checkpoint.py`
10. `research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py`

## Controlling scientific contract

The benchmark input is **native raw Databento MBO DBN**, not Step-1 and not a reduced/collapsed surface.

The raw files are the canonical `.mbo.dbn.zst` sources for the October 1, 3, 4, and 5, 2021 set already preserved on the EC2/EBS research host. October 1 and 3 are warmup/development; October 4 and 5 are the held-out benchmark window.

Do not substitute:

- reduced/non-full-MBO seconds data;
- `V4_NATIVE_FULL_MBO_SECONDS.jsonl.gz`;
- MBP/top-10 projections as the scientific input;
- Step-1 event evidence;
- Step-1 self-fit/self-score;
- Step-1 labels, answers, typed state, reconciliation products, or any answer-bearing derivative.

Use native raw MBO event-by-event in receive-time causal order. Preserve full reconstructed depth, resting-order state, FIFO queue state, raw action groups, and provenance. `ts_recv_ns` is the causal availability clock.

Step-1 stays sealed until every required benchmark output listed below is frozen and hashed.

## Eight required blind locks

The accepted matrix is:

- `A-clean`: ChatGPT controls the Frankies on native raw MBO with no prior Oct-4/5 reduced-surface Frankie findings.
- `A-memory`: same ChatGPT controller and same native raw MBO, with only Frankie's unrevealed prior reduced-surface Oct-4/5 knowledge added.
- `B0-clean`: fixed-depth native BOSS baseline.
- `B0-memory`: fixed-depth native BOSS plus the same allowed prior memory package.
- `B1-clean`: BOSS plus whole-representation recurrent reasoning loops, no Granite.
- `B1-memory`: same recurrent BOSS plus the allowed memory package.
- `B2-clean`: recurrent BOSS plus Granite 4.2 8B reasoning assistance.
- `B2-memory`: same B2 plus the allowed memory package.

No current arm may receive another current arm's outputs before all required locks are frozen. BOSS/Granite must not see Chat outputs. The memory-assisted package must be the same pre-existing unrevealed reduced-surface Frankie knowledge for the comparable A/B memory arms; it must not contain Step-1/post-reveal content.

Only after all eight locks verify may Step-1 be unsealed once for reconciliation/scoring.

## Restart/progress contract

User explicitly requires interval saves so an interruption does not destroy large amounts of work.

Checkpoint rules:

- controller-neutral schema shared by A/B0/B1/B2;
- checkpoint only at an `F_LAST`-closed event-group boundary;
- source-manifest hash immutable through a run;
- monotonic raw-MBO record cursor;
- chained checkpoint hashes;
- atomic writes;
- final lock is terminal/immutable;
- progress percentage is `completed raw MBO records / total hash-bound raw MBO records`, never elapsed-time estimation;
- checkpoint at configurable event-group intervals, every raw-file boundary, and immediately before/after expensive Frankie/BOSS/Granite calls;
- exact resume must restore market continuation state, not merely a file cursor.

The existing `InstrumentBook.checkpoint_state()` is diagnostic-rich but not by itself sufficient for byte-equivalent restart. The next implementation slice must add exact adapter snapshot/restore including orders, FIFO levels, rolling activity rows/windows, integrity counters, clock/sequence watermarks, raw symbol state, and adapter record/group counters. Prove it with continuous replay versus checkpoint -> restore -> continue equivalence.

## Current checkpoint implementation status

As of the pre-handoff branch state, the following exist:

- `research/kalshi/frankie_boss/benchmark_checkpoint.py`
- `research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py`
- restart-safety spec and implementation plan

The checkpoint implementation includes:

- controller enum for A/B0/B1/B2;
- clean vs memory-assisted mode;
- exact record-count percentage;
- source/state SHA-256 validation;
- deterministic checkpoint hashing;
- hash-chain verification;
- F_LAST closure rejection;
- source/controller/memory-mode drift rejection;
- tamper rejection;
- terminal lock semantics;
- closed schema blocking Step-1/reveal/outcome passthrough;
- atomic write/load verification.

**Do not assume this tranche is complete merely because code/tests exist.** The next chat must run and record the focused GREEN verification first:

`python -m unittest research.kalshi.frankie_boss.tests.test_benchmark_checkpoint -v`

Then:

`python -m compileall -q research/kalshi/frankie_boss`

Run the repository-native BOSS preservation tests when the environment has pytest/torch.

No Frankie, BOSS benchmark, Granite, or reveal has been launched by this work.

## Current BOSS architecture truth

Do not assume the intended BOSS is already executable.

B0 exists as the current fixed-depth `Trunk` and must remain untouched as the baseline.

`GatedDeltaCell` is temporal sequence memory within a forward pass. It is **not** the whole-representation reasoning loop required for B1.

Whole-representation recurrent/adaptive reasoning depth and a compute-halting controller are not yet implemented.

Granite 4.2 8B is not yet wired into the executable BOSS runtime. It remains a research candidate. Existing deterministic `state_serialization.py` is useful as the controlled Granite-visible state boundary, but Granite invocation/runtime/model identity and objective warmup probes still need implementation and verification.

The intended full BOSS arm is B2 = B1 recurrent reasoning + Granite 4.2 8B assistance. B0/B1 are controls, not substitutes for B2.

## Raw-MBO brownfield seam

Reuse the tested native adapter instead of writing a new DBN parser:

- `research/ng_exhaustion_mbo_v4_full_state_replay_20260820.py::replay_dbn_files`
- `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py::V4MboAdapter`

The full-state bridge exposes complete reconstructed book/FIFO state at completed native MBO event groups while retaining `native_dbn_replayable=True`, `census_view=V4_NATIVE_FULL`, and `causal_availability_clock=ts_recv_ns`.

The earlier two-Frankie workflow is only a brownfield orchestration/sealing reference:

`.github/workflows/ng_exhaustion_two_frankies_prior_surface_blind_2day_20260825.yml`

Preserve its proven exact-checkout, keyless packet-stage, answer wall, sequential Frankie lock/freeze, source hashing, and receipt machinery, but replace its reduced-seconds scientific input seam with direct native raw-MBO replay. Do not silently reuse its `PRIOR_REDUCED_NON_FULL_MBO_SURFACE` input.

## AWS/resource facts

Existing research host:

- region: `us-east-2`
- instance: `i-08cee7171c0a76a04`
- current class: `r6i.2xlarge`
- host vCPUs: 8
- memory: about 64 GiB
- EBS: `vol-05a0b1e56f8c16478`

The Step-1 6-CPU future policy is a Step-1 memory-pressure policy, not a generic Frankie/BOSS cap. Frankie raw-MBO preparation/orchestration may use the 8-vCPU host subject to measured RAM/thread pressure. If Granite inference is local, record and monitor its actual CPU/RAM behavior separately.

## Agent Skills / brownfield rules

Use `addyosmani/agent-skills` tag `0.6.7` exactly, especially:

- `using-agent-skills`
- `spec-driven-development`
- `planning-and-task-breakdown`
- `context-engineering`
- `incremental-implementation`
- `test-driven-development`
- `doubt-driven-development`
- `git-workflow-and-versioning`
- `observability-and-instrumentation`
- `ci-cd-and-automation`
- `shipping-and-launch`

Characterize first. Make the smallest additive change. Preserve the fixed B0 baseline. Do not refactor adjacent systems. Verify before proceeding. Treat odd existing behavior as potentially load-bearing until disproven.

## Immediate next work, in order

1. Verify the checkpoint GREEN tranche and record receipts.
2. Add exact V4 adapter snapshot/restore with RED restore-equivalence tests, then GREEN implementation.
3. Build the hash-bound native raw-MBO source/count manifest and percentage probe. Only `.mbo.dbn.zst` raw sources may pass.
4. Adapt the Chat two-Frankie packet/orchestration seam to native raw MBO while preserving answer-wall and freeze machinery. Do not launch yet.
5. Wire B0 against the identical raw-MBO source/manifest.
6. Add B1 whole-representation recurrent reasoning beside B0, with B0 unchanged and explicit loop/depth receipts.
7. Add Granite 4.2 8B runtime/integration for B2 using the deterministic serializer and objective Oct-1/3 warmup probes before any held-out use.
8. Add controller-isolation and memory-package identity tests.
9. Build restart-safe launch workflows/progress probes for the eight required arms.
10. Run all launch gates, verify remote SHAs/source hashes, then launch. No Step-1 reveal until all eight final locks exist.

## Parallelization recommendation

If independent coding agents are available in the next environment, parallelize only after shared contracts are frozen:

- main/integration lane: restart state + raw-MBO manifest + Chat packet seam + final launch/reveal gates;
- agent lane B1: recurrent reasoning implementation/tests against untouched B0;
- agent lane B2: Granite runtime/serializer probes, depending on the serializer/shared state contract;
- review/test lane: preservation, contamination, and controller-isolation tests.

Agents must work on isolated branches/worktrees and must not launch, reveal, or overwrite shared orchestration boundaries. Main/integration lane owns reconciliation and publication.

## Stop conditions

Do not launch if any of these are unresolved:

- checkpoint/resume equivalence not proven;
- raw source/count manifest not hash-bound;
- any reduced/seconds/Step-1 input path can enter the benchmark;
- B1 loops are not actually executable/tested;
- B2 Granite is not actually integrated/tested;
- controller-output isolation not proven;
- memory-package identity not proven;
- percentage probe is elapsed-time based;
- launch diff contains unrelated changes;
- any intended arm can see Step-1 or another current arm before lock.

Negative/null/KILL findings are scientific results. Preserve them; never drop chains/events because they are inconvenient.
