# Frankie full-stack October and boss/Sol-replacement lifecycle

## Completed checkpoint: Frankie boss / Sol replacement seam

### Outcome

Persist the supplied from-scratch boss-model checkpoint and ReFRAG v2.1 source bundle in Markets,
then close only the two declared seams: the named QSV feature registry and the explicit internal-head
to BLD-1 projection. Keep the existing Frankie core, S135 provider seam, ReFRAG governance, and all
1,940 registered capability paths unchanged and addressable.

### Source decisions

- Repository-root `markets_adapter.py::MarketChunkEncoder.encode` at stable Markets ref
  `7f492b2bcb3934ff3e280f4ef0b44fc3d38b486e` is the executable authority for QSV/OD input order.
  The generic OD mirror, unrelated 45-column BTC experiment, 128-D dipole coefficient object, un-emitted
  Phase 1.5 attributes, and manifest prose are not substituted for the executable vector.
- `QSV_FEATURE_REGISTRY` is owned once by ReFRAG: the market encoder's 14 emitted named features
  followed by generated FFT-magnitude slot names derived from that encoder's configured `d_enc`.
- `TrunkConfig.qsv_dim` is derived from `len(QSV_FEATURE_REGISTRY)` and must equal it. QSV remains
  dormant by default through a separate `use_qsv` switch; masking and exact projection ablation stay
  unchanged when enabled.
- Internal-to-BLD projection is semantic, not a guessed numerical transform. The only public mappings
  are whole-session net USD, overnight gap USD, the already-decoded endogenous timestamp/value P50
  curve, and the already-governed `low|med|high` confidence label. Probabilities, logits, `p_up`, size,
  regime, contradiction, sigma, and evidence heads remain internal.
- The typed entry point projects through the authoritative S121-compatible 12-field BLD-1 boundary;
  CALL/ABSTAIN disposition remains independent of confidence and the market-path forecast.
- The boss trunk has exactly one shared temporal/causal graph branch, not three graph models.

### Increments

1. Persist exact supplied checkpoint and ReFRAG artifacts with SHA-256 provenance; materialize the
   executable checkpoint as an isolated `research.kalshi.frankie_boss` package.
2. Add RED tests proving registry order matches encoder output, width is derived rather than hardcoded,
   configuration drift fails closed, and optional masking/ablation remain exact.
3. Implement the ReFRAG-owned registry and trunk import/configuration changes; run the focused slice.
4. Add RED tests proving the four explicit internal mappings, endpoint semantics, malformed-output
   abstention, and non-leakage of additional learned quantities.
5. Implement the typed mapping and additive projector entry point; run focused and full checkpoint suites.
6. Run a fresh-context adversarial review, the agent-skills five-axis review, diff/secrets checks, then
   commit, push, and verify the branch through GitHub.

### Acceptance

- `qsv_dim == len(QSV_FEATURE_REGISTRY)` by construction and validation; no trunk width literal exists.
- Registry names are byte-order aligned with every vector emitted by the actual ReFRAG encoder.
- QSV is disabled by default, masked when partially unavailable, and exactly ablatable when enabled.
- Exactly four internal learned quantities cross into BLD-1; additional heads cannot leak through.
- Exactly one temporal graph branch exists in the trunk.
- The existing Frankie core/provider files and ReFRAG manifest governance are not modified or duplicated.
- The original 101-test checkpoint and all new tests pass from the persisted Markets package.

### Completion record

- Completed implementation: local `a31307729c00aa6f2996b711ab2fcf65c2ef2e3f`.
- Connector-published equivalent: `fd7d9a00ac2728660de674a06b6ce55e569311f0`.
- Remote branch: `codex/frankie-boss-sol-replacement-20260824`.
- Verification: 101 supplied tests reproduced; 160 bounded implementation/preservation tests passed;
  1,940 capability paths and 46 blocks remained wired for both lanes and all five roles.
- Review: no unresolved Critical or Required finding.

### Next continuation

Use `research/kalshi/FRANKIE_BOSS_SOL_REPLACEMENT_HANDOFF_20260824.md` as the governing handoff.
The next chat must preserve this checkpoint and choose the next bounded Sol-replacement tranche from
the actual remaining architecture. It must not reinterpret these two completed seams, replace
Frankie's core/provider boundary, reduce the capability registry, duplicate ReFRAG governance, or
expand the single graph branch into three models.

## Preserved prior outcome: full-stack October launch

Build a fresh additive runner at the remote target-branch base that implements every requirement in
`research/kalshi/NG_EXHAUSTION_FRANKIE_FULL_STACK_OCTOBER_NEXT_CHAT_HANDOFF_20260824.md`, passes the
15 launch gates, and launches the bounded full October interval `[2021-10-01, 2021-11-01)`. Preserve
the two historical dirty worktrees and all permanent services. Step-1 stays mechanically sealed until
the primary discoveries, movies, and first-lock/no-lock outputs freeze.

## Architecture decisions

- Main agent owns contracts, integration, commits, push, dispatch, and rollback. Temporary agents work
  on isolated branches/worktrees and do not push or launch.
- Implement a new runner identity; the old hourly canary is transport/forensic evidence only.
- Keep two explicit planes: a lossless authority-gated knowledge plane and a continuous V4-native causal
  market-data plane. Their shared boundary is content-addressed, typed, append-only records.
- S135 is the sole primary authority and Frankie is the sole primary probability/lock owner. The four
  live specialists return evidence packets on the same causal-prefix hash; no voting or averaging.
- S137/HippoRAG and provisional V4 components remain labeled shadow-only and cannot affect primary locks.
- New bridge behavior follows focused RED/GREEN tests; established V4 scientific modules remain unchanged
  unless a concrete launch error proves the smallest necessary repair.
- Final runtime correction: within each lane, execute the four helpers concurrently with the exact affinity
  map recurrence=CPU0, extension=CPU1, timing=CPU2, context=CPU3; keep control then combined lane order,
  then let Frankie synthesize. Persist affinity/timing receipts and fail before provider calls on fewer than
  four available CPUs.

## Final narrow launch checkpoint — do not reopen completed work

The only remaining implementation is four-CPU helper affinity/parallelism and its direct receipts. Do not
retest, rebuild, inspect, or revise the knowledge plane, 1,940/46 data registry, weather/storage ingestion,
H modules, provisional integration, sealed wall, dependency locks, credential hardening, source inventory,
or other completed subsystems. Do not perform a broad build inspection. Run only the focused CPU-path tests
named in `research/kalshi/NG_EXHAUSTION_FRANKIE_FOUR_CPU_HELPER_LAUNCH_HANDOFF_20260824.md`, publish the
result, regenerate the launch marker from the actual remote implementation SHA, and run October.

## Task list and dependencies

1. **Knowledge plane and answer wall** (parallel, no dependencies): content-addressed source catalog,
   authority/supersession/access policy, complete S135/90-play and frozen exhaustion retrieval,
   byte-range coverage receipts, forbidden-V3 denial, and pre-freeze Step-1 denial.
2. **Causal plane and opportunity process** (parallel, no dependencies): exact legacy/V4 crosswalk,
   continuous per-second derived geometry, predecessor bootstrap/lifecycle, causal clocks, lawful pre-birth
   opportunity instances, stopped-chain/negative controls, and discovery-mark contract.
3. **Four-helper/Sol/ledger runtime** (parallel, depends only on frozen contracts in this plan): four
   specialist roles with identical prefix hashes, actual `gpt-5.6-sol` invocation receipts, Frankie-only
   synthesis/locks, append-only movies/ledgers, shadow ablations, and observable progress events.
4. **Integration checkpoint** (main; depends on 1-3): reconcile agent commits into the clean integration
   worktree, resolve interfaces additively, and run focused contract tests.
5. **Launch surface** (main; depends on 4): unique bounded service/workflow, source/bootstrap validation,
   live logs/run URL, rollback/stop procedure, and no effect on permanent services.
6. **Bounded review** (main; depends on 5): one five-axis code review, fix only Critical/Required findings,
   then run the handoff's launch-critical tests and static workflow checks.
7. **Full October dispatch** (main; depends on all 15 gates): commit and push exact code, launch October,
   verify accepted Sol provider response plus first state/helper/reasoning/probability receipts, and report
   remote state without claiming predictive success.

## Acceptance checkpoints

- **Foundation:** all source bytes are covered; S135 and 90 plays are retrievable; forbidden V3 and sealed
  Step-1 reads fail closed; exact legacy/V4 mappings receipt causal availability.
- **Runtime:** canonical MBO replay is continuous; four live helpers share one prefix hash; Frankie alone
  synthesizes and locks; negative, weak, sparse, contradictory, abstention, and no-lock records persist.
- **Provider:** a real request resolves to `gpt-5.6-sol`, returns a provider response ID, parses successfully,
  cites retrieved evidence, and binds state/knowledge/code identities.
- **Launch:** unique October service is observable and reversible; full October starts only after all gates
  pass; permanent services and dirty worktrees remain unchanged.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agent changes collide at orchestration boundaries | Integration delay | Contract-first additive modules, isolated worktrees, main-only cherry-pick/integration |
| Knowledge catalog accidentally serves answer-derived material | Invalid blind experiment | Explicit authority/access enums plus denial tests before any model call |
| Rich MBO fields drift from legacy learned semantics | Recognition failure | Exact crosswalk with field provenance, causal-availability, and 100% receipts |
| A launch failure tempts broad rework | Lost time/scientific drift | Activate debugging skill only on observed error; smallest fix plus regression test |
| Runtime costs or volume become unbounded | Operational failure | Bounded October scope, resumable append-only ledgers, progress/cost receipts, unique stop command |

---

# Archived: October-only full-MBO/full-V4 shard plan

## Outcome

Produce an October 2021-only runner that reuses the frozen Step-1 MBO/V4 engine,
runs four balanced weekly shards on separate CPUs, and is accepted only after
continued-versus-fresh boundary-state proofs and monolithic scientific
equivalence. Do not auto-launch on push, alter the frozen engine, mutate
permanent Frankie, stop the existing three-month workers, or resume the
five-year serial controller.

## Architecture decisions

- Use Sunday-reopen DBN book-bootstrap boundaries (`20211010`, `20211017`, `20211024`) so the four
  target ranges are balanced around actual trading weeks rather than arbitrary
  calendar chunks.
- Prove each boundary by replaying the preceding weekly transition into a
  continued adapter and the boundary object into a fresh adapter, then require
  exact equality of every future-output-bearing V4 state component. The three
  transition proofs may run concurrently, but the gate validates their
  induction chain from the October 1 base.
- Let the previous shard own boundary warmup output through the proven equality
  cut; let the next shard replay the same boundary object and trim everything
  before that cut. This preserves each target second exactly once.
- Treat the frozen child segment receipt as internal execution evidence. The
  authoritative wrapper receipt binds the exact ordered object roster, engine,
  ruleset, boundary proof, target interval, and trimmed output.
- Compare monolithic and merged rows after one narrow provenance
  canonicalization: `source_dbn_object` must resolve to the already-bound
  manifest key/SHA and is replaced by the canonical S3 URI. No scientific field
  is ignored or normalized.

## Increments

1. Add failing tests for full-state boundary divergence, exact shard/receipt
   binding, coverage, and path-neutral scientific equivalence.
2. Implement the Sunday-reopen plan, differential state gate, target trimming,
   validated merge, and monolithic acceptance receipt without modifying the
   frozen engine.
3. Make the workflow manual-only and order it as tests -> three parallel
   boundary proofs -> four parallel shard workers -> validated merge ->
   monolithic equivalence/acceptance.
4. Run focused and frozen-engine regressions, static workflow checks, four Sol
   reviews, and a final code-quality review. Commit/push only after all gates are
   green; dispatch remains a separate explicit action.

## Acceptance criteria

- The exact 26-object October manifest roster is covered and no object is
  substituted.
- Every output second belongs to exactly one planned target interval; no empty
  shard, overlap, gap, reorder, or receipt swap can pass.
- Boundary proof covers books, FIFO order/priority, rolling activity rows and
  windows, integrity counters, sequence/clock watermarks, symbols, instrument
  roster, closed event groups, and aggregation cut safety.
- The accepted merged scientific row stream equals the existing monolithic
  October reference after the single allowlisted path canonicalization.
- Workflow pushes cannot launch compute; production dispatch requires an
  explicit manual action after proof artifacts exist.

## Informational pre-Frankie October picture

After the accepted October structural outputs exist, and before the planned
Frankie work, compare October `LEGACY_CONTROL` with October
`V4_NATIVE_FULL` through their immutable crosswalk. This same-period comparison
is the primary estimate of what deeper MBO information adds; use the frozen
54-week D0-D5 population only as historical context so period/regime differences
are not mistaken for an MBO effect.

Report matched/native-only/legacy-only exhaustion events, D0-D5/final-depth and
P/O/S/X changes, predecessor/descendant/reset structure, timing/gap changes, and
the added full-depth/FIFO/order-count/signed-flow/activity evidence available on
matched events. Preserve all disagreements and missing cases. This is a
curiosity-driven structural description only—not a test, acceptance gate,
prediction, trade claim, model launch, or Frankie update.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| A Sunday DBN book bootstrap is incomplete or retained state differs | Scientific drift | Fail that boundary and fall back to deterministic October-prefix warmup; never tune the science |
| Local stage paths differ across runners | False equivalence failure | Bind key/SHA, validate path suffix, canonicalize only `source_dbn_object` |
| Monolithic October finishes before shards are ready | No immediate runtime benefit | Keep it as the equivalence reference; the verified shard runner remains reusable |
| Extra workers contend or provide no speedup | Wasted spend | Record CPU quota and canary timing; keep only a measured improvement |

---

# Archived: Post-census Frankie readiness plan

## Outcome

When the active five-year Step-1 census completes, verify its exact outputs and freeze a deterministic, non-result-bearing handoff artifact for the next small V4 pilot. Do not dispatch a prediction, use holdout data, trade, or mutate permanent Frankie state.

## Increments

1. Make completion verification accept the promoted one-day-canary receipt and a successfully exited transient unit when the final receipt and exact outputs prove completion.
2. Build a fail-closed Step-1 receipt/population/crosswalk loader that emits an immutable V4 pilot-input registry without choosing a model or authorizing a result-bearing run.
3. Add a manual preparation workflow that downloads only the exact declared outputs, builds the registry, and uploads evidence. It must stop before empirical dispatch.
4. Run focused tests, static workflow checks, and an adversarial review; then commit and push the preparation without starting Frankie.

## Boundaries

- Active census candidate: `0d318335825b4a0e19a5a2881522f3da0374788e`.
- The user's accepted one-day canary is sufficient; do not rerun multiweek preflight.
- Exact pilot D/date/model/snapshot remain intentionally unset until the frozen registry exists and the user authorizes that manifest-bound result-bearing run.
- If final reconciliation fails on the obsolete three-week equivalence assertion, repair only that observed failure and reuse completed segment receipts; do not replay the five-year census.
