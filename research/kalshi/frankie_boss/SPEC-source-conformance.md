# Explicit source stream conformance V1

This additive driver connects an explicitly mapped native-record stream to the
unchanged C15 full-evidence builder. It does not extract DBN fields, fetch sources,
derive QSV, authorize a result-bearing run, or establish production throughput.

The caller provides a SourceScope and independently trusted scope genesis hash.
Every append supplies its global physical cursor, source member index and source
digest, plus the complete raw mapping and explicit session identity. The driver
checks those source coordinates against the scope before ingestion. The mapping
passes unchanged to C15Builder; every applied record and declared defect remains
available, including non-F_LAST events, duplicate messages and extra raw fields.
No record is sorted, deduplicated, aggregated, repaired or implicitly projected.
Declared hashes bind caller assertions; they do not prove these mappings were
extracted from the declared source bytes. Native extraction conformance remains
a separate gate requiring a pinned complete-field extractor.

The driver owns its builder and journal as a single writer. A failed append stops
the driver. Pre-ingestion envelope failures do not count as accepted raw records;
builder failures retain the existing INPUT/FAILED evidence. Recovery requires an
explicit trusted checkpoint and its matching journal; there is no truncation.
Checkpoint export requires closed groups and verifies all journal pairs. Restore
uses C15Builder.restore with an independently supplied state hash and rechecks
stream conformance. The driver does not add a second book or replay engine.

Completion requires the exact declared total and each member count, closed groups,
paired INPUT/APPLIED evidence, source/cursor consistency, and agreement between
journal and builder terminal prefix. Its immutable receipt binds scope kind/hash,
record/member/group counts, terminal prefix, journal head and builder state hash.
Completion is idempotent but revalidates the journal; appends afterward fail.
Partial checkpoints are not completion receipts. Receipt hashes prove integrity,
not operational authorization or source extraction correctness.

Acceptance: synthetic mixed/interleaved events preserve original control outputs,
raw bytes and defects; bad cursors/digests/members, missing/extra records, unfinished
groups and journal tampering cannot complete; trusted checkpoint restart yields
the same final receipt as continuous ingestion. Existing forecast, QSV, Frankie,
V4 adapter and C15 modules remain unchanged.

Verification: run test_source_conformance.py first, then adjacent C15 full-evidence
and causal-prefix tests with the repository's documented PYTHONPATH setup.
