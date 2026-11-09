> Current additions are documented in [the October 31 completion guide](COMPLETION_GUIDE_20261031.md): JavaScript workflow reading, imported stage events/measurements, conditional forecasts, reviewed stateful boundaries and explicit saved tasks. Earlier limits below describe the original Python slice unless superseded there.

# Calculation, reuse and pre-run review

Open the mission card's **Pre-run risk review · Guide preview** for a project-wide review, or a Python piece's **Inspect actual code · Guide preview** for its calculations. The same report is in `workflow` in JSON, `/api/map` and standalone HTML exports. BuildMap reads source and small optional review records; it never runs the mapped workflow or changes its products.

## Source inspection

Python syntax analysis shows module bodies, top-level functions, direct class methods, calls, assignments, returns, literal file products, loops and comprehensions. Supported imports connect unique undecorated top-level declarations across analyzed files. These are candidate source connections, not measured data flow or a runtime schedule.

Findings cover possible repeated reads, loop/comprehension expansion, whole-result construction/reads, collection growth across iterations, per-iteration wait syntax and saved-state compatibility questions. Each includes captured source/hash, uncertainty, impact, a review action, a correctness tradeoff and required verification. Expand a calculation to inspect existing pool, dispatch, release and chunk-parameter cues before proposing an optimization.

Saved-product review shows recognized persistence calls, helper-name cues, branch guards, nearby existence checks and identity-comparison syntax. A nearby check is not proof that it guards that load. Compatibility, ownership, atomicity, restart completeness and real reuse remain unverified. No filename is accepted as a checkpoint contract.

The trusted Python reader uses isolated standard-library AST parsing, never target imports. Limits: 64 Python files, 4 MB total source, 1 MB per file, 5 seconds and 16 MB parser output. Unselected, oversized, invalid and unsupported files stay visible. Dynamic dispatch/path evaluation, nested functions/classes, inheritance, shell/YAML execution and SQL semantics remain outside the adapter. Resource facts are local syntactic cues, not path-sensitive alias or lifetime analysis. Helpers and guards can bound apparent growth. Unknown receiver methods can have unrelated behavior. No findings is not clearance to run.

The mission review's **Scan coverage** panel lists Python status counts, the specific Python files left unreviewed and inventory files outside the Python risk adapter. JavaScript Guide or import support does not mean another language received workflow risk analysis. Counts describe the discovered/explicitly declared inventory, not every file on disk: Git ignore rules, excluded/hidden paths, deleted files, symlinks and unreadable files can affect that boundary. The structured record is `workflow.coverage`; exact programmatic Python selections also remain in `workflow.scope`.

For an entire codebase, use `node src/cli.js /path/to/project --workflow-all --json` or `--workflow-all --html /new/output.html`. This explicitly analyzes every eligible Python file in sequential batches of at most 64 files / 4 MB, with the same 1 MB per-file and 5-second / 16 MB per-parser-process limits. Failed batches split to isolate problematic files; missing Python and individual failures remain visible. The ordinary live/default review stays bounded. Whole-project mode requires a one-shot export so a large analysis does not run on every live poll. The scanner also inventories YAML/TOML and systemd service/timer definitions, while making their unsupported execution semantics explicit. Full inventory coverage does not prove every language, dynamic caller, scientific result or runtime handoff.

## Optional coverage and observation records

Supply `.buildmap/analysis.json` in the mapped project with `version: 1` and optional `products`, `stages` and `runtime` arrays. BuildMap does not create this file automatically. [The synthetic example](../tests/fixtures/workflow-analysis.json) exercises all three sections; its measurements are invented test data, not benchmarks. You do not need this file to use the map or static inspector.

Records are supplied metadata, not authenticated evidence. They never promote a piece to computing/verified/live. Missing records and counters stay unknown. Malformed or ambiguous IDs are excluded with visible diagnostics; valid independent records remain available. Unsupported document versions invalidate the document. No history store or mandatory lineage tracking is introduced; replace superseded records when appropriate. An optional baseline is needed only when you choose to compare reported performance.

### Products and extension plans

Each product has `id`, optional display `path`, `required: { contract, rows, columns }`, and explicit `available: []` or an array of saved-source declarations. Each available source has an optional `id`, `contract`, `regions: [{ rows: { start, end }, columns: [...] }]` and optional receipt `bindings`.

The required and available contracts must match exactly, including additional supplied fields. Required nonempty string fields are `sourceIdentity`, `calculationIdentity`, `schemaIdentity`, `axisIdentity` and `availabilityIdentity`. Use identities that capture the actual input revision, scientific formula, schema, ordered coordinate system and missing-value policy. BuildMap cannot establish these identities from arbitrary strings. Contract equality is a conditional planning input, not a safety certification.

`semantics` must specify one of:

- `{ "kind": "independent" }`: missing output rows require the same input rows.
- `{ "kind": "rolling", "lookbackRows": 2, "originRow": 0 }`: a missing output interval `[s,e)` needs causal input `[max(originRow,s-2),e)`. Use this only when that declared backward overlap fully describes the calculation; centered windows, forward dependencies and boundary policies need an appropriate independent domain review. Required rows cannot precede the origin.
- `{ "kind": "stateful" }`: partial extension is blocked until a domain-specific boundary-state policy is reviewed. BuildMap does not infer resets or a reusable partial state.

Row coordinates are nonnegative safe integers with half-open, nonempty intervals. Column names are exact, unique nonempty strings. Coverage is unioned separately per column, intersects only required ranges, preserves holes and uses arbitrary-precision cell counts without enumerating rows. Outputs include reusable intervals, missing output intervals and required input overlap. It never fills missing values, assumes AB/BA symmetry, writes a table, activates reuse or migrates a checkpoint. Verify an extended result against full recomputation including boundaries, ordering and missing values before adopting the plan.

Incomplete/mismatched contracts and stale bound receipts contribute no reusable coverage. Unbound matching declarations can contribute **under supplied contracts**, explicitly unverified. Explicit `available: []` means no saved source was declared, not that a filesystem search proved none exists. Existing product bytes are never opened by this planner. Returned statuses distinguish complete/partial under supplied contracts, absent, and incompatible/unavailable sources; excluded-source reasons remain visible.

### Declared stages

Each stage has `id`, optional `name`, `dependsOn: [stageId]`, `inputs`, `outputs` and `checkpointProducts` arrays of product IDs. Optional `calculation: { path, name }` matches a unique analyzed Python declaration; no match does not prove unused or missing code.

The reviewer flags missing/ambiguous references, dependency cycles, multiple declared producers and declared inputs whose producers are outside the predecessor set. These are inconsistencies/questions in the supplied plan, not observed runtime failures, deadlocks or proof of missing execution wiring. The existing free goal walkthroughs and Guide tasks remain the place to explain intent and agree on bounded changes.

### Reported runtime counters and comparisons

Each observation has `id`, optional `stageId`, `identity`, optional `counters`, optional `metrics`, optional `bindings` and optional `baselineId`. Identity requires nonempty `sourceIdentity`, `calculationIdentity`, `workloadIdentity`, `environmentIdentity` and `metricScopeIdentity`. Include machine/worker topology and metric aggregation conventions in those identities so comparisons have the same meaning. Extra identity fields must also match for comparison.

Optional `calculation: { "path": "pipeline.py", "name": "run", "sourceHash": "<lowercase SHA-256>" }` links a runtime record directly to a unique analyzed declaration. Omit `sourceHash` only if you intend an unbound source candidate. Without an explicit reference, an unambiguous stage calculation can supply the navigation candidate. Explicit unmatched/ambiguous references never fall back to another target; a mismatched hash blocks navigation and comparison. Explicit references in a comparison must resolve to the same declaration. Source buttons use the captured fingerprint, so detached controls cannot open changed source. These links help inspect which code a report claims to describe; they do not prove measured provenance or authenticate the observation. Current receipt bindings and identity checks still apply separately.

Counters: `originalJobs`, `eligibleJobs`, `completedJobs`, `remainingJobs`, **`pairComparisons`**, `reads`, `bytesRead`, `cacheHits`, `cacheMisses`. Use nonnegative safe integers or decimal strings of up to 100 digits. Jobs and directional pair comparisons are separate. Missing/null stays unknown; explicit zero stays zero. No remaining-work count is inferred. Optional `accounting: "eligible=completed+remaining"` requires all three counters and verifies that arithmetic; it is not assumed for workflows with other accounting semantics.

Metrics: `elapsedSeconds`, `cpuUtilizationPercent` (normalized 0–100), `peakMemoryBytes` (safe integer), `ioWaitSeconds`. Values must be finite and nonnegative; document process/system scope and normalization in `metricScopeIdentity`. Unsupported log formats are not parsed and no monitoring service is contacted.

`bindings` maps exact project-relative small receipt/source paths to lowercase SHA-256 values. Unbound reports remain visible as unbound. Missing/changed/outside/oversized bindings mark a report stale or unavailable. Matching local bytes establish receipt freshness only; BuildMap cannot authenticate their truth or infer which source they actually measured. Include relevant current source files as bindings if you need their edits to invalidate a report, within the size limits. Do not bind huge payloads; use an appropriately generated identity receipt.

Comparison requires distinct accepted observations, current matching receipt bindings, identical full identities and the same stage. Differences are **current minus baseline**, with exact signed counter arithmetic; unknown values stay unknown. A negative elapsed-time/byte difference is a reduction under the supplied records, not proof of a validated optimization. Workload/environment/scope mismatch, stale/unbound receipts or an absent/ambiguous baseline refuses comparison. Zero baselines do not produce a percentage or division. There are no static runtime/savings estimates.

## Bounds and operational limits

Analysis JSON: 1 MB, at most 100 records per section, at most 256 intervals/columns/regions per array and a global 100,000 region/column planning budget. Each record has at most 64 bindings. A scan reads at most 256 distinct bound files, 1 MB each, with a 4 MB total accepted binding budget (one additional bounded read can discover exhaustion). All reads must resolve inside the project. Nothing writes products, resumes jobs, changes worker counts, contacts AWS, installs target dependencies or executes source. Treat plans as review material and exercise your project's own correctness and restart checks before changing its workflow.
