# Full digest integration — 2026-09-23

Extends SPEC_DIGEST_STREAMING_20260922.md. Existing calculation layers are retained; the repository term bedrock does not mean the Amazon Bedrock service. No new model provider is added.

API: frankie_box_digest_sources.BedrockSources(entries, scratch_directory) snapshots independently pinned persisted JSON and exposes replayable disk-backed ordered tables, derived count, layer count and traversal verdict. Metadata stays bounded by layer/column count; row and dictionary cardinality stay on disk. It preserves the reference renderer's member union, typed conflicts, ordering, first-nonempty lifecycle selection and companion tables.

API: frankie_box_digest_document.write_digest(destination, receipt, layers, prices, frames, structures, roll, first, buys, sells, *, bedrock_entries, scratch_directory) accepts one-pass legacy iterables and exact producer flow arrays. Families aggregate on disk with first-seen ties. Per-second generation preserves cumulative arithmetic order. The table codec independently inverts each table; assembly checks copied block hashes and publishes only fully verified fresh output with no overwrite, retaining all scratch evidence.

Session.derive uses this file writer instead of full layer loads/string rendering. The existing derivation preservation path retains previous artifacts; the digest proof joins its preserved siblings. File witnessing hashes incrementally. Compatibility render APIs remain available to small callers.

Test first: observe missing-module/method failures, then compare complete document bytes to renderer at immutable e297553a7c96dd615879e5aa8e5c5a0118aeaff2 in isolated Linux Actions. Cover one-pass inputs, late/global ordering, typed floats/nanoseconds, sections, corruption/write failures and existing destinations. Fresh-process resource checks cover layer source growth; complete production workload capacity is still separately measured.

No original ingestion replay or model/runtime action. Real launch inputs and native deployment gates remain required. project_sections, exact whole-input tokenizer and reading/writing memory remain separate boundaries; do not label an estimate as exact or drop any scientific output. Root owns integration/ref updates; two source owners work in parallel with host preservation and deployment audit.
