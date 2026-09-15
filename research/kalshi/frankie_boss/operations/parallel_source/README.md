# Independent GitHub source verification

This runner verifies an isolated snapshot of the existing full Sunday journal.
It never submits inference, re-extracts source data, writes local launch gates,
or stops another process. Python 3.13 and its standard library are sufficient.

## Invocation

```sh
python -B verify_snapshot.py --bundle-dir /data/bundle --output-dir /data/result --workers 3
```

The output directory must not exist and must be separate from the bundle.
Default workers: `max(1, os.cpu_count() - 1)`; the parent performs ordered
source conformance while workers validate envelopes. On a four-CPU runner,
three workers and the parent can use all four CPUs. Actual speed remains to
be measured. No runtime or startup deadline is introduced by this script.
The hosting provider's job limit still applies.

## Bundle contract

The parent must authenticate and safely extract the archive before invoking
the script. Bundle contains:

- `source.sqlite`: a standalone consistent SQLite backup, no WAL/SHM/journal sidecars.
- `checkpoint.json`: exact terminal periodic checkpoint bytes.
- `checkpoint-receipt.json`: exact retained receipt.
- `manifest.json`: original selected-source manifest.
- `code/`: flattened twelve Python files listed in `CODE_FILES` in the runner.
- `bundle-manifest.json`: `{"files":{"relative/path":{"bytes":123,"sha256":"..."}}}`.

All sixteen mandatory files must appear in `files`. Extra pinned files such as
scope and extraction receipts are allowed and verified. Extra top-level manifest
metadata is allowed. Code is copied byte-for-byte into an isolated research
package layout; package initializers are not executed. Preserve original CRLF
bytes because source implementation identity hashes raw file bytes.

## Verification

The exact original `C15Builder.restore()` validates checkpoint identity,
restores and roundtrips adapter/prefix state, and requests a full journal pass.
The original `SourceConformanceDriver.complete()` requests the second pass and
checks all INPUT/APPLIED pairs and reconstructed source-prefix/group receipts.

Only the journal iterator is replaced. Worker predicates reproduce the original
`EvidenceJournal.entries()` parser, exact re-encoding, envelope identity, and
digest checks. Futures return in original row order. At most twice the worker
count is in flight. Global count/head and a fresh database-tail check finish
each pass. No rows are sorted differently, filtered, sampled, or skipped.

Independent hard-coded terminal pins bind the exact checkpoint SHA, scope,
state, journal head/count, source prefix, 57,027 records and 43,569 groups.
The snapshot's physical SHA is checked before and after verification.

## Results

`verification-receipt.json` records full SourceCompletion and its digest,
physical snapshot SHA/size, checkpoint identity, code hashes, runner hash,
worker count, timestamps, and GitHub run identity when available.
It explicitly sets `gate_authority=false`. A successful receipt is not an
automatic authorization to replace local completion/ingestion/progress files.
Failures produce `verification-failure.json` and a nonzero exit.
Progress is newline JSON on stdout with advancing entry and physical-read counters.

## New synthetic validation

Seven new behavioral checks passed once: original completion equality and
two-pass progress; self-hashed wrong journal binding rejection; modified code
rejection; path escape rejection; noncanonical body rejection; corrupt digest
rejection; missing tail rejection. The completion check also verified unchanged
physical DB bytes and absence of torch imports.

That first test invocation exited nonzero during teardown because the *test
fixture* relied on SQLite's transaction context manager to close a connection.
The fixture now closes explicitly. A separate new Windows rename/cleanup check
passed with exit zero, confirming the corrected fixture releases its handle.
Already-passing behavioral checks were not repeated. No production journal or
market source was opened, and no existing test suite was rerun.

Tests require `FRANKIE_TEST_CODE_SOURCE` pointing to the existing
`research/kalshi/frankie_boss` directory, and TEMP/TMP set to E on this host.
