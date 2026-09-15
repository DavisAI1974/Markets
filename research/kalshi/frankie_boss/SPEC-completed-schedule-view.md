# Read-only completed-source schedule view

This helper verifies independent checkpoint bytes/state hashes, source implementation identity, source scope, exact completion receipt, complete pair count, adapter summary counts and restored RecordPrefixChain. It opens a read-only VerifiedJournalReader only after those checks. It is explicitly READ_ONLY_COMPLETED_SOURCE_SCHEDULE_VIEW; no adapter is restored or processing authorized.

Existing build_schedule and journal_prefix remain unchanged. They stream every INPUT/APPLIED pair, validate cursor and raw source bindings, and compute all 19 cutoffs. The view additionally validates alternating kinds and the final APPLIED source prefix, record and group counts. A successful exhausted stream exposes terminal verification witnesses. Nothing is truncated, sampled, or cached. This avoids the duplicate whole-journal scan performed by C15Builder.restore before schedule construction.

The operational one-shot script still waits for ingestion-receipt.json written after the source writer closes, refuses failure.json, requires all57,027records, retains original failed schedule output, and writes new schedule output. New execution receipt binds view and reader code SHA256 independently of source identity. No real source reads occur before completion.

New synthetic seams: seven checkpoint/completion/tail checks passed once; one additional pair-kind rejection check is separate. No existing passing suites or completed source operations repeated.

Fresh review found that a self-consistent partial checkpoint could otherwise pass with a forged completion denominator. The view now independently requires chain.next_cursor to equal the sum of source member record counts. A new partial-source seam failed before this guard and passed afterward; the earlier eight passing checks were not repeated.
