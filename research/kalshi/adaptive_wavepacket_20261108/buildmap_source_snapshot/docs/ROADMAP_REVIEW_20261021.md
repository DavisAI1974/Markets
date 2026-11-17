# BuildMap roadmap review — 2026-10-21

Source: supplied `BuildMap_Codex_Project_Roadmap_20261021.docx`. Reviewed app base: PR #1, `feat/buildmap-v1-living-map` at `3298e79ca0ff8f9d48eea064e463bb1ea6e31108`. Default `main` is the initial commit `5375ceb`; it is not the app baseline. All 106 existing Node tests pass on Node 24.19.0 before changes. Prior browser checks are historical, not rerun evidence.

Work is isolated in branch `private/workflow-inspector-risk-20261021`, repository `/workspace/BuildMap`. The user confirmed the other BuildMap audit finished and authorized committing/pushing this separate branch. The repository is public; the branch name indicates isolation, not access control. The upstream PR and other branches are preserved. A fresh fetch found no newer upstream app changes beyond the reviewed base.

## Inventory before implementation

Existing = the acceptance scope is met; Partial = useful related implementation exists but the requested scope is incomplete; Missing = no implementation of the requested capability. References below are repository paths at the reviewed base.

| ID | Feature | Baseline | Evidence and remaining scope | Frankie priority |
| --- | --- | --- | --- | --- |
| BM-01 | Calculation & Data Flow Inspector | Partial | `src/code-guide.js`, `src/javascript.js`, `nodes[].codeGuide`, `public/app.js`: JavaScript parameters, returns, calls and source identity. No Python calculations, file-product lineage or workflow tracing. | First slice |
| BM-02 | Pre-Run Architecture / Workload Risk Review | Missing | Existing `scan.js` gaps concern implementation/evidence/declared wiring; they do not review workload, reads, memory or checkpoint reuse. | First slice |
| BM-03 | Producer–Consumer & Reuse Map | Partial | `src/imports.js`/`scan.js` source imports and declared dependencies exist, explicitly not runtime data flow. Shared data-product producers/consumers/identity/coverage are absent. | Literal products first; semantic identity later |
| BM-04 | Workload Estimator / Combinatorial Explosion | Missing | No symbolic loop expansion, grounded job counts or separate pair counts. | Nested-loop syntax first; counts only with evidence |
| BM-05 | Duplicate Computation / Data Reads | Missing | No duplicate-read/computation detector or cache recognition. | Repeated literal reads with uncertainty and reuse cues |
| BM-06 | Checkpoint & Restart Paths | Missing | BuildMap's own evidence receipts are not an inspected project's checkpoint/restart map. | Next: identities, receipts, guarded recovery |
| BM-07 | Incremental Table Coverage / Extension | Missing | File inventory/missing source is not table row/column/range coverage. | Later: exact compatibility; never fill missing values |
| BM-08 | CPU / Memory / I/O / Parallelism | Missing | No inspected-project topology, utilization or streaming barrier analysis. | Later; measurements required for bottleneck claims |
| BM-09 | Intended vs Actual / Agent Drift | Partial | Explicit dependency-plan drift in `scan.js`; `public/guide-tasks.js` bounded scopes and later snapshot comparison. No semantic workflow/stage-contract comparison. | Retain bounded tasks; stage wiring later |
| BM-10 | Guided Walkthrough + Task Briefs | Partial | Free declared walkthroughs/basic briefs and Guide function reading/reviewed tasks exist. No automatic project-wide calculation tour or durable continuity. | Reuse existing inspector; no billing work |
| BM-11 | Runtime Overlay / Savings | Missing | User-recorded evidence with source/input hashes exists, but no metrics/log importer or comparable measured savings. | Defer; never infer savings from static syntax |
| BM-12 | Frankie Dogfood / Regressions | Missing | Existing tests exercise BuildMap, not Frankie workload/reuse semantics. No Frankie checkout/data is present. | Small synthetic regression pack now; real-source review pending |

## Bounded first slice

Extend the existing scanner and Guide panel, without introducing a competing mapper. Use an optional isolated Python standard-library AST parser; pass captured source bytes, never import or run target code. Keep missing Python, parse failures, size limits and changed source explicit. Extract top-level function, direct class method and module-body syntax, arguments/returns, loops, comprehension axes/filters, calls, and supported literal file I/O. Correlate exact path expressions only as possible products: a matching filename is not compatible saved state, a table schema, or verified reuse.

Pre-run findings cover repeated literal read sites and nested-loop fan-out. Each includes source hashes/locations, affected calculation, confidence, impact rationale, safe review action, correctness tradeoff and required runtime validation. No actual job/remaining-pair/elapsed-time/savings figures are invented. AB/BA directionality remains intact. Cache/decorator/lazy/restart names are reported as unverified cues, never proof that repetition is fixed or that a new cache is needed.

Keep the full free map/evidence/goal/basic-brief contract. The deeper inspector remains an accessible Guide development preview, with no invented paid enforcement. Current check records can replace superseded records once the new observation supports the same scope. Evidence history, lineage and comparison are not deliverables; only current source support and honest scope matter.

## Completed follow-up implementation

1. Source-call candidates connect supported unique declarations, with arguments retained as written expressions. Persistence/load helpers, nearby guards and identity checks are reviewable without claiming compatible restart state.
2. Resource findings cover whole-result allocations, collection retention and possible per-iteration waits. Existing pool/chunk/release controls remain visible; utilization and actual bottlenecks need observations.
3. Optional small review records supply separate original/eligible/completed/remaining jobs, directional pairs and resource metrics. Current bound receipts and identical identities allow signed reported before/after differences; invalid comparisons are refused.
4. Exact contract-based coverage plans preserve per-column holes and rolling input overlap. Stateful extension stays blocked without a domain boundary-state policy. Declared stage contracts reveal missing references, cycles, producer conflicts and ordering questions.

The roadmap's October audit figures (161 GB, 99 layers, 32/6 GB indexes) are context, not current production measurements. No Frankie production command, dataset/checkpoint write, AWS access, deployment or remote merge is authorized by this implementation slice.

## Implemented review capabilities and current status

All BM-01 through BM-12 are now **Partial** against the full roadmap acceptance scope. No item is claimed fully Existing. BM-06 adds persistence/guard inspection, BM-07 conditional exact coverage/extension plans, BM-08 resource syntax risks and optional metrics, and BM-11 bounded reported observations/comparisons. BM-09 also checks declared stage contracts. Domain-specific compatibility policies, automatic semantic data propagation, live telemetry integration and current full Frankie validation are not implemented or claimed.

- `src/python-analyzer.py`: isolated standard-library Python AST reader for module bodies/top-level functions/direct class methods, parameters, calls, returns, assignments, supported literal I/O, nested loops and comprehensions. Syntax is not a business-purpose explanation or observed execution. Python AST columns use one-based UTF-8 byte offsets.
- `src/workflow.js` and `src/scan.js`: existing scan integration, bounded optional parser, source-linked calculations, possible data products, evidence-linked warnings and explicit unknowns. The `workflow` record is included in the existing JSON/API/export snapshot, separately from the free evidence/gap contract.
- `public/app.js`: per-piece calculation/product review and project-wide mission-card pre-run report; expandable findings, correctness/validation guidance and captured-source navigation. Existing Guide/free navigation, basic briefs and proof states stay intact.
- `tests/fixtures/workflow-pipeline.py`, `tests/workflow.test.js`, `tests/ui.test.js`: small non-executing synthetic regression pack. Tests cover possible shared preparation, 99-layer expansion, symbolic dimensions, arbitrary-precision potential iteration counts, distinct AB/BA calls, optimization cues, unknown checkpoint compatibility, false-positive suppression, stale source, parser availability/coverage limits, CLI/API/export and shared-client navigation/refresh.
- `.buildmap/project.json`: new files belong to the existing scanner and verification pieces; no competing engine or new paid entitlement system.
- `src/workflow-risk.js`, `src/review-evidence.js`, `tests/review-evidence.test.js`: saved-state/resource review, bounded read-only optional contracts, interval algebra, stage diagnostics, exact counters and comparable reports. [Schema, examples and operational limits](WORKFLOW_REVIEW.md) describe what is conditional, unbound, stale or blocked.

Validation: **143/143 Node tests pass on Node 24.19.0**, with Python 3.12.14. **14/14 scoped Chromium 154.0.8037.57 browser checks pass**, with no page errors. These cover navigation, escaped input, 390px layout, free inventory return, offline export without API/assets/polling, live source/receipt refresh, parse failures, rolling coverage, declared stages, reported job/pair counters/comparisons, explicit scan coverage and runtime-to-calculation navigation. The browser driver is `.buildmap/workflow-browser-check.mjs`; Playwright is separately provisioned, not a product dependency. Example rerun:

```bash
npm test
BUILDMAP_PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core/index.mjs node .buildmap/workflow-browser-check.mjs
```

The complete local test suite has not been rerun on Node 20; a real AWS whole-code scan did run successfully on Node 20.20.2. The earlier full 30-case browser suite, physical devices, exhaustive accessibility and real scientific end-to-end execution have not been revalidated. Current synthetic browser checks do not renew the old whole-MVP end-to-end scope claim. No user project, production dataset/checkpoint, PR merge or deployment is changed by this implementation.

Resume from `/workspace/BuildMap` on `private/workflow-inspector-risk-20261021`. The next application-specific step is read-only validation against the current complete Frankie workflow, using genuine contracts and observations rather than the synthetic example. No evidence-history subsystem is needed.

Current `.buildmap/evidence.json` replaces superseded component records after the actual final checks. Obsolete whole-outcome/completion claims are removed; that broader scope stays pending until observed again. No evidence archive or lineage record is added.

The current private AWS source checkout has now been located read-only, including the newer calculation commit. The whole-code scan completed against a stable current source commit: 1,856 files inventoried and all 1,469 Python files parsed, with no Python files skipped. The sequential beginning-to-end workflow handoff review remains in progress; no full runtime verdict is claimed. The active Search work and one-day run are individual parts, not the review boundary. October 6 and October 14 checkouts are not used as current-run evidence. Generic class-method/comprehension/scoped-review support is built and tested; no current Frankie findings or workflow verdict is issued from those older sources.

BuildMap is project-agnostic. All product code, tests and documentation are in the BuildMap Git repository on the separate branch. No analyzer rules name Frankie-specific schedulers or stages. The renamed `tests/fixtures/workflow-pipeline.py` uses generic lazy-job/subset/cache examples.

Source-call candidates now connect unique undecorated top-level Python functions within a file or through supported direct module, alias and relative imports. Call sites carry both source identities and locations; shadowed, reassigned, decorated, mutated, ambiguous, re-exported, external or unselected targets remain unresolved. The inspector navigates to callees and back to callers in live/captured maps; changed fingerprints disable detached links. Connections are source candidates, not runtime execution, scheduling or data-flow proof. No edges or upper proof states are added to the free map.

The two requested follow-ups are included: a project-wide scan-coverage panel names unreviewed/excluded Python and files outside the risk adapter, and optional runtime calculation references navigate to captured declarations. Ambiguous/stale explicit references never guess or fall back; stale hashes disable comparisons and navigation. These remain general-purpose features with synthetic/live/export regression coverage.

Explicit `--workflow-all --json` / `--workflow-all --html` snapshots remove the 64-file total cutoff by processing every eligible Python file in bounded sequential batches. YAML/TOML and systemd service/timer files are inventoried with unsupported execution semantics visible. This mode is opt-in and never runs on automatic live polling.
