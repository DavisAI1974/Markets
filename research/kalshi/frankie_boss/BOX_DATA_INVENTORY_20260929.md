# Box data inventory 2026-09-29 (box i-035994afa8bdf66a5): staged code and the Monday root's bedrock tables

Read-only probes over SSM ~12:10-12:40Z; deletions through committed named-only scripts on Greg's go (drop-in
`DROP_IN_20260929_TUEWED_DATAPOINTS.md`). Counts and bytes as the box printed them. The rest of the old-data inventory
(failed / duplicate runs under `work/`, zip-the-keepers) is NOT in this file yet.

## 1. Staged code (DONE, `frankie_box_cleanup_code.sh`, plan run 36566066468, delete run 36566237836)

Rule (Greg): delete every staged checkout, transfer pack and ingest worktree nothing uses (no running process, no current
run's receipt or config, not the newest staged); one complete example of a kind only if none would remain.

| Kind | Removed | Bytes removed | Kept | Bytes kept |
|---|---|---|---|---|
| staged checkout `code/<sha>-<run>-1/` | 58 | 77,227,075,744 | 22 | ~29.35e9 |
| transfer folder `code/transfer-*` | 79 | 45,741 | 1 (newest) | 579 |
| ingest worktree `ingest-code/<sha>/` | 0 | 0 | 2 | 1,495,057,616 |

- Free space 265,180,835,840 -> 342,043,054,080 bytes. Receipt with each removed checkout's staging intent/receipt:
  `/opt/frankie-box/receipts/code-cleanup-20260929T120938Z.json`.
- The transfer packs (`source.pack`) were ALREADY gone (each folder held only its 579-byte intent): the handoff's
  "80 transfer packs ~45 GB not removed" was stale; the cache cleanup had removed them.
- Kept and why: `38182d7c` (orchestrator pairs2 running; newest), `66f50851` (Tue/Wed ingest receipts), `6d07952e`
  (day facts), Monday r1-r10 run configs / principal inputs / calculations pins (`5295f2d1`, `cdeb2026`, `fe71eb56`, ...),
  worktrees `38182d7c` and `c887bf9a` (Wednesday 20211006 ingest running). Current = touched within 24 h or held by a
  process; a second pass with a shorter window can take the r1-r10 checkouts once those runs are retired.

## 2. Monday root bedrock tables (`work/monday-calculations/full-20211004-20260927-r1-48`)

Root total 1,641,003,823,104 bytes: `work/bedrock` 818,565,300,224, `work/derived` 818,495,377,408,
`superseded` 3,837,747,200.

### The retained copy (named, from the root's own `calculations-receipt.json`, status `calculations_retained`)
The receipt's digest render says: `"bedrock_tables": "not rendered: retained in the layer files and the moved-aside digest"`.
Pinned there:
- Layer ledgers `work/bedrock/recovery-9defa3169f7d46679491da2b1bfbbce2/ledgers/`: `exact_member_rows.jsonl`
  537,182,189,410 bytes / 1,535,939 rows; `exact_lifecycle_rows.jsonl` 14,424,155,424 / 13,402,454 rows;
  `legacy_observable_rows.jsonl` 1,323,153,203 / 1,006,873 rows (sha256 in the receipt).
- `work/derive.json` (sha pinned), which names the PUBLISHED layer files
  `work/derived/.projection-v2/published-e6ff40904d5a437ea30a6f365e8f21f7/<layer>.json.gz` (47 files, 146,868,396,032
  bytes; each self-contained, rows inline, no pointer into the projection archives). KEPT.
- The current digest `work/derivation-digest-full.md` (94,961,846 bytes) + `digest-proof.json` (the five legacy tables
  legacy_price, per_second_flow_and_roll20, legacy_book_imbalance, legacy_structure_observables, structure_families by
  sha256), and the moved-aside previous digest `superseded/digest-render-20260928T115002Z/derivation-digest-full.md`
  (3,837,715,264 bytes).
- `work/bedrock/recovery-1b8392a5.../result.json`, checkpoint in `recovery-8c03f629...`.

### What `work/derived` held and the call
| Path under work/derived | Bytes | What it is | Call |
|---|---|---|---|
| `.projection-v2/published-e6ff...` | 146,868,396,032 | the published layer files derive.json pins | KEEP (retained copy) |
| `.projection-v2/published-8248...` | 76,130,742,272 | an earlier partial publish (37 of 47 files); named by nothing | delete |
| `.projection-v2/member` | 145,484,726,272 | projection range archives (built from the ledgers) | delete |
| `.projection-v2/lifecycle` | 1,461,571,584 | same, lifecycle | delete |
| `.digest-21f4036e...` | 149,678,825,472 | a second digest render: its calculation-layers match 109f's (same names and sizes, sample byte-identical); its 5 saved tables are the 5 the current digest pins | delete |
| `.digest-side-work` | 3,743,678,464 | the side builder's 18 saved bedrock tables (bedrock.run ... bedrock.matching_rule.4.4) | delete |
| `.digest-109f.../table-0005..0022` (no 0007) | ~20e9 | unsaved partial bedrock table renders | delete |
| `.digest-109f.../calculation-layers` | 213,162,897,408 | named by `work/clm-sidecar/monday-20260928a/manifest.json` (sources.sqlite) | KEEP (a reader names it) |
| `.digest-109f.../table-0000..0004` | small | the 5 saved legacy tables | KEEP (with 109f) |
| `.rows` | 57,122,316,288 | projection row spools named by the root's legacy-reuse-*.json | KEEP (named) |

Deletion script: `deploy/aws/box/frankie_box_cleanup_bedrock.sh` (refuses unless the receipt's retained copy is present
at its pinned sizes, derive.json and digest-proof by sha256; refuses any target a *.json outside work/derived names, any
open file, a locked calculation root; copies every small JSON inside a target to
`/opt/frankie-box/receipts/bedrock-cleanup-<utc>/`).

### Not yet classified (next pass)
`work/bedrock` holds 14 `recovery-*` generations; only `9defa3169f...` (ledgers, 787 GB), `1b8392a5...` (result) and
`8c03f629...` (checkpoint) are pinned. The other 11 total ~27.5 GB (8.2, 6.2, 5.5, 2.5 GB and seven of 0.73 GB). Plus
`work/bedrock/ledgers` 2.46 GB. Candidates for the failed/duplicate pass with their evidence.
