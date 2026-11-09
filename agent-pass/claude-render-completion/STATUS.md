# Lifecycle render handoff — 2026-11-09

Step 1 is complete from the retained inputs, with missing paths explicit. Stop for Greg's preview checkpoint.
Ccode owns the three-day suite run (user steering in this chat); do not duplicate that work.
No market reanalysis or merging was performed.

## Authoritative output
[Verified data directory](https://github.com/DavisAI1974/markets-data/tree/b1123a72115a0fb65cdcde74ba5450e0d40adb68/tasks/family-research-20261022/claude-lifecycle-renders/run-42581055248-1)
Data commit: `b1123a72115a0fb65cdcde74ba5450e0d40adb68`.
[Successful build, checks and daily ZIPs](https://github.com/DavisAI1974/markets-data/actions/runs/42581055248).
Renderer code: `27cfddab590419ebe009d27273271c0445ec6f32`.
Original Claude source: `beb2104c079045c24832f2279eac5e8e69bc576e`.

| Date | Candidate pages | Saved-array rows | Pages explicitly missing array |
| --- | ---: | ---: | ---: |
| 20231002 | 741 | 741 | 0 |
| 20231003 | 833 | 824 | 9 |
| 20231017 | 741 | 740 | 1 |
| 20231018 | 863 | 852 | 11 |
| Total | 3178 | 3157 | 21 |

Nineteen omissions are explicitly `seam_or_warmup` in Claude's coverage table (8 on Oct 3, 11 on Oct 18).
They retain their actual recognition timestamps and companion flow; the absent book/flow arrays are not fabricated.
Two rows are `finalize_only_no_live_recognition` (one each Oct 3/17).
Their original episode and operand records supply agreeing birth clocks, but no live recognition.
Unavailable coverage cutoffs use -1; the display axis convention is separately labelled.

Original array numbering is retained; candidates omitted from that array follow at the end with original candidate-input row coordinates.
Numbering is not another agent's case numbering.
Original array boundaries run from -60 through +1260 seconds. Later measured flip/empty markers remain in metadata and title; capped displays are labelled.
The 99-layer/13-input pinning is a separate pending task on `codex/timestamp-pins-99-13-20261109`; do not mistake these render clocks for completion of that whole pinning task.

## Verification
Eleven focused clock/missingness tests succeeded.
Every candidate ID and input-row identity reconciles; every available recognition clock matches the original integer CSV value.
Every saved variable's finite/missing cell counts reconcile, and every PNG's dimensions/integrity/hash were checked.
For a missing-array page, the reconciliation's missing cell slots describe the requested display positions, not claimed observed source cells.
The source NPZ, candidate JSONL, coverage, flow, weakening and detector ledgers are preserved byte-for-byte with hashes.
The final output supersedes intermediate run 42580756823, whose 19 seam/warmup pages had omitted recognition markers.
No original Claude file was overwritten.

## Preview files
- [Oct 2 first candidate](https://github.com/DavisAI1974/markets-data/tree/b1123a72115a0fb65cdcde74ba5450e0d40adb68/tasks/family-research-20261022/claude-lifecycle-renders/run-42581055248-1/previews/20231002/20231002_0001_dip-19632-1696206036.png)
- [Oct 3 long tail](https://github.com/DavisAI1974/markets-data/tree/b1123a72115a0fb65cdcde74ba5450e0d40adb68/tasks/family-research-20261022/claude-lifecycle-renders/run-42581055248-1/previews/20231003/20231003_0609_dip-19633-1696345466.png)
- [Oct 17 finalization-only record](https://github.com/DavisAI1974/markets-data/tree/b1123a72115a0fb65cdcde74ba5450e0d40adb68/tasks/family-research-20261022/claude-lifecycle-renders/run-42581055248-1/previews/20231017/20231017_0741_dip-19647-1697576378.png)
- [Oct 18 long tail](https://github.com/DavisAI1974/markets-data/tree/b1123a72115a0fb65cdcde74ba5450e0d40adb68/tasks/family-research-20261022/claude-lifecycle-renders/run-42581055248-1/previews/20231018/20231018_0732_dip-19648-1697652514.png)
