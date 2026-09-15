# Independent GitHub source verification — launch review

Frozen Sunday application code: `35982ac7d42b546446038866299c23ca4fc50edc`.
This is a separate verification job. It does not start inference or release the local Sunday gates.

## Reviewed result

Independent cloud/runner review found no blocking issue. All twelve bundled raw source files were compared with the frozen commit after CRLF normalization; all matched. The archive retains the original raw CRLF bytes required by checkpoint implementation identity.

Runner SHA256: `b71281dcf8adedadc296fe411be64cbaa7c80ee1959beabd84dd5cdabc9dc9b6`.

The verifier reproduces every original per-row validation predicate in bounded, ordered process workers. Three workers and the parent use the four advertised GitHub runner CPUs. Original checkpoint restoration and source conformance still run, including adapter roundtrip, INPUT/APPLIED pairing, all prefix/group receipts, and terminal identity. Two full passes remain. Actual speedup is unmeasured until this job runs.

Snapshot creation uses SQLite online backup from a read-only source connection, including committed WAL data. The independent copy must match the already-written terminal checkpoint. The live source process continues. Copied database restoration uses the original SQLite constructor, performs reads and connection configuration, then enables query-only before conformance. Physical SHA is verified before and after.

Transfer uses private S3 storage, AES256 server-side encryption, a checksum-bound conditional PUT, and an RSA/AES encrypted upload capability. Credentials and signed URLs stay out of files/logs except the encrypted capability. Raw journal data is excluded from public Actions artifacts and Git. The workflow exposes existing AWS credentials only to transfer steps. No account, authentication setup, usage reset, Pod or model action is performed.

Archive extraction rejects traversal, links, duplicate members and expanded size excess. The runner checks actual available disk against expanded snapshot plus compressed archive plus reserve. Hosted jobs have GitHub's six-hour provider maximum; the verifier adds no elapsed deadline. Local work remains available if the hosted job fails or times out.

## Validation performed once

- Seven new parallel-verifier behavior checks passed, including exact original completion equivalence and canonical/digest/tail corruption rejection. The first invocation had a test-fixture teardown failure due to an unclosed SQLite connection. Explicit fixture close was added; one new Windows rename/cleanup test passed. Previously passing behavior checks were not repeated.
- Two new archive-boundary tests passed: valid bundle preservation and traversal/absolute path/symlink rejection.
- New Python files parsed; workflow YAML parsed.
- Twelve copied source files matched the frozen committed implementation after newline normalization.

## Adoption boundary

A successful `verification-receipt.json` has `gate_authority=false`. It independently verifies the exact snapshot. It must not be copied over local `completion.json`, `ingestion-receipt.json`, progress or configuration files. The existing schedule/lineage/prefix processes still wait for the original source receipts. Using the remote result as the first finisher requires a separately reviewed integration that preserves original logical identity and physical-file provenance.

Optimization review is tracked separately in `JOURNAL_OPTIMIZATION_REVIEW.md`; its existing 3.37x synthetic reader measurement is not a target, ceiling, or Sunday performance claim.
