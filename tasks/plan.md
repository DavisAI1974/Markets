# Standard monthly Frankie run: prior knowledge to live evidence

Canonical procedure: `research/kalshi/NG_EXHAUSTION_FRANKIE_MONTHLY_RUN_PROCEDURE.md`. Every new handoff must
place the procedure's required first-read block immediately after its title.

## Outcome

Turn the October construction into one reusable month-at-a-time pipeline. Every month begins by ingesting
the immediately prior month's frozen learned-knowledge pack, binds one immutable target-month roster, runs
the same paired-lane CPU/provider machinery, and ends by freezing the learned output that becomes the next
month's input. Month changes are configuration and immutable authorization changes, not runtime rebuilds.

## Architecture decisions

- Reusable code owns prior-learning verification, causal-prefix construction, paired lanes, the fixed
  helper-to-CPU map, concurrency, receipt hashing, progress, packaging, systemd launch, and first-evidence
  monitoring.
- A month config owns only the half-open interval, predecessor object, canonical object/knowledge manifest
  identities, expected object count, names, branch, and artifact prefix.
- A launch marker remains immutable and per launch. It binds the fetched remote implementation SHA plus the
  selected month config and manifests; it is never reused as mutable framework state.
- The first 1-2 accepted prefixes are the canary while the bounded full-month unit continues. Progress is
  reported as completed/remaining percentage and accepted-prefix count.
- Any observed failure receives the smallest wrapper/runtime correction and one focused regression. It does
  not reopen settled science, data registries, dependency sets, or broad suites.
- The current four paid helpers remain the accepted production path until a separate Nucleus shadow release
  proves that local structured helper-equivalent sections preserve Frankie's blind decisions. The cost target
  is two logical 5.6-sol invocations per paired prefix, one Frankie synthesis per lane, rather than ten.
- Do not relaunch October while evaluating Nucleus. Attempt 8 was deliberately stopped before provider calls,
  and its stopped unit is the current operational truth.

## Files produced by the October CPU correction

| File | Current responsibility | Standard disposition |
|---|---|---|
| `research/kalshi/frankie_full_stack_runtime_contracts_20260824.py` | Immutable CPU-affinity/timing contracts and hashes | Reusable framework |
| `research/kalshi/frankie_full_stack_runtime_adapter_20260824.py` | Four-worker executor, pinning, join-before-Frankie, durable ledger/event path | Reusable framework |
| `research/kalshi/frankie_causal_runtime_tools_20260824.py` | Thread-safe causal evidence journal | Reusable framework |
| `research/kalshi/frankie_full_stack_paired_lane_orchestrator_20260824.py` | Receipt validation/binding and sequential control-then-combined lanes | Reusable framework |
| `research/kalshi/tests/test_frankie_full_stack_runtime_adapter_20260824.py` | Fake-provider concurrency, affinity, ordering, and timing proof | Reusable focused test |
| `.github/workflows/ng_exhaustion_frankie_fullstack_october_20260824.yml` | Hash-locked package, unprivileged systemd wrapper, launch/evidence gate | Extract reusable monthly template; retain October instance |
| `research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_october_launch_workflow_20260824.py` | Workflow CPU/receipt/progress gate | Parameterize reusable test pattern |
| `research/kalshi/ng_exhaustion_frankie_fullstack_october_20260824.py` | October interval, event projection, and replay progress | Move month values to config; reuse generic runner |
| `research/kalshi/NG_EXHAUSTION_FRANKIE_FULLSTACK_OCTOBER_LAUNCH_20260824.json` | Exact-SHA October authorization | Keep immutable and month-specific |

No standalone progress or receipt file was added: contracts live in runtime contracts, execution/persistence
in the adapter, cross-lane hashes in the orchestrator, accepted-event projection/progress in the month runner,
and launch validation in the workflow and its focused test.

## Dependency graph

1. Prior-month learned-knowledge receipt and target-month config
2. Immutable source roster and causal-prefix binding
3. Reusable paired-lane runtime and durable evidence
4. Replay progress and next-month learned-output freeze
5. Two focused gates
6. Exact-SHA publish, marker, launch, and first-evidence canary

Each phase depends on the preceding phase. Control and combined lanes are deliberately sequential inside
phase 3; only the four helpers within one lane run concurrently.

## Reviewed file policy

The agents' inventories were reconciled against the current code. The phrase "change dates" means changing
one descriptor that also binds the lawful predecessor, exact target roster/count, raw-manifest identity,
and prior-learning identity. Dates alone cannot identify those inputs. The first 1-2 accepted prefixes are
an observation canary; the full-month unit continues without a stop/resume identity change.

### One-time standardization changes

| File | One-time action | After standardization |
|---|---|---|
| `research/kalshi/frankie_full_stack_runtime_contracts_20260824.py` | Replace October interval constants with validated descriptor-bound interval fields | DO NOT CHANGE monthly |
| `research/kalshi/frankie_full_stack_runtime_adapter_20260824.py` | Generalize October progress event/bounds; preserve CPU/provider execution | DO NOT CHANGE monthly |
| `research/kalshi/frankie_causal_runtime_tools_20260824.py` | No change expected | DO NOT CHANGE monthly |
| `research/kalshi/frankie_full_stack_paired_lane_orchestrator_20260824.py` | No change expected | DO NOT CHANGE monthly |
| `research/kalshi/frankie_fullstack_monthly_config_20260824.py` | Add strict descriptor loader/validator | DO NOT CHANGE monthly |
| `research/kalshi/frankie_frozen_knowledge_receipt_20260824.py` | Add canonical prior-learning pack verifier/receipt builder | DO NOT CHANGE monthly |
| `research/kalshi/ng_exhaustion_frankie_fullstack_monthly_20260824.py` | Extract the generic runner from the October wrapper | DO NOT CHANGE monthly |
| `.github/workflows/ng_exhaustion_frankie_fullstack_monthly_20260824.yml` | Add descriptor/marker-driven generic launch template | DO NOT CHANGE monthly |
| `research/kalshi/tests/test_frankie_full_stack_runtime_adapter_20260824.py` | Replace month-named fixture/event literals only where the generic contract requires it | DO NOT CHANGE monthly |
| `research/kalshi/tests/test_frankie_fullstack_monthly_contract_20260824.py` | Add one synthetic descriptor + prior-learning contract node | DO NOT CHANGE monthly |
| `research/kalshi/tests/test_ng_exhaustion_frankie_fullstack_monthly_launch_workflow_20260824.py` | Add one generic marker/workflow/receipt gate node | DO NOT CHANGE monthly |

The October runner, workflow, focused workflow proof, and marker remain immutable historical artifacts after
the generic equivalents exist.

### Normal month rollover files

| File | Policy | Contents |
|---|---|---|
| `research/kalshi/config/ng_exhaustion_frankie_fullstack_YYYYMM.json` | CHANGE EACH MONTH | Month bounds/label; predecessor and target roster identities; raw-manifest hash; prior-learning declaration hash; artifact namespace; canary size 1-2 |
| `research/kalshi/config/ng_exhaustion_frankie_frozen_knowledge_sources_YYYYMM.json` | CHANGE EACH MONTH | Immutable provider-visible prior-learning sources, byte ranges/lengths, hashes, authority classes, freeze identity |
| `research/kalshi/receipts/NG_EXHAUSTION_FRANKIE_FROZEN_KNOWLEDGE_YYYYMM.json` | GENERATED FOR THE MONTH | Canonical source receipts, aggregate knowledge hash, descriptor hash, and receipt hash |
| `research/kalshi/launch/NG_EXHAUSTION_FRANKIE_FULLSTACK_YYYYMM_LAUNCH.json` | GENERATED EACH LAUNCH | Fetched implementation SHA, descriptor/knowledge/framework hashes, branch/scope, and launch authorization |
| Run output `PREFLIGHT.json`, ledgers, journals, event/progress log, `FINAL_RECEIPT.json` | GENERATED EACH RUN | Durable execution evidence; never hand-edited input |

Branch, package SHA, wheelhouse SHA, marker commit, run/attempt, SSM command, unit/root/output names, first-event
IDs, and artifact receipts change per launch but are derived and recorded automatically. AWS target/credential
locations are protected deployment configuration, not monthly source edits.

## Final monthly runbook with associated files

| # | Step | Files that change or are generated | Files explicitly unchanged | Focused verification |
|---:|---|---|---|---|
| 1 | Freeze prior month | Prior month `FINAL_RECEIPT.json`; generated frozen-knowledge pack/receipt | Runtime, lanes, workflow, tests | Final progress 100/0; chains and freeze hash validate |
| 2 | Author next-month descriptor | `config/...fullstack_YYYYMM.json` | All implementation/workflow/test files | Exact UTC half-open interval, predecessor, roster/hash/count, manifest and prior-learning hash |
| 3 | Declare prior learning | `config/...frozen_knowledge_sources_YYYYMM.json` | Knowledge authority and sealed-wall code | Every byte/hash/range verifies; target answers absent |
| 4 | Generate knowledge receipt | `receipts/...FROZEN_KNOWLEDGE_YYYYMM.json` | Receipt builder | Independent canonical recomputation is byte-identical |
| 5 | Validate immutable prefix inputs | No hand edits; derived roster/prefix receipts | Causal/scientific modules | Deterministic order, monotone cutoffs, identical lane prefix/snapshot hashes |
| 6 | Run narrow prelaunch gate | No hand edits | Generic tests and runtime | At most two nodes: monthly contract and workflow/receipt gate |
| 7 | Publish month inputs | Config declarations + generated knowledge receipt commit | Runtime/workflow/tests | Remote diff contains only allowlisted monthly inputs; refetch; stop on drift |
| 8 | Generate and publish marker | `launch/...YYYYMM_LAUNCH.json` | Generic workflow | Marker parent is exact fetched implementation SHA; all hashes recompute |
| 9 | Prepare remote unit | Derived package/root/user/unit/artifact identities | Generic workflow/wrapper | Extract → restore repo traversal → unprivileged offline install → restrictive permissions; CPUs 0-3 present |
| 10 | Execute paired prefix | Generated lane ledgers/journals/provider/CPU receipts | Adapter, contracts, orchestrator, CPU map | Four helpers overlap on distinct singleton CPUs; Frankie fifth; control ends before combined starts |
| 11 | Accept first-event canary | Generated first `PAIRED_PREFIX_ACCEPTED` and progress receipt | Unit continues unchanged | Recompute both lanes' receipts/hashes; completed + remaining = 100; accepted count 1-2 |
| 12 | Continue and close month | Generated progress, ledgers, journals, `FINAL_RECEIPT.json` | Config, knowledge, marker, implementation | Monotone progress to 100/0; freeze learned pack for next month |

Normal-rollover acceptance: only the month descriptor and frozen-knowledge source declaration are edited;
the knowledge receipt and launch marker are generated; implementation, workflow, and tests remain byte-identical.
Changes to a raw canonical manifest, knowledge schema, dependency lock, model, CPU topology, or authority rule are
separate platform/data/science releases, never hidden inside a monthly rollover.

## Task 0: Establish the Nucleus source of truth and cost architecture

**Description:** Inspect `DavisAI1974/operator_hilbert_seq` read-only once GitHub actually serves it, locate
Nucleus and its launch/runtime boundary, and determine whether it can produce the four structured
helper-equivalent sections locally before one Frankie synthesis per lane. Compare with the user's desktop
copy only by git identity and file hashes if that copy is later pushed or uploaded; no runtime dependency may
point at a desktop drive.

**Current source state:** The visibility change propagated after the initial 404. The public scaffold resolves
on `main` at `5bc511c06d3048a510333910588b9a6305532ab2` (`2025-12-28T15:43:50Z`). It contains only
`app/main.py`, `app/nova_optimizer.py`, README/attributes/ignore files, and an empty QA workflow. It is not the
complete Nucleus build: its API computations are placeholders, the optimizer is local heuristic string
compression rather than Amazon Nova or a model, the README's core modules are absent, and required imports,
packaging, dependencies, weights, and real tests are missing. The user will supply links to the other builds in
the next chat; compare them before selecting an authority.

**Acceptance criteria:**
- [x] Exact public scaffold, default branch, remote HEAD SHA/date, and clean source inventory are recorded.
- [ ] Nucleus model/runtime, weights, dependencies, entrypoints, wrappers, tests, and missing local assets are
  identified from the other build(s) the user supplies.
- [ ] The proposed boundary keeps the immutable prefix, lane isolation, sealed answer wall, source citations,
  omission receipts, and probability/lock authority with Frankie.
- [ ] A 1-2-prefix shadow comparison defines quality, citation, latency, and token/cost gates before integration.
- [ ] No October launch, provider call, production-path modification, broad test, or historical replay occurs.

**Dependencies:** None

**Files likely touched:** Documentation only until the source-of-truth review and shadow design are accepted.

## Task 1: Define the monthly input contract

**Description:** Define one content-addressed config for the target month and one read-only prior-month
learned-knowledge manifest. Verify their complete lineage before replay or provider access.

**Acceptance criteria:**
- [ ] Exactly one prior month/predecessor lineage and exact manifest hashes are required.
- [ ] Target-month answer data remains sealed and no provider call precedes the ingest receipt.
- [ ] `PRIOR_MONTH_KNOWLEDGE_INGESTED` binds source month, roster, aggregate hash, and wall state.

**Verification:** One focused config/ingest contract node with synthetic manifests.

**Dependencies:** Task 0 architecture decision

## Task 2: Extract a reusable monthly runner

**Description:** Move October literals into the month config while retaining the immutable-prefix, paired-lane,
receipt, and progress machinery as one generic runner.

**Acceptance criteria:**
- [ ] The target interval is half-open and roster order/hash is deterministic.
- [ ] Both lanes receive an identical prefix/snapshot; control finishes before combined starts.
- [ ] Progress is monotone, content-addressed, sums to 100%, and freezes at 100/0.

**Verification:** Focused synthetic-month runner node; no historical replay.

**Dependencies:** Task 1

## Task 3: Extract the reusable launch template

**Description:** Parameterize month names/config/marker/artifact paths while keeping package hashing,
unprivileged execution, exact CPU gates, and first-event validation invariant.

**Acceptance criteria:**
- [ ] `CPUAffinity=0 1 2 3`, singleton helper affinities, and pre-provider fail-closed checks cannot vary.
- [ ] Package, wheelhouse, config, manifest, implementation, and marker identities are all bound.
- [ ] The wrapper is provider-readable during install and restrictive during runtime.

**Verification:** One focused launch-template/static node.

**Dependencies:** Tasks 1-2

## Task 4: Freeze the month-to-month handoff

**Description:** After lawful completion, produce a frozen learned-knowledge pack and receipt that is the only
knowledge input accepted by the following month.

**Acceptance criteria:**
- [ ] Final progress is 100%, causal/evidence chains validate, and learned outputs are content-addressed.
- [ ] The next month verifies the predecessor receipt without rewriting it.
- [ ] Failed/incomplete runs cannot publish a next-month knowledge authority.

**Verification:** Focused handoff round-trip with synthetic month N and N+1 manifests.

**Dependencies:** Tasks 2-3

## Task 5: Publish and operate one month

**Description:** Commit/push implementation, refetch, generate the exact-SHA marker as the next fast-forward,
launch, and monitor the first 1-2 accepted prefixes while the month continues.

**Acceptance criteria:**
- [ ] Only two focused gates run; no broad or settled-suite rerun.
- [ ] First accepted event durably proves both lanes, CPUs 0-3, helper overlap, lane non-overlap, and progress.
- [ ] Operators can report completed/remaining percentage and stop only the isolated month unit.

**Verification:** Exact remote SHA/marker ancestry plus durable first-event receipt recomputation.

**Dependencies:** Tasks 0-4

## Standardization checkpoints

- **After Tasks 0-1:** current October launch reaches first evidence; monthly input schema is frozen.
- **After Tasks 2-3:** one synthetic month passes the two focused runtime/workflow nodes.
- **After Tasks 4-5:** month N output is accepted unchanged as month N+1 input and the operating run exposes
  completed/remaining percentage.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Month-specific literals leak into reusable code | Recurring rebuilds | Single validated config; invariant runtime/template tests |
| Prior-month outputs are incomplete or mutable | Invalid knowledge lineage | Content-addressed freeze receipt; fail before replay/provider |
| Launch wrapper permissions drift | Pre-provider launch failure | Explicit extraction/traversal/install ordering gate |
| A failure prompts broad revalidation | Lost time and scope drift | One observed cause, smallest correction, 1-2 focused nodes |
| Nucleus repository or desktop copy is incomplete/stale | False architecture conclusion | Bind remote/branch/HEAD and compare tracked/untracked file hashes before testing |
| Opaque Nucleus summaries omit decisive evidence | Scientific and audit failure | Structured source-linked sections, omission manifest, full evidence retrieval, and blinded shadow gate |

---

# Frankie full-stack October implementation and launch

## Outcome

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
