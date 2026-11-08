# BuildMap v0.1 review and improvement pass

Reviewed PR #1 from `1ee8314a130cc1b8db36399757c84400b286f1a9`, including `GPT6_REVIEW_HANDOFF.md`, the manifest/evidence, source, and tests. The initial pass introduced no framework or npm runtime dependency; the later parser pass below adds Acorn.

Current product direction: the strategy integration below supersedes the earlier paid-walkthrough split. Current walkthroughs and basic briefs are free; BuildMap Guide remains proposed. Historical entries retain the behavior and checks recorded at their checkpoints.

## Findings and changes

| Finding | Result |
| --- | --- |
| Planned dependencies granted `connected` without source wiring. | Declared and observed edges are separate; declarations no longer promote state. |
| Manifest status, status-only receipts, and receipts for missing code could hide unsupported claims. | Upper states require a descriptive evidence record and complete implementation. Rejected claims remain inspectable and become gaps. |
| Evidence had no freshness model; ordinary source edits could leave the fingerprint unchanged. | Optional full-piece SHA-256 binding rejects stale receipts. Content hashes refresh the snapshot even without graph changes. Unbound claims disclose unknown freshness. |
| HTML/CSS were excluded, making the dogfood visualizer appear missing beneath its computing claim. | Assets and explicit declared files count as implementation. HTML/CSS relationships are discovered within documented limits. The unsupported visualizer computing claim was removed. |
| Python relative imports were handled as JS paths; JS comments/string examples could create false edges. | Separate heuristic source discovery handles Python packages/relative imports, JS lexical exclusions/re-exports, and TypeScript emitted `.js` names. |
| Code and planned arrows used opposite directions and “feeds” language implied runtime flow. | All dependency arrows run dependency → dependent; observed edges retain importer/imported provenance. Runtime flow is not claimed. |
| Missing wiring and unsupported assumptions were buried in the graph. | Prioritized clickable gaps, piece warnings, declared/observed inspector sections, and `/api/gaps` expose them directly. |
| An arbitrary percentage was labeled “System proof,” and the mission inherited upper states. | It is now an explicitly documented evidence index; the mission remains an unproved intent target. |
| CLI flags before a path could turn a port into the target directory. | Strict option parsing, one-shot `--json`, temporary-clone cleanup, and runtime API tests. |
| Fit merely scrolled; refresh errors and removed selections were easy to miss. | Fit scales; actual-size restores; selection persists or clears; refresh errors display a stale-snapshot warning. |
| README described capabilities beyond the verified build. | Rewritten around current behavior, explicit limitations, trust/freshness semantics, and the still-unmerged quick start. |

## Validation

- Baseline: 7 tests passed; local HTTP map, health, HTML, and JS smoke passed before changes.
- First-pass suite: 25 tests, covering model semantics, discovery, CLI/API, live edits, and real client logic against a DOM double.
- JS syntax checks and `git diff --check` passed; package dry-run inspected.
- Public URL clone/JSON smoke succeeded with `octocat/Hello-World`, recovered `README` intent, and removed its temporary clone on exit. BuildMap's default branch was also cloned; it currently contains no app code.
- Dogfood manifest includes the new import-discovery module and all test files. Test receipts are bound to the corresponding final source hashes. No piece is marked live.

**Browser layout/integration remains unverified.** The installed Playwright package has no local browser executable, and the available cloud browser returned `ERR_CONNECTION_REFUSED` for the workspace's loopback server. The DOM harness checks rendering logic, escaping, provenance, selection, filtering, scaling intent, and refresh behavior; it cannot establish visual layout or actual browser/server integration. The visualizer therefore stays at its source-discovered state.

## Remaining product work

1. Exercise the UI in a browser against a real project, including narrow screens and a larger map. Only then record a source-bound visualizer observation.
2. Add parser-backed language resolution before treating missing source wiring as stronger than a review prompt. HTTP relationships, TypeScript aliases, Python `src` layouts, and other languages remain outside current support.
3. Add authenticated CI/runtime/deployment receipts. Current evidence is manually recorded; source identity is not proof authenticity or deployment liveness.
4. Add capability/subsystem navigation when real repository size justifies it. The current bounded dependency layering tolerates cycles but is not a full graph-layout engine.

The next useful dogfood gap remains the server-to-visualizer HTTP connection. It is intentionally shown as declared but unobserved rather than “fixed” by treating the declaration as code evidence.

## Continuation from c14340b

The next pass adds two practical capabilities while preserving the same state contract:

- **Portable HTML snapshots:** `--html OUTPUT` embeds the current map and real UI assets into one interactive file. It labels the capture time, makes no HTTP requests or polling calls, preserves all evidence states, safely encodes project descriptions, and refuses to overwrite an existing file. Exported metadata includes local paths and evidence notes, not full source.
- **Git-aware brownfield inventory:** Git ignore rules and negation apply to untracked files; tracked source remains visible even in normally excluded directories. Mapping a subtree excludes siblings and deleted tracked files. Explicit manifest files can override ignores. Git fsmonitor hooks are disabled, filesystem fallback is reported, and project-root symlink aliases retain containment.

Current validation: **32 tests pass on Node v24.19.0**. The new checks cover HTML safety/round-trip data, CLI export and overwrite refusal, request-free offline rendering, Git ignore behavior, tracked source, subtree boundaries, fsmonitor-hook avoidance, and root aliases. Syntax and whitespace checks pass. Dogfood receipts were refreshed only after the checks completed.

An attempted browser review of the exported file was rejected by the browser URL security policy, which permits only HTTP(S), while the cloud browser still cannot reach the workspace's loopback server. No alternate route around that rejection was attempted. Browser layout and actual browser/server integration therefore remain unverified, and the visualizer retains no upper evidence claim.

## Continuation from 3825faa

The map now detects both directions of declared-versus-observed architecture drift. A manifest piece with explicit `dependsOn` reports incoming source dependencies outside its plan, with file provenance; an omitted dependency list stays unspecified. An explicit empty list is a meaningful no-dependency plan. These findings do not alter proof states or mutate the manifest.

Evidence-target accounting now prevents silent losses. Unknown/deleted targets become project findings with their raw claims. File receipts inside a manifest component are retained and assessed in its inspector but never grant component-level proof. Invalid collection shapes and falsy receipts are visible, and ordinary object-prototype names cannot be mistaken for evidence records. Project findings open the mission inspector; raw records are escaped for display and snapshot export.

Current validation: **40 tests pass on Node v24.19.0**, including drift with preserved proof states, unspecified versus empty intent, unmapped claims, file-only scope, malformed/falsy records, prototype-named ids, and inspector rendering/escaping. Browser layout and integration remain pending under the already documented environment restrictions. No upper visualizer state was added.

## Continuation from 705ff1f

GitHub URL mode now accepts `--ref BRANCH_OR_TAG`. It validates ref syntax before creating a clone, rejects ref selection for local paths, and reports the requested/selected ref and exact cloned commit in `project.source`. The UI explicitly labels GitHub source as a snapshot. Repo names come from the URL when no manifest name exists. No new evidence state follows from clone provenance.

Validation: **44 tests pass on Node v24.19.0**. Branch and tag selection, exact revision identity, missing-ref cleanup, local-path refusal, provenance-only state behavior, and UI metadata are covered. A real public branch/JSON smoke mapped the five-component BuildMap PR branch at `705ff1f3a523297e7c96474252bebb3ffc6e0a3f` and removed its temporary clone. Syntax and whitespace checks pass.

The remaining work is recorded in [BUILD_GAPS.md](BUILD_GAPS.md). Browser verification and a run on the advertised minimum Node 20 runtime remain release-confidence checks. Broader parsers, receipt provenance/freshness, scale/navigation, and deeper intent/mechanism modeling remain product improvements. These categories have separate completion criteria.

## Continuation from a2330cc

The ownership audit found that a later overlapping component silently lost its shared implementation file. A receipt could then verify only the reduced set. Declarations and hashes now retain the full scope on both pieces; an ownership blocker rejects their component claims until the overlap is resolved. Ambiguous files cannot be arbitrarily assigned to cross-piece source edges or a file receipt. File claims remain inspectable as project findings. Unique-file wiring still works, and reversing component order does not choose an owner.

Two discovery corrections remove misleading source states: a computed JS import/require argument no longer resolves its initial string as a complete path, and root-relative HTML/CSS assets resolve with query/fragment suffixes. Discovery remains heuristic and does not claim that references execute.

Filtered cards now leave the tab sequence and accessibility tree. Selecting a gap reveals its piece while retaining the search, and the inspector marks ownership-conflicted files. These behaviors were checked through the existing DOM double; real browser layout/accessibility/integration remains unverified under the documented restrictions.

Validation: **48/48 tests pass on Node v20.20.2 and v24.19.0**. The four new regression tests cover full overlapping proof scope, ambiguous wiring/file receipts and resolution, computed import arguments, asset URL suffixes, and filtered-card navigation/selection. A separate Node 20 dogfood smoke exercised CLI JSON output, CLI server startup, map/gaps/health APIs, all three assets, and clean SIGTERM exit. Source syntax and whitespace checks pass. The minimum-runtime release check is complete for Node 20.20.2; browser checks remain pending. Relevant source-bound receipts were refreshed after the tests; the visualizer still has no upper-state receipt. PR #1 remains open, with no deployment/live claim.


## Continuation from 87692a1

Optional `inputHashes` extends recorded receipts to explicitly selected dependency, test, data, or configuration files. Previously, changes outside a piece's own implementation could leave its receipt accepted. Now changed or unavailable selected inputs reject the receipt, name the affected files, and change the snapshot fingerprint even if those inputs are outside source discovery. Hashing stays inside the mapped root, is cached per scan, and grants no source relationships or implementation state.

The inspector exposes recorded/current input hashes and limited coverage for both component and file-only claims. Malformed bindings cannot grant proof. Existing receipts retain their semantics; input-only bindings still disclose unknown implementation freshness. Source identity, explicit input identity, receipt authenticity, complete dependency coverage, and runtime/deployment liveness remain separate.

Validation: **53/53 tests pass on Node v20.20.2 and v24.19.0**. Five regression tests cover input edits/deletion/restoration, unchanged receipt compatibility, source-binding and descriptive-evidence requirements, malformed/unsafe/outside-root inputs, file-only scope, and escaped inspector output. The existing HTTP test now verifies input-only edits reaching `/api/map` and `/api/gaps`. A Node 20 CLI smoke against a temporary copy of BuildMap showed that one selected configuration edit invalidated all four receipts; the original checkout stayed unchanged. Syntax and whitespace checks pass. Dogfood receipts now bind selected dependencies/checks/configuration after successful tests; the visualizer still has no computing/verified/live claim. Browser restrictions remain in effect, and PR #1 stays open without deployment.


## Continuation from b43600a

JavaScript (`.js`, `.mjs`, `.cjs`) now uses Acorn syntax trees for import/re-export discovery. This excludes regex/comment/string examples, handles escaped literals and actual imports in template expressions, and reports parse failures rather than falling back to misleading source matches. TypeScript/JSX retain their lexical adapter. Acorn is pinned as the sole runtime dependency; `npm ci`, the lockfile, and installation documentation replace the former dependency-free setup.

The bounded HTTP adapter matches literal root-relative global fetch calls to a unique supported inline Node `http.createServer` response-related path condition. It retains endpoint/method and both source locations; mock factories, logging-only branches, negative comparisons, method mismatches, and ambiguous providers cannot grant a match. Dynamic routing, other frameworks, broad method guards, and deployed origin/port association remain outside support. These are explicitly labeled heuristic source path matches, not observations of execution.

BuildMap now finds its own `/api/map` server-to-visualizer match, so the no-observed-connection and unobserved-dependency prompts close within supported discovery. The visualizer's only finding remains behavior-unproved. No computing/verified/live receipt was added to it.

Validation: **58/58 tests pass on Node v20.20.2 and v24.19.0**. Five new regressions cover method/query/path/location provenance and source-only states, missing/ambiguous providers and input-bound freshness, syntax/regex/template/shadowed-call handling, unsupported/mock/logging/negative handler forms, and escaped HTTP inspector metadata. Clean locked installation, syntax/whitespace checks, and package dry-run pass. Refreshed dogfood receipts bind the complete scanner implementation plus selected dependency/check/package-lock inputs. Browser restrictions remain unchanged; PR #1 remains open and nothing is deployed/live.


## MVP file visibility from 14412b4

The shared product client now previews two implementation paths per card, reports present/missing and additional-file counts, and shows the full list in the inspector. Discovered-file inspection explains explicit grouping; an empty planned component is no longer mislabeled as a mission node. Card spacing is adjusted for the inventory preview. The live app and standalone export use the same code, so this is retained product work.

Validation: **60/60 tests pass on Node v20.20.2 and v24.19.0**. New checks cover escaped paths, partial/empty/mission file scope, and real scanner snapshots fed into the client through file creation, explicit grouping, deletion, and selected-inspector refresh. These checks use the DOM double, not real browser layout verification. Receipts were refreshed only for the relevant recorded test checks; the visualizer stays source-connected with no upper-state receipt. PR #1 remains open and nothing is deployed/live.


## MVP navigation from 023ddb3

Search previously dimmed unmatched cards without helping a user reach distant results, and gap selection did not scroll to its card. The shared live/export client now lists clickable search results, reports the total and no-match state, searches every assigned file path, and expands beyond the initial twelve matches on request. Enter locates the first result; Escape clears the search. Result and gap selection use current scaled geometry to reveal and focus the card. Redraws retain keyboard focus on surviving cards/results, return it to search when its target disappears, and leave existing search focus alone. Card/result selection is also exposed through `aria-pressed`.

Validation: **63/63 tests pass on Node v20.20.2 and v24.19.0**. Three focused regressions exercise safe result text, searching a third assigned file, expansion and live result removal, offline operation without requests, distant-card navigation at actual size and fit scale, and focus continuity/fallback. These are DOM-double interaction checks; real browser scrolling, layout, and accessibility remain unverified under the documented restrictions. Syntax and whitespace checks pass. The source/evidence contract is unchanged, the visualizer has no upper-state receipt, and PR #1 stays open without deployment/live claims.


## Outcome walkthroughs from cd8e3a4

The owner-approved product direction connects the build to intended outcomes and shows where demonstrated behavior stops. Optional manifest outcomes declare a goal, ordered steps with expected results, and supporting pieces. A separate outcome receipt carries a named example, per-step input/output and explicit handoff descriptions, complete participating/supporting source hashes, and a hash of the normalized outcome definition. Plan/source/selected-input changes reject previous examples. Partial/failed/invalid records and unmapped targets remain inspectable. Piece verification does not grant outcome proof, and outcome proof does not grant piece or mission proof or alter the evidence index. No outcome live state is supported.

The shared client adds outcome selection, participating-piece highlights, ordered examples, first unresolved-point feedback, piece inspection/return links, and declared scope information. Unassigned pieces become informational review findings, not conclusions that code is unnecessary. This uses existing source, APIs, and export assets. BuildMap declares its own goal; its browser step and whole outcome remain unproved.

Validation: **71/71 tests pass on Node v20.20.2 and v24.19.0**. Six focused tests cover plan/source separation, actual execution and I/O recording in authored fixtures, full source/support/plan/input freshness, partial/failed/missing-handoff/invalid receipts, ownership/missing/orphan scope, and safe export round trips. Two shared-client tests cover escaped samples, outcome-to-piece navigation, highlighting through search, refresh/staleness/removal, and offline operation; the existing HTTP check covers plan edits and outcome gap ids. Syntax/whitespace checks pass. Client checks remain DOM-double observations, not browser layout/accessibility/integration proof. No browser workaround, deployment, or live claim was made; PR #1 stays open.

Current authoring is through manifest/evidence files. Examples and handoff descriptions remain user-recorded claims; there is no automatic instrumentation, semantic comparison with expected-result prose, or receipt authentication. A named example does not prove every input. Those boundaries are explicit in the README.

A read-only Node v24.19.0 dogfood observation recovered intent, scanned the repo, started a temporary local server, and fetched `/api/map`. Its fingerprint and selected fields matched the direct scan. The receipt records selected values for those three steps and leaves browser inspection absent; the walkthrough remains unproved with `inspect` as its first unresolved point. The server was closed. This records a partial example, not a complete trace, runtime instrumentation, or browser proof.


## Selection and plain-English polish from 262f198

Gap boxes now retain a pressed/selected state while their finding remains in the refreshed map. Selecting another gap clears the previous choice; direct piece/outcome selection and clearing outcome context clear gap selection. Persistent blue backgrounds/glows also strengthen map-card, outcome/search-result, and Fit/Actual size selection without changing proof states.

Optional step explanations and project-specific illustrations are typed, preserved in snapshots, escaped in the inspector, and included in definition binding. BuildMap's own labels and explanations describe its actual goal and steps in everyday language. The user clarified that the customer-order story illustrated the writing style; no universal order workflow or analogy is applied to other jobs. Recorded observations remain distinct from explanatory text.

The existing interaction/freshness tests now cover exclusive gap selection across refresh, Fit/Actual size pressed states, escaped tailored explanations, and explanation/example definition changes. **71/71 tests still pass on Node v20.20.2 and v24.19.0**; no new tests or framework were added. Real browser appearance remains pending under the existing restrictions. Backend partial observations are refreshed after these source changes; the browser step and whole outcome remain unproved.


## Free map and paid walkthrough from 8309e13

The user confirmed the original product as free, with the walkthrough as the paid layer on top and nothing removed from the original. Separate view buttons now make that boundary visible. The default Map retains the full original graph, mission/evidence index, source/evidence gaps, search, files/inspector, fit/actual size, refresh and exports/APIs. Walkthrough has its own goal-first heading, sidebar, wider step/record reading view, and scoped outcome/scope findings. Step inspection opens the free map and supports returning to the journey. Map selection/search/scale and walkthrough selection survive view changes. Orphan outcome claims stay inspectable. The views share the engine and client; no subscription/paywall/second scanner or deployment was introduced. Both are accessible as MVP review views.

Validation: **72/72 tests pass on Node v20.20.2 and v24.19.0**. One new shared-client regression checks retained free features, independent finding lists, selection/search/scale continuity, goal/piece return navigation, escaped orphan outcome claims, unchanged underlying evidence data, and offline operation without requests. Existing outcome/client tests were adapted to select the paid view. All original map tests remain. Syntax and whitespace checks pass. These checks use the DOM double; real browser layout/accessibility/server integration still need a permitted observation. Backend samples are refreshed against current source; the browser step and whole outcome remain unproved.


## Plain-English findings and focused tasks from 4ae99a3

Beginner-to-intermediate builders are the confirmed primary audience. The shared client now explains a selected finding, suggests one bounded next review, and provides a reviewable task brief for manual copying to a coding agent. Free-map guidance/briefs remain free; paid walkthrough briefs add the selected goal and first unresolved step. Quoted context includes intent, capture fingerprint/source, the finding, relevant piece files/state/assessment, and goal/step context where applicable. It asks for current inspection, minimal justified work, affected-behavior checks, and a stop before wider scope. It sends no messages, executes nothing, and grants no evidence states. Unassigned pieces remain potential support; unseen source wiring remains subject to scanner limits.

Scoped piece findings now remain reviewable in the paid view before opening their free-map inspector. Selecting another finding rebuilds the task; refresh removes resolved findings and updates surviving context. Detached controls cannot copy a different fingerprint. Clipboard absence/rejection opens read-only selectable text for manual copying, including offline use.

Validation: **74/74 tests pass on Node v20.20.2 and v24.19.0**. Two focused interaction checks cover selected-finding scope, escaped explanations/raw task text, unchanged model/evidence, stale-refresh labeling, copied payloads/manual fallback, refresh/removal, actual scan-to-walkthrough first-step context, and unassigned support review. Client checks still use the DOM double. Actual browser layout, clipboard, accessibility, and server integration remain pending under the documented restriction. Backend partial example observations are refreshed after successful checks; the browser step and whole outcome remain unproved. PR #1 stays open and nothing is deployed/live.


## Finished-product destination and local setup from e74c023

The user requested a plain-English ending that explains what the pieces build toward. Both inspectors now end with the attributed finished experience and behavior. Optional manifest `finishedProduct` is validated and exposed in project metadata/APIs/exports; missing descriptions fall back only to documented intent, and missing appearance/unknown intent stay explicit. Invalid descriptions become findings. This is intended product context, not implementation or evidence proof. Focused task briefs include it.

The next scoped beginner usability improvement is an explicit local `--init` interview that creates an initial project description. It does not overwrite an existing plan, modify source/evidence, generate components/walkthroughs/code, or grant states. It exits after saving; mapping remains read-only. Remote/export/ref combinations, incomplete/empty-goal input, and symlinked configuration directories are rejected. The implementation is `src/setup.js`, assigned to the existing server/CLI component.

Validation: **78/78 tests pass on Node v20.20.2 and v24.19.0**. Four focused checks cover attribution/invalid/unknown fallback, real scan-to-client bottom placement/escaping/refresh in live and offline views with unchanged proof, actual CLI setup/defaults, preserved source/evidence, existing-plan refusal, unfinished input, and incompatible targets. Syntax/whitespace checks pass. Refreshed test receipts bind the changed implementation and selected checks/manifest inputs after successful tests. A fresh read-only backend observation updates the first three sample steps; browser inspection remains absent. DOM-double checks are not browser proof. PR stays open; no deployment or live claim.


## Guided walkthrough authoring from bb39f5c

Builders previously had to author JSON to use the walkthrough layer. An explicit local `--walkthrough` command now adds one goal and ordered steps selected from the current map, with expected results, optional explanations, and supporting pieces. It previews the whole plan and saves only after the builder types `yes`. It retains existing fields/goals and source/evidence, supports planned pieces and repeated steps, and avoids ids used by either existing goals or orphan receipts. It never creates implementation, source connections, observed handoffs, examples, or proof. Existing manifest-bound receipts can stale after a plan edit.

Invalid plans, incomplete answers, incompatible modes, linked manifest/configuration paths, plan edits during the interview and new receipt collisions refuse the save. A temporary-file rename avoids partial JSON during normal local authoring; no cross-process locking service is claimed. Mapping remains read-only. The empty shared-client walkthrough view now explains local setup and distinguishes fresh local polling from captured snapshots; it retains the finished-product ending and updates when plans arrive. Free features remain intact.

Validation: **82/82 tests pass on Node v20.20.2 and v24.19.0**. Four focused regressions exercise actual CLI append and scan results, preservation and orphan-id avoidance; cancellation/unfinished answers/defaults/invalid choices/unsafe paths/modes; concurrent plan/evidence edits; and live/offline empty-state guidance, refresh and retained free-map features through the DOM double. Syntax/whitespace checks pass. Updated receipts cover backend/test checks only; a fresh partial intent/scan/HTTP observation still leaves the browser step and the whole outcome unproved. Browser restrictions were not retried or bypassed; no deployment or live claim was made and PR #1 remains open.


## Strategy integration from 2a54023

The user supplied the competitive strategy DOCX and asked Work to adopt it while preserving newer work. The matching strategy Markdown at `2a54023` and the guided-authoring implementation at `3363bce` are retained. The existing walkthrough and basic agent task briefs now belong to BuildMap Free. The proposed paid BuildMap Guide is documented separately, with deeper code explanation/coaching/impact/review/verification/continuity unbuilt and pricing undecided.

Goals appear in the default map sidebar and can be inspected beside the graph, with participating/supporting highlights. Clearing goal focus preserves search and fit scale. The wider free walkthrough remains available, including scoped findings, samples, basic goal-aware copy briefs and piece-return navigation. Refresh retains current goal detail/focus and handles removed goals. Evidence data/states are unchanged by navigation. Live and exported clients share the same implementation; README, gap report, declared destination and next-chat handoff reflect the new boundary.

Validation: **83/83 tests pass on Node v20.20.2 and v24.19.0**. One focused real-scan-to-client regression exercises goal selection beside the graph, escaping, highlights/search, copied-brief fallback, refresh/focus, clear-focus scale/search retention, piece inspection/return, removed goals, offline operation and unchanged proof. Existing shared-client/free-feature checks are retained; export checks enforce free labels. Syntax and whitespace checks pass. Receipts and partial backend intent/scan/HTTP observations are refreshed only after the checks; browser layout/integration remains unobserved and the whole outcome unproved. PR #1 stays open; nothing is deployed or marked live.


## Free piece authoring from 591452e

The free builder flow previously required JSON to group files or declare planned pieces. Explicit local `--piece` setup now appends a reviewed name/job/contribution and complete exact file list, choosing existing ungrouped files by number and adding future paths. Missing or empty implementation remains planned. Existing components/project fields/goals/source/evidence are preserved, generated ids avoid orphan claims, and file-only receipts remain file-only. Existing ownership and direct walkthrough references block regrouping rather than silently moving files or breaking goals. Unsafe/non-file/linked paths, incomplete input, cancellation, incompatible modes and concurrent plan/receipt changes refuse the save.

Walkthrough and piece authoring share current-plan loading/atomic-save logic. Default mapping remains read-only. The free inspector and empty-map help point builders to the guided command. Existing-piece edits, ownership moves and walkthrough-reference migration remain file-authored. Guide source-reading work stays parked separately; no preview artifact was generated.

Validation: **87/87 tests pass on Node v20.20.2 and v24.19.0**. Four focused regressions cover reviewed append and exact/present/missing/empty file scope; retained fields/source/evidence/goals and file-only/orphan claim semantics; ownership/direct-goal/path/mode/cancellation/incomplete-input refusals; concurrent edits/new receipt collisions; and an actual CLI init→piece→file-arrival→walkthrough flow rendered in the existing DOM double. Syntax and whitespace checks pass. Updated test receipts and partial backend intent/scan/HTTP observations retain the unproved browser step and whole outcome. Browser layout/integration is unobserved; PR #1 remains open with no deployment or live claim.


## Evidence review and BuildMap source-stage checkpoint from 3f7ae7f

Free evidence review now presents file/source facts, attributed recorded descriptions, receipt acceptance/freshness/coverage and limits in plain English. Original raw claims/assessments/hashes remain available in expandable details. State meanings and manual recording guidance explain why command names, files and agent assertions do not independently establish observed behavior. Walkthrough review separates intended results from recorded samples, counts observed/failed/unaccepted step records and keeps whole-example acceptance independent of piece/mission proof. Navigation renders existing data and changes no evidence state.

Validation: **89/89 tests pass on Node v20.20.2 and v24.19.0**. Two focused real-scan-to-client regressions cover current/stale/invalid-input/unbound/file-only/missing evidence, escaping, refresh/offline contexts, and absent/partial/failed/accepted/stale-plan outcome examples with unchanged piece proof. Existing free features and CLI builder flow remain checked. Syntax/whitespace checks pass. Refreshed test receipts and partial backend observations preserve the unproved browser step and whole outcome; no piece is live.

The user asked to finish this stage before refinements and update the gap sheet. `BUILD_GAPS.md` now distinguishes implemented current source scope, the blocked real-browser acceptance check, and later refinements/parked Guide work. This closes the source-build checkpoint within the documented MVP boundary, not release/browser/deployment acceptance. PR #1 stays open and no user-facing HTML preview was generated.

## Local Chromium acceptance — 2026-10-13

The browser environment is working using a separately installed local Chromium executable. The retained `.buildmap/browser-check.mjs` passes 18 scoped cases on Chromium 153.0.8010.0 / Node 24.19.0. Live dogfood navigation, desktop and 390px layout, native search/Tab/focus, fit/scroll, goal/piece return, clipboard permission and fallback, in-memory export isolation, a 30-piece fixture, source edits/deletion and API failure/recovery were observed. No product source, browser security setting, external tunnel, deployment or HTML preview artifact was needed. The full existing suite also passes 89/89 on Node 24; the earlier Node 20 result remains the recorded source checkpoint.

The new visualizer receipt records this precise browser-check scope with full implementation and selected test/dependency input bindings. It does not authenticate the receipt, prove every behavior/browser/device, establish full accessibility, or complete the independent named dogfood outcome. The first three outcome-step samples remain historical partial backend observations, with no browser-step I/O inserted from this separate check. Cloud loopback/local-file restrictions remain in force. See [browser report](docs/BROWSER_ACCEPTANCE_20261013.md) and [gap sheet](BUILD_GAPS.md). PR #1 remains open; nothing is deployed or marked live.

## Explicit MVP completion display and full example — 2026-10-13

The final project box was always an intent target and could not show the requested completed MVP. An optional explicit completion declaration/review now ties its visible badge to named current verified outcome examples. The review binds the scope/selected definitions and exact outcome receipts, while the outcome engine independently checks complete ordered samples, source and selected inputs. Piece verification alone cannot complete it. Invalid, computing/partial/failed, status-only or live claims stay pending. Scope/plan/source/input/record changes invalidate completion; the underlying mission intent state, piece states and evidence-index denominator remain unchanged.

92/92 tests pass on Node 20.20.2 and 24.19.0. Three focused regressions cover scope/record freshness and rejected claims, then scan-to-client escaped live/offline display, links and refresh. The retained local Chromium baseline passes 19 cases, including final-box verified-to-pending behavior in a disposable fixture. A separate actual current four-step intent/scan/HTTP/browser example is recorded with selected real values and explicit handoff checks. Its named outcome and explicit MVP review are accepted. The final box refreshes to MVP verified and opens the checked goal in live and 390px in-memory export views. No current dogfood gaps are detected; this does not establish every future requirement, human comprehension, full accessibility/device/browser coverage, authentication or continuing liveness. No HTML preview artifact was generated in this pass. See [completion observation](docs/MVP_COMPLETION_20261013.md). PR #1 remains open; nothing is deployed or marked live.


## Bounded existing-piece extension — 2026-10-13

Reviewed the preserved `--extend-piece` draft against the current MVP/source/evidence contract and integrated only its CLI/setup/test files. The local interview adds files to one declared piece after review while retaining original ids, metadata/file entries, ownership, goals, source and evidence. A review correction preserves authored file spelling/order/duplicates and legacy fields rather than rebuilding them from normalized scanner output. Inferred mapped ids are pinned; positional correspondence is guarded. Unsafe ownership/reference/path changes, overlapping ownership, unbound upper-state claims and concurrent plan/selected-receipt edits are refused. Other editing/migration/evidence capture stays file-authored.

96/96 tests pass on Node 20.20.2 and 24.19.0. Four focused regressions cover actual CLI extension, legacy/inferred/planned declarations, preserved source/evidence/goals, stale piece/outcome/completion records, file-only scope, refusals/no-op/cancellation/incomplete input and concurrent edits/path changes. Syntax/whitespace checks pass. The 19 retained local Chromium cases and separate complete named MVP example/scope review were repeated; relevant evidence is current, no dogfood gaps are detected and no piece is live. See `docs/EXTEND_PIECE_REVIEW_20261013.md`. No runtime dependency, preview artifact, paid expansion, merge or deployment was added. The assigned refinement is complete.


## First Guide code-reading increment — 2026-10-13

The user authorized starting the paid direction after free-MVP completion. Reviewed and integrated only the parked JavaScript preview’s source/client/tests on `818a0f7`, preserving newer free evidence/completion and the completed file extension. Guide describes actual parsed parameter/default/return/call syntax with argument expressions, exact locations/hashes and explicit unsupported/unresolved limits. Same-file calls can open/focus a conservatively resolved function. Source-bound expansion/focus survives unrelated refreshes; changed source resets it, and detached controls cannot navigate an earlier fingerprint. Back/goal return retain the full free inspector and basic briefs. No runtime dependency or mapped execution was added.

101 tests pass on Node 20.20.2 and 24.19.0. Five Guide regressions cover source reading/scope/freshness and safe current/captured navigation; the 25-case Chromium rerun retains all 19 free checks and adds six Guide cases. Relevant receipts and the separate complete named free-MVP example/scope review were refreshed only after actual checks. No dogfood gaps or live states are detected. See `docs/GUIDE_CODE_READING_20261013.md`. The next paid increment is deeper task preparation; impact/post-agent review, continuity and billing remain unbuilt. No HTML preview, merge or deployment was created.


## Guide reviewed tasks and later-change comparison — 2026-10-13

Guide now captures a user-described goal/criteria/exclusions, current piece/function/goal context and exact explicitly allowed files, then requires review/agreement before automatic copy. Basic free briefs remain. The agreed baseline survives in-tab navigation and source refresh; current local reads compare mapped file/scope/definition/relationship/evidence/goal/completion changes and suggest a next point. Acceptance criteria are not automatically evaluated; this is neither a full Git diff nor agent attribution. Failed reads, snapshots and other checkouts refuse current comparison. No project/evidence is written or source executed. One in-tab task is retained, with persistent continuity unbuilt.

The public pure helper is bundled into the same export/DOM client and served through a fixed read-only asset route. Its direct unit-test import is an explicit new visualizer dependency for the verification piece, acknowledged in the plan. Existing ownership/ids/goals/completion and free features are preserved. 106 tests pass on Node 20/24; 30 local Chromium cases pass, with five focused Node and five browser task checks. Relevant receipts and the independent named free-MVP example/review were repeated. See `docs/GUIDE_TASK_REVIEW_20261013.md`. No preview, merge, deployment, billing or live claim was added.
