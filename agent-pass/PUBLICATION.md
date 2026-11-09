# Verified GitHub publication

The local-only storage rule is removed. Code/findings/handoffs live in Markets. Data/tables/renders/workbooks/provenance live in markets-data. Existing E-drive files are migration sources only. No desktop research computation or UI; no AWS/S3.

## Completed native dipole snapshot

- Repository: [DavisAI1974/markets-data](https://github.com/DavisAI1974/markets-data).
- Immutable commit: `0487d83b1ddb1abe5e4cfae12e8b88797801f428`.
- [Snapshot index](https://github.com/DavisAI1974/markets-data/tree/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180).
- [Manifest](https://github.com/DavisAI1974/markets-data/blob/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/MANIFEST.json), SHA256 `2191b7af9a9c29b69f1cfcbbaebef2d3ace1004518c07e2e5f7a93f8acd751ad`.
- 593 artifact files, 361,592,154 stored bytes: 337 figures, 206 tables, core workbook, receipts, derived caches/previews, losslessly compressed workbook inspection, five supplied historical crypto images and four supplied Desktop figures.
- Verification: each staged/committed artifact was checked against its manifest SHA256 and byte count. A fresh shallow network fetch into an independent bare repository then verified all 593 remote artifact blobs against those hashes and sizes. No research was recomputed.
- Original pinned source blobs retain their recorded Git revisions/paths/hashes in the manifest; they were not duplicated into this snapshot.
- Existing markets-data input paths and original MANIFEST.json were preserved. Corrections use new snapshot paths.

[Figures](https://github.com/DavisAI1974/markets-data/tree/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/figures) Â· [Tables](https://github.com/DavisAI1974/markets-data/tree/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/tables) Â· [Workbook](https://github.com/DavisAI1974/markets-data/blob/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/research-tables.xlsx)

## Desktop lean snapshot

[Desktop overlay and source tables](https://github.com/DavisAI1974/markets-data/tree/f2aecec2c3ef14c453b4e4badcfb6f2362efd0de/tasks/family-research-20261022/desktop-lean/20261108-9622d038f) are published at `f2aecec2c3ef14c453b4e4badcfb6f2362efd0de`. The manifest records 11 original-byte artifact copies (including one explicit preview duplicate) from Markets commit 9622d038f. All committed artifact SHA256 values and byte sizes match; the remote branch commit matches the local commit. Code remains in Markets. The user clarification about the historical 2,000-event average is retained in the snapshot README and FINDINGS ledger.

## Preventing the removed rule from returning

Corrected agent-pass AGENTS, EXECUTION, NEXT_CHAT_HANDOFF, FINDINGS, PROGRESS, PENDING_PUBLICATION, and all three report/inventory generators that repeated the old policy. Corrected the discovered persistent memory entry, its index and the Git-source-of-truth memory. Repository-wide entry-point and historical-reference corrections are published separately on [codex/github-storage-policy-20261108](https://github.com/DavisAI1974/Markets/tree/43f89e00e68b159d6e242c33f9355d2bef934cfc), without switching another session's branch or including its unrelated code changes.

## Migration scope still outstanding

This receipt covers the native dipole research snapshot, not the entire E drive. The broader Markets audit found additional untracked/ignored market history and research files, including multi-gigabyte raw history and files over GitHub's per-file size limit. Their transfer and lossless splitting/compression still need an exact manifest and verification. Credential files found among scratch inputs are excluded from repository publication. Existing source files have not been deleted. Unrelated projects on E are not covered by this receipt.

Continue research from GitHub on remote compute, using the two repository commits and immutable artifact paths above. Do not resume desktop computations or recreate a local-only publication hold. PR15 remains draft and unmerged.
