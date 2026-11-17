# Existing-piece extension review — October 13, 2026

The bounded `--extend-piece` refinement is complete. Review began from current PR #1 head `e301c3cc0e15ca1eedd5e59f5a822fc8b6d1ad99`, using the preserved draft `831b77e72834b92fdb8ef3da650299a0c1b14a83` on `refinement/extend-piece-wip-20261013`. Only its CLI/setup/server-test changes were integrated; its inherited gap sheet/handoff/evidence were not adopted and the branch was not merged wholesale.

## Result and preservation correction

An explicit local interview selects one declared piece, adds unassigned or planned exact file paths, shows the full scope and saves only after `yes`. It retains original metadata, file spelling/order/duplicates and legacy fields, other pieces, walkthroughs and completion declarations. Previously inferred ids become explicit without changing their mapped identity. The draft initially rebuilt existing file entries from normalized scanner output; review corrected this to append to the original entries. An explicit correspondence guard keeps the selected normalized piece tied to its original manifest position.

No files are removed or moved, goals rewritten, source created, mapped code executed or evidence recorded by this command. New choices are deduplicated. No additions, cancellation or incomplete answers write nothing. Overlapping ownership, unsafe/linked/non-file paths, direct-file goal references, invalid/linked plans, unbound upper-state claims and concurrent plan/selected-receipt edits refuse the save. New paths are rechecked before saving. The existing guarded temporary-file/rename writer is reused; this remains a single-user local interview, without a cross-process locking service.

Old bound piece/outcome records cannot cover added source, and completion becomes pending until the relevant checks and scope review are repeated. Existing file-only claims stay file-only. Source and evidence bytes are retained. Broader description editing, removals, ownership/reference migration and evidence capture remain file-authored.

## Focused verification

Four regressions added to the existing server test file cover:

- Actual CLI additions to the second declared piece, retaining metadata/original file entries/goals/completion/source/evidence while old piece/outcome/completion records become pending and file-only proof stays scoped.
- Legacy `file` and string `files`, inferred ids and empty planned pieces; another declaration is unchanged and missing source is not created.
- Ownership/direct-file support references, malformed/linked paths and plans, incompatible modes, unbound computing/verified/live claims, cancellation/no-op/incomplete input and help.
- Concurrent plan edits, added/changed/deleted selected receipts, unrelated receipt preservation and a new path changed to a symlink before saving.

**96/96 tests pass on Node 20.20.2 and 24.19.0**, including all 17 server checks. JS syntax and whitespace checks pass. No runtime dependency was added. The same retained **19 local Chromium cases pass** on Chromium 153.0.8010.0 / Node 24.19.0; CLI extension is covered by the Node checks, not inferred from the browser baseline. The complete named four-step intent → scan → local HTTP → Chromium example and explicit MVP review were separately repeated against the current implementation after the checks. Relevant receipts were refreshed only from those passing observations; unchanged intent/scanner receipts remain historical current records.

The current dogfood scan has five accepted piece receipts, a current verified goal and explicit MVP review, no detected gaps and zero live states. Full accessibility, other browsers/devices, scale, receipt authentication and continuing liveness remain open. See the current browser/completion observation documents and JSON bindings.

The full map, walkthrough and basic briefs remain free. Guide stays parked. No HTML preview artifact was generated; in-memory product exports were exercised by retained checks. Cloud restrictions were respected. PR #1 remains open; nothing was merged, deployed or marked live. This completes the assigned refinement; no broader feature work is assigned.
