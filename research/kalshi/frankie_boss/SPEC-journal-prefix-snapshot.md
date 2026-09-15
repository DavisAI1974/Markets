# SPEC: journal prefix snapshot (bounded, verified, read-only)

Date: 2026-09-15. Claude slice on `codex/full-frankie-boss-connection-20260915` @ 6c480f75.
Module: `research/kalshi/frankie_boss/journal_prefix_snapshot.py`. Tests: `tests/test_journal_prefix_snapshot.py`.
Not wired into any runtime path; `online_source_prefix.py` is unchanged. Codex owns integration.

## Purpose

`online_source_prefix.snapshot_closed_prefix` accumulates every selected raw row in a Python list before
inserting them, so its memory grows with the cutoff. This helper copies the same original
`ordinal/kind/body/digest` bytes page by page, committing each page to the destination before the next is
read, then verifies the entire copy with `VerifiedJournalReader` before the destination path is created.

## API

```
snapshot_journal_prefix(source_path, destination_path, *,
                        parent_count, parent_head_hash, through_cursor,
                        parent_sha256=None, page_rows=64) -> receipt dict
```

- `parent_count`, `parent_head_hash`: the independently trusted tail of the source. The stored tail must
  equal them (checked through `VerifiedJournalReader` at open) before any byte is copied. The current
  database tail is never trusted on its own.
- `through_cursor`: zero-based cursor of the final APPLIED record. Ordinals `0 .. 2*through_cursor+1` are
  copied. That final APPLIED record must carry `raw_record.flags & 128` (F_LAST), else the attempt is refused.
- `parent_sha256`: optional physical pin of the source file, checked before and after the copy.
- `page_rows`: rows fetched per page; the only per-row state held is one page (default 64).

Receipt keys: `schema` (`C15_JOURNAL_PREFIX_SNAPSHOT_V1`), `evidence_class` (`READ_ONLY_VERIFIED_JOURNAL_PREFIX`),
`original_journal`, `snapshot_journal`, `parent{count, head_hash, sha256}`, `through_cursor`, `records_in_prefix`,
`journal_count` and `journal_head_hash` (the actual copied prefix tail, as stored), `snapshot_sha256`,
`source_prefix_hash` (the final APPLIED record's `terminal_prefix_hash`), `groups_in_prefix` (F_LAST closes in
the prefix), `record_count`/`group_count` (the final APPLIED record's adapter counters), `as_of` (maximum
`normalized.ts_recv_ns`), `source_as_of` (maximum `normalized.ts_event_ns`), `provenance{method, page_rows,
verified_by, source_size_bytes, source_mtime_ns, staging_path}`, `full_source_complete=False`,
`model_forward_performed=False`.

Open the result with `VerifiedJournalReader(receipt['snapshot_journal'], expected_count=receipt['journal_count'],
expected_head_hash=receipt['journal_head_hash'])`. No handle is returned; nothing is left open.

## Procedure

1. Argument validation; the destination must not exist (a symlink counts as existing) and must differ from
   the source; the source must be a regular file.
2. Closed-source check: refuse if `<source>-journal` exists (hot rollback transaction) or `<source>-wal`
   holds frames beyond its 32-byte header (uncheckpointed writer content). A zero-length `-wal` or a `-shm`
   file is ignored: a read-only open of a WAL-mode database (including this helper's own and the reader's)
   creates them and cannot remove them, and they carry no content. Retained WAL snapshots from
   `source_recovery` are therefore acceptable sources once their writer has closed.
3. Optional `parent_sha256` check; record source size and mtime.
4. Trusted parent check: `VerifiedJournalReader(source, expected_count=parent_count, expected_head_hash=
   parent_head_hash)` must open (stored tail equals the trusted pair); `2*through_cursor+1 < parent_count`.
5. Staging file `<destination>.partial-<uuid>` is created as an `EvidenceJournal` (same table and append-only
   triggers). Pages of at most `page_rows` rows are read from a read-only, query-only source connection with
   `WHERE ordinal>? AND ordinal<=? ORDER BY ordinal LIMIT ?`; each page is checked for ordinal continuity,
   INPUT/APPLIED alternation, `bytes` body and `str` digest, then inserted and committed before the next page
   is fetched. A FAILED row or a gap refuses the copy.
6. The staging file is verified end to end by `VerifiedJournalReader` with `expected_count = rows copied` and
   `expected_head_hash = last copied digest`: canonical bytes, digests, previous-hash chain and tail. Streaming
   that same pass, every INPUT/APPLIED pair is checked as `context_session.journal_prefix` does (cursor
   sequence, `pack(raw_record) == pack(record)`, member and session equality), clock maxima are taken, F_LAST
   closes are counted, and the final APPLIED must be `cursor == through_cursor` with F_LAST set.
7. Source size and mtime must be unchanged and the closed-source check must still hold; the optional sha256
   is rechecked.
8. `os.rename(staging, destination)`. If the destination appeared meanwhile the rename fails
   (`FileExistsError` on Windows) and the staging file stays; nothing is ever overwritten.

On any failure after step 5 begins, the staging file is retained for diagnosis and its path is attached to the
exception as a note (`partial prefix snapshot retained for diagnosis: ...`). The destination path is never
created by a failed attempt, so a retry may reuse it.

## What it is not

Not full-source completion (`full_source_complete=False` always), not a `C15Builder` checkpoint, not an
`OnlinePrefix` view, not training permission. It does not decode records for adapter replay, does not touch
the source for writing, and does not open active ingestion or recovery databases (a live writer's journal
fails the closed-source check or the parent tail check).

## Bounded memory

Per-row Python state is one page of raw rows plus, during verification, one decoded envelope (the reader
streams). No full-journal list exists at any point. `test_copy_is_paged_and_durable_before_the_next_page_is_read`
wraps the page generator and proves, with `page_rows=2` on a 12-row source, that every earlier page is already
present in the staging file when the next page is requested.

## Test results (this slice only, run once)

`PYTHONPATH=".;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests"`
`python -m pytest research/kalshi/frankie_boss/tests/test_journal_prefix_snapshot.py -q` -> **12 passed** (5.71 s).
No existing suite was rerun; no smoke runs, source replay, model, cloud/Pod or active recovery database reads.
Seams covered: exact original rows and digests retained and source bytes unchanged
(sha256 before/after); paged, durable copying; non-F_LAST cutoffs (cursors 1 and 3) and an out-of-range cursor
refused with the partial retained only when copying had begun; a FAILED row inside the prefix refused while
an earlier F_LAST cutoff still succeeds; three corruptions (digest, body, kind) rejected; an existing
destination preserved byte-for-byte and a destination appearing mid-copy never overwritten; wrong parent
count, wrong physical pin and a hot `-journal` sidecar refused; a retained WAL-mode copy accepted as a source.

## Unresolved limitations

- The closed-source rule is heuristic on sidecars plus the trusted-tail check; it cannot detect a writer that
  holds the file open without an outstanding transaction. The caller must stop the writer first, as
  `source_recovery.rehydrate_source` already requires.
- Source mtime/size equality is a cheap change detector, not a proof; pass `parent_sha256` when a physical
  pin is required (two full reads of the source).
- Each APPLIED body is decoded once (during verification); the copy pass reads bytes only. Total cost is one
  `VerifiedJournalReader` pass over the prefix plus the raw copy.
- The helper trusts `raw_record.flags`, `normalized.ts_event_ns`/`ts_recv_ns`, `terminal_prefix_hash`,
  `record_count` and `group_count` as written by `C15Builder.apply`; a journal written by another producer
  with different payload keys is refused with a `KeyError` from the pair check, not silently accepted.

## Blob hashes (git, LF)

- journal_prefix_snapshot.py 8e176377844d8ff205487c1c277dc72db70564e6
- tests/test_journal_prefix_snapshot.py beb9c67996ca7e9c1a1cb78a468e07a3afdfe346
