# Post-census Frankie readiness plan

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
