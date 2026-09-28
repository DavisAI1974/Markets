# REVIEW 2026-09-28: the parallel bedrock writer and the 460 GB disk fill (code-review-and-quality)

Scope: `deploy/aws/box/frankie_box_digest_parallel.py` as run by the side builder (723e5020, and ce884139 before it),
`frankie_box_bedrock_side.py`, `frankie_box_digest_stream.py` and `frankie_box_digest_render.py` (the codec the passes
call), and the WIP lean writer patch `wip/parallel_lean_plan_WIP_20260928.patch`. Read-only review. There was no box
action and no test run. The box numbers below come from the GitHub run logs of the probes, quoted by run id.

## 1. What the receipts show (box i-035994afa8bdf66a5, 2026-09-28 UTC)

| When | Run | Fact |
|---|---|---|
| 01:09:03 to 01:39:34 | 36368854682 (progress.jsonl, 1st side build, ce884139, 28 threads, 56 parts) | snapshot pass (it wrote a source copy) |
| 01:39:34 to 01:58:02 | same | **plan pass: 18 min 28 s for the whole table** |
| 01:58:02 to about 02:03 | same | count pass, then disk full |
| 02:17 | 36369244657 (disk_usage) | `.digest-side-20260928T010901Z` = 456,201,678,848 B, almost all in `table-0007/part-*/part.sqlite` of 7.2 to 9.9 GB each. Parts 0-27 were last written 02:00-02:01, which means they finished counting. Parts 28 and up were last written at 02:03 (still counting). |
| 03:08 | 36372443877 (cleanup) | removed 465,093,579,941 B; free 465,080,025,088 B |
| 03:19:53 | 36373163230 (2nd side build, 723e5020, 30 threads, 60 parts) | start; snapshot |
| 03:40 | 36374592089 (disk_usage) | **free 461,206,233,088 B**; `.digest-side-work` = 258,048 B (the snapshot writes nothing) |
| 03:48:42 | 36375500281 (progress.jsonl) | plan pass starts (the last progress line anyone read) |
| 04:09:32 | 36373163230 | the side-builder SSM command died ("ipc messaging received timeout signal"); no traceback |
| about 04:13Z | 36377558316 (console log) | `journald: No space left on device`; no OOM lines |

So **about 461 GB was written in at most about 21 minutes (03:48:42 to about 04:09), about 370 MB/s**. The number holds.

**Correction to the handoff: "the plan pass crashed" is not a receipt.** The last progress read was at 03:54. The same
`_plan`, unchanged from ce884139 (same rows, 28 threads), finished the whole table in 18 min 28 s. On 30 threads it
should have finished at about 04:06, and `_count` would then have started. The first run also died about 5 minutes into
`_count`. **Most likely the plan pass was SAVED to passes.pkl and the disk filled in the count pass**, writing
`freq.sqlite` beside the finished `plans.sqlite` files, exactly as the first run did. This matters for the recovery
(section 5).

## 2. Where the bytes go, pass by pass (every pass with the per-row pattern)

W = the width of the table-wide column union (the header columns). R = rows (one per F_LAST group, 1,535,939).
Line numbers are those of 723e5020, the code that ran.

| Pass | What it stores per row | Code |
|---|---|---|
| `_snapshot` | nothing since 1d6018f4. It still computes the full `TS._dump(row)` (pack, dumps, loads, unpack, compare, zlib) of every row as a check, then throws it away. | parallel.py:138 |
| **`_plan`** | **one zlib'd JSON `(kind, text)` pair for EVERY column of the union, on EVERY row: W cells, including `?` absent and `=` derived.** Every string/JSON value is escaped a second time inside the envelope. | parallel.py:157-158 |
| **`_count`** | **`frequency(key TEXT PRIMARY KEY, ...)` in a rowid table: every distinct string or JSON cell of every kept column, UNCOMPRESSED, stored TWICE (the table row plus the `sqlite_autoindex` b-tree).** The cells include `book_full.ask_levels_full`, the whole ask ladder with every FIFO queue, different on almost every row (the crosswalk names the bid ladder `bid_levels_full[]`, reduced to a count, but the ask ladder without `[]`, so it rides whole). It also holds up to 2,000,000 keys in RAM per helper before it flushes. | parallel.py:175-199 |
| merge | `dictionary.sqlite`: every part's keys again, uncompressed, twice again (table plus PK index) plus a UNIQUE index on number. Built on ONE core. | parallel.py:458-485 |
| `_final` | `final.sqlite`: every row again (compressed) | parallel.py:220-250 |
| `_emit` + copy | `rows.txt` per part UNCOMPRESSED, then copied into `table-0007.txt`: **2x the uncompressed table on disk** until the copy is saved | parallel.py:253-263, 502-548 |
| `_verify` | reads each part's whole byte segment into RAM (`handle.read(length)`), plus an inverse dictionary database | parallel.py:274-277 |
| serial `TS.write_table` (ROOT) | the same four stores in one `table.sqlite` (source, plans, final, frequency), on one core | digest_stream.py:68-168 |

### The suspect (the plan's union envelope): real, but I cannot show it is the multiplier from code alone
- Measured with the real codec: an absent `?` cell costs 43 bytes before zlib, and a run of 1,000 costs 409 bytes after
  zlib level 1. A large JSON value costs 1.03-1.04x in `plans.sqlite` what it costs in `sources.sqlite` (tested on the
  repo's audit JSONs). The plan is only many times the source if W is very large, or the non-absent cells do not form runs.
- The crosswalk's 94 member paths all have fixed keys (the 5 activity anchors, action letters, counters), so from code
  I would expect W in the hundreds. The saved snapshot knows W exactly (`len(passes['snapshot'][i]['columns'])`).
- Against that, the first run's per-part files average about 8.1 GB for 27.4k rows, **about 300 KB stored per row**,
  while the uncompressed member spools on the box (`.rows/*-members.jsonl`, 57 GB for all layers) bound the raw member
  content at about 37 KB per row. Something stores about 8x the row content: either a W far larger than the code
  suggests (in the plan), or the uncompressed, doubly-stored keys (in the count).
- **I will not claim the split without the file sizes.** Section 5 gets them at no extra cost.

## 3. Findings (severity labelled)

1. **Critical: nothing checks disk before a pass.** Every pass writes on the order of the table or more, 30 helpers at
   once, with no free-space check. Both side builds filled the 2 TB disk and took SSM down with it. Add a guard before
   each pass: `shutil.disk_usage` against an estimate from the previous pass (for example, refuse `_final` unless free
   exceeds 2x the summed literal text of the plan), and stop cleanly with a receipt instead of filling the disk.
2. **Critical: the count/dictionary key design stores every dictionary candidate uncompressed, twice.** Use
   `WITHOUT ROWID` tables (the key is stored once) and key them by a digest (`sha256(key)`, 32 bytes). Keep a key's text
   only when the merge numbers it (count >= 2); the final pass writes the text of each numbered key once, from the part
   that holds its first occurrence. The inverse proof decodes every `@n` back and round-trips each row against the
   source, so a digest collision cannot pass silently. Same bytes as the serial writer.
3. **Required: the WIP lean patch keeps the #2 pattern.** Its combined plan/count pass still creates
   `frequency(key TEXT PRIMARY KEY)` and adds `held(j, key, ...) PRIMARY KEY (j, key)`, both rowid tables with full
   uncompressed keys, so it removes `plans.sqlite` and `final.sqlite` but not the count's bytes. Apply #2 in the patch
   before it ships.
4. **Required: the copy step doubles the uncompressed table.** Unlink each part's `rows.txt` as soon as it is appended
   and fsynced. Peak disk becomes the table plus one part. The trade-off: an interrupted copy then reruns `_final`.
   Record that as the save-point rule.
5. **Required: `_verify` reads a whole part segment into RAM.** Stream it line by line (the file offsets are already
   known) so 30 helpers do not each hold GBs.
6. **FYI, a format question for Greg (not a code bug):** the crosswalk carries `book_full.ask_levels_full` whole on
   every group row, but reduces the bid ladder to counts (`bid_levels_full[]`). If that is intended, the members table
   carries the full ask ladder once per group, uncompressed, in the text Frankie reads. If not, the path should be
   `book_full.ask_levels_full[]`. That is a crosswalk change, so it is Greg's call.

## 4. Making it faster (ranked by leverage)

1. **One read for plan and count, and no stored plans** (the WIP). This removes a full write and re-read of every row
   (`plans.sqlite`), plus `final.sqlite` and the emit pass. The old count pass sat at 37% CPU in disk wait, with
   `TS._load` (16%) and JSON decode (18%) re-reading the plans (py-spy, run 36368258630).
2. **Digest keys in WITHOUT ROWID tables (#2).** This cuts the count and merge writes and speeds the single-core merge.
3. **Drop the `TS._dump(row)` round-trip check in `_snapshot`.** The rows come out of `json.loads` + `_spell`
   (JSON types only), so the check cannot fail, yet it recursively packs, serializes, parses, unpacks and compares
   every row. Leave table 7 as it is (its snapshot is saved, and the V2 adoption requires `_snapshot` unchanged). This
   would speed the lifecycle tables that follow. It needs a keyed `_snapshot` version so the table-7 adoption is not lost.
4. Stream `_verify` (#5). Less RAM, and the page cache is left to the source reads.
5. Keep the same 30 CPUs (the specs sha depends on 2 x len(cpus) parts).

## 5. Recovery-plan correction (the handoff's option A)

The boothook as written deletes ONLY `part-*/plans.sqlite`. If the count pass had started (section 1), part of the 461
GB is `part-*/freq.sqlite`, and it stays. Under the lean writer only `passes.pkl` (the snapshot) is reused, so the
boothook should:
1. Print `ls -l` of every `table-0007/part-*/*` file, plus `ls -l table-0007/passes.pkl` and `df -B1 /`, to
   `/dev/console`. `frankie_box_console.sh` then reads them without SSM, which gives the plan/count byte split (section 2)
   for free.
2. Delete `table-0007/part-*/plans.sqlite`, `freq.sqlite` and `final.sqlite` (none are used by the lean writer), keeping
   `passes.pkl`.

The rest of the handoff stands: it is still a box power action, and it needs Greg's go.

## 6. Status (later 2026-09-28): fixes built, then a second, independent review
All of sections 3-5 are built: commits 24a7a4f7, and the follow-up commit carrying this section, on
`claude/frankie-monday-continuation-qlkvqr`. The ask ladder is carried as `book_full.ask_levels_full[]#count`
(Greg: the whole ladder was not intended). The handoff's UPDATE section lists what changed and the dispatch order.

A fresh-context code-reviewer pass on 24a7a4f7 (read-only; it compared the new writer with `TS.write_table` on generic
inline rows in its sandbox: 384/390 byte-identical, and every failure was the 1-row case below) found:
- **Critical, fixed:** `_final` refused every table whose columns are all constant or derived (every 1-row table:
  `bedrock.run`, `bedrock.matching_rule.*`). ROOT would have failed on its first bedrock table. The check now tests the
  cells themselves; an empty row line is what the serial writer writes.
- **Fixed:**
  - `MEMBER_LIST_PATHS` is now in the table save key (`_code_identity`).
  - A corrected column that meets a column already read now refuses on conflict instead of being silently overwritten.
  - The coordinator's table-wide facts (`_seeds`, `_table_facts`, `_separator`) are named helpers keyed with their passes.
  - Disk checks before the copy's header and dictionary, and before the proof's dictionary load.
  - Queued parts check disk first (they fail fast after a `DiskReserve` stop).
  - The unused plan bound is removed.
  - The destination directory is created.
  - `tests/test_digest_save_points.py` is updated to the legacy-key behaviour (not run: Greg's rule).
- **Accepted, recorded:**
  - Every bedrock table rebuilds this time, because its key carries the whole code identity. None was saved, so
    nothing is lost.
  - A fix to `_copy` after the copy is saved re-plans the table, because the dictionary and counts are deleted by
    then. That is the price of the disk policy.
