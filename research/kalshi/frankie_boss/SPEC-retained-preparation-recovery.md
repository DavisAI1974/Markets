# Exact retained first-prefix preparation recovery

recover_retained_preparation(context,witness,as_of=...,through_cursor=...,progress=...) returns (tokens,info,input_hash,teacher,rows). The witness schema RETAINED_FIRST_PREPARATION_RECOVERY_V1 contains request/prepared/initialization {path,sha256} and prefix {path,sha256,count,head_hash}. The host must independently pin the witness manifest before passing it.

The helper supports the complete contiguous first-prefix context only, with no QSV. It verifies retained request/prompt/compact/native hashes, original receipt fields and source scope, exact native model/registry and teacher binding/initialnormalizer. Native inverse reconstruction recovers tensors; RecordPrefixChain reconstructs every source prefix from normalized records, with every packet hash checked. Info uses the original ordered PACKET_FIELDS; arbitrary dict reordering changes the input hash and was rejected during the new seam. The original input tensor hash must match.

The only missing calculation is teacher.attach. It receives one fully verified INPUT/APPLIED stream from the independently pinned CLOSED first-prefix database. It does not restore/apply an adapter or read the full Sunday journal. Source journal count/head/path, group chronology, full original APPLIED evidence, teacher targets/raw/normalizer step receipts and exact saved attachment hash remain required. A differing teacher hash fails; there is no patching or fallback. One model/teacher identity check follows calculation. No native forward or remote operation exists in this helper.

Host integration: temporarily supply an exact-cutoff closure through context._prepare while constructing the existing PreparedContextCache, restore the original method in finally, then install cache.prepare through the normal host lifecycle. Cache's existing pre/post model/source/teacher/checkpoint checks remain intact. The helper itself neither mutates pinned cache modules nor claims persisted cache support.

New synthetic seam recovered the entire tuple bit-for-bit against original preparation for three varied source records, with native forward and full _prepare forbidden during recovery. It observed exactly six verified journal envelopes in one pass and passed in9.90seconds. No real retained preparation was executed, and no previously passing suite was repeated. Subsequent explicit closed-source/registry guards are narrow fail-closed validation reviewed separately.

Continuation verification (2026-09-15): three new synthetic refusal cases passed
in 14.61 seconds for registry mismatch, nonempty WAL, and mismatched cached
journal handle. Each forbids constructing the verified teacher reader, proving
refusal occurs before the teacher scan. The earlier full-tuple and early-prefix
passing tests were deselected and were not repeated. Actual recovery is reserved
for the host cache constructor so its one teacher-only pass remains reusable in
memory; the independently pinned witness is supplied by host configuration.
