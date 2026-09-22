# Trading-day schedule and launch binding

Authority: Greg's September 22 direction to build modules 2-4 now and leave receipt-dependent and modelling values explicitly blank.

The launch source is the committed Monday manifest: trade date 20211004, Sunday 18:00 to Monday 17:00 America/New_York. UTC files are partitions. The existing weekend folding includes the 245 pre-open records; scheduling must not filter them away. The manifest declares 2,032,203 records; only the completed ingestion receipt measures the accepted count.

## Contract
A new schedule schema carries the trade date, exact source manifest hash and members, measured record and journal identities, explicit step count, authored cutoff rule, and positive model_context_rows. Retain the V1 Sunday reader and historical artifacts unchanged. Unknown values in the launch declaration are JSON null; validation names every missing field and refuses before source access or runtime work.

Cutoffs remain an independently supplied and hashed roster of closed groups. Do not choose a time interval, a row window, or a cycle count. Build causal clocks and prefix hashes from the verified completed compact journal. Verify every mapping row, cutoff closure, increasing availability, terminal count and feedback boundary. Preserve checkpoint and journal identity checks.

## Host
Read record and cycle counts from the verified schedule. Materialize every requested prefix, including cycle zero, from the compact container; never require the historical raw source or reuse its prefix zero. Seed selection and code witnesses are re-minted by the existing collector. New source contracts declare trade date and cycle count and remain separately pinned; do not manufacture principal conventions or learning labels.

## Box
Carry the trade date in the request and source object. Preserve the expanded cycle-zero producers, classroom, comparison and receipts. Stream rows through the traversal and project layer files without retaining every layer's rows simultaneously. The service context is not a reason to omit evidence. Keep full ledgers and file witnesses.

## Validation and release
Regression: raw and both CLI writers must publish completion receipts without querying compact-only tables.
Test new schedule serialization, corruption, null refusals, declared cycle counts, compact-only prefixes, exact source anchors, and streaming equivalence. Verify old Sunday fixtures still read unchanged.
No production dispatch while ingest run 35694087514 is active. No canary. Publish route, row count, cutoff roster/rule, source contract and post-ingest pins remain blocking blanks until supplied. The existing full rerun order with step 1b still applies.

## Implementation order
1. Add failing regressions and new-contract tests.
2. Build schedule validation and completed compact scheduling.
3. Adapt host gates and compact prefix generation.
4. Carry trade-date identity through the expanded box and bound memory usage.
5. Run remote checks, review diffs, record remaining blanks and exact commit.
