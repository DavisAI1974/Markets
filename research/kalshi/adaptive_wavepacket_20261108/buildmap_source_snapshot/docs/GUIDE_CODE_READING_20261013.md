# BuildMap Guide — first code-reading increment

The user authorized starting the paid direction after the free MVP and bounded existing-piece extension were complete. The first Guide increment is now integrated from the preserved `guide/source-code-preview-20261013` draft at `327753325be5b1479ddfb36f76e85c85c88d3467`, on current free base `818a0f7c491a7960483d3e9f181b27674a05f6f7`. Only its source/client/tests were carried over. Conflicts were resolved by retaining the newer evidence-review and completion code alongside Guide; stale draft docs/evidence/manifest were not adopted. The original branch remains preserved.

## What the builder can do

Open a piece’s free inspector and choose **Inspect actual code · Guide preview**. Expand top-level JavaScript functions to read declared inputs/defaults, return-expression descriptions and object fields, body calls/constructions and argument expressions, locations and captured source hashes. Read the declared same-file target from a call when its bare name is uniquely bound. The target panel opens, scrolls into view and receives keyboard focus. Return to the unchanged free inspector/basic brief, or back to a goal walkthrough when inspection started there.

Function expansion/focus survives an unrelated local refresh while its source hash stays current. Changed source discards prior expansion and safely focuses the back button. Detached call controls cannot navigate an earlier fingerprint. Captured exports include the same descriptions without requests and disclose that they do not follow later changes. Missing/unsupported source is explicit. Small function cards, wrapping and visible keyboard focus support inspection at desktop and 390px widths.

The preview uses the existing Acorn parse and adds no runtime dependency. Parsed syntax reaches `nodes[].codeGuide` in the read-only API, JSON output and shared live/export client. The retained source module is `src/code-guide.js`, owned by the existing scanner component; other ownership, ids, goal steps, the explicit free completion declaration and the completed `--extend-piece` implementation remain intact. Only the declared finished-product wording now acknowledges the first Guide capability. The selected manifest binding was refreshed after actual checks.

## Evidence and limits

These are deterministic descriptions of written syntax. They do not execute mapped code, infer business intent, observe inputs/outputs, prove effects or successful behavior, or establish runtime data flow. Source order is not execution order. Declared parameter/default and call-argument expressions are separate from actual values; spread syntax does not reveal runtime argument counts. Return summaries are syntax, not actual outputs. Whole-file unique bare-name binding is a conservative same-file match, not general scope analysis or cross-file tracing. Imported, method and dynamic targets stay unresolved.

The catalog supports top-level `.js`, `.mjs` and `.cjs` functions and identifier-assigned arrows/function expressions. Nested functions, callbacks, class/object methods and block functions are not catalogued; nested function bodies do not contribute to enclosing call/return counts. Body calls are counted separately from default-parameter summaries. Deep expressions disclose limited expansion. Unsupported formats, parse errors, missing/unreadable files and the existing 1 MB discovery boundary are labeled. A detected change between source inventory and parsing suppresses that explanation until refresh.

Guide navigation grants no evidence state, verifies no outcome, and does not complete the mission. The existing explicitly reviewed **free MVP** badge remains its separate named goal/scope; it does not claim the full paid Guide roadmap is complete. Hash identity is not authenticated provenance or live use.

## Verification

**101/101 tests pass on Node 20.20.2 and 24.19.0.** Three scanner regressions from the draft cover real parsed functions/arguments/returns/conservative calls without executing fixture code, unsupported/parse-failed/large/missing scope, and source changes invalidating explanations/receipts. A retained client regression covers escaping, current/captured refresh/back navigation and unchanged proof/free features. One additional client regression covers same-file navigation, preserved focus/expansion after unrelated refresh, changed-source reset and stale-control refusal. Existing free-MVP authoring, API, export, evidence and completion tests remain.

**25 local Chromium cases pass** on Chromium 153.0.8010.0 / Node 24.19.0: the original 19 cases plus six Guide observations for current/captured reading, argument and resolved same-file navigation/focus, unrelated refresh, changed-source/unresolved/390px display, and missing source. No uncaught page errors. This remains scoped browser observation, not exhaustive accessibility, physical-device, other-browser or scale proof.

After those checks, affected source/input receipts were refreshed and the separate complete four-step free-MVP intent → scan → local HTTP → Chromium example and explicit scope review were repeated. The current dogfood scan has five accepted piece receipts, an accepted named free goal and completion review, no detected gaps and zero live states. The browser/completion JSON files record actual checked hashes and runtime scope.

## Later task/review increment

After this 101-test/25-browser-case code-reading checkpoint, the authorized reviewed-task and bounded source-change comparison increments were implemented. See `docs/GUIDE_TASK_REVIEW_20261013.md` for the current 106-test/30-case scope, explicit criteria/file permission, retained in-tab baseline and refusal to infer acceptance from source or agent claims. Persistent continuity, richer diff/impact and assisted actual verification remain later work.

Pricing, accounts, billing and paid access enforcement remain unbuilt. This preview is accessible for development review; no paid service has launched. No target execution, separate coding agent or broad orchestration was added. No HTML preview artifact was generated; retained checks use in-memory exports. Cloud restrictions remain respected. PR #1 stays open; nothing is merged, deployed or marked live.
