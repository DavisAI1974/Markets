# Resume the whole-code and complete-workflow review

The user requested the entire current Frankie codebase and its workflow from beginning to end, in sequential pieces if necessary. The whole-code scan is complete. The sequential source/receipt review is still in progress; **do not report the end-to-end workflow as passed**.

## BuildMap work

- Repository: `DavisAI1974/BuildMap`, `/workspace/BuildMap`.
- Branch: `private/workflow-inspector-risk-20261021`.
- Implementation checkpoint: `e6a30c7e0b92005c4d81a46c5e36f772b25a3c2f`, already pushed.
- Latest checks: 143 Node tests and 14 scoped Chromium checks passed.
- `--workflow-all --json` / `--workflow-all --html` removes the 64-file total cutoff. Every eligible Python file is processed in sequential batches of at most 64 files / 4 MB. Live polling stays bounded. YAML/TOML/service/timer files are inventoried with unsupported execution semantics disclosed.
- Keep BuildMap general-purpose. All implementation, tests, documentation and review artifacts belong in the BuildMap repository. No C drive; no BuildMap branch/code in Markets.

## Current source and completed scan

The user identified the private AWS checkout, not a published GitHub branch:

- Repository: `DavisAI1974/Markets`.
- Branch: `codex/search-assembly-20261021`.
- Checkout: `/opt/frankie-box/work/source-session63-assembly`.
- AWS instance: `i-035994afa8bdf66a5`, region `us-east-1`.
- The screenshot's base was `23c0432`; the source subsequently advanced. The complete scan captured **`ad00e5b54814ac12bf6a4f8662182d6b02869834`**, with the same HEAD and clean tracked working tree before/after scanning.
- Never substitute October 6/14 checkouts or the saved run's older deployed release for this current-source review. Current source and deployed/saved execution are separate claims.

BuildMap ran from its own separate Git checkout at `/opt/frankie-box/work/BuildMap`, using Node 20.20.2. No target module or workflow was executed. The scanner inventoried **1,856 files** and parsed **all 1,469 Python files**, with **zero Python files skipped**. There are 387 non-Python inventory files whose workflow execution semantics are outside the Python adapter.

The snapshot contains 18,577 calculation records, 29,363 candidate source-call links and 18,857 static review cues. These are **not confirmed defects or execution traces**. There are 192,236 call sites without supported source links. No optional analysis contracts/runtime observations were supplied in the mapped source.

Private full artifacts remain inside the AWS BuildMap repository:

- `.git/whole-workflow-review/map.json` (316,458,499 bytes).
- `.git/whole-workflow-review/summary.json`.

Local private inspection material, if the workspace persists, is under `/workspace/BuildMap/.git/buildmap-review/current/`: `whole-code-summary.json`, `queue-context.json`, `handoffs.json`, `source-hashes.json`, `capture.json`, and a source sample in `source/`. The source sample is for manual reading, **not the whole-code scan**. Its primary-file hashes matched the full scan. Raw private source is not committed or published in BuildMap.

## Continue in sequential workflow pieces

1. Intake/fetch, sealed ingest, external/day attachment and ROOT admission.
2. ROOT outputs, teacher/hub prerequisites and classroom ownership.
3. Shared data preparation, classroom lessons and independent Search/calculation branches, their joins and exact cache/restart reuse.
4. Batch scientific lessons, accumulated/prior claims, novel Frankie findings and survivor updates.
5. Exchange, Jev and checked knowledge, voice/meeting, school and reports.
6. Late report revisions, successor drain, final owner/day closure, and save/resume/failure boundaries across every handoff.

Trace the actual queue path, not just the `STAGES` tuple. Entry points include `frankie_box_experiment.Run.start`, `frankie_box_frankie_queue._root_job`, `_finish_day`, `_finish_steps`, `class_day` and `_classroom_and_search`. The queue runs classroom lessons beside independent data/Search work on disjoint subsets of the retained booking, joins before scientific lessons, then runs exchange → Jev → voice → school → reports. Search-only days have a different branch. Final reports can require a current revision before successor/day closure.

Current source already contains deferred exact-input decoding, both-direction exact pair/FFT reuse, early sealed-group calculation and shared writer ownership. Inspect and acknowledge these before proposing duplicate optimizations. Some newer indexed consumers/publication paths remain deliberately guarded; determine each producer/consumer contract and supported scope rather than calling every guard a bug.

Small saved step receipts were read without running native commands. They include older source/booking failures and historical completed/reused stages. **An old failed Search receipt is not proof that current Search is failed.** Check fresh native owner/assembly state and source pins before stating liveness or current completion. A later owner-status read returned success but its JSON exceeded SSM's output limit and was truncated; do not treat it as a valid observation. Re-read only the required scalar fields in bounded output.

Use the connected AWS tool's read-only SSM commands if necessary. No workflow launches, stops, resumes, new scientific tests, data/index rebuilds, infrastructure changes or edits to the Markets checkout are part of this review. Keep private detailed findings in the BuildMap Git inspection area; publish only general-purpose BuildMap changes. Do not repeat the completed whole-code scan unless relevant source changes justify it.
