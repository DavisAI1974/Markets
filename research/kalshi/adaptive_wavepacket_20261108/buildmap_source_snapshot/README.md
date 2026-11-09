# BuildMap

**A living map of software being built: what each piece does, which intended outcome it serves, what has evidence, and where a walkthrough is unfinished.**

BuildMap watches a repository by rescanning it every time its browser client polls. Planned pieces appear before their implementation exists. Source references add observed connections. Recorded observations and checks can advance a piece beyond source existence. A gap list keeps missing implementation, unobserved wiring, and unsupported claims in view.

The core contract is **existence, connection, computation, verification, and live use are different things**. BuildMap borrows the spatial language of workflow maps; it is a software map, not a workflow editor.

## Runtime observation increment

Explicit signed local Python observation is implemented; it is never started by mapping or refresh. See [runtime observation](docs/RUNTIME_OBSERVATION.md) for collection, trust, current-source/input checks, finite-case comparisons and limits, and [the finalization checklist](docs/FINALIZATION_CHECKLIST_20261031.md) for the remaining roadmap work. Billing stays last, with a Stripe stub.

## Current completion increment — October 31, 2026

**Calculations & risks · Guide** is a searchable, paginated reading view. Python and JavaScript calculations share inputs, assignment/return steps, source-call argument bindings, saved outputs, possible consumers and contextualized warnings. Function purpose comes from source documentation, a declared stage or the piece plan; it is attributed rather than invented. Calls and filenames remain source candidates.

Guide tasks can be explicitly **saved on this device**, restored with their original baseline, and exported/imported as bounded project-scoped JSON. Storage denial does not break the map. Imported baselines remain untrusted, and cannot authorize a new automatic handoff without reviewing current context. There is one saved task per project; saving replaces that project’s saved task. No task history service is introduced.

Structured runtime records and stage-event logs can be imported without executing the mapped project:

```bash
node src/cli.js ../project --import-measurements ../project/measured.ndjson --analysis-output ../reviewed-analysis.json
```

The output is a **new file** for review. Existing analysis is preserved and merged; conflicting IDs refuse import. After reviewing it, place the document at `.buildmap/analysis.json` yourself. Input logs inside the mapped project are bound by SHA-256. External logs remain unbound unless explicit project-relative bindings are supplied. Measurements, stage events and contracts are reported data, not authenticated execution. See [the completion guide](docs/COMPLETION_GUIDE_20261031.md) for schemas, boundaries, test evidence and release scope.

Source-based dimension forecasts require a captured calculation, matching loop axes, an explicit independent-Cartesian declaration and current dimension receipts. Jobs and directional pairs remain separate from potential iterations. Stateful coverage extension additionally requires a reviewed domain policy and exactly one current compatible boundary-state receipt at each missing-range start; unknown state blocks extension.

This increment is a local source release candidate. Accounts, commercial provider/pricing configuration and hosted paid-service activation remain unconfigured. Existing free map, walkthroughs and basic briefs remain free. Historical descriptions below refer to earlier checkpoints; the completion guide takes precedence for the new capabilities.

## Who BuildMap is for

BuildMap focuses on beginner-to-intermediate builders, especially people working with coding agents who need help understanding how a complete application fits together and keeping work aligned with its goal. Experienced developers can use the same source and evidence detail. The complete map, current goal walkthroughs, and basic focused task briefs are free. BuildMap Guide is the paid direction for deeper building and review help. Its JavaScript function-reading preview and initial Python calculation/pre-run risk inspector are implemented for review; reviewed task preparation and snapshot change review are also available; billing remains unconfigured; explicit device-local task saving and task JSON import/export are now available.

Setup still requires Node/Git commands. An optional local `--init` interview writes your initial goal and finished-product description without hand-editing JSON. An optional local `--walkthrough` interview also adds a goal and its ordered steps using existing mapped pieces. Guided `--piece` setup groups available files or declares planned pieces; `--extend-piece` adds files to an existing piece. Other existing-piece edits and recording evidence still require file authoring; this is not an existing no-code application builder.

## Python calculation and workflow inspection

The workflow-inspection development branch adds a general-purpose calculation and pre-run risk inspector. Open a Python piece and choose **Inspect actual code · Guide preview**, or select the mission card and choose **Pre-run risk review · Guide preview** for the project-wide report. Expand calculations and direct class methods to inspect declared inputs, assignments/transformations, returns, comprehension expansion, possible literal file products and consumers; expand warnings for repeated read sites and nested-loop fan-out. Source buttons open the captured function, with exact file/line and source hash. Calculation connections show possible callers and callees across files through supported imports; they do not establish execution order or actual data handoffs.

`GET /api/map`, `--json` and self-contained HTML snapshots include the structured `workflow` report. Inspection requires optional `python3` (3.9+), using only its standard-library AST in isolated mode. Missing Python, parse failures and bounded coverage are visible; the complete free map remains available. No target code is imported or executed.

The inspector also reviews saved-product loads/guards, whole-result memory risks, collection retention and possible per-iteration waits, while showing existing cache/chunk/pool/release cues. Optional `.buildmap/analysis.json` adds exact contract-based row/column coverage and extension plans, declared stage checks and reported workload counters. Rolling plans retain declared input overlap; stateful partial extension stays blocked. Comparable current receipt-bound observations can show measured differences; no static savings are invented. Products are never modified or certified safe to resume. Jobs and directional pair comparisons remain separate.

The project-wide **Scan coverage** panel names files left unreviewed and languages outside the Python risk adapter. Optional runtime calculation references link reported measurements to the captured calculation for inspection; stale or ambiguous references cannot select a target or justify a comparison.

To inspect every eligible Python file across a large repository, use `node src/cli.js /path/to/project --workflow-all --json` or `--workflow-all --html /new/report.html`. Analysis runs in bounded sequential batches; the default live review remains limited. YAML/TOML and service/timer definitions are inventoried, with unsupported workflow semantics disclosed.

Dynamic paths, nested/inherited methods, shell/YAML execution, SQL and runtime call tracing remain outside the syntax adapter. Accounts, billing and outside-customer expansion are deferred. See [review records, schemas, limits and examples](docs/WORKFLOW_REVIEW.md) and [the roadmap inventory and remaining scope](docs/ROADMAP_REVIEW_20261021.md).

## Quick start

Requires Node.js 20+. Install the single pinned runtime parser dependency, [Acorn](https://github.com/acornjs/acorn), with `npm ci`. Git is required for GitHub URL input and Git-inventory tests. Local mapping falls back to filesystem discovery when Git is unavailable.

v0.1 is currently on [PR #1](https://github.com/DavisAI1974/BuildMap/pull/1); the default branch does not contain the app yet.

```bash
git clone https://github.com/DavisAI1974/BuildMap.git
cd BuildMap
git switch feat/buildmap-v1-living-map
npm ci
npm test
node src/cli.js .
```

Open **http://127.0.0.1:4173**. Each piece previews up to two file paths and shows present/missing counts; select it for the full file list. Click a piece or a gap to inspect its files, purpose, contribution, connections, evidence assessment, and source hashes. Search includes piece ids, names, every assigned path, states, and gap descriptions. Matching pieces appear as clickable results with a count and a no-match message; show all matches when there are more than twelve. Press Enter in search to locate the first match, or Escape to clear it. Selecting a result or gap scrolls to and focuses its card; changed maps retain focus on surviving cards/results, falling back to search if the focused piece disappears. Selected gap boxes, pieces, outcomes, search results, and Fit/Actual size controls use a persistent blue highlight. This indicates navigation selection, not additional proof. Filtered cards leave keyboard navigation; selecting a gap keeps its piece visible while the search remains active. **Fit map** scales the full map into the viewport; **Actual size** restores readable cards and scrolling.

Point it at another project, choose a port, or get a one-shot snapshot:

```bash
node src/cli.js ../some-project
node src/cli.js --port 5000 ../some-project
node src/cli.js ../some-project --json
node src/cli.js ../some-project --html ../buildmap.html
node src/cli.js --help
```

A nonexistent local target becomes an empty project folder. Mapping otherwise reads the project without modifying it. The separate, explicitly requested `--init` operation below writes an initial project description. The HTTP server binds to loopback by default and exposes map metadata, including local paths and recorded evidence; choose a broader `--host` only when you intend that information to be accessible.

Public GitHub repository URLs are also supported:

```bash
node src/cli.js https://github.com/owner/repository
node src/cli.js https://github.com/owner/repository --ref feature/map
```

This makes a shallow clone of the **default branch**, or the branch/tag named by `--ref`, into a temporary folder. `--ref` accepts branch/tag names, including names with slashes; raw commit SHAs and GitHub `/tree/` URL paths are not supported. It applies only to GitHub URL input and never checks out a local working tree. It is a read-only snapshot, not a live view of later GitHub pushes. Restart to fetch a new snapshot. Temporary clones are removed on normal exit, Ctrl+C, or SIGTERM; force-killing the process can leave one behind. Repository URLs with branch paths, queries, or fragments are not supported. For private repositories or commit-level local checkout, clone with your usual credentials, check out the revision locally, and pass its path. GitHub snapshots report their URL, selected ref, and cloned commit in `project.source` and the UI; this metadata does not grant evidence states or deployment proof.

The review exercised public clone/JSON mode against `octocat/Hello-World`, recovered its README intent, and confirmed cleanup. A branch-specific smoke also cloned BuildMap’s PR branch at `705ff1f3a523297e7c96474252bebb3ffc6e0a3f`, mapped its five components, reported the exact revision, and confirmed cleanup. Offline fixture tests cover both branch and tag selection and cleanup after a missing ref. All 106 tests pass on Node v20.20.2 and v24.19.0. A Node 20 dogfood smoke also exercised CLI JSON output, CLI server startup, API/assets, and clean SIGTERM exit. Local HTTP serving and live source edits are covered by tests. Scoped real-browser checks now pass in local headless Chromium 153.0.8010.0 on Node 24.19.0: live map/goal navigation, desktop and 390px layout, search/focus/fit/scroll, clipboard permission and fallback, a 30-piece fixture, source changes and failure/recovery. The self-contained export was rendered in memory through a local HTTP test server and made no asset/API/polling requests. The cloud browser’s loopback and local-file restrictions remain in place; no blocked cloud navigation was retried. Full accessibility review, real devices and other browsers remain untested. See [the browser observation](docs/BROWSER_ACCEPTANCE_20261013.md) for scope and rerun instructions. DOM harness tests remain separate from these browser checks.

## Describe a new project with four questions

```bash
node src/cli.js ../my-project --init
node src/cli.js ../my-project
```

Setup asks for the project name, what it should help someone accomplish, what the finished experience should look/feel like (optional), and what it should do (defaults to your goal). It creates `.buildmap/project.json`, then exits. Existing source and evidence remain intact; an existing project plan is never overwritten. Unfinished or empty-goal answers produce no project description. Setup accepts local folders only, separately from mapping/exports, and rejects a symlinked `.buildmap` directory. No implementation, dependencies, components, walkthrough plan, or proof is invented. Existing source is discovered when you open the map.

The bottom of each map inspector and walkthrough has **What we’re building toward**: the intended finished experience and behavior. This ending is free project context in both views and in focused task briefs. It describes the destination rather than claiming the current build delivers it. Without a declared ending, documented intent supplies the behavior with its original attribution; appearance stays undescribed. Unknown intent stays unknown.

You can author the same description directly in the manifest:

```json
{
  "finishedProduct": {
    "experience": "The owner’s description of what using this project should be like.",
    "behavior": "The owner’s description of what the finished product should accomplish."
  }
}
```

`behavior` must be a nonempty string; `experience` is an optional nonempty string. Invalid descriptions produce a finding and fall back to attributed intent. `/api/map`, `/api/gaps` project summaries, JSON output, live refresh, and snapshots carry `project.finishedProduct`. It never grants evidence states or rewrites a goal’s walkthrough plan.

## Share an interactive snapshot

```bash
node src/cli.js ../some-project --html ../buildmap.html
```

Open the single HTML file in a browser to inspect the captured map, select gaps, search pieces, and fit the map without running a server or fetching external assets. The same client renders both live maps and exports. The header shows **snapshot** and the capture time; exports do not poll, watch source changes, or grant new evidence states.

Exports contain map metadata, file paths, the mapped root, recorded evidence notes, and any recorded walkthrough input/output values, rather than full repository source. The output must be a new file in an existing directory; existing files are never overwritten. Put it outside the mapped project to keep generated HTML from becoming another discovered piece. `--html` and `--json` are separate one-shot modes.

## Start from what exists

Greenfield can begin with a manifest, README, both, or neither. Planned pieces can exist before any code. Missing intent does not block mapping.

Brownfield uses this intent ladder:

1. Explicit mission in `.buildmap/project.json`.
2. First usable prose in README, architecture/design docs, or `SPEC.md`.
3. Discovered implementation and source relationships.
4. Comparison of declared dependencies with observed connections.

Intent is labeled **declared**, **inferred**, or **unknown**. README extraction is a heuristic, not a semantic understanding of the repository. A gap recommends documenting intent or interviewing the owner when it is missing. The optional local `--init` interview collects a description from the owner; it is not an autonomous interview agent or an automatic component/walkthrough designer.

## How files join the map

Supported source files that are not assigned in `.buildmap/project.json` appear as their own pieces. They are not automatically assigned to an existing component. Use guided `--piece` setup to group available files into a new component, or `--extend-piece` to add them to an existing component; direct file authoring also remains available. Local polling reflects that assignment. Declared paths remain visible as missing before creation or after deletion.

Cards preview two paths and show how many more are in the inspector. All mapped files appear in their piece's full file list. This is a supported-source inventory plus explicit declarations, not an automatic list of every repository file. Other assets/configuration can be declared explicitly; see the discovery limits below. File presence does not establish that a piece works.

The live app and HTML snapshots use the same product interface. A snapshot freezes the map data; it does not watch ongoing edits.

## Group files or describe a planned piece

```bash
node src/cli.js ../my-project --piece
node src/cli.js ../my-project
```

Run `--init` first if the project has no description. Piece setup lists ungrouped mapped files, asks for a name, its job and optional contribution, and lets you choose existing files by number. Add exact project-relative paths for other assets or future implementation, one per answer. It shows the complete file list as present or planned/missing and saves only when you type `yes`; other answers cancel. A piece with no files stays planned. No source files or directories are created.

The command appends one new piece, preserving existing project fields, components, walkthroughs and evidence. It avoids ids already used by pieces or orphan component receipts. Duplicate file choices are deduplicated. Grouping does not prove component behavior: an existing file receipt remains a file-only claim, and missing implementation stays visible. New source is not assigned to an existing piece automatically.

Paths must be exact and local: no absolute/traversal/backslash/wildcard paths or linked file/directory paths. Existing component ownership is never changed. Files already used directly by a walkthrough cannot be grouped by this command because grouping changes their piece id; review those references through file authoring before regrouping. Editing an existing piece, moving its files and migrating walkthrough references are outside this append-only flow. Invalid plans, incomplete answers, linked configuration paths, concurrent plan edits and new receipt-id collisions refuse the save. Source/evidence remain untouched; selected manifest-bound receipts can become stale after a plan edit. Mapping remains read-only, separate from these explicitly requested local setup commands.

## Add files to an existing piece

```bash
node src/cli.js ../my-project --extend-piece
node src/cli.js ../my-project
```

Choose a declared piece by number, select available ungrouped files or enter exact additional/planned paths, then review the full file list and type `yes` to save. The command retains its id, metadata, existing file entries, other pieces, goals and completion declaration. Legacy `file`/string lists are retained while the expanded `files` array is written; an inferred id is made explicit so it stays stable. Repeated choices add each new path once. No additions, cancellation or incomplete answers leave the plan unchanged.

This only adds files. It does not remove/move ownership, rename pieces, migrate direct-file walkthrough references, create source or record evidence. The same path/configuration checks apply as for `--piece`; overlapping ownership, invalid plans and changes to the plan or selected piece receipt during the interview refuse the save. New paths are checked again before saving. An existing computing/verified/live claim without source hashes must be reviewed and bound after a real observation before extension; the command leaves that claim untouched.

Adding source scope makes old bound piece/outcome records stale or incomplete, and their completion review becomes pending. File-only claims stay file-only. Repeat the relevant checks before recording new bindings; extension itself grants no proof. Broader piece editing and evidence capture remain file-authored.

## Turn a finding into a focused task

Select a gap, or inspect a piece with findings, to see **What this means** and **One useful next step**. The advice suggests a bounded review: an unseen connection may be a scanner limitation, and an unassigned piece may be useful supporting work. It does not diagnose a root cause, delete code, or change evidence states. The exact finding remains inspectable.

**Copy task brief** prepares one task for a coding agent with the project intent, captured fingerprint, relevant piece/files, finding, suggested review, and limits against unrelated features/dependencies/refactors. When reviewing a goal in the free map or walkthrough, it also includes the selected goal and first unresolved step. Free-map guidance and briefs remain free. Review the brief before handing it to an agent; BuildMap does not send it or execute it. Re-scan the current repository before acting on captured context. If clipboard access is unavailable, the task panel opens with selectable text for manual copying; this works in the shared live/export client. The local Chromium check observed exact copying with clipboard permission granted and selectable-text fallback when permission was unavailable; other browsers remain untested.

## Free map with goals and walkthroughs

**BuildMap Free** includes the complete graph, mission/intent, file inventory, source connections, inspector, evidence states/index, source/evidence gaps, search, fit/actual size, local refresh, read-only APIs, and standalone snapshots. It also includes the current goal walkthroughs: ordered steps, project-specific plain-English explanations, expected results, recorded inputs/outputs and handoff claims, the first unfinished point, and outcome/scope findings. **Keep your agent focused** and the existing basic **Copy task brief** stay free, including selected-goal context.

Map is the default. Choose a goal under **Your goals** to read its walkthrough beside the graph and highlight participating/supporting pieces. The wider **Walkthrough · Free** view offers the same steps in a reading layout. Inspect a step's piece, return to its walkthrough, or clear the map's goal focus while preserving search and scale. Both views use the same source/evidence engine and live/export client.

Outcome findings remain scoped separately so they do not replace the original source/evidence gap list or card warnings. `/api/map` and `/api/gaps` retain their combined findings for compatibility; outcome findings carry `scope: "outcome"` (and `outcomeId` when applicable). Orphan/malformed outcome claims remain inspectable in the free walkthrough. Navigation does not change proof states, evidence counts, or the piece evidence index.

**BuildMap Guide** is the proposed paid tier for deeper actual-code explanations, next-step coaching with acceptance criteria, change-impact previews, post-agent review, guided verification and continuity across sessions. The JavaScript code-reading increment below is implemented for review; user-reviewed task preparation and snapshot change review are also implemented below; explicit device-local task continuity is available; shared accounts and broader automation remain planned. Its intended build loop is understand the current state, prepare one bounded task, build with the user's preferred agent, review actual changes/evidence, and continue. Prices, accounts, billing, and access enforcement are undecided or unbuilt; no paid service has launched. The current map, walkthrough and basic briefs will not be taken away to create that tier.

The updated product direction is recorded in [the competitive strategy handoff](docs/BUILDMAP_COMPETITIVE_STRATEGY_HANDOFF_20261013.md). Its competitor findings are a dated research snapshot, not current independently verified pricing or proof of BuildMap's implementation.

## Read functions with the Guide preview

Select a piece in the free map, then choose **Inspect actual code · Guide preview**. Expand a function to read declared parameters/defaults, return-expression descriptions and object fields, calls/constructions and their argument expressions, source locations and captured hashes. **Read called function** opens and focuses a same-file target only when its bare name is uniquely bound. This helps you follow the source between functions without claiming that the call executes. **Back to piece** restores the full free files/evidence/gaps/basic brief; a goal-linked inspection can also return directly to its free walkthrough.

Function panels and keyboard focus survive unrelated local refreshes when their source identity stays current. Changing that file clears its old expansion and returns focus to the Guide back button; removed pieces and missing files remain explicit. Exported snapshots retain captured explanations without requests and disclose that they do not follow later edits. The Guide button is available for this development preview; accounts, billing and paid access enforcement are not implemented.

This is deterministic source reading using the existing Acorn parse. It describes written syntax, not observed values, types, effects, successful behavior, business meaning or runtime data flow. Calls are listed in source order. Nested callbacks, class/object methods and functions inside blocks are not catalogued; their bodies are excluded from enclosing function counts. Body calls are counted separately from summarized default-parameter expressions. Spread syntax does not reveal the runtime argument count. Complex nested expressions disclose limited expansion. Imported/dynamic targets stay unresolved; there is no cross-file function trace.

Supported files are `.js`, `.mjs` and `.cjs`. TypeScript/JSX and other formats, parse errors, missing/unreadable source and the existing 1 MB discovery limit are labeled per file. A detected source change between inventory and parsing suppresses its explanation until refresh. A file with no supported functions is not claimed to have no behavior. Navigation changes no evidence state, verifies no outcome and grants no mission completion.

`nodes[].codeGuide` carries source-syntax basis, limitations and per-file status/hash/functions in the read-only API, JSON output and shared live/export client. These are syntax descriptions, names and references rather than full repository source or an execution trace. Snapshots include that metadata; review captured context before sharing. See [the Guide integration review](docs/GUIDE_CODE_READING_20261013.md).

## Prepare a reviewed Guide task and compare later changes

From Guide, choose **Prepare detailed task**, or **Prepare task for this function**. Describe one task goal, add acceptance criteria (one per line), state what must stay unchanged, and optionally associate a project goal. The exact file scope starts with the selected piece; select supporting pieces explicitly to allow changes to their files. Dependencies suggest review impact, but never silently expand permission. Function selection focuses the task while keeping that disclosed file scope. Missing exact paths can be planned; declare arbitrary new paths through existing piece authoring first.

**Review this task** captures current source identities, piece/function context, selected goal definitions and possible dependency review scope. Read the concrete brief and choose **Agree to this task**. A changed snapshot or failed refresh blocks agreement until you edit/review current context. **Copy detailed task** provides the agreed text or opens selectable manual text when clipboard copying fails. Source changes block a new automatic handoff from the old baseline. Neither button sends a task or executes code. The complete map, goal walkthrough and existing basic **Copy task brief** remain free.

The **Guide task** button restores the active draft/agreed task after navigating elsewhere. Draft wording, selected support ids and text selection survive refresh. An agreed task retains its original baseline while an agent works. One active task is held in this browser tab. Use Save task on this device to retain it across reloads, or Export task JSON for an explicit portable copy. Starting another task replaces the active task; the saved task changes only when you save again. Tasks are not written into project/evidence files or embedded into snapshots automatically. Shared accounts and task-history services remain unconfigured.

**Review later changes** waits for a successful local map refresh and compares it with the agreed baseline. It lists changed/appeared/missing/newly mapped/no-longer-mapped files inside and outside allowed scope, changed piece definitions/ownership, evidence records or assessments, goals, source/planned relationships, intent/destination and separate completion. It identifies changed function files, current target evidence and a next goal point where available. Possible review impact is based on mapped source/planned dependencies and can include downstream pieces; it is not observed runtime impact.

The comparison covers mapped implementation, declared missing paths and currently assessed selected input hashes. It is not a full-repository inventory, line-level Git diff, change attribution to an agent or semantic correctness review. Acceptance criteria still need your actual checks; no change, matching hash, new receipt or agent claim automatically passes the task or grants proof. The original baseline is retained, and a comparison is labeled out of date after a later edit. Failed fresh reads, captured exports, GitHub snapshots and different checkouts refuse a current working-tree comparison. Captured exports can prepare/copy a clearly captured task without making current-change claims.

These are bounded Guide development features, not a launched paid service. The shared helper remains read-only and uses no new runtime dependency. See [the task and review scope](docs/GUIDE_TASK_REVIEW_20261013.md).

## Walk through an intended outcome

Choose a goal in the free map sidebar, or open **Walkthrough · Free** and select a goal to highlight its participating and supporting pieces. The main walkthrough view shows the goal, ordered steps, expected results, recorded inputs/outputs, handoff notes, and the first missing, failed, or unobserved point. Inspect a step's piece and return to the walkthrough. The same interface works in live mode and exports; local edits update the selected outcome.

To add your first walkthrough without hand-writing JSON, run:

```bash
node src/cli.js ../my-project --walkthrough
node src/cli.js ../my-project
```

Start with `--init` if the project has no description yet, and add source or planned pieces before choosing steps. The interview lists current mapped pieces, asks for one goal, ordered steps, each expected result, optional plain-English explanations, and supporting pieces such as tests. Review the complete plan and type `yes` to save; any other answer cancels. It appends one walkthrough and retains all existing project fields and goals. Unique ids avoid both existing goals and orphan evidence claims. Planned pieces can be selected, and one piece can appear in multiple steps.

No code, source connections, recorded examples, or proof are created. The walkthrough starts unproved; existing evidence files stay untouched, and plan-bound receipts may become stale when the manifest changes. Default mapping remains read-only. This is explicit local authoring, separate from `--init`, remote snapshots, and exports. Unfinished input, invalid plans, linked configuration paths, or a plan changed while answering are refused. Other edits to existing pieces/walkthroughs and evidence capture remain file-based. New pieces can be authored with `--piece`, and existing file scope expanded with `--extend-piece`. A GitHub or HTML snapshot needs a local checkout and a fresh map/export after saving.

You can also define outcomes alongside `components` in `.buildmap/project.json`:

```json
{
  "outcomes": [{
    "id": "confirm-order",
    "name": "Confirm a customer order",
    "goal": "Calculate the total and show the customer a confirmation.",
    "supports": ["order-checks"],
    "steps": [
      { "id": "price", "nodeId": "pricing", "label": "Calculate total", "expected": "Quantity multiplied by unit price." },
      { "id": "confirm", "nodeId": "confirmation", "label": "Show confirmation", "expected": "A confirmation containing the total." }
    ]
  }]
}
```

Each outcome needs a unique nonempty id, a goal, and at least one ordered step. Steps need unique ids, an exact mapped `nodeId`, a label, and a descriptive `expected` result. Optional nonempty `explanation` text states that project's actual goal and step in plain English; optional `example` text can add a project-specific illustration. Each job supplies its own wording. These explanations are distinct from recorded input/output observations and are included in the outcome definition hash. Optional `name` defaults to the id; optional `supports` lists pieces such as tests or infrastructure that support the outcome without pretending they are runtime stages. A piece can serve several outcomes or appear in several steps. Missing targets remain visible.

These are declared goals and behavior plans, not automatically inferred or authenticated owner approvals. Source arrows remain dependency arrows; walkthrough ordering does not add connections or prove runtime flow. Once at least one valid outcome exists, pieces with no assignment produce an informational scope-review finding. This helps spot drift; support work can be useful even before it is assigned, and BuildMap never removes it or declares it unnecessary.

### Record a walkthrough example

After observing the behavior, add its receipt under `outcomes` in `.buildmap/evidence.json`:

```json
{
  "outcomes": {
    "confirm-order": {
      "status": "verified",
      "note": "Observed this example and checked its final confirmation.",
      "definitionHash": "<current definition SHA-256 from the outcome inspector/API>",
      "sourceHashes": {
        "src/pricing.js": "<actual SHA-256>",
        "src/confirmation.js": "<actual SHA-256>",
        "tests/orders.test.js": "<actual SHA-256>"
      },
      "example": {
        "name": "Two items at three each",
        "input": { "quantity": 2, "unitPrice": 3 },
        "output": { "message": "Order total: 6" },
        "steps": [
          { "stepId": "price", "result": "observed", "input": { "quantity": 2, "unitPrice": 3 }, "output": { "total": 6 } },
          { "stepId": "confirm", "result": "observed", "handoff": "Supplied the calculated total to confirmation.", "input": { "total": 6 }, "output": { "message": "Order total: 6" } }
        ]
      }
    }
  }
}
```

The paths above must exactly match the participating/supporting implementation in your map; placeholders are illustrative and reject the claim. Copy the outcome's current `definitionHash` and complete `sourceHashes` only after the observation/check succeeds. Definition hashes bind the goal, step order, targets, expected results, and support assignments. Source hashes bind every participating/supporting implementation file. Optional `inputHashes` binds selected dependencies/fixtures/configuration with the same rules described below.

An outcome stays `unproved` until its own receipt is accepted. Accepted outcome receipts may be `computing` or `verified`; `live` is not supported for outcome receipts. A receipt needs a descriptive note/command/proof and a named example with overall input/output. Each planned step needs one ordered record with `result: "observed"`, input and output; every step after the first also needs a nonempty handoff description. The overall input/output must equal the first step's input and last step's output. Values can be any JSON value, including zero, false, or null. Optional step notes describe context; `result: "failed"` records a failure without proving the outcome. Partial examples remain inspectable and show where observations stop.

BuildMap does not execute target code, compare actual values with natural-language expectations, authenticate observations, or automatically instrument runtime handoffs. Handoff descriptions are explicit recorded claims, not transport proof inferred from imports. The named example covers that example; it does not prove all inputs or general correctness. Complete transitive inputs, environments, and continuing liveness remain outside these receipts. Changes to the plan, participating/supporting source, or selected inputs reject the earlier example; recorded values stay visible with their assessment.

Outcome proof never promotes a piece, proves the mission, or changes the piece evidence index. The API exposes `outcomes`, their source/definition hashes and assessments, each step's state/record, and `firstGap`; nodes expose declared `outcomeIds`. Outcome findings carry `outcomeId` so agents can inspect the goal and the specific unresolved point before expanding work.

BuildMap declares its own "Understand the current build" outcome. A complete current local Node/Chromium example records selected intent/scanner/HTTP/browser input and output fields and all four handoffs. Actual browser reads locate a piece, its purpose/files/evidence, and the free goal’s steps, reported samples, next review point and destination. This is an automated content/visibility check with selected fields, not a full payload capture, instrumented trace, authenticated provenance or human comprehension study. The named example is verified independently of the piece receipts. See [the completion observation](docs/MVP_COMPLETION_20261013.md).

## Show a reviewed completion scope

The final project box can show **MVP verified** for an explicitly declared milestone. Click it to inspect the scope review, current bindings and named checked walkthroughs. Without a declared scope, the box remains an intent target. A pending scope explains the missing, changed or unaccepted review; verified pieces alone do not finish it.

Declare the scope in `.buildmap/project.json`:

```json
{ "completion": { "label": "MVP", "outcomeIds": ["inspect-build"] } }
```

Use your actual outcome ids. Each named goal needs its own current, source-bound **verified** example covering every step and handoff. After actually checking those examples and reviewing this exact scope, record `.buildmap/evidence.json.completion`:

```json
{
  "completion": {
    "status": "verified",
    "note": "Describe the scope you actually checked and its limits.",
    "definitionHash": "<current project.completion.definitionHash>",
    "outcomeEvidenceHashes": { "inspect-build": "<current project.completion.outcomeEvidenceHashes.inspect-build>" }
  }
}
```

The hashes shown in `/api/map` or JSON output are identity bindings, not proof that anything ran. Copy them only after the actual checks and review. The placeholders reject the claim. The declaration needs a nonempty label and a nonempty list of unique exact ids; every id must refer to a valid goal. Completion accepts only a descriptive verified review, the current definition and exact selected outcome records, and independently accepted source-bound verified examples. It never accepts computing/partial/failed examples, status-only or live claims. Changes to scope, selected plans, participating/supporting source, selected inputs or outcome records return the display to pending. Repeat the needed checks and review before recording new bindings.

The badge covers only those declared goals and named examples. It does not assert every future requirement, full accessibility, other environments or live deployment. The API mission state remains an intent target; `project.completion` carries the separate scoped review and does not alter piece states or the evidence-index denominator. BuildMap’s own current MVP review is supported by the complete local example above and the scoped browser baseline. No service is deployed or marked live.

## Evidence states

| State | Meaning in the current snapshot | Basis |
| --- | --- | --- |
| `planned` | Some or all declared implementation is missing, or no files are declared. | Manifest and current file inventory. |
| `coded` | All implementation files exist. | Current file inventory. |
| `connected` | Complete implementation has at least one resolved source reference, including internal references. | Heuristic source discovery. |
| `computing` | Useful work has been observed. | Explicit evidence record. |
| `verified` | A behavior check has been recorded as passing. | Explicit evidence record. |
| `live` | Active use in a deployed/runtime system has been recorded. | Explicit evidence record. |

**Declaring a dependency draws a dashed line; it does not earn `connected`.** A manifest `status` is descriptive only and cannot grant proof. A receipt cannot hide missing implementation. Partial pieces stay `planned`, with present and missing files listed separately.

Each piece exposes `baseStatus` independently of its evidence-driven `status`. A tested standalone piece may be `verified` while its source state remains `coded`. The gap list still flags missing cross-piece connections, even for pieces with upper evidence states.

Within one snapshot, weaker receipts cannot downgrade source-discovered state. Across snapshots, deletion or changed source can invalidate earlier claims. The mission card is an **intent target**, not an inferred verified/live outcome.

### Read the evidence before acting

The free inspector separates **What the files show**, **What someone recorded**, **Does the record still match?**, and **What it does not establish**. It shows the recorded note/proof/command as attributed text, explains unknown or rejected freshness and selected-input coverage, and keeps raw claims, assessments and hashes available under an expandable details section. Recording guidance and state meanings are included. File-only claims cannot prove a whole component.

The free walkthrough distinguishes expected results from reported samples, counts steps marked observed/failed/unaccepted, and explains whether the whole named example is accepted. A partial or failed record remains inspectable; accepted piece checks do not close the whole outcome. Binding and acceptance describe the captured snapshot, not an authenticated check or continuing live use. After source changes, repeat the observation/check before recording new hashes; replacing hashes alone is not new evidence.

### Recording evidence

`.buildmap/evidence.json` accepts component ids and discovered file paths:

```json
{
  "components": {
    "queue-engine": {
      "status": "verified",
      "command": "npm test -- queue-engine",
      "note": "FIFO behavior and edge cases passed."
    }
  },
  "files": {
    "src/worker.js": {
      "status": "computing",
      "note": "Observed processing an input and emitting the expected output."
    }
  }
}
```

Evidence targets use the exact ids and file paths reported by the map. Unknown/deleted targets and malformed collections become visible project findings rather than disappearing. Click a project finding to inspect its raw recorded claim on the mission card.

A file receipt grants a state only to a discovered file piece. If the file belongs to a manifest component, its receipt is retained as an assessed **file-only claim** in that component's inspector; it cannot verify the behavior of the whole component. Use a component-level receipt for that claim. Missing or stale file-only claims remain visible too.

Upper states require a recognized status plus a nonempty `note`, `command`, or `proof`. **These are user-recorded claims. BuildMap does not run commands, authenticate receipts, or prove that a named command passed.** Do not grant `verified` merely because a test file exists, or `live` merely because a deploy script exists.

For freshness, add an optional `sourceHashes` object containing the current SHA-256 of **every implementation file in that piece**. Copy the entire object from `/api/map`, `--json`, or the piece inspector after the observation/check passes:

```json
{
  "status": "verified",
  "command": "npm test -- queue-engine",
  "note": "Check passed against the recorded source.",
  "sourceHashes": {
    "src/queue.js": "<actual 64-character SHA-256 from the map>"
  }
}
```

The placeholder is illustrative and will not match real source. A mismatch, missing hash, extra bound file, or missing implementation rejects the claim for the current snapshot. Unbound receipts remain supported but display **freshness unknown**. Matching hashes establish source identity only; they do not authenticate the observation or establish that a deployment is still running. Dependency/test-input freshness is optional and covers only explicitly selected files.

### Binding dependencies and test inputs

An optional `inputHashes` object extends a receipt to selected dependency, test, fixture, or configuration files:

```json
{
  "status": "verified",
  "note": "Queue check passed with the recorded feed and fixture.",
  "sourceHashes": {
    "src/queue.js": "<actual SHA-256 for the implementation>"
  },
  "inputHashes": {
    "src/feed.js": "<actual SHA-256 for the dependency>",
    "tests/queue.test.js": "<actual SHA-256 for the check>",
    "fixtures/input.json": "<actual SHA-256 for the fixture>"
  }
}
```

The placeholders reject the claim; use actual lowercase 64-character SHA-256 values after the observation/check passes. Input paths must be exact, normalized project-relative file paths inside the mapped root. The object must contain at least one input. Explicit inputs can include ignored or non-source files; they do not add mapped pieces or source connections. Missing/unreadable files, unsafe paths, malformed hashes, or changed bytes reject the receipt and name the affected input. Input changes update the snapshot fingerprint even when the graph and implementation files are unchanged.

The inspector shows recorded/current input hashes and rejection reasons. `/api/map` and `--json` expose `evidenceAssessment.inputs` with `binding` (`current`, `stale`, or `invalid`), `currentHashes`, and `issues`; unavailable files have a null current hash. Supply the selected paths, then record those current hashes only after the check passes. The same assessment appears on file-only claims, which still cannot grant component proof.

`inputHashes` supplements full-piece `sourceHashes`; it does not replace them. A receipt with inputs but no source binding still reports implementation freshness as unknown. Existing receipts without input hashes retain their behavior and disclose that dependency/test-input freshness is untracked. Only the named inputs are covered: BuildMap does not infer a complete dependency/test set, authenticate CI, capture the runtime environment, or establish continuing liveness. Avoid binding the receipt file to itself, since writing that receipt changes its bytes.

### Evidence index

The header's **Evidence index** is a weighted summary of piece states: planned 0, coded 20, connected 45, computing 65, verified 85, live 100, averaged across mapped pieces. It is **not** percentage complete, test coverage, a probability of correctness, or mission proof. The mission card is excluded. Undocumented future requirements are absent from the denominator, so even an index of 100 cannot prove completeness.

## Describing pieces

A minimal `.buildmap/project.json`:

```json
{
  "name": "Order Intelligence",
  "mission": "Understand the current order queue before making a decision.",
  "components": [
    {
      "id": "feed",
      "name": "Market feed",
      "files": ["src/feed.ts"],
      "purpose": "Read incoming exchange events.",
      "contributes": "Gives the system raw events to reconstruct.",
      "visual": { "kind": "flow", "label": "Ingest" }
    },
    {
      "id": "fifo",
      "name": "FIFO queue",
      "files": ["src/fifo.ts"],
      "dependsOn": ["feed"],
      "purpose": "Reconstruct queue position and volume ahead.",
      "contributes": "Shows how much liquidity is in front of an order.",
      "visual": { "kind": "queue", "label": "Reconstruct" }
    }
  ]
}
```

Files are exact project-relative paths, not glob patterns. `file` is accepted for a single path; leading `./` and duplicate paths are normalized. Explicitly declared assets/configuration also count as implementation. A file belongs to one component. Overlapping declarations remain visible in every affected piece, including their full file/hash scope; they produce blocker findings and prevent component receipts from advancing those pieces until ownership is resolved. Connections involving an ambiguous file are excluded from cross-piece wiring, and its file receipt becomes an inspectable project finding. Duplicate/reserved ids also produce diagnostics. `__mission__` and the `file:` prefix are reserved. Component descriptions must be strings, and `dependsOn` must be an array of piece ids. Omitting `dependsOn` leaves dependency intent unspecified. An explicit empty array declares that the piece should have no cross-piece dependencies.

Mini-visuals include `flow`, `scanner`, `graph`, `proof`, `lens`, `goal`, `gate`, and `queue`; unknown kinds use a simple arrow. They are illustrative mechanisms chosen by the manifest or inferred from filenames, not execution traces or behavior extracted from a program. The inspector labels that distinction.

## Connections and gaps

Solid arrows run **dependency → dependent**. For a source import, the inspector shows the importer and imported file. Dashed arrows are declared dependencies; a matching source connection replaces their dashed rendering while both records remain available in the API. Green lines indicate a declared contribution to the mission. None of these lines establishes runtime data flow.

When a manifest piece explicitly supplies `dependsOn`, BuildMap also compares its incoming observed dependencies with that plan. An observed dependency outside the list becomes an **unexpected-dependency** review gap, with importer/imported provenance. Edges expose `planStatus` (`matched`, `undeclared`, or `unspecified`) and the inspector labels connections outside the plan. Omitting the list does not invent a zero-dependency requirement. Drift findings do not rewrite the plan or change proof states.

The prioritized gap list includes:

- missing or partial implementation;
- rejected or stale evidence claims;
- unknown dependency ids, declared dependencies with no observed match, and observed dependencies outside an explicit plan;
- pieces without cross-piece source connections;
- existing pieces with no computation/verification evidence;
- unbound receipts, unmapped targets, file-only claims inside components, malformed configuration, unresolved relative JS/TS references, and scan limitations.

A missing source connection is a **review prompt**, not proof of dead code. Entry points, unsupported HTTP frameworks, dependency injection, generated code, and unsupported languages can be connected at runtime without visible source matches. BuildMap now discovers its own server-to-browser `/api/map` path match, with locations for the literal fetch and Node handler condition. This earns source connectivity only. A separate, scoped local Chromium receipt records passing visualizer checks; the source match itself grants no behavior proof.

### Discovery scope

The scanner inventories common source extensions, HTML/CSS, Dockerfiles, Makefiles, and explicitly declared files.

In a Git worktree, it uses Git's tracked/non-ignored inventory, including nested ignore rules and negation. Tracked source is retained even under normally excluded build/dependency directories. Default dependency/build/cache exclusions apply to untracked files. Mapping a subfolder stays inside that subtree, and deleted tracked files do not establish implementation. Repository fsmonitor hooks are disabled during inventory.

Outside Git, or when Git is unavailable, filesystem discovery skips default dependency/build/cache directories and hidden directories; it does not interpret `.gitignore`. Git failures other than a non-repository or absent executable produce a fallback diagnostic. The API reports `scan.inventoryMode` as `git` or `filesystem`.

Neither mode inspects binaries or follows directory symlinks; Git inventory does not recurse into submodules. Explicit manifest files may override ignores and can include configuration/assets, but cannot establish implementation outside the mapped root. A symlink alias for the project root is supported.

JavaScript syntax discovery uses a parser; relationship resolution and the remaining language adapters are still bounded:

| Source | Relationships discovered |
| --- | --- |
| JavaScript (`.js`, `.mjs`, `.cjs`) | Acorn-parsed local imports/re-exports and literal `require`/dynamic imports, including escaped literals and actual imports in template expressions. Regex/string/comment examples are excluded. Computed paths are skipped. Extension/index resolution and emitted `.js` → TS sources remain supported. |
| TypeScript/JSX (`.ts`, `.tsx`, `.jsx`) | Lexical import/re-export discovery with documented regex/template/alias limitations; no HTTP adapter yet. |
| JavaScript HTTP | Literal root-relative global `fetch` requests matched to one supported Node `http.createServer` handler condition, with endpoint/method and file/line/column provenance. |
| Python | Repository-root modules, packages, sibling/parent relative imports, named submodules. |
| HTML | Local script/link references; leading `/` is interpreted relative to the project root; query strings/fragments are ignored for file lookup. |
| CSS | Quoted `@import` references. |
| Other inventoried languages | Files only; no relationship parser yet. |

JavaScript parser failures skip source references with a visible diagnostic; `.js`/`.mjs` use module syntax and `.cjs` uses CommonJS syntax. Local bindings/reassignments conservatively suppress `require`, `fetch`, and HTTP factory recognition, sometimes across the entire file. TypeScript/JSX regex/template handling, TypeScript aliases, Python `src` layouts and multiline imports, bundler resolution, and HTML server-root conventions remain incomplete. Dependency discovery above 1 MB is skipped with a diagnostic; the file stays in the inventory. Syntax presence does not prove a reference executes. Changes to scanned file contents change the fingerprint even when the graph stays the same.

### HTTP source matches

The HTTP adapter recognizes default/namespace `http` imports, named `createServer` imports, and equivalent top-level native `require` forms. The handler must be an inline callback with request/response identifiers. Supported positive `if` conditions compare `req.url`, or the `pathname` of a directly parsed request URL, with a literal path. The branch must reference a response write/end directly or through a recognized local helper. Literal method constraints in the same condition are checked; broader guards are not inferred.

Only root-relative global fetches with an omitted options object or a literal options object and known method participate. Computed paths/options, wrappers, named callbacks, Express and other frameworks, mount prefixes, HTTPS factories, and dynamic routing remain unsupported. Zero or multiple matching handler conditions produce unresolved/ambiguous findings rather than selecting a provider. Query strings/fragments use URL semantics appropriate to raw URL versus pathname comparisons.

HTTP observations stay on source edges with `kind: "http-source"`, the request `endpoint`/`method`, `importerLocation`, `providerLocation`, and the handler's `providerMethod` (null when unresolved). The inspector labels them **heuristic source path matches**. They participate in declared-plan comparison, but path equality in a repository does not establish a shared deployed origin/port, reachable transport, actual execution, or useful behavior. No HTTP source match grants computing, verified, or live status.

## Agent/API access

No database, bundler, or framework is required. Acorn is the sole runtime dependency; its exact version and install integrity are recorded in `package.json` and `package-lock.json`.

| Interface | Output |
| --- | --- |
| `GET /api/map` | Project, states, nodes, edges with provenance, outcome walkthroughs, gaps, diagnostics, scan scope, hashes, fingerprint, timestamp. |
| `GET /api/gaps` | Project summary, prioritized gaps, diagnostics, fingerprint, timestamp. |
| `GET /api/health` | Server availability and mapped root; not a scan/proof check. |
| `node src/cli.js PATH --json` | Full map snapshot to stdout, then exit. |
| `node src/cli.js PATH --html OUTPUT` | Self-contained interactive HTML snapshot to a new file, then exit. |

Gap records contain `id`, `kind`, `nodeId` (or null), `message`, and `priority` (`blocker`, `warning`, `info`). Drift gaps also carry `dependencyId` and source `observations`; evidence diagnostics can carry the original `evidence` record. GitHub maps expose origin/ref/revision metadata in `project.source`; local maps report local source mode. The `scan` summary separates `importCount` from `httpReferenceCount` and names the JavaScript parser and HTTP adapter. Outcome gaps also carry `outcomeId`. `outcomes` includes declared steps/supports, example records, `hasEvidence`, `status`, `firstGap`, source/definition hashes and assessments; nodes expose their declared `outcomeIds`. Nodes expose `dependencyIntent`, `conflictingFiles`, and, when applicable, assessed `fileEvidence` entries. They are evidence-based prompts for the builder, not instructions to execute. APIs are read-only and do not expose arbitrary repository files as static downloads.

## Architecture and validation

Intent recovery (`src/intent.js`), Git/filesystem inventory, and source discovery (`src/imports.js` and parser adapter `src/javascript.js`) feed the snapshot/evidence/gap model (`src/scan.js`). Outcome assessment (`src/outcomes.js`) adds independent declared walkthroughs and scope findings. The CLI selects a target; the local server exposes snapshots and serves `public/`. The live browser client polls `/api/map` every 1.6 seconds, redraws on fingerprint changes, preserves selection, and displays a stale-snapshot warning when refresh fails. `src/export.js` embeds the captured map and those same assets into one HTML file; snapshot mode performs no requests or polling.

```bash
npm test
```

Tests cover intent fallback, planned/partial implementation, declared versus observed wiring, explicit evidence and source/selected-input freshness, unmapped/file-only claims, explicit-plan drift, parser-backed JS/imports/assets and HTTP path provenance/ambiguity/method/scope checks, Git ignores/tracked files/subtrees, malformed config, path containment, CLI arguments/JSON mode, branch/tag selection and clone provenance, HTML export safety and overwrite refusal, HTTP endpoints/live edits, and live/offline client rendering/selection/filtering/refresh through a DOM double. They do not replace browser layout or deployment verification. See [REVIEW_NOTES.md](REVIEW_NOTES.md) for review findings and [BUILD_GAPS.md](BUILD_GAPS.md) for the current remaining work, with release checks separated from later capabilities.

BuildMap dogfoods its own manifest and source-bound test receipts with selected dependency/test-input hashes. Its visualizer now has a source-bound receipt for scoped local Chromium checks. The separate complete named outcome and explicit MVP review are also recorded; neither the piece checks nor that limited scope establish complete accessibility, every browser or continuing live use. Future work should improve language parsers, runtime/CI receipts, and capability-level navigation before adding decoration.

The current free BuildMap source-build stage is implemented within its documented local CLI/map/walkthrough scope. The local Chromium acceptance baseline has been observed; broader accessibility and device/browser review remain open. [BUILD_GAPS.md](BUILD_GAPS.md) tracks implemented stage requirements, that acceptance boundary, and refinements to revisit after review. The first Guide code-reading increment is integrated for review; task preparation and snapshot change review are implemented; persistent continuity remains planned. No paid launch or deployment is claimed.

## License

MIT
