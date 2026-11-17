# BuildMap calculation review and continuity

Base: `6655634c987adcbc543da87a7a789b16e015586d`. This increment extends the local application; it does not deploy or operate an inspected project. The former workflow is historical test material.

## Use the complete flow

1. Run `npm ci`, then `node src/cli.js /path/to/project`. The existing free map, goal walkthroughs, source/evidence inspector and basic task briefs remain free.
2. Open **Calculations & risks · Guide**. Search by calculation, file, parameter or recognized file product. Results render 25 per page. Choose a calculation to read attributed purpose, inputs, ordered written assignments/returns, saved outputs, callers and possible consumers. Follow supported calls with their argument expressions and return assignments, or return to callers. Recognized helper reads carry one-call argument substitutions; identifier nodes are substituted without rewriting quoted text. Symbolic paths do not become shared-product identities. Inspect source returns to the full free piece with its selected function expanded.
3. Review source-linked warnings. Opposite branches are contextualized, and directly linked cache/reuse/scheduling helpers are exposed. Matching calls inside a loop can reveal a repeated-read helper; matching written argument expressions can reveal repeated computation. Neither is an equivalence proof. Review mutable values, side effects, guards and existing caches before changing anything.
4. Inspect declared product coverage, stage contracts, worker/wait cues, workload dimension models and supplied runtime observations. The existing project-wide report remains available on the final mission card. JSON/API/export share the same model.
5. Prepare a bounded Guide task with actual acceptance criteria and exclusions. Review and agree on the exact paths. Save explicitly on this device, restore its original baseline after reload, or export/import JSON for the same project/checkout. Imported tasks cannot authorize a fresh automatic handoff until current context is reviewed. **Remove saved copy** retains the active task so it can be saved again. Starting a different task changes the active task, not the saved copy until you save.
6. After an agent changes source, refresh successfully and review later changes. The original agreed baseline remains unchanged; acceptance criteria still require real checks.

## Measurement and event import

`node src/cli.js PROJECT --import-measurements INPUT --analysis-output NEW_FILE` reads at most 1 MB of explicit input and creates a new JSON document. It does not overwrite existing files or automatically activate the document. Existing `.buildmap/analysis.json` is read through the same contained, bounded-file boundary as the scanner and merged. Conflicting IDs refuse import. Review the output before adopting it as the project's analysis file.

Input can be a version-1 document with `runtime` and/or `events` arrays, or NDJSON records:

```json
{"type":"buildmap-measurement","version":1,"observation":{"id":"run-a","identity":{"sourceIdentity":"input-and-program-revision","calculationIdentity":"algorithm-contract","workloadIdentity":"exact-input","environmentIdentity":"machine-and-worker-topology","metricScopeIdentity":"whole-process"},"counters":{"eligibleJobs":"10","completedJobs":"10","remainingJobs":"0","pairComparisons":"0"},"metrics":{"elapsedSeconds":0.5}}}
```

Stage-event records use `type: "buildmap-stage-event"`, `version: 1` and an `event` object with `id`, `runIdentity`, `clockIdentity`, nonnegative increasing `sequence`, `stageId`, and `event`. Supported names: `start`, `finish`, `read-product`, `write-product`, `load-checkpoint`, `save-checkpoint`. Finishes require `result: "passed" | "failed" | "interrupted"`; product/checkpoint events require `productId`. Declare the stages/products with the existing schema. No dependency is inferred between different clocks. Missing starts, unsatisfied declared predecessors and off-contract product events become review diagnostics; partial logs may explain them.

Logs inside the mapped project are bound to their exact bytes. Logs outside remain unbound unless explicitly bound to project-relative receipts. Bind relevant source files as well when source edits must invalidate a report. Neither a hash nor an importer authenticates the truth of a record. No monitoring credentials, target imports or workflow launches are involved. Counter arithmetic remains exact; unknown values remain unknown. Job counts, pair counts and modeled inner iterations remain distinct.

## Conditional dimension forecasts

Optional `analysis.workloads` entries have `id`, `workloadIdentity`, `independentCartesian: true`, `calculation: {path,name,sourceHash}`, current receipt `bindings`, and `axes: [{expression,min,likely,max}]`. Use nonnegative safe integers or decimal strings, with `min <= likely <= max`. Expressions must exactly match a captured nested-loop/comprehension axis model. Missing/changed source, unresolved axes or unbound/stale dimension receipts refuse estimates. Values are potential inner iterations under those supplied dimensions, not actual jobs, useful comparisons or elapsed-time predictions. Dependent axes cannot be multiplied by this model.

## Stateful coverage and checkpoint review

Independent and backward-rolling coverage retain the existing contract and per-column interval rules. Stateful calculations remain blocked unless `required.contract.semantics.boundaryPolicy` supplies nonempty `id`, `stateSchemaIdentity`, `review`, `owner`, `missingValuePolicy`, and `ordering: "ordered-rows"`.

Each `product.boundaryStates` entry supplies `id`, `row`, `stateIdentity`, an exact matching `contract` and current receipt `bindings`. Every missing output interval needs exactly one compatible state at its starting row. Duplicates, missing policy, stale bindings and identity mismatches block the affected extension. A conditional plan does not inspect state contents, authorize activation or replace comparison with an uninterrupted/full recomputation. Missing values, directionality, causal ordering and holes are preserved.

Checkpoint source records retain the exact enclosing branch syntax separately from nearby checks. Where a declared stage calculation and exact product path match uniquely, the report attaches that supplied contract and coverage status. Ownership and restart behavior are not inferred from a filename or a nearby existence check.

## Language and scale boundaries

Python retains top-level functions, direct class methods and module bodies; nested functions/classes, dynamic dispatch and runtime value propagation remain unsupported. JavaScript adds top-level function/arrow workflows, local exported ES-module call candidates, literal/unique-constant Node filesystem products, loops, assignments, returns and reuse cues. Shadowed imports and non-exported targets do not gain cross-file links. TypeScript/JSX and other inventoried languages retain their existing bounded import support; they do not receive a full calculation-risk verdict.

Written arguments, attributed documentation, possible file products and supplied contracts are separate sources of information. No arbitrary dynamic program can be certified from these source adapters. Source expressions may be abbreviated with an ellipsis; use the source inspector for details. JSON carries the complete captured analysis within parser limits. The whole-Python export option retains sequential bounded batches; ordinary polling remains bounded.

The historical local workflow test inventoried 789 files and parsed all 685 available Python files in about 29.4 seconds, producing 10,516 calculations and 16,647 supported source-call candidates at that inspection checkpoint. That checkout differs from the previous 1,469-file capture. Private source and detailed findings are not published. No scientific production workflow was launched. Whole-file parsing does not establish all nested/dynamic execution paths.

## Release boundary

The local user flow now connects explanation, risk review, optional observed data, bounded tasks and explicit continuity. It includes the first useful-release path plus conditional advanced review capabilities. Read the acceptance report for actual checks. It is not a claim that every acceptance criterion in the expansive 12-project portfolio is universally solved.

Accounts, pricing, payment-provider configuration and hosted paid-service access are not silently invented or activated. The local tool has no billing provider. A commercial launch requires those product decisions and credentials. Persistent continuity here is device-local and explicit JSON, not a shared account/history service. Arbitrary logs, unrestricted dynamic dispatch, semantic equivalence of arbitrary computations and authenticated production telemetry remain explicit boundaries, not hidden completion claims.
