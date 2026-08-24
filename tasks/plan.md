# October-only full-MBO/full-V4 shard plan

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
