# Pinned native MBO source ingestion V1

Additive local-file pipeline: verified source snapshot -> exact DBN decoding ->
complete raw mapping -> SourceConformanceDriver/C15 -> trusted checkpoint and
native encoder with explicitly declared registry extensions. Synthetic actual SDK
records are the acceptance fixtures. No provider call or market-data run occurs.

Pin databento-dbn 0.62.0, zstandard 0.25.0, their installed runtime binary hashes,
the extractor source hash,
and an explicit DBN metadata version (1, 2 or 3). Decode AS_IS: no version upgrade,
timestamp conversion, dataframe, symbol guessing, filtering or aggregation.
Every record must be actual MBO. Other record kinds, schema/version disagreement,
partial metadata/records, trailing bytes and incomplete Zstandard frames fail.
Concatenated Zstandard frames are supported without ignoring their suffixes.

Copy each supplied local source into a private temporary file while computing its
SHA-256 and size; compare both against the trusted SourceScope before creating
the C15 journal or ingesting any record. Decode the verified copies, not reopened
source paths. Source list and explicit per-member session identities must match
the scope roster. The caller owns authorization and scope provenance.

Preserve the original record bytes, all 14 public native fields, hidden record
length, and optional ts_out (None when physically absent). Bind the extraction
pin into every mapping. The SDK must reproduce each framed record byte-for-byte.
The raw record header length and all fields remain exact integer/string/bytes
values. No pretty-price or pretty-timestamp values are used. Original metadata
bytes are retained in the ingestion result and bound by the verified source hash.

Use NativeRegistry(extra_fields=SOURCE_EXTRA_FIELDS); the base registry and all
existing source/C15/forecast modules remain unchanged. Completion requires the
existing driver's exact roster counts, group closure and journal verification.
The returned C15 checkpoint is a caller-owned copy whose trusted hash is in the
immutable completion receipt. Failed ingestion retains any existing journal and
produces no completion result; it does not truncate or silently resume.

Tests prove actual SDK byte round-trip (including large IDs, signed fields and
ts_out), plain and compressed verified-file ingestion, checkpoint restore and
native tensor reconstruction, wrong hashes/pins/schema, non-MBO and truncation
failures. Throughput and production operational acceptance remain unmeasured.
