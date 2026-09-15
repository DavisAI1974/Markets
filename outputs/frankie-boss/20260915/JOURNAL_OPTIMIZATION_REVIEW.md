# Journal size and CPU optimization review

Date: 2026-09-15. Code review plus one bounded, read-only experiment on a closed independent journal copy, applying `performance-optimization/SKILL.md`.
Code checkout: `Markets-full-frankie`, frozen launch commit `35982ac7d42b546446038866299c23ca4fc50edc`.

## Conclusion

Lossless improvements can be stacked. The bounded experiment measured 9.11x to 11.57x compression of a 128-row sample, and exact order sharing plus compression achieved 21.48x on three adjacent completed observations. All sampled observation bytes reconstructed exactly. **24x is not a verified result.** The 21.48x result is a small storage prototype measurement, not whole-journal performance or the current runner's journal format.

For CPU work, the existing faster reader can support final source conformance and return completion and checkpoint from one verified immutable state. The original source worker uses the older reader and performs that verification twice. Parallel workers, one conformance pass, compressed transport, and future compact storage address different costs; their combined speedup must be measured rather than obtained by multiplying ratios. The reviewed parallel runner remains unchanged by this exploration.

This work changed no repository code, existing process, journal, model, Pod, account, or launch pin. It created only the isolated experiment script, result and this report. The experiment opened the closed independent backup read-only, sampled 128 rows totaling 10.75 MB, and performed bounded new microbenchmarks. It never opened the active original database, reread the full journal, or reran passing tests. Detailed measurements, identities and limitations appear in the addendum.

## What is already built

| Component | Status and scope |
|---|---|
| Exact stacked model context | Built and configured for Sunday. SPEC-granite-context-stacked.md identifies 929,730 tokens for the first 3,262-record compact input. Current launch handoff records 92,427 input tokens for the stacked request: approximately 10.06 times fewer. It preserves decoded typed evidence. This is a model-input representation change, not source record removal or journal compaction. |
| VerifiedJournalReader | Built. One JSON parse, validating tagged decode, one canonical serialization, and hash of already-validated bytes per row. Legacy EvidenceJournal.entries repeats packing and serialization. |
| Faster-reader integrations | Present in source_recovery.py, completed_schedule_view.py, retained_preparation_recovery.py, journal_prefix_snapshot.py, and operations/run_actual_sunday.py. Its module header and original specification saying it is not wired anywhere are stale. |
| Single-pass recovery | Present in source_recovery.py. It verifies the retained parent once and compares generated canonical envelopes to original raw bodies. It does not skip adapter rehydration. |
| Final source conformance | Still uses the old EvidenceJournal.entries through SourceConformanceDriver._verified_checkpoint. The active resume script calls complete(), then checkpoint(), both calling _verified_checkpoint. |
| Journal compression / delta storage | Absent from the inspected production writer/reader and current runner's journal format. Existing body bytes are uncompressed, exactly typed canonical JSON. An isolated sample order-dictionary prototype and compression measurements are complete; they are not deployed. |

The latest small periodic checkpoint receipt already binds cursor 57,027, journal count 114,054, journal head `d8de0394367b66ea034d2553c3dd45fb7b1ae2b3c92724f8817627118f173500`, and state hash `d46ec93352cfa63fab20e260bb608b0b76e71e5ca10cacd952de6b912bea2d64`. That receipt alone is not the final source conformance result.

## Why the journal is large

1. c15_builder.py:65 commits INPUT containing the complete raw record and provenance, before applying the record.
2. c15_builder.py:100-113 commits APPLIED containing raw record again, normalized fields, effect, order before/after and ranks, observation, frame, legacy rows, receipt, integrity, boundaries and prefix/count commitments.
3. c15_observer.py:14-25 copies every resting order and every FIFO price-level list at each completed group. These are full snapshots, so unchanged orders recur across nearby groups.
4. c15_journal.py:47-68 wraps each node with an explicit type tag. Bytes and exact float bits use hex. This preserves distinctions required by the evidence contract, but adds space and many Python objects on decode.

Thus 57,027 updates yield 114,054 stored entries, with substantial repeated structure. The reported 11.7 GB size is consistent with this design. The follow-up sample measured observations at about 91% of sampled body bytes and demonstrated substantial lossless compression. No full-journal field inventory or full-journal codec reduction ratio was measured by this experiment.

## Ranked actions

### 1. Finish-source conformance using the existing verified reader

Create an independent read-only finalization path accepting a separately pinned immutable checkpoint and a consistent, separate SQLite snapshot. Preserve all SourceConformanceDriver checks: scope, INPUT/APPLIED pairing and values, normalized provenance, recomputed prefix chain, group receipts/counts, checkpoint adapter/prefix state, journal count and head, exact source implementation identity.

Use VerifiedJournalReader for cryptographic/canonical traversal. Do not replace those semantic checks with reader.verify(): the reader verifies journal integrity, not full source conformance. Pin the independent verifier and reader implementation as additional audit identities; do not alter the source producer identity or launch checkout.

Existing SPEC-verified-journal-reader.md reports a synthetic 3,000-entry, 13.8 MB traversal: legacy 3.604 s, faster reader 1.071 s, 3.37x. These are small synthetic measurements; Sunday finalization also recomputes source-prefix receipts, so its speedup may differ materially. There is no measured Sunday speedup yet.

### 2. Produce completion and checkpoint from the same verified state

SourceConformanceDriver.complete() obtains verified state and counts, creates completion, then discards the state. checkpoint() repeats the entire scan. A combined finalization operation can return both artifacts from that one verification, removing one duplicate scan without removing any unique check.

A cache is valid only for the exact same immutable snapshot, checkpoint bytes/state hash, scope, journal count/head, verifier identity and source implementation identity. Never reuse it merely because a filename, count, timestamp or elapsed time matches. An externally writable database requires an enforced immutable copy or equivalent protected snapshot; rereading only its tail does not prove old interior rows are unchanged. Do not reuse an incompletely consumed iterator as a verification success.

This is structurally one scan instead of two for that finalization stage; it is not a measured 2x whole-run speedup. Preserve fresh mutable return values or immutable owned state so callers cannot mutate a cached proof.

### 3. Compress original bytes for GitHub transport / archival

A separate compressed snapshot can preserve every source byte and be checked against its own compressed hash plus the decompressed physical hash and independently pinned logical checkpoint. The bounded follow-up measured gzip levels 1 and 6 on a sample of the independent snapshot; details are below. Use the parent's separate whole-archive result for actual transfer size rather than extrapolating the sample.

This does not reduce 57,027 records, change calculations, or reduce JSON traversal CPU after decompression. A compressed upload also does not eliminate the runner's decompressed disk requirement. Streaming compressed verification would require a new transport/container reader, with checks for full consumption, truncation, size and identity; the existing SQLite reader cannot consume a compressed archive directly.

### 4. Versioned lossless storage codec for future journals

The smallest storage design is independently compressed canonical body blobs or bounded blocks, with original uncompressed bytes reconstructed before existing canonical validation and logical hashing. Keep ordinal/kind/digest and the original hash-chain authority. Version the physical container, compression parameters, bounded uncompressed lengths, indexes and codec identity; keep original evidence retained and provide exact-byte export.

Larger possible savings come from exact dictionary sharing, repeated subtrees, and deltas between observations. These must reconstruct every original order snapshot, list/dict ordering, null/absent distinction, float bit pattern, raw field, and receipt before accepting an existing logical identity. Reconstruct from stored exact values/deltas, not by rerunning scientific calculations under potentially different code. Such a format needs corruption, truncation, random-access and exact round-trip evidence before migration. The already-built model-context codec is not a drop-in journal codec.

The follow-up demonstrates size savings for sampled bytes and a small exact order-sharing prototype. A full-journal format reduction ratio and net CPU reduction remain unestablished. Compression adds decompression work; reducing disk traffic and reducing Python object traversal are different optimizations.

### 5. Reduce repeated prefix work in a later isolated change

journal_prefix_snapshot.py copies and fully verifies each selected prefix independently. Many prefixes overlap. A future immutable shared-parent reader could verify once and issue separately bound cutoff witnesses, or batch one forward traversal across all nineteen cutoffs. It must preserve each original through-cursor, terminal digest, F_LAST closure, selection seed, and no-future-data rule. Current actual-host receipts expect physical snapshots; replacing them with shared-parent views is an interface/security change, not a trivial path substitution.

For the current run, independent GitHub verification can proceed without changing the frozen launch code. A competing result must pass an explicit result-acceptance gate before it can replace any local handoff; never race mutable shared output filenames.

## Minimal next step

Use the consistent independent snapshot and pinned final periodic checkpoint for one instrumented read-only finalizer on GitHub. Use VerifiedJournalReader plus unchanged semantic conformance checks and produce completion/checkpoint together. Report input bytes, entries verified, read/CPU/wall time, checkpoint/hash equality and result provenance. Preserve the advancing original worker. This measures an actual improvement while leaving the paid run code and original evidence untouched.

Separately measure compression of that independent snapshot if transfer/disk is the immediate bottleneck. Do not mix storage-codec redesign into the Sunday launch without a separate reviewed implementation and new identity pins.

## Bytes read for this review

SHA256 values are of local file bytes, including their existing line endings. Paths below are relative to research/kalshi/frankie_boss in the frozen checkout.

| File | SHA256 |
|---|---|
| c15_journal.py | 898b1671c867b8b10b664dd948cc73890a79fa786b6244dfe5164d6c6503586e |
| c15_builder.py | 6f1c9050a7e1da226fe1828c4667020d2536e2607971c468df96f615edba66bd |
| c15_observer.py | 223a7841f79b9e530cbe1b96f4c058f9bd23e73016f329ba977e2078a27d7871 |
| source_conformance.py | 0dd7e21b6533f5f8a68722678f147e41d2ebbea766f796b801eeb3daabb66876 |
| verified_journal_reader.py | 2e23c8d680320f498c18caa95625ed6747c62166f20ee25e68889d7984382fa4 |
| source_recovery.py | 7d3543803bffd17270ead68821a4a8250c07fcb0baccfc8ee89964a1a35747f8 |
| journal_prefix_snapshot.py | 1a982ba18f322bd52381a85011b0d65c690a762f323385afabfa2c66985b385f |
| completed_schedule_view.py | 86207e234be206717e81fe05c4170ed471a16c4ab9bb63870ff81b81dde0f25e |
| SPEC-verified-journal-reader.md | f17a4d2a209bbe9723ebfaa24657f338a7613d6039be56070a1de2c711631976 |

## Follow-up: stack improvements, do not treat 3.37x as a ceiling

The user explicitly requested exploration beyond the original reader result and composition of improvements. A new bounded experiment was run once after `snapshot-progress.json` reached `snapshot_hash`, which the snapshot producer writes only after closing both SQLite backup connections. It opened only `github-parallel/bundle/source.sqlite` read-only with immutable semantics, checked its tail against the separate final periodic checkpoint, and compared file size/mtime before and after reading. The active original database was never opened.

Experiment: `optimization/sample_journal.py`; retained results: `optimization/sample-results.json`. It read 128 rows totaling 10,748,549 canonical body bytes: 48 evenly spaced INPUT/APPLIED pairs plus 16 adjacent pairs, capped at 32 MiB. No row was skipped by the cap. This is a fixed sample, not a statistically weighted estimate of the whole database. Parent hashing/compression and original source verification continued concurrently. Total experiment command wall time was about 9.6 seconds.

### Measured storage shares and lossless byte compression

| Sample component | Bytes | Interpretation |
|---|---:|---|
| INPUT bodies | 80,867 | About 0.75% of sampled canonical body bytes |
| APPLIED bodies | 10,667,682 | About 99.25% |
| observation field values | 9,784,157 | About 91.0% of all sampled body bytes; includes complete book snapshots |
| frame field values | 592,893 | About 5.5% of all sampled body bytes |

Field counts exclude their field-name/envelope overhead. The observation result substantiates the original code-based suspicion: full book snapshots dominate this sample. Reducing record count is unnecessary to target that redundancy.

| Full 128-row sampled byte stream | Stored bytes | Reduction against original sampled stream |
|---|---:|---:|
| Original canonical bodies, newline separated | 10,748,676 | 1.00x |
| gzip level 1 | 1,180,249 | 9.11x |
| gzip level 6 | 929,197 | 11.57x |

Both decompressions reproduced the original bytes exactly. Level 6 was 21.3% smaller than level 1 in this sample. Compression CPU readings were 0.015625 s and 0.078125 s respectively, with decompression 0.03125 s each; these are coarse Windows process-CPU ticks, not trustworthy fine-grained latency comparisons. Use the parent's real whole-archive result for actual transfer size. Do not extrapolate this sample into an 11.57x full-journal guarantee.

### Measured composition: exact order sharing plus compression

The 16 adjacent records contained three completed-group observations. The prototype stores each distinct complete typed order once and represents the observation's ordered order list by dictionary indices, retaining every other observation field unchanged. The decoder reconstructed byte-identical canonical observations, including order-list ordering, field ordering and exact types. It is an isolated storage experiment, not a production codec.

The three observations contain 617,472 bytes of repeated order objects but only 206,112 bytes of distinct order objects (717 distinct orders).

| Same three observations | Bytes | Reduction against original observations |
|---|---:|---:|
| Original | 777,745 | 1.00x |
| Exact order dictionary only | 400,633 | 1.94x |
| Original plus gzip level 1 | 76,934 | 10.11x |
| Order dictionary plus gzip level 1 | 43,821 | 17.75x |
| Original plus gzip level 6 | 59,942 | 12.97x |
| Order dictionary plus gzip level 6 | 36,200 | 21.48x |

The combined level-6 result is directly measured, not a multiplication of standalone ratios. Adding order sharing before gzip made the final representation 39.6% smaller than gzip alone on these three observations. This demonstrates that the approaches can compose; three observations cannot establish the whole-journal ratio. No order was discarded and no calculation was rerun.

### Reader plus compressed bytes: exploratory CPU observation

One fixed 16-row subset (1,119,337 bytes) compared the original row validation, existing fast reader validation, and fast validation after gzip decompression. Each variant ran once and checked canonical bytes and stored digest for each sampled row. It did not claim complete journal continuity or semantic source conformance.

| Variant | Process CPU seconds |
|---|---:|
| Legacy row validation | 0.234375 |
| Existing fast reader validation | 0.031250 |
| gzip level 1 decompression plus fast validation | 0.031250 |
| gzip level 6 decompression plus fast validation | 0.078125 |

The raw ratio of legacy to fast is 7.5x on this tiny subset. It must not be promoted as a dependable performance gain: timer granularity is coarse relative to the fast duration, sample order is fixed, there is one observation per variant, and concurrent system work continued. It shows why the earlier synthetic 3.37x is not a ceiling. The direct combined measurement also shows that compression and CPU savings must be evaluated together rather than multiplying unrelated ratios.

### Prioritized combined implementation stack

1. **Existing faster reader:** reduce repeated Python packing/canonicalization while preserving exact acceptance and digest rules. Already used in the independent parallel verifier prepared by the parent; preserve its reviewed code.
2. **One immutable conformance pass:** derive final checkpoint and completion from the same full semantic verification, with checkpoint/source/verifier bindings. The old path visits 228,108 rows across two scans; the combined operation requires one 114,054-row conformance traversal. This is a work-count reduction, not a measured whole-run 2x claim.
3. **Independent process partitions:** use the parent's reviewed parallel verifier and its seam/aggregate checks. Return compact witnesses rather than shipping decoded book objects over multiprocessing pipes. Sum worker coverage and validate adjacent chain/pair boundaries; multiprocessing alone must not bypass sequential source-prefix semantics. Real elapsed and total CPU results remain pending. Three workers do not imply 3x speedup, especially under shared disk/memory limits.
4. **Compressed transport immediately; compact storage separately:** use the already-prepared compressed snapshot for transfer. A future indexed compressed-body container can preserve original logical hashes while shrinking storage. It needs an explicit version, decoder identity, uncompressed-length bounds and error handling, plus complete exact-byte export. Transfer compression does not remove the current runner's decompressed SQLite space requirement.
5. **Exact shared order objects / deltas before compression:** extend the demonstrated order dictionary to bounded blocks, allowing independent partition decode and bounded memory. Preserve all other observation values, list ordering and the original canonical digest after reconstruction. A block dictionary or exact mutation delta can reduce repeated full snapshot storage. New format and implementation pins are required; do not mutate retained V1 evidence in place.
6. **One scan across cutoff consumers:** later batch cutoff witnesses over an immutable verified parent instead of repeatedly reading overlapping full prefixes. Preserve each causal cutoff and no-future-evidence boundary; current physical-snapshot interfaces require a separately reviewed change.

CPU ratios, storage ratios and wall-time parallel speedups describe different quantities. No combined total speedup is claimed until the combined path is measured on the same fixed input with complete conformance evidence. The current exploration demonstrates a measured storage stack reaching 21.48x for a small observation sample and identifies additional compatible CPU work reductions. It does not stop at 3.37x or promise that 21.48x applies to Sunday as a whole.

### Continuation and experiment identity

Keep the original worker, frozen launch checkout and current reviewed GitHub verifier intact. The next measurement should be the already-authorized real parallel verification's result, not another passing test or duplicate full scan. If future storage work is authorized, build a versioned bounded-block codec in a separate checkout, compare original and reconstructed canonical row bytes and complete logical checkpoint, and measure its compression/decode cost separately before integrating it.

- Sample script SHA256: `8ad905acbcc37032e657d345a15a27c7366076d512a54fc990e43c998ab602e5`.
- Sample result SHA256: `4a40eba582b9388f7bbca43024369fab36f930179c6fc5850a0f852141d8a707`.
- Input sample SHA256 and exact selected ordinals are retained in sample-results.json.
- The script refuses to run while the backup is open and refuses to overwrite an existing result. No automatic rerun is requested.
