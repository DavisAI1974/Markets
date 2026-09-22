# DIGEST_V6 bounded-memory design — 2026-09-22

Status: reviewed design only. Current production digest generation is NOT fully streaming. Do not claim a two-million-row runtime or speedup from existing row spools.

## Requirement

Generate byte-identical DIGEST_V6 and prove every row reconstructs exactly, without memory proportional to row count or distinct dictionary values. Preserve all current optimizations and scientific values; no document or BOSS output truncation.

Keep digest_text/render_layers compatibility APIs for small callers. Production requires write_digest(destination, ..., scratch_directory), which stages a fresh file, verifies it completely, then publishes while preserving previous evidence.

## Existing allocations

boss_session.derive reloads every bedrock JSON and creates one complete digest string. digest_text materializes all legacy row spools. render_table retains flat rows, plans, dictionaries, cells and text. parse_table builds all lines and parsed rows. render_layers retains every parsed table and block. bedrock_tables retains merged members and all section rows.

RowSpool makes the earlier derivation cheaper but does not remove these allocations.

## Byte-preserving implementation

1. Use replayable disk table sources. Stream-parse the independently pinned layer JSON, or normalize each spool row through the exact existing JSON round trip (sort_keys=True, default=str, tuples become lists). Raw spool types/order differ from reloaded JSON; bypassing this conversion can alter first-seen columns and dictionary numbers.
2. Disk-plan each table with a flat-row spool, planned-cell spool, SQLite frequency/dictionary index and final-cell spool. Preserve first-seen column order, all-row derivability/constants, cross-table comparisons, counts after excluding whole columns, first-occurrence dictionary numbering, scale selection, cell collapse and final separator choice. These are whole-table decisions: a generator alone is insufficient.
3. Emit header and rows incrementally after planning. The dictionary header can itself be table-sized; emit/parse tab-delimited entries incrementally rather than using readline/split.
4. Stream inverse parsing one row at a time, comparing immediately with _same and enforcing exact count and complete block consumption. Keep dictionary values on disk. Preserve negative zero, NaN, tuple/list identity, missing vs null, escaped strings and all current derived rules.
5. Keep only required cross-table context. CROSS_DERIVED currently needs two timestamp columns from legacy_book_imbalance, by ordinal. Store those verified values on disk and stream them beside structures. RowSpool arbitrary indexing scans and must not create quadratic access.
6. Disk-aggregate bedrock member (group_index,column) unions with typed conflict checks and original insertion/group ordering. Preserve lifecycle's FIRST derived layer having nonempty rows for each section; do not union duplicate projections. Preserve family count ordering with first-seen ties.
7. Generate per-second rows without changing cumulative-sum arithmetic order. Reassociating floating point operations into a rolling sum can change exact output.
8. Keep all failed scratch evidence. Publish no current digest on disk, verification or count failure. Use move receipts for prior artifacts.

Memory may depend on the largest row/cell, column metadata, previous row, bounded dependency buffers and configured SQLite cache. An arbitrarily large single nested cell is not a constant-memory promise.

## Proof requirements

- Byte-exact differential output against the existing renderer at e297553a7c96dd615879e5aa8e5c5a0118aeaff2, all current fixtures and randomized structural rows.
- Late differing constants, non-derivable values and spaces; mostly unique strings; late repeated strings; constants-only/empty tables; scales and paired offsets; cross-table match/fallback; bedrock conflicts and family ties.
- Production derive sentinels forbid full bedrock load_json, list(RowSpool), whole digest reads and string-returning wrappers.
- Fresh-process resource tests at substantially different row counts, fixed row width and increasing distinct dictionary size; record RSS and Python allocations.
- Corruption, truncation, count mismatch, write failure and interruption retain old evidence and publish no successful digest.

## Separate remaining memory boundaries

project_sections still loads producer result.json. Legacy flow arrays grow with represented seconds. _measure_digest reads/decodes/tokenizes the whole digest: arbitrary chunk token counts are not exact whole-input BPE counts. A bounded exact tokenizer method needs its own equivalence proof; never relabel estimates as exact.

reading_corpus, reading and writing also load full documents. Completing this codec will establish bounded digest generation/proof, not an entirely bounded session. Record these distinct limits and measure actual workload before release.
