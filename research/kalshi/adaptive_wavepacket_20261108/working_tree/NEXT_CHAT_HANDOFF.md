# BuildMap v0.1 — next-chat handoff

Repository: `DavisAI1974/BuildMap`

PR: https://github.com/DavisAI1974/BuildMap/pull/1

Branch: `feat/buildmap-v1-living-map`

Continuation base for the finished-product/local-setup pass: `e74c023afc5b098469a5a6b110734506662f5e45`; use the current branch head, not the continuation base.

**Fetch the current branch head first and preserve anything newer; do not reset to the historical checkpoint.** This file is updated alongside the latest review corrections and validation.

## Next-chat checkpoint — 2026-10-13

The user authorized proceeding from Guide code reading into deeper task preparation and change-impact/post-agent review. Both are now implemented within a bounded, read-only local snapshot workflow, based on `953bf3737425fc89c69f2daca5e744d8865886fd`. Fetch the current branch head and preserve newer work; do not reset to this parent.

Read `docs/GUIDE_TASK_REVIEW_20261013.md`, then the prior `docs/GUIDE_CODE_READING_20261013.md`. Guide now collects an explicit task goal, acceptance criteria and exclusions, optional current function/goal focus and explicitly selected support pieces. It captures exact allowed files, current source identities, code/goal context and possible source/planned dependency review impact. Review the concrete brief, agree to the matching snapshot and copy manually; changed source or failed refresh blocks old agreement/copy. Basic free briefs remain unchanged. No task is sent, no mapped code is executed and no project/evidence is authored by this flow.

`public/guide-tasks.js` contains pure capture/comparison/brief functions and belongs to the existing visualizer. `src/server.js` serves that fixed public module; `src/export.js.clientSource()` bundles this owned module and the same app for self-contained exports/DOM checks. No runtime dependency was added. The source/goal/completion ownership contracts, extension feature and free evidence review are retained; the new task test file belongs to the existing verification piece.

A single draft/agreed task stays in the active browser tab across map navigation and refresh; wording/support ids/text selection are preserved. The original agreed baseline is never silently rebound after edits. Review later changes waits for the current local read (including an already-running refresh) and lists inside/outside mapped file changes, definitions/ownership, evidence/goal/completion changes, relationship/intent changes, current target evidence and a next goal point. It does not evaluate acceptance criteria, authenticate receipts, attribute changes to an agent or produce a full-repository/line-level Git diff. Snapshots/GitHub clones, failed reads and different checkouts cannot establish a current working-tree comparison. Starting another task replaces this tab's task; reload loses it. Persistent sessions/history/import/export remain unbuilt.

106 tests pass on Node 20.20.2 and 24.19.0; syntax/whitespace checks pass. The retained Chromium baseline passes 30 cases: prior 25 plus five task cases for captured manual copy/refusal, draft text/caret through refresh, reviewed exact scope/copy/free return, actual inside/outside edits/narrow display and failure/recovery. Five focused Node tests cover immutable capture/refusals/impact, actual comparison/retained baseline, source/planned/evidence/namespace limits and agreed client transitions/fallbacks. Relevant receipts and the separate complete named free-MVP four-step observation/scope review were repeated after actual checks. Five piece checks, the named free goal and scope review are current; no dogfood gaps or live states are detected. Free completion does not establish all Guide requirements.

The assigned code → task → bounded change review sequence is implemented. Next refinements should come from actual use: saved/versioned continuity, richer code/diff/impact support and assisted actual verification are remaining Guide directions. Accounts, pricing/billing/access enforcement, automatic execution, a separate coding agent and broad orchestration remain unbuilt. Do not claim a full paid launch or semantic agent review.

After source changes, refresh only genuinely checked receipts, repeat `.buildmap/browser-check.mjs` and explicitly repeat `.buildmap/record-mvp-example.mjs` for the named free example/scope review. Optional browser tooling stays outside Acorn. Permitted executable: `/workspace/scratch/77e2d3a3bcf7/browser-runtime/extracted/chromium`; Playwright Core: `/opt/codex/runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs`. Use the documented environment variables. Respect cloud loopback/local-file restrictions; do not tunnel or deploy.

The full map, current goal walkthrough and basic briefs stay free. No HTML preview artifact was generated; previews are produced only when asked. PR #1 remains open; nothing is merged/deployed/live. No subagents are requested.

## BuildMap stage checkpoint

The user asked to finish the BuildMap stage, then return to refinements, and to update the gap sheet to stay on track. The current free source-build scope is implemented and tracked row by row in `BUILD_GAPS.md`. The final box now shows MVP verified for its explicit reviewed scope, backed by a current complete named four-step local example. See `docs/MVP_COMPLETION_20261013.md`. The core source stage is complete; the bounded extension refinement is complete and the first Guide increment is checked as described above. The local Chromium browser baseline now passes within the recorded scope; cloud-browser restrictions still apply; do not label the product released, deployed, fully browser-verified or live. Begin later refinement only from concrete feedback or an observed issue. This supersedes earlier “next free work” suggestions below.

## Latest user priorities

The free tier's agreed MVP scope is complete; the user has now authorized starting Guide with code reading, then deeper task preparation and change review. Do not create or update HTML preview artifacts unless the user explicitly asks; this does not remove the product's existing export command. Continue source changes and appropriate checks without generating a preview each pass.

The originally parked JavaScript code-reading preview is now reviewed and integrated, preserving the original branch and newer free work. Current validation is 106 tests on Node 20/24 and 30 local Chromium cases; task preparation and bounded snapshot review are now implemented as described above. Its function reading/navigation is a first Guide development increment; deeper coaching and the paid service remain unbuilt.

Guided grouping and planned descriptions use `--piece`; reviewed existing-piece file additions use `--extend-piece`. Other edits and ownership/reference migration remain file-authored. Preserve existing project fields, exact file scope, source/evidence distinctions and current walkthrough authoring. Follow that with a clear review of recorded evidence and the permitted real-browser check. The free tier should let a beginner describe a project, map it, organize its pieces, follow a goal, find an unfinished point and prepare a bounded task; the wider paid roadmap can wait.

## Active request and boundaries

Continue the usable BuildMap MVP with outcome walkthroughs on top of the existing map. The user accepted this direction to help owners understand behavior and reduce agent drift/bloat: connect agreed goals to pieces, expected results, real recorded example values, and the first unfinished/unobserved handoff. This is authorized product work; no further design confirmation is required for the implemented scope. Continue the BuildMap v0.1 review/improvement pass. Use the repository and tests as the source of truth. Make focused, high-leverage improvements, preserve the evidence-state contract, and keep README/evidence honest. The user also asked for the remaining build gaps; the maintained list is `BUILD_GAPS.md`.

PR #1 stays open. The default branch does not contain the app yet. No merge, deployment, npm publication, or live claim was performed. Do not treat the remaining product roadmap as a requirement to build every future feature before v0.1 can be reviewed.

## Read first

1. `NEXT_CHAT_HANDOFF.md`
2. `docs/BUILDMAP_COMPETITIVE_STRATEGY_HANDOFF_20261013.md` (updated strategy; preserve its research caveats)
3. `BUILD_GAPS.md`
4. `README.md` and `docs/MVP_COMPLETION_20261013.md` (explicit completion contract/current full example)
5. `REVIEW_NOTES.md`
6. `docs/GUIDE_TASK_REVIEW_20261013.md`, `docs/GUIDE_CODE_READING_20261013.md` and `.buildmap/project.json` and `.buildmap/evidence.json`
7. Source and tests relevant to the next change.

`GPT6_REVIEW_HANDOFF.md` preserves the original product intent; its historical test counts, progress claims, and initial implementation descriptions have been superseded by the current files.

## Current MVP direction

The user wants a usable MVP and insists work carries into the final build. Improve the existing product source, rather than building a parallel prototype. Cards now preview two file paths, show present/missing counts and additional-file counts, and open the full inspector list. Discovered files remain independent pieces until explicitly grouped in the manifest. Tests exercise actual scan-to-client creation, grouping, deletion, and selection refresh. The live app and standalone exports share the same client. Search now lists clickable matches, searches every assigned file, shows counts/no-match feedback, and supports Enter/Escape. Result/gap selection scrolls to and focuses its card. Poll-driven redraws retain focus on surviving cards/results or return it to search when the target disappears.

A captured MVP was shown in conversation and saved as BuildMap_MVP.html outside the repository. It is a snapshot, not a hosted/deployed/live product. Browser limitations still apply. The wider roadmap is not required before using the core MVP.

## Outcome walkthrough scope

- `.buildmap/project.json` may declare `outcomes`: goal, optional name/supporting piece ids, and ordered steps with unique id, nodeId, label, expected result.
- `src/outcomes.js` assesses plans, current source/definition bindings, partial/failed examples, and scope assignments. `scanProject` exposes `outcomes` and each piece's `outcomeIds`; gaps carry `outcomeId` where relevant.
- `.buildmap/evidence.json.outcomes[id]` accepts computing/verified receipts with descriptive evidence, complete participating/supporting source hashes, the current definition hash, and a named example with overall input/output plus one record per step. Every later step requires an explicit handoff description. Source imports never prove those handoffs. Outcome live receipts are unsupported.
- Individual piece receipts do not prove an outcome, and outcome receipts do not promote pieces or the mission. Outcomes are excluded from the piece evidence index. Plan/source/selected-input changes invalidate earlier examples; raw values remain inspectable.
- Sidebar outcome selection highlights participating/supporting pieces, opens the ordered walkthrough, shows its first unresolved point and input/output samples, and links to piece inspection and back. Live edits and offline exports use this same client. Pieces without outcome assignments produce informational scope-review findings; useful support work is not labeled unnecessary.
- BuildMap declares "Understand the current build." A fresh Node 24/local Chromium example now records selected real input/output fields for all four intent/scan/HTTP/browser steps with explicit handoff checks. Its independent outcome is verified; a separate explicit declared-scope review lets the final box show MVP verified. It is not a full payload, instrumented trace, human comprehension study or deployment. No cloud-browser restriction was retried or bypassed.
- New walkthrough plans can be authored with the explicit local `--walkthrough` interview; existing-plan editing and examples remain file-authored. No automatic runtime instrumentation, receipt authentication, interpretation of natural-language expected results, branching paths, or graphical outcome editor was added.

## Latest user feedback incorporated

Selected boxes should clearly light up. Gap choices now keep one pressed/selected state through refresh, with persistent blue background/glow; map cards, outcomes, search results, and Fit/Actual size controls use consistent selection treatment. This does not change evidence states.

The user clarified twice that the earlier customer-order table was an example of plain wording, not a workflow or analogy to apply to every project. Explain each job's own goal and actual steps in simple language. BuildMap's walkthrough now reads "Agree on the goal", "Check what's built", "Make the results available", and "Review what works", with BuildMap-specific explanations. Optional per-step `explanation` and `example` strings support tailored wording; illustrations stay separate from recorded results. The full normalized definition, including these fields, is bound by the definition hash.

## Updated free and paid boundary

The user attached `BuildMap_Competitive_Strategy_Work_Handoff.docx` and instructed Work to use it as the updated product direction while preserving newer repository work. The matching Markdown strategy was already added in commit `2a54023`, above the guided-authoring commit `3363bce`; both are preserved. This supersedes the earlier paid-walkthrough split.

**The complete map, current goal-first walkthrough and basic focused task briefs are free.** Keep file inventory, source/evidence details, search/fit, gaps/drift findings, expected results, recorded examples, first unfinished point, finished-product ending, APIs/exports and Keep your agent focused. Do not retract any existing capability to manufacture a paid tier.

Goals now appear in the default map sidebar. Choosing one reads its walkthrough beside the graph and highlights participating/supporting pieces. Clear goal focus restores the search-filtered graph; inspecting a step and returning to the wider walkthrough still works. Map · Free and Walkthrough · Free are reading views of the same product. The original source/evidence gap list remains intact; outcome/scope findings remain separately inspectable in the free walkthrough. Refresh, selection, examples and briefs share the existing engine/client, without changing evidence states.

**BuildMap Guide** includes code reading, reviewed task preparation with explicit criteria/scope and bounded local snapshot comparison. Deeper semantic/diff review, assisted actual verification and saved continuity remain planned; billing is unbuilt. Its proposed loop is understand, prepare, build with the user's agent, review actual changes/evidence, continue. Pricing is undecided. Do not claim code execution/data flow from source references or agent assertions; no billing, orchestration platform or separate coding agent is authorized by this strategy alone.

Scoped local Chromium checks now pass; see the browser observation below. Cloud-browser restrictions, broader accessibility/device review and the incomplete named dogfood outcome example remain. PR #1 stays open with no deployment/live claim. Historical review entries describing the earlier paid split record prior behavior and are superseded by this section.

## Audience and focused task briefs

The user confirmed beginner-to-intermediate coder/builders as the primary audience: people intimidated by starting a project, without full-stack/architecture experience, or struggling to control agent drift/bloat. Experienced users can still inspect deeper detail. Keep this focus in setup, default language, and next-step guidance. It is positioning, not verified market-size research.

The shared client explains findings in plain English and offers one useful next step plus a reviewable, manually copied task brief. Free-map briefs remain free. Free goal-aware briefs add the selected goal and first unresolved step. Context includes captured fingerprint/source and relevant files/assessment; the brief asks agents to inspect/re-scan, keep the change small, report observed results, and stop before widening scope. It never sends tasks, runs commands, updates evidence, or decides that an unassigned piece should be deleted. Scoped piece findings can be reviewed in the free walkthrough and then inspected in the free map. Clipboard absence/rejection falls back to selectable text; these are DOM-double interaction checks, not real-browser observations. Two focused regressions bring the suite to 74.

## Finished product ending and guided local start

The user requested the ending that the pieces are building toward at the bottom of both explanation views. Map inspectors, walkthroughs, and scoped walkthrough finding explanations now end with "What we’re building toward": what the finished experience should look/feel like and what it should do. Optional manifest `finishedProduct` has required nonempty `behavior` and optional nonempty `experience`; the scanner exposes this as attributed `project.finishedProduct`. Without it, behavior falls back to documented intent and experience stays undescribed. Unknown intent and malformed descriptions remain honest; nothing grants proof or rewrites walkthrough definitions. BuildMap declares its own intended finished experience and behavior. Focused task context includes this destination.

The next scoped usability gap was starting without manual JSON authoring. `node src/cli.js LOCAL_PATH --init` asks four plain-English questions and creates only the initial manifest, then exits. It preserves source/evidence, refuses existing plans and incompatible remote/export/ref modes, and does not invent implementation, components, dependencies, walkthroughs, or receipts. Empty goals/unfinished input write no description; symlinked `.buildmap` folders are rejected. `src/setup.js` is retained product source assigned to the server component. Default mapping remains read-only.

Four focused checks bring the suite to 78: attributed/malformed/unknown destination handling; real scan-to-live/offline ending placement, escaping, refresh and unchanged proof; actual CLI setup/defaults; preservation/refusal/cancellation/incompatible target behavior. Both Node 20 and 24 pass. Backend partial observations are refreshed; the browser step is still unobserved and no piece is live.

CLI installation/startup, existing-piece/walkthrough editing and evidence authoring remain usability gaps. New pieces now have guided local `--piece` setup. New walkthroughs now have a guided local command, described below. Browser onboarding is not built. Do not claim a no-code application builder or add accounts/billing/a broad editor without a scoped use case. The next useful work should come from review feedback or a concrete repository need; the real-browser release check remains blocked by the documented environment restrictions.

## Business idea to revisit

The earlier paid-walkthrough idea has been superseded by Free map/walkthrough/basic briefs plus proposed paid BuildMap Guide. The company-internal-tool use case remains relevant (a real estate agency replacing some SaaS functionality was the example). The fee amounts and business model details remain hypotheses; this is not authorization to add billing, accounts, or a SaaS-builder platform to the MVP.

## What landed

- Source existence, observed connectivity, and explicit proof claims are separate. Declared dependencies never grant connected status; bare manifest statuses and status-only receipts never grant upper states.
- Optional `inputHashes` binds selected dependency/test/data/config files without adding source pieces or edges. Changed/missing/unsafe/malformed inputs reject receipts and update fingerprints; the inspector/API exposes recorded/current inputs and reasons. Existing receipts keep their semantics; inputs cannot replace source binding or descriptive evidence.
- Partial implementation stays visible. Source-bound receipts become stale on implementation changes; unbound claims disclose unknown freshness. The mission is an unproved intent target.
- Acorn-parsed JavaScript imports/re-exports, lexical TypeScript/JSX discovery, Python packages/relative imports, HTML/CSS relationships, explicit assets/configuration, and visible scan limitations.
- Consistent dependency-to-dependent arrows with file provenance; declared-vs-observed wiring is distinct.
- Explicit dependency plans are compared in both directions. Omitted `dependsOn` is unspecified; `[]` declares no cross-piece dependencies. Drift findings do not change proof states.
- Unmapped, malformed, and falsy evidence records are visible. File-only claims in manifest components remain assessed/inspectable without granting component proof. Project findings open the mission inspector.
- Clickable prioritized gaps, inspector, real fit scaling, actual-size restoration, selection preservation/removal, safe display, and stale-refresh feedback.
- Git-aware inventory respects ignores while preserving tracked source, keeps subtree boundaries, disables fsmonitor hooks, and supports root aliases with containment.
- Read-only `/api/map`, `/api/gaps`, `/api/health`; one-shot `--json` and safe self-contained HTML `--html OUTPUT` exports.
- GitHub branch/tag targeting with `--ref`, exact clone revision metadata in `project.source`, explicit snapshot labeling, clone cleanup, and rejection of local ref selection. No evidence state is granted by provenance.
- Overlapping declarations retain every implementation file/hash, reject component proof until ownership is resolved, and keep ambiguous file claims inspectable without choosing a wiring owner.
- Computed JS import paths no longer create literal-prefix connections; HTML/CSS root asset URLs resolve query/fragment suffixes. Filtered cards leave keyboard navigation, gap selection reveals its piece, and the inspector marks ownership conflicts.
- A bounded parser-backed Node HTTP/global fetch adapter matches unique literal paths with endpoint/method/source locations. Ambiguous or unsupported paths stay unresolved. Source matches compare against dependency plans but never grant upper states or prove deployed origin/transport/execution.
- README, review notes, gap report, and dogfood receipts updated. Node 20+ remains supported, with one pinned runtime parser dependency: Acorn. Run `npm ci` after checkout; the lockfile is committed.

## Current validation and proof state

- **106/106 tests passed on Node v20.20.2 (`node --test`) and v24.19.0 (`npm test`).**
- Node 20 copied-dogfood CLI smoke showed that a selected `package.json` edit invalidates all four receipts without changing their implementation; current selected input bindings match.
- Node 20 dogfood CLI JSON/server smoke passed: five mapped components, API/assets, matching CLI/API fingerprints, no live claims, clean SIGTERM exit.
- The view-separation pass adds one retained-feature/navigation check for live and offline use, including scoped orphan claims; total tests are now 72. It preserves the original free map while presenting the paid journey separately.
- The outcome pass adds six focused scanner/receipt/export checks and two DOM-harness interactions; the HTTP test now covers outcome plan edits through map/gaps APIs. An authored fixture example actually executes its two functions and records their I/O; accepted journey proof does not promote pieces.
- Three earlier DOM-harness regressions cover safe searchable paths, result expansion/live edits/offline mode, scaled navigation to distant cards, and focus continuity. They do not establish real scrolling/layout/accessibility behavior.
- JS syntax and whitespace checks passed.
- Local HTTP/API/assets and live source edits covered by tests.
- Public default-clone smoke with `octocat/Hello-World` recovered README intent and cleaned up.
- Real branch/JSON smoke cloned BuildMap's PR branch at `705ff1f3a523297e7c96474252bebb3ffc6e0a3f`, mapped its five components, reported that exact revision, and cleaned up.
- Offline fixture checks cover branch and tag selection, failed-ref cleanup, HTML export safety/overwrite refusal, and client live/offline logic through a DOM double.
- Dogfood map: **five verified components from scoped, current source-bound recorded receipts with selected inputs, no live states, no missing implementation, no unexpected plan dependencies, no unmapped evidence, one HTTP source reference, an independently accepted full named outcome, an accepted explicit MVP scope review, and no current detected gaps**. The visualizer receipt covers the 30-case local Chromium baseline; the named four-step outcome and completion review are separate.

Do not call DOM-double tests browser verification. Receipts are manually recorded claims; source hashes bind each piece's implementation and optional input hashes bind only explicitly selected dependency/test/data/config files. Complete transitive input coverage, environment identity, and continuing deployment liveness are not established.

## Remaining gaps in priority order

### Release-confidence checks

1. The scoped local Chromium baseline now passes for live server/export, narrow and larger fixtures, selection/search/fit/basic keyboard, edits and failure/recovery. Remaining review covers full accessibility/keyboard usability, real devices/other browsers. The complete named dogfood example and separate scoped review are now recorded. Record only what is actually observed.

Completed release check: the full suite and CLI/server smoke passed on Node 20.20.2. No additional runtime check is currently pending.

### Broader product work

2. Wider wiring discovery: HTTP wrappers/frameworks/dynamic routing/origin association, TypeScript/JSX parsers and aliases, Python src layouts, and other languages. Basic JS parsing and literal Node-HTTP/fetch path matching are implemented.
3. Complete/automatic dependency/test-input coverage and independent CI/runtime/deployment receipt provenance. Explicit selected-input freshness is implemented.
4. Large-repo performance and capability/subsystem navigation. Full scans/hashes and all-node rendering are current limitations.
5. Deeper attributed intent recovery, contradiction review/interviews, and source-derived mechanism explanations.

Git arrival animation, continuous remote refresh, all five conceptual zoom levels, and automated deployment/publication are deferred extensions. See `BUILD_GAPS.md` for completion criteria.

## Current browser limitation

The cloud browser returned `ERR_CONNECTION_REFUSED` for the workspace server. Its URL security policy also rejected local HTML-file navigation and expressly prohibited workarounds around that rejection. Those cloud restrictions remain; do not retry or bypass them. The standard Playwright browser CDN returned a 195-byte Site Unavailable HTML page instead of its archive. A standard npm-distributed local Chromium package (`@sparticuz/chromium@153.0.0`) was installed outside the product dependencies, unpacked without changing archive ownership, and launched with default Playwright settings against direct local HTTP. No cloud navigation, external tunnel, hosting or deployment was used. Chromium 153.0.8010.0 passes 30 scoped cases on Node 24.19.0 using `.buildmap/browser-check.mjs`; the export is rendered only in memory over a local test server, with no HTML preview artifact written. See `docs/BROWSER_ACCEPTANCE_20261013.md` and its JSON report. A source-bound scoped visualizer receipt is now recorded; a complete independent four-step dogfood example and explicit MVP scope review are now recorded with the browser-step I/O. Broader accessibility, real-device and other-browser observations remain open.

The complete named dogfood example and scope review are now accepted, with no current detected gaps. This is scoped recorded evidence, not broad mission proof or continuing liveness. Its declared server dependency now has an observed heuristic HTTP source path match with locations; this is not runtime/browser proof.

## Resume commands

If a checkout is already available, inspect its status before switching or fetching. Otherwise clone and select the feature branch:

```bash
git clone https://github.com/DavisAI1974/BuildMap.git
cd BuildMap
git fetch origin feat/buildmap-v1-living-map
git switch feat/buildmap-v1-living-map
git log --oneline -4
git status --short
npm ci
npm test
node src/cli.js . --json
```

Local server:

```bash
node src/cli.js .
```

Remote branch snapshot (uses the current public branch; does not follow later pushes):

```bash
node src/cli.js https://github.com/DavisAI1974/BuildMap --ref feat/buildmap-v1-living-map --json
```

Offline map:

```bash
node src/cli.js . --html ../buildmap.html
```

The output must be a new file; put it outside the mapped repo.

## Publication mechanics in this environment

Shell clones/fetches work, but shell push failed because GitHub username credentials are unavailable. The connected GitHub API successfully published tested trees in focused commits and updated the branch with an expected-head lease and `force:false`. Published tree hashes were compared against the tested local tree. Do not repeatedly try unauthenticated shell push or force-overwrite newer work; use the connector when needed and verify the final PR head.

The current checkout is `/workspace/scratch/77e2d3a3bcf7/BuildMap`; scratch may not persist into the next chat, so Git is authoritative. Equivalent local commits were preserved in `review/local-*` backup branches before aligning to API-created commits. There are no active subagents and no intentional smoke server left running. Temporary JSON/HTML review files are reproducible intermediates, not remaining deliverables.

Refresh receipts only after relevant checks pass. Avoid framework churn and gratuitous tests/validators. Keep commentary brief and continue within the user's authorized scope.


## Guided walkthrough authoring from bb39f5c

The next beginner usability gap was writing walkthrough JSON. `node src/cli.js LOCAL_PATH --walkthrough` now lists existing mapped pieces and asks for a name, goal, ordered piece selections, expected results, optional explanations, and support assignments. The builder reviews the full plan and explicitly types `yes` to append it. Other answers cancel; unfinished input writes nothing. It permits planned pieces and repeated piece use, generates unique ids avoiding existing outcomes and orphan receipt ids, preserves all existing manifest fields/goals, and leaves source/evidence untouched. No implementation, source edges, observed examples, or proof are invented. Plan-bound receipts can become stale when the manifest changes.

This is explicit local authoring in retained `src/setup.js`, separate from `--init`, mapping, exports and remote snapshots. Existing project descriptions are required. Invalid plans, symlinked/hardlinked manifest files, linked configuration directories, edits during the interview and newly colliding receipt ids are refused. Saving uses a temporary file and rename to avoid partial JSON. Normal single-user CLI edits are covered; there is no cross-process locking service or graphical editor.

The shared client explains how to create the first walkthrough, including `--init` when needed. It distinguishes live local refresh from a captured snapshot requiring a local checkout and fresh map/export, retains the finished-product ending, and updates its empty guidance when a plan arrives. Existing free-map features remain available. Browser restrictions were neither retried nor bypassed.

Four focused tests bring the suite to 82 on Node 20.20.2 and 24.19.0: actual CLI append with original fields/goals/source/evidence/piece states retained and orphan-id avoidance; cancellation/defaults/invalid choices/incomplete input/mode/path refusal; concurrent edits and new receipt collisions; and shared-client empty guidance/refresh/offline/free-map retention. The latter uses the DOM double, not browser proof. Receipts are refreshed only after passing checks. The partial backend example is re-observed; its browser step and the whole outcome stay unproved. No piece is live. PR #1 stays open; nothing is deployed or published.

New groups/planned pieces now have guided local `--piece` setup. The next usability gaps are existing-piece editing/reference migration and recorded-example comprehension/capture. The proposed first Guide increment is deeper source-attributed code explanation from a concrete use case, not a claim that it already exists. Scope a concrete next change rather than building a broad editor or billing platform. The outstanding release-confidence check is still a permitted real-browser observation.


## Updated strategy integration from 2a54023

The uploaded strategy is adopted through the updated boundary above, README, gap report, UI labels and declared finished-product description. Current walkthroughs and goal-aware basic briefs remain free. Goals are directly accessible in the map; the wider reading view is retained for longer explanations. No new Guide capability or paid service was built.

83 tests pass on Node 20.20.2 and 24.19.0. One focused scan-to-client regression covers map goal selection beside the graph, escaped wording, participant highlights through search, unchanged proof, basic goal-aware copy fallback, refresh/focus, clear focus with retained scale/search, piece inspection/return and removed goals. Existing live/offline/navigation/export checks now enforce the free labels and features. These remain DOM-double checks, not browser verification. Test receipts and partial backend intent/scan/HTTP observations are refreshed after successful checks; the browser step and the whole outcome remain unproved. No piece is live.


## Free piece authoring from 591452e

`node src/cli.js LOCAL_PATH --piece` now asks for a piece name/job/contribution, existing ungrouped file numbers and additional exact paths, including future implementation. The builder reviews every file as present or planned/missing and types `yes` to append one declaration. Empty file sets stay planned. Existing components, fields, walkthroughs, source and evidence are retained; duplicate choices are deduplicated and ids avoid existing pieces/orphan component receipts. Grouping never promotes file-only claims into component proof. No implementation or dependency plan is invented.

Authoring rejects unsafe/non-file/linked paths and existing ownership. Direct walkthrough file references block regrouping so current goals are not silently broken or rewritten. This flow does not edit existing pieces, move owned files or migrate references. Shared plan loading/save logic is reused by walkthrough and piece authoring, retaining regular-config checks, current-plan comparison, receipt-collision checks and temporary-file rename. Incomplete input/cancellation writes nothing. Default mapping remains read-only. The free inspector and empty-map help explain the local command.

87/87 tests pass on Node 20.20.2 and 24.19.0. Four focused regressions cover reviewed grouping/planned/empty pieces with preserved fields/source/evidence and file-only/orphan claims; ownership/direct-goal/unsafe-path/mode/cancellation refusals; concurrent plan edits/new receipts; and the actual CLI init→piece→file-arrival→walkthrough path rendered through the shared DOM double with unchanged proof. Existing walkthrough and export checks remain. Syntax/whitespace checks pass. Test receipts and partial backend observations are refreshed after checks; the browser step and whole outcome remain unproved, with no live states.

Guide work stays parked on `guide/source-code-preview-20261013`; it has not been merged into this free branch. No user-facing HTML preview was generated. Next free work should clarify how beginners review recorded examples/evidence without mistaking file presence, agent claims or source connections for behavior proof. A real-browser observation still needs a permitted environment; do not retry or bypass the documented restrictions.


## Evidence review and stage checkpoint from 3f7ae7f

The free piece inspector now separates file/source facts, attributed recorded descriptions, binding/coverage checks and what remains unknown. Original raw claims, assessments, selected-input details and current hashes stay inspectable. It includes plain-English state meanings and manual observation-recording guidance; it does not run/authenticate checks or create/change receipts. The walkthrough distinguishes plans from samples, counts observed/failed/unaccepted step records and keeps whole-example acceptance separate from piece checks and mission proof. Explanations refer to the captured snapshot, including offline/stale contexts.

89/89 tests pass on Node 20.20.2 and 24.19.0. Two focused scan-to-client regressions cover accepted/stale/invalid-input/unbound/file-only/missing evidence, attributed text escaping, refresh and offline behavior; and absent/partial/failed/accepted/stale-plan examples with unchanged piece proof. Existing free map, task briefs, CLI builder flow, APIs and export checks remain. Syntax/whitespace checks pass. Test receipts and partial backend intent/scan/HTTP observations are refreshed only after checks; the browser step and whole outcome stay unproved, with no live state.

The user’s gap-sheet request is implemented in `BUILD_GAPS.md`: current stage requirements are marked implemented/checked, the real-browser acceptance row is blocked, and broader refinements/paid Guide are separate later work. Keep this checkpoint stable for review rather than expanding its scope indefinitely. No user-facing HTML preview was generated.

## Local browser acceptance checkpoint — 2026-10-13

The user asked to get the browser working. The retained local Chromium check passes 18 scoped cases; the existing 89-test suite was rerun successfully on Node 24.19.0. No core product source was changed for browser provisioning. The gap sheet and README distinguish this baseline from complete accessibility/device coverage and the still-partial independent outcome example. Five source-bound piece receipts are now accepted, none live. Historical entries above saying browser behavior was unobserved describe earlier checkpoints and are superseded only within the new report’s explicit scope.

During this browser checkpoint the main workspace had paused, uncommitted `--extend-piece` changes in `src/cli.js`, `src/setup.js` and `tests/server.test.js`. They were excluded from the browser checkpoint and are now durably parked on the branch identified above. Browser checks ran in a clean detached worktree from the current pushed free branch. Do not discard the paused work or claim it is published/tested. Resume it only when returning to scoped refinements.

## Explicit completion and full MVP example — 2026-10-13

The user requested both remaining steps for the final BuildMap box: a full current example including browser, and a completion display supported by that checked scope. Both are implemented and observed. Optional manifest `completion` contains a label and exact unique outcome ids. A descriptive verified `evidence.completion` review binds its current normalized scope/selected definitions and exact selected outcome receipt hashes. All selected outcomes must independently have current source-bound verified examples. Piece checks, computing/partial/failed examples, status-only/live claims and changed source/selected inputs/plans/records cannot complete the scope. Pending/invalid reviews remain inspectable. The underlying mission node stays an intent target, excluded from piece counts/index; only its separate declared-scope badge shows MVP verified. Never change it to an inferred whole-project live/done claim.

92 tests pass on Node 20.20.2 and 24.19.0; three new focused regressions cover freshness/rejected claims and real-scan live/offline client rendering, links, escaping and refresh. The retained browser baseline passes 19 cases, including a disposable fixture completion lighting the box and returning to pending after a source edit. `.buildmap/record-mvp-example.mjs` was explicitly invoked after those checks and authors only BuildMap’s selected current four-step example and scope review. Actual readIntent, scanProject, local HTTP and Chromium reads supply the selected fields and handoff assertions. The live final box refresh and its checked-goal link, plus the 390px in-memory export display/link, pass. Full source and selected manifest/driver/package bindings match. The current dogfood scan has five verified piece receipts, a verified named outcome and explicit MVP review, no detected gaps, and no live state. See `docs/MVP_COMPLETION_20261013.md` and its JSON observation. Broader accessibility/device/browser/scale and independent provenance remain unobserved. Receipt/hash matching does not authenticate checks.

No new user-facing HTML preview was generated for this pass; the earlier requested HTML is a captured earlier checkpoint. Generate a new snapshot only when asked. PR #1 stays open; nothing is merged, deployed or marked live. Paid Guide remains parked. The CLI/setup/server-test extension draft was excluded from this clean-worktree completion checkpoint and is now parked separately as described above; it is not part of this PR.
