# CCode: replace family and recognition substitutes with archived inputs

User requested these directions while Codex continues the four-date combined event studies. No need to wait for the new combined studies; both input exports below already exist.

## 1. Actual first-observed structural family starts

The family four-arm/prebirth/primer replication is complete for October 2, 3 and 17, with original October 18 reproduction. Do not use frozen touch-print candidates as substitutes for family starts.

Pinned markets-data commit: `7b50d634f94ea4777d1e772ac2b916b001019582`.
Root: `tasks/family-research-20261022/family-replication/run-42566535537-1`.

For each date, use:
- `family-20231002/chronological-instance-index.csv` — 796 first-observed families, 510 common four-arm inputs.
- `family-20231003/chronological-instance-index.csv` — 849 families, 535 common inputs.
- `family-20231017/chronological-instance-index.csv` — 824 families, 517 common inputs.
- `family-20231018/chronological-instance-index.csv` — original 749-family reference, 437 common inputs.

[Browse all four immutable folders](https://github.com/DavisAI1974/markets-data/tree/7b50d634f94ea4777d1e772ac2b916b001019582/tasks/family-research-20261022/family-replication/run-42566535537-1).

Each folder contains `flow-book-discovery-v1/` with all eight completed tables, 120 fits, family prebirth/primer tables, analysis receipt and SHA256 manifest. The three new dates also have `strict-pre-root-source-coordinates.json` and `source-receipt.json`: full ROOT archive hashes/bytes/row counts passed, selected clocks/cursors and raw structural IDs reconciled. Fields preserve the original root.* book/activity operands at strictly earlier snapshots.

[Method and population distinctions](FAMILY_REPLICATION.md). These dates use all first observed structural IDs on each retained span; they are not a copied 749-ID whitelist. The full observed October 18 universe has 764 IDs; the old selected 749 are preserved for exact reference reproduction. No equal-count coercion or favorable-case filtering.

[Original runner and date adapter](https://github.com/DavisAI1974/Markets/blob/59195f9339c48cfcbd4a6bf9916a935a4da4fb1d/agent-pass/replication/finish_family_replication.py) show the unchanged original four-arm functions and explicit per-date input bindings. The original October 18 eight tables reproduce. A missing prequote remains missing; it is not replaced with another quote.

All-family occurrences and first-start descriptors are also available in:
`markets-data@54e1b1be98ae6defff25ccfe7e1c3498e8f569f9:tasks/family-research-20261022/family-replication/run-42564821790-1/family-preflight/<YYYYMMDD>/`
Files: `family-starts.json`, `all-family-occurrences.csv.gz`, `population-receipt.json`.

## 2. Actual archived Native recognition inputs

Pinned Markets commit: `1a8ba3478a70c1b01405eb04d37659354e92e807`.

| Date | Archived candidates | Live recognitions | File |
|---|---:|---:|---|
| Oct 2 | 741 | 741 | [candidate-inputs.jsonl.gz](https://github.com/DavisAI1974/Markets/blob/1a8ba3478a70c1b01405eb04d37659354e92e807/tasks/family-research-20261022/replay-comparison/20231002/candidate-inputs.jsonl.gz) |
| Oct 3 | 833 | 832 | [candidate-inputs.jsonl.gz](https://github.com/DavisAI1974/Markets/blob/1a8ba3478a70c1b01405eb04d37659354e92e807/tasks/family-research-20261022/replay-comparison/20231003/candidate-inputs.jsonl.gz) |
| Oct 17 | 741 | 740 | [candidate-inputs.jsonl.gz](https://github.com/DavisAI1974/Markets/blob/1a8ba3478a70c1b01405eb04d37659354e92e807/tasks/family-research-20261022/replay-comparison/20231017/candidate-inputs.jsonl.gz) |
| Oct 18 | 863 | 863 | [october18-candidate-inputs.jsonl.gz](https://github.com/DavisAI1974/Markets/blob/1a8ba3478a70c1b01405eb04d37659354e92e807/tasks/family-research-20261022/october18-candidate-inputs.jsonl.gz) |

The files are verified present at those paths. New-date exports carry `candidate_id`, `birth_second`, `recognition_receive_ns`, `recognition_cursor`, `recognition_group`, original operands and reconstructed window state. Actual live recognition clocks/cursors match original completed groups. Keep `available_second` separate from `recognition_receive_ns`.

Finalization-only exceptions:
- Oct 3: `dip-19633-1696366763`
- Oct 17: `dip-19647-1697576378`

Those have `recognition_group=null`, disposition `finalize_only_no_live_recognition`, and retain original episode/operand payloads. They have no invented live recognition timestamp. Read their birth from the original episode when the common convenience field is absent.

For these files replace t0+50-second assumptions with the actual archived recognition, when a true match exists. CCode's independently generated full-session population (839/857/830/890) differs from archived Native 741/833/741/863. Join using explicit identity/birth/instrument/scope definitions; report matched, ambiguous, unmatched and finalization-only rows. Do not force the independent detector population onto archived candidates or replace an unmatched recognition with t0+50 without labeling that as a separate rule-based scenario.

[Export construction, group checks and coverage](https://github.com/DavisAI1974/Markets/blob/1a8ba3478a70c1b01405eb04d37659354e92e807/tasks/family-research-20261022/replay-comparison/README.md).
[Adapter source](https://github.com/DavisAI1974/Markets/blob/1a8ba3478a70c1b01405eb04d37659354e92e807/tasks/family-research-20261022/research_replay_comparison.py).
Replace the substitute-based result files and their summaries with the corrected actual-input analysis. The corrected version is authoritative; do not retain a known mistake as a competing research result.

## Current division of work

Codex is running three combined timing/instance/event studies on all four dates, preserving individual events and separate event/receive/known-by/recognition clocks. The 99 layers and 13 external points are deferred by user instruction. Keep CCode's own analysis and results separate until the time/source reconciliation. GitHub is the working source/destination; no desktop computation, AWS/S3, live orders or merge.
