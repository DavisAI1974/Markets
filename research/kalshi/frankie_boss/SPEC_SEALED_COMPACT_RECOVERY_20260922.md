# Monday sealed-container recovery design — 2026-09-22

Status: design reviewed; not implemented, not executed, no successful ingestion receipt.

## Preserved evidence

The cancelled run 35694087514 processed all 2,032,203 declared records, then stopped at 62.76% conformance. AWS confirmed cancellation at 08:27:39Z. Audit 35705637431 found no ingest processes/helpers and 32 CPUs.

Preserve in place:
`/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite`

Measured file bytes: 23,687,368,704. Seal count: 4,064,406 entries. Seal head: `534f442aa0008032064c540f1c472433cb665a97bfec94399f8137ca103f207c`. There are 37,934 compact boxes with 70–256 rows per box. Box packing was active; no new speedup has been measured. These are measurements, not a completion receipt or independently established physical SHA256.

The builder checkpoint was saved only after successful conformance. No checkpoint exists from this cancelled operation. No continuation may fabricate one.

## Recovery contract

A new, separate read-only recovery operation may verify the complete sealed container and reconstruct state from retained observations. It must not call C15Builder.apply, InstrumentBook.apply, open/decompress source files, extend a journal, alter its seal, resume ingest, or synthesize missing records.

Require independently pinned manifest/scope, physical container SHA256 and bytes, seal count/head, and original deployed implementation identity. The original box checkout is reported as `2ae4da204b0d2a12f605e765f281b505ff51491a`; audit its actual provenance before using it. Journal envelopes do not independently establish C15Builder.identity.

Refuse missing or mismatched physical identity, sidecars, unsealed containers, odd entry counts, FAILED records, unsupported implementation versions, wrong declared record count, bad block/hash/seam, open groups, or missing terminal observations. Full conformance must run from the beginning: 62.76% progress was not a durable conformance checkpoint.

## Reconstruction from retained facts

The existing source_recovery.rehydrate_source is unsuitable. It uses raw SQLite entries, copies the database, calls builder.apply per record, and may append APPLIED. Do not invoke it for this container.

Use verified full canonical envelopes in workers. Transfer only recovery fields, preserving ordered seams; do not restore full book IPC for every row. Current compact conformance projection omits effect/frame/observation and needs a separate recovery projection.

- Recompute RecordPrefixChain from the verified ordered stream, including group counters and final receipt.
- Rebuild global record/group counts from that stream.
- Recover orders, FIFO levels, integrity and watermarks from each instrument's final closed APPLIED observation. Convert exactly as mbo_resume_state._book_state does, including empty-level filtering and order.
- Carry the last frame raw_symbol, checked against normalized history.
- Reconstruct activity using normalized plus retained effect, copying the pinned adapter's exact algorithm: snapshots skipped; append non-snapshot activity; expire strictly from the deque front while its receive timestamp is less than the current message receive time minus 300 seconds. A terminal timestamp filter is wrong when clocks regress.
- Recover each instrument's activity clock from its last F_LAST frame, and session from the verified submitted session.
- Retrieve and verify only terminal full observations separately when needed, avoiding full-book transport per record.
- Require restore_adapter_state followed by export to reproduce the reconstructed state exactly. Verify prefix, adapter, session and count consistency.

References: c15_observer.observe_book; mbo_resume_state export/restore; causal_prefix_records RecordPrefixChain; pinned V4 adapter _append_activity/event_frame; compact_conformance_reader.

## Honest publication and missing boundary evidence

Publish new artifacts only in a fresh recovery directory after full verification. Recheck the original container physical identity before publication. Record recovered state as reconstructed, with original container and code pins, method, conformance result and measured resources. Preserve interrupted recovery attempts.

The partial-source next-session lookahead was retained only in memory by ingest_block_sources. It is absent from the journal. Logged source_verification under pinned original code supports an inference that the check was reached, but cannot recreate the exact original next_session_id witness. Require independent boundary evidence, or explicitly authored acceptance of a narrower recovery attestation. Never manufacture partial_members_ingested or an original ingestion receipt.

prepare_trading_day currently assumes journal_file lives next to ingestion_receipt. Add an explicit pinned-container recovery schema/interface to use the preserved original path from a fresh recovery directory. Do not move or duplicate the 23.7 GB source to satisfy the old convention.

## Proof required before remote execution

An uninterrupted synthetic compact fixture supplies an independent expected checkpoint and completion. Reconstruct from journal alone and require identical canonical packed state bytes/hash and equivalent completion under original implementation pins.

Exercise multiple instruments, interleaved groups, snapshots, reset/one-side clear, modifications/cancels, missing references, trades/fills/none, empty FIFO levels, raw-symbol carry-forward, session/member seams, receive-clock regression, later snapshot-only timestamps, and exact 300-second boundaries.

Install failure sentinels on adapter apply, source opening/decompression, journal writes and seal changes. Require zero calls. Test corrupt bytes/blocks/seams/scope/code identity, odd tails, FAILED records, incomplete counts and unfinished groups. Interrupt verification and publication; require preserved parent bytes and no successful receipt. Feed recovered state into real completed-schedule and compact-prefix preparation fixtures.

Only after these checks, review and original-code provenance can a conformance-only operation be considered. NO CANARY. NO INGEST RESTART. No host/Pod stops, no bootstrap changes. Greg-dependent launch values remain blank.
