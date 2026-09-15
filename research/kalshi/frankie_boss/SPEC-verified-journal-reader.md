# SPEC: verified journal reader (read-only, bounded memory)

Date: 2026-09-15. Claude slice on `codex/full-frankie-boss-connection-20260915` @ 04209376.
Module: `research/kalshi/frankie_boss/verified_journal_reader.py`. Tests: `tests/test_verified_journal_reader.py`.
Not wired into any runtime path. Codex owns integration.

## Purpose

`EvidenceJournal.entries()` (c15_journal.py) verifies each row by `unpack(json.loads(body))`, then
`canonical_bytes(pack(envelope))` to check canonical bytes, then `evidence_hash(envelope)` which packs and
serializes the same envelope a second time. Consumers (builder, context session, controller journal, ledger,
handoff export, reveal) repeat that full read. This reader performs the same acceptance and rejection decisions
with one parse, one validating decode, one canonical serialization and one SHA-256 over the validated bytes.

## Separate implementation identity

- `VerifiedJournalReader` is a new class. `c15_journal.py`, `causal_packet.py`, `c15_builder.py`,
  `context_session.py`, the teacher, coordinator, adapter, runtime and launch files are unchanged. Every
  existing source-code identity that active source recovery pins is untouched.
- The reader imports only `SCHEMA` and `evidence_hash` from `c15_journal` (the latter once, to derive the
  genesis hash `evidence_hash(dict(schema=SCHEMA))`). The digest prefix is the existing `SCHEMA + NUL`.
- It shares no state with `EvidenceJournal`; it opens its own read-only SQLite connection.

## API

```
VerifiedJournalReader(path, *, expected_count: int, expected_head_hash: str)
    .path         Path
    .count        int   (the supplied expectation, verified against the stored tail at open)
    .head_hash    str   (same)
    .entries()    generator of unpacked envelopes, in ordinal order, verified row by row
    .verify(*, count, head_hash)   iterate everything, then compare to the supplied pair
    .append(...)  always raises PermissionError
    .close()      ; also usable as a context manager
canonical_tagged_bytes(tree) -> bytes    specialised canonical_bytes for pack() output
decode_tagged(tree) -> value             unpack() with structural validation
GENESIS_HASH, DIGEST_PREFIX
```

Compatibility with `EvidenceJournal` read behaviour: `path`, `count`, `head_hash`, `entries()`, `verify()` and
`close()` have the same names, signatures and success semantics. Differences, all deliberate:

1. Construction requires `expected_count` and `expected_head_hash` (keyword-only). The stored tail row is
   compared to them at open and the reader refuses with `journal differs from checkpoint; existing evidence
   was retained` on mismatch. The tail is never trusted on its own. `count`/`head_hash` are the supplied values.
2. The connection is opened with `?mode=ro` plus `PRAGMA query_only=1`; any write through it fails at the
   SQLite level. There is no public `connection` attribute. `append` raises before touching the database.
3. Rejections are always `ValueError`. The original can surface `KeyError`, `TypeError` or `IndexError` for
   some malformed tagged trees (for example a JSON object where a tagged list is expected); this reader
   normalises those to `ValueError('malformed evidence value tag')`. The set of rejected rows is the same.

## Verification per row (order matters)

1. `body` must be `bytes` (a TEXT body is rejected exactly as the original's `str != bytes` comparison does).
2. `tree = json.loads(body)`.
3. `envelope = decode_tagged(tree)`: a validating `unpack`. It accepts a node only if `pack(unpack(node))`
   would reproduce it byte-for-byte: tag arity, exact `type(...) is` checks (no bool under `int`, no int under
   `bool`, no float anywhere), lowercase even-length hex for `bytes`, lowercase 16-hex for `float64` whose bits
   round-trip through `struct`, list-typed sequence bodies, string and unique mapping keys, known tags only.
4. `canonical_tagged_bytes(tree) == body` (canonical byte check, performed before any hashing).
5. Envelope fields: mapping, `ordinal == running count == envelope['ordinal']`, `schema`, `kind` column equals
   `envelope['kind']`, `previous_hash` equals the prior digest.
6. `sha256(SCHEMA + NUL + body) == digest` over the already-validated bytes.
7. After the last row: running count equals `count` and last digest equals `head_hash`, else
   `evidence journal changed during iteration` (also covers rows appended after open and a deleted tail).
8. Fresh tail reread (added 2026-09-15, second slice): once the iterating SELECT has finished and released
   its read snapshot, the stored tail is queried again with a fresh statement and must still equal
   `(count, head_hash)`. In WAL mode a row appended by another connection during iteration is invisible to
   the iterated rows, so step 7 alone would pass; only the stored tail reveals it. Likewise a tail row deleted
   externally during iteration is still served by the snapshot and is caught only here.
   `tests/test_verified_reader_concurrent_tail.py` covers both, plus an unchanged WAL journal that must still
   verify. `EvidenceJournal.entries()` (unchanged, not owned by this slice) has the same WAL gap; the reader
   does not inherit it. In rollback-journal mode a concurrent writer is blocked by the reader's shared lock
   instead, so the case cannot arise there.

Steps 3 and 4 together are what make step 6 equivalent to `evidence_hash(envelope)`: the original hashes
`canonical_bytes(pack(envelope))`, and `pack(envelope) == tree` (step 3) with `canonical_bytes(tree) == body`
(step 4) gives `canonical_bytes(pack(envelope)) == body`.

## The specialised serializer and its equivalence

`pack()` emits only `list`, `str`, `bool` and `int` nodes; floats and bytes are hex strings. `causal_packet._canon`
is the identity on that vocabulary (bool checked before int; str and int returned unchanged; lists rebuilt in
order; no mappings, so `sort_keys` has nothing to sort). `canonical_bytes(tree)` therefore equals
`json.dumps(tree, separators=(",", ":"), ensure_ascii=True).encode("utf-8")`, which is `canonical_tagged_bytes`.

Demonstrated in `test_specialised_serializer_is_byte_identical_to_canonical_bytes`: for every stored row of a
journal containing the full value sweep (nested mappings, list versus tuple at every depth, empty and full
bytes, Unicode including astral and a lone surrogate, control characters, integers to 10**100 and negative,
+0.0 and -0.0, subnormal, max, +/-inf, quiet and signalling NaN payloads with sign bits, bool beside int beside
float beside their string forms), `canonical_tagged_bytes(tree) == canonical_bytes(tree) == body`,
`pack(decode_tagged(tree)) == tree`, and the prefix hash of `body` equals `evidence_hash(envelope)` and the
stored digest. `test_reader_yields_exactly_the_original_entries_with_exact_types` compares the two readers'
outputs with exact-type equality including float bit patterns.

## Bounded memory

Rows are pulled from the SQLite cursor one at a time and yielded immediately; nothing is accumulated, no
prefetch, no cache. `test_entries_stream_row_by_row_and_stop_at_the_first_bad_row` shows the first two rows are
yielded before a corrupt third row is examined. Peak traced allocation during iteration was ~0.1 MB for both
readers on synthetic journals of 300 and 3000 entries (size-independent), see measurements below.

## Corruption rejection (differential, both readers must reject)

27 parametrised cases on a fresh temporary journal: altered canonical bytes with identical JSON semantics,
altered digest column, ordinal gap, wrong kind column, broken previous hash, changed body with stale digest,
changed body with recomputed digest (breaks the next row's chain), deleted middle row, body stored as TEXT,
unknown tag, bool under int, float under int, int under bool, uppercase and short float hex, odd and uppercase
bytes hex, null with payload, tag arity, empty node, JSON object node, duplicate mapping keys, non-string key,
list under tuple tag, envelope not a mapping, envelope missing `kind`, envelope schema changed. Plus tail
mismatch after open (row appended by a writer), incomplete iteration (tail deleted), and `verify` with a wrong
count. Expected-pair validation at open covers wrong count, wrong hash, wrong types, uppercase hash and a
missing file; an empty journal opens only against `GENESIS_HASH`.

## Test results (this slice only, run once)

`PYTHONPATH=".;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests"`
`python -m pytest research/kalshi/frankie_boss/tests/test_verified_journal_reader.py -q` -> **33 passed** (3.07 s).
No existing suite was rerun. No smoke runs, model calls, source replay, cloud/Pod, principal or Memory A action.
No retained database was opened; every journal in the tests is a temporary file written by `EvidenceJournal`.

## Measured performance (synthetic, clearly not the Sunday dataset)

Scratch script (not committed): a temporary journal of N generated envelopes (~4.6 KB canonical bytes each:
a 10-level book, 64 float features, bytes, Unicode, tuples), full iteration, best of three, Python 3.13.7,
Windows 10, this box.

| N | on disk | EvidenceJournal.entries() | VerifiedJournalReader.entries() | speedup |
|---|---|---|---|---|
| 3000 | 13.8 MB | 3.604 s | 1.071 s | 3.37x |
| 300 (tracemalloc on, inflates both) | 1.4 MB | 2.167 s | 0.911 s | 2.38x |

Peak traced memory (tracemalloc, 300-entry run): 0.1 MB for both readers.

Estimate, not measured: the ratio depends on envelope shape. Envelopes dominated by long strings or bytes
(cheap for `pack`) will show less gain; envelopes dominated by many small nodes (deep mappings, float lists)
will show more, because the saving is two `pack` recursions and one `_canon` walk plus one `json.dumps` per row.
The full Sunday dataset was not reread and no number here describes it.

## Integration requirements (for Codex; nothing below is done)

- The reader is a drop-in for the read paths only where the caller already holds an independently trusted
  `(count, head_hash)` pair: `ControllerJournal.__init__` (checkpoint), `ExecutionLedger.__init__` (checkpoint),
  `C15Builder.restore` (`journal_count`/`journal_hash` in state), `context_session` identity replay,
  `agent_file_handoff` native checkpoint verification. Callers that read the live builder journal through the
  writer's own `count`/`head_hash` (`_active()` self-checks, `presented` streams) would have to pass that pair
  explicitly; the reader will not infer it.
- Do not open the active ingestion or recovery databases with this reader while a writer holds them for a
  running recovery; `mode=ro` does not bypass SQLite locking and the tail check would race the writer.
- Existing checkpoint identity checks (`controller_journal`, `execution_ledger`, `c15_builder.restore`,
  `BossTrainingCheckpoint`) are not bypassed or replaced. The reader only replaces the per-row verification
  cost inside a read; every caller-side identity rule stays where it is.
- Code identity: any pin on `c15_journal.py` bytes is unaffected. If a caller pins the reader's own bytes it
  must add `verified_journal_reader.py` to that pin explicitly; nothing does today.
- The exception-class normalisation (item 3 above): two handlers wrap journal opens and re-raise
  `KeyError`/`TypeError`/`IndexError` as `ValueError` (`agent_file_handoff._open` and the handoff export at
  `agent_file_handoff.py:197`). With this reader they receive `ValueError` directly, so the outcome class is
  unchanged; only the message text differs (`malformed evidence value tag` instead of `malformed retained
  journal`). No caller in `research/kalshi/frankie_boss` outside tests depends on the message text.

## Blob hashes (git, LF)

- verified_journal_reader.py 6e43e6f520797273aed24069aed5035528181071 (fresh tail reread; was ef9ab457b1bc4714b5bc522233fa5145774b8162)
- tests/test_verified_reader_concurrent_tail.py beba7319dc488bf812f049ce2e121b45f7669630
- tests/test_verified_journal_reader.py 1a4248a2304ae7168ada9a4308177d18923db7f4
