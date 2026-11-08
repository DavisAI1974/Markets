# Local browser observation — October 13, 2026

The local browser environment is working. **30 scoped checks pass** in headless Chromium **153.0.8010.0**, driven by Playwright on Node **24.19.0**. The Guide task/review rerun starts from parent `953bf3737425fc89c69f2daca5e744d8865886fd`; the JSON observation identifies the actual changed working source/check hashes. The full suite passes **106/106** on Node 20.20.2 and 24.19.0.

The retained driver is [browser-check.mjs](../.buildmap/browser-check.mjs). The [JSON observation](BROWSER_ACCEPTANCE_20261013.json) records the browser/runtime, revision, actual check results, visualizer source hashes and selected input hashes. This is a manually recorded local check, not independently authenticated CI evidence.

## What was observed

| Area | Passing check scope |
| --- | --- |
| Live map | Direct local HTTP, six dogfood cards including the mission, free views and zero live states. |
| Search and navigation | Search by an assigned file, Enter selection, Escape clear, native Tab excluding filtered cards, selected-card focus and horizontal scrolling. |
| Fit | Desktop graph fits its viewport; actual size restores readable cards and scrolling. A separate 30-piece source fixture fits and locates a distant card. |
| Goals and evidence | Goal steps beside the graph, participant highlights, recorded samples, first gap and destination; wider free walkthrough, inspect a step and return. Fixture gap selection reveals its piece and evidence review. |
| Narrow layout | 390×844 viewport, reachable map/goal controls and no document-width overflow. Screenshots of desktop walkthrough and narrow map were inspected. This is viewport emulation, not a physical mobile device. |
| Copy briefs | Exact task text copied with clipboard read/write permission granted. Without permission, selectable text opens. With clipboard unavailable in a separate context, the complete text is focused and selected. |
| Export | The production `snapshotHtml` output renders in memory over a temporary local HTTP server. Search, goal and fit work; only the document is requested, with no external assets, API calls or polling over the observed interval. No HTML preview file was written. Local-file navigation was not tested. |
| Completion | A disposable fixture’s explicit reviewed scope lights the final box and opens its checked goal. Changing its source returns the display to pending. |
| Changes | Actual fixture source edit produces a new fetched fingerprint while preserving selected-card focus. Deleting declared source updates the card and inspector to planned/missing. |
| Failure and recovery | Intercepted HTTP 500 during polling retains the last map and shows stale feedback, then recovers. An initial API failure reports retry and subsequently loads the map. |
| Guide code reading | Current and captured JavaScript descriptions; same-file function jump and focus; retained expansion/focus after unrelated refresh; changed source clearing its old expansion; unresolved targets, 390px layout and missing declared source. Six new cases, with no target code execution. |
| Guide tasks and review | Captured manual copy and current-comparison refusal; retained draft wording/caret through refresh; reviewed function/explicit support scope, escaping and exact clipboard/free return; actual inside/outside scope edits and 390px layout; failed fresh-read refusal/recovery. Five new cases, without acceptance evaluation or target execution. |
| Browser errors | No uncaught page JavaScript errors on the pages exercised by the driver. Expected API failures are intentional test conditions. |

The driver edits only a disposable project fixture, closes its temporary servers and browser, and removes that fixture. It reads the mapped checkout. Completion remains checked in the disposable fixture. Guide was integrated for the user’s paid-tier request while retaining the original free checks. These cases observe its source-reading/navigation behavior; the wider Guide loop is outside scope.

## What remains open

This baseline does not establish complete accessibility, screen-reader behavior, an exhaustive keyboard-only workflow, touch usability on real devices, Firefox/Safari or other Chromium builds, large-repository performance, every export transport/origin, or continuing deployment liveness. Fit can make a larger map's cards small; actual size and search remain the inspection path. There is no scale benchmark.

The new visualizer receipt covers only these passing checks and their selected bindings. Existing piece receipts remain separate. The independent dogfood example is recorded by a separate explicitly invoked driver, covering all four steps and its declared scope review; see [completion observation](MVP_COMPLETION_20261013.md). This baseline driver does not author project evidence. The mission remains an intent target with a separate scoped completion badge; no piece is live.

## Environment and rerun

The cloud browser cannot reach workspace loopback, and its local-HTML URL policy expressly prohibits workarounds. Those restrictions remain. Its blocked navigation was not retried. The Playwright browser CDN returned a 195-byte HTML “Site Unavailable” page rather than an archive. A standard npm-distributed `@sparticuz/chromium@153.0.0` package installed successfully outside BuildMap's dependencies. Its included binary was unpacked locally; archive ownership changes were omitted because this filesystem rejected `chown`. Playwright launched it with default browser settings and direct localhost HTTP. No external tunnel, hosting, security-policy change or deployment was used.

Browser tooling remains optional and separate from the single Acorn product dependency. In an environment with Playwright Core and a compatible browser already installed:

```bash
BUILDMAP_PLAYWRIGHT_MODULE=/absolute/path/to/playwright-core/index.mjs \
BUILDMAP_BROWSER_EXECUTABLE=/absolute/path/to/chromium \
BUILDMAP_BROWSER_REPORT=/temporary/path/browser-observation.json \
node .buildmap/browser-check.mjs
```

If `playwright-core` resolves normally and its browser is installed, omit the module/executable variables. The optional report variable writes JSON to the chosen path; the driver writes no HTML or screenshot artifacts. A future workspace may need its local browser provisioned again. A successful local check does not repair or authorize the blocked cloud route.

PR #1 remains open. Nothing is merged, deployed, published or marked live. The complete map, current walkthrough and basic task briefs remain free; Guide code reading, reviewed task preparation and bounded change comparison are checked; persistent continuity and billing remain unbuilt.
